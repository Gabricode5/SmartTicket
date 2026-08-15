"""Tests du rollback best-effort de provision() sur échec partiel — cf.
ops/provision_client.py::_rollback().

Seule couverture de test existante pour ops/ à ce jour : ce dossier manipule des ressources
Render facturées, et le rollback est du code qui ne s'exécute QUE quand tout va déjà mal — sans
test durable, on ne découvre qu'il est cassé que le jour où on compte vraiment dessus.

Lancer : cd ops && pip install -r requirements-dev.txt && pytest
"""
from unittest import mock

import pytest

import db
import provision_client
import render_client  # module réel, non mocké — pour lire ses vraies constantes dans les tests


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Chaque test tourne sur son propre fichier SQLite jetable — jamais le vrai
    ops/instances.db du poste (qui contiendrait de vraies instances clientes)."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_instances.db")


@pytest.fixture
def render_mock():
    with mock.patch.object(provision_client, "render") as render_mock:
        yield render_mock


@pytest.fixture
def notify_mock():
    with mock.patch.object(provision_client, "notify") as notify_mock:
        yield notify_mock


def _mock_common_steps(render_mock, *, postgres_id: str):
    render_mock.get_owner_id.return_value = "owner-1"
    render_mock.create_postgres.return_value = {"id": postgres_id}
    # Explicite plutôt que de compter sur la vérité par défaut d'un MagicMock non configuré
    # (cf. render_client.wait_for_postgres_available(), ajoutée le 2026-07-15 pour la race
    # condition sur GET .../connection-info juste après la création d'une base Postgres).
    render_mock.wait_for_postgres_available.return_value = True
    render_mock.get_postgres_connection_info.return_value = {"internalConnectionString": "postgres://x"}
    render_mock.wait_for_deploy_live.return_value = True
    # get_service() est désormais LA source de vérité pour l'URL réelle d'un service — plus
    # jamais devinée depuis son nom (bug réel du 2026-08-15, cf. provision_client.py) — donc
    # plus jamais lue depuis la réponse de create_web_service. URL dérivée de l'id demandé :
    # déterministe et distincte par service, pour que chaque test s'y retrouve facilement.
    render_mock.get_service.side_effect = lambda service_id: {
        "id": service_id, "serviceDetails": {"url": f"https://{service_id}.onrender.com"},
    }


def _mock_frontend_creation_failure(render_mock, *, backend_id: str):
    """Backend créé avec succès, la création du frontend échoue — le point d'échec utilisé
    par tous les tests de rollback ci-dessous : il garantit 2 ressources déjà créées
    (Postgres + backend) au moment où provision() doit déclencher le rollback."""
    render_mock.create_web_service.side_effect = [
        {"id": backend_id, "serviceDetails": {"url": f"https://{backend_id}.onrender.com"}},
        RuntimeError("Render 500: échec de création du frontend"),
    ]


def test_full_success_never_calls_delete_and_marks_instance_active(render_mock, notify_mock):
    _mock_common_steps(render_mock, postgres_id="pg-1")
    render_mock.create_web_service.side_effect = [
        {"id": "backend-1", "serviceDetails": {"url": "https://backend-1.onrender.com"}},
        {"id": "frontend-1", "serviceDetails": {"url": "https://frontend-1.onrender.com"}},
    ]
    notify_mock.send_welcome_email.return_value = True

    result = provision_client.provision(
        client_name="Acme", slug="acme-success", postgres_plan="starter", admin_email="a@acme.com",
    )

    assert result.status == "active"
    render_mock.delete_resources.assert_not_called()
    # provision() doit transmettre la version PostgreSQL par défaut à render.create_postgres()
    # (paramètre requis côté API Render depuis le 2026-07-14, cf. render_client.py) — vérifie
    # le câblage bout-en-bout, la forme exacte du payload est couverte par test_render_client.py.
    _, postgres_kwargs = render_mock.create_postgres.call_args
    assert postgres_kwargs["version"] == render_client.DEFAULT_POSTGRES_VERSION
    row = db.get_instance("acme-success")
    assert row["statut"] == "active"
    assert row["render_backend_service_id"] == "backend-1"
    assert row["render_frontend_service_id"] == "frontend-1"


def test_partial_failure_rolls_back_in_reverse_order_and_frees_slug(render_mock, notify_mock):
    _mock_common_steps(render_mock, postgres_id="pg-2")
    _mock_frontend_creation_failure(render_mock, backend_id="backend-2")
    render_mock.delete_resources.return_value = []  # rollback réussi à 100%

    result = provision_client.provision(
        client_name="Acme2", slug="acme-rollback-ok", postgres_plan="starter", admin_email="a@acme2.com",
    )

    assert result.status == "failed"
    assert "ROLLBACK INCOMPLET" not in result.error

    # Postgres créé en premier, backend en second → suppression dans l'ordre INVERSE :
    # backend d'abord, Postgres ensuite.
    (called_resources,), _ = render_mock.delete_resources.call_args
    assert [label for label, _, _ in called_resources] == ["service backend", "base Postgres"]
    assert [rid for _, _, rid in called_resources] == ["backend-2", "pg-2"]

    assert db.get_instance("acme-rollback-ok") is None
    assert not db.slug_exists("acme-rollback-ok")


def test_incomplete_rollback_burns_the_slug_and_reports_orphans(render_mock, notify_mock):
    _mock_common_steps(render_mock, postgres_id="pg-3")
    _mock_frontend_creation_failure(render_mock, backend_id="backend-3")
    render_mock.delete_resources.return_value = [("service backend", "service", "backend-3")]

    result = provision_client.provision(
        client_name="Acme3", slug="acme-rollback-fail", postgres_plan="starter", admin_email="a@acme3.com",
    )

    assert result.status == "failed"
    assert "ROLLBACK INCOMPLET" in result.error
    assert "backend-3" in result.error

    row = db.get_instance("acme-rollback-fail")
    assert row is not None, "la ligne doit être CONSERVÉE (pas supprimée) après un rollback incomplet"
    assert row["statut"] == "failed"
    assert "backend-3" in row["notes"]


def test_burned_slug_blocks_retry_without_touching_render_again(render_mock, notify_mock):
    _mock_common_steps(render_mock, postgres_id="pg-4")
    _mock_frontend_creation_failure(render_mock, backend_id="backend-4")
    render_mock.delete_resources.return_value = [("service backend", "service", "backend-4")]

    first = provision_client.provision(
        client_name="Acme4", slug="acme-burned", postgres_plan="starter", admin_email="a@acme4.com",
    )
    assert first.status == "failed"
    assert db.slug_exists("acme-burned")

    retry = provision_client.provision(
        client_name="Acme4", slug="acme-burned", postgres_plan="starter", admin_email="a@acme4.com",
    )

    assert retry.status == "failed"
    assert "existe déjà" in retry.error
    # Un seul appel Render au total (celui du premier essai) : le retry n'a rien recréé.
    render_mock.create_postgres.assert_called_once()


class TestFrontendReceivesTheRealBackendUrl:
    """Bug trouvé le 2026-07-14 (frontend recevait NEXT_PUBLIC_API_URL vide à son premier
    build) corrigé à l'époque en PRÉDISANT l'URL *.onrender.com par avance — cette prédiction
    s'est révélée FAUSSE en conditions réelles le 2026-08-15 : Render peut assigner une URL
    différente du nom de service demandé (suffixe supplémentaire imprévisible constaté sur
    l'instance martin-technologies, ex. "...-9abaae-xml6.onrender.com" au lieu de
    "...-9abaae-backend.onrender.com"). provision() ne prédit donc plus AUCUNE URL
    *.onrender.com : elle les relit via render.get_service() (serviceDetails.url) juste
    après le premier déploiement de chaque service, jamais reconstruites par convention."""

    def test_provision_reads_backend_url_from_the_api_response_not_from_a_naming_convention(self, render_mock, notify_mock):
        """LE test demandé pour ce bug : la valeur utilisée doit venir de get_service(),
        pas d'une construction à partir du nom du service. Prouvé ici en donnant à
        get_service() une URL qui NE RESSEMBLE PAS au nom du service demandé (suffixe
        totalement différent, comme observé en conditions réelles) — si provision()
        reconstruisait encore l'URL par convention, ce test échouerait."""
        _mock_common_steps(render_mock, postgres_id="pg-5")
        render_mock.create_web_service.side_effect = [
            {"id": "backend-5"}, {"id": "frontend-5"},
        ]
        render_mock.get_service.side_effect = lambda service_id: {
            "backend-5": {"id": "backend-5", "serviceDetails": {"url": "https://smartticket-acme5-9abaae-xml6.onrender.com"}},
            "frontend-5": {"id": "frontend-5", "serviceDetails": {"url": "https://smartticket-acme5-9abaae-abc1.onrender.com"}},
        }[service_id]
        notify_mock.send_welcome_email.return_value = True

        result = provision_client.provision(
            client_name="Acme5", slug="acme5", postgres_plan="starter", admin_email="a@acme5.com",
        )

        assert result.status == "active"
        backend_call_kwargs = render_mock.create_web_service.call_args_list[0].kwargs
        frontend_call_kwargs = render_mock.create_web_service.call_args_list[1].kwargs

        # C'est LE champ qui était vide avant le tout premier correctif — jamais vide, et
        # jamais un fallback localhost/placeholder.
        api_url = frontend_call_kwargs["env_vars"]["NEXT_PUBLIC_API_URL"]
        assert api_url, "NEXT_PUBLIC_API_URL ne doit jamais être vide au moment du build frontend"
        assert "localhost" not in api_url
        # La valeur EXACTE renvoyée par get_service(), pas une reconstruction par convention
        # à partir du nom "smartticket-acme5-...-backend" (qui donnerait une URL différente).
        assert api_url == "https://smartticket-acme5-9abaae-xml6.onrender.com"
        assert result.backend_url == "https://smartticket-acme5-9abaae-xml6.onrender.com"

        # CORS_ORIGINS ne peut être correcte qu'APRÈS coup (le frontend n'existe pas encore
        # quand le backend est créé) — republiée via set_env_vars() puis redéployée, cf.
        # classe suivante pour la vérification dédiée de ce mécanisme.
        render_mock.set_env_vars.assert_called_once()
        updated_env = render_mock.set_env_vars.call_args.args[1]
        assert updated_env["CORS_ORIGINS"] == "https://smartticket-acme5-9abaae-abc1.onrender.com"
        assert updated_env["FRONTEND_URL"] == "https://smartticket-acme5-9abaae-abc1.onrender.com"
        render_mock.trigger_deploy.assert_called_once_with("backend-5")

    def test_provision_passes_custom_domain_url_to_frontend_when_domain_given(self, render_mock, notify_mock):
        """Avec --domain, aucune ambiguïté possible : le domaine est choisi PAR NOUS
        (build_domain_urls()), jamais par Render — get_service() n'est même pas consulté
        pour l'URL, et aucun redéploiement correctif n'est nécessaire."""
        _mock_common_steps(render_mock, postgres_id="pg-6")
        render_mock.create_web_service.side_effect = [{"id": "backend-6"}, {"id": "frontend-6"}]
        notify_mock.send_welcome_email.return_value = True

        result = provision_client.provision(
            client_name="Acme6", slug="acme6", postgres_plan="starter", admin_email="a@acme6.com",
            domain="smartticket.fr",
        )

        assert result.status == "active"
        backend_call_kwargs = render_mock.create_web_service.call_args_list[0].kwargs
        frontend_call_kwargs = render_mock.create_web_service.call_args_list[1].kwargs
        assert frontend_call_kwargs["env_vars"]["NEXT_PUBLIC_API_URL"] == "https://acme6-api.smartticket.fr"
        assert backend_call_kwargs["env_vars"]["CORS_ORIGINS"] == "https://acme6.smartticket.fr"
        render_mock.add_custom_domain.assert_called_once_with("frontend-6", "acme6.smartticket.fr")
        # Déterministe dès la création : jamais besoin de republier/redéployer le backend.
        render_mock.set_env_vars.assert_not_called()
        render_mock.trigger_deploy.assert_not_called()


class TestPostgresAvailabilityIsAwaitedBeforeConnectionInfo:
    """Race condition trouvée le 2026-07-15 en conditions réelles : GET
    .../connection-info répondait 404 ~400ms après POST /postgres, la base étant encore
    'creating'. provision() doit désormais attendre render.wait_for_postgres_available()
    et déclencher le rollback normal si l'attente expire, plutôt que de laisser
    get_postgres_connection_info() échouer bruyamment. Cf. render_client.py et
    ops/tests/test_render_client.py pour la couverture du polling lui-même."""

    def test_provision_waits_for_postgres_before_fetching_connection_info(self, render_mock, notify_mock):
        _mock_common_steps(render_mock, postgres_id="pg-8")
        render_mock.create_web_service.side_effect = [
            {"id": "backend-8", "serviceDetails": {"url": "https://backend-8.onrender.com"}},
            {"id": "frontend-8", "serviceDetails": {"url": "https://frontend-8.onrender.com"}},
        ]
        notify_mock.send_welcome_email.return_value = True

        manager = mock.Mock()
        manager.attach_mock(render_mock.wait_for_postgres_available, "wait_for_postgres_available")
        manager.attach_mock(render_mock.get_postgres_connection_info, "get_postgres_connection_info")

        result = provision_client.provision(
            client_name="Acme8", slug="acme8", postgres_plan="starter", admin_email="a@acme8.com",
        )

        assert result.status == "active"
        # L'ordre exact qui a fait défaut en réel : le polling doit être terminé AVANT le
        # premier appel à connection-info, jamais l'inverse ni en parallèle.
        assert [call[0] for call in manager.mock_calls] == [
            "wait_for_postgres_available", "get_postgres_connection_info",
        ]
        render_mock.wait_for_postgres_available.assert_called_once_with("pg-8")

    def test_provision_rolls_back_when_postgres_never_becomes_available(self, render_mock, notify_mock):
        _mock_common_steps(render_mock, postgres_id="pg-9")
        # Seule différence avec un run réussi : la base ne devient jamais 'available'.
        render_mock.wait_for_postgres_available.return_value = False
        render_mock.delete_resources.return_value = []  # rollback réussi à 100%

        result = provision_client.provision(
            client_name="Acme9", slug="acme9", postgres_plan="starter", admin_email="a@acme9.com",
        )

        assert result.status == "failed"
        assert "ROLLBACK INCOMPLET" not in result.error
        # get_postgres_connection_info() ne doit jamais être appelée si l'attente échoue —
        # c'est justement l'appel qui répondait 404 en conditions réelles.
        render_mock.get_postgres_connection_info.assert_not_called()
        # Un seul service créé (le backend) au moment de l'échec sur le Postgres : aucun
        # web service n'a même été tenté.
        render_mock.create_web_service.assert_not_called()
        (called_resources,), _ = render_mock.delete_resources.call_args
        assert [label for label, _, _ in called_resources] == ["base Postgres"]
        assert [rid for _, _, rid in called_resources] == ["pg-9"]

        assert db.get_instance("acme9") is None
        assert not db.slug_exists("acme9")


class TestSmtpFromSenderValidation:
    """Bug réel du 2026-07-16 : Brevo répondait 401 sur les emails de vérification/reset de
    l'instance provisionnée. La clé BREVO_API_KEY était valide — le problème venait de
    l'adresse expéditrice (backend/email_utils.py retombait sur son défaut
    "no-reply@smartticket.app", jamais validée dans Brevo → Senders), et l'échec était
    intercepté et seulement loggé côté backend, donc invisible. provision() doit maintenant
    refuser de démarrer si BREVO_API_KEY est définie sans SMTP_FROM, et transmettre SMTP_FROM
    à chaque instance provisionnée pour que son backend l'utilise aussi."""

    def test_provision_raises_before_any_render_call_when_brevo_key_set_without_smtp_from(
        self, render_mock, notify_mock, monkeypatch,
    ):
        monkeypatch.setenv("BREVO_API_KEY", "test-brevo-key")
        monkeypatch.delenv("SMTP_FROM", raising=False)

        with pytest.raises(RuntimeError, match="SMTP_FROM"):
            provision_client.provision(
                client_name="Acme10", slug="acme10", postgres_plan="starter", admin_email="a@acme10.com",
            )

        # Échec avant le moindre appel Render, et rien de persisté dans instances.db —
        # exactement comme les échecs de validation existants (ex: slug déjà pris).
        render_mock.get_owner_id.assert_not_called()
        render_mock.create_postgres.assert_not_called()
        assert db.get_instance("acme10") is None

    def test_provision_does_not_raise_when_brevo_key_absent_even_without_smtp_from(self, render_mock, notify_mock):
        """Sans BREVO_API_KEY (email juste loggé côté client, cf. notify.py), l'absence de
        SMTP_FROM est sans conséquence — ne doit pas bloquer un provisioning de test."""
        _mock_common_steps(render_mock, postgres_id="pg-11")
        render_mock.create_web_service.side_effect = [
            {"id": "backend-11", "serviceDetails": {"url": "https://backend-11.onrender.com"}},
            {"id": "frontend-11", "serviceDetails": {"url": "https://frontend-11.onrender.com"}},
        ]
        notify_mock.send_welcome_email.return_value = True

        result = provision_client.provision(
            client_name="Acme11", slug="acme11", postgres_plan="starter", admin_email="a@acme11.com",
        )

        assert result.status == "active"

    def test_provision_passes_smtp_from_to_backend_env(self, render_mock, notify_mock, monkeypatch):
        monkeypatch.setenv("BREVO_API_KEY", "test-brevo-key")
        monkeypatch.setenv("SMTP_FROM", "gabriel.guery10@gmail.com")
        _mock_common_steps(render_mock, postgres_id="pg-12")
        render_mock.create_web_service.side_effect = [
            {"id": "backend-12", "serviceDetails": {"url": "https://backend-12.onrender.com"}},
            {"id": "frontend-12", "serviceDetails": {"url": "https://frontend-12.onrender.com"}},
        ]
        notify_mock.send_welcome_email.return_value = True

        result = provision_client.provision(
            client_name="Acme12", slug="acme12", postgres_plan="starter", admin_email="a@acme12.com",
        )

        assert result.status == "active"
        backend_call_kwargs = render_mock.create_web_service.call_args_list[0].kwargs
        # C'est ce champ qui était absent avant le correctif — le backend de l'instance
        # provisionnée retombait silencieusement sur une adresse expéditrice non validée.
        assert backend_call_kwargs["env_vars"]["SMTP_FROM"] == "gabriel.guery10@gmail.com"


class TestSlugReuseGeneratesFreshRenderNames:
    """Bug réel du 2026-07-17 : un slug tout juste supprimé (delete_client.py) puis
    immédiatement réutilisé pour un nouveau provisioning produisait un 404 sur /setup. Le
    schéma OpenAPI de Render confirme que `name` doit être unique DANS LE WORKSPACE pour
    POST /services comme POST /postgres ("must be unique within the workspace") — une
    contrainte réelle, pas supposée — mais ne documente ni le délai de libération d'un nom
    après suppression côté Render, ni la propagation DNS/edge du sous-domaine associé : deux
    détails opérationnels hors du contrat d'API, invérifiables depuis le schéma seul.
    render_suffix (cf. generate_render_suffix() dans provision_client.py), généré à CHAQUE
    provisioning et jamais réutilisé, rend le nom de chaque ressource Render globalement
    neuf — il ne peut plus jamais entrer en collision avec une ressource récemment
    supprimée sous le même slug métier, quel que soit le délai réel côté Render."""

    def test_reprovisioning_the_same_slug_after_deprovisioning_succeeds_with_fresh_render_names(
        self, render_mock, notify_mock,
    ):
        render_mock.get_owner_id.return_value = "owner-1"
        # Les noms Render "réellement créés" échoent le nom demandé — capture directement ce
        # que provision() a choisi comme nom, sans dépendre d'une valeur figée en dur.
        render_mock.create_postgres.side_effect = lambda *, name, **kwargs: {"id": f"{name}-id"}
        render_mock.wait_for_postgres_available.return_value = True
        render_mock.get_postgres_connection_info.return_value = {"internalConnectionString": "postgres://x"}
        render_mock.wait_for_deploy_live.return_value = True
        render_mock.create_web_service.side_effect = lambda *, name, **kwargs: {
            "id": f"{name}-id", "serviceDetails": {"url": f"https://{name}.onrender.com"},
        }
        # get_service() est la source de vérité pour l'URL réelle (jamais devinée, cf.
        # provision_client.py) — dérivée ici de l'id du service demandé.
        render_mock.get_service.side_effect = lambda service_id: {
            "id": service_id, "serviceDetails": {"url": f"https://{service_id}.onrender.com"},
        }
        notify_mock.send_welcome_email.return_value = True

        first = provision_client.provision(
            client_name="Acme13", slug="acme13", postgres_plan="starter", admin_email="a@acme13.com",
        )
        assert first.status == "active"
        first_postgres_name = render_mock.create_postgres.call_args_list[0].kwargs["name"]
        first_backend_name = render_mock.create_web_service.call_args_list[0].kwargs["name"]
        first_frontend_name = render_mock.create_web_service.call_args_list[1].kwargs["name"]

        # "Deprovisioning" — un slug supprimé redevient immédiatement disponible (même effet
        # sur instances.db qu'un delete_client.py réussi, ou qu'un rollback COMPLET de
        # provision() lui-même : la ligne est simplement retirée).
        db.delete_instance_row("acme13")

        second = provision_client.provision(
            client_name="Acme13", slug="acme13", postgres_plan="starter", admin_email="a@acme13.com",
        )

        assert second.status == "active", f"le re-provisioning du même slug doit réussir : {second.error}"
        second_postgres_name = render_mock.create_postgres.call_args_list[1].kwargs["name"]
        second_backend_name = render_mock.create_web_service.call_args_list[2].kwargs["name"]
        second_frontend_name = render_mock.create_web_service.call_args_list[3].kwargs["name"]

        # Le coeur du correctif : même slug métier, mais noms Render TOUJOURS différents —
        # plus aucune collision possible avec les ressources tout juste supprimées.
        assert second_postgres_name != first_postgres_name
        assert second_backend_name != first_backend_name
        assert second_frontend_name != first_frontend_name
        assert second_postgres_name.startswith("smartticket-acme13-")
        assert second_backend_name.startswith("smartticket-acme13-")
        assert second_frontend_name.startswith("smartticket-acme13-")

        # Le slug métier, lui, reste inchangé et propre en base — seul le nom Render varie.
        row = db.get_instance("acme13")
        assert row["slug"] == "acme13"


class TestBackendEmailLinksUseTheRealFrontendUrl:
    """Bug réel du 2026-07-17 : email de vérification bien REÇU (Brevo fonctionnait), mais le
    lien pointait sur localhost -> ERR_CONNECTION_REFUSED. Cause : backend/email_utils.py
    construit les liens de TOUS les emails transactionnels (vérification d'email, reset
    password, invitation en masse) à partir de FRONTEND_URL, qui défaut à
    "http://localhost:3005" — jamais injectée par provision() jusqu'ici. Pendant côté backend
    du bug NEXT_PUBLIC_API_URL déjà corrigé côté frontend (cf. TestFrontendReceivesTheRealBackendUrl
    ci-dessus). Le lien de setup (ops/notify.py) n'est PAS concerné : setup_url est construit
    directement dans provision() à partir de frontend_url, jamais via cette variable backend."""

    def test_provision_injects_non_empty_non_localhost_frontend_url_into_backend_env(self, render_mock, notify_mock):
        _mock_common_steps(render_mock, postgres_id="pg-14")
        render_mock.create_web_service.side_effect = [
            {"id": "backend-14", "serviceDetails": {"url": "https://smartticket-acme14-backend.onrender.com"}},
            {"id": "frontend-14", "serviceDetails": {"url": "https://smartticket-acme14-frontend.onrender.com"}},
        ]
        notify_mock.send_welcome_email.return_value = True

        result = provision_client.provision(
            client_name="Acme14", slug="acme14", postgres_plan="starter", admin_email="a@acme14.com",
        )

        assert result.status == "active"
        backend_call_kwargs = render_mock.create_web_service.call_args_list[0].kwargs

        # C'est LE champ qui était absent avant le correctif — backend/email_utils.py
        # retombait sur son défaut localhost pour CHAQUE lien d'email transactionnel.
        frontend_url_env = backend_call_kwargs["env_vars"]["FRONTEND_URL"]
        assert frontend_url_env, "FRONTEND_URL ne doit jamais être vide côté backend"
        assert "localhost" not in frontend_url_env

        # Même valeur que CORS_ORIGINS (déjà correcte) et que l'URL utilisée pour setup_url —
        # une seule source de vérité pour "l'URL publique du frontend", pas trois qui
        # pourraient un jour diverger.
        assert frontend_url_env == backend_call_kwargs["env_vars"]["CORS_ORIGINS"]
        assert result.setup_url.startswith(frontend_url_env)

    def test_provision_injects_custom_domain_frontend_url_when_domain_given(self, render_mock, notify_mock):
        _mock_common_steps(render_mock, postgres_id="pg-15")
        render_mock.create_web_service.side_effect = [
            {"id": "backend-15", "serviceDetails": {"url": "https://acme15-api.smartticket.fr"}},
            {"id": "frontend-15", "serviceDetails": {"url": "https://acme15.smartticket.fr"}},
        ]
        notify_mock.send_welcome_email.return_value = True

        result = provision_client.provision(
            client_name="Acme15", slug="acme15", postgres_plan="starter", admin_email="a@acme15.com",
            domain="smartticket.fr",
        )

        assert result.status == "active"
        backend_call_kwargs = render_mock.create_web_service.call_args_list[0].kwargs
        assert backend_call_kwargs["env_vars"]["FRONTEND_URL"] == "https://acme15.smartticket.fr"


class TestFrontendReceivesTheBrandName:
    """White-label du nom de marque (2026-08-15) : le frontend affichait "SmartTicket" en
    dur (header, sidebar, pages auth) quel que soit le client — cf. frontend/lib/brand.ts.
    provision() doit injecter NEXT_PUBLIC_BRAND_NAME = client_name AVANT le premier build du
    frontend (même piège de timing que NEXT_PUBLIC_API_URL/FRONTEND_URL : bakée au build,
    jamais réévaluée au runtime)."""

    def test_provision_injects_brand_name_equal_to_client_name(self, render_mock, notify_mock):
        _mock_common_steps(render_mock, postgres_id="pg-16")
        render_mock.create_web_service.side_effect = [
            {"id": "backend-16", "serviceDetails": {"url": "https://smartticket-acme16-backend.onrender.com"}},
            {"id": "frontend-16", "serviceDetails": {"url": "https://smartticket-acme16-frontend.onrender.com"}},
        ]
        notify_mock.send_welcome_email.return_value = True

        result = provision_client.provision(
            client_name="Martin Technologies", slug="acme16", postgres_plan="starter", admin_email="a@acme16.com",
        )

        assert result.status == "active"
        frontend_call_kwargs = render_mock.create_web_service.call_args_list[1].kwargs

        # C'est CE champ qui était absent avant le correctif — le frontend retombait sur le
        # défaut "SmartTicket" de lib/brand.ts, quel que soit le client.
        brand_name = frontend_call_kwargs["env_vars"]["NEXT_PUBLIC_BRAND_NAME"]
        assert brand_name, "NEXT_PUBLIC_BRAND_NAME ne doit jamais être vide au moment du build frontend"
        assert brand_name == "Martin Technologies"


class TestProvisionSetsClientInstanceDeploymentMode:
    """Séparation site vitrine / instance client (2026-08-15) : l'instance affichait la
    landing marketing SmartTicket ("Essayer gratuitement", "Propulsé par Mistral AI"...) à sa
    racine "/" — inacceptable pour le public d'un client (secteur régulé). provision() doit
    poser NEXT_PUBLIC_DEPLOYMENT_MODE=instance AVANT le premier build du frontend (même piège
    de timing que NEXT_PUBLIC_BRAND_NAME/NEXT_PUBLIC_API_URL : bakée au build, jamais
    réévaluée au runtime) — frontend/middleware.ts s'appuie dessus pour rediriger "/" vers
    l'app cliente plutôt que de servir la landing."""

    def test_provision_injects_instance_deployment_mode(self, render_mock, notify_mock):
        _mock_common_steps(render_mock, postgres_id="pg-17")
        render_mock.create_web_service.side_effect = [
            {"id": "backend-17"}, {"id": "frontend-17"},
        ]
        notify_mock.send_welcome_email.return_value = True

        result = provision_client.provision(
            client_name="Acme17", slug="acme17", postgres_plan="starter", admin_email="a@acme17.com",
        )

        assert result.status == "active"
        frontend_call_kwargs = render_mock.create_web_service.call_args_list[1].kwargs
        # "instance", jamais "marketing" ni absent — un oubli laisserait la landing
        # SmartTicket accessible au public du client (frontend/lib/deploymentMode.ts défaut
        # certes déjà à "instance" par sécurité, mais provision() doit la poser explicitement).
        assert frontend_call_kwargs["env_vars"]["NEXT_PUBLIC_DEPLOYMENT_MODE"] == "instance"

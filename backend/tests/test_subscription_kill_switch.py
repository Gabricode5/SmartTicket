"""Coupe-circuit d'abonnement (modèle "flotte d'instances") : GET/PUT
/v1/instance/subscription-status, protégés par VENDOR_KEY (jamais par le rôle admin
classique — un client qui ne paye plus ne doit pas pouvoir se réactiver lui-même), et le
middleware qui bloque le reste de l'API (402) tant que l'instance est suspendue."""
import os

_VENDOR_HEADERS = {"X-Vendor-Key": os.environ["VENDOR_KEY"]}


class TestVendorKeyProtection:
    def test_get_without_vendor_key_forbidden(self, client):
        resp = client.get("/v1/instance/subscription-status")
        assert resp.status_code == 403

    def test_get_with_wrong_vendor_key_forbidden(self, client):
        resp = client.get("/v1/instance/subscription-status", headers={"X-Vendor-Key": "wrong"})
        assert resp.status_code == 403

    def test_put_without_vendor_key_forbidden(self, client):
        resp = client.put("/v1/instance/subscription-status", json={"status": "suspended"})
        assert resp.status_code == 403


class TestSubscriptionStatusEndpoint:
    def test_default_status_is_active(self, client):
        resp = client.get("/v1/instance/subscription-status", headers=_VENDOR_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_can_suspend_and_reactivate(self, client):
        resp = client.put(
            "/v1/instance/subscription-status",
            json={"status": "suspended", "reason": "Facture impayée"},
            headers=_VENDOR_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"
        assert resp.json()["reason"] == "Facture impayée"

        resp = client.put(
            "/v1/instance/subscription-status",
            json={"status": "active"},
            headers=_VENDOR_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_invalid_status_rejected(self, client):
        resp = client.put(
            "/v1/instance/subscription-status",
            json={"status": "not-a-real-status"},
            headers=_VENDOR_HEADERS,
        )
        assert resp.status_code == 400


class TestSubscriptionGateMiddleware:
    def test_health_check_always_reachable(self, client):
        client.put("/v1/instance/subscription-status", json={"status": "suspended"}, headers=_VENDOR_HEADERS)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_status_endpoint_reachable_even_when_suspended(self, client):
        client.put("/v1/instance/subscription-status", json={"status": "suspended"}, headers=_VENDOR_HEADERS)
        resp = client.get("/v1/instance/subscription-status", headers=_VENDOR_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

    def test_api_blocked_when_suspended(self, client):
        client.put(
            "/v1/instance/subscription-status",
            json={"status": "suspended", "reason": "Facture impayée"},
            headers=_VENDOR_HEADERS,
        )
        resp = client.get("/v1/me")
        assert resp.status_code == 402
        assert resp.json()["detail"] == "Facture impayée"

    def test_api_works_normally_when_active(self, client, registered_user):
        resp = client.post("/v1/login", json={
            "email": registered_user["email"], "password": registered_user["password"],
        })
        assert resp.status_code == 200

    def test_reactivation_restores_access(self, client, registered_user):
        client.put("/v1/instance/subscription-status", json={"status": "suspended"}, headers=_VENDOR_HEADERS)
        blocked = client.post("/v1/login", json={
            "email": registered_user["email"], "password": registered_user["password"],
        })
        assert blocked.status_code == 402

        client.put("/v1/instance/subscription-status", json={"status": "active"}, headers=_VENDOR_HEADERS)
        restored = client.post("/v1/login", json={
            "email": registered_user["email"], "password": registered_user["password"],
        })
        assert restored.status_code == 200

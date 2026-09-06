"""pipeline.answer : assemble retrieval + prompt a deux couches + generation."""
from rag_core.models import KnowledgeChunk
from rag_core.pipeline import answer
from tests._fakes import FakeEmbedder, FakeGenerator, unit_vector


def test_answer_returns_suggestion_and_metadata(db):
    db.add(
        KnowledgeChunk(
            contenu="Politique de retour : 30 jours apres reception.",
            embedding=unit_vector(5),
            source="kb",
        )
    )
    db.commit()

    emb = FakeEmbedder({"Quel est le delai de retour ?": unit_vector(5)})
    gen = FakeGenerator(lambda _p: "Vous disposez de 30 jours.")

    res = answer(db, "Quel est le delai de retour ?", embedder=emb, generator=gen)

    assert res.suggestion == "Vous disposez de 30 jours."
    assert res.chunk_count == 1
    assert res.model == "fake-generate"
    assert res.best_match_distance is not None and res.best_match_distance < 1e-6
    assert res.low_confidence is False


def test_answer_feeds_two_layer_prompt_to_the_generator(db):
    db.add(
        KnowledgeChunk(
            contenu="Le SAV est joignable du lundi au vendredi.",
            embedding=unit_vector(6),
            source="kb",
        )
    )
    db.commit()

    emb = FakeEmbedder({"horaires ?": unit_vector(6)})
    gen = FakeGenerator()
    answer(db, "horaires ?", client_overlay="Vouvoie toujours le client.", embedder=emb, generator=gen)

    prompt = gen.last_prompt
    assert prompt is not None
    # couche 1 avant couche 2
    assert prompt.index("=== REGLES DE SECURITE ===") < prompt.index("=== PERSONNALISATION CLIENT ===")
    # surcouche client injectee
    assert "Vouvoie toujours le client." in prompt
    # contexte RAG injecte
    assert "Le SAV est joignable" in prompt


def test_low_confidence_when_base_is_empty(db):
    emb = FakeEmbedder()
    gen = FakeGenerator(lambda _p: "Je n'ai pas assez d'informations.")
    res = answer(db, "question sans base de connaissance", embedder=emb, generator=gen)

    assert res.chunk_count == 0
    assert res.chunk_ids == []
    assert res.best_match_distance is None
    assert res.low_confidence is True


def test_low_confidence_when_best_match_is_far(db, monkeypatch):
    monkeypatch.setattr("rag_core.pipeline.RAG_LOW_CONFIDENCE_DISTANCE", 0.1)
    db.add(KnowledgeChunk(contenu="sujet A", embedding=unit_vector(10), source="kb"))
    db.commit()
    # question orthogonale au seul chunk => distance cosinus = 1.0 > 0.1
    emb = FakeEmbedder({"sujet totalement different": unit_vector(900)})
    res = answer(db, "sujet totalement different", embedder=emb, generator=FakeGenerator())

    assert res.chunk_count == 1
    assert res.best_match_distance is not None and res.best_match_distance > 0.1
    assert res.low_confidence is True

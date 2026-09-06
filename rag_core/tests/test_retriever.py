"""Retrieval de bout en bout contre un vrai Postgres+pgvector (fixture `db`), embedder
mocke pour piloter la similarite sans appel reseau."""
from rag_core.models import KnowledgeChunk
from rag_core.retriever import retrieve
from tests._fakes import FakeEmbedder, unit_vector


def _seed(db):
    db.add_all(
        [
            KnowledgeChunk(contenu="Doc alpha : generalites.", embedding=unit_vector(1), source="a"),
            KnowledgeChunk(
                contenu="Doc bravo : politique de facturation mensuelle.",
                embedding=unit_vector(2),
                source="b",
            ),
            KnowledgeChunk(contenu="Doc charlie : divers.", embedding=unit_vector(3), source="c"),
        ]
    )
    db.commit()


def test_empty_base_returns_empty_context(db):
    ctx = retrieve(db, "n'importe quoi", embedder=FakeEmbedder())
    assert ctx.context == ""
    assert ctx.chunk_ids == []
    assert ctx.best_match_distance is None
    assert ctx.chunk_count == 0


def test_closest_chunk_ranks_first_and_distance_is_captured(db):
    _seed(db)
    emb = FakeEmbedder({"question sur la facturation": unit_vector(2)})
    ctx = retrieve(db, "question sur la facturation", embedder=emb)

    assert ctx.chunk_ids[0] == 2
    assert "bravo" in ctx.context
    # vecteur identique => distance cosinus ~ 0
    assert ctx.best_match_distance is not None
    assert ctx.best_match_distance < 1e-6


def test_context_is_truncated_to_max_chars(db, monkeypatch):
    monkeypatch.setattr("rag_core.retriever.KB_MAX_CONTEXT_CHARS", 20)
    db.add(KnowledgeChunk(contenu="x" * 500, embedding=unit_vector(7), source="big"))
    db.commit()
    ctx = retrieve(db, "q", embedder=FakeEmbedder({"q": unit_vector(7)}))
    assert len(ctx.context) == 20


def test_quarantined_chunk_is_dropped_from_context(db):
    db.add_all(
        [
            KnowledgeChunk(
                contenu="bon chunk", embedding=unit_vector(4), source="ok", feedback_score=0
            ),
            KnowledgeChunk(
                contenu="chunk banni", embedding=unit_vector(4), source="ko", feedback_score=-10
            ),
        ]
    )
    db.commit()
    ctx = retrieve(db, "q", embedder=FakeEmbedder({"q": unit_vector(4)}))
    assert "chunk banni" not in ctx.context
    assert "bon chunk" in ctx.context

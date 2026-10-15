"""Ingestion de bout en bout contre le vrai Postgres+pgvector (fixture `db`), embeddings
mockes (FakeEmbedder) -- aucun appel reseau."""
import io

import pytest
from sqlalchemy import func, select

from rag_core import ingest as ingest_mod
from rag_core.ingest import IngestError, _robots_allows, ingest_file, ingest_text, ingest_url
from rag_core.models import KnowledgeChunk
from tests._fakes import FakeEmbedder

# ~30 phrases distinctes -> plusieurs chunks de 1000 apres split.
LONG_DOC = " ".join(
    f"Phrase numero {i} : le service client traite les demandes de facturation et de livraison."
    for i in range(60)
)


def _count(db) -> int:
    return db.execute(select(func.count()).select_from(KnowledgeChunk)).scalar_one()


def test_ingest_text_inserts_chunks(db):
    emb = FakeEmbedder()
    res = ingest_text(db, LONG_DOC, source="doc-1", category="faq", embedder=emb)

    assert res.ok and res.inserted >= 2
    assert res.inserted == _count(db)
    rows = db.query(KnowledgeChunk).all()
    assert {r.source for r in rows} == {"doc-1"}
    assert {r.category for r in rows} == {"faq"}
    assert all(r.embedding is not None for r in rows)
    assert all(r.feedback_score == 0 for r in rows)


def test_ingest_text_default_category_when_none(db):
    res = ingest_text(db, LONG_DOC, source="doc-2", embedder=FakeEmbedder())
    rows = db.query(KnowledgeChunk).all()
    assert res.inserted == len(rows)
    assert {r.category for r in rows} == {"documentation"}  # config.INGEST_DEFAULT_CATEGORY


def test_ingest_text_rejects_content_shorter_than_min_length(db):
    with pytest.raises(IngestError):
        ingest_text(db, "trop court", source="tiny", embedder=FakeEmbedder())
    assert _count(db) == 0


def test_ingest_text_filters_low_quality_chunks(db):
    good = " ".join(f"Information utile et lisible numero {i} sur nos horaires." for i in range(40))
    garbage = "?" * 400  # un "chunk" qui echoue le seuil qualite
    res = ingest_text(db, good + " " + garbage, source="mix", embedder=FakeEmbedder())
    assert res.chunks_rejected >= 1
    assert res.inserted == _count(db)


def test_ingest_text_truncates_to_max_chunks(db, monkeypatch):
    monkeypatch.setattr(ingest_mod.config, "INGEST_MAX_CHUNKS", 2)
    res = ingest_text(db, LONG_DOC, source="capped", embedder=FakeEmbedder())
    assert res.truncated is True
    assert res.inserted == 2
    assert _count(db) == 2


def test_ingest_text_embeds_in_batches(db, monkeypatch):
    monkeypatch.setattr(ingest_mod.config, "INGEST_EMBED_BATCH_SIZE", 2)
    emb = FakeEmbedder()
    res = ingest_text(db, LONG_DOC, source="batched", embedder=emb)
    assert sum(emb.batch_sizes) == res.inserted
    assert all(size <= 2 for size in emb.batch_sizes)
    assert len(emb.batch_sizes) >= 2


def test_ingest_file_txt(db):
    payload = LONG_DOC.encode("utf-8")
    res = ingest_file(db, payload, "guide.txt", embedder=FakeEmbedder())
    assert res.inserted == _count(db) >= 2
    assert {r.source for r in db.query(KnowledgeChunk).all()} == {"guide.txt"}


def test_ingest_file_rejects_unsupported_extension(db):
    with pytest.raises(IngestError):
        ingest_file(db, b"whatever", "archive.zip", embedder=FakeEmbedder())
    assert _count(db) == 0


def test_ingest_file_docx(db):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    for i in range(40):
        document.add_paragraph(f"Paragraphe {i} : politique de retour et delais de remboursement.")
    buf = io.BytesIO()
    document.save(buf)

    res = ingest_file(db, buf.getvalue(), "politique.docx", embedder=FakeEmbedder())
    assert res.inserted == _count(db) >= 2
    assert {r.source for r in db.query(KnowledgeChunk).all()} == {"politique.docx"}


def test_ingest_url_with_injected_fetcher(db):
    res = ingest_url(
        db,
        "https://client.example/kb/livraison",
        embedder=FakeEmbedder(),
        respect_robots=False,
        fetcher=lambda _url: LONG_DOC,
    )
    assert res.inserted == _count(db) >= 2
    assert {r.source for r in db.query(KnowledgeChunk).all()} == {
        "https://client.example/kb/livraison"
    }


def test_ingest_url_rejects_non_textual_extension(db):
    with pytest.raises(IngestError):
        ingest_url(db, "https://client.example/manuel.pdf", embedder=FakeEmbedder())
    assert _count(db) == 0


def test_ingest_url_respects_robots_disallow(db, monkeypatch):
    monkeypatch.setattr(ingest_mod, "_robots_allows", lambda *_a, **_k: False)
    with pytest.raises(IngestError):
        ingest_url(
            db,
            "https://client.example/kb/interdit",
            embedder=FakeEmbedder(),
            fetcher=lambda _url: LONG_DOC,
        )
    assert _count(db) == 0


class _FakeRobotParser:
    def __init__(self, *, readable=True, allowed=True):
        self._readable = readable
        self._allowed = allowed

    def set_url(self, _url):
        pass

    def read(self):
        if not self._readable:
            raise OSError("robots.txt injoignable")

    def can_fetch(self, _agent, _url):
        return self._allowed


def test_robots_allows_fail_open_when_unreadable(monkeypatch):
    monkeypatch.setattr(ingest_mod, "RobotFileParser", lambda: _FakeRobotParser(readable=False))
    assert _robots_allows("https://x.example/page", "Mozilla/5.0") is True


def test_robots_allows_reflects_can_fetch(monkeypatch):
    monkeypatch.setattr(ingest_mod, "RobotFileParser", lambda: _FakeRobotParser(allowed=False))
    assert _robots_allows("https://x.example/page", "Mozilla/5.0") is False
    monkeypatch.setattr(ingest_mod, "RobotFileParser", lambda: _FakeRobotParser(allowed=True))
    assert _robots_allows("https://x.example/page", "Mozilla/5.0") is True

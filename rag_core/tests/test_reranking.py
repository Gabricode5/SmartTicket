from collections import namedtuple

from rag_core.config import RERANK_QUARANTINE_THRESHOLD
from rag_core.reranking import _lexical_overlap, _tokenize, rerank_chunks

C = namedtuple("C", "id contenu")


def test_empty_candidates():
    assert rerank_chunks("question", [], {}, top_k=5) == []


def test_returns_at_most_top_k():
    chunks = [C(i, f"contenu numero {i}") for i in range(10)]
    out = rerank_chunks("contenu", chunks, {}, top_k=3)
    assert len(out) == 3


def test_quarantine_excludes_chunk_at_or_below_threshold():
    chunks = [C(1, "garde"), C(2, "exclu"), C(3, "garde aussi")]
    feedback = {2: RERANK_QUARANTINE_THRESHOLD}
    out = rerank_chunks("garde", chunks, feedback, top_k=5)
    assert [c.id for c in out] == [1, 3]


def test_quarantine_keeps_chunk_just_above_threshold():
    chunks = [C(1, "un"), C(2, "deux")]
    feedback = {2: RERANK_QUARANTINE_THRESHOLD + 1}
    out = rerank_chunks("un deux", chunks, feedback, top_k=5)
    assert {c.id for c in out} == {1, 2}


def test_similarity_order_is_preserved_without_other_signals():
    # candidats deja tries par similarite (index 0 = plus proche), aucun feedback,
    # aucun recouvrement lexical => l'ordre d'entree est conserve.
    chunks = [C(1, "aaa"), C(2, "bbb"), C(3, "ccc")]
    out = rerank_chunks("zzz", chunks, {}, top_k=3)
    assert [c.id for c in out] == [1, 2, 3]


def test_lexical_overlap_helper():
    assert _lexical_overlap(_tokenize("facturation mensuelle"), "la facturation est mensuelle") == 1.0
    assert _lexical_overlap(_tokenize("facturation mensuelle"), "aucun rapport ici") == 0.0
    assert _lexical_overlap(set(), "peu importe") == 0.0

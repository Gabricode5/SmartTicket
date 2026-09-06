"""Nettoyage + scoring qualite (portage verbatim de backend/ingest_postgres.py)."""
from rag_core.text import clean_text, quality_score


def test_clean_text_strips_nul_and_control_chars():
    assert clean_text("bon\x00jour\x07 monde") == "bonjour monde"


def test_clean_text_collapses_whitespace():
    assert clean_text("  a\t\t b \n\n c  ") == "a b c"


def test_clean_text_handles_none_and_empty():
    assert clean_text("") == ""
    assert clean_text(None) == ""  # type: ignore[arg-type]


def test_quality_score_clean_paragraph_is_high():
    txt = "Notre service client repond du lundi au vendredi, de 9h a 18h, par email et telephone."
    assert quality_score(txt) > 0.9


def test_quality_score_empty_is_zero():
    assert quality_score("") == 0.0


def test_quality_score_penalises_question_mark_noise():
    # texte truffe de '?' (typique d'un encodage casse)
    assert quality_score("??? ?? ???? ? ?? ??? ????? ?? ?") < 0.4


def test_quality_score_penalises_binary_signature():
    with_sig = "Ceci contient une signature JFIF issue d'une image mal extraite " * 2
    assert quality_score(with_sig) < quality_score(with_sig.replace("JFIF", "texte"))


def test_quality_score_penalises_base64_blob():
    blob = "A" * 200
    assert quality_score(f"intro {blob} fin") <= 0.5

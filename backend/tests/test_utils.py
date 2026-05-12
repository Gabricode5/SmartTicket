"""Unit tests for pure utility functions (no DB required)."""
from dependencies import sanitize_model_name, chunk_text, sanitize_text, build_rag_prompt


class TestSanitizeModelName:
    def test_returns_single_name(self):
        assert sanitize_model_name("mistral-small-latest", "fallback") == "mistral-small-latest"

    def test_picks_first_from_csv(self):
        assert sanitize_model_name("model-a,model-b", "fallback") == "model-a"

    def test_replaces_semicolon_with_comma(self):
        assert sanitize_model_name("model-a;model-b", "fallback") == "model-a"

    def test_empty_string_returns_fallback(self):
        assert sanitize_model_name("", "fallback") == "fallback"

    def test_none_returns_fallback(self):
        assert sanitize_model_name(None, "fallback") == "fallback"

    def test_strips_whitespace(self):
        assert sanitize_model_name("  mistral-small  ", "fallback") == "mistral-small"


class TestChunkText:
    def test_single_chunk_when_text_shorter_than_size(self):
        chunks = chunk_text("hello", 100, 0)
        assert chunks == ["hello"]

    def test_splits_into_multiple_chunks(self):
        chunks = chunk_text("abcdefghij", 4, 0)
        assert len(chunks) > 1
        assert all(len(c) <= 4 for c in chunks)

    def test_overlap_creates_repeated_content(self):
        text = "abcdefghij"
        chunks = chunk_text(text, 6, 2)
        assert len(chunks) >= 2

    def test_zero_size_returns_full_text(self):
        chunks = chunk_text("hello world", 0, 0)
        assert chunks == ["hello world"]


class TestSanitizeText:
    def test_removes_null_bytes(self):
        assert sanitize_text("hello\x00world") == "helloworld"

    def test_strips_whitespace(self):
        assert sanitize_text("  hello  ") == "hello"

    def test_clean_text_unchanged(self):
        assert sanitize_text("hello world") == "hello world"


class TestBuildRagPrompt:
    def test_contains_question(self):
        prompt = build_rag_prompt("What is X?", "Some context")
        assert "What is X?" in prompt

    def test_contains_context(self):
        prompt = build_rag_prompt("question", "important context")
        assert "important context" in prompt

    def test_empty_context_shows_placeholder(self):
        prompt = build_rag_prompt("question", "")
        assert "Aucun contexte disponible" in prompt

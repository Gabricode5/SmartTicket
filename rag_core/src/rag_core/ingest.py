"""Ingestion : texte / fichier / URL -> chunks -> embeddings -> INSERT knowledge_chunk.

Reutilise la logique de backend/ingest_postgres.py (chunking RecursiveCharacterTextSplitter
1000/100, filtres qualite via rag_core.text, MIN_TEXT_LENGTH, plafond MAX_KB_CHUNKS,
embeddings par batch) mais persiste vers le schema rag_core (KnowledgeChunk). Aucun import
de backend/.

Hors perimetre pour l'instant (le backend a une version si besoin plus tard) : le crawl
recursif de sitemap. `ingest_url` traite UNE page.
"""
import io
import logging
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from rag_core import config
from rag_core.llm.factory import get_embedder
from rag_core.models import KnowledgeChunk
from rag_core.text import clean_text, quality_score

logger = logging.getLogger(__name__)

# Extensions dont on sait d'avance que ce n'est pas du texte HTML exploitable.
NON_HTML_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar",
    ".7z", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".mp3", ".wav", ".mp4", ".avi", ".mov", ".wmv", ".webm", ".woff", ".woff2",
    ".ttf", ".otf", ".eot", ".css", ".js", ".json", ".xml",
)

SUPPORTED_FILE_EXTENSIONS = ("txt", "docx", "pdf")


@dataclass
class IngestResult:
    source: str
    inserted: int
    chunks_rejected: int
    truncated: bool

    @property
    def ok(self) -> bool:
        return self.inserted > 0


class IngestError(RuntimeError):
    """Ingestion impossible (robots.txt interdit, type de fichier non supporte, contenu vide...)."""


def _split(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.INGEST_CHUNK_SIZE,
        chunk_overlap=config.INGEST_CHUNK_OVERLAP,
    )
    return splitter.split_text(text)


def _prepare_chunks(raw_text: str) -> tuple[list[str], int, bool]:
    """raw_text -> (chunks retenus, nb rejetes, tronque?). Memes filtres que backend/."""
    cleaned = clean_text(raw_text)
    if len(cleaned) < config.INGEST_MIN_TEXT_LENGTH:
        return [], 0, False

    kept: list[str] = []
    rejected = 0
    for piece in _split(cleaned):
        chunk = clean_text(piece)
        if (
            len(chunk) >= config.INGEST_MIN_TEXT_LENGTH
            and quality_score(chunk) >= config.INGEST_CHUNK_QUALITY_THRESHOLD
        ):
            kept.append(chunk)
        else:
            rejected += 1

    truncated = False
    if config.INGEST_MAX_CHUNKS > 0 and len(kept) > config.INGEST_MAX_CHUNKS:
        kept = kept[: config.INGEST_MAX_CHUNKS]
        truncated = True
    return kept, rejected, truncated


def ingest_text(
    db: Session,
    content: str,
    *,
    source: str,
    category: str | None = None,
    embedder=None,
) -> IngestResult:
    """Primitive d'ingestion : decoupe `content`, filtre, embed par batch, INSERT, commit.

    `embedder` injectable pour les tests (sinon resolu via le catalogue ferme).
    """
    embedder = embedder or get_embedder()
    category = category or config.INGEST_DEFAULT_CATEGORY

    chunks, rejected, truncated = _prepare_chunks(content)
    if not chunks:
        raise IngestError(f"Aucun chunk exploitable extrait de la source '{source}'.")

    inserted = 0
    for start in range(0, len(chunks), config.INGEST_EMBED_BATCH_SIZE):
        batch = chunks[start : start + config.INGEST_EMBED_BATCH_SIZE]
        vectors = embedder.embed(batch)
        for chunk_text, vector in zip(batch, vectors, strict=True):
            db.add(
                KnowledgeChunk(
                    contenu=chunk_text,
                    embedding=vector,
                    source=source,
                    category=category,
                )
            )
            inserted += 1
    db.commit()
    logger.info(
        "ingest_text: source=%s inserted=%d rejected=%d truncated=%s",
        source, inserted, rejected, truncated,
    )
    return IngestResult(source=source, inserted=inserted, chunks_rejected=rejected, truncated=truncated)


def _extract_file_text(file_bytes: bytes, ext: str) -> str:
    if ext == "txt":
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1")
    if ext == "docx":
        from docx import Document as DocxDocument

        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise IngestError(f"Type de fichier non supporte : .{ext}")


def ingest_file(
    db: Session,
    file_bytes: bytes,
    filename: str,
    *,
    category: str | None = None,
    embedder=None,
) -> IngestResult:
    """Extrait le texte d'un .txt / .docx / .pdf puis delegue a ingest_text."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_FILE_EXTENSIONS:
        raise IngestError(
            f"Extension '.{ext}' non supportee (attendu : {', '.join(SUPPORTED_FILE_EXTENSIONS)})."
        )
    raw_text = _extract_file_text(file_bytes, ext)
    return ingest_text(db, raw_text, source=filename, category=category, embedder=embedder)


def _robots_allows(url: str, user_agent: str) -> bool:
    """True si robots.txt autorise (ou est illisible/absent -> on n'empeche pas)."""
    parser = RobotFileParser()
    parser.set_url(urljoin(url, "/robots.txt"))
    try:
        parser.read()
    except Exception as exc:  # robots.txt illisible : on continue sans restriction
        logger.info("robots.txt illisible pour %s (%s) -- ingestion autorisee par defaut", url, exc)
        return True
    return parser.can_fetch(user_agent, url)


def _default_fetcher(url: str) -> str:
    """Charge le contenu texte d'une page via langchain WebBaseLoader."""
    from langchain_community.document_loaders import WebBaseLoader

    loader = WebBaseLoader(url)
    loader.requests_kwargs = {
        "headers": {"User-Agent": config.INGEST_USER_AGENT},
        "timeout": config.INGEST_SCRAPE_TIMEOUT,
    }
    docs = loader.load()
    return "\n\n".join((doc.page_content or "") for doc in docs)


def ingest_url(
    db: Session,
    url: str,
    *,
    category: str | None = None,
    embedder=None,
    respect_robots: bool = True,
    fetcher: Callable[[str], str] | None = None,
) -> IngestResult:
    """Ingere UNE page web. `fetcher` injectable pour les tests (sinon WebBaseLoader)."""
    if url.lower().rsplit("?", 1)[0].endswith(NON_HTML_EXTENSIONS):
        raise IngestError(f"URL non textuelle (extension exclue) : {url}")
    if respect_robots and not _robots_allows(url, config.INGEST_USER_AGENT):
        raise IngestError(f"Le robots.txt interdit l'ingestion de : {url}")

    fetcher = fetcher or _default_fetcher
    page_text = fetcher(url)
    return ingest_text(db, page_text, source=url, category=category, embedder=embedder)

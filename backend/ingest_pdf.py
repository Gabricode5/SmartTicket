from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
import tempfile, os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
COLLECTION_NAME = "rag_documents"

# Section-aware splitter: prefers blank-line boundaries (paragraph / section breaks)
# before falling back to sentence or word boundaries.
# chunk_overlap=0 avoids duplicating section content across adjacent chunks.
_section_splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n\n", "\n\n", "\n", ". "],
    chunk_size=2000,
    chunk_overlap=0,
    keep_separator=False,
)


def _get_connection_string() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://admin:Password1234@localhost:5432/ticketdb")
    return raw.replace("postgresql://", "postgresql+psycopg://", 1)


def ingest_pdf_to_postgres(file_bytes: bytes, filename: str, category: str = "pdf") -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        loader = PyPDFLoader(tmp_path)
        pages = loader.load()          # one Document per PDF page
        num_pages = len(pages)

        # Split by section boundaries; page metadata (page number, source) is preserved
        chunks = _section_splitter.split_documents(pages)

        for chunk in chunks:
            chunk.metadata["source"] = filename
            chunk.metadata["category"] = category

        print(f"[PDF] {filename}: {num_pages} pages → {len(chunks)} sections")

        embed = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL)
        PGVector.from_documents(
            documents=chunks,
            embedding=embed,
            collection_name=COLLECTION_NAME,
            connection=_get_connection_string(),
            use_jsonb=True,
        )

        return {
            "inserted": len(chunks),
            "chunks": len(chunks),
            "filename": filename,
            "category": category,
            "pages": num_pages,
        }
    finally:
        os.unlink(tmp_path)

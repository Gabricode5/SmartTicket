import logging

from sqlalchemy import inspect, text

from database import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ensure_chat_sessions_status_column() -> None:
    """
    Ensure the `status` column exists on the `chat_sessions` table.

    This is a minimal, one-off migration that can be safely re-run:
    - If the table is missing, it logs an error.
    - If the column already exists, it logs and does nothing.
    - If the column is missing, it adds it with the expected definition.
    """
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    if "chat_sessions" not in tables:
        logger.error("Table 'chat_sessions' does not exist. Run your init-db.sql first.")
        return

    columns = {col["name"] for col in inspector.get_columns("chat_sessions")}
    if "status" in columns:
        logger.info("Column 'chat_sessions.status' already exists. Nothing to do.")
        return

    logger.info("Column 'chat_sessions.status' is missing. Adding it now...")
    ddl = text(
        "ALTER TABLE chat_sessions "
        "ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'open';"
    )

    with engine.begin() as conn:
        conn.execute(ddl)

    logger.info("Column 'chat_sessions.status' successfully added.")


def ensure_knowledge_base_embedding_dim() -> None:
    """
    Ensure knowledge_base.embedding is vector(1024).

    pgvector does not allow ALTER COLUMN to change vector dimensions, so we:
    1. Drop the HNSW index (if any) on the column.
    2. Drop the old column.
    3. Re-add it as vector(1024).
    All existing rows are deleted because their 768-dim embeddings are
    incompatible with the new dimension and must be re-ingested.
    Safe to re-run: checks the current dimension first.
    """
    inspector = inspect(engine)

    if "knowledge_base" not in inspector.get_table_names():
        logger.error("Table 'knowledge_base' does not exist. Run your init-db.sql first.")
        return

    cols = {col["name"]: col for col in inspector.get_columns("knowledge_base")}
    if "embedding" not in cols:
        logger.info("Column 'knowledge_base.embedding' missing — will be created as vector(1024).")
    else:
        col_type = str(cols["embedding"]["type"])
        if "1024" in col_type:
            logger.info("Column 'knowledge_base.embedding' already vector(1024). Nothing to do.")
            return
        logger.info("Column 'knowledge_base.embedding' is %s — migrating to vector(1024)...", col_type)

    with engine.begin() as conn:
        # Drop HNSW / ivfflat index if it exists
        conn.execute(text(
            "DROP INDEX IF EXISTS knowledge_base_embedding_idx;"
        ))
        # Drop old column (also removes any inline constraint)
        conn.execute(text(
            "ALTER TABLE knowledge_base DROP COLUMN IF EXISTS embedding;"
        ))
        # Re-add with correct dimension; truncate stale rows first
        conn.execute(text("TRUNCATE TABLE knowledge_base RESTART IDENTITY CASCADE;"))
        conn.execute(text(
            "ALTER TABLE knowledge_base ADD COLUMN embedding vector(1024) NOT NULL;"
        ))
        # Recreate HNSW index
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS knowledge_base_embedding_idx "
            "ON knowledge_base USING hnsw (embedding vector_cosine_ops);"
        ))

    logger.info("Column 'knowledge_base.embedding' successfully migrated to vector(1024). "
                "All previous knowledge-base rows were cleared — please re-ingest your sources.")


def ensure_knowledge_base_source_column() -> None:
    inspector = inspect(engine)
    if "knowledge_base" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("knowledge_base")}
    if "source" in columns:
        logger.info("Column 'knowledge_base.source' already exists. Nothing to do.")
        return
    logger.info("Adding column 'knowledge_base.source'...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS source VARCHAR(500);"))
    logger.info("Column 'knowledge_base.source' added.")


def main() -> None:
    logger.info("Starting custom DB migration based on SQLAlchemy models...")
    ensure_chat_sessions_status_column()
    ensure_knowledge_base_embedding_dim()
    ensure_knowledge_base_source_column()
    logger.info("Migration finished.")


if __name__ == "__main__":
    main()

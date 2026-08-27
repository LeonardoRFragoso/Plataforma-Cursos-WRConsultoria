"""Script administrativo idempotente para ingestion do Tutor NR.

Lê os 15 extracted-text.md do diretório local de análise, faz upload
para o storage privado (S3/Tebi) e ingeri os chunks no banco de dados.

Uso:
    # Dry-run (padrão — não persiste nada)
    python -m app.scripts.ingest_nr_tutor_knowledge --dry-run

    # Aplicar (persiste no banco + storage)
    python -m app.scripts.ingest_nr_tutor_knowledge --apply

    # Apenas uma fonte
    python -m app.scripts.ingest_nr_tutor_knowledge --apply --source nr10-sep

    # Reindexar (força reprocessamento mesmo se hash não mudou)
    python -m app.scripts.ingest_nr_tutor_knowledge --apply --reindex

Variáveis de ambiente:
    TUTOR_KNOWLEDGE_DIR: diretório com as pastas nr*/extracted-text.md
                         (padrão: /home/leonardo/dev/Cursos-WR/analysis)
    DATABASE_URL: URL do banco PostgreSQL
    STORAGE_*: configurações do storage S3/Tebi
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.services.tutor.ingestion import ingest_all
from app.services.tutor.sources import EXPECTED_SLUGS, SOURCES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_nr_tutor_knowledge")

DEFAULT_KNOWLEDGE_DIR = "/home/leonardo/dev/Cursos-WR/analysis"


def _load_source_contents(knowledge_dir: Path) -> dict[str, str]:
    """Lê os 15 extracted-text.md do diretório de análise."""
    contents = {}
    for source in SOURCES:
        filepath = knowledge_dir / source.slug / "extracted-text.md"
        if filepath.exists():
            contents[source.slug] = filepath.read_text(encoding="utf-8")
            logger.info("Loaded %s: %d chars", source.slug, len(contents[source.slug]))
        else:
            logger.warning("MISSING: %s (expected at %s)", source.slug, filepath)
    return contents


def _build_storage_keys(tenant_id: str) -> dict[str, str]:
    """Constrói as storage keys privadas para cada fonte."""
    keys = {}
    for source in SOURCES:
        keys[source.slug] = (
            f"tenants/{tenant_id}/tutor-knowledge/sources/"
            f"{source.slug}/extracted-text.md"
        )
    return keys


async def _upload_to_storage(
    contents: dict[str, str],
    storage_keys: dict[str, str],
) -> dict[str, str]:
    """Faz upload dos documentos para o storage privado.

    Retorna dict de {slug: storage_key} para uploads bem-sucedidos.
    Para storage local, simplesmente grava no diretório.
    """
    from app.core.config import settings
    from app.core.storage import _is_local_backend, save_local_file

    uploaded = {}
    if _is_local_backend():
        for slug, content in contents.items():
            key = storage_keys[slug]
            try:
                save_local_file(key, content.encode("utf-8"), "text/markdown")
                uploaded[slug] = key
                logger.info("Uploaded (local) %s → %s", slug, key)
            except Exception as exc:  # noqa: BLE001
                logger.error("Upload failed for %s: %s", slug, exc)
    else:
        from app.core.storage import _get_s3_client
        s3 = _get_s3_client()
        for slug, content in contents.items():
            key = storage_keys[slug]
            try:
                s3.put_object(
                    Bucket=settings.STORAGE_BUCKET,
                    Key=key,
                    Body=content.encode("utf-8"),
                    ContentType="text/markdown",
                    Metadata={
                        "source_slug": slug,
                        "content_type": "text/markdown",
                    },
                )
                uploaded[slug] = key
                logger.info("Uploaded (S3) %s → %s", slug, key)
            except Exception as exc:  # noqa: BLE001
                logger.error("Upload failed for %s: %s", slug, exc)

    return uploaded


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingestion do Tutor NR knowledge base"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Simula sem persistir (padrão)",
    )
    parser.add_argument(
        "--apply", action="store_true", default=False,
        help="Persiste no banco e storage",
    )
    parser.add_argument(
        "--source", action="append", dest="sources",
        help="Processa apenas estas fontes (slug)",
    )
    parser.add_argument(
        "--reindex", action="store_true", default=False,
        help="Força reprocessamento mesmo se hash não mudou",
    )
    args = parser.parse_args()

    apply_mode = args.apply
    dry_run = not apply_mode
    only_slugs = args.sources

    knowledge_dir = Path(
        os.environ.get("TUTOR_KNOWLEDGE_DIR", DEFAULT_KNOWLEDGE_DIR)
    )

    logger.info("=== NR Tutor Knowledge Ingestion ===")
    logger.info("Mode: %s", "APPLY" if apply_mode else "DRY-RUN")
    logger.info("Knowledge dir: %s", knowledge_dir)
    logger.info("Sources: %s", only_slugs or "ALL 15")

    # Validate sources
    if only_slugs:
        for slug in only_slugs:
            if slug not in EXPECTED_SLUGS:
                logger.error("Unknown source slug: %s", slug)
                return 1

    # Load contents
    contents = _load_source_contents(knowledge_dir)
    if not contents:
        logger.error("No content files found in %s", knowledge_dir)
        return 1

    missing = set(EXPECTED_SLUGS) - set(contents.keys())
    if missing:
        logger.warning("Missing sources: %s", sorted(missing))

    if only_slugs:
        contents = {k: v for k, v in contents.items() if k in only_slugs}

    tenant_id = str(WR_TENANT_ID)
    storage_keys = _build_storage_keys(tenant_id)

    if dry_run:
        # Dry-run: just show what would happen
        from app.services.tutor.chunking import chunk_document
        from app.services.tutor.ingestion import compute_document_hash, count_headings

        logger.info("\n--- DRY RUN (no persistence) ---")
        total_chunks = 0
        for slug, content in sorted(contents.items()):
            chunks = chunk_document(content, "")
            doc_hash = compute_document_hash(content)
            headings = count_headings(content)
            total_chunks += len(chunks)
            logger.info(
                "  %s: chars=%d headings=%d chunks=%d hash=%s",
                slug, len(content), headings, len(chunks), doc_hash[:12],
            )
        logger.info("Total: %d sources, %d chunks", len(contents), total_chunks)
        logger.info("Run with --apply to persist.")
        return 0

    # Apply mode: upload + ingest
    logger.info("Uploading documents to private storage...")
    uploaded = await _upload_to_storage(contents, storage_keys)
    logger.info("Uploaded %d/%d documents", len(uploaded), len(contents))

    # Ingest into database
    logger.info("Ingesting into database...")
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(
            text(f"SET LOCAL app.current_tenant = '{tenant_id}'")
        )

        report = await ingest_all(
            db,
            WR_TENANT_ID,
            contents,
            storage_keys,
            dry_run=False,
            only_slugs=only_slugs,
        )

        await db.commit()

    # Print report
    logger.info("\n=== INGESTION REPORT ===")
    logger.info("Documents changed: %d", report.documents_changed)
    logger.info("Chunks created: %d", report.chunks_created)
    logger.info("Unchanged: %d", report.unchanged)
    logger.info("Missing: %d", report.missing)
    logger.info("Errors: %d", report.errors)

    for result in report.results:
        logger.info(
            "  %s: %s (chars=%d chunks=%d headings=%d hash=%s)",
            result.source_slug, result.status,
            result.char_count, result.chunk_count, result.heading_count,
            result.content_hash[:12] if result.content_hash else "N/A",
        )

    # Coverage check
    indexed = sum(1 for r in report.results if r.status in ("CREATED", "UPDATED", "UNCHANGED"))
    logger.info("\nCoverage: %d/%d sources indexed", indexed, len(EXPECTED_SLUGS))

    if report.errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

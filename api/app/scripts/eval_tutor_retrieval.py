"""Avaliação de retrieval do Tutor NR contra o golden dataset.

Ingesta todas as 15 fontes de conhecimento, executa cada pergunta do
golden dataset e calcula métricas:

- Top-1 source accuracy
- Top-3 source recall
- Multi-source recall
- Wrong-variant rate

Uso:
    cd api
    WR_TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos_test_cert" \
      venv/bin/python -m app.scripts.eval_tutor_retrieval

Não expõe conteúdo privado integral — apenas slugs, scores e métricas.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal, Base, engine
from app.models.tenant import Tenant, TenantStatus
from app.services.tutor.ingestion import ingest_all
from app.services.tutor.retrieval import retrieve
from app.services.tutor.sources import SOURCES


GOLDEN_PATH = Path(__file__).resolve().parent.parent.parent.parent / "analysis" / "tutor" / "golden-retrieval-cases.json"
KNOWLEDGE_DIR = Path("/home/leonardo/dev/Cursos-WR/analysis")


async def setup_database():
    """Cria schema e insere tenant + todas as 15 fontes."""
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await conn.execute(text("""
            DO $$ DECLARE t text;
            BEGIN
                FOR t IN SELECT typname FROM pg_type
                    JOIN pg_namespace n ON n.oid = pg_type.typnamespace
                    WHERE typtype = 'e' AND n.nspname = 'public'
                LOOP EXECUTE format('DROP TYPE IF EXISTS %I CASCADE', t); END LOOP;
            END $$
        """))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_user_tenant_email_lower "
            "ON users (tenant_id, lower(email))"
        ))
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION tutor_chunk_search_vector_update() RETURNS trigger AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('portuguese', coalesce(NEW.heading, '')), 'A') ||
                    setweight(to_tsvector('portuguese', coalesce(NEW.heading_path, '')), 'B') ||
                    setweight(to_tsvector('portuguese', coalesce(NEW.content, '')), 'C');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        await conn.execute(text("""
            CREATE TRIGGER tutor_chunk_search_vector_trigger
            BEFORE INSERT OR UPDATE ON tutor_knowledge_chunks
            FOR EACH ROW EXECUTE FUNCTION tutor_chunk_search_vector_update();
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_tutor_chunk_search_vector "
            "ON tutor_knowledge_chunks USING gin(search_vector)"
        ))
        for table in ('tutor_knowledge_documents', 'tutor_knowledge_chunks'):
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
            await conn.execute(text(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}"))
            await conn.execute(text(
                f"CREATE POLICY tenant_isolation_{table} ON {table} "
                f"FOR ALL TO public "
                f"USING (tenant_id = current_setting('app.current_tenant', true)::UUID)"
            ))

    # Insert tenant
    async with AsyncSessionLocal() as session:
        existing = await session.get(Tenant, WR_TENANT_ID)
        if not existing:
            session.add(Tenant(
                id=WR_TENANT_ID,
                name="WR Consultoria",
                slug="wr",
                status=TenantStatus.ACTIVE,
                contact_name="Admin",
                contact_email="admin@wr.com",
            ))
            await session.commit()

    # Ingest all 15 sources
    contents: dict[str, str] = {}
    storage_keys: dict[str, str] = {}
    for source in SOURCES:
        path = KNOWLEDGE_DIR / source.slug / "extracted-text.md"
        if not path.exists():
            print(f"WARNING: Missing source file: {path}")
            continue
        contents[source.slug] = path.read_text(encoding="utf-8")
        storage_keys[source.slug] = (
            f"tenants/{WR_TENANT_ID}/tutor-knowledge/sources/{source.slug}/extracted-text.md"
        )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        report = await ingest_all(db, WR_TENANT_ID, contents, storage_keys, dry_run=False)
        await db.commit()

    total_chunks = sum(r.chunk_count for r in report.results)
    print(f"Ingested {len(report.results)} sources, {total_chunks} chunks")
    return report


async def evaluate_single(question: str, expected_sources: list[str],
                          forbidden_primary: list[str],
                          conversation_context: list[dict] | None = None) -> dict:
    """Avalia uma única pergunta."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        result = await retrieve(
            db, WR_TENANT_ID, question,
            top_k=6,
            conversation_context=conversation_context,
        )

    retrieved_sources = list({c.source_slug for c in result.chunks})
    top1_source = result.chunks[0].source_slug if result.chunks else None
    top3_sources = list({c.source_slug for c in result.chunks[:3]})

    # Metrics for this case
    top1_correct = top1_source in expected_sources if top1_source else False
    top1_forbidden = top1_source in forbidden_primary if top1_source else False

    # Top-3 recall: how many expected sources appear in top-3
    top3_recall = len(set(expected_sources) & set(top3_sources)) / len(expected_sources) if expected_sources else 0

    # Full recall: how many expected sources appear in all retrieved
    full_recall = len(set(expected_sources) & set(retrieved_sources)) / len(expected_sources) if expected_sources else 0

    return {
        "question": question[:80],
        "expected_sources": expected_sources,
        "retrieved_sources": retrieved_sources,
        "top1_source": top1_source,
        "top1_correct": top1_correct,
        "top1_forbidden": top1_forbidden,
        "top3_sources": top3_sources,
        "top3_recall": top3_recall,
        "full_recall": full_recall,
        "total_chunks": len(result.chunks),
        "top_score": result.debug.get("top_score", 0),
        "detected_scope": result.debug.get("detected_scope", []),
        "exact_terms": result.debug.get("exact_terms", [])[:5],
    }


async def main():
    # Load golden dataset
    with open(GOLDEN_PATH) as f:
        golden = json.load(f)

    cases = golden["cases"]
    print(f"Loaded {len(cases)} golden cases")

    # Setup database with all 15 sources
    await setup_database()

    # Evaluate each case
    results = []
    for case in cases:
        context = None
        if "expected_context" in case:
            ctx = case["expected_context"]
            context = [{"role": "user", "text": ctx["prev_question"]}]

        result = await evaluate_single(
            case["question"],
            case["expected_sources"],
            case.get("forbidden_primary_sources", []),
            conversation_context=context,
        )
        results.append(result)

        status = "✓" if result["top1_correct"] and not result["top1_forbidden"] else "✗"
        print(
            f"{status} Q: {result['question'][:50]:50s} "
            f"top1={result['top1_source']:25s} "
            f"expected={result['expected_sources']} "
            f"recall={result['full_recall']:.0%}"
        )

    # Calculate aggregate metrics
    total = len(results)
    top1_correct = sum(1 for r in results if r["top1_correct"])
    top1_forbidden = sum(1 for r in results if r["top1_forbidden"])
    top3_recall_avg = sum(r["top3_recall"] for r in results) / total
    full_recall_avg = sum(r["full_recall"] for r in results) / total

    # Multi-source cases
    multi_cases = [r for r in results if len(r["expected_sources"]) > 1]
    multi_recall_avg = (
        sum(r["full_recall"] for r in multi_cases) / len(multi_cases)
        if multi_cases else 0
    )

    # Wrong-variant rate: top1 is forbidden
    wrong_variant_rate = top1_forbidden / total

    metrics = {
        "total_cases": total,
        "top1_accuracy": top1_correct / total,
        "top1_forbidden_count": top1_forbidden,
        "top3_recall_avg": top3_recall_avg,
        "full_recall_avg": full_recall_avg,
        "multi_source_recall_avg": multi_recall_avg,
        "multi_source_cases": len(multi_cases),
        "wrong_variant_rate": wrong_variant_rate,
        "thresholds": {
            "top1_accuracy_target": 0.90,
            "top3_recall_target": 0.95,
            "wrong_variant_max": 0.05,
        },
        "meets_thresholds": {
            "top1": top1_correct / total >= 0.90,
            "top3_recall": top3_recall_avg >= 0.95,
            "wrong_variant": wrong_variant_rate <= 0.05,
        },
    }

    print("\n" + "=" * 70)
    print("RETRIEVAL METRICS SUMMARY")
    print("=" * 70)
    print(f"Total cases:              {total}")
    print(f"Top-1 accuracy:           {top1_correct}/{total} = {top1_correct/total:.1%} (target: 90%)")
    print(f"Top-3 recall (avg):       {top3_recall_avg:.1%} (target: 95%)")
    print(f"Full recall (avg):        {full_recall_avg:.1%}")
    print(f"Multi-source recall:      {multi_recall_avg:.1%} ({len(multi_cases)} cases)")
    print(f"Wrong-variant rate:       {wrong_variant_rate:.1%} (max: 5%)")
    print(f"Top-1 forbidden count:    {top1_forbidden}")
    print()
    all_pass = all(metrics["meets_thresholds"].values())
    print(f"MEETS ALL THRESHOLDS: {'YES' if all_pass else 'NO'}")

    # Save detailed results
    output = {
        "metrics": metrics,
        "results": results,
    }
    output_path = Path(__file__).resolve().parent.parent.parent.parent / "analysis" / "tutor" / "retrieval-eval-results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to: {output_path}")

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

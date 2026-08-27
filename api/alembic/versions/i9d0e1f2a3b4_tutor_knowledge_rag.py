"""tutor knowledge rag tables with RLS and FTS

Revision ID: i9d0e1f2a3b4
Revises: h6c7d8e9f0a1
Create Date: 2026-08-27 08:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'i9d0e1f2a3b4'
down_revision: str | None = 'h6c7d8e9f0a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria tabelas tutor_knowledge_documents e tutor_knowledge_chunks com RLS + FTS."""
    tutor_knowledge_status = postgresql.ENUM(
        'ACTIVE', 'SUPERSEDED', 'ARCHIVED', name='tutorknowledgestatus',
    )
    tutor_knowledge_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'tutor_knowledge_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('source_slug', sa.String(100), nullable=False),
        sa.Column('nr_code', sa.String(20), nullable=False),
        sa.Column('course_variant', sa.String(100), nullable=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('knowledge_version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('status', tutor_knowledge_status, nullable=False, server_default='ACTIVE'),
        sa.Column('char_count', sa.Integer, nullable=True),
        sa.Column('chunk_count', sa.Integer, nullable=True),
        sa.Column('heading_count', sa.Integer, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'source_slug', 'knowledge_version',
                            name='uq_tutor_doc_tenant_slug_version'),
    )
    op.create_index('ix_tutor_doc_tenant_nr', 'tutor_knowledge_documents',
                    ['tenant_id', 'nr_code'])
    op.create_index('ix_tutor_doc_tenant_status', 'tutor_knowledge_documents',
                    ['tenant_id', 'status'])

    op.create_table(
        'tutor_knowledge_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tutor_knowledge_documents.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('heading', sa.String(500), nullable=True),
        sa.Column('heading_path', sa.Text, nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('search_vector', postgresql.TSVECTOR, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_tutor_chunk_doc_index'),
    )
    op.create_index('ix_tutor_chunk_tenant_doc', 'tutor_knowledge_chunks',
                    ['tenant_id', 'document_id'])
    op.create_index('ix_tutor_chunk_tenant_active', 'tutor_knowledge_chunks',
                    ['tenant_id', 'is_active'])

    # GIN index for full-text search on tsvector
    op.create_index(
        'ix_tutor_chunk_search_vector',
        'tutor_knowledge_chunks',
        ['search_vector'],
        postgresql_using='gin',
    )

    # Trigger to auto-populate search_vector from content using Portuguese config
    op.execute("""
        CREATE OR REPLACE FUNCTION tutor_chunk_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('portuguese', coalesce(NEW.heading, '')), 'A') ||
                setweight(to_tsvector('portuguese', coalesce(NEW.heading_path, '')), 'B') ||
                setweight(to_tsvector('portuguese', coalesce(NEW.content, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER tutor_chunk_search_vector_trigger
        BEFORE INSERT OR UPDATE ON tutor_knowledge_chunks
        FOR EACH ROW EXECUTE FUNCTION tutor_chunk_search_vector_update();
    """)

    # RLS for tenant isolation
    for table in ('tutor_knowledge_documents', 'tutor_knowledge_chunks'):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"FOR ALL TO public "
            f"USING (tenant_id = current_setting('app.current_tenant', true)::UUID)"
        )


def downgrade() -> None:
    """Remove tabelas do Tutor NR knowledge RAG."""
    for table in ('tutor_knowledge_chunks', 'tutor_knowledge_documents'):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP TRIGGER IF EXISTS tutor_chunk_search_vector_trigger ON tutor_knowledge_chunks")
    op.execute("DROP FUNCTION IF EXISTS tutor_chunk_search_vector_update()")

    op.drop_table('tutor_knowledge_chunks')
    op.drop_table('tutor_knowledge_documents')

    tutor_knowledge_status = postgresql.ENUM(
        'ACTIVE', 'SUPERSEDED', 'ARCHIVED', name='tutorknowledgestatus',
    )
    tutor_knowledge_status.drop(op.get_bind(), checkfirst=True)

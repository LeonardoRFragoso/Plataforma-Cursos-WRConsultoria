import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Adicionar a pasta api ao path para importar os módulos do app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.core.database import Base

# Importar todos os models para registrar suas tabelas no Base.metadata
from app.models.attendance import Attendance  # noqa: F401
from app.models.certificate import Certificate  # noqa: F401
from app.models.class_model import Class  # noqa: F401
from app.models.company import Company  # noqa: F401
from app.models.course import Course  # noqa: F401
from app.models.enrollment import Enrollment  # noqa: F401
from app.models.lesson import Lesson, LessonMaterial, LessonProgress  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.plan import Plan  # noqa: F401
from app.models.student import Student  # noqa: F401
from app.models.tenant import PartnerLead, Tenant  # noqa: F401
from app.models.tenant_secret import TenantSecret  # noqa: F401
from app.models.tenant_subscription import TenantSubscription  # noqa: F401
from app.models.user import User  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Usar a DATABASE_URL do settings (.env ou padrão)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

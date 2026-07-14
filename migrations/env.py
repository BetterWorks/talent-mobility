import asyncio
from logging import getLogger
from logging.config import fileConfig

from sqlalchemy import inspect, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.schema import CreateSchema

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
from app.settings import CELERY_RESULT_TABLES, DATABASE_SCHEMA, DATABASE_URL
from app.db.candidate_profile import CandidateProfile  # noqa: F401
from app.db.data_embeddings import DataEmbeddings  # noqa: F401
from app.db.internal_mobility_request import InternalMobilityRequest  # noqa: F401
from app.db.run_ai_matches import RunAiMatches  # noqa: F401
from app.db.users_hris_details import UsersHrisDetails  # noqa: F401
from app.db import meta

config = context.config

logger = getLogger('alembic.runtime.migration')

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option('sqlalchemy.url', DATABASE_URL)

target_metadata = meta


def include_name_filter(name, type_, parent_names):
    if type_ == "schema":
        return name == target_metadata.schema

    if type_ == "table":
        if name in CELERY_RESULT_TABLES.values():
            return False

    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=target_metadata.schema,
        include_schemas=True,
        include_name=include_name_filter
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # The following 3 lines are required to support non-default
        # database schema for our database objects
        version_table_schema=target_metadata.schema,
        include_schemas=True,
        include_name=include_name_filter
    )

    with context.begin_transaction():
        if DATABASE_SCHEMA not in inspect(connection).get_schema_names():
            logger.info("`%s` DB schema not found, creating it..." % DATABASE_SCHEMA)
            try:
                connection.execute(CreateSchema(DATABASE_SCHEMA))
            except Exception as e:
                logger.error("Error occurred while creating schema")
                raise e

            logger.info("`%s` DB schema created successfully..." % DATABASE_SCHEMA)
        else:
            logger.info("`%s` DB schema found, continuing with the migrations..." % DATABASE_SCHEMA)

        if DATABASE_SCHEMA not in inspect(connection).get_schema_names():
            raise Exception("Unable to find/create the `%s` DB schema needed for this app" % DATABASE_SCHEMA)

        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from typing import AsyncIterable

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.settings import DATABASE_SCHEMA, DATABASE_URL, get_async_engine_options
from app.utils.logs import agent


meta = MetaData(schema=DATABASE_SCHEMA)
engine = create_async_engine(DATABASE_URL, **get_async_engine_options())

logger = agent.get_context_bound_logger()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Database schema created/refreshed successfully")


async def get_session() -> AsyncIterable[AsyncSession]:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@event.listens_for(engine.sync_engine, "handle_error")
def handle_sqlalchemy_errors(context):
    exc = context.original_exception
    if isinstance(exc, Exception):
        error_message = (f'An error occurred during the database interaction: {str(exc)}\n'
                         f'[SQL: {str(context.statement)}]')
        logger.error(error_message, exc_info=True)

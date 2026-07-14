from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import engine


def get_utc_now(tz: bool = True) -> datetime:
    dt = datetime.now(timezone.utc)
    if tz:
        return dt
    return dt.replace(tzinfo=None)


async def run_async_session_task(task, *args, **kwargs):
    ''' creates async_session and passes it as the first arg in called task function '''
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        return await task(session, *args, **kwargs)

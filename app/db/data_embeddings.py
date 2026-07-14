from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.mutable import MutableDict
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class DataEmbeddingsBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)

    user_uuid: UUID = Field()
    org_uuid: UUID = Field()

    data: Optional[dict] = Field(default=None)
    embedding_gemma: Optional[list] = Field(default=None, sa_column=Column(HALFVEC(768)))

    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    hash_id: Optional[str] = Field(default=None)
    date: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    module: Optional[str] = Field(default=None)


class DataEmbeddings(DataEmbeddingsBase, table=True):
    __tablename__ = 'data_embeddings'
    metadata = meta
    data: Optional[dict] = Field(default=None, sa_column=Column(MutableDict.as_mutable(JSONB)))

    class Config:
        arbitrary_types_allowed = True


class DataEmbeddingsDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: DataEmbeddingsBase) -> DataEmbeddings:
        new_embedding = DataEmbeddings(**data.model_dump())
        self.session.add(new_embedding)
        await self.session.commit()
        await self.session.refresh(new_embedding)
        return new_embedding

    async def get_by_hash_id(self, hash_id: str) -> Optional[DataEmbeddings]:
        result = await self.session.execute(
            select(DataEmbeddings).where(DataEmbeddings.hash_id == hash_id)
        )
        return result.scalars().first()

    async def get_by_user(self, user_uuid: UUID, org_uuid: UUID, module: Optional[str] = None):
        result = await self.session.execute(
            select(DataEmbeddings).where(
                DataEmbeddings.user_uuid == user_uuid,
                DataEmbeddings.org_uuid == org_uuid,
                True if module is None else DataEmbeddings.module == module,
            )
        )
        return result.scalars().all()

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, func, over, select
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

    async def top_candidates(
        self, jd_vec: list[float], limit: int = 5, top_k: int = 10
    ) -> list[tuple[UUID, UUID, float]]:
        """Rank users by similarity to the JD vector and return the top `limit`.

        Module-agnostic: for every user, each of their embedding rows is scored
        by cosine similarity to the JD, ranked, and only that user's `top_k`
        best-matching rows are averaged into a single per-user match score.
        Users are then ordered by that score. The mean of the top_k best rows
        (rather than MAX or a full AVG) keeps the score robust whether a user
        has few rows or many.

        Returns (user_uuid, org_uuid, match_score) tuples, best first. The score
        is a raw cosine similarity (~0.3-0.5), suitable for ranking; it is not a
        calibrated display percentage.
        """
        distance = DataEmbeddings.embedding_gemma.cosine_distance(jd_vec)

        ranked = (
            select(
                DataEmbeddings.user_uuid.label('user_uuid'),
                DataEmbeddings.org_uuid.label('org_uuid'),
                (1 - distance).label('sim'),
                over(
                    func.row_number(),
                    partition_by=DataEmbeddings.user_uuid,
                    order_by=distance.asc(),
                ).label('rn'),
            )
            .where(DataEmbeddings.embedding_gemma.is_not(None))
            .subquery()
        )

        stmt = (
            select(
                ranked.c.user_uuid,
                ranked.c.org_uuid,
                func.avg(ranked.c.sim).label('match_score'),
            )
            .where(ranked.c.rn <= top_k)
            .group_by(ranked.c.user_uuid, ranked.c.org_uuid)
            .order_by(func.avg(ranked.c.sim).desc())
            .limit(limit)
        )

        rows = (await self.session.execute(stmt)).all()
        return [(r.user_uuid, r.org_uuid, float(r.match_score)) for r in rows]

    async def top_rows_for_user(
        self, user_uuid: UUID, org_uuid: UUID, jd_vec: list[float], k: int = 10
    ) -> list[DataEmbeddings]:
        """Return a single user's `k` embedding rows most similar to the JD.

        These are the evidence data points fed to the LLM synthesis prompt, so
        the model sees the most role-relevant facts for this user rather than an
        arbitrary slice of their rows.
        """
        distance = DataEmbeddings.embedding_gemma.cosine_distance(jd_vec)
        stmt = (
            select(DataEmbeddings)
            .where(
                DataEmbeddings.user_uuid == user_uuid,
                DataEmbeddings.org_uuid == org_uuid,
                DataEmbeddings.embedding_gemma.is_not(None),
            )
            .order_by(distance.asc())
            .limit(k)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

"""create better_sense schema tables

Revision ID: 9f1a2b3c4d5e
Revises:
Create Date: 2026-07-14 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel
from app.settings import DATABASE_SCHEMA
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import HALFVEC

# revision identifiers, used by Alembic.
revision = '9f1a2b3c4d5e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'internal_mobility_request',
        sa.Column('id', sqlmodel.sql.sqltypes.GUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('job_description', sa.Text(), nullable=True),
        sa.Column('seniority_level', sa.Text(), nullable=True),
        sa.Column('business_unit', sa.Text(), nullable=True),
        sa.Column('hiring_manager', sa.Text(), nullable=True),
        sa.Column('min_salary', sa.Numeric(18, 2), nullable=True),
        sa.Column('max_salary', sa.Numeric(18, 2), nullable=True),
        sa.Column('budget_currency', sa.Text(), nullable=True),
        sa.Column('required_skills', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('number_of_candidates_to_hire', sa.Integer(), nullable=True),
        sa.Column('hiring_estimate_in_days', sa.Integer(), nullable=True),
        sa.Column('external_hiring_cost', sa.Numeric(18, 2), nullable=True),
        sa.Column('start_date_target', sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='internal_mobility_request_pkey'),
        schema=DATABASE_SCHEMA,
    )
    op.create_index('idx_imr_business_unit', 'internal_mobility_request', ['business_unit'], schema=DATABASE_SCHEMA)
    op.create_index('idx_imr_hiring_manager', 'internal_mobility_request', ['hiring_manager'], schema=DATABASE_SCHEMA)
    op.create_index('idx_imr_seniority_level', 'internal_mobility_request', ['seniority_level'], schema=DATABASE_SCHEMA)
    op.create_index('idx_imr_created', 'internal_mobility_request', ['created'], schema=DATABASE_SCHEMA)

    op.create_table(
        'users_hris_details',
        sa.Column('id', sqlmodel.sql.sqltypes.GUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_uuid', sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column('org_uuid', sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('current_salary', sa.Numeric(18, 2), nullable=True),
        sa.Column('hike_given_on', sa.Date(), nullable=True),
        sa.Column('hike_percentage', sa.Numeric(7, 4), nullable=True),
        sa.PrimaryKeyConstraint('id', name='users_hris_details_pkey'),
        schema=DATABASE_SCHEMA,
    )
    op.create_index(
        'idx_uhd_user_org_uuid', 'users_hris_details', ['user_uuid', 'org_uuid'],
        unique=True, schema=DATABASE_SCHEMA
    )
    op.create_index('idx_uhd_org_uuid', 'users_hris_details', ['org_uuid'], schema=DATABASE_SCHEMA)
    op.create_index('idx_uhd_user_uuid', 'users_hris_details', ['user_uuid'], schema=DATABASE_SCHEMA)

    op.create_table(
        'data_embeddings',
        sa.Column('id', sqlmodel.sql.sqltypes.GUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_uuid', sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column('org_uuid', sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('embedding_gemma', HALFVEC(768), nullable=True),
        sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('hash_id', sa.Text(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('module', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='data_embeddings_pkey'),
        schema=DATABASE_SCHEMA,
    )
    op.create_index(
        'idx_de_embedding_gemma_hnsw', 'data_embeddings', ['embedding_gemma'],
        schema=DATABASE_SCHEMA, postgresql_using='hnsw',
        postgresql_with={'m': '16', 'ef_construction': '64'},
        postgresql_ops={'embedding_gemma': 'halfvec_cosine_ops'},
    )
    op.create_index('idx_de_user_uuid', 'data_embeddings', ['user_uuid'], schema=DATABASE_SCHEMA)
    op.create_index('idx_de_org_uuid', 'data_embeddings', ['org_uuid'], schema=DATABASE_SCHEMA)
    op.create_index('idx_de_module', 'data_embeddings', ['module'], schema=DATABASE_SCHEMA)
    op.create_index(
        'idx_de_hash_id', 'data_embeddings', ['hash_id'],
        unique=True, schema=DATABASE_SCHEMA, postgresql_where=sa.text('hash_id IS NOT NULL')
    )
    op.create_index(
        'idx_de_data_gin', 'data_embeddings', ['data'],
        schema=DATABASE_SCHEMA, postgresql_using='gin'
    )

    op.create_table(
        'run_ai_matches',
        sa.Column('id', sqlmodel.sql.sqltypes.GUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('request_id', sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='run_ai_matches_pkey'),
        schema=DATABASE_SCHEMA,
    )
    op.create_index('idx_ram_request_id', 'run_ai_matches', ['request_id'], schema=DATABASE_SCHEMA)
    op.create_index('idx_ram_status', 'run_ai_matches', ['status'], schema=DATABASE_SCHEMA)
    op.create_index('idx_ram_created', 'run_ai_matches', ['created'], schema=DATABASE_SCHEMA)

    op.create_table(
        'candidate_profile',
        sa.Column('id', sqlmodel.sql.sqltypes.GUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_uuid', sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column('org_uuid', sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('modified', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('run_ai_match', sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column('profile_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='candidate_profile_pkey'),
        schema=DATABASE_SCHEMA,
    )
    op.create_index('idx_cp_run_ai_match', 'candidate_profile', ['run_ai_match'], schema=DATABASE_SCHEMA)
    op.create_index('idx_cp_user_uuid', 'candidate_profile', ['user_uuid'], schema=DATABASE_SCHEMA)
    op.create_index('idx_cp_org_uuid', 'candidate_profile', ['org_uuid'], schema=DATABASE_SCHEMA)
    op.create_index('idx_cp_status', 'candidate_profile', ['status'], schema=DATABASE_SCHEMA)
    op.create_index(
        'idx_cp_profile_data_gin', 'candidate_profile', ['profile_data'],
        schema=DATABASE_SCHEMA, postgresql_using='gin'
    )


def downgrade() -> None:
    op.drop_table('candidate_profile', schema=DATABASE_SCHEMA)
    op.drop_table('run_ai_matches', schema=DATABASE_SCHEMA)
    op.drop_table('data_embeddings', schema=DATABASE_SCHEMA)
    op.drop_table('users_hris_details', schema=DATABASE_SCHEMA)
    op.drop_table('internal_mobility_request', schema=DATABASE_SCHEMA)

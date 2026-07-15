-- =============================================================================
-- Schema: better_sense
-- Description: Internal mobility and candidate matching tables
-- Convention: UUIDs as PKs, timestamptz for timestamps, no enforced FKs
--             (cross-table references are logical, not constraint-based)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Schema
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS better_sense;


-- -----------------------------------------------------------------------------
-- 2. Table: internal_mobility_request
--    Stores job openings posted for internal mobility hiring.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS better_sense.internal_mobility_request (
    id                              uuid            NOT NULL DEFAULT gen_random_uuid(),

    -- Audit timestamps
    created                         timestamptz     NOT NULL DEFAULT now(),
    modified                        timestamptz     NOT NULL DEFAULT now(),

    -- Job details
    title                           text            NOT NULL,
    job_description                 text            NULL,
    seniority_level                 text            NULL,   -- app-level enum: junior | mid | senior | lead | principal | director | vp | c_level

    -- Organisational references (logical refs â no FK constraint)
    business_unit                   text            NULL,   -- ref: org business unit identifier
    hiring_manager                  text            NULL,   -- ref: core_profile.uuid

    -- Compensation
    min_salary                      numeric(18, 2)  NULL,
    max_salary                      numeric(18, 2)  NULL,
    budget_currency                 text            NULL,   -- e.g. 'INR', 'USD'

    -- Skills & hiring plan
    required_skills                 text[]          NULL,   -- array of skill names / UUIDs
    number_of_candidates_to_hire    integer         NULL,
    hiring_estimate_in_days         integer         NULL,
    external_hiring_cost            numeric(18, 2)  NULL,

    -- Timeline
    start_date_target               date            NULL,

    -- Workflow status (app-level enum: open | in_progress | review | approved | closed)
    status                          text            NOT NULL DEFAULT 'open',

    CONSTRAINT internal_mobility_request_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_imr_business_unit
    ON better_sense.internal_mobility_request USING btree (business_unit);

CREATE INDEX IF NOT EXISTS idx_imr_hiring_manager
    ON better_sense.internal_mobility_request USING btree (hiring_manager);

CREATE INDEX IF NOT EXISTS idx_imr_seniority_level
    ON better_sense.internal_mobility_request USING btree (seniority_level);

CREATE INDEX IF NOT EXISTS idx_imr_created
    ON better_sense.internal_mobility_request USING btree (created);

CREATE INDEX IF NOT EXISTS idx_imr_status
    ON better_sense.internal_mobility_request USING btree (status);


-- -----------------------------------------------------------------------------
-- 3. Table: users_hris_details
--    HR Information System snapshot per user per organisation.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS better_sense.users_hris_details (
    id                  uuid            NOT NULL DEFAULT gen_random_uuid(),

    -- Identity (logical refs to core user / org tables)
    user_uuid           uuid            NOT NULL,   -- ref: core_profile.uuid
    org_uuid            uuid            NOT NULL,   -- ref: organisation uuid
    org_id              integer         NULL,        -- ref: legacy org id
    user_id             integer         NULL,        -- ref: legacy user id

    -- Compensation history
    current_salary      numeric(18, 2)  NULL,
    hike_given_on       date            NULL,
    hike_percentage     numeric(7, 4)   NULL,       -- e.g. 12.5000 => 12.5 %

    CONSTRAINT users_hris_details_pkey PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_uhd_user_org_uuid
    ON better_sense.users_hris_details USING btree (user_uuid, org_uuid);

CREATE INDEX IF NOT EXISTS idx_uhd_org_uuid
    ON better_sense.users_hris_details USING btree (org_uuid);

CREATE INDEX IF NOT EXISTS idx_uhd_user_uuid
    ON better_sense.users_hris_details USING btree (user_uuid);


-- -----------------------------------------------------------------------------
-- 4. Table: data_embeddings
--    Structured data snapshots + vector embeddings per user.
--    Requires pgvector extension (public.halfvec) to be installed.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS better_sense.data_embeddings (
    id                  uuid            NOT NULL DEFAULT gen_random_uuid(),

    -- Identity (logical refs)
    user_uuid           uuid            NOT NULL,   -- ref: core_profile.uuid
    org_uuid            uuid            NOT NULL,   -- ref: organisation uuid

    -- Payload
    data                jsonb           NULL,
    embedding_gemma     public.halfvec(768)  NULL,  -- normalised vector (gemma model); 768 = gemma embedding dimensions

    -- Audit timestamps
    created             timestamptz     NOT NULL DEFAULT now(),
    modified            timestamptz     NOT NULL DEFAULT now(),

    -- Metadata
    hash_id             text            NULL,        -- dedup hash of the data point
    date                timestamptz     NULL,        -- application-level update date
    module              text            NULL,        -- source module name (e.g. 'goals', 'feedback')

    CONSTRAINT data_embeddings_pkey PRIMARY KEY (id)
);

-- HNSW vector index for cosine similarity search (mirrors embedding.skill pattern)
CREATE INDEX IF NOT EXISTS idx_de_embedding_gemma_hnsw
    ON better_sense.data_embeddings
    USING hnsw (embedding_gemma public.halfvec_cosine_ops)
    WITH (m = '16', ef_construction = '64');

CREATE INDEX IF NOT EXISTS idx_de_user_uuid
    ON better_sense.data_embeddings USING btree (user_uuid);

CREATE INDEX IF NOT EXISTS idx_de_org_uuid
    ON better_sense.data_embeddings USING btree (org_uuid);

CREATE INDEX IF NOT EXISTS idx_de_module
    ON better_sense.data_embeddings USING btree (module);

CREATE UNIQUE INDEX IF NOT EXISTS idx_de_hash_id
    ON better_sense.data_embeddings USING btree (hash_id)
    WHERE hash_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_de_data_gin
    ON better_sense.data_embeddings USING gin (data);


-- -----------------------------------------------------------------------------
-- 5. Table: run_ai_matches
--    Tracks AI matching job runs (parent of candidate_profile).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS better_sense.run_ai_matches (
    id          uuid        NOT NULL DEFAULT gen_random_uuid(),

    created     timestamptz NOT NULL DEFAULT now(),
    modified    timestamptz NOT NULL DEFAULT now(),

    -- Logical ref: better_sense.internal_mobility_request.id
    request_id  uuid        NULL,

    -- Run lifecycle status (app-level enum: pending | running | completed | failed)
    status      text        NULL,

    CONSTRAINT run_ai_matches_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_ram_request_id
    ON better_sense.run_ai_matches USING btree (request_id);

CREATE INDEX IF NOT EXISTS idx_ram_status
    ON better_sense.run_ai_matches USING btree (status);

CREATE INDEX IF NOT EXISTS idx_ram_created
    ON better_sense.run_ai_matches USING btree (created);


-- -----------------------------------------------------------------------------
-- 6. Table: candidate_profile
--    AI-generated candidate match profiles produced by a run_ai_matches run.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS better_sense.candidate_profile (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),

    -- Identity (logical refs)
    user_uuid       uuid        NOT NULL,   -- ref: core_profile.uuid
    org_uuid        uuid        NOT NULL,   -- ref: organisation uuid
    org_id          integer     NULL,        -- ref: legacy org id
    user_id         integer     NULL,        -- ref: legacy user id

    -- Audit timestamps
    created         timestamptz NOT NULL DEFAULT now(),
    modified        timestamptz NOT NULL DEFAULT now(),

    -- Logical ref: better_sense.run_ai_matches.id
    run_ai_match    uuid        NULL,

    -- Match output
    profile_data    jsonb       NULL,   -- matching metrics, skills breakdown, scores, etc.

    -- Workflow status (app-level enum)
    -- 0 = pending | 1 = matched | 2 = approved | 3 = hold | 4 = rejected
    status          integer     NOT NULL DEFAULT 0,

    CONSTRAINT candidate_profile_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_cp_run_ai_match
    ON better_sense.candidate_profile USING btree (run_ai_match);

CREATE INDEX IF NOT EXISTS idx_cp_user_uuid
    ON better_sense.candidate_profile USING btree (user_uuid);

CREATE INDEX IF NOT EXISTS idx_cp_org_uuid
    ON better_sense.candidate_profile USING btree (org_uuid);

CREATE INDEX IF NOT EXISTS idx_cp_status
    ON better_sense.candidate_profile USING btree (status);

CREATE INDEX IF NOT EXISTS idx_cp_profile_data_gin
    ON better_sense.candidate_profile USING gin (profile_data);


-- =============================================================================
-- End of migration
-- =============================================================================

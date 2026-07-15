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

    -- Employment snapshot (fed to the candidate deep-dive header)
    department          text            NULL,
    location            text            NULL,
    start_date          date            NULL,       -- used to derive tenure
    current_manager     text            NULL,       -- ref: core_profile.uuid (logical)
    job_level           text            NULL,        -- e.g. 'L5 · Senior'

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
    -- 5 = review | 6 = evidence_pending (reserved, not modeled yet) | 7 = decision
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


-- -----------------------------------------------------------------------------
-- 7. Table: decision
--    Human decision recorded against a candidate_profile (Decision Review screen).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS better_sense.decision (
    id                  uuid            NOT NULL DEFAULT gen_random_uuid(),

    -- Audit timestamps
    created             timestamptz     NOT NULL DEFAULT now(),
    modified            timestamptz     NOT NULL DEFAULT now(),

    -- Logical ref: better_sense.candidate_profile.id
    candidate_match_id  uuid            NOT NULL,

    -- app-level enum: approve | hold | reject | proceed_external
    outcome             text            NOT NULL,
    reason_code         text            NULL,   -- required by app logic for hold/reject/proceed_external
    note                text            NULL,
    review_date         date            NULL,

    -- Logical ref: better_sense.mobility_case.id — set only when outcome = approve
    case_id             uuid            NULL,

    CONSTRAINT decision_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_decision_candidate_match_id
    ON better_sense.decision USING btree (candidate_match_id);

CREATE INDEX IF NOT EXISTS idx_decision_case_id
    ON better_sense.decision USING btree (case_id);

CREATE INDEX IF NOT EXISTS idx_decision_created
    ON better_sense.decision USING btree (created);


-- -----------------------------------------------------------------------------
-- 8. Table: evidence_request
--    "Ask for Evidence" requests tracked against a candidate_profile.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS better_sense.evidence_request (
    id                  uuid            NOT NULL DEFAULT gen_random_uuid(),

    -- Audit timestamps
    created             timestamptz     NOT NULL DEFAULT now(),
    modified            timestamptz     NOT NULL DEFAULT now(),

    -- Logical ref: better_sense.candidate_profile.id
    candidate_match_id  uuid            NOT NULL,

    -- app-level enum: manager_validation | recent_feedback | skills_assessment |
    --                  project_impact | candidate_interest
    evidence_type       text            NOT NULL,

    -- ref: Haven's org-wide user identity search (BWUserIdentityAutoComplete) — a different
    -- identity source than users_hris_details/data_embeddings, so no local FK/name lookup exists
    assignee_id         uuid            NOT NULL,

    due_date            date            NULL,

    -- app-level enum: pending | received | disputed
    status              text            NOT NULL DEFAULT 'pending',
    response            text            NULL,
    note                text            NULL,

    CONSTRAINT evidence_request_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_er_candidate_match_id
    ON better_sense.evidence_request USING btree (candidate_match_id);

CREATE INDEX IF NOT EXISTS idx_er_status
    ON better_sense.evidence_request USING btree (status);

CREATE INDEX IF NOT EXISTS idx_er_created
    ON better_sense.evidence_request USING btree (created);


-- -----------------------------------------------------------------------------
-- 9. Table: mobility_case
--    Created when a candidate decision is approved; hands off to Consent/Planning/
--    Tracking/Outcomes (only Decision-stage fields are populated for now).
--    Named `mobility_case`, not `case` — `case` is a reserved SQL keyword.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS better_sense.mobility_case (
    id                  uuid            NOT NULL DEFAULT gen_random_uuid(),

    -- Audit timestamps
    created             timestamptz     NOT NULL DEFAULT now(),
    modified            timestamptz     NOT NULL DEFAULT now(),

    -- Logical refs
    candidate_match_id  uuid            NOT NULL,   -- ref: better_sense.candidate_profile.id
    role_request_id     uuid            NOT NULL,   -- ref: better_sense.internal_mobility_request.id
    decision_id         uuid            NULL,       -- ref: better_sense.decision.id

    -- app-level enum: consent_pending | planning | in_transition | at_risk | completed |
    --                  closed | declined | release_blocked
    status              text            NOT NULL DEFAULT 'consent_pending',

    CONSTRAINT mobility_case_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_mc_candidate_match_id
    ON better_sense.mobility_case USING btree (candidate_match_id);

CREATE INDEX IF NOT EXISTS idx_mc_role_request_id
    ON better_sense.mobility_case USING btree (role_request_id);

CREATE INDEX IF NOT EXISTS idx_mc_status
    ON better_sense.mobility_case USING btree (status);


-- =============================================================================
-- End of migration
-- =============================================================================

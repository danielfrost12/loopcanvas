-- ══════════════════════════════════════════════════════════════
-- LoopCanvas Job Queue — Supabase Schema
-- ══════════════════════════════════════════════════════════════
--
-- Run this in your Supabase SQL editor to create the job queue table.
-- Supabase free tier: 500MB database, 1GB file storage, 50K MAU.
-- This table will use < 1MB for thousands of jobs.
--
-- To set up:
--   1. Go to supabase.com and create a free project
--   2. Go to SQL Editor → New Query
--   3. Paste this entire file and click Run
--   4. Go to Settings → API → copy your URL and anon key
--   5. Set SUPABASE_URL and SUPABASE_KEY in your server environment

-- Canvas generation jobs
CREATE TABLE IF NOT EXISTS canvas_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Input
    audio_path TEXT NOT NULL,
    audio_url TEXT,
    direction JSONB,
    emotional_dna JSONB,
    params JSONB DEFAULT '{}',

    -- Worker
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    worker_type TEXT,

    -- Progress
    progress INTEGER DEFAULT 0,
    message TEXT DEFAULT '',
    generation_mode TEXT DEFAULT 'full',

    -- Output
    output_url TEXT,
    output_dir TEXT,
    quality_score REAL,
    loop_score REAL,

    -- Retry
    attempt INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error TEXT,

    -- Priority (lower = higher priority)
    priority INTEGER DEFAULT 10
);

-- Index for fast job claiming (workers query queued jobs sorted by priority)
CREATE INDEX IF NOT EXISTS idx_canvas_jobs_queued
    ON canvas_jobs (priority, created_at)
    WHERE status = 'queued';

-- Index for status queries
CREATE INDEX IF NOT EXISTS idx_canvas_jobs_status
    ON canvas_jobs (status);

-- Index for worker lookups
CREATE INDEX IF NOT EXISTS idx_canvas_jobs_worker
    ON canvas_jobs (claimed_by)
    WHERE claimed_by IS NOT NULL;

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER canvas_jobs_updated_at
    BEFORE UPDATE ON canvas_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ══════════════════════════════════════════════════════════════
-- Atomic claim function (prevents race conditions between workers)
-- ══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION claim_next_job(
    p_worker_id TEXT,
    p_worker_type TEXT DEFAULT 'unknown'
)
RETURNS TABLE (
    job_id TEXT,
    audio_path TEXT,
    audio_url TEXT,
    direction JSONB,
    emotional_dna JSONB,
    params JSONB,
    priority INTEGER
) AS $$
DECLARE
    v_job_id TEXT;
BEGIN
    -- Atomically select and update in one statement
    UPDATE canvas_jobs
    SET
        status = 'claimed',
        claimed_by = p_worker_id,
        claimed_at = NOW(),
        worker_type = p_worker_type
    WHERE canvas_jobs.job_id = (
        SELECT canvas_jobs.job_id
        FROM canvas_jobs
        WHERE canvas_jobs.status = 'queued'
        ORDER BY canvas_jobs.priority ASC, canvas_jobs.created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING
        canvas_jobs.job_id,
        canvas_jobs.audio_path,
        canvas_jobs.audio_url,
        canvas_jobs.direction,
        canvas_jobs.emotional_dna,
        canvas_jobs.params,
        canvas_jobs.priority
    INTO job_id, audio_path, audio_url, direction, emotional_dna, params, priority;

    IF job_id IS NOT NULL THEN
        RETURN QUERY SELECT job_id, audio_path, audio_url, direction, emotional_dna, params, priority;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ══════════════════════════════════════════════════════════════
-- Stale job cleanup (re-queue jobs claimed > 30 min ago)
-- ══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION cleanup_stale_jobs(
    p_timeout_minutes INTEGER DEFAULT 30
)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE canvas_jobs
    SET
        status = 'queued',
        claimed_by = NULL,
        claimed_at = NULL,
        message = 'Re-queued: worker timed out'
    WHERE status IN ('claimed', 'generating')
      AND claimed_at < NOW() - (p_timeout_minutes || ' minutes')::INTERVAL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- ══════════════════════════════════════════════════════════════
-- Queue stats view
-- ══════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW queue_stats AS
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'queued') AS queued,
    COUNT(*) FILTER (WHERE status = 'claimed') AS claimed,
    COUNT(*) FILTER (WHERE status = 'generating') AS generating,
    COUNT(*) FILTER (WHERE status = 'complete') AS complete,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    COUNT(*) FILTER (WHERE status = 'dead') AS dead,
    AVG(quality_score) FILTER (WHERE status = 'complete') AS avg_quality,
    AVG(loop_score) FILTER (WHERE status = 'complete') AS avg_loop_score
FROM canvas_jobs;

-- ══════════════════════════════════════════════════════════════
-- Row Level Security (optional but recommended)
-- ══════════════════════════════════════════════════════════════

-- Enable RLS
ALTER TABLE canvas_jobs ENABLE ROW LEVEL SECURITY;

-- Allow all operations via the service role / anon key
-- (For production, restrict to authenticated users)
CREATE POLICY "Allow all operations" ON canvas_jobs
    FOR ALL
    USING (true)
    WITH CHECK (true);

# WEEK 1: DATABASE SCHEMA + FEATURE FLAGS + ROUTING

**Goal:** Implement Platform Spec v1.0 database foundation + feature flag infrastructure  
**Duration:** 3-4 dagen  
**Scope:** Database only, NO business logic changes yet

---

## PRE-FLIGHT CHECKS ✓

Before you start, verify:
- [ ] You are in `/home/exedev/wonderz-agentics` directory
- [ ] Git status is clean: `git status`
- [ ] Backend is running: `systemctl status wonderz-backend`
- [ ] You have database access: `psql $DATABASE_URL -c "SELECT 1"`

---

## PHASE 1: DATABASE MIGRATION (Task 1.1)

### What you do:
Create migration file that implements Platform Spec v1.0 complete schema.

### File to create: `app/migrations/068_platform_spec_v1_schema.sql`

**CRITICAL REQUIREMENTS:**
- All table names EXACTLY as specified
- All constraints must be present
- Backfill existing jobs → tasks
- Include verification queries at end
- IDEMPOTENT: can run multiple times safely

**Content:**
```sql
-- ============================================================================
-- PLATFORM SPEC V1.0 - COMPLETE DATABASE SCHEMA
-- Implements: Workers/Talents architecture, Lessons lifecycle, Evidence-based
-- Author: Wonderz Platform Team
-- Date: 2026-03-13
-- Migration: 068
-- ============================================================================

-- ============================================================================
-- 1. TASKS TABLE (Platform Spec sectie 9.1)
-- Core replacement for job-centric approach
-- ============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES jobs(job_id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    agent_role TEXT NOT NULL CHECK (agent_role IN ('worker', 'talent')),
    task_type TEXT NOT NULL,
    status TEXT CHECK (status IN (
        'pending', 'assigned', 'in_progress', 'completed', 
        'failed', 'validation_pending', 'validation_failed'
    )) DEFAULT 'pending',
    input_context JSONB,
    output_data JSONB,
    evidence_refs JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    retry_count INTEGER DEFAULT 0,
    parent_task_id TEXT REFERENCES tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_job ON tasks(job_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id, status);

COMMENT ON TABLE tasks IS 'Platform Spec v1.0 task tracking - replaces job-centric model';

-- ============================================================================
-- 2. VALIDATION DECISIONS (Platform Spec sectie 14.3)
-- Talent validation results storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS validation_decisions (
    decision_id BIGSERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
    validator_agent_id TEXT NOT NULL,
    decision TEXT CHECK (decision IN (
        'approved', 'approved_with_changes', 'rejected'
    )) NOT NULL,
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    confidence_breakdown JSONB,
    validation_checks JSONB,
    blocking_issues TEXT[],
    delta_required JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_validation_task ON validation_decisions(task_id);
CREATE INDEX IF NOT EXISTS idx_validation_decision ON validation_decisions(decision);

COMMENT ON TABLE validation_decisions IS 'Talent agent validation results per task';

-- ============================================================================
-- 3. LESSONS STORE (Platform Spec sectie 6)
-- Only persistent memory in the system
-- ============================================================================
CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    source_task_id TEXT REFERENCES tasks(task_id),
    agent_role TEXT NOT NULL,
    context_tags TEXT[],
    lesson_type TEXT CHECK (lesson_type IN (
        'pattern', 'anti_pattern', 'fix', 'architecture_decision'
    )),
    gevonden TEXT NOT NULL,
    oorzaak TEXT NOT NULL,
    fix_voorstel TEXT NOT NULL,
    volgende_actie TEXT NOT NULL,
    evidence_quality DECIMAL(3,2),
    reusability_score DECIMAL(3,2),
    confidence_score DECIMAL(3,2),
    status TEXT CHECK (status IN (
        'proposed', 'approved', 'rejected', 'deprecated'
    )) DEFAULT 'proposed',
    created_at TIMESTAMPTZ DEFAULT now(),
    approved_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ,
    superseded_by TEXT REFERENCES lessons(lesson_id)
);

CREATE INDEX IF NOT EXISTS idx_lessons_role ON lessons(agent_role, status);
CREATE INDEX IF NOT EXISTS idx_lessons_tags ON lessons USING gin(context_tags);
CREATE INDEX IF NOT EXISTS idx_lessons_score ON lessons(confidence_score DESC) 
    WHERE status = 'approved';

COMMENT ON TABLE lessons IS 'Persistent knowledge store - only memory that survives sessions';

-- ============================================================================
-- 4. NEXUS PIPELINE STATE
-- NEXUS-specific tracking on top of Platform Spec
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus_state (
    job_id TEXT PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
    current_phase INTEGER CHECK (current_phase BETWEEN 1 AND 7),
    phase_status TEXT CHECK (phase_status IN (
        'pending', 'running', 'done', 'failed', 'budget_exceeded'
    )),
    handoff_context JSONB,
    token_budget INTEGER DEFAULT 50000,
    token_used_total INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_nexus_job ON nexus_state(job_id);
CREATE INDEX IF NOT EXISTS idx_nexus_phase ON nexus_state(current_phase, phase_status);

COMMENT ON TABLE nexus_state IS 'NEXUS 7-phase pipeline state tracking';

-- ============================================================================
-- 5. NEXUS PHASE HISTORY
-- Audit trail of all phase transitions
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus_phase_history (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT REFERENCES jobs(job_id) ON DELETE CASCADE,
    phase_number INTEGER,
    phase_name TEXT,
    status TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    tokens_used INTEGER,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_phase_history_job ON nexus_phase_history(job_id, phase_number);
CREATE INDEX IF NOT EXISTS idx_phase_history_status ON nexus_phase_history(status);

COMMENT ON TABLE nexus_phase_history IS 'Audit log of NEXUS phase executions';

-- ============================================================================
-- 6. SOURCE REGISTRY CACHE (Platform Spec sectie 3)
-- Evidence retrieval cache for faster lookups
-- ============================================================================
CREATE TABLE IF NOT EXISTS source_registry_cache (
    cache_id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_path TEXT,
    content_hash TEXT NOT NULL,
    cached_content TEXT,
    cached_metadata JSONB,
    retrieved_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,
    access_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_source_cache_lookup 
    ON source_registry_cache(source_id, artifact_type, content_hash);
CREATE INDEX IF NOT EXISTS idx_source_cache_expiry ON source_registry_cache(expires_at);

COMMENT ON TABLE source_registry_cache IS 'Cache for evidence source retrieval';

-- ============================================================================
-- DATA MIGRATION: Backfill existing jobs → tasks
-- ============================================================================
INSERT INTO tasks (task_id, job_id, agent_id, agent_role, task_type, status, created_at)
SELECT 
    j.id || '-legacy' AS task_id,
    j.id AS job_id,
    'legacy-copywriter' AS agent_id,
    'worker' AS agent_role,
    'content_generation' AS task_type,
    CASE 
        WHEN j.status = 'COMPLETED' THEN 'completed'
        WHEN j.status = 'FAILED' THEN 'failed'
        WHEN j.status = 'RUNNING' THEN 'in_progress'
        WHEN j.status = 'JOB_READY' THEN 'completed'
        ELSE 'pending'
    END AS status,
    j.created_at
FROM jobs j
WHERE NOT EXISTS (
    SELECT 1 FROM tasks t WHERE t.job_id = j.id
)
ON CONFLICT (task_id) DO NOTHING;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update nexus_state.updated_at
CREATE OR REPLACE FUNCTION update_nexus_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS nexus_state_update_timestamp ON nexus_state;
CREATE TRIGGER nexus_state_update_timestamp
BEFORE UPDATE ON nexus_state
FOR EACH ROW
EXECUTE FUNCTION update_nexus_state_timestamp();

-- Prevent lesson deletion if it supersedes other lessons
CREATE OR REPLACE FUNCTION prevent_lesson_deletion()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM lessons 
        WHERE superseded_by = OLD.lesson_id
    ) THEN
        RAISE EXCEPTION 'Cannot delete lesson % - it supersedes other lessons', OLD.lesson_id;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS prevent_lesson_cascade_delete ON lessons;
CREATE TRIGGER prevent_lesson_cascade_delete
BEFORE DELETE ON lessons
FOR EACH ROW
EXECUTE FUNCTION prevent_lesson_deletion();

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

DO $$
DECLARE
    missing_tables TEXT[];
    table_counts TEXT;
BEGIN
    -- Check all tables exist
    SELECT ARRAY_AGG(t) INTO missing_tables
    FROM unnest(ARRAY[
        'tasks', 'validation_decisions', 'lessons',
        'nexus_state', 'nexus_phase_history', 'source_registry_cache'
    ]) AS t
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = t
    );
    
    IF array_length(missing_tables, 1) > 0 THEN
        RAISE EXCEPTION 'MIGRATION FAILED - Missing tables: %', 
            array_to_string(missing_tables, ', ');
    END IF;
    
    -- Report row counts
    SELECT string_agg(
        format('%s: %s rows', table_name, 
            (SELECT COUNT(*) FROM information_schema.tables WHERE table_name = t.table_name)
        ), 
        E'\n'
    ) INTO table_counts
    FROM unnest(ARRAY[
        'tasks', 'validation_decisions', 'lessons',
        'nexus_state', 'nexus_phase_history', 'source_registry_cache'
    ]) AS table_name;
    
    RAISE NOTICE E'✓ MIGRATION 068 SUCCESS\n\nTables created:\n%', table_counts;
    
    -- Check backfill
    RAISE NOTICE 'Tasks created from jobs: %', (SELECT COUNT(*) FROM tasks WHERE task_id LIKE '%-legacy');
END $$;

-- Final verification query
SELECT 
    t.table_name,
    (SELECT COUNT(*) FROM information_schema.columns 
     WHERE table_schema = 'public' AND table_name = t.table_name) as columns,
    obj_description(
        (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass
    ) as description
FROM information_schema.tables t
WHERE t.table_schema = 'public' 
  AND t.table_name IN (
    'tasks', 'validation_decisions', 'lessons',
    'nexus_state', 'nexus_phase_history', 'source_registry_cache'
  )
ORDER BY t.table_name;
```

**Acceptance criteria:**
- [ ] Migration file created at exact path
- [ ] All 6 tables defined with constraints
- [ ] Triggers created successfully
- [ ] Backfill query included
- [ ] Verification queries at end

---

## PHASE 2: CONFIG INFRASTRUCTURE (Task 1.2)

### What you do:
Create centralized configuration with feature flags.

### File to create: `app/config.py`

**Content:**
```python
"""
Application Configuration - Platform Spec v1.0
Centralized feature flags and settings
"""
import os
from typing import Literal
import logging

logger = logging.getLogger(__name__)

class PlatformConfig:
    """
    Platform Spec v1.0 configuration
    Controls NEXUS rollout and feature activation
    """
    
    # ========================================================================
    # FEATURE FLAGS
    # ========================================================================
    
    ENABLE_NEXUS: bool = os.getenv("ENABLE_NEXUS", "false").lower() == "true"
    ENABLE_TASK_ENGINE: bool = os.getenv("ENABLE_TASK_ENGINE", "false").lower() == "true"
    ENABLE_LESSONS_STORE: bool = os.getenv("ENABLE_LESSONS_STORE", "false").lower() == "true"
    
    # Gradual rollout percentage (0-100)
    NEXUS_ROLLOUT_PCT: int = int(os.getenv("NEXUS_ROLLOUT_PCT", "0"))
    
    # Pipeline selection mode
    PIPELINE_MODE: Literal["legacy", "nexus", "auto"] = os.getenv(
        "PIPELINE_MODE", "auto"
    )
    
    # ========================================================================
    # TOKEN BUDGETS (Platform Spec sectie 3.4)
    # ========================================================================
    
    DEFAULT_TOKEN_BUDGET: int = int(os.getenv("DEFAULT_TOKEN_BUDGET", "50000"))
    HARD_STOP_THRESHOLD: float = 1.0  # 100% of budget
    WARNING_THRESHOLD: float = 0.8     # 80% of budget
    
    # ========================================================================
    # CONFIDENCE THRESHOLDS (Platform Spec sectie 5)
    # ========================================================================
    
    LESSON_MIN_CONFIDENCE: float = 0.70
    HIGH_CONFIDENCE_THRESHOLD: float = 0.90
    
    # ========================================================================
    # DECISION LOGIC
    # ========================================================================
    
    @classmethod
    def should_use_nexus(cls, job_id: str) -> bool:
        """
        Determine if a job should use NEXUS pipeline
        
        Logic:
        - legacy mode: always False (old pipeline only)
        - nexus mode: always True (NEXUS only)
        - auto mode: consistent hashing based on NEXUS_ROLLOUT_PCT
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            True if job should use NEXUS, False for legacy pipeline
        """
        if cls.PIPELINE_MODE == "legacy":
            logger.debug(f"Job {job_id}: forced legacy (PIPELINE_MODE=legacy)")
            return False
            
        if cls.PIPELINE_MODE == "nexus":
            logger.debug(f"Job {job_id}: forced NEXUS (PIPELINE_MODE=nexus)")
            return True
        
        # Auto mode: consistent hashing for gradual rollout
        import hashlib
        hash_int = int(hashlib.md5(job_id.encode()).hexdigest(), 16)
        use_nexus = (hash_int % 100) < cls.NEXUS_ROLLOUT_PCT
        
        logger.debug(
            f"Job {job_id}: {'NEXUS' if use_nexus else 'legacy'} "
            f"(hash bucket {hash_int % 100}, rollout {cls.NEXUS_ROLLOUT_PCT}%)"
        )
        
        return use_nexus
    
    @classmethod
    def get_config_summary(cls) -> dict:
        """Return current configuration for debugging"""
        return {
            "enable_nexus": cls.ENABLE_NEXUS,
            "enable_task_engine": cls.ENABLE_TASK_ENGINE,
            "enable_lessons_store": cls.ENABLE_LESSONS_STORE,
            "nexus_rollout_pct": cls.NEXUS_ROLLOUT_PCT,
            "pipeline_mode": cls.PIPELINE_MODE,
            "default_token_budget": cls.DEFAULT_TOKEN_BUDGET,
            "lesson_min_confidence": cls.LESSON_MIN_CONFIDENCE
        }

# Global config instance
config = PlatformConfig()

# Log config on import
logger.info(f"Platform config loaded: {config.get_config_summary()}")
```

**Acceptance criteria:**
- [ ] File created at `app/config.py`
- [ ] All feature flags defined
- [ ] `should_use_nexus()` logic correct
- [ ] Consistent hashing implementation
- [ ] Config summary method present

---

## PHASE 3: ROUTING LAYER UPDATE (Task 1.3)

### What you do:
Update job start endpoint to route based on config.

### File to modify: `app/routes/jobs.py`

**FIND this block:**
```python
@router.post("/{job_id}/start")
async def start_job(job_id: str, pool=Depends(get_pool)):
    # Current implementation (varies)
```

**REPLACE with:**
```python
from app.config import config
from app.orchestration.nexus_pipeline import NEXUSPipeline
from app.services.job_pipeline import run_job_inline

@router.post("/{job_id}/start")
async def start_job(job_id: str, pool=Depends(get_pool)):
    """
    Start job execution - routes to NEXUS or legacy pipeline
    
    Routing logic in app.config.PlatformConfig.should_use_nexus()
    """
    use_nexus = config.should_use_nexus(job_id)
    
    logger.info(
        f"Starting job {job_id} via {'NEXUS' if use_nexus else 'LEGACY'} pipeline "
        f"(mode: {config.PIPELINE_MODE}, rollout: {config.NEXUS_ROLLOUT_PCT}%)"
    )
    
    if use_nexus:
        try:
            # NEXUS pipeline
            pipeline = NEXUSPipeline(job_id, pool)
            await pipeline.run()
            
            return {
                "status": "started",
                "pipeline": "nexus",
                "job_id": job_id,
                "message": "Job started via NEXUS 7-phase pipeline"
            }
            
        except Exception as e:
            logger.error(f"NEXUS pipeline failed for job {job_id}: {e}", exc_info=True)
            
            # Fallback to legacy only in auto mode
            if config.PIPELINE_MODE == "auto":
                logger.warning(f"Falling back to legacy pipeline for job {job_id}")
                await run_job_inline(job_id, pool)
                
                return {
                    "status": "started",
                    "pipeline": "legacy_fallback",
                    "job_id": job_id,
                    "message": "NEXUS failed, fell back to legacy pipeline",
                    "error": str(e)
                }
            else:
                # In 'nexus' mode, don't fallback - let it fail
                raise
    else:
        # Legacy pipeline
        await run_job_inline(job_id, pool)
        
        return {
            "status": "started",
            "pipeline": "legacy",
            "job_id": job_id,
            "message": "Job started via legacy pipeline"
        }
```

**Acceptance criteria:**
- [ ] Import statements added
- [ ] Routing logic uses `config.should_use_nexus()`
- [ ] Fallback only in auto mode
- [ ] Response includes pipeline info
- [ ] Logging shows which pipeline used

---

## PHASE 4: INTEGRATION TEST (Task 1.4)

### What you do:
Create integration test to verify database schema + routing.

### File to create: `tests/integration/test_week1_infrastructure.py`

**Content:**
```python
"""
Week 1 Integration Tests
Verify database schema and routing infrastructure
"""
import pytest
from app.config import config

@pytest.mark.asyncio
async def test_database_tables_exist(db_pool):
    """Verify all Platform Spec v1.0 tables created"""
    expected_tables = [
        'tasks',
        'validation_decisions',
        'lessons',
        'nexus_state',
        'nexus_phase_history',
        'source_registry_cache'
    ]
    
    async with db_pool.acquire() as conn:
        for table_name in expected_tables:
            result = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_name = $1
            """, table_name)
            
            assert result == 1, f"Table {table_name} does not exist"

@pytest.mark.asyncio
async def test_tasks_backfill(db_pool):
    """Verify jobs were backfilled into tasks table"""
    async with db_pool.acquire() as conn:
        # Count jobs
        job_count = await conn.fetchval("SELECT COUNT(*) FROM jobs")
        
        # Count tasks
        task_count = await conn.fetchval("SELECT COUNT(*) FROM tasks")
        
        # Should have at least as many tasks as jobs
        assert task_count >= job_count, \
            f"Tasks ({task_count}) < Jobs ({job_count}) - backfill failed"

@pytest.mark.asyncio
async def test_config_routing_logic():
    """Verify routing decision logic"""
    import os
    
    # Test legacy mode
    os.environ['PIPELINE_MODE'] = 'legacy'
    assert config.should_use_nexus('test-job-1') == False
    
    # Test nexus mode
    os.environ['PIPELINE_MODE'] = 'nexus'
    assert config.should_use_nexus('test-job-2') == True
    
    # Test auto mode with 0% rollout
    os.environ['PIPELINE_MODE'] = 'auto'
    os.environ['NEXUS_ROLLOUT_PCT'] = '0'
    assert config.should_use_nexus('test-job-3') == False
    
    # Test auto mode with 100% rollout
    os.environ['NEXUS_ROLLOUT_PCT'] = '100'
    assert config.should_use_nexus('test-job-4') == True
    
    # Reset
    os.environ['PIPELINE_MODE'] = 'auto'
    os.environ['NEXUS_ROLLOUT_PCT'] = '0'

@pytest.mark.asyncio
async def test_nexus_state_persistence(db_pool):
    """Verify NEXUS state can be saved and loaded"""
    import json
    from uuid import uuid4
    
    test_job_id = str(uuid4())
    test_context = {
        'strategic_brief': 'Test brief',
        'execution_plan': ['step1', 'step2']
    }
    
    async with db_pool.acquire() as conn:
        # Save state
        await conn.execute("""
            INSERT INTO nexus_state (job_id, current_phase, phase_status, handoff_context)
            VALUES ($1, $2, $3, $4)
        """, test_job_id, 3, 'running', json.dumps(test_context))
        
        # Load state
        row = await conn.fetchrow("""
            SELECT * FROM nexus_state WHERE job_id = $1
        """, test_job_id)
        
        assert row is not None
        assert row['current_phase'] == 3
        assert row['phase_status'] == 'running'
        
        loaded_context = json.loads(row['handoff_context'])
        assert loaded_context['strategic_brief'] == 'Test brief'
        
        # Cleanup
        await conn.execute("DELETE FROM nexus_state WHERE job_id = $1", test_job_id)
```

**Acceptance criteria:**
- [ ] Test file created
- [ ] All 4 tests defined
- [ ] Tests use pytest.mark.asyncio
- [ ] Database assertions correct
- [ ] Config tests cover all modes

---

## WHAT YOU DO NOT DO ❌

**DO NOT:**
- Modify business logic in agents (Week 2)
- Change system prompts (Week 2)
- Implement TaskEngine (Week 2)
- Remove legacy code (Week 4)
- Deploy to production (Shelley does this)

**ONLY DO:**
- Database migration file
- Config infrastructure
- Routing layer
- Integration tests

---

## COMMIT STRATEGY

**After EACH phase:**
```bash
git add app/migrations/068_platform_spec_v1_schema.sql
git commit -m "feat(db): Platform Spec v1.0 schema - tasks, lessons, nexus_state"

git add app/config.py
git commit -m "feat(config): Add feature flags for NEXUS rollout"

git add app/routes/jobs.py
git commit -m "feat(routing): Add NEXUS/legacy pipeline routing logic"

git add tests/integration/test_week1_infrastructure.py
git commit -m "test: Week 1 infrastructure integration tests"
```

**Final push:**
```bash
git push origin main
```

---

## VERIFICATION CHECKLIST

After you finish, verify:

- [ ] `app/migrations/068_platform_spec_v1_schema.sql` exists
- [ ] `app/config.py` exists with all flags
- [ ] `app/routes/jobs.py` has routing logic
- [ ] `tests/integration/test_week1_infrastructure.py` exists
- [ ] All files committed
- [ ] Git pushed to main
- [ ] NO syntax errors: `python -m py_compile app/config.py`
- [ ] Imports work: `python -c "from app.config import config; print(config.get_config_summary())"`

**Tell Shelley:**
"Week 1 code klaar. Shelley moet nu:
1. Run migration: `psql $DATABASE_URL -f app/migrations/068_platform_spec_v1_schema.sql`
2. Deploy: `git pull && sudo systemctl restart wonderz-backend`
3. Verify: `pytest tests/integration/test_week1_infrastructure.py -v`"

---

## DONE CRITERIA ✓

Week 1 is done when:
- ✅ All 4 files created
- ✅ All tests pass locally
- ✅ Git pushed
- ✅ Shelley notified for deployment

**Estimated time:** 3-4 hours if you work fase-by-fase

---

END OF WEEK 1 PROMPT

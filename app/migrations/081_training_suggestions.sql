-- Migration 081: training_suggestions for HR resource discovery
-- Doel: pending/approved/rejected trainingsuggesties per development point opslaan
-- Let op: development_points kan in sommige omgevingen id (BIGINT/UUID) of alleen point_id (TEXT) hebben.
-- Deze migratie kiest daarom automatisch de juiste FK-variant.

DO $$
DECLARE
    has_dp_id BOOLEAN;
    has_dp_point_id BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'development_points'
          AND column_name = 'id'
    ) INTO has_dp_id;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'development_points'
          AND column_name = 'point_id'
    ) INTO has_dp_point_id;

    IF has_dp_id THEN
        -- Optie A: development_points.id bestaat
        EXECUTE $sql$
            CREATE TABLE IF NOT EXISTS training_suggestions (
                id BIGSERIAL PRIMARY KEY,
                development_point_id BIGINT REFERENCES development_points(id) ON DELETE CASCADE,
                agent_id TEXT REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
                url TEXT NOT NULL,
                title TEXT,
                rationale TEXT,
                discovered_by TEXT DEFAULT 'hr-manager',
                status TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected')),
                approved_by TEXT,
                approval_notes TEXT,
                discovered_at TIMESTAMPTZ DEFAULT now(),
                reviewed_at TIMESTAMPTZ
            )
        $sql$;
    ELSIF has_dp_point_id THEN
        -- Optie B: alleen development_points.point_id bestaat
        EXECUTE $sql$
            CREATE TABLE IF NOT EXISTS training_suggestions (
                id BIGSERIAL PRIMARY KEY,
                development_point_ref TEXT REFERENCES development_points(point_id) ON DELETE CASCADE,
                agent_id TEXT REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
                url TEXT NOT NULL,
                title TEXT,
                rationale TEXT,
                discovered_by TEXT DEFAULT 'hr-manager',
                status TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected')),
                approved_by TEXT,
                approval_notes TEXT,
                discovered_at TIMESTAMPTZ DEFAULT now(),
                reviewed_at TIMESTAMPTZ
            )
        $sql$;
    ELSE
        RAISE EXCEPTION 'development_points mist zowel id als point_id; FK kan niet worden bepaald';
    END IF;
END $$;

-- Indexen
CREATE INDEX IF NOT EXISTS idx_training_suggestions_agent
    ON training_suggestions(agent_id);

CREATE INDEX IF NOT EXISTS idx_training_suggestions_status
    ON training_suggestions(status);

-- Maak index op de juiste development point referentie-kolom als die bestaat
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'training_suggestions'
          AND column_name = 'development_point_id'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_training_suggestions_dp_id ON training_suggestions(development_point_id)';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'training_suggestions'
          AND column_name = 'development_point_ref'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_training_suggestions_dp_ref ON training_suggestions(development_point_ref)';
    END IF;
END $$;

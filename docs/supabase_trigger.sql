-- Bestand: docs/supabase_trigger.sql
-- Uitvoeren via: Supabase Dashboard → SQL Editor (niet via app-DB-connectie)

-- 1. Sync functie
CREATE OR REPLACE FUNCTION sync_user_to_app()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.users (id, email)
        VALUES (NEW.id, NEW.email)
        ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;
    ELSIF TG_OP = 'DELETE' THEN
        DELETE FROM public.users WHERE id = OLD.id;
    END IF;
    RETURN NEW;
END;
$$;

-- 2. Trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR DELETE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION sync_user_to_app();

-- 3. Backfill (eenmalig)
INSERT INTO public.users (id, email)
SELECT id, email FROM auth.users
ON CONFLICT (id) DO NOTHING;

-- 4. Verificatie
SELECT
    (SELECT COUNT(*) FROM auth.users) AS auth_count,
    (SELECT COUNT(*) FROM public.users) AS app_count;
-- Beide moeten gelijk zijn

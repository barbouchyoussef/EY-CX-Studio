BEGIN;

DO $$
DECLARE
    improve_axis_id INTEGER;
    maintain_axis_id INTEGER;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'axes'
    ) THEN
        SELECT id
        INTO improve_axis_id
        FROM axes
        WHERE lower(code) = 'improve' OR lower(name) = 'improve'
        ORDER BY id
        LIMIT 1;

        SELECT id
        INTO maintain_axis_id
        FROM axes
        WHERE lower(code) = 'maintain' OR lower(name) = 'maintain'
        ORDER BY id
        LIMIT 1;

        IF maintain_axis_id IS NOT NULL THEN
            IF improve_axis_id IS NULL THEN
                UPDATE axes
                SET code = 'improve',
                    name = 'Improve'
                WHERE id = maintain_axis_id;

                improve_axis_id := maintain_axis_id;
            ELSIF improve_axis_id <> maintain_axis_id THEN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'capabilities' AND column_name = 'axis_id'
                ) THEN
                    UPDATE capabilities
                    SET axis_id = improve_axis_id
                    WHERE axis_id = maintain_axis_id;
                END IF;

                DELETE FROM axes
                WHERE id = maintain_axis_id;
            END IF;
        END IF;

        IF improve_axis_id IS NOT NULL THEN
            UPDATE axes
            SET code = 'improve',
                name = 'Improve'
            WHERE id = improve_axis_id;
        END IF;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'capabilities' AND column_name = 'code'
    ) THEN
        UPDATE capabilities
        SET code = regexp_replace(code, '^maintain\.', 'improve.')
        WHERE code LIKE 'maintain.%';
    END IF;
END $$;

COMMIT;

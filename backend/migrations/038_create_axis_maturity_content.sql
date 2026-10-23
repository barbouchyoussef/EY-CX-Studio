BEGIN;

CREATE TABLE IF NOT EXISTS axis_maturity_content (
    id SERIAL PRIMARY KEY,
    axis_id INTEGER NOT NULL REFERENCES axes(id) ON DELETE CASCADE,
    maturity_level_id INTEGER NOT NULL REFERENCES maturity_levels(id) ON DELETE CASCADE,
    axis_description TEXT,
    axis_panel_copy TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT axis_maturity_content_axis_level_key UNIQUE (axis_id, maturity_level_id)
);

CREATE INDEX IF NOT EXISTS idx_axis_maturity_content_axis_id ON axis_maturity_content(axis_id);
CREATE INDEX IF NOT EXISTS idx_axis_maturity_content_maturity_level_id ON axis_maturity_content(maturity_level_id);

COMMIT;

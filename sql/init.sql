-- Запускается автоматически при первом старте контейнера postgres
-- Если БД уже существует — выполни вручную: psql -d prices_db -f sql/init.sql

CREATE TABLE IF NOT EXISTS model_metrics (
    id              SERIAL PRIMARY KEY,
    trained_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_version   TEXT NOT NULL,          -- напр. "2026-05-15_08-00"
    mae             FLOAT NOT NULL,
    rmse            FLOAT NOT NULL,
    mape            FLOAT NOT NULL,
    r2              FLOAT NOT NULL,
    train_size      INTEGER NOT NULL,
    test_size       INTEGER NOT NULL,
    iterations_used INTEGER,                -- best iteration CatBoost
    degraded        BOOLEAN DEFAULT FALSE,  -- TRUE если MAPE > порога
    notes           TEXT                    -- любые комментарии
);

CREATE INDEX IF NOT EXISTS idx_model_metrics_trained_at
    ON model_metrics (trained_at DESC);

-- Представление для Streamlit / API: последние 30 запусков
CREATE OR REPLACE VIEW v_model_metrics_recent AS
SELECT *
FROM model_metrics
ORDER BY trained_at DESC
LIMIT 30;
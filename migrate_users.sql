-- 建立 users 表（若不存在）
-- 在 Supabase SQL Editor 執行一次即可
-- 容器啟動時 init_db() 也會自動執行，此檔為備用

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 確認 users 表建立完成
SELECT COUNT(*) AS user_count FROM users;

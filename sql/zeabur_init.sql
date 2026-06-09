--
-- RiiqiMaker 初始化 SQL（Zeabur PostgreSQL）
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);

-- 清空既有表（如果存在）
DROP TABLE IF EXISTS public.users CASCADE;
DROP TABLE IF EXISTS public.prompt_templates CASCADE;
DROP TABLE IF EXISTS public.cup_sizes CASCADE;
DROP TABLE IF EXISTS public.ai_settings CASCADE;

-- ai_settings
CREATE TABLE public.ai_settings (
    key text NOT NULL PRIMARY KEY,
    value text DEFAULT ''::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);

-- cup_sizes
CREATE TABLE public.cup_sizes (
    id integer NOT NULL,
    cup_name text NOT NULL,
    cup_series text NOT NULL,
    outer_r real NOT NULL,
    inner_r real NOT NULL,
    theta_deg real NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    note text,
    edited_by text,
    created_at timestamp with time zone DEFAULT now()
);

CREATE SEQUENCE public.cup_sizes_id_seq AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.cup_sizes_id_seq OWNED BY public.cup_sizes.id;
ALTER TABLE ONLY public.cup_sizes ALTER COLUMN id SET DEFAULT nextval('public.cup_sizes_id_seq'::regclass);
ALTER TABLE ONLY public.cup_sizes ADD CONSTRAINT cup_sizes_pkey PRIMARY KEY (id);

-- prompt_templates
CREATE TABLE public.prompt_templates (
    id integer NOT NULL,
    name text NOT NULL,
    body text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);

CREATE SEQUENCE public.prompt_templates_id_seq AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.prompt_templates_id_seq OWNED BY public.prompt_templates.id;
ALTER TABLE ONLY public.prompt_templates ALTER COLUMN id SET DEFAULT nextval('public.prompt_templates_id_seq'::regclass);
ALTER TABLE ONLY public.prompt_templates ADD CONSTRAINT prompt_templates_pkey PRIMARY KEY (id);

-- users
CREATE TABLE public.users (
    id integer NOT NULL,
    username text NOT NULL,
    password_hash text NOT NULL,
    role text DEFAULT 'user'::text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);

CREATE SEQUENCE public.users_id_seq AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;
ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);
ALTER TABLE ONLY public.users ADD CONSTRAINT users_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.users ADD CONSTRAINT users_username_key UNIQUE (username);

-- ==================== DATA ====================

-- ai_settings（API keys 留空，由環境變數或後台設定）
INSERT INTO public.ai_settings VALUES ('gemini_api_key', '', now());
INSERT INTO public.ai_settings VALUES ('ai_model', 'imagen-3.0-generate-002', now());
INSERT INTO public.ai_settings VALUES ('hf_api_key', '', now());
INSERT INTO public.ai_settings VALUES ('site_title', 'RiiqiMaker', now());
INSERT INTO public.ai_settings VALUES ('ui_theme', 'warm', now());
INSERT INTO public.ai_settings VALUES ('ui_font_family', 'Nunito', now());
INSERT INTO public.ai_settings VALUES ('ui_font_color', '', now());
INSERT INTO public.ai_settings VALUES ('ui_font_size', '16', now());
INSERT INTO public.ai_settings VALUES ('convert_desc', '', now());

-- cup_sizes（修正中文亂碼）
INSERT INTO public.cup_sizes VALUES (1, '8oz_冷熱杯', 'cold_hot', 337.28, 248.29, 41.17, true, NULL, NULL, now());
INSERT INTO public.cup_sizes VALUES (2, '12oz_冷熱杯', 'cold_hot', 381.41, 273.41, 40.96, true, NULL, NULL, now());
INSERT INTO public.cup_sizes VALUES (3, '16oz_冷熱杯', 'cold_hot', 439.65, 307.24, 35.55, true, '原35.55', NULL, now());
INSERT INTO public.cup_sizes VALUES (4, '20oz_冷熱杯', 'cold_hot', 516.95, 356.9, 30.12, true, NULL, NULL, now());
INSERT INTO public.cup_sizes VALUES (5, '22oz_冷熱杯', 'cold_hot', 618.61, 452.47, 25.11, true, NULL, NULL, now());
INSERT INTO public.cup_sizes VALUES (6, '24oz_冷熱杯', 'cold_hot', 530.29, 363.22, 31.12, true, NULL, NULL, now());
INSERT INTO public.cup_sizes VALUES (7, '8oz_雙層杯', 'double_wall', 371.42, 289.44, 38.26, true, NULL, NULL, now());
INSERT INTO public.cup_sizes VALUES (8, '12oz_雙層杯', 'double_wall', 411, 310.68, 38.99, true, NULL, NULL, now());
INSERT INTO public.cup_sizes VALUES (9, '16oz_雙層杯', 'double_wall', 479.33, 356.26, 33.57, true, NULL, NULL, now());
INSERT INTO public.cup_sizes VALUES (10, '20oz_雙層杯', 'double_wall', 569.89, 418.87, 28.04, true, NULL, NULL, now());

-- prompt_templates
INSERT INTO public.prompt_templates VALUES (1, '預設範本', '{theme}. {style} style. Main text: "{text}".
Flat lay surface pattern design, top-down view. Illustrated repeating pattern.
Flat 2D vector illustration, pure white background, vibrant colors, seamless left-right edges.
No 3D, no cup shape, no border frame, no shadows, no perspective.', true, 1, now());

-- sequences
SELECT pg_catalog.setval('public.cup_sizes_id_seq', 10, true);
SELECT pg_catalog.setval('public.prompt_templates_id_seq', 1, true);
SELECT pg_catalog.setval('public.users_id_seq', 1, true);

-- 注意：users 表由 app.py init_db() 自動建立 admin 帳號（使用 ADMIN_PASSWORD 環境變數）

import os
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get('DATABASE_URL')

DEFAULT_PROMPT = """{theme}. {style} style. Main text: "{text}".
Flat lay surface pattern design, top-down view. Illustrated repeating pattern.
Flat 2D vector illustration, pure white background, vibrant colors, seamless left-right edges.
No 3D, no cup shape, no border frame, no shadows, no perspective."""

CUP_DATA = [
    ('8oz_冷熱杯',  'cold_hot',    337.28, 248.29, 41.17),
    ('12oz_冷熱杯', 'cold_hot',    381.41, 273.41, 40.96),
    ('16oz_冷熱杯', 'cold_hot',    439.65, 307.24, 35.55),
    ('20oz_冷熱杯', 'cold_hot',    516.95, 356.90, 30.12),
    ('22oz_冷熱杯', 'cold_hot',    618.61, 452.47, 25.11),
    ('24oz_冷熱杯', 'cold_hot',    530.29, 363.22, 31.12),
    ('8oz_雙層杯',  'double_wall', 371.42, 289.44, 38.26),
    ('12oz_雙層杯', 'double_wall', 411.00, 310.68, 38.99),
    ('16oz_雙層杯', 'double_wall', 479.33, 356.26, 33.57),
    ('20oz_雙層杯', 'double_wall', 569.89, 418.87, 28.04),
]

# ── PostgreSQL (生產環境) ──────────────────────────────────

def _pg_conn():
    import psycopg2
    import psycopg2.extras
    return psycopg2.connect(DATABASE_URL)


def _init_pg():
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cup_sizes (
                    id         SERIAL PRIMARY KEY,
                    cup_name   TEXT    NOT NULL,
                    cup_series TEXT    NOT NULL,
                    outer_r    REAL    NOT NULL,
                    inner_r    REAL    NOT NULL,
                    theta_deg  REAL    NOT NULL,
                    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
                    note       TEXT,
                    edited_by  TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    id         SERIAL PRIMARY KEY,
                    name       TEXT    NOT NULL,
                    body       TEXT    NOT NULL,
                    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
                    version    INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute('SELECT COUNT(*) FROM cup_sizes')
            if cur.fetchone()[0] == 0:
                cur.executemany(
                    'INSERT INTO cup_sizes (cup_name, cup_series, outer_r, inner_r, theta_deg) VALUES (%s,%s,%s,%s,%s)',
                    CUP_DATA
                )
            cur.execute("ALTER TABLE cup_sizes ADD COLUMN IF NOT EXISTS note TEXT;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_settings (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL DEFAULT '',
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute('SELECT COUNT(*) FROM prompt_templates')
            if cur.fetchone()[0] == 0:
                cur.execute(
                    'INSERT INTO prompt_templates (name, body) VALUES (%s,%s)',
                    ('預設模板', DEFAULT_PROMPT)
                )
            for k, v in [
                ('gemini_api_key', ''), ('ai_model', 'imagen-3.0-generate-002'), ('hf_api_key', ''),
                ('site_title', 'RiiqiMaker'),
                ('ui_theme', 'warm'), ('ui_font_family', 'Nunito'),
                ('ui_font_color', ''), ('ui_font_size', '16'),
            ]:
                cur.execute(
                    'INSERT INTO ai_settings (key, value) VALUES (%s,%s) ON CONFLICT (key) DO NOTHING',
                    (k, v)
                )
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    username      TEXT    NOT NULL UNIQUE,
                    password_hash TEXT    NOT NULL,
                    role          TEXT    NOT NULL DEFAULT 'user',
                    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at    TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS banners (
                    id         SERIAL PRIMARY KEY,
                    slot       INTEGER NOT NULL UNIQUE,
                    image_data BYTEA   NOT NULL,
                    mime_type  TEXT    NOT NULL DEFAULT 'image/jpeg',
                    size_kb    INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute('SELECT COUNT(*) FROM users')
            if cur.fetchone()[0] == 0:
                admin_pw = os.environ.get('ADMIN_PASSWORD', 'admin1234')
                cur.execute(
                    'INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s)',
                    ('admin', generate_password_hash(admin_pw), 'admin')
                )
            else:
                # 每次啟動同步 admin 密碼（確保與環境變數一致）
                admin_pw = os.environ.get('ADMIN_PASSWORD')
                if admin_pw:
                    cur.execute(
                        'UPDATE users SET password_hash = %s WHERE username = %s',
                        (generate_password_hash(admin_pw), 'admin')
                    )
        conn.commit()


def _get_cups_pg():
    with _pg_conn() as conn:
        with conn.cursor(cursor_factory=__import__('psycopg2.extras', fromlist=['RealDictCursor']).RealDictCursor) as cur:
            cur.execute(
                'SELECT id, cup_name, cup_series, outer_r, inner_r, theta_deg, note FROM cup_sizes WHERE is_active=TRUE ORDER BY cup_series, id'
            )
            return [dict(r) for r in cur.fetchall()]


def _get_cup_pg(cup_id):
    import psycopg2.extras
    with _pg_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                'SELECT id, cup_name, cup_series, outer_r, inner_r, theta_deg, note FROM cup_sizes WHERE id=%s AND is_active=TRUE',
                (cup_id,)
            )
            row = cur.fetchone()
    return dict(row) if row else None


# ── SQLite (本機開發) ─────────────────────────────────────

def _sqlite_path():
    import sqlite3
    path = os.path.join(os.path.dirname(__file__), 'instance', 'app.db')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _sq_conn():
    import sqlite3
    c = sqlite3.connect(_sqlite_path())
    c.row_factory = sqlite3.Row
    return c


def _init_sq():
    with _sq_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS cup_sizes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                cup_name   TEXT    NOT NULL,
                cup_series TEXT    NOT NULL,
                outer_r    REAL    NOT NULL,
                inner_r    REAL    NOT NULL,
                theta_deg  REAL    NOT NULL,
                is_active  INTEGER NOT NULL DEFAULT 1,
                note       TEXT,
                edited_by  TEXT,
                created_at TEXT    DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS prompt_templates (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                body       TEXT    NOT NULL,
                is_active  INTEGER NOT NULL DEFAULT 1,
                version    INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    DEFAULT (datetime('now','localtime'))
            );
        """)
        row = c.execute('SELECT COUNT(*) FROM cup_sizes').fetchone()[0]
        if row == 0:
            c.executemany(
                'INSERT INTO cup_sizes (cup_name, cup_series, outer_r, inner_r, theta_deg) VALUES (?,?,?,?,?)',
                CUP_DATA
            )
        c.execute("""
            CREATE TABLE IF NOT EXISTS ai_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL DEFAULT '',
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        row = c.execute('SELECT COUNT(*) FROM prompt_templates').fetchone()[0]
        if row == 0:
            c.execute(
                'INSERT INTO prompt_templates (name, body) VALUES (?,?)',
                ('預設模板', DEFAULT_PROMPT)
            )
        for k, v in [
            ('gemini_api_key', ''), ('ai_model', 'imagen-3.0-generate-002'), ('hf_api_key', ''),
            ('convert_desc', '系統將自動依照所選杯型的 R、r、θ 參數，使用極座標數學轉換，把矩形圖彎成扇形。'),
            ('ui_theme', 'warm'), ('ui_font_family', 'Nunito'),
            ('ui_font_color', ''), ('ui_font_size', '16'),
        ]:
            c.execute('INSERT OR IGNORE INTO ai_settings (key, value) VALUES (?,?)', (k, v))
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'user',
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT    DEFAULT (datetime('now','localtime'))
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS banners (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                slot       INTEGER NOT NULL UNIQUE,
                image_data BLOB    NOT NULL,
                mime_type  TEXT    NOT NULL DEFAULT 'image/jpeg',
                size_kb    INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT    DEFAULT (datetime('now','localtime'))
            );
        """)
        if c.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
            admin_pw = os.environ.get('ADMIN_PASSWORD', 'admin1234')
            c.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (?,?,?)',
                ('admin', generate_password_hash(admin_pw), 'admin')
            )


def _get_cups_sq():
    with _sq_conn() as c:
        rows = c.execute(
            'SELECT id, cup_name, cup_series, outer_r, inner_r, theta_deg, note FROM cup_sizes WHERE is_active=1 ORDER BY cup_series, id'
        ).fetchall()
    return [dict(r) for r in rows]


def _get_cup_sq(cup_id):
    with _sq_conn() as c:
        row = c.execute(
            'SELECT id, cup_name, cup_series, outer_r, inner_r, theta_deg, note FROM cup_sizes WHERE id=? AND is_active=1',
            (cup_id,)
        ).fetchone()
    return dict(row) if row else None


# ── 公開介面 ──────────────────────────────────────────────

def init_db():
    if DATABASE_URL:
        _init_pg()
    else:
        _init_sq()


def get_cups():
    return _get_cups_pg() if DATABASE_URL else _get_cups_sq()


def get_cup_by_id(cup_id):
    return _get_cup_pg(cup_id) if DATABASE_URL else _get_cup_sq(cup_id)


def get_ai_setting(key):
    if DATABASE_URL:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT value FROM ai_settings WHERE key=%s', (key,))
                row = cur.fetchone()
    else:
        with _sq_conn() as c:
            row = c.execute('SELECT value FROM ai_settings WHERE key=?', (key,)).fetchone()
    return row[0] if row else ''


def set_ai_setting(key, value):
    if DATABASE_URL:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO ai_settings (key, value) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET value=%s, updated_at=NOW()',
                    (key, value, value)
                )
            conn.commit()
    else:
        with _sq_conn() as c:
            c.execute(
                'INSERT INTO ai_settings (key, value) VALUES (?,?) ON CONFLICT (key) DO UPDATE SET value=?, updated_at=datetime(\'now\',\'localtime\')',
                (key, value, value)
            )


def update_cup(cup_id, outer_r, inner_r, theta_deg, note=''):
    if DATABASE_URL:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'UPDATE cup_sizes SET outer_r=%s, inner_r=%s, theta_deg=%s, note=%s WHERE id=%s',
                    (outer_r, inner_r, theta_deg, note, cup_id)
                )
            conn.commit()
    else:
        with _sq_conn() as c:
            c.execute(
                'UPDATE cup_sizes SET outer_r=?, inner_r=?, theta_deg=?, note=? WHERE id=?',
                (outer_r, inner_r, theta_deg, note, cup_id)
            )


def save_prompt(body):
    if DATABASE_URL:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE prompt_templates SET body=%s WHERE id=1', (body,))
            conn.commit()
    else:
        with _sq_conn() as c:
            c.execute('UPDATE prompt_templates SET body=? WHERE id=1', (body,))


def get_user_by_username(username):
    if DATABASE_URL:
        import psycopg2.extras
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    'SELECT id, username, password_hash, role, is_active FROM users WHERE username=%s',
                    (username,)
                )
                row = cur.fetchone()
    else:
        with _sq_conn() as c:
            row = c.execute(
                'SELECT id, username, password_hash, role, is_active FROM users WHERE username=?',
                (username,)
            ).fetchone()
    return dict(row) if row else None


def verify_user(username, password):
    user = get_user_by_username(username)
    if not user or not user['is_active']:
        return None
    if check_password_hash(user['password_hash'], password):
        return user
    return None


def change_password(user_id, new_password):
    hashed = generate_password_hash(new_password)
    if DATABASE_URL:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE users SET password_hash=%s WHERE id=%s', (hashed, user_id))
            conn.commit()
    else:
        with _sq_conn() as c:
            c.execute('UPDATE users SET password_hash=? WHERE id=?', (hashed, user_id))


def get_all_users():
    if DATABASE_URL:
        import psycopg2.extras
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute('SELECT id, username, role, is_active, created_at FROM users ORDER BY id')
                return [dict(r) for r in cur.fetchall()]
    else:
        with _sq_conn() as c:
            rows = c.execute(
                'SELECT id, username, role, is_active, created_at FROM users ORDER BY id'
            ).fetchall()
        return [dict(r) for r in rows]


def create_user(username, password, role='user'):
    hashed = generate_password_hash(password)
    if DATABASE_URL:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s)',
                    (username, hashed, role)
                )
            conn.commit()
    else:
        with _sq_conn() as c:
            c.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (?,?,?)',
                (username, hashed, role)
            )


def toggle_user_active(user_id, is_active):
    val = bool(is_active)
    if DATABASE_URL:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE users SET is_active=%s WHERE id=%s', (val, user_id))
            conn.commit()
    else:
        with _sq_conn() as c:
            c.execute('UPDATE users SET is_active=? WHERE id=?', (int(val), user_id))


def get_active_prompt():
    if DATABASE_URL:
        import psycopg2.extras
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute('SELECT body FROM prompt_templates WHERE is_active=TRUE ORDER BY id DESC LIMIT 1')
                row = cur.fetchone()
    else:
        with _sq_conn() as c:
            row = c.execute('SELECT body FROM prompt_templates WHERE is_active=1 ORDER BY id DESC LIMIT 1').fetchone()
    return dict(row)['body'] if row else DEFAULT_PROMPT


# ── Banner 圖片（存 DB 避免 ephemeral filesystem 問題）────

def save_banner(slot, image_bytes, mime_type='image/jpeg'):
    """儲存 Banner 圖片到資料庫"""
    size_kb = len(image_bytes) // 1024
    if DATABASE_URL:
        import psycopg2
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO banners (slot, image_data, mime_type, size_kb, updated_at)
                       VALUES (%s, %s, %s, %s, NOW())
                       ON CONFLICT (slot) DO UPDATE
                       SET image_data = EXCLUDED.image_data,
                           mime_type  = EXCLUDED.mime_type,
                           size_kb    = EXCLUDED.size_kb,
                           updated_at = NOW()""",
                    (slot, psycopg2.Binary(image_bytes), mime_type, size_kb)
                )
            conn.commit()
    else:
        with _sq_conn() as c:
            c.execute(
                """INSERT INTO banners (slot, image_data, mime_type, size_kb)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (slot) DO UPDATE
                   SET image_data = excluded.image_data,
                       mime_type  = excluded.mime_type,
                       size_kb    = excluded.size_kb,
                       updated_at = datetime('now','localtime')""",
                (slot, image_bytes, mime_type, size_kb)
            )
    return size_kb


def get_banner(slot):
    """從資料庫讀取 Banner 圖片，回傳 (image_bytes, mime_type) 或 None"""
    if DATABASE_URL:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT image_data, mime_type FROM banners WHERE slot=%s', (slot,))
                row = cur.fetchone()
        if row:
            return (bytes(row[0]), row[1])
    else:
        with _sq_conn() as c:
            row = c.execute('SELECT image_data, mime_type FROM banners WHERE slot=?', (slot,)).fetchone()
        if row:
            return (row[0], row[1])
    return None


def get_banner_status():
    """取得所有 Banner 狀態"""
    result = []
    for n in (1, 2, 3):
        if DATABASE_URL:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT size_kb FROM banners WHERE slot=%s', (n,))
                    row = cur.fetchone()
        else:
            with _sq_conn() as c:
                row = c.execute('SELECT size_kb FROM banners WHERE slot=?', (n,)).fetchone()
        exists = row is not None
        size_kb = row[0] if row else 0
        result.append({'n': n, 'exists': exists, 'size_kb': size_kb})
    return result

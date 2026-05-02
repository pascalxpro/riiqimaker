# 部署指南

## 正式機資訊
- NAS 路徑：`\\HJ-02\docker\cup-app\`
- Container Manager 專案：`cup-app`
- 對外 URL：https://cup.kiseki.me

---

## 部署步驟

### 1. 複製檔案到 NAS
將以下檔案複製到 `\\HJ-02\docker\cup-app\`：
```
app.py
database.py
requirements.txt
Dockerfile
docker-compose.yml
templates/
static/
```
（uploads/ 資料夾保留，不要覆蓋）

### 2. Supabase：建立 users 表
若容器首次啟動前 users 表尚未建立，在 Supabase SQL Editor 執行：
```sql
-- 見 migrate_users.sql
```
※ 容器啟動時 init_db() 也會自動建表，通常不需要手動執行。

### 3. Supabase：更新 Prompt
在 Supabase SQL Editor 執行 `update_prompt.sql`（若尚未執行）。

### 4. 重建容器
在 Container Manager 中：
1. 停止 `cup-app` 專案
2. 刪除舊容器（不刪除 volumes）
3. 重新建置並啟動

---

## 首次登入後必做事項

| 步驟 | 說明 |
|------|------|
| 1 | 瀏覽 https://cup.kiseki.me/login |
| 2 | 帳號：`admin`　密碼：`RuiXing@2026!` |
| 3 | 進入後台 → **修改我的密碼** → 立即改成新密碼 |
| 4 | 視需要新增其他帳號 |

---

## 環境變數（docker-compose.yml）

| 變數 | 說明 |
|------|------|
| `DATABASE_URL` | Supabase PostgreSQL 連線字串 |
| `SECRET_KEY` | Flask Session 加密金鑰（已設定） |
| `ADMIN_PASSWORD` | 初始 admin 密碼，**首次建表後失效** |
| `FLASK_ENV` | `production` |
| `GEMINI_API_KEY` | Gemini API Key（可在後台更換） |

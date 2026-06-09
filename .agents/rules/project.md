# 矩形轉扇形圖

## 專案概述
Python Flask 應用程式，將矩形圖像轉換為扇形圖，整合 PostgreSQL 資料儲存、Gemini AI 輔助、圖片上傳管理。

## 技術棧
- **框架**：Python Flask 3.0+
- **圖像處理**：Pillow 10+、NumPy、SciPy
- **資料庫**：PostgreSQL（透過 psycopg2-binary）
- **AI**：Google Gemini（google-genai）
- **其他**：python-dotenv

## 資料庫：PostgreSQL（NAS Supabase）

- 連線透過 Docker 網路 `supabase_default`（外部網路）
- 連線設定在 `database.py`

## 部署：NAS Docker

- container 名稱：`cup-app`，對外 port：`5100`
- 環境變數從 `.env` 讀取
- 上傳圖片掛載於 `./uploads`，靜態檔案掛載於 `./static`

```bash
docker compose up -d --build
docker compose logs -f cup-app
```

## 開發

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py    # port 5000
```

## 重要規則
- `SECRET_KEY` 必須設定，未設定時應用程式拒絕啟動
- Production 環境（`FLASK_ENV=production`）Session Cookie 自動啟用 `Secure`
- 上傳只接受 `png`、`jpg`、`jpeg`，最大 20MB
- 修改路由時注意 `login_required` 和 `admin_required` decorator

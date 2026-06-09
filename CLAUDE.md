# RiiqiMaker

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

```bash
docker compose up -d --build    # 建置並啟動
docker compose restart          # 重啟不重建
docker compose logs -f riiqimaker  # 查看 log
```

### 部署注意事項
- container 名稱：`riiqimaker`，對外 port：`5100`
- 環境變數從 `.env` 讀取（`env_file: .env`）
- 必須設定 `SECRET_KEY` 環境變數，未設定時應用程式**拒絕啟動**
- 上傳圖片掛載於 `./uploads`（host 路徑）
- 靜態檔案掛載於 `./static`（host 路徑）
- 加入 `supabase_default` 網路才能連 PostgreSQL

## 開發

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python app.py                  # 本地開發（port 5000）
```

## 安全注意事項
- `SECRET_KEY` 必須設定，不能省略（app.py 強制檢查）
- Production 環境 `FLASK_ENV=production` 時，Session Cookie 自動啟用 `Secure` 旗標
- 上傳檔案只接受 `png`、`jpg`、`jpeg`，最大 20MB
- 有 `login_required` 和 `admin_required` decorator，修改路由時注意權限

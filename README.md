# RiiqiMaker — 紙杯扇形展開圖設計系統

紙杯印刷設計輔助工具，將矩形稿自動轉換為扇形展開圖，並整合 AI 圖像生成功能，適用於印刷廠內部設計流程。

**線上服務：** 

---

## 功能概覽

- 矩形設計稿 → 扇形展開圖自動轉換（依各杯型幾何參數計算）
- 支援單層杯、雙層杯多種規格（8 / 12 / 16 / 20 / 22 / 24 oz）
- 整合 Gemini AI 圖像生成，從文字描述生成設計草稿
- 多帳號管理，區分 admin / user 角色
- 後台管理杯型參數、AI Prompt 模板、API Key

---

## 技術架構

| 層級 | 技術 |
|------|------|
| 後端 | Python 3.11 / Flask |
| 資料庫 | PostgreSQL（部署於 NAS Supabase） |
| AI | Google Gemini API / HuggingFace FLUX |
| 圖像處理 | Pillow / NumPy / SciPy |
| 部署 | Docker + Synology Container Manager |

---

## 快速啟動（本機開發）

### 1. 取得程式碼

```bash
git clone https://github.com/seebox-xpro/riiqimaker.git
cd riiqimaker
```

### 2. 建立虛擬環境並安裝套件

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`，填入以下必要值：

| 變數 | 說明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 連線字串（連至 NAS Supabase） |
| `SECRET_KEY` | Flask Session 加密金鑰，隨機長字串即可 |
| `ADMIN_PASSWORD` | 初始 admin 密碼（僅首次建表時有效） |
| `GEMINI_API_KEY` | Gemini API Key（也可在後台設定） |

> **注意：** 資料庫（杯型參數、帳號、Prompt）存於 NAS PostgreSQL，連上同一個 DB 即可取得所有既有資料，不需重新設定。

### 4. 啟動伺服器

```bash
python app.py
```

瀏覽器開啟 http://localhost:5000

---

## 部署至 NAS（Docker）

詳細步驟請參閱 [DEPLOY.md](DEPLOY.md)。

```bash
# 將檔案同步至 NAS 後，在 Container Manager 重建容器
docker-compose up -d --build
```

---

## 目錄結構

```
riiqimaker/
├── app.py                  # 主程式（Flask 路由、API、圖像轉換邏輯）
├── database.py             # DB 初始化、CRUD 函式
├── requirements.txt        # Python 套件清單
├── Dockerfile
├── docker-compose.yml
├── .env.example            # 環境變數範本
├── templates/              # Jinja2 HTML 模板
│   ├── base.html
│   ├── index.html          # 主操作頁面
│   ├── admin.html          # 後台管理
│   └── login.html
├── static/
│   ├── css/main.css
│   └── js/main.js
└── Docs/                   # 杯型 Prompt 模板、規劃文件
```

---

## 帳號與權限

| 角色 | 權限 |
|------|------|
| `admin` | 全功能，含後台管理杯型、Prompt、帳號、API Key |
| `user` | 使用轉換與 AI 生成功能 |

首次部署後以 admin 身份登入，立即至後台修改預設密碼。

---

## 注意事項

- `.env` 含資料庫密碼，**不可上傳至版本控制**（已加入 `.gitignore`）
- `uploads/` 為暫存工作目錄，不隨 git 同步
- AI Prompt 模板與 API Key 存於資料庫，更換電腦後連同一個 DB 自動取得

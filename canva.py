"""
Canva Connect API 整合模組
支援 Popup 模式（方案 A）與 Redirect 模式（方案 B），透過後台 canva_mode 設定切換。
"""
import os, io, hashlib, base64, secrets, time
from functools import wraps

from flask import Blueprint, request, jsonify, redirect, session, url_for, abort, current_app
import requests as http_requests
from PIL import Image

from database import get_ai_setting

canva_bp = Blueprint('canva', __name__, url_prefix='/canva')

# ── 常數 ─────────────────────────────────────────────────
CANVA_AUTH_URL  = 'https://www.canva.com/api/oauth/authorize'
CANVA_TOKEN_URL = 'https://api.canva.com/rest/v1/oauth/token'
CANVA_API_BASE  = 'https://api.canva.com/rest/v1'

CANVA_SCOPES = ' '.join([
    'design:content:read',
    'design:content:write',
    'design:meta:read',
    'asset:write',
    'asset:read',
])


def _client_id():
    return os.environ.get('CANVA_CLIENT_ID', '')


def _client_secret():
    return os.environ.get('CANVA_CLIENT_SECRET', '')


def _canva_mode():
    """從 DB 讀取 canva_mode 設定，預設 popup"""
    mode = get_ai_setting('canva_mode')
    return mode if mode in ('popup', 'redirect') else 'popup'


# ── PKCE 工具 ─────────────────────────────────────────────

def _generate_pkce():
    """產生 PKCE code_verifier + code_challenge (S256)"""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    return verifier, challenge


# ── Token 輔助 ────────────────────────────────────────────

def _get_token():
    """從 session 取得 access_token，若過期嘗試 refresh"""
    token = session.get('canva_access_token')
    expires_at = session.get('canva_token_expires_at', 0)

    if token and time.time() < expires_at:
        return token

    # 嘗試 refresh
    refresh = session.get('canva_refresh_token')
    if refresh:
        new_token = _refresh_token(refresh)
        if new_token:
            return new_token

    return None


def _refresh_token(refresh_token):
    """用 refresh_token 換新的 access_token"""
    try:
        resp = http_requests.post(CANVA_TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': _client_id(),
            'client_secret': _client_secret(),
        }, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            session['canva_access_token'] = data['access_token']
            session['canva_refresh_token'] = data.get('refresh_token', refresh_token)
            session['canva_token_expires_at'] = time.time() + data.get('expires_in', 3600) - 60
            return data['access_token']
    except Exception as e:
        print(f'[Canva] refresh_token failed: {e}')
    return None


def _canva_headers():
    """Canva API 認證 headers"""
    token = _get_token()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def canva_login_required(f):
    """裝飾器：確認使用者已連接 Canva"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _get_token():
            return jsonify({'ok': False, 'msg': '請先連接 Canva 帳號'}), 401
        return f(*args, **kwargs)
    return decorated


# ── 路由：檢查狀態 ────────────────────────────────────────

@canva_bp.route('/status')
def canva_status():
    """檢查當前 session 是否已連接 Canva"""
    token = _get_token()
    return jsonify({
        'connected': token is not None,
        'mode': _canva_mode(),
        'has_client_id': bool(_client_id()),
    })


# ── 路由：OAuth 授權入口 ──────────────────────────────────

@canva_bp.route('/auth')
def canva_auth():
    """重導到 Canva OAuth 授權頁"""
    client_id = _client_id()
    if not client_id:
        return '<h3>CANVA_CLIENT_ID 環境變數未設定</h3>', 500

    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(32)

    # 存入 session 以便 callback 驗證
    session['canva_pkce_verifier'] = verifier
    session['canva_oauth_state'] = state

    # 組合 redirect_uri（強制 HTTPS，因 Zeabur 反向代理會導致 url_for 產生 http）
    redirect_uri = url_for('canva.canva_callback', _external=True, _scheme='https')

    # 用 urlencode 確保所有參數正確編碼
    from urllib.parse import urlencode
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': CANVA_SCOPES,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'state': state,
    })
    auth_url = f'{CANVA_AUTH_URL}?{params}'
    return redirect(auth_url)


# ── 路由：OAuth 回調 ──────────────────────────────────────

@canva_bp.route('/callback')
def canva_callback():
    """處理 Canva OAuth 回調"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        return _callback_error(f'授權被拒絕：{error}')

    if not code:
        return _callback_error('缺少授權碼')

    # 驗證 state
    saved_state = session.pop('canva_oauth_state', None)
    if state != saved_state:
        return _callback_error('CSRF 驗證失敗')

    verifier = session.pop('canva_pkce_verifier', None)
    if not verifier:
        return _callback_error('PKCE verifier 遺失')

    redirect_uri = url_for('canva.canva_callback', _external=True, _scheme='https')

    # 用 code + verifier 換 token
    try:
        resp = http_requests.post(CANVA_TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'code': code,
            'code_verifier': verifier,
            'redirect_uri': redirect_uri,
            'client_id': _client_id(),
            'client_secret': _client_secret(),
        }, timeout=15)

        if resp.status_code != 200:
            return _callback_error(f'Token 交換失敗：{resp.status_code} {resp.text[:200]}')

        data = resp.json()
        session['canva_access_token'] = data['access_token']
        session['canva_refresh_token'] = data.get('refresh_token', '')
        session['canva_token_expires_at'] = time.time() + data.get('expires_in', 3600) - 60

    except Exception as e:
        return _callback_error(f'Token 交換異常：{str(e)}')

    # 依模式決定回調行為
    mode = _canva_mode()
    if mode == 'popup':
        return _callback_popup_success()
    else:
        return redirect(url_for('index'))


def _callback_popup_success():
    """Popup 模式：postMessage 通知主視窗 + 自動關閉"""
    return '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Canva 授權成功</title>
<style>
  body{display:flex;align-items:center;justify-content:center;height:100vh;margin:0;
       font-family:system-ui;background:#f8f7ff;color:#333}
  .box{text-align:center;padding:40px}
  .icon{font-size:48px;margin-bottom:16px}
  p{color:#666;margin-top:12px}
</style></head><body>
<div class="box">
  <div class="icon">✅</div>
  <h2>Canva 連接成功！</h2>
  <p>視窗即將自動關閉…</p>
</div>
<script>
  if (window.opener) {
    window.opener.postMessage({type: 'canva-auth-success'}, '*');
  }
  setTimeout(() => window.close(), 1200);
</script>
</body></html>'''


def _callback_error(msg):
    """授權失敗頁面"""
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Canva 授權失敗</title>
<style>
  body{{display:flex;align-items:center;justify-content:center;height:100vh;margin:0;
       font-family:system-ui;background:#fff5f5;color:#333}}
  .box{{text-align:center;padding:40px;max-width:400px}}
  .icon{{font-size:48px;margin-bottom:16px}}
  p{{color:#c0392b;margin-top:12px;font-size:.9rem}}
  a{{display:inline-block;margin-top:20px;padding:10px 24px;background:#7D2AE8;color:#fff;
     text-decoration:none;border-radius:10px;font-weight:600}}
</style></head><body>
<div class="box">
  <div class="icon">❌</div>
  <h2>授權失敗</h2>
  <p>{msg}</p>
  <a href="javascript:window.close()">關閉視窗</a>
</div>
</body></html>'''


# ── 路由：建立 Design ─────────────────────────────────────

@canva_bp.route('/create-design', methods=['POST'])
@canva_login_required
def canva_create_design():
    """
    動態產生空白 PNG → 上傳 Canva Asset → 用 Asset 建立 Design
    Request JSON: { "cup_id": 1, "w_px": 2294, "h_px": 1029, "cup_name": "8oz 冷熱杯" }
    """
    data = request.get_json()
    w_px = data.get('w_px')
    h_px = data.get('h_px')
    cup_name = data.get('cup_name', '紙杯設計')

    if not w_px or not h_px:
        return jsonify({'ok': False, 'msg': '缺少尺寸資訊'}), 400

    headers = _canva_headers()
    if not headers:
        return jsonify({'ok': False, 'msg': 'Canva Token 已失效'}), 401

    try:
        # Step 1: 動態產生空白 PNG
        img = Image.new('RGBA', (int(w_px), int(h_px)), (255, 255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        # Step 2: 上傳到 Canva Asset API
        upload_headers = {
            'Authorization': headers['Authorization'],
        }
        # Canva Asset Upload 用 multipart
        asset_resp = http_requests.post(
            f'{CANVA_API_BASE}/asset-uploads',
            headers=upload_headers,
            data={
                'name_base64': base64.b64encode(f'Riiqi {cup_name} 底圖'.encode()).decode(),
            },
            files={
                'file': (f'blank_{w_px}x{h_px}.png', buf, 'image/png'),
            },
            timeout=30,
        )

        if asset_resp.status_code not in (200, 201):
            return jsonify({'ok': False, 'msg': f'Asset 上傳失敗：{asset_resp.status_code}',
                           'detail': asset_resp.text[:300]}), 500

        asset_data = asset_resp.json()
        # asset-uploads 回傳的結構可能是 job，需要等待完成
        asset_job = asset_data.get('job', {})
        asset_id = asset_job.get('asset', {}).get('id') or asset_data.get('asset', {}).get('id')

        if not asset_id:
            # 可能是非同步 job，需要輪詢
            job_id = asset_job.get('id')
            if job_id:
                # 輪詢最多 30 秒
                for _ in range(15):
                    time.sleep(2)
                    check = http_requests.get(
                        f'{CANVA_API_BASE}/asset-uploads/{job_id}',
                        headers=headers,
                        timeout=10,
                    )
                    if check.status_code == 200:
                        check_data = check.json()
                        job_status = check_data.get('job', {}).get('status', '')
                        if job_status == 'success':
                            asset_id = check_data['job']['asset']['id']
                            break
                        elif job_status == 'failed':
                            return jsonify({'ok': False, 'msg': 'Asset 上傳失敗'}), 500

            if not asset_id:
                return jsonify({'ok': False, 'msg': '無法取得 Asset ID'}), 500

        # Step 3: 用 Asset 建立 Design
        design_resp = http_requests.post(
            f'{CANVA_API_BASE}/designs',
            headers=headers,
            json={
                'design_type': {
                    'type': 'preset',
                    'name': 'doc',
                },
                'asset_id': asset_id,
                'title': f'Riiqi {cup_name} — 矩形圖設計',
            },
            timeout=15,
        )

        if design_resp.status_code not in (200, 201):
            return jsonify({'ok': False, 'msg': f'Design 建立失敗：{design_resp.status_code}',
                           'detail': design_resp.text[:300]}), 500

        design_data = design_resp.json()
        design = design_data.get('design', {})
        design_id = design.get('id', '')
        edit_url = design.get('urls', {}).get('edit_url', '')

        if not edit_url:
            return jsonify({'ok': False, 'msg': '無法取得 Design 編輯連結'}), 500

        # 存 design_id 到 session
        session['canva_design_id'] = design_id

        return jsonify({
            'ok': True,
            'design_id': design_id,
            'edit_url': edit_url,
        })

    except Exception as e:
        print(f'[Canva] create-design error: {e}')
        return jsonify({'ok': False, 'msg': f'建立失敗：{str(e)}'}), 500


# ── 路由：匯出 Design ─────────────────────────────────────

@canva_bp.route('/export', methods=['POST'])
@canva_login_required
def canva_export():
    """觸發 Canva Export Job"""
    data = request.get_json()
    design_id = data.get('design_id') or session.get('canva_design_id')

    if not design_id:
        return jsonify({'ok': False, 'msg': '缺少 Design ID'}), 400

    headers = _canva_headers()
    if not headers:
        return jsonify({'ok': False, 'msg': 'Canva Token 已失效'}), 401

    try:
        resp = http_requests.post(
            f'{CANVA_API_BASE}/exports',
            headers=headers,
            json={
                'design_id': design_id,
                'format': {'type': 'png'},
            },
            timeout=15,
        )

        if resp.status_code not in (200, 201):
            return jsonify({'ok': False, 'msg': f'匯出請求失敗：{resp.status_code}',
                           'detail': resp.text[:300]}), 500

        export_data = resp.json()
        job = export_data.get('job', {})
        job_id = job.get('id', '')

        return jsonify({
            'ok': True,
            'job_id': job_id,
            'status': job.get('status', 'in_progress'),
        })

    except Exception as e:
        return jsonify({'ok': False, 'msg': f'匯出失敗：{str(e)}'}), 500


# ── 路由：輪詢匯出進度 ────────────────────────────────────

@canva_bp.route('/export-status/<job_id>')
@canva_login_required
def canva_export_status(job_id):
    """查詢匯出進度，完成時下載 PNG 到 uploads/"""
    headers = _canva_headers()
    if not headers:
        return jsonify({'ok': False, 'msg': 'Canva Token 已失效'}), 401

    try:
        resp = http_requests.get(
            f'{CANVA_API_BASE}/exports/{job_id}',
            headers=headers,
            timeout=15,
        )

        if resp.status_code != 200:
            return jsonify({'ok': False, 'msg': f'查詢失敗：{resp.status_code}'}), 500

        data = resp.json()
        job = data.get('job', {})
        status = job.get('status', 'unknown')

        if status == 'success':
            # 下載 PNG 到 uploads/
            urls = job.get('urls', [])
            if urls:
                download_url = urls[0]
                png_resp = http_requests.get(download_url, timeout=30)
                if png_resp.status_code == 200:
                    import time as _t
                    ts = _t.strftime('%Y%m%d_%H%M%S')
                    filename = f'canva_design_{ts}.png'
                    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                    filepath = os.path.join(upload_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(png_resp.content)

                    return jsonify({
                        'ok': True,
                        'status': 'success',
                        'filename': filename,
                        'url': f'/uploads/{filename}',
                    })

            return jsonify({'ok': False, 'status': 'success', 'msg': '匯出成功但無下載連結'}), 500

        elif status == 'failed':
            return jsonify({'ok': False, 'status': 'failed', 'msg': '匯出失敗'}), 500

        else:
            return jsonify({'ok': True, 'status': status})

    except Exception as e:
        return jsonify({'ok': False, 'msg': f'查詢異常：{str(e)}'}), 500


# ── 路由：中斷連接 ────────────────────────────────────────

@canva_bp.route('/disconnect', methods=['POST'])
def canva_disconnect():
    """清除 session 中的 Canva token"""
    session.pop('canva_access_token', None)
    session.pop('canva_refresh_token', None)
    session.pop('canva_token_expires_at', None)
    session.pop('canva_design_id', None)
    return jsonify({'ok': True})

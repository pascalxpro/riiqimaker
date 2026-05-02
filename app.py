import os, math, time, io
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_from_directory, abort, session, redirect, url_for
from database import (init_db, get_cups, get_cup_by_id,
                      get_active_prompt, save_prompt,
                      update_cup, get_ai_setting, set_ai_setting,
                      verify_user, change_password, get_all_users,
                      create_user, toggle_user_active)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
BANNER_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'banners')
ALLOWED_EXT = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

_secret = os.environ.get('SECRET_KEY')
if not _secret:
    raise RuntimeError('SECRET_KEY 環境變數未設定，拒絕啟動')
app.secret_key = _secret

# Session cookie 安全設定
_is_prod = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = _is_prod


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page', next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page', next=request.path))
        if session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BANNER_FOLDER, exist_ok=True)


@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']         = 'SAMEORIGIN'
    response.headers['X-XSS-Protection']        = '1; mode=block'
    response.headers['Referrer-Policy']         = 'strict-origin-when-cross-origin'
    if _is_prod:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def _compute_dims(outer_r, inner_r, theta_deg):
    """從 R, r, θ 計算矩形圖像素尺寸"""
    theta = math.radians(theta_deg)
    W_mm = 2 * outer_r * math.sin(theta / 2)
    H_mm = outer_r - inner_r * math.cos(theta / 2)
    return round(W_mm * 10), round(H_mm * 10)


def _polar_warp(rect_img, outer_r, inner_r, theta_deg):
    """
    Polar warp: 矩形展開圖 → 扇形圖（RGBA，扇形外透明）

    座標系：
      頂邊 (y=0) = 外弧（R），底邊 (y=H) = 內弧（r）
      扇形在畫布內向上開展，頂點在畫布外（下方）
    """
    import numpy as np
    from PIL import Image as PILImage

    SCALE = 10.0            # mm → px
    R = outer_r * SCALE
    r = inner_r * SCALE
    theta = math.radians(theta_deg)

    out_w = math.ceil(2 * R * math.sin(theta / 2))
    out_h = math.ceil(R - r * math.cos(theta / 2))

    apex_x = out_w / 2.0
    apex_y = R              # 頂點在畫布上方 R px 處（常在畫布外）

    in_w, in_h = rect_img.size
    rect = np.array(rect_img.convert('RGBA'), dtype=np.float32)

    ys, xs = np.mgrid[0:out_h, 0:out_w].astype(np.float32)
    dx = xs - apex_x
    dy = ys - apex_y       # 負值（畫素在頂點上方）

    rho = np.sqrt(dx * dx + dy * dy)
    phi = np.arctan2(dx, -dy)   # 相對向上垂直軸的角度

    mask = (rho >= r) & (rho <= R) & (np.abs(phi) <= theta / 2)

    src_x = np.clip((phi / theta + 0.5) * in_w, 0, in_w - 1)
    src_y = np.clip((R - rho) / (R - r) * in_h, 0, in_h - 1)

    # 雙線性插值
    x0 = src_x.astype(np.int32); x1 = np.clip(x0 + 1, 0, in_w - 1)
    y0 = src_y.astype(np.int32); y1 = np.clip(y0 + 1, 0, in_h - 1)
    fx = (src_x - x0)[:, :, np.newaxis]
    fy = (src_y - y0)[:, :, np.newaxis]

    sampled = (
        rect[y0, x0] * (1 - fx) * (1 - fy) +
        rect[y0, x1] * fx       * (1 - fy) +
        rect[y1, x0] * (1 - fx) * fy +
        rect[y1, x1] * fx       * fy
    ).astype(np.uint8)

    # 扇形外填純白 #FFFFFF（規格要求）
    out = np.full((out_h, out_w, 3), 255, dtype=np.uint8)
    sampled_rgb = sampled[:, :, :3]
    out[mask] = sampled_rgb[mask]

    return PILImage.fromarray(out, 'RGB')


# ── 頁面路由 ──────────────────────────────────────────────

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()
    user = verify_user(data.get('username', ''), data.get('password', ''))
    if not user:
        return jsonify({'ok': False, 'msg': '帳號或密碼錯誤'}), 401
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    return jsonify({'ok': True, 'role': user['role']})


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/auth/me')
def api_me():
    if 'user_id' not in session:
        return jsonify({'logged_in': False})
    return jsonify({'logged_in': True, 'username': session['username'], 'role': session['role']})


@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def api_change_password():
    data = request.get_json()
    old_pw  = data.get('old_password', '')
    new_pw  = data.get('new_password', '')
    if not new_pw or len(new_pw) < 6:
        return jsonify({'ok': False, 'msg': '新密碼至少 6 個字元'}), 400
    user = verify_user(session['username'], old_pw)
    if not user:
        return jsonify({'ok': False, 'msg': '目前密碼錯誤'}), 401
    change_password(session['user_id'], new_pw)
    return jsonify({'ok': True})


@app.route('/guide')
def guide():
    return render_template('使用說明簡報.html')


@app.route('/')
def index():
    cups = get_cups()
    for c in cups:
        c['w_px'], c['h_px'] = _compute_dims(c['outer_r'], c['inner_r'], c['theta_deg'])
    banner_exists = [
        os.path.isfile(os.path.join(BANNER_FOLDER, f'banner{n}.jpg'))
        for n in (1, 2, 3)
    ]
    return render_template('index.html', cups=cups, banner_exists=banner_exists)


# ── API 路由 ──────────────────────────────────────────────

@app.route('/api/cups')
def api_cups():
    cups = get_cups()
    for c in cups:
        c['w_px'], c['h_px'] = _compute_dims(c['outer_r'], c['inner_r'], c['theta_deg'])
    return jsonify(cups)


@app.route('/api/cups/<int:cup_id>')
def api_cup(cup_id):
    cup = get_cup_by_id(cup_id)
    if not cup:
        abort(404)
    cup['w_px'], cup['h_px'] = _compute_dims(cup['outer_r'], cup['inner_r'], cup['theta_deg'])
    return jsonify(cup)


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Stage 1B：上傳矩形圖並驗證尺寸"""
    cup_id = request.form.get('cup_id', type=int)
    if not cup_id:
        return jsonify({'ok': False, 'msg': '請先選擇杯型'}), 400

    cup = get_cup_by_id(cup_id)
    if not cup:
        return jsonify({'ok': False, 'msg': '杯型不存在'}), 400

    f = request.files.get('file')
    if not f or not _allowed(f.filename):
        return jsonify({'ok': False, 'msg': '請上傳 PNG 或 JPG 圖片'}), 400

    from PIL import Image
    import io
    img = Image.open(io.BytesIO(f.read()))
    w, h = img.size
    exp_w, exp_h = _compute_dims(cup['outer_r'], cup['inner_r'], cup['theta_deg'])

    # 檢查尺寸，不符時自動縮放並回傳警告
    tol = 0.05
    w_ok = abs(w - exp_w) / exp_w <= tol
    h_ok = abs(h - exp_h) / exp_h <= tol
    warning = None
    if not w_ok or not h_ok:
        warning = f'圖片尺寸（{w}×{h}px）與建議尺寸（{exp_w}×{exp_h}px）不符，轉換結果比例可能略有差異'

    ts = time.strftime('%Y%m%d_%H%M%S')
    fname = f"{cup['cup_name']}_矩形圖_{ts}.png"
    save_path = os.path.join(UPLOAD_FOLDER, fname)
    img.save(save_path, 'PNG')

    result = {'ok': True, 'filename': fname, 'w': w, 'h': h}
    if warning:
        result['warning'] = warning
    return jsonify(result)


def _expand_prompt_with_llm(theme, style, text, custom_prompt, gemini_key):
    """Gemini Flash 將中文關鍵字擴寫成豐富英文視覺描述，取代 prompt 第一行"""
    from google import genai
    from google.genai import types

    system = (
        "You are a surface pattern design prompt engineer for AI image generation. "
        "Convert the user's brief input into a vivid, specific English visual description. "
        "Output ONLY the description (2-3 sentences), no explanation, no markdown. "
        "Describe: color palette, visual motifs, textures, mood, decorative elements. "
        "Naturally incorporate the main text as a centered label in the pattern."
    )
    user_msg = f"Theme: {theme}\nStyle: {style}\nMain text: \"{text}\""
    if custom_prompt:
        user_msg += f"\nExtra: {custom_prompt}"

    client = genai.Client(api_key=gemini_key)
    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=1024,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
    )
    # 逐 part 收集文字，避免 resp.text 在思考模式下為 None
    text = ''
    if resp.candidates:
        for part in resp.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                text += part.text
    text = text.strip()
    if not text:
        raise ValueError('Flash 回應為空（thinking_budget=0 但仍無輸出）')
    return text


def _hf_generate_image(prompt, w_px, h_px, api_key, model_id='black-forest-labs/FLUX.1-schnell'):
    """Hugging Face Inference API 圖像生成"""
    import requests
    # 對齊到 8 的倍數，最長邊不超過 1024（免費版限制）
    scale = min(1.0, 1024 / max(w_px, h_px))
    w_req = max(256, int(w_px * scale / 8) * 8)
    h_req = max(256, int(h_px * scale / 8) * 8)
    url = f'https://router.huggingface.co/hf-inference/models/{model_id}'
    resp = requests.post(
        url,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={'inputs': prompt, 'parameters': {'width': w_req, 'height': h_req, 'num_inference_steps': 4}},
        timeout=120
    )
    if resp.status_code != 200:
        raise Exception(f'HF API {resp.status_code}: {resp.text[:300]}')
    return resp.content


@app.route('/api/generate', methods=['POST'])
def api_generate():
    """Stage 1A：AI 生成矩形圖（支援 Google Gemini / Hugging Face FLUX）"""
    cup_id        = request.form.get('cup_id', type=int)
    theme         = request.form.get('theme', '').strip()
    style         = request.form.get('style', '').strip() or '現代簡約'
    text          = request.form.get('text',  '').strip() or '（無文字）'
    custom_prompt = request.form.get('custom_prompt', '').strip()

    if not cup_id:
        return jsonify({'ok': False, 'msg': '請先選擇杯型'}), 400
    if not theme:
        return jsonify({'ok': False, 'msg': '請填入設計主題'}), 400

    cup = get_cup_by_id(cup_id)
    if not cup:
        return jsonify({'ok': False, 'msg': '杯型不存在'}), 400

    model      = get_ai_setting('ai_model') or 'imagen-3.0-generate-002'
    gemini_key = (get_ai_setting('gemini_api_key') or os.environ.get('GEMINI_API_KEY', '')).strip()
    w_px, h_px = _compute_dims(cup['outer_r'], cup['inner_r'], cup['theta_deg'])
    template   = get_active_prompt()
    template_lines = template.split('\n')

    # LLM 擴寫：用 Gemini Flash 將中文關鍵字轉為豐富英文視覺描述
    expanded = None
    expand_error = None
    if gemini_key:
        try:
            expanded = _expand_prompt_with_llm(theme, style, text, custom_prompt, gemini_key)
        except Exception as ex:
            expand_error = str(ex)

    if expanded:
        # 擴寫成功：用 Flash 的描述取代第一行，強制插入文字指令，保留技術約束行
        text_line = f'The text "{text}" is displayed as a clear, prominent, centered label.'
        prompt = expanded + '\n' + text_line + '\n' + '\n'.join(template_lines[1:])
    else:
        # Fallback：原始 template 格式化
        prompt = template.format(
            cup_name=cup['cup_name'],
            W_mm=w_px / 10, H_mm=h_px / 10,
            theme=theme, style=style, text=text
        )
        if custom_prompt:
            lines = prompt.split('\n')
            lines.insert(1, custom_prompt)
            prompt = '\n'.join(lines)

    try:
        from PIL import Image

        # ── Hugging Face FLUX ──────────────────────────────
        if model.startswith('hf:'):
            hf_key = (get_ai_setting('hf_api_key') or os.environ.get('HF_API_KEY', '')).strip()
            if not hf_key:
                return jsonify({'ok': False, 'msg': '尚未設定 Hugging Face API Key，請至管理後台設定'}), 500
            model_id  = model[3:]  # strip 'hf:'
            img_bytes = _hf_generate_image(prompt, w_px, h_px, hf_key, model_id)

        # ── Google Gemini / Imagen ─────────────────────────
        else:
            import base64
            from google import genai
            from google.genai import types

            if not gemini_key:
                return jsonify({'ok': False, 'msg': '尚未設定 Gemini API Key，請至管理後台設定'}), 500

            client = genai.Client(api_key=gemini_key)

            if model.startswith('gemini'):
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE'])
                )
                img_bytes = None
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        img_bytes = base64.b64decode(part.inline_data.data)
                        break
                if not img_bytes:
                    return jsonify({'ok': False, 'msg': 'AI 未回傳圖片，請換個主題描述後重試'}), 500
            else:
                # Imagen
                ratio = w_px / h_px
                if ratio >= 1.5:   aspect = '16:9'
                elif ratio >= 1.1: aspect = '4:3'
                elif ratio >= 0.9: aspect = '1:1'
                elif ratio >= 0.65:aspect = '3:4'
                else:              aspect = '9:16'
                response = client.models.generate_images(
                    model=model,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio=aspect,
                        safety_filter_level='BLOCK_ONLY_HIGH',
                        person_generation='ALLOW_ADULT',
                    )
                )
                img_bytes = response.generated_images[0].image.image_bytes

        pil_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        pil_img = pil_img.resize((w_px, h_px), Image.LANCZOS)

        ts    = time.strftime('%Y%m%d_%H%M%S')
        fname = f"{cup['cup_name']}_矩形圖_{ts}.png"
        pil_img.save(os.path.join(UPLOAD_FOLDER, fname), 'PNG')

        return jsonify({'ok': True, 'filename': fname, 'w': w_px, 'h': h_px,
                        'prompt_used': prompt, 'expand_error': expand_error})

    except Exception as e:
        msg = str(e)
        raw = msg
        if 'API_KEY' in msg.upper() or 'PERMISSION' in msg.upper() or 'UNAUTHORIZED' in msg.upper():
            msg = 'API Key 無效或無權限'
        elif 'QUOTA' in msg.upper() or 'RATE' in msg.upper() or '429' in msg:
            msg = f'用量/速率限制：{raw[:300]}'
        elif 'SAFETY' in msg.upper():
            msg = '圖片內容被安全篩選器阻擋，請修改主題描述後重試'
        return jsonify({'ok': False, 'msg': f'AI 生成失敗：{msg}'}), 500


@app.route('/api/convert', methods=['POST'])
def api_convert():
    """Stage 2：Polar Warp 矩形→扇形"""
    cup_id   = request.form.get('cup_id', type=int)
    filename = request.form.get('filename', '').strip()

    if not cup_id or not filename:
        return jsonify({'ok': False, 'msg': '缺少杯型或檔案名稱'}), 400

    safe_name = os.path.basename(filename)
    src_path  = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.isfile(src_path):
        return jsonify({'ok': False, 'msg': '找不到矩形圖檔案'}), 400

    cup = get_cup_by_id(cup_id)
    if not cup:
        return jsonify({'ok': False, 'msg': '杯型不存在'}), 400

    try:
        from PIL import Image as PILImage
        rect_img = PILImage.open(src_path)
        fan_img  = _polar_warp(rect_img, cup['outer_r'], cup['inner_r'], cup['theta_deg'])

        ts        = time.strftime('%Y%m%d_%H%M%S')
        fan_fname = f"{cup['cup_name']}_扇形圖_{ts}.png"
        fan_img.save(os.path.join(UPLOAD_FOLDER, fan_fname), 'PNG')

        return jsonify({'ok': True, 'filename': fan_fname,
                        'w': fan_img.width, 'h': fan_img.height})
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'轉換失敗：{str(e)}'}), 500


@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html')


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    return jsonify(get_all_users())


@app.route('/api/admin/users', methods=['POST'])
@admin_required
def admin_create_user():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role     = data.get('role', 'user')
    if not username or not password:
        return jsonify({'ok': False, 'msg': '帳號和密碼不可為空'}), 400
    if len(password) < 6:
        return jsonify({'ok': False, 'msg': '密碼至少 6 個字元'}), 400
    if role not in ('admin', 'user'):
        return jsonify({'ok': False, 'msg': '無效的角色'}), 400
    try:
        create_user(username, password, role)
    except Exception:
        return jsonify({'ok': False, 'msg': '帳號已存在'}), 409
    return jsonify({'ok': True})


@app.route('/api/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    if user_id == session['user_id']:
        return jsonify({'ok': False, 'msg': '不能停用自己'}), 400
    data = request.get_json()
    toggle_user_active(user_id, data.get('is_active', True))
    return jsonify({'ok': True})


@app.context_processor
def inject_globals():
    return {
        'site_title':    get_ai_setting('site_title') or '杯杯設計工坊',
        'ui_theme':      get_ai_setting('ui_theme') or 'warm',
        'ui_font_family': get_ai_setting('ui_font_family') or 'Nunito',
        'ui_font_color': get_ai_setting('ui_font_color') or '',
        'ui_font_size':  get_ai_setting('ui_font_size') or '16',
    }


@app.route('/api/admin/appearance', methods=['GET'])
@admin_required
def admin_get_appearance():
    return jsonify({
        'ok': True,
        'ui_theme':      get_ai_setting('ui_theme') or 'warm',
        'ui_font_family': get_ai_setting('ui_font_family') or 'Nunito',
        'ui_font_color': get_ai_setting('ui_font_color') or '',
        'ui_font_size':  get_ai_setting('ui_font_size') or '16',
    })


@app.route('/api/admin/appearance', methods=['POST'])
@admin_required
def admin_save_appearance():
    data = request.get_json()
    valid_themes = {'warm','ocean','lavender','matcha','berry','business','artistic','neon'}
    valid_fonts  = {'Nunito','Noto Sans TC','Noto Serif TC','Roboto','Playfair Display'}
    theme = data.get('ui_theme', 'warm')
    font  = data.get('ui_font_family', 'Nunito')
    if theme not in valid_themes:
        return jsonify({'ok': False, 'msg': '無效的主題'}), 400
    if font not in valid_fonts:
        return jsonify({'ok': False, 'msg': '無效的字型'}), 400
    try:
        size = int(data.get('ui_font_size', 16))
        size = max(12, min(20, size))
    except (ValueError, TypeError):
        size = 16
    set_ai_setting('ui_theme', theme)
    set_ai_setting('ui_font_family', font)
    set_ai_setting('ui_font_color', data.get('ui_font_color', ''))
    set_ai_setting('ui_font_size', str(size))
    return jsonify({'ok': True})


@app.route('/api/admin/site-title', methods=['POST'])
@admin_required
def admin_save_site_title():
    data = request.get_json()
    title = (data.get('site_title') or '').strip()
    if not title:
        return jsonify({'ok': False, 'msg': '名稱不能為空'}), 400
    set_ai_setting('site_title', title)
    return jsonify({'ok': True})


@app.route('/api/admin/prompt', methods=['GET'])
@admin_required
def admin_get_prompt():
    return jsonify({'ok': True, 'body': get_active_prompt()})


@app.route('/api/admin/prompt', methods=['POST'])
@admin_required
def admin_save_prompt():
    data = request.get_json()
    body = data.get('body', '').strip()
    if not body:
        return jsonify({'ok': False, 'msg': 'Prompt 不可為空'}), 400
    save_prompt(body)
    return jsonify({'ok': True})


@app.route('/api/admin/ai-settings', methods=['GET'])
@admin_required
def admin_get_ai_settings():
    key    = get_ai_setting('gemini_api_key')
    hf_key = get_ai_setting('hf_api_key')
    model  = get_ai_setting('ai_model') or 'imagen-3.0-generate-002'
    masked    = ('•' * (len(key)    - 4) + key[-4:])    if len(key)    > 4 else ('•' * len(key))
    hf_masked = ('•' * (len(hf_key) - 4) + hf_key[-4:]) if len(hf_key) > 4 else ('•' * len(hf_key))
    return jsonify({
        'model': model,
        'key_masked': masked, 'key_set': bool(key),
        'hf_key_masked': hf_masked, 'hf_key_set': bool(hf_key),
    })


@app.route('/api/admin/ai-settings', methods=['POST'])
@admin_required
def admin_save_ai_settings():
    data   = request.get_json()
    model  = data.get('model', '').strip()
    key    = data.get('api_key', '').strip()
    hf_key = data.get('hf_key', '').strip()
    if model:  set_ai_setting('ai_model', model)
    if key:    set_ai_setting('gemini_api_key', key)
    if hf_key: set_ai_setting('hf_api_key', hf_key)
    return jsonify({'ok': True})


@app.route('/api/admin/test-flash', methods=['POST'])
@admin_required
def admin_test_flash():
    """測試 Gemini Flash 文字模型（用於 LLM 擴寫）是否可用"""
    data    = request.get_json()
    api_key = data.get('api_key', '').strip()
    if not api_key:
        api_key = (get_ai_setting('gemini_api_key') or os.environ.get('GEMINI_API_KEY', '')).strip()
    if not api_key:
        return jsonify({'ok': False, 'msg': '尚未設定 API Key'})
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='Reply with the word OK only.',
            config=types.GenerateContentConfig(
                max_output_tokens=512,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
        )
        reply = ''
        if resp.candidates:
            for part in resp.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    reply += part.text
        reply = reply.strip() or '(no text)'
        return jsonify({'ok': True, 'msg': f'gemini-2.5-flash 回應：{reply}'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'Flash 連線失敗：{str(e)[:300]}'})


@app.route('/api/admin/clear-key', methods=['POST'])
@admin_required
def admin_clear_key():
    """清除指定的 API Key"""
    data     = request.get_json()
    key_name = data.get('key', '')
    if key_name not in ('gemini_api_key', 'hf_api_key'):
        return jsonify({'ok': False, 'msg': '無效的 key 名稱'}), 400
    set_ai_setting(key_name, '')
    return jsonify({'ok': True})


@app.route('/api/admin/test-connection-only', methods=['POST'])
@admin_required
def admin_test_connection_only():
    """只驗證 API Key 是否有效，不掃描模型清單"""
    data    = request.get_json()
    api_key = data.get('api_key', '').strip()
    if not api_key:
        api_key = (get_ai_setting('gemini_api_key') or os.environ.get('GEMINI_API_KEY', '')).strip()
    if not api_key:
        return jsonify({'ok': False, 'msg': '尚未設定 API Key'})
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        # 只取第一個模型，快速驗證 Key 有效性
        next(iter(client.models.list()))
        return jsonify({'ok': True, 'msg': 'API Key 有效，連線正常'})
    except Exception as e:
        msg = str(e)
        if 'API_KEY' in msg.upper() or 'INVALID' in msg.upper():
            msg = 'API Key 無效'
        return jsonify({'ok': False, 'msg': f'連線失敗：{msg}'})


@app.route('/api/admin/test-connection', methods=['POST'])
@admin_required
def admin_test_connection():
    data    = request.get_json()
    api_key = data.get('api_key', '').strip()

    if not api_key:
        api_key = (get_ai_setting('gemini_api_key') or os.environ.get('GEMINI_API_KEY', '')).strip()
    if not api_key:
        return jsonify({'ok': False, 'msg': '尚未設定 API Key'})

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        all_models = list(client.models.list())

        imagen_models, flash_img_models = [], []
        for m in all_models:
            n = m.name.lower()
            if 'imagen' in n:
                imagen_models.append(m.name)
            elif 'flash' in n and 'image' in n:
                flash_img_models.append(m.name)

        return jsonify({
            'ok': True,
            'msg': f'連線成功！找到 {len(imagen_models)} 個 Imagen 模型、{len(flash_img_models)} 個 Flash 圖像模型',
            'imagen_models': imagen_models,
            'flash_img_models': flash_img_models,
        })
    except Exception as e:
        msg = str(e)
        if 'API_KEY' in msg.upper() or 'INVALID' in msg.upper():
            msg = 'API Key 無效'
        return jsonify({'ok': False, 'msg': f'連線失敗：{msg}'})


@app.route('/api/admin/cups', methods=['GET'])
@admin_required
def admin_get_cups():
    cups = get_cups()
    for c in cups:
        c['w_px'], c['h_px'] = _compute_dims(c['outer_r'], c['inner_r'], c['theta_deg'])
    return jsonify(cups)


@app.route('/api/admin/cups/<int:cup_id>', methods=['POST'])
@admin_required
def admin_update_cup(cup_id):
    data = request.get_json()
    try:
        outer_r   = float(data['outer_r'])
        inner_r   = float(data['inner_r'])
        theta_deg = float(data['theta_deg'])
        note      = data.get('note', '')
    except (KeyError, ValueError):
        return jsonify({'ok': False, 'msg': '數值格式錯誤'}), 400
    if outer_r <= inner_r:
        return jsonify({'ok': False, 'msg': '外弧半徑必須大於內弧半徑'}), 400
    if not (1 <= theta_deg <= 180):
        return jsonify({'ok': False, 'msg': '夾角需在 1°～180° 之間'}), 400
    update_cup(cup_id, outer_r, inner_r, theta_deg, note)
    cup = get_cup_by_id(cup_id)
    cup['w_px'], cup['h_px'] = _compute_dims(cup['outer_r'], cup['inner_r'], cup['theta_deg'])
    return jsonify({'ok': True, 'cup': cup})


@app.route('/download/<filename>')
@login_required
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


# ── Banner 圖片 ────────────────────────────────────────────

@app.route('/banner/<int:n>')
def banner_image(n):
    """提供輪播 Banner 圖片"""
    if n not in (1, 2, 3):
        abort(404)
    fname = f'banner{n}.jpg'
    path = os.path.join(BANNER_FOLDER, fname)
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(BANNER_FOLDER, fname)


@app.route('/api/admin/banner-status')
@admin_required
def admin_banner_status():
    """回傳 3 張 banner 是否已上傳"""
    banners = []
    for n in (1, 2, 3):
        path = os.path.join(BANNER_FOLDER, f'banner{n}.jpg')
        exists = os.path.isfile(path)
        size_kb = os.path.getsize(path) // 1024 if exists else 0
        banners.append({'n': n, 'exists': exists, 'size_kb': size_kb})
    return jsonify({'ok': True, 'banners': banners})


@app.route('/api/admin/banner-upload', methods=['POST'])
@admin_required
def admin_banner_upload():
    """上傳並壓縮 Banner 圖片"""
    n = request.form.get('n', type=int)
    if n not in (1, 2, 3):
        return jsonify({'ok': False, 'msg': '無效的 Banner 編號'}), 400

    f = request.files.get('file')
    if not f or not _allowed(f.filename):
        return jsonify({'ok': False, 'msg': '請上傳 PNG 或 JPG 圖片'}), 400

    fit = request.form.get('fit', 'cover')  # 'cover'=裁切中央  'scale'=等比縮放
    try:
        target_w = int(request.form.get('target_w', 1440))
        target_h = int(request.form.get('target_h', 500))
        target_w = max(400, min(2400, target_w))
        target_h = max(200, min(1200, target_h))
    except (ValueError, TypeError):
        target_w, target_h = 1440, 500

    from PIL import Image
    img = Image.open(io.BytesIO(f.read())).convert('RGB')
    orig_w, orig_h = img.size

    if fit == 'cover':
        # 裁切中央：先裁到目標比例，再縮放
        img_ratio    = orig_w / orig_h
        target_ratio = target_w / target_h
        if img_ratio > target_ratio:
            new_w = int(orig_h * target_ratio)
            left  = (orig_w - new_w) // 2
            img   = img.crop((left, 0, left + new_w, orig_h))
        elif img_ratio < target_ratio:
            new_h = int(orig_w / target_ratio)
            top   = (orig_h - new_h) // 2
            img   = img.crop((0, top, orig_w, top + new_h))
        img = img.resize((target_w, target_h), Image.LANCZOS)
    else:
        # 等比縮放：縮到目標範圍內，不裁切
        img.thumbnail((target_w, target_h), Image.LANCZOS)

    save_path = os.path.join(BANNER_FOLDER, f'banner{n}.jpg')
    img.save(save_path, 'JPEG', quality=82, optimize=True)

    size_kb = os.path.getsize(save_path) // 1024
    return jsonify({
        'ok': True,
        'size_kb': size_kb,
        'w': img.width, 'h': img.height,
        'orig_w': orig_w, 'orig_h': orig_h,
    })


@app.route('/api/admin/banner-delete/<int:n>', methods=['POST'])
@admin_required
def admin_banner_delete(n):
    """刪除指定 Banner 圖片"""
    if n not in (1, 2, 3):
        return jsonify({'ok': False, 'msg': '無效的 Banner 編號'}), 400
    path = os.path.join(BANNER_FOLDER, f'banner{n}.jpg')
    if os.path.isfile(path):
        os.remove(path)
    return jsonify({'ok': True})


# ── 啟動 ──────────────────────────────────────────────────

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    init_db()
    is_dev = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=is_dev, host='0.0.0.0', port=5000)

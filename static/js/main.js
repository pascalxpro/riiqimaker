/* ══════════════════════════════════════
   登入狀態
══════════════════════════════════════ */
console.log('[main.js] v2026-05-02b 已載入');

// 進階 Prompt 永遠展開（移除收放功能）
document.addEventListener('DOMContentLoaded', () => {
  const advPanel  = document.getElementById('advPanel');
  const advToggle = document.getElementById('advToggle');
  const advArrow  = document.getElementById('advArrow');
  if (advPanel)  { advPanel.style.display = 'block'; }
  if (advArrow)  { advArrow.style.display = 'none'; }
  if (advToggle) { advToggle.style.cursor = 'default'; advToggle.style.pointerEvents = 'none'; }
});
fetch('/api/auth/me').then(r => r.json()).then(d => {
  const authBtn       = document.getElementById('authBtn');
  const authBtnMobile = document.getElementById('authBtnMobile');
  if (!authBtn) return;
  if (d.logged_in) {
    const html = `<span style="font-size:.85rem;color:var(--text2);margin-right:6px">${d.username}</span>
      <button class="btn-login" id="btnLogout">登出</button>`;
    authBtn.innerHTML = html;
    if (authBtnMobile) authBtnMobile.innerHTML = html;
    document.getElementById('btnLogout')?.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      location.href = '/';
    });
    document.querySelectorAll('#authBtnMobile #btnLogout').forEach(b =>
      b.addEventListener('click', async () => {
        await fetch('/api/auth/logout', { method: 'POST' });
        location.href = '/';
      })
    );
  }
});

/* ══════════════════════════════════════
   主題切換
══════════════════════════════════════ */
const THEMES = ['warm', 'ocean', 'lavender', 'matcha', 'berry', 'business', 'artistic', 'neon'];

function applyTheme(t) {
  document.body.setAttribute('data-theme', t);
  localStorage.setItem('theme', t);
  document.querySelectorAll('.theme-dot').forEach(d => {
    d.classList.toggle('active', d.dataset.t === t);
  });
}

document.querySelectorAll('.theme-dot').forEach(dot => {
  dot.addEventListener('click', () => applyTheme(dot.dataset.t));
});

// 載入上次選擇的主題（優先 localStorage，其次 server 預設）
applyTheme(localStorage.getItem('theme') || document.body.dataset.theme || 'warm');


/* ══════════════════════════════════════
   漢堡選單
══════════════════════════════════════ */
const hamburger  = document.getElementById('hamburger');
const mobileMenu = document.getElementById('mobileMenu');

hamburger?.addEventListener('click', () => {
  hamburger.classList.toggle('open');
  mobileMenu.classList.toggle('open');
});


/* ══════════════════════════════════════
   杯型選擇
══════════════════════════════════════ */
let selectedCupId = null;
let selectedCupWPx = 0;
let selectedCupHPx = 0;
let selectedCupName = '';

function selectCup(id, wPx, hPx, name) {
  selectedCupId = id;

  document.querySelectorAll('.cup-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.id) === id);
  });

  const specBox = document.getElementById('specBox');
  specBox.querySelector('.spec-name').textContent = name;
  specBox.querySelector('.spec-size').textContent = `${wPx} × ${hPx} px`;
  specBox.classList.add('show');

  // 更新 Stage 1A info box
  document.getElementById('infoSize').textContent = `${wPx} × ${hPx} px`;
  // 更新 Stage 1B info box
  document.getElementById('uploadInfoSize').textContent = `${wPx} × ${hPx} px`;
  // 更新 Stage 1C Canva info box
  const canvaInfo = document.getElementById('canvaInfoSize');
  if (canvaInfo) canvaInfo.textContent = `${wPx} × ${hPx} px`;
  // 儲存尺寸供 Canva 使用
  selectedCupWPx = wPx;
  selectedCupHPx = hPx;
  selectedCupName = name;
}

// ── URL 參數自動選杯型 ─────────────────────────────────────
// 用法：https://riiqimaker.kiseki.me/?cup_id=2
//       https://riiqimaker.kiseki.me/?cup_id=2&tab=canva
(function autoSelectFromURL() {
  const params = new URLSearchParams(window.location.search);
  const cupId = params.get('cup_id');
  if (!cupId) return;

  // 找到對應的杯型按鈕並模擬點擊
  const btn = document.querySelector(`.cup-btn[data-id="${cupId}"]`);
  if (btn) {
    btn.click();

    // 自動切換到指定 tab（如 canva / upload / ai）
    const tab = params.get('tab');
    if (tab) {
      const tabBtn = document.querySelector(`.tab-btn[data-tab="panel1${tab === 'canva' ? 'c' : tab === 'upload' ? 'b' : 'a'}"]`);
      if (tabBtn) tabBtn.click();
    }

    // 捲動到步驟 2（製作矩形圖）
    setTimeout(() => {
      const step2 = document.querySelector('.card:nth-child(2)');
      if (step2) step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 300);
  }
})();


/* ══════════════════════════════════════
   Stage Tabs（1A / 1B / 1C）
══════════════════════════════════════ */
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === target));
  });
});


/* ══════════════════════════════════════
   Stage 1B：拖放 & 上傳
══════════════════════════════════════ */
const dropZone   = document.getElementById('dropZone');
const fileInput  = document.getElementById('fileInput');
const uploadForm = document.getElementById('uploadForm');
const uploadErr  = document.getElementById('uploadErr');

dropZone?.addEventListener('click', () => fileInput.click());

dropZone?.addEventListener('dragover', e => {
  e.preventDefault(); dropZone.classList.add('drag-over');
});
dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone?.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) handleFileSelect(f);
});

fileInput?.addEventListener('change', () => {
  if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
});

function handleFileSelect(f) {
  const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg'];
  if (!allowedTypes.includes(f.type)) {
    showErr(uploadErr, '請上傳 PNG 或 JPG 格式的圖片');
    return;
  }
  dropZone.querySelector('p').textContent = `已選取：${f.name}`;
  dropZone.querySelector('small').textContent = `${(f.size / 1024).toFixed(0)} KB`;

  // 圖片即時預覽
  const dzIcon = dropZone.querySelector('.dz-icon');
  let previewImg = dropZone.querySelector('.dz-preview');
  if (!previewImg) {
    previewImg = document.createElement('img');
    previewImg.className = 'dz-preview';
    previewImg.style.cssText = 'max-width:100%;max-height:220px;border-radius:12px;margin-top:10px;object-fit:contain;box-shadow:0 2px 12px rgba(0,0,0,.1);cursor:zoom-in';
    previewImg.addEventListener('click', (e) => { e.stopPropagation(); openLightbox(previewImg.src); });
    dropZone.appendChild(previewImg);
  }
  if (dzIcon) dzIcon.style.display = 'none';
  const reader = new FileReader();
  reader.onload = (e) => { previewImg.src = e.target.result; };
  reader.readAsDataURL(f);
}

uploadForm?.addEventListener('submit', async e => {
  e.preventDefault();
  if (!selectedCupId) { showErr(uploadErr, '請先選擇杯型'); return; }
  if (!fileInput.files[0]) { showErr(uploadErr, '請選擇圖片檔案'); return; }

  hideErr(uploadErr);
  hideWarn(uploadWarn);
  const fd = new FormData();
  fd.append('cup_id', selectedCupId);
  fd.append('file', fileInput.files[0]);

  showProgress('uploadProgress', '上傳圖片中…', 40);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      setProgress('uploadProgress', 100, '上傳成功！');
      const uploadSubmitBtn = uploadForm.querySelector('.btn-primary');
      if (uploadSubmitBtn) { uploadSubmitBtn.textContent = '✅ 已上傳完成'; uploadSubmitBtn.disabled = true; }
      setTimeout(() => {
        hideProgress('uploadProgress');
        if (data.warning) showWarn(uploadWarn, '⚠️ ' + data.warning);
        showCelebrate('uploadCelebrate');
        onRectReady(data.filename);
      }, 800);
    } else {
      hideProgress('uploadProgress');
      showErr(uploadErr, data.msg);
    }
  } catch {
    hideProgress('uploadProgress');
    showErr(uploadErr, '上傳失敗，請稍後再試');
  }
});


/* ══════════════════════════════════════
   Stage 1A：AI 生成
══════════════════════════════════════ */
const generateForm = document.getElementById('generateForm');
const generateErr  = document.getElementById('generateErr');

let generatedFilename = null;

generateForm?.addEventListener('submit', async e => {
  e.preventDefault();
  if (!selectedCupId) { showErr(generateErr, '請先選擇杯型'); return; }

  const theme = generateForm.querySelector('[name=theme]').value.trim();
  if (!theme) { showErr(generateErr, '請填入設計主題'); return; }

  hideErr(generateErr);
  const msgs = ['讓 AI 動腦中…', '調配色彩…', '描繪輪廓…', '加上細節…', '快好了！'];
  let i = 0;
  showProgress('genProgress', msgs[0], 10);
  const iv = setInterval(() => {
    i++;
    if (i < msgs.length) setProgress('genProgress', (i + 1) * 18, msgs[i]);
  }, 2000);

  try {
    const fd = new FormData(generateForm);
    fd.append('cup_id', selectedCupId);
    const res  = await fetch('/api/generate', { method: 'POST', body: fd });
    const data = await res.json();
    clearInterval(iv);

    if (data.ok) {
      setProgress('genProgress', 100, '生成完成！');
      if (data.prompt_used || data.expand_error) {
        const preview = document.getElementById('promptPreview');
        const body    = document.getElementById('promptPreviewBody');
        const toggle  = document.getElementById('promptPreviewToggle');
        if (preview && body && toggle) {
          let txt = '';
          if (data.expand_error) txt = '[Flash 擴寫失敗] ' + data.expand_error + '\n\n';
          txt += data.prompt_used || '';
          body.textContent = txt;
          preview.style.display = 'block';
          toggle.onclick = () => {
            const open = body.style.display === 'block';
            body.style.display = open ? 'none' : 'block';
            toggle.textContent = (open ? '▶' : '▼') + ' 查看實際送出的 Prompt';
          };
        }
      }
      const genSubmitBtn = generateForm.querySelector('.btn-primary');
      if (genSubmitBtn) { genSubmitBtn.textContent = '✅ 已生成完成'; genSubmitBtn.disabled = true; }
      setTimeout(() => {
        hideProgress('genProgress');
        onRectReady(data.filename);
      }, 600);
    } else {
      hideProgress('genProgress');
      showErr(generateErr, data.msg);
    }
  } catch {
    clearInterval(iv);
    hideProgress('genProgress');
    showErr(generateErr, 'AI 連線失敗，請稍後再試');
  }
});


/* ══════════════════════════════════════
   矩形圖完成後共用流程
══════════════════════════════════════ */
function onRectReady(filename) {
  generatedFilename = filename;

  // 下載區連結（轉換完成後才顯示）
  document.getElementById('rectPreview').src = `/download/${filename}`;
  document.getElementById('dlRect').href = `/download/${filename}`;

  // Card 2 內嵌縮圖預覽（放大 + 點擊 lightbox）
  const mini = document.getElementById('rectMiniPreview');
  if (mini) {
    mini.src = `/download/${filename}`;
    mini.style.width  = '180px';
    mini.style.height = '104px';
    mini.classList.add('img-zoomable');
    mini.title = '點擊放大檢視';
    mini.onclick = () => openLightbox(`/download/${filename}`);
    console.log('[mini] classes:', mini.className, 'cursor:', getComputedStyle(mini).cursor);
  }

  // 顯示 Card 2 內嵌轉換區（滑入動畫）
  const convertSection = document.getElementById('convertSection');
  if (convertSection) {
    convertSection.style.display = 'block';
    convertSection.classList.remove('anim-slide-down');
    void convertSection.offsetWidth; // reflow 觸發重播
    convertSection.classList.add('anim-slide-down');
  }

  // 啟用轉換按鈕並加脈衝光環
  const btn = document.getElementById('btnConvert');
  if (btn) {
    btn.disabled = false;
    btn.textContent = '🌀 開始轉換扇形圖';
    btn.classList.add('btn-pulse');
  }

  // 注入「重新開始」按鈕（若已存在不重複加）
  if (!document.getElementById('btnReset') && convertSection) {
    const resetBtn = document.createElement('button');
    resetBtn.id = 'btnReset';
    resetBtn.className = 'btn-test';
    resetBtn.style.cssText = 'width:100%;margin-top:10px;padding:10px;font-size:.9rem;font-weight:700;border-radius:14px';
    resetBtn.textContent = '🔄 重新開始（重新上傳或生成）';
    resetBtn.addEventListener('click', resetFlow);
    convertSection.firstElementChild.appendChild(resetBtn);
  }

  // Step 進度
  document.getElementById('step2').classList.add('active');

  // 捲到轉換區
  setTimeout(() => convertSection?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 100);
}


/* ══════════════════════════════════════
   工具函式
══════════════════════════════════════ */
function showErr(el, msg) {
  el.textContent = msg;
  el.classList.add('show');
}
function hideErr(el) { el.classList.remove('show'); }

function showWarn(el, msg) {
  el.textContent = msg;
  el.classList.add('show');
}
function hideWarn(el) { el?.classList.remove('show'); }

function showProgress(id, msg, pct) {
  const w = document.getElementById(id);
  w.classList.add('show');
  w.querySelector('.progress-bar-fill').style.width = pct + '%';
  w.querySelector('.progress-msg').textContent = msg;
}
function setProgress(id, pct, msg) {
  const w = document.getElementById(id);
  w.querySelector('.progress-bar-fill').style.width = pct + '%';
  w.querySelector('.progress-msg').textContent = msg;
}
function hideProgress(id) {
  document.getElementById(id)?.classList.remove('show');
}
function showCelebrate(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.add('show'); }
}

/* 捲動到主功能區 */
document.getElementById('btnStart')?.addEventListener('click', () => {
  document.getElementById('mainSection')?.scrollIntoView({ behavior: 'smooth' });
});


/* ══════════════════════════════════════
   Stage 2：Polar Warp 轉換
══════════════════════════════════════ */
const btnConvert = document.getElementById('btnConvert');
const convertErr = document.getElementById('convertErr');

btnConvert?.addEventListener('click', async () => {
  if (!generatedFilename || !selectedCupId) return;

  hideErr(convertErr);
  btnConvert.disabled = true;
  btnConvert.classList.remove('btn-pulse');
  btnConvert.innerHTML = '<span class="btn-spinner"></span>轉換中…';

  const msgs = ['計算極座標中…', '展開扇形弧度…', '貼合每條弧線…', '最後收尾…'];
  let i = 0;
  showProgress('convertProgress', msgs[0], 15);
  const iv = setInterval(() => {
    i++;
    if (i < msgs.length) setProgress('convertProgress', (i + 1) * 22, msgs[i]);
  }, 1500);

  try {
    const fd = new FormData();
    fd.append('cup_id', selectedCupId);
    fd.append('filename', generatedFilename);

    const res  = await fetch('/api/convert', { method: 'POST', body: fd });
    const data = await res.json();
    clearInterval(iv);

    if (data.ok) {
      setProgress('convertProgress', 100, '轉換完成！');
      setTimeout(() => {
        hideProgress('convertProgress');
        onFanReady(data.filename);
      }, 600);
    } else {
      hideProgress('convertProgress');
      showErr(convertErr, data.msg);
      btnConvert.disabled = false;
    }
  } catch {
    clearInterval(iv);
    hideProgress('convertProgress');
    showErr(convertErr, '轉換失敗，請稍後再試');
    btnConvert.disabled = false;
  }
});

function onFanReady(filename) {
  document.getElementById('fanPreview').src = `/download/${filename}`;
  document.getElementById('dlFan').href     = `/download/${filename}`;

  // 轉換按鈕顯示完成狀態
  const btnConvert = document.getElementById('btnConvert');
  if (btnConvert) btnConvert.innerHTML = '✅ 轉換完成';

  // 顯示下載結果區
  document.getElementById('resultPlaceholder').style.display = 'none';
  const resultWrap = document.getElementById('resultWrap');
  resultWrap.style.display = 'block';

  // Step 進度
  document.getElementById('step2').classList.add('done');
  document.getElementById('step3').classList.add('active');

  // 捲到下載區
  resultWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function openLightbox(src) {
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position:fixed; inset:0; z-index:9999;
    background:rgba(0,0,0,.88);
    display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:14px;
    cursor:zoom-out; animation:lb-fade .25s ease;
  `;

  const img = document.createElement('img');
  img.src = src;
  img.style.cssText = `
    max-width:92vw; max-height:82vh;
    border-radius:12px; object-fit:contain;
    box-shadow:0 8px 48px rgba(0,0,0,.6);
  `;

  const hint = document.createElement('div');
  hint.style.cssText = 'color:rgba(255,255,255,.65);font-size:.85rem;user-select:none';
  hint.textContent = '點擊任意處或按 ESC 關閉';

  overlay.append(img, hint);
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  overlay.addEventListener('click', close);
  const onEsc = e => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onEsc); } };
  document.addEventListener('keydown', onEsc);
}

function resetFlow() {
  generatedFilename = null;

  // 移除「重新開始」按鈕（下次 onRectReady 重新注入）
  document.getElementById('btnReset')?.remove();

  // 還原上傳按鈕
  const uploadSubmitBtn = uploadForm?.querySelector('.btn-primary');
  if (uploadSubmitBtn) { uploadSubmitBtn.textContent = '✅ 上傳並驗證'; uploadSubmitBtn.disabled = false; }

  // 還原生成按鈕
  const genSubmitBtn = generateForm?.querySelector('.btn-primary');
  if (genSubmitBtn) { genSubmitBtn.textContent = '✨ 開始生成矩形圖'; genSubmitBtn.disabled = false; }

  // 還原上傳 drop zone
  if (fileInput) fileInput.value = '';
  const dzP = dropZone?.querySelector('p');
  const dzS = dropZone?.querySelector('small');
  if (dzP) dzP.textContent = '點擊選擇或拖放圖片到這裡';
  if (dzS) dzS.textContent = '支援 PNG、JPG，建議按照上方尺寸製作';
  // 移除圖片預覽
  const dzPreview = dropZone?.querySelector('.dz-preview');
  if (dzPreview) dzPreview.remove();
  const dzIcon = dropZone?.querySelector('.dz-icon');
  if (dzIcon) dzIcon.style.display = '';

  // 清除 progress / error / celebrate
  hideProgress('uploadProgress');
  hideProgress('genProgress');
  hideProgress('convertProgress');
  const uploadErr2 = document.getElementById('uploadErr');
  const generateErr2 = document.getElementById('generateErr');
  if (uploadErr2) hideErr(uploadErr2);
  if (generateErr2) hideErr(generateErr2);
  hideWarn(document.getElementById('uploadWarn'));
  const cel = document.getElementById('uploadCelebrate');
  if (cel) cel.classList.remove('show');

  // 隱藏 prompt preview
  const pp = document.getElementById('promptPreview');
  if (pp) pp.style.display = 'none';

  // 隱藏轉換區
  const convertSection = document.getElementById('convertSection');
  if (convertSection) convertSection.style.display = 'none';

  // 還原轉換按鈕
  const btn = document.getElementById('btnConvert');
  if (btn) { btn.disabled = true; btn.textContent = '🌀 開始轉換扇形圖'; btn.classList.remove('btn-pulse'); }

  // 隱藏下載區
  document.getElementById('resultWrap').style.display = 'none';
  document.getElementById('resultPlaceholder').style.display = '';

  // 重置步驟指示器
  document.getElementById('step2').classList.remove('done', 'active');
  document.getElementById('step3').classList.remove('active');

  // 捲到製作區頂部
  document.getElementById('mainSection')?.scrollIntoView({ behavior: 'smooth' });
}


/* ══════════════════════════════════════
   Canva Connect API 整合
══════════════════════════════════════ */
let canvaDesignId = null;

// 初始化：檢查 Canva 連接狀態
(function initCanva() {
  const panel = document.getElementById('panel1c');
  if (!panel) return;  // Canva 未啟用

  fetch('/canva/status').then(r => r.json()).then(data => {
    if (data.connected) {
      _canvaShowConnected();
    }
  }).catch(() => {});
})();


function _canvaShowConnected() {
  const dot = document.getElementById('canvaDot');
  const txt = document.getElementById('canvaStatusText');
  const connectArea = document.getElementById('canvaConnectArea');
  const designArea  = document.getElementById('canvaDesignArea');
  if (dot) dot.classList.add('connected');
  if (txt) txt.textContent = '✅ 已連接 Canva';
  if (connectArea) connectArea.querySelector('.btn-canva').style.display = 'none';
  if (designArea) designArea.style.display = '';
}


function connectCanva() {
  if (typeof canvaMode !== 'undefined' && canvaMode === 'redirect') {
    // Redirect 模式：整頁跳轉
    window.location.href = '/canva/auth';
  } else {
    // Popup 模式：小視窗
    const w = 600, h = 700;
    const left = (screen.width - w) / 2;
    const top  = (screen.height - h) / 2;
    window.open('/canva/auth', 'canva-auth',
      `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no`);
  }
}

// 監聽 Popup 回傳的授權成功訊息
window.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'canva-auth-success') {
    _canvaShowConnected();
  }
});


function createCanvaDesign() {
  if (!selectedCupId) {
    _canvaShowError('請先選擇杯型');
    return;
  }

  const btn = document.getElementById('btnCanvaCreate');
  btn.disabled = true;
  btn.textContent = '⭐ 正在建立設計…';
  _canvaShowError('');

  // 先同步開啟空白視窗（避免被瀏覽器阻擋彈出視窗）
  let editorWindow = null;
  if (typeof canvaMode === 'undefined' || canvaMode !== 'redirect') {
    const w = 1280, h = 800;
    const left = (screen.width - w) / 2;
    const top  = (screen.height - h) / 2;
    editorWindow = window.open('about:blank', 'canva-editor',
      `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no`);
    if (editorWindow) {
      editorWindow.document.write(`
        <html><head><title>Canva 設計</title>
        <style>body{display:flex;align-items:center;justify-content:center;height:100vh;margin:0;
        font-family:system-ui;background:#f8f7ff;color:#333}
        .loader{text-align:center}.spinner{width:48px;height:48px;border:4px solid #e0e0e0;
        border-top:4px solid #7D2AE8;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 16px}
        @keyframes spin{to{transform:rotate(360deg)}}</style></head><body>
        <div class="loader"><div class="spinner"></div><h3>正在建立 Canva 設計…</h3><p>請稍候，尺寸與底圖準備中</p></div>
        </body></html>`);
    }
  }

  fetch('/canva/create-design', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      cup_id: selectedCupId,
      w_px: selectedCupWPx,
      h_px: selectedCupHPx,
      cup_name: selectedCupName,
    }),
  })
  .then(r => r.json())
  .then(data => {
    btn.disabled = false;
    btn.textContent = '✨ 開啟 Canva 設計';

    if (!data.ok) {
      const errMsg = data.msg || '建立失敗';
      const errDetail = data.detail || '';
      console.error('[Canva] create-design error:', errMsg, errDetail);
      // 在 popup 裡顯示錯誤（而非直接關閉）
      if (editorWindow && !editorWindow.closed) {
        editorWindow.document.body.innerHTML = `
          <div style="text-align:center;padding:40px;font-family:system-ui">
            <div style="font-size:48px;margin-bottom:16px">❌</div>
            <h3>建立失敗</h3>
            <p style="color:#c0392b;max-width:500px;margin:12px auto;word-break:break-all">${errMsg}</p>
            ${errDetail ? `<pre style="text-align:left;background:#f5f5f5;padding:12px;border-radius:8px;max-width:500px;margin:12px auto;overflow:auto;font-size:12px">${errDetail}</pre>` : ''}
            <button onclick="window.close()" style="margin-top:20px;padding:10px 24px;background:#7D2AE8;color:#fff;border:none;border-radius:10px;cursor:pointer;font-size:14px">關閉視窗</button>
          </div>`;
      }
      _canvaShowError(errMsg);
      return;
    }

    canvaDesignId = data.design_id;

    // 導向 Canva 編輯器
    if (editorWindow && !editorWindow.closed) {
      editorWindow.location.href = data.edit_url;
    } else {
      // Redirect 模式 or popup 被關閉
      editorWindow = window.open(data.edit_url, '_blank');
    }

    const hint = document.getElementById('canvaHint');
    if (hint) hint.textContent = '✅ Canva 編輯器已開啟，設計完成後關閉視窗即可。';

    // 監聽編輯器關閉 → 自動匯出
    if (editorWindow) {
      const timer = setInterval(() => {
        if (editorWindow.closed) {
          clearInterval(timer);
          if (hint) hint.textContent = '📦 正在匯出設計稿…';
          _exportCanvaDesign();
        }
      }, 1000);
    }
  })
  .catch(err => {
    btn.disabled = false;
    btn.textContent = '✨ 開啟 Canva 設計';
    console.error('[Canva] network error:', err);
    if (editorWindow && !editorWindow.closed) {
      editorWindow.document.body.innerHTML = `
        <div style="text-align:center;padding:40px;font-family:system-ui">
          <div style="font-size:48px;margin-bottom:16px">⚠️</div>
          <h3>網路錯誤</h3>
          <p style="color:#c0392b">${err.message || err}</p>
          <button onclick="window.close()" style="margin-top:20px;padding:10px 24px;background:#7D2AE8;color:#fff;border:none;border-radius:10px;cursor:pointer;font-size:14px">關閉視窗</button>
        </div>`;
    }
    _canvaShowError('網路錯誤，請重試');
  });
}



function _exportCanvaDesign() {
  if (!canvaDesignId) {
    _canvaShowError('缺少 Design ID');
    return;
  }

  const progress = document.getElementById('canvaExportProgress');
  const fill = progress.querySelector('.progress-bar-fill');
  const msg  = progress.querySelector('.progress-msg');
  progress.style.display = '';
  fill.style.width = '20%';
  msg.textContent = '⭐ 正在向 Canva 請求匯出 PNG…';

  fetch('/canva/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ design_id: canvaDesignId }),
  })
  .then(r => r.json())
  .then(data => {
    if (!data.ok) {
      _canvaShowError(data.msg || '匯出失敗');
      progress.style.display = 'none';
      return;
    }
    fill.style.width = '40%';
    msg.textContent = '⏳ 等待 Canva 處理中…';
    _pollExportStatus(data.job_id, fill, msg, progress);
  })
  .catch(() => {
    _canvaShowError('匯出請求失敗');
    progress.style.display = 'none';
  });
}


function _pollExportStatus(jobId, fill, msg, progress) {
  let attempts = 0;
  const maxAttempts = 30;  // 最多輪詢 30 次（約 60 秒）

  const poll = () => {
    attempts++;
    const pct = Math.min(40 + (attempts / maxAttempts) * 50, 90);
    fill.style.width = pct + '%';

    fetch(`/canva/export-status/${jobId}`)
      .then(r => r.json())
      .then(data => {
        if (data.status === 'success' && data.filename) {
          fill.style.width = '100%';
          msg.textContent = '✅ 匯出完成！';

          // 複用共用流程：設定矩形圖預覽、下載連結、顯示轉換區
          onRectReady(data.filename);

          // 慶祝
          const cel = document.getElementById('canvaCelebrate');
          if (cel) cel.classList.add('show');

          setTimeout(() => {
            progress.style.display = 'none';
            const convertSection = document.getElementById('convertSection');
            if (convertSection) convertSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }, 800);
          return;
        }

        if (data.status === 'failed') {
          _canvaShowError('匯出失敗，請重試');
          progress.style.display = 'none';
          return;
        }

        if (attempts >= maxAttempts) {
          _canvaShowError('匯出逾時，請重試');
          progress.style.display = 'none';
          return;
        }

        msg.textContent = `⏳ 等待 Canva 處理中…（${attempts}/${maxAttempts}）`;
        setTimeout(poll, 2000);
      })
      .catch(() => {
        if (attempts < maxAttempts) {
          setTimeout(poll, 3000);
        } else {
          _canvaShowError('查詢失敗');
          progress.style.display = 'none';
        }
      });
  };

  setTimeout(poll, 2000);
}


function _canvaShowError(msg) {
  const el = document.getElementById('canvaErr');
  if (el) {
    el.textContent = msg;
    el.style.display = msg ? '' : 'none';
  }
}

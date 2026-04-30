(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || '').replace(/\/$/, '');
  const title = currentScript?.dataset.chatbotTitle || 'GBM Deep Think';

  if (!apiBase) {
    console.error('Missing data-api-base');
    return;
  }

  const root = document.createElement('div');
  root.id = 'gbm-chat-root';
  document.body.appendChild(root);

  let mode = 'visual';
  let lastData = null;

  function abs(url) {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    if (url.startsWith('/')) return apiBase + url;
    return url;
  }

  function esc(t) {
    return String(t || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  root.innerHTML = `
    <style>
      #gbm-chat-root * { box-sizing: border-box; font-family: Arial, sans-serif; }

      .gbm-launcher {
        display:block !important;
        position:fixed !important;
        bottom:20px !important;
        right:20px !important;
        z-index:2147483647 !important;
        background:#006f63;
        color:#fff;
        padding:14px 20px;
        border-radius:999px;
        border:none;
        font-weight:bold;
        cursor:pointer;
      }

      .gbm-panel {
        position:fixed;
        bottom:80px;
        right:20px;
        width:420px;
        height:600px;
        background:#fff;
        border-radius:12px;
        display:none;
        flex-direction:column;
        overflow:hidden;
        z-index:2147483646;
        box-shadow:0 10px 30px rgba(0,0,0,.25);
      }

      .gbm-header {
        background:#006f63;
        color:#fff;
        padding:12px;
        display:flex;
        justify-content:space-between;
      }

      .gbm-messages {
        flex:1;
        overflow:auto;
        padding:10px;
        background:#f1f5f9;
      }

      .gbm-input-row {
        display:flex;
        gap:6px;
        padding:10px;
      }

      .gbm-input {
        flex:1;
        padding:8px;
      }

      .gbm-send {
        background:#006f63;
        color:#fff;
        border:none;
        padding:8px 12px;
        cursor:pointer;
      }

      .gbm-card {
        border:1px solid #ddd;
        margin-top:10px;
        border-radius:10px;
        overflow:hidden;
      }

      .gbm-card img {
        width:100%;
        height:120px;
        object-fit:cover;
      }

      .gbm-card-body {
        padding:8px;
      }

      .gbm-toggle {
        font-size:12px;
        color:#006f63;
        cursor:pointer;
        margin:8px 0;
        font-weight:bold;
      }
    </style>

    <button class="gbm-launcher">${esc(title)}</button>

    <div class="gbm-panel">
      <div class="gbm-header">
        <div>${esc(title)}</div>
        <div class="gbm-close" style="cursor:pointer;">✕</div>
      </div>

      <div class="gbm-messages"></div>

      <div class="gbm-input-row">
        <input class="gbm-input" placeholder="Ask something..." />
        <button class="gbm-send">Send</button>
      </div>
    </div>
  `;

  const launcher = root.querySelector('.gbm-launcher');
  const panel = root.querySelector('.gbm-panel');
  const messages = root.querySelector('.gbm-messages');
  const input = root.querySelector('.gbm-input');
  const send = root.querySelector('.gbm-send');
  const closeBtn = root.querySelector('.gbm-close');

  launcher.onclick = () => {
    panel.style.display = 'flex';
    launcher.style.display = 'none';
    input.focus();
  };

  closeBtn.onclick = () => {
    panel.style.display = 'none';
    launcher.style.display = 'block';
  };

  function renderVisual(data) {
    lastData = data;

    const wrap = document.createElement('div');

    wrap.innerHTML = `
      <div>${esc(data.visual_summary || data.answer)}</div>
      <div class="gbm-toggle">DIVE DEEPER WITH TEXT ONLY</div>
    `;

    wrap.querySelector('.gbm-toggle').onclick = () => {
      mode = 'text';
      messages.innerHTML = '';
      renderText(data);
    };

    (data.cards || []).forEach(c => {
      const el = document.createElement('div');
      el.className = 'gbm-card';
      el.innerHTML = `
        <img src="${abs(c.image || '/assets/thumbs/fallback-article.jpg')}">
        <div class="gbm-card-body">
          <a href="${abs(c.url)}" target="_blank">${esc(c.title)}</a>
        </div>
      `;
      messages.appendChild(el);
    });

    (data.magazines || []).forEach(m => {
      const el = document.createElement('div');
      el.className = 'gbm-card';
      el.innerHTML = `
        <img src="${abs(m.cover || '/assets/covers/fallback-magazine.jpg')}">
        <div class="gbm-card-body">
          <a href="${abs(m.url)}" target="_blank">${esc(m.title)}</a>
        </div>
      `;
      messages.appendChild(el);
    });

    messages.appendChild(wrap);
  }

  function renderText(data) {
    const wrap = document.createElement('div');

    wrap.innerHTML = `
      <div>${esc(data.text_only_answer)}</div>
      <div class="gbm-toggle">RETURN TO VISUAL MODE</div>
    `;

    wrap.querySelector('.gbm-toggle').onclick = () => {
      mode = 'visual';
      messages.innerHTML = '';
      renderVisual(data);
    };

    messages.appendChild(wrap);
  }

  async function ask() {
    const q = input.value.trim();
    if (!q) return;

    messages.innerHTML = `<div>Thinking...</div>`;

    const res = await fetch(apiBase + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });

    const data = await res.json();
    messages.innerHTML = '';

    if (mode === 'visual') renderVisual(data);
    else renderText(data);
  }

  send.onclick = ask;

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  });

})();

(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || '').replace(/\/$/, '');
  const title = currentScript?.dataset.chatbotTitle || 'GBM Deep Think';

  if (!apiBase) {
    console.error('Missing data-api-base');
    return;
  }

  const root = document.createElement('div');
  document.body.appendChild(root);

  let mode = 'visual';

  function abs(url) {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    return apiBase + url;
  }

  root.innerHTML = `
  <style>
    .gbm-launcher {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #006f63;
      color: white;
      padding: 14px 18px;
      border-radius: 999px;
      font-weight: 700;
      cursor: pointer;
      z-index: 999999;
      box-shadow: 0 8px 20px rgba(0,0,0,0.2);
    }

    .gbm-panel {
      position: fixed;
      bottom: 80px;
      right: 20px;
      width: 900px;
      max-width: calc(100vw - 30px);
      height: 720px;
      background: white;
      border-radius: 16px;
      display: none;
      flex-direction: column;
      overflow: hidden;
      z-index: 999998;
      box-shadow: 0 20px 60px rgba(0,0,0,0.25);
    }

    .gbm-header {
      background: linear-gradient(135deg,#007565,#005447);
      color: white;
      padding: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .gbm-title {
      font-size: 20px;
      font-weight: 800;
    }

    .gbm-close {
      font-size: 28px;
      cursor: pointer;
      background: none;
      border: none;
      color: white;
    }

    .gbm-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      background: #f7fafc;
    }

    .gbm-answer {
      margin-bottom: 16px;
      line-height: 1.5;
    }

    .gbm-insights {
      display: grid;
      grid-template-columns: repeat(4,1fr);
      gap: 10px;
      margin: 15px 0;
    }

    .gbm-insight {
      background: white;
      border: 1px solid #ddd;
      border-radius: 10px;
      padding: 10px;
      font-size: 12px;
      text-align: center;
    }

    .gbm-cards {
      display: grid;
      grid-template-columns: repeat(4,1fr);
      gap: 14px;
    }

    .gbm-card {
      border: 1px solid #ddd;
      border-radius: 12px;
      overflow: hidden;
      background: white;
    }

    .gbm-card img {
      width: 100%;
      height: 120px;
      object-fit: cover;
    }

    .gbm-card-body {
      padding: 10px;
    }

    .gbm-card-title {
      font-weight: 700;
      font-size: 13px;
      margin-bottom: 6px;
    }

    .gbm-card a {
      font-size: 12px;
      color: #007565;
      font-weight: 700;
      text-decoration: none;
    }

    .gbm-input-row {
      display: flex;
      padding: 12px;
      border-top: 1px solid #eee;
      gap: 8px;
    }

    .gbm-input {
      flex: 1;
      padding: 12px;
      border-radius: 999px;
      border: 1px solid #ccc;
    }

    .gbm-send {
      background: #007565;
      color: white;
      border: none;
      padding: 0 18px;
      border-radius: 999px;
      cursor: pointer;
      font-weight: 700;
    }

    .gbm-thinking {
      font-weight: 700;
      color: #007565;
    }
  </style>

  <div class="gbm-launcher">${title}</div>

  <div class="gbm-panel">
    <div class="gbm-header">
      <div class="gbm-title">${title}</div>
      <button class="gbm-close">×</button>
    </div>

    <div class="gbm-messages"></div>

    <div class="gbm-input-row">
      <input class="gbm-input" placeholder="Ask anything..." />
      <button class="gbm-send">SEND</button>
    </div>
  </div>
  `;

  const launcher = root.querySelector('.gbm-launcher');
  const panel = root.querySelector('.gbm-panel');
  const messages = root.querySelector('.gbm-messages');
  const input = root.querySelector('.gbm-input');
  const send = root.querySelector('.gbm-send');

  launcher.onclick = () => panel.style.display = 'flex';
  root.querySelector('.gbm-close').onclick = () => panel.style.display = 'none';

  function render(data) {
    messages.innerHTML = `
      <div class="gbm-answer">${data.answer || ''}</div>
    `;

    if (data.key_insights) {
      const insights = document.createElement('div');
      insights.className = 'gbm-insights';

      data.key_insights.slice(0,4).forEach(i => {
        insights.innerHTML += `
          <div class="gbm-insight">
            <strong>${i.title}</strong><br>
            ${i.text}
          </div>
        `;
      });

      messages.appendChild(insights);
    }

    if (data.cards && data.cards.length) {
      const cards = document.createElement('div');
      cards.className = 'gbm-cards';

      data.cards.slice(0,4).forEach(c => {
        cards.innerHTML += `
          <div class="gbm-card">
            <img src="${abs(c.image)}" onerror="this.src='${apiBase}/assets/thumbs/fallback-article.jpg'">
            <div class="gbm-card-body">
              <div class="gbm-card-title">${c.title}</div>
              <a href="${abs(c.url)}" target="_blank">Read Article →</a>
            </div>
          </div>
        `;
      });

      messages.appendChild(cards);
    }
  }

  async function ask() {
    const q = input.value.trim();
    if (!q) return;

    messages.innerHTML = `<div class="gbm-thinking">Thinking...</div>`;

    const res = await fetch(apiBase + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });

    const data = await res.json();
    render(data);
  }

  send.onclick = ask;
  input.addEventListener('keydown', e => e.key === 'Enter' && ask());
})();(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || '').replace(/\/$/, '');
  const title = currentScript?.dataset.chatbotTitle || 'GBM Deep Think';

  if (!apiBase) {
    console.error('Missing data-api-base');
    return;
  }

  const root = document.createElement('div');
  document.body.appendChild(root);

  let mode = 'visual';
  let lastData = null;

  function abs(url) {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    return apiBase + url;
  }

  root.innerHTML = `
  <style>
    .gbm-launcher {
      position:fixed !important;
      bottom:20px;
      right:20px;
      z-index:999999;
      background:#006f63;
      color:#fff;
      padding:14px 18px;
      border-radius:999px;
      font-weight:bold;
      cursor:pointer;
    }

    .gbm-panel {
      position:fixed;
      bottom:80px;
      right:20px;
      width:720px;
      max-width:95vw;
      height:720px;
      max-height:90vh;
      background:#fff;
      border-radius:18px;
      display:none;
      flex-direction:column;
      overflow:hidden;
      z-index:999998;
      box-shadow:0 20px 60px rgba(0,0,0,.25);
    }

    .gbm-header {
      background:linear-gradient(135deg,#007565,#005447);
      color:#fff;
      padding:18px;
      display:flex;
      justify-content:space-between;
      font-size:22px;
      font-weight:900;
    }

    .gbm-messages {
      flex:1;
      overflow:auto;
      padding:20px;
      background:#f8fafc;
    }

    .gbm-input-row {
      display:flex;
      padding:14px;
      gap:10px;
      border-top:1px solid #ddd;
    }

    .gbm-input {
      flex:1;
      border-radius:999px;
      padding:12px;
      border:1px solid #ccc;
    }

    .gbm-send {
      background:#007565;
      color:#fff;
      border:none;
      border-radius:50%;
      width:48px;
      height:48px;
      cursor:pointer;
    }

    .gbm-card {
      border:1px solid #ddd;
      border-radius:12px;
      overflow:hidden;
      margin-top:14px;
      background:#fff;
    }

    .gbm-card img {
      width:100%;
      height:120px;
      object-fit:cover;
    }

    .gbm-card-body {
      padding:10px;
    }

    .gbm-toggle {
      margin:10px 0;
      font-weight:bold;
      color:#007565;
      cursor:pointer;
    }

    .gbm-thinking {
      font-weight:bold;
      color:#007565;
    }
  </style>

  <button class="gbm-launcher">${title}</button>

  <div class="gbm-panel">
    <div class="gbm-header">
      ${title}
      <span class="gbm-close" style="cursor:pointer;">✕</span>
    </div>

    <div class="gbm-messages"></div>

    <div class="gbm-input-row">
      <input class="gbm-input" placeholder="Ask something..." />
      <button class="gbm-send">➤</button>
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
  };

  closeBtn.onclick = () => {
    panel.style.display = 'none';
    launcher.style.display = 'block';
  };

  function renderVisual(data) {
    lastData = data;

    const wrap = document.createElement('div');

    wrap.innerHTML = `
      <div>${data.visual_summary || data.answer}</div>
      <div class="gbm-toggle">DIVE DEEPER WITH TEXT ONLY</div>
    `;

    wrap.querySelector('.gbm-toggle').onclick = () => {
      mode = 'text';
      messages.innerHTML = '';
      renderText(data);
    };

    // BLOG CARDS
    (data.cards || []).forEach(c => {
      const el = document.createElement('div');
      el.className = 'gbm-card';
      el.innerHTML = `
        <img src="${abs(c.image || '/assets/thumbs/fallback-article.jpg')}">
        <div class="gbm-card-body">
          <a href="${abs(c.url)}" target="_blank">${c.title}</a>
        </div>
      `;
      wrap.appendChild(el);
    });

    // MAGAZINE CARDS
    (data.magazines || []).forEach(m => {
      const el = document.createElement('div');
      el.className = 'gbm-card';
      el.innerHTML = `
        <img src="${abs(m.cover || '/assets/covers/fallback-magazine.jpg')}">
        <div class="gbm-card-body">
          <a href="${abs(m.url)}" target="_blank">${m.title}</a>
        </div>
      `;
      wrap.appendChild(el);
    });

    messages.appendChild(wrap);
  }

  function renderText(data) {
    const wrap = document.createElement('div');

    wrap.innerHTML = `
      <div>${data.text_only_answer}</div>
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

    messages.innerHTML = `<div class="gbm-thinking">Thinking...</div>`;

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
    if (e.key === 'Enter') {
      e.preventDefault();
      ask();
    }
  });

})();

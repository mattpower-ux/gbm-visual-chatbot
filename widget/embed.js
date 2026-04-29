(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || '').replace(/\/$/, '');
  const title = currentScript?.dataset.chatbotTitle || 'Ask Green Builder';

  if (!apiBase) {
    console.error('Missing data-api-base');
    return;
  }

  const root = document.createElement('div');
  document.body.appendChild(root);

  let mode = 'visual';

  root.innerHTML = `
    <style>
      .gbm-launcher { position:fixed; bottom:20px; right:20px; background:#0f766e; color:#fff; padding:12px 16px; border-radius:999px; cursor:pointer; }
      .gbm-panel { position:fixed; bottom:80px; right:20px; width:420px; height:620px; background:#fff; border-radius:14px; display:none; flex-direction:column; overflow:hidden; }
      .gbm-header { background:#0f766e; color:#fff; padding:12px; font-weight:bold; }
      .gbm-messages { flex:1; overflow:auto; padding:10px; background:#f1f5f9; }
      .gbm-input-row { display:flex; gap:6px; padding:10px; }
      .gbm-input { flex:1; padding:8px; }
      .gbm-send { background:#0f766e; color:white; border:none; padding:8px; }
      .gbm-card { border:1px solid #ddd; margin-top:10px; border-radius:10px; overflow:hidden; }
      .gbm-card img { width:100%; height:120px; object-fit:cover; }
      .gbm-card-body { padding:8px; }
      .gbm-toggle { font-size:12px; color:#0f766e; cursor:pointer; margin-bottom:8px; }
    </style>

    <button class="gbm-launcher">${title}</button>

    <div class="gbm-panel">
      <div class="gbm-header">${title}</div>
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

  launcher.onclick = () => {
    panel.style.display = panel.style.display === 'flex' ? 'none' : 'flex';
  };

  function renderVisual(data) {
    const wrap = document.createElement('div');

    wrap.innerHTML = `
      <div>${data.visual_summary || data.answer}</div>
      <div class="gbm-toggle">TEXT ONLY VERSION</div>
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
        <img src="${c.image || ''}">
        <div class="gbm-card-body">
          <a href="${apiBase + c.url}" target="_blank">${c.title}</a>
        </div>
      `;
      wrap.appendChild(el);
    });

    (data.magazines || []).forEach(m => {
      const el = document.createElement('div');
      el.className = 'gbm-card';
      el.innerHTML = `
        <img src="${apiBase + m.cover}">
        <div class="gbm-card-body">
          <a href="${apiBase + m.url}" target="_blank">${m.title}</a>
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
  input.addEventListener('keydown', e => e.key === 'Enter' && ask());
})();

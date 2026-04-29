(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || '').replace(/\/$/, '');
  const title = currentScript?.dataset.chatbotTitle || 'Ask Green Builder';

  const root = document.createElement('div');
  root.id = 'gbm-chatbot-root';
  document.body.appendChild(root);

  let mode = 'visual';

  root.innerHTML = `
    <style>
      #gbm-chatbot-root * { box-sizing: border-box; font-family: Arial, sans-serif; }

      .gbm-launcher {
        position: fixed; bottom: 20px; right: 20px;
        background: #0f766e; color: #fff;
        border-radius: 999px; padding: 14px 18px;
        cursor: pointer;
      }

      .gbm-panel {
        position: fixed; bottom: 80px; right: 20px;
        width: 400px; height: 620px;
        background: #fff; border-radius: 16px;
        display: none; flex-direction: column;
        overflow: hidden;
      }

      .gbm-header { background: #0f766e; color: #fff; padding: 14px; font-weight: bold; }

      .gbm-messages { flex: 1; overflow-y: auto; padding: 12px; background: #f8fafc; }

      .gbm-msg { margin-bottom: 12px; }

      .gbm-user { text-align: right; }

      .gbm-bot { background: #fff; border: 1px solid #ddd; padding: 10px; border-radius: 12px; }

      .gbm-summary { font-weight: 500; margin-bottom: 8px; }

      .gbm-toggle {
        font-size: 12px;
        color: #0f766e;
        cursor: pointer;
        margin-bottom: 8px;
      }

      .gbm-insight {
        background: #eef6f5;
        padding: 8px;
        border-radius: 8px;
        margin-bottom: 6px;
        font-size: 13px;
      }

      .gbm-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        margin-bottom: 10px;
        overflow: hidden;
        background: white;
      }

      .gbm-card img {
        width: 100%;
        height: 120px;
        object-fit: cover;
      }

      .gbm-card-body {
        padding: 8px;
        font-size: 13px;
      }

      .gbm-card a {
        color: #0f766e;
        text-decoration: none;
        font-weight: bold;
      }

      .gbm-input-row { display: flex; padding: 10px; gap: 6px; }

      .gbm-input { flex: 1; padding: 8px; }

      .gbm-send { background: #0f766e; color: white; border: none; padding: 8px 10px; }
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
    wrap.className = 'gbm-bot';

    // Summary
    const summary = document.createElement('div');
    summary.className = 'gbm-summary';
    summary.textContent = data.visual_summary;
    wrap.appendChild(summary);

    // Toggle
    const toggle = document.createElement('div');
    toggle.className = 'gbm-toggle';
    toggle.textContent = 'TEXT ONLY VERSION';
    toggle.onclick = () => {
      mode = 'text';
      messages.innerHTML = '';
      renderText(data);
    };
    wrap.appendChild(toggle);

    // Insights
    (data.key_insights || []).forEach(i => {
      const el = document.createElement('div');
      el.className = 'gbm-insight';
      el.textContent = i.text;
      wrap.appendChild(el);
    });

    // Blog cards
    (data.cards || []).forEach(c => {
      const card = document.createElement('div');
      card.className = 'gbm-card';
      card.innerHTML = `
        <img src="${c.image}">
        <div class="gbm-card-body">
          <a href="${c.url}" target="_blank">${c.title}</a>
        </div>
      `;
      wrap.appendChild(card);
    });

    // Magazine cards
    (data.magazines || []).forEach(m => {
      const card = document.createElement('div');
      card.className = 'gbm-card';
      card.innerHTML = `
        <img src="${m.cover}">
        <div class="gbm-card-body">
          <a href="${m.url}" target="_blank">${m.title}</a>
        </div>
      `;
      wrap.appendChild(card);
    });

    messages.appendChild(wrap);
  }

  function renderText(data) {
    const wrap = document.createElement('div');
    wrap.className = 'gbm-bot';

    wrap.textContent = data.text_only_answer;

    const toggle = document.createElement('div');
    toggle.className = 'gbm-toggle';
    toggle.textContent = 'RETURN TO VISUAL MODE';
    toggle.onclick = () => {
      mode = 'visual';
      messages.innerHTML = '';
      renderVisual(data);
    };

    wrap.appendChild(toggle);

    messages.appendChild(wrap);
  }

  function addUser(text) {
    const el = document.createElement('div');
    el.className = 'gb

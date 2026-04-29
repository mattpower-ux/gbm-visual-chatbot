(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || '').replace(/\/$/, '');
  const title = currentScript?.dataset.chatbotTitle || 'Solar Snoop';
  const subtitle = currentScript?.dataset.chatbotSubtitle || 'Plan your solar + storage DIY dream';

  if (!apiBase) {
    console.error('Missing data-api-base');
    return;
  }

  const root = document.createElement('div');
  root.id = 'gbm-visual-chat-root';
  document.body.appendChild(root);

  let mode = 'visual';
  let lastData = null;

  function abs(url) {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    if (url.startsWith('/')) return apiBase + url;
    return url;
  }

  function esc(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  root.innerHTML = `
    <style>
      #gbm-visual-chat-root * { box-sizing: border-box; font-family: Inter, Arial, sans-serif; }

      .gbm-launcher {
        position: fixed; right: 22px; bottom: 22px; z-index: 999999;
        background: #006f63; color: #fff; border: none; border-radius: 999px;
        padding: 14px 20px; font-size: 15px; font-weight: 800; cursor: pointer;
        box-shadow: 0 12px 32px rgba(0,0,0,.25);
      }

      .gbm-panel {
        position: fixed; right: 20px; bottom: 84px; z-index: 999999;
        width: 760px; max-width: calc(100vw - 28px);
        height: 760px; max-height: calc(100vh - 110px);
        display: none; flex-direction: column;
        background: #fff; border-radius: 18px; overflow: hidden;
        box-shadow: 0 20px 60px rgba(0,0,0,.25);
        border: 1px solid rgba(0,0,0,.08);
      }

      .gbm-header {
        background: linear-gradient(135deg, #007565, #005447);
        color: white; padding: 18px 22px; display: flex; align-items: center; justify-content: space-between;
      }

      .gbm-brand { display: flex; align-items: center; gap: 14px; }
      .gbm-avatar {
        width: 58px; height: 58px; border-radius: 50%;
        background: #f5c84c; display: grid; place-items: center;
        font-size: 30px; border: 3px solid rgba(255,255,255,.7);
      }
      .gbm-title { font-size: 25px; font-weight: 900; line-height: 1.05; }
      .gbm-subtitle { font-size: 14px; opacity: .95; margin-top: 4px; }
      .gbm-close { background: transparent; color: white; border: 0; font-size: 34px; cursor: pointer; }

      .gbm-messages {
        flex: 1; overflow-y: auto; padding: 20px 24px;
        background: linear-gradient(#ffffff, #f8fafc);
      }

      .gbm-user-row { display: flex; justify-content: flex-end; margin-bottom: 18px; }
      .gbm-user-bubble {
        background: #e9f3f1; color: #1f2937; border-radius: 18px;
        padding: 12px 16px; max-width: 70%; font-size: 15px;
        border: 1px solid #d5e6e2;
      }

      .gbm-answer-row { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 18px; }
      .gbm-small-avatar {
        width: 42px; height: 42px; border-radius: 50%; background: #f5c84c;
        display: grid; place-items: center; flex: 0 0 auto; font-size: 22px;
        border: 2px solid #007565;
      }

      .gbm-answer { flex: 1; color: #172033; font-size: 15px; line-height: 1.5; }
      .gbm-summary { margin-bottom: 8px; }
      .gbm-text-toggle {
        border: 1px solid #007565; color: #007565; background: white;
        border-radius: 999px; padding: 6px 11px; font-size: 11px;
        font-weight: 800; cursor: pointer; margin: 4px 0 12px;
      }

      .gbm-section-title {
        font-size: 17px; font-weight: 900; color: #172033;
        margin: 18px 0 10px; padding-top: 12px; border-top: 1px solid #e5e7eb;
      }

      .gbm-insights-box {
        border: 1px solid #dbe5e2; border-radius: 16px;
        padding: 14px; background: #fbfefd; margin: 14px 0 16px;
      }

      .gbm-insights-title {
        font-size: 17px; font-weight: 900; margin-bottom: 12px; color: #172033;
      }

      .gbm-insight-grid {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
      }

      .gbm-insight {
        text-align: center; padding: 10px 8px; border-right: 1px solid #dbe5e2;
      }

      .gbm-insight:last-child { border-right: none; }

      .gbm-icon {
        width: 46px; height: 46px; border-radius: 50%;
        display: grid; place-items: center; margin: 0 auto 8px;
        background: #007565; color: white; font-size: 22px;
      }

      .gbm-insight-title { font-weight: 900; font-size: 13px; color: #143d39; margin-bottom: 5px; }
      .gbm-insight-text { font-size: 12px; line-height: 1.35; color: #333; }

      .gbm-card-row {
        display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px;
      }

      .gbm-card {
        border: 1px solid #dfe5e8; border-radius: 12px; overflow: hidden;
        background: white; box-shadow: 0 4px 12px rgba(0,0,0,.06);
      }

      .gbm-card img {
        width: 100%; height: 105px; object-fit: cover; display: block;
        background: #e5e7eb;
      }

      .gbm-card-body { padding: 10px; }
      .gbm-tag {
        display: inline-block; font-size: 10px; font-weight: 900;
        color: #007565; background: #e4f4f1; border: 1px solid #b9ded8;
        border-radius: 999px; padding: 3px 7px; margin-bottom: 7px;
        text-transform: uppercase;
      }

      .gbm-card-title { font-size: 13px; font-weight: 900; line-height: 1.25; color: #111827; margin-bottom: 6px; }
      .gbm-card-source { color: #007565; font-size: 12px; font-weight: 800; margin-bottom: 8px; }
      .gbm-card-link {
        display: block; border-top: 1px solid #edf0f2; padding-top: 8px;
        color: #007565; font-size: 12px; font-weight: 900; text-decoration: none;
      }

      .gbm-mag-card {
        display: grid; grid-template-columns: 110px 1fr 150px; gap: 16px;
        align-items: center; border: 1px solid #dfe5e8; border-radius: 16px;
        background: white; padding: 12px; box-shadow: 0 4px 12px rgba(0,0,0,.05);
      }

      .gbm-mag-card img {
        width: 100px; height: 120px; object-fit: cover; border-radius: 8px;
        background: #e5e7eb;
      }

      .gbm-mag-title { font-weight: 900; font-size: 15px; color: #111827; margin-bottom: 5px; }
      .gbm-mag-meta { color: #007565; font-weight: 800; font-size: 13px; margin-bottom: 6px; }
      .gbm-mag-excerpt { color: #334155; font-size: 12px; line-height: 1.35; }

      .gbm-mag-button {
        text-align: center; border: 1px solid #007565; color: #007565;
        border-radius: 12px; padding: 12px 10px; text-decoration: none;
        font-weight: 900; font-size: 13px;
      }

      .gbm-input-row {
        padding: 14px 20px; background: #fff; border-top: 1px solid #e5e7eb;
        display: flex; gap: 10px; align-items: center;
      }

      .gbm-input {
        flex: 1; border: 1px solid #d1d5db; border-radius: 999px;
        padding: 13px 16px; font-size: 14px; outline: none;
      }

      .gbm-send {
        width: 48px; height: 48px; border-radius: 50%; border: none;
        background: #007565; color: white; font-size: 22px; cursor: pointer;
        display: grid; place-items: center;
      }

      .gbm-disclaimer {
        text-align: center; font-size: 11px; color: #6b7280; padding-bottom: 8px;
      }

      .gbm-text-only {
        white-space: pre-wrap; background: white; border: 1px solid #dfe5e8;
        border-radius: 14px; padding: 14px; line-height: 1.55; font-size: 14px;
      }

      .gbm-sources { margin-top: 14px; border-top: 1px solid #e5e7eb; padding-top: 10px; }
      .gbm-sources a { display: block; color: #007565; font-weight: 800; margin-top: 6px; text-decoration: none; }

      @media (max-width: 760px) {
        .gbm-panel { width: calc(100vw - 24px); height: calc(100vh - 96px); right: 12px; bottom: 76px; }
        .gbm-insight-grid { grid-template-columns: 1fr; }
        .gbm-insight { border-right: none; border-bottom: 1px solid #dbe5e2; }
        .gbm-card-row { grid-template-columns: 1fr; }
        .gbm-mag-card { grid-template-columns: 80px 1fr; }
        .gbm-mag-button { grid-column: 1 / -1; }
      }
    </style>

    <button class="gbm-launcher">${esc(title)}</button>

    <div class="gbm-panel">
      <div class="gbm-header">
        <div class="gbm-brand">
          <div class="gbm-avatar">🔎</div>
          <div>
            <div class="gbm-title">${esc(title)}</div>
            <div class="gbm-subtitle">${esc(subtitle)}</div>
          </div>
        </div>
        <button class="gbm-close">×</button>
      </div>

      <div class="gbm-messages">
        <div class="gbm-answer-row">
          <div class="gbm-small-avatar">🔎</div>
          <div class="gbm-answer">
            Ask me about Green Builder articles, magazine archives, resilience, insulation, solar, electrification, or sustainable building.
          </div>
        </div>
      </div>

      <div class="gbm-input-row">
        <input class="gbm-input" placeholder="Ask Green Builder about insulation, solar, batteries, or resilient homes..." />
        <button class="gbm-send">➤</button>
      </div>
      <div class="gbm-disclaimer">Solar Snoop can make mistakes. Check important info.</div>
    </div>
  `;

  const launcher = root.querySelector('.gbm-launcher');
  const closeBtn = root.querySelector('.gbm-close');
  const panel = root.querySelector('.gbm-panel');
  const messages = root.querySelector('.gbm-messages');
  const input = root.querySelector('.gbm-input');
  const send = root.querySelector('.gbm-send');

  launcher.onclick = () => {
    panel.style.display = 'flex';
    launcher.style.display = 'none';
    setTimeout(() => input.focus(), 50);
  };

  closeBtn.onclick = () => {
    panel.style.display = 'none';
    launcher.style.display = 'block';
  };

  function clearMessages() {
    messages.innerHTML = '';
  }

  function addUserMessage(q) {
    const row = document.createElement('div');
    row.className = 'gbm-user-row';
    row.innerHTML = `<div class="gbm-user-bubble">${esc(q)}</div>`;
    messages.appendChild(row);
  }

  function imageFallback(img, kind) {
    img.onerror = null;
    img.src = kind === 'mag'
      ? abs('/assets/covers/fallback-magazine.jpg')
      : abs('/assets/thumbs/fallback-article.jpg');
  }

  function renderVisual(data) {
    lastData = data;

    const row = document.createElement('div');
    row.className = 'gbm-answer-row';

    const summary = esc(data.visual_summary || data.answer || 'No answer returned.');

    row.innerHTML = `
      <div class="gbm-small-avatar">🔎</div>
      <div class="gbm-answer">
        <div class="gbm-summary">${summary}</div>
        <button class="gbm-text-toggle">TEXT ONLY VERSION</button>
      </div>
    `;

    const answerBox = row.querySelector('.gbm-answer');
    row.querySelector('.gbm-text-toggle').onclick = () => {
      mode = 'text';
      clearMessages();
      if (lastData) renderText(lastData);
    };

    const insights = data.key_insights || [];
    if (insights.length) {
      const box = document.createElement('div');
      box.className = 'gbm-insights-box';
      box.innerHTML = `<div class="gbm-insights-title">💡 Key Insights</div>`;

      const grid = document.createElement('div');
      grid.className = 'gbm-insight-grid';

      insights.slice(0, 6).forEach((i, idx) => {
        const icon = idx === 0 ? '🏠' : idx === 1 ? '🛠️' : idx === 2 ? '💧' : '✓';
        const el = document.createElement('div');
        el.className = 'gbm-insight';
        el.innerHTML = `
          <div class="gbm-icon">${icon}</div>
          <div class="gbm-insight-title">${esc(i.title || 'Insight')}</div>
          <div class="gbm-insight-text">${esc(i.text || '')}</div>
        `;
        grid.appendChild(el);
      });

      box.appendChild(grid);
      answerBox.appendChild(box);
    }

    const cards = data.cards || [];
    if (cards.length) {
      const label = document.createElement('div');
      label.className = 'gbm-section-title';
      label.textContent = '📖 Recommended Reading';
      answerBox.appendChild(label);

      const cardRow = document.createElement('div');
      cardRow.className = 'gbm-card-row';

      cards.slice(0, 6).forEach(c => {
        const card = document.createElement('div');
        card.className = 'gbm-card';
        card.innerHTML = `
          <img src="${abs(c.image || '/assets/thumbs/fallback-article.jpg')}" alt="">
          <div class="gbm-card-body">
            <div class="gbm-tag">${esc(c.category || 'Article')}</div>
            <div class="gbm-card-title">${esc(c.title || 'Green Builder article')}</div>
            <div class="gbm-card-source">${esc(c.source || 'Green Builder')}</div>
            <a class="gbm-card-link" href="${abs(c.url)}" target="_blank" rel="noopener">Read Article ↗</a>
          </div>
        `;
        card.querySelector('img').onerror = function () { imageFallback(this, 'article'); };
        cardRow.appendChild(card);
      });

      answerBox.appendChild(cardRow);
    }

    const magazines = data.magazines || [];
    if (magazines.length) {
      const label = document.createElement('div');
      label.className = 'gbm-section-title';
      label.textContent = '📖 From the Magazine';
      answerBox.appendChild(label);

      const m = magazines[0];
      const mag = document.createElement('div');
      mag.className = 'gbm-mag-card';
      mag.innerHTML = `
        <img src="${abs(m.cover || '/assets/covers/fallback-magazine.jpg')}" alt="">
        <div>
          <div class="gbm-mag-title">${esc(m.title || 'Green Builder Magazine')}</div>
          <div class="gbm-mag-meta">${esc(m.issue || 'Magazine archive')}</div>
          <div class="gbm-mag-excerpt">${esc(m.excerpt || '')}</div>
        </div>
        <a class="gbm-mag-button" href="${abs(m.url)}" target="_blank" rel="noopener">View Magazine ↗</a>
      `;
      mag.querySelector('img').onerror = function () { imageFallback(this, 'mag'); };
      answerBox.appendChild(mag);
    }

    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
  }

  function renderText(data) {
    lastData = data;

    const row = document.createElement('div');
    row.className = 'gbm-answer-row';

    const sources = data.sources || [];
    const sourceHtml = sources.length
      ? `<div class="gbm-sources"><strong>Sources:</strong>${sources.map(s =>
          `<a href="${abs(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.url)}</a>`
        ).join('')}</div>`
      : '';

    row.innerHTML = `
      <div class="gbm-small-avatar">🔎</div>
      <div class="gbm-answer">
        <button class="gbm-text-toggle">RETURN TO VISUAL MODE</button>
        <div class="gbm-text-only">${esc(data.text_only_answer || data.answer || '')}${sourceHtml}</div>
      </div>
    `;

    row.querySelector('.gbm-text-toggle').onclick = () => {
      mode = 'visual';
      clearMessages();
      if (lastData) renderVisual(lastData);
    };

    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
  }

  async function ask() {
    const q = input.value.trim();
    if (!q) return;

    clearMessages();
    addUserMessage(q);
    input.value = '';
    send.disabled = true;

    const loading = document.createElement('div');
    loading.className = 'gbm-answer-row';
    loading.innerHTML = `<div class="gbm-small-avatar">🔎</div><div class="gbm-answer">Thinking...</div>`;
    messages.appendChild(loading);

    try {
      const res = await fetch(apiBase + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: q,
          session_id: 'web-' + Date.now(),
          page_url: window.location.href,
          referrer: document.referrer || '',
          user_agent: navigator.userAgent || ''
        })
      });

      const data = await res.json();
      loading.remove();

      if (mode === 'text') renderText(data);
      else renderVisual(data);
    } catch (e) {
      loading.remove();
      renderVisual({
        visual_summary: 'Sorry, the Green Builder assistant is temporarily unavailable.',
        answer: 'Sorry, the Green Builder assistant is temporarily unavailable.',
        key_insights: [],
        cards: [],
        magazines: [],
        sources: [],
        text_only_answer: 'Sorry, the Green Builder assistant is temporarily unavailable.'
      });
    } finally {
      send.disabled = false;
      input.focus();
    }
  }

  send.onclick = ask;
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') ask();
  });
})();

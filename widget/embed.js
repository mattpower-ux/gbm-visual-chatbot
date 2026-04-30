(async function () {
  const API = window.GBM_CHATBOT_API || "https://gbm-visual-chatbot.onrender.com";

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html) e.innerHTML = html;
    return e;
  }

  function renderCards(cards) {
    if (!cards || !cards.length) return "";

    return `
      <div class="gbm-cards">
        ${cards.map(c => `
          <div class="gbm-card">
            <img src="${c.image}" class="gbm-card-img"/>
            <div class="gbm-card-body">
              <div class="gbm-card-title">${c.title}</div>
              <a href="${c.url}" target="_blank" class="gbm-read">Read Article</a>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderMagazines(mags) {
    if (!mags || !mags.length) return "";

    const m = mags[0]; // show top match

    return `
      <div class="gbm-mag-section">
        <div class="gbm-mag-header">From the Magazine</div>
        <div class="gbm-mag-card">
          <img src="${m.cover}" class="gbm-mag-cover"/>
          <div class="gbm-mag-body">
            <div class="gbm-mag-title">${m.title}</div>
            <div class="gbm-mag-meta">${m.source} • ${m.issue}</div>
            <div class="gbm-mag-desc">${m.excerpt || ""}</div>
          </div>
          <a href="${m.url}" target="_blank" class="gbm-mag-btn">
            View Magazine
          </a>
        </div>
      </div>
    `;
  }

  function renderTextLinks(cards, mags) {
    let links = [];

    if (cards) {
      links.push(...cards.map(c =>
        `<a href="${c.url}" target="_blank">${c.title}</a>`
      ));
    }

    if (mags) {
      links.push(...mags.map(m =>
        `<a href="${m.url}" target="_blank">${m.title}</a>`
      ));
    }

    return `
      <div class="gbm-text-links">
        <strong>Sources:</strong><br/>
        ${links.join("<br/>")}
      </div>
    `;
  }

  async function send(q) {
    const res = await fetch(`${API}/chat`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: q, session_id: "web"})
    });
    return res.json();
  }

  function buildUI() {
    const wrap = el("div", "gbm-wrap");
    const log = el("div", "gbm-log");
    const input = el("input", "gbm-input");
    const btn = el("button", "gbm-send", "Send");

    input.placeholder = "Ask about building, energy, resilience…";

    btn.onclick = async () => {
      const q = input.value.trim();
      if (!q) return;

      const bubble = el("div", "gbm-q", q);
      log.appendChild(bubble);

      const data = await send(q);

      const ans = el("div", "gbm-a");
      ans.innerHTML = `
        <div class="gbm-text">${data.answer}</div>
        ${renderCards(data.cards)}
        ${renderMagazines(data.magazines)}
      `;

      log.appendChild(ans);

      input.value = "";
      log.scrollTop = log.scrollHeight;
    };

    input.addEventListener("keypress", e => {
      if (e.key === "Enter") btn.click();
    });

    wrap.appendChild(log);

    const bar = el("div", "gbm-bar");
    bar.appendChild(input);
    bar.appendChild(btn);
    wrap.appendChild(bar);

    document.body.appendChild(wrap);
  }

  // TEXT-ONLY MODE SUPPORT
  window.GBM_render_text_only = function (data, container) {
    container.innerHTML = `
      <div class="gbm-text-only">
        <div>${data.answer}</div>
        ${renderTextLinks(data.cards, data.magazines)}
      </div>
    `;
  };

  buildUI();
})();

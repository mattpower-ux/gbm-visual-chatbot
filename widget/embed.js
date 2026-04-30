(function () {

  const API = "https://gbm-visual-chatbot.onrender.com";

  function abs(u) {
    if (!u) return "";
    if (u.startsWith("http")) return u;
    return API + u;
  }

  function el(tag, cls) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    return e;
  }

  // -------------------------
  // CARDS (UNCHANGED)
  // -------------------------
  function renderCards(cards) {
    if (!cards || !cards.length) return "";

    return `
      <div class="gbm-cards">
        ${cards.map(c => `
          <div class="gbm-card">
            <img src="${abs(c.image)}"
                 onerror="this.src='${API}/assets/thumbs/fallback-article.jpg'">
            <div class="gbm-card-body">
              <div class="gbm-card-title">${c.title}</div>
              <a href="${c.url}" target="_blank">Read →</a>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  // -------------------------
  // ✅ FIXED MAGAZINE BLOCK
  // -------------------------
  function renderMagazines(mags) {
    if (!mags || !mags.length) return "";

    const m = mags[0];

    return `
      <div class="gbm-mag-section">
        <div class="gbm-mag-header">From the Magazine</div>

        <div class="gbm-mag-card">
          <img class="gbm-mag-cover"
               src="${abs(m.cover)}"
               onerror="this.src='${API}/assets/covers/fallback-magazine.jpg'">

          <div class="gbm-mag-body">
            <div class="gbm-mag-title">${m.title}</div>
            <div class="gbm-mag-meta">
              ${m.source || "Green Builder Magazine"}
              ${m.issue ? " • " + m.issue : ""}
            </div>

            <a href="${m.url}" target="_blank" class="gbm-mag-btn">
              View Magazine PDF →
            </a>
          </div>
        </div>
      </div>
    `;
  }

  // -------------------------
  // CHAT
  // -------------------------
  async function send(q) {
    const res = await fetch(`${API}/chat`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: q, session_id: "web"})
    });
    return res.json();
  }

  // -------------------------
  // UI
  // -------------------------
  function buildUI() {

    const wrap = el("div", "gbm-wrap");
    const log = el("div", "gbm-log");

    const input = el("input", "gbm-input");
    const btn = el("button", "gbm-send");

    btn.innerText = "SEND";
    input.placeholder = "Ask about building, energy, resilience…";

    btn.onclick = async () => {
      const q = input.value.trim();
      if (!q) return;

      const qBubble = el("div", "gbm-q");
      qBubble.innerText = q;
      log.appendChild(qBubble);

      const data = await send(q);

      const ans = el("div", "gbm-a");
      ans.innerHTML = `
        <div class="gbm-text">${data.answer}</div>
        ${renderCards(data.cards)}
        ${renderMagazines(data.magazines)}
      `;

      log.appendChild(ans);
      log.scrollTop = log.scrollHeight;
      input.value = "";
    };

    input.addEventListener("keypress", e => {
      if (e.key === "Enter") btn.click();
    });

    const bar = el("div", "gbm-bar");
    bar.appendChild(input);
    bar.appendChild(btn);

    wrap.appendChild(log);
    wrap.appendChild(bar);
    document.body.appendChild(wrap);
  }

  // -------------------------
  // ✅ CSS FIX ONLY
  // -------------------------
  const style = document.createElement("style");
  style.innerHTML = `
  
  .gbm-mag-card {
    display: flex;
    align-items: center;
    gap: 16px;
    border: 1px solid #d7dede;
    border-radius: 16px;
    background: #fff;
    padding: 14px;
    margin-top: 12px;
  }

  .gbm-mag-cover {
    width: 92px !important;
    height: 122px !important;
    min-width: 92px;
    object-fit: cover;
    border-radius: 6px;
    background: #eef2f2;
    flex: 0 0 auto;
  }

  .gbm-mag-body {
    flex: 1;
  }

  .gbm-mag-title {
    font-weight: 800;
    font-size: 16px;
    margin-bottom: 4px;
  }

  .gbm-mag-meta {
    font-size: 13px;
    color: #007565;
    font-weight: 700;
    margin-bottom: 6px;
  }

  .gbm-mag-btn {
    border: 1px solid #007565;
    padding: 8px 12px;
    border-radius: 8px;
    text-decoration: none;
    color: #007565;
    font-weight: 700;
  }

  `;
  document.head.appendChild(style);

  buildUI();

})();

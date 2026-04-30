(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || "https://gbm-visual-chatbot.onrender.com").replace(/\/$/, "");
  const title = currentScript?.dataset.chatbotTitle || "GBM Deep Think";

  const root = document.createElement("div");
  document.body.appendChild(root);

  let mode = "visual";

  function abs(url) {
    if (!url) return "";
    if (url.startsWith("http")) return url;
    return apiBase + url;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  root.innerHTML = `
  <style>
    .gbm-launcher {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #007565;
      color: white;
      padding: 14px 20px;
      border-radius: 999px;
      font-weight: 800;
      cursor: pointer;
      z-index: 999999;
      box-shadow: 0 8px 20px rgba(0,0,0,.25);
      font-family: Arial, sans-serif;
    }

    .gbm-panel {
      position: fixed;
      bottom: 80px;
      right: 20px;
      width: 900px;
      max-width: calc(100vw - 30px);
      height: 720px;
      max-height: calc(100vh - 100px);
      background: white;
      border-radius: 16px;
      display: none;
      flex-direction: column;
      overflow: hidden;
      z-index: 999998;
      box-shadow: 0 20px 60px rgba(0,0,0,.28);
      font-family: Arial, sans-serif;
      color: #1f2937;
    }

    .gbm-header {
      background: linear-gradient(135deg,#007565,#005447);
      color: white;
      padding: 16px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .gbm-title { font-size: 22px; font-weight: 900; }
    .gbm-close { font-size: 30px; cursor: pointer; border: 0; background: transparent; color: white; }

    .gbm-messages {
      flex: 1;
      overflow-y: auto;
      padding: 22px;
      background: #f7fafc;
    }

    .gbm-answer { margin-bottom: 14px; line-height: 1.5; font-size: 16px; }
    .gbm-thinking { font-weight: 800; color: #007565; }

    .gbm-toggle {
      margin: 12px 0 18px;
      font-weight: 900;
      color: #007565;
      cursor: pointer;
      text-transform: uppercase;
      font-size: 13px;
    }

    .gbm-insights {
      display: grid;
      grid-template-columns: repeat(3,1fr);
      gap: 10px;
      margin: 14px 0 20px;
    }

    .gbm-insight {
      background: white;
      border: 1px solid #d8dddd;
      border-radius: 12px;
      padding: 12px;
      font-size: 13px;
    }

    .gbm-section-title {
      font-size: 18px;
      font-weight: 900;
      margin: 18px 0 10px;
    }

    .gbm-card-row {
      display: flex;
      gap: 12px;
      overflow-x: auto;
      padding-bottom: 12px;
    }

    .gbm-card {
      min-width: 210px;
      max-width: 210px;
      border: 1px solid #d8dddd;
      border-radius: 12px;
      overflow: hidden;
      background: white;
      flex: 0 0 auto;
    }

    .gbm-card img {
      width: 100%;
      height: 118px;
      object-fit: cover;
      display: block;
      background: #eef2f2;
    }

    .gbm-card-body { padding: 10px; }
    .gbm-card-title { font-weight: 800; font-size: 13px; line-height: 1.25; margin-bottom: 8px; }
    .gbm-card a { color: #007565; font-size: 12px; font-weight: 800; text-decoration: none; }

    .gbm-mag-section { margin-top: 16px; }
    .gbm-mag-header { font-size: 18px; font-weight: 900; margin-bottom: 10px; }

    .gbm-mag-card {
      display: flex;
      align-items: center;
      gap: 16px;
      border: 1px solid #d7dede;
      border-radius: 16px;
      background: white;
      padding: 14px;
      margin-top: 8px;
    }

    .gbm-mag-cover {
      width: 92px !important;
      height: 122px !important;
      min-width: 92px !important;
      object-fit: cover !important;
      border-radius: 6px;
      background: #eef2f2;
      flex: 0 0 auto;
    }

    .gbm-mag-body { flex: 1; }
    .gbm-mag-title { font-size: 16px; font-weight: 900; margin-bottom: 5px; }
    .gbm-mag-meta { font-size: 13px; color: #007565; font-weight: 800; margin-bottom: 8px; }

    .gbm-mag-btn {
      display: inline-block;
      border: 1px solid #007565;
      border-radius: 9px;
      padding: 8px 12px;
      color: #007565;
      text-decoration: none;
      font-weight: 900;
      font-size: 13px;
    }

    .gbm-input-row {
      display: flex;
      padding: 12px;
      border-top: 1px solid #e5e7eb;
      gap: 8px;
      background: white;
    }

    .gbm-input {
      flex: 1;
      padding: 13px 15px;
      border-radius: 999px;
      border: 1px solid #cbd5e1;
      font-size: 15px;
    }

    .gbm-send {
      background: #007565;
      color: white;
      border: 0;
      padding: 0 18px;
      border-radius: 999px;
      cursor: pointer;
      font-weight: 900;
    }

    .gbm-sources li { margin-bottom: 8px; }
    .gbm-sources a { color: #007565; font-weight: 800; text-decoration: none; }

    @media (max-width: 760px) {
      .gbm-panel { right: 0; bottom: 0; width: 100vw; height: 100vh; max-height: 100vh; border-radius: 0; }
      .gbm-insights { grid-template-columns: 1fr; }
    }
  </style>

  <div class="gbm-launcher">${escapeHtml(title)}</div>

  <div class="gbm-panel">
    <div class="gbm-header">
      <div class="gbm-title">${escapeHtml(title)}</div>
      <button class="gbm-close">×</button>
    </div>
    <div class="gbm-messages">
      <div class="gbm-answer">Ask me about Green Builder Media articles, magazines, sustainable homes, resilience, solar, electrification, products, or market trends.</div>
    </div>
    <div class="gbm-input-row">
      <input class="gbm-input" placeholder="Ask Green Builder..." />
      <button class="gbm-send">SEND</button>
    </div>
  </div>
  `;

  const launcher = root.querySelector(".gbm-launcher");
  const panel = root.querySelector(".gbm-panel");
  const messages = root.querySelector(".gbm-messages");
  const input = root.querySelector(".gbm-input");
  const send = root.querySelector(".gbm-send");
  const close = root.querySelector(".gbm-close");

  launcher.onclick = () => {
    panel.style.display = "flex";
    launcher.style.display = "none";
    input.focus();
  };

  close.onclick = () => {
    panel.style.display = "none";
    launcher.style.display = "block";
  };

  function renderInsights(data) {
    const insights = data.key_insights || [];
    if (!insights.length) return "";

    return `
      <div class="gbm-insights">
        ${insights.slice(0,3).map(i => `
          <div class="gbm-insight">
            <strong>${escapeHtml(i.title || "Insight")}</strong><br>
            ${escapeHtml(i.text || "")}
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderCards(data) {
    const cards = data.cards || [];
    if (!cards.length) return "";

    return `
      <div class="gbm-section-title">Recommended Reading</div>
      <div class="gbm-card-row">
        ${cards.slice(0,8).map(c => {
          const img = c.image || c.remote_image || "/assets/thumbs/fallback-article.jpg";
          return `
            <div class="gbm-card">
              <img src="${abs(img)}" onerror="this.onerror=null;this.src='${abs(c.remote_image || "/assets/thumbs/fallback-article.jpg")}';">
              <div class="gbm-card-body">
                <div class="gbm-card-title">${escapeHtml(c.title || "Green Builder article")}</div>
                <a href="${abs(c.url)}" target="_blank" rel="noopener">Read Article ↗</a>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderMagazines(data) {
    const mags = data.magazines || [];
    if (!mags.length) return "";

    const m = mags[0];

    return `
      <div class="gbm-mag-section">
        <div class="gbm-mag-header">From the Magazine</div>
        <div class="gbm-mag-card">
          <img class="gbm-mag-cover"
               src="${abs(m.cover || "/assets/covers/fallback-magazine.jpg")}"
               onerror="this.onerror=null;this.src='${abs("/assets/covers/fallback-magazine.jpg")}';">
          <div class="gbm-mag-body">
            <div class="gbm-mag-title">${escapeHtml(m.title || "Green Builder Magazine")}</div>
            <div class="gbm-mag-meta">${escapeHtml(m.source || "Green Builder Magazine")}</div>
            <a class="gbm-mag-btn" href="${abs(m.url)}" target="_blank" rel="noopener">View Magazine PDF ↗</a>
          </div>
        </div>
      </div>
    `;
  }

  function renderVisual(data) {
    mode = "visual";
    messages.innerHTML = `
      <div class="gbm-answer">${escapeHtml(data.visual_summary || data.answer || "").replace(/\n/g, "<br>")}</div>
      <div class="gbm-toggle">DIVE DEEPER WITH TEXT ONLY</div>
      ${renderInsights(data)}
      ${renderCards(data)}
      ${renderMagazines(data)}
    `;

    messages.querySelector(".gbm-toggle").onclick = () => renderText(data);
  }

  function renderText(data) {
    mode = "text";

    const sourceLinks = [];

    (data.cards || []).forEach(c => {
      if (c.url) sourceLinks.push(`<li><a href="${abs(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.title || c.url)}</a></li>`);
    });

    (data.magazines || []).forEach(m => {
      if (m.url) sourceLinks.push(`<li><a href="${abs(m.url)}" target="_blank" rel="noopener">${escapeHtml(m.title || m.url)}</a></li>`);
    });

    (data.sources || []).forEach(s => {
      if (s.url && !sourceLinks.join("").includes(escapeHtml(s.url))) {
        sourceLinks.push(`<li><a href="${abs(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.title || s.url)}</a></li>`);
      }
    });

    messages.innerHTML = `
      <div class="gbm-answer">${escapeHtml(data.text_only_answer || data.answer || "").replace(/\n/g, "<br>")}</div>
      <div class="gbm-toggle">RETURN TO VISUAL MODE</div>
      ${sourceLinks.length ? `<div class="gbm-sources"><h3>Sources</h3><ol>${sourceLinks.join("")}</ol></div>` : ""}
    `;

    messages.querySelector(".gbm-toggle").onclick = () => renderVisual(data);
  }

  async function ask() {
    const q = input.value.trim();
    if (!q) return;

    messages.innerHTML = `<div class="gbm-thinking">Thinking...</div>`;

    try {
      const res = await fetch(apiBase + "/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          question: q,
          session_id: window.gbmSessionId || "web-" + Date.now(),
          page_url: window.location.href,
          referrer: document.referrer || "",
          user_agent: navigator.userAgent || ""
        })
      });

      const data = await res.json();
      input.value = "";

      if (mode === "text") renderText(data);
      else renderVisual(data);

    } catch (err) {
      messages.innerHTML = `<div class="gbm-answer">Sorry — the chatbot had trouble responding. ${escapeHtml(err.message || "")}</div>`;
    }
  }

  send.onclick = ask;

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.keyCode === 13) {
      e.preventDefault();
      send.click();
    }
  });
})();

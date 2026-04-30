(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || "").replace(/\/$/, "");
  const title = currentScript?.dataset.chatbotTitle || "GBM Deep Think";
  const subtitle = currentScript?.dataset.chatbotSubtitle || "";
  const brandColor = currentScript?.dataset.brandColor || "#007565";

  if (!apiBase) {
    console.error("Missing data-api-base on chatbot script tag.");
    return;
  }

  const root = document.createElement("div");
  document.body.appendChild(root);

  let mode = "visual";
  let lastData = null;

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

  function paragraphize(text) {
    return escapeHtml(text || "")
      .split(/\n\s*\n/)
      .filter(Boolean)
      .map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`)
      .join("");
  }

  function imageTag(primary, fallback, alt) {
    const p = abs(primary || "");
    const f = abs(fallback || "/assets/thumbs/fallback-article.jpg");
    return `
      <img 
        src="${p || f}" 
        alt="${escapeHtml(alt)}"
        loading="lazy"
        onerror="this.onerror=null;this.src='${f}';"
      />
    `;
  }

  root.innerHTML = `
    <style>
      .gbm-launcher {
        position: fixed !important;
        right: 22px;
        bottom: 22px;
        z-index: 999999;
        background: ${brandColor};
        color: #fff;
        border: none;
        border-radius: 999px;
        padding: 15px 26px;
        font-family: Arial, Helvetica, sans-serif;
        font-size: 18px;
        font-weight: 800;
        cursor: pointer;
        box-shadow: 0 10px 24px rgba(0,0,0,.24);
      }

      .gbm-panel {
        position: fixed;
        right: 18px;
        bottom: 86px;
        width: 960px;
        max-width: calc(100vw - 28px);
        height: 760px;
        max-height: calc(100vh - 110px);
        z-index: 999998;
        display: none;
        flex-direction: column;
        overflow: hidden;
        background: #fff;
        border-radius: 20px;
        box-shadow: 0 24px 70px rgba(0,0,0,.28);
        font-family: Arial, Helvetica, sans-serif;
        color: #20223f;
      }

      .gbm-header {
        background: linear-gradient(135deg, ${brandColor}, #005447);
        color: #fff;
        padding: 22px 26px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .gbm-header-text {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .gbm-title {
        font-size: 28px;
        line-height: 1.1;
        font-weight: 900;
      }

      .gbm-subtitle {
        font-size: 15px;
        opacity: .92;
        font-weight: 500;
      }

      .gbm-close {
        background: transparent;
        border: none;
        color: #fff;
        font-size: 42px;
        line-height: 1;
        cursor: pointer;
      }

      .gbm-messages {
        flex: 1;
        overflow-y: auto;
        padding: 26px 30px;
        background: #f8fafc;
      }

      .gbm-answer {
        font-size: 18px;
        line-height: 1.48;
        margin-bottom: 14px;
      }

      .gbm-answer p {
        margin: 0 0 14px;
      }

      .gbm-toggle {
        display: inline-block;
        margin: 2px 0 20px;
        color: ${brandColor};
        font-weight: 900;
        font-size: 16px;
        cursor: pointer;
        text-transform: uppercase;
      }

      .gbm-section-title {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 20px 0 12px;
        font-size: 18px;
        font-weight: 900;
        color: #1f2937;
      }

      .gbm-insights {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin: 18px 0 22px;
        padding: 18px;
        border: 1px solid #d9e2e2;
        border-radius: 18px;
        background: #ffffff;
      }

      .gbm-insight {
        border-right: 1px solid #d9e2e2;
        padding: 4px 12px 4px 4px;
      }

      .gbm-insight:last-child {
        border-right: none;
      }

      .gbm-insight-title {
        font-size: 15px;
        font-weight: 900;
        color: #123b36;
        margin-bottom: 7px;
      }

      .gbm-insight-text {
        font-size: 14px;
        line-height: 1.35;
        color: #30324a;
      }

      .gbm-card-row {
        display: flex;
        gap: 16px;
        overflow-x: auto;
        padding: 4px 2px 14px;
        scroll-snap-type: x mandatory;
      }

      .gbm-card {
        flex: 0 0 210px;
        scroll-snap-align: start;
        border: 1px solid #d8dddd;
        border-radius: 14px;
        overflow: hidden;
        background: #fff;
        box-shadow: 0 2px 7px rgba(0,0,0,.08);
      }

      .gbm-card img {
        width: 100%;
        height: 118px;
        object-fit: cover;
        display: block;
        background: #eef2f2;
      }

      .gbm-card-body {
        padding: 12px 13px 14px;
      }

      .gbm-card-kicker {
        display: inline-block;
        margin-bottom: 8px;
        padding: 4px 8px;
        border-radius: 999px;
        border: 1px solid #b8d8d3;
        color: ${brandColor};
        font-size: 11px;
        font-weight: 900;
        text-transform: uppercase;
      }

      .gbm-card-title {
        color: #1f2937;
        font-size: 15px;
        line-height: 1.22;
        font-weight: 900;
        margin-bottom: 10px;
      }

      .gbm-card-link {
        color: ${brandColor};
        font-size: 13px;
        font-weight: 900;
        text-decoration: none;
      }

      .gbm-mag-card {
        display: flex;
        align-items: center;
        gap: 18px;
        border: 1px solid #d8dddd;
        border-radius: 16px;
        background: #fff;
        padding: 14px;
        margin-top: 8px;
      }

      .gbm-mag-card img {
        width: 92px;
        height: 122px;
        object-fit: cover;
        border-radius: 6px;
        background: #eef2f2;
      }

      .gbm-mag-title {
        font-size: 17px;
        font-weight: 900;
        margin-bottom: 7px;
      }

      .gbm-mag-meta {
        color: ${brandColor};
        font-size: 14px;
        font-weight: 700;
        margin-bottom: 10px;
      }

      .gbm-text-sources {
        margin-top: 22px;
        border-top: 1px solid #d8dddd;
        padding-top: 14px;
      }

      .gbm-text-sources a {
        color: ${brandColor};
        font-weight: 800;
        text-decoration: none;
      }

      .gbm-input-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 22px;
        border-top: 1px solid #e1e5e5;
        background: #fff;
      }

      .gbm-input {
        flex: 1;
        border: 1px solid #ccd3d3;
        border-radius: 999px;
        padding: 16px 20px;
        font-size: 17px;
        outline: none;
      }

      .gbm-send {
        width: 58px;
        height: 58px;
        border-radius: 50%;
        border: none;
        background: ${brandColor};
        color: #fff;
        font-size: 28px;
        cursor: pointer;
        font-weight: 900;
      }

      .gbm-thinking {
        color: ${brandColor};
        font-weight: 900;
        font-size: 18px;
      }

      @media (max-width: 760px) {
        .gbm-panel {
          right: 0;
          bottom: 0;
          width: 100vw;
          height: 100vh;
          max-width: 100vw;
          max-height: 100vh;
          border-radius: 0;
        }

        .gbm-insights {
          grid-template-columns: 1fr;
        }

        .gbm-insight {
          border-right: none;
          border-bottom: 1px solid #d9e2e2;
          padding-bottom: 12px;
        }

        .gbm-insight:last-child {
          border-bottom: none;
        }

        .gbm-card {
          flex-basis: 235px;
        }
      }
    </style>

    <button class="gbm-launcher">${escapeHtml(title)}</button>

    <div class="gbm-panel">
      <div class="gbm-header">
        <div class="gbm-header-text">
          <div class="gbm-title">${escapeHtml(title)}</div>
          ${subtitle ? `<div class="gbm-subtitle">${escapeHtml(subtitle)}</div>` : ""}
        </div>
        <button class="gbm-close" aria-label="Close chatbot">×</button>
      </div>

      <div class="gbm-messages">
        <div class="gbm-answer">Ask me about Green Builder Media articles, magazines, sustainable homes, resilience, solar, electrification, products, or market trends.</div>
      </div>

      <div class="gbm-input-row">
        <input class="gbm-input" placeholder="Ask Green Builder..." />
        <button class="gbm-send" aria-label="Send">➤</button>
      </div>
    </div>
  `;

  const launcher = root.querySelector(".gbm-launcher");
  const panel = root.querySelector(".gbm-panel");
  const messages = root.querySelector(".gbm-messages");
  const input = root.querySelector(".gbm-input");
  const send = root.querySelector(".gbm-send");
  const closeBtn = root.querySelector(".gbm-close");

  launcher.onclick = () => {
    panel.style.display = "flex";
    launcher.style.display = "none";
    input.focus();
  };

  closeBtn.onclick = () => {
    panel.style.display = "none";
    launcher.style.display = "block";
  };

  function renderInsights(data, container) {
    const insights = data.key_insights || [];
    if (!insights.length) return;

    const section = document.createElement("div");
    section.className = "gbm-insights";

    insights.slice(0, 4).forEach((item) => {
      const insight = document.createElement("div");
      insight.className = "gbm-insight";
      insight.innerHTML = `
        <div class="gbm-insight-title">${escapeHtml(item.title || "Insight")}</div>
        <div class="gbm-insight-text">${escapeHtml(item.text || "")}</div>
      `;
      section.appendChild(insight);
    });

    container.appendChild(section);
  }

  function renderCards(data, container) {
    const cards = data.cards || [];
    if (!cards.length) return;

    const titleEl = document.createElement("div");
    titleEl.className = "gbm-section-title";
    titleEl.innerHTML = "📖 Recommended Reading";
    container.appendChild(titleEl);

    const row = document.createElement("div");
    row.className = "gbm-card-row";

    cards.slice(0, 8).forEach((card) => {
      const el = document.createElement("div");
      el.className = "gbm-card";

      const primaryImage = card.image || card.remote_image || "/assets/thumbs/fallback-article.jpg";
      const fallbackImage = card.remote_image || "/assets/thumbs/fallback-article.jpg";

      el.innerHTML = `
        <a href="${abs(card.url)}" target="_blank" rel="noopener">
          ${imageTag(primaryImage, fallbackImage, card.title)}
        </a>
        <div class="gbm-card-body">
          <div class="gbm-card-kicker">${escapeHtml(card.category || card.source || "Article")}</div>
          <div class="gbm-card-title">${escapeHtml(card.title || "Green Builder article")}</div>
          <a class="gbm-card-link" href="${abs(card.url)}" target="_blank" rel="noopener">Read Article ↗</a>
        </div>
      `;
      row.appendChild(el);
    });

    container.appendChild(row);
  }

  function renderMagazines(data, container) {
    const magazines = data.magazines || [];
    if (!magazines.length) return;

    const titleEl = document.createElement("div");
    titleEl.className = "gbm-section-title";
    titleEl.innerHTML = "📘 From the Magazine";
    container.appendChild(titleEl);

    magazines.slice(0, 3).forEach((mag) => {
      const el = document.createElement("div");
      el.className = "gbm-mag-card";

      el.innerHTML = `
        ${imageTag(mag.cover || "/assets/covers/fallback-magazine.jpg", "/assets/covers/fallback-magazine.jpg", mag.title)}
        <div>
          <div class="gbm-mag-title">${escapeHtml(mag.title || "Green Builder Magazine")}</div>
          <div class="gbm-mag-meta">${escapeHtml(mag.issue || mag.source || "Magazine archive")}</div>
          <a class="gbm-card-link" href="${abs(mag.url)}" target="_blank" rel="noopener">View PDF ↗</a>
        </div>
      `;
      container.appendChild(el);
    });
  }

  function renderVisual(data) {
    lastData = data;
    mode = "visual";
    messages.innerHTML = "";

    const wrap = document.createElement("div");

    wrap.innerHTML = `
      <div class="gbm-answer">${paragraphize(data.visual_summary || data.answer || "")}</div>
      <div class="gbm-toggle">DIVE DEEPER WITH TEXT ONLY</div>
    `;

    wrap.querySelector(".gbm-toggle").onclick = () => renderText(data);

    renderInsights(data, wrap);
    renderCards(data, wrap);
    renderMagazines(data, wrap);

    messages.appendChild(wrap);
  }

  function renderText(data) {
    lastData = data;
    mode = "text";
    messages.innerHTML = "";

    const wrap = document.createElement("div");

    const sources = data.sources || [];
    const sourceHtml = sources.length
      ? `
        <div class="gbm-text-sources">
          <div class="gbm-section-title">Sources</div>
          <ol>
            ${sources.map((s) => `
              <li>
                <a href="${abs(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.title || s.url)}</a>
              </li>
            `).join("")}
          </ol>
        </div>
      `
      : "";

    wrap.innerHTML = `
      <div class="gbm-answer">${paragraphize(data.text_only_answer || data.answer || "")}</div>
      <div class="gbm-toggle">RETURN TO VISUAL MODE</div>
      ${sourceHtml}
    `;

    wrap.querySelector(".gbm-toggle").onclick = () => renderVisual(data);
    messages.appendChild(wrap);
  }

  async function ask() {
    const q = input.value.trim();
    if (!q) return;

    messages.innerHTML = `<div class="gbm-thinking">Thinking...</div>`;

    try {
      const res = await fetch(apiBase + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          session_id: window.gbmSessionId || "web-" + Date.now(),
          page_url: window.location.href,
          referrer: document.referrer || "",
          user_agent: navigator.userAgent || ""
        })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Chat request failed.");
      }

      input.value = "";
      if (mode === "text") renderText(data);
      else renderVisual(data);

    } catch (err) {
      messages.innerHTML = `
        <div class="gbm-answer">
          Sorry — the chatbot had trouble responding. ${escapeHtml(err.message || "")}
        </div>
      `;
    }
  }

  send.onclick = ask;

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      ask();
    }
  });
})();

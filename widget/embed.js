```javascript
(function () {
  if (window.GBM_DEEPTHINK_LOADED) return;
  window.GBM_DEEPTHINK_LOADED = true;

  const SCRIPT = document.currentScript;
  const API_BASE = (SCRIPT && SCRIPT.dataset.apiBase) || "https://gbm-visual-chatbot.onrender.com";
  const COGNITION_LOGO_URL = "https://7820107.fs1.hubspotusercontent-na1.net/hubfs/7820107/Cognition%20Button.png";
  const COGNITION_SMART_DATA_URL = "https://www.greenbuildermedia.com/cognition-smart-data";

  let currentMode = "visual";
  let lastPayload = null;
  let lastQuestion = "";
  let sessionId = localStorage.getItem("gbm_deepthink_session_id");
  if (!sessionId) {
    sessionId = Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("gbm_deepthink_session_id", sessionId);
  }

  const style = document.createElement("style");
  style.textContent = `
    :root {
      --gbm-blue: #128fdb;
      --gbm-blue-dark: #0b5f92;
      --gbm-ink: #163244;
      --gbm-muted: #5f7180;
      --gbm-card: #ffffff;
      --gbm-soft: #f2f8fc;
      --gbm-line: rgba(22, 50, 68, .13);
      --gbm-shadow: 0 18px 50px rgba(16, 71, 113, .18);
    }

    #gbm-deepthink-launcher {
      position: fixed;
      right: 22px;
      bottom: 22px;
      width: 74px;
      height: 74px;
      border-radius: 50%;
      border: 0;
      cursor: pointer;
      box-shadow: 0 14px 34px rgba(0,0,0,.28);
      background: #ffffff;
      padding: 7px;
      z-index: 2147483000;
      overflow: hidden;
    }

    #gbm-deepthink-launcher img {
      width: 100%;
      height: 100%;
      border-radius: 50%;
      display: block;
      object-fit: contain;
      background: #fff;
    }

    #gbm-deepthink-launcher::after {
      content: "";
      position: absolute;
      inset: -40%;
      background: linear-gradient(120deg, transparent 35%, rgba(18,143,219,.28), transparent 65%);
      transform: translateX(-80%) rotate(20deg);
      animation: gbmPulseSweep 3.8s ease-in-out 1;
      pointer-events: none;
    }

    @keyframes gbmPulseSweep {
      0% { transform: translateX(-90%) rotate(20deg); opacity: 0; }
      18% { opacity: 1; }
      52% { transform: translateX(85%) rotate(20deg); opacity: .9; }
      100% { transform: translateX(85%) rotate(20deg); opacity: 0; }
    }

    #gbm-deepthink-panel {
      position: fixed;
      right: 22px;
      bottom: 108px;
      width: min(1080px, calc(100vw - 44px));
      height: min(760px, calc(100vh - 140px));
      background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
      border: 1px solid var(--gbm-line);
      border-radius: 26px;
      box-shadow: var(--gbm-shadow);
      z-index: 2147483001;
      overflow: hidden;
      display: none;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--gbm-ink);
    }

    #gbm-deepthink-panel.gbm-open { display: flex; flex-direction: column; }

    .gbm-head {
      background:
        radial-gradient(circle at 20% 10%, rgba(255,255,255,.25), transparent 24%),
        linear-gradient(135deg, #064b76 0%, #128fdb 100%);
      color: white;
      padding: 16px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }

    .gbm-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .gbm-brand img {
      width: 46px;
      height: 46px;
      border-radius: 50%;
      background: white;
      object-fit: contain;
      flex: 0 0 auto;
    }

    .gbm-title {
      font-size: 18px;
      font-weight: 800;
      letter-spacing: .01em;
      line-height: 1.15;
    }

    .gbm-subtitle {
      font-size: 12px;
      opacity: .92;
      margin-top: 3px;
      line-height: 1.25;
      max-width: 760px;
    }

    .gbm-close {
      border: 1px solid rgba(255,255,255,.5);
      background: rgba(255,255,255,.14);
      color: white;
      border-radius: 999px;
      width: 36px;
      height: 36px;
      cursor: pointer;
      font-size: 22px;
      line-height: 1;
      flex: 0 0 auto;
    }

    .gbm-body {
      flex: 1;
      overflow: auto;
      padding: 18px;
    }

    .gbm-welcome {
      background: #ffffff;
      border: 1px solid var(--gbm-line);
      border-radius: 20px;
      padding: 18px;
      box-shadow: 0 8px 26px rgba(18,143,219,.08);
      margin-bottom: 14px;
    }

    .gbm-welcome-title {
      font-size: 20px;
      font-weight: 800;
      margin-bottom: 6px;
    }

    .gbm-welcome-text {
      color: var(--gbm-muted);
      font-size: 14px;
      line-height: 1.48;
    }

    .gbm-messages {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .gbm-question {
      align-self: flex-end;
      max-width: 80%;
      background: var(--gbm-blue);
      color: #ffffff;
      border-radius: 18px 18px 4px 18px;
      padding: 12px 14px;
      font-size: 14px;
      line-height: 1.45;
      box-shadow: 0 8px 18px rgba(18,143,219,.18);
    }

    .gbm-answer-wrap {
      display: grid;
      grid-template-columns: 42px 1fr;
      gap: 10px;
      align-items: flex-start;
    }

    .gbm-avatar {
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: #ffffff;
      border: 1px solid var(--gbm-line);
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }

    .gbm-avatar img {
      width: 34px;
      height: 34px;
      object-fit: contain;
      border-radius: 50%;
    }

    .gbm-answer {
      background: #ffffff;
      border: 1px solid var(--gbm-line);
      border-radius: 18px 18px 18px 4px;
      padding: 14px 15px;
      line-height: 1.55;
      font-size: 14px;
      color: var(--gbm-ink);
      box-shadow: 0 8px 26px rgba(16,71,113,.07);
    }

    .gbm-toggle {
      color: var(--gbm-blue-dark);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .06em;
      margin: -4px 0 2px 52px;
      cursor: pointer;
      width: fit-content;
    }

    .gbm-toggle:hover { text-decoration: underline; }

    .gbm-hot-take {
      background: linear-gradient(135deg, rgba(18,143,219,.10), rgba(255,255,255,1));
      border: 1px solid rgba(18,143,219,.25);
      border-radius: 22px;
      padding: 14px;
      margin: 4px 0 4px 52px;
      box-shadow: 0 10px 28px rgba(18,143,219,.10);
    }

    .gbm-hot-take-inner {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 260px;
      gap: 14px;
      align-items: center;
    }

    .gbm-hot-kicker {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .09em;
      color: var(--gbm-blue-dark);
      font-weight: 900;
      margin-bottom: 6px;
    }

    .gbm-hot-title {
      font-size: 19px;
      line-height: 1.16;
      font-weight: 900;
      color: var(--gbm-ink);
      margin-bottom: 8px;
    }

    .gbm-hot-caption {
      color: var(--gbm-muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .gbm-hot-links {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }

    .gbm-hot-link {
      color: var(--gbm-blue-dark);
      font-size: 12px;
      font-weight: 800;
      text-decoration: none;
      background: rgba(18,143,219,.10);
      border: 1px solid rgba(18,143,219,.20);
      border-radius: 999px;
      padding: 7px 9px;
    }

    .gbm-hot-link-primary {
      color: white;
      background: var(--gbm-blue);
      border-color: var(--gbm-blue);
    }

    .gbm-hot-image-wrap {
      position: relative;
      background: #ffffff;
      border: 1px solid var(--gbm-line);
      border-radius: 16px;
      overflow: hidden;
      min-height: 145px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .gbm-hot-image {
      width: 100%;
      max-height: 210px;
      object-fit: contain;
      display: block;
      background: #ffffff;
    }

    .gbm-expand-image {
      position: absolute;
      right: 8px;
      bottom: 8px;
      background: rgba(6,75,118,.86);
      color: #ffffff;
      text-decoration: none;
      font-size: 11px;
      font-weight: 800;
      padding: 6px 8px;
      border-radius: 999px;
    }

    .gbm-section-title {
      margin: 12px 0 0 52px;
      font-size: 13px;
      font-weight: 900;
      letter-spacing: .08em;
      color: var(--gbm-ink);
    }

    .gbm-grid {
      margin-left: 52px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .gbm-col {
      background: #ffffff;
      border: 1px solid var(--gbm-line);
      border-radius: 18px;
      padding: 10px;
      min-height: 215px;
      box-shadow: 0 8px 24px rgba(16,71,113,.06);
    }

    .gbm-col-head {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 8px;
      font-weight: 900;
      color: var(--gbm-ink);
      font-size: 13px;
    }

    .gbm-card {
      display: block;
      text-decoration: none;
      color: inherit;
      border: 1px solid rgba(22,50,68,.10);
      border-radius: 14px;
      overflow: hidden;
      background: #fbfdff;
      margin-bottom: 9px;
      transition: transform .15s ease, box-shadow .15s ease;
    }

    .gbm-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 24px rgba(18,143,219,.14);
    }

    .gbm-card img {
      width: 100%;
      height: 86px;
      object-fit: cover;
      display: block;
      background: #e8f3fb;
    }

    .gbm-card-body { padding: 9px; }

    .gbm-card-title {
      font-size: 12px;
      line-height: 1.28;
      font-weight: 800;
      color: var(--gbm-ink);
      margin-bottom: 5px;
    }

    .gbm-card-meta {
      font-size: 10.5px;
      line-height: 1.25;
      color: var(--gbm-muted);
      text-transform: uppercase;
      letter-spacing: .03em;
      font-weight: 700;
    }

    .gbm-empty {
      color: var(--gbm-muted);
      background: var(--gbm-soft);
      border: 1px dashed rgba(18,143,219,.24);
      border-radius: 14px;
      padding: 12px;
      font-size: 12px;
      line-height: 1.4;
    }

    .gbm-form {
      display: flex;
      gap: 9px;
      border-top: 1px solid var(--gbm-line);
      padding: 12px;
      background: #ffffff;
    }

    .gbm-input {
      flex: 1;
      border: 1px solid rgba(22,50,68,.18);
      border-radius: 999px;
      padding: 12px 14px;
      font-size: 14px;
      outline: none;
    }

    .gbm-input:focus {
      border-color: var(--gbm-blue);
      box-shadow: 0 0 0 3px rgba(18,143,219,.14);
    }

    .gbm-submit {
      border: 0;
      border-radius: 999px;
      background: var(--gbm-blue);
      color: white;
      font-weight: 900;
      padding: 0 18px;
      cursor: pointer;
    }

    .gbm-submit:disabled {
      opacity: .55;
      cursor: not-allowed;
    }

    .gbm-loading {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--gbm-muted);
      font-size: 13px;
      margin-left: 52px;
      padding: 10px 0;
    }

    .gbm-dot {
      width: 7px;
      height: 7px;
      background: var(--gbm-blue);
      border-radius: 50%;
      animation: gbmDot 1s infinite ease-in-out;
    }

    .gbm-dot:nth-child(2) { animation-delay: .15s; }
    .gbm-dot:nth-child(3) { animation-delay: .3s; }

    @keyframes gbmDot {
      0%, 80%, 100% { transform: scale(.7); opacity: .45; }
      40% { transform: scale(1); opacity: 1; }
    }

    @media (max-width: 940px) {
      #gbm-deepthink-panel {
        right: 12px;
        bottom: 94px;
        width: calc(100vw - 24px);
        height: calc(100vh - 112px);
      }

      .gbm-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .gbm-hot-take-inner {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 560px) {
      #gbm-deepthink-launcher {
        width: 64px;
        height: 64px;
        right: 16px;
        bottom: 16px;
      }

      #gbm-deepthink-panel {
        right: 0;
        bottom: 0;
        width: 100vw;
        height: 100vh;
        border-radius: 0;
      }

      .gbm-subtitle { display: none; }
      .gbm-body { padding: 12px; }
      .gbm-question { max-width: 92%; }
      .gbm-grid, .gbm-hot-take, .gbm-section-title, .gbm-toggle { margin-left: 0; }
      .gbm-grid { grid-template-columns: 1fr; }
      .gbm-form { padding: 10px; }
      .gbm-submit { padding: 0 14px; }
    }
  `;
  document.head.appendChild(style);

  const launcher = document.createElement("button");
  launcher.id = "gbm-deepthink-launcher";
  launcher.setAttribute("aria-label", "Open COGNITION DeepDive");
  launcher.innerHTML = `<img src="${COGNITION_LOGO_URL}" alt="COGNITION">`;

  const panel = document.createElement("div");
  panel.id = "gbm-deepthink-panel";
  panel.innerHTML = `
    <div class="gbm-head">
      <div class="gbm-brand">
        <img src="${COGNITION_LOGO_URL}" alt="COGNITION">
        <div>
          <div class="gbm-title">COGNITION DeepDive</div>
          <div class="gbm-subtitle">Make your query, and tap the power of our exclusive COGNITION SmartData, combining new research with 25 years of expertise in sustainable building.</div>
        </div>
      </div>
      <button class="gbm-close" aria-label="Close">×</button>
    </div>
    <div class="gbm-body">
      <div class="gbm-welcome">
        <div class="gbm-welcome-title">Ask us anything about sustainable building.</div>
        <div class="gbm-welcome-text">COGNITION DeepDive searches Green Builder Media articles, guides, magazines, videos, podcasts, and SmartData insights to produce an evidence-based answer with supporting resources.</div>
      </div>
      <div class="gbm-messages"></div>
    </div>
    <form class="gbm-form">
      <input class="gbm-input" type="text" placeholder="Ask about heat pumps, electrification, resilience, codes, solar, water, materials..." />
      <button class="gbm-submit" type="submit">Ask</button>
    </form>
  `;

  document.body.appendChild(launcher);
  document.body.appendChild(panel);

  const closeBtn = panel.querySelector(".gbm-close");
  const form = panel.querySelector(".gbm-form");
  const input = panel.querySelector(".gbm-input");
  const submit = panel.querySelector(".gbm-submit");
  const messages = panel.querySelector(".gbm-messages");
  const welcome = panel.querySelector(".gbm-welcome");

  launcher.addEventListener("click", () => {
    panel.classList.toggle("gbm-open");
    if (panel.classList.contains("gbm-open")) input.focus();
  });

  closeBtn.addEventListener("click", () => {
    panel.classList.remove("gbm-open");
  });

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function abs(url) {
    if (!url) return "";
    const raw = String(url);
    if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
    if (raw.startsWith("/")) return API_BASE.replace(/\/$/, "") + raw;
    return raw;
  }

  function normalizeUrl(url) {
    return String(url || "").trim();
  }

  function dedupeByUrl(items) {
    const seen = new Set();
    const out = [];
    (items || []).forEach(item => {
      const url = normalizeUrl(item && item.url);
      if (!url) return;
      if (seen.has(url)) return;
      seen.add(url);
      out.push(item);
    });
    return out;
  }

  function imageForCard(card, type) {
    const explicit = card.image || card.thumbnail_url || card.thumbnail || card.cover || card.og_image || card.featured_image;
    if (explicit) return abs(explicit);

    if (type === "pdf") return abs("/assets/covers/fallback-magazine.jpg");
    if (type === "video" || type === "podcast") return COGNITION_LOGO_URL;
    return abs("/assets/thumbs/fallback-article.jpg");
  }

  function cardTitle(card) {
    return card.title || card.name || card.source_name || "Green Builder Media Resource";
  }

  function cardMeta(card, type) {
    if (type === "pdf") {
      const page = card.page != null ? ` · p. ${card.page}` : "";
      return `${card.source || card.issue || "Magazine / Guide"}${page}`;
    }
    if (type === "video") return card.source || "Green Builder Media YouTube";
    if (type === "podcast") return card.source || "Green Builder Media Podcast";
    return card.category || card.source || card.attribution_label || "Article";
  }

  function renderCard(card, type) {
    const url = abs(card.url || card.article_url || "");
    if (!url) return "";
    const title = cardTitle(card);
    const img = imageForCard(card, type);
    return `
      <a class="gbm-card" href="${esc(url)}" target="_blank" rel="noopener">
        <img src="${esc(img)}" alt="${esc(title)}" loading="lazy" onerror="this.onerror=null;this.src='${esc(type === "pdf" ? abs("/assets/covers/fallback-magazine.jpg") : COGNITION_LOGO_URL)}';" />
        <div class="gbm-card-body">
          <div class="gbm-card-title">${esc(title)}</div>
          <div class="gbm-card-meta">${esc(cardMeta(card, type))}</div>
        </div>
      </a>
    `;
  }

  function renderColumn(title, type, items, emptyText) {
    const clean = dedupeByUrl(items || []).slice(0, 2);
    return `
      <div class="gbm-col">
        <div class="gbm-col-head">${esc(title)}</div>
        ${clean.length ? clean.map(item => renderCard(item, type)).join("") : `<div class="gbm-empty">${esc(emptyText)}</div>`}
      </div>
    `;
  }

  function twoParagraphAnswer(text) {
    const raw = String(text || "").trim();
    if (!raw) return "I couldn't find enough Green Builder Media context to answer that question.";

    const paragraphs = raw.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
    if (paragraphs.length >= 2) return paragraphs.slice(0, 2).join("\n\n");

    const sentences = raw.match(/[^.!?]+[.!?]+(?:\s|$)/g) || [];
    if (sentences.length >= 3) {
      return sentences.slice(0, 3).join(" ").trim();
    }

    return raw.length > 850 ? raw.slice(0, 850).replace(/\s+\S*$/, "") + "..." : raw;
  }

  function isPdfCard(card) {
    const type = String(card.type || card.source_type || "").toLowerCase();
    const url = String(card.url || "").toLowerCase();
    return type === "pdf" || type === "magazine" || url.includes("/magazines/") || url.endsWith(".pdf") || url.includes(".pdf");
  }

  function isVideoCard(card) {
    const type = String(card.type || card.source_type || "").toLowerCase();
    const url = String(card.url || "").toLowerCase();
    return type === "video" || url.includes("youtube.com/watch") || url.includes("youtu.be/");
  }

  function isPodcastCard(card) {
    const type = String(card.type || card.source_type || "").toLowerCase();
    return type === "podcast";
  }

  function firstUsableArticle(articles) {
    return (articles || []).find(a => a && a.url);
  }

  function renderQuestion(question) {
    return `<div class="gbm-question">${esc(question)}</div>`;
  }

  function renderLoading(question) {
    welcome.style.display = "none";
    messages.innerHTML = `
      ${renderQuestion(question)}
      <div class="gbm-loading">
        <span class="gbm-dot"></span><span class="gbm-dot"></span><span class="gbm-dot"></span>
        <span>Searching Green Builder Media knowledge sources...</span>
      </div>
    `;
  }

  function renderHotTake(payload, articles) {
    const hot = payload.hot_take || payload.hotTake || payload.cognition_hot_take || {};

    const chartImage =
      hot.chart_image ||
      hot.chartImage ||
      hot.image ||
      hot.image_url ||
      hot.thumbnail ||
      hot.thumbnail_url ||
      "";

    const title =
      hot.title ||
      hot.article_title ||
      hot.articleTitle ||
      "";

    const caption =
      hot.caption ||
      hot.summary ||
      "";

    const imageBlob = String(chartImage || "").toLowerCase();
    const titleBlob = String(title || "").toLowerCase();
    const captionBlob = String(caption || "").toLowerCase();

    const isPlaceholder =
      !chartImage ||
      imageBlob.includes("fallback") ||
      imageBlob.includes("placeholder") ||
      imageBlob.includes("cognition%20button") ||
      imageBlob.includes("cognition button") ||
      imageBlob.includes("logo");

    const isDefaultCopy =
      titleBlob === "cognition smartdata" ||
      captionBlob.includes("as the hot take chart library is connected to the backend") ||
      captionBlob.includes("this area will automatically display");

    const weakTitle = title.trim().length < 8;
    const weakCaption = caption.trim().length < 60;

    if (isPlaceholder || isDefaultCopy || (weakTitle && weakCaption)) {
      return "";
    }

    const articleFallback = firstUsableArticle(articles);

    const articleUrl =
      hot.article_url ||
      hot.articleUrl ||
      hot.url ||
      (articleFallback ? articleFallback.url : COGNITION_SMART_DATA_URL);

    return `
      <div class="gbm-hot-take">
        <div class="gbm-hot-take-inner">
          <div class="gbm-hot-copy">
            <div class="gbm-hot-kicker">KEY INSIGHT</div>
            <div class="gbm-hot-title">${esc(title)}</div>
            <div class="gbm-hot-caption">${esc(caption)}</div>

            <div class="gbm-hot-links">
              <a class="gbm-hot-link gbm-hot-link-primary" href="${abs(articleUrl)}" target="_blank" rel="noopener">
                Read full analysis ↗
              </a>
              <a class="gbm-hot-link" href="${COGNITION_SMART_DATA_URL}" target="_blank" rel="noopener">
                More COGNITION insights ↗
              </a>
            </div>
          </div>

          <div class="gbm-hot-image-wrap">
            <a href="${abs(chartImage)}" target="_blank" rel="noopener">
              <img
                class="gbm-hot-image"
                src="${abs(chartImage)}"
                alt="COGNITION data graphic"
              />
            </a>
            <a class="gbm-expand-image" href="${abs(chartImage)}" target="_blank" rel="noopener">
              Expand image ↗
            </a>
          </div>
        </div>
      </div>
    `;
  }

  function renderVisual(payload, question) {
    currentMode = "visual";
    lastPayload = payload;

    const allCards = payload.cards || [];
    const allSources = payload.sources || [];

    const pdfCardsFromCards = allCards.filter(isPdfCard);
    const pdfCardsFromSources = allSources
      .filter(isPdfCard)
      .map(s => ({
        title: s.title,
        url: s.url,
        image: s.image || s.thumbnail || s.thumbnail_url || s.cover,
        cover: s.cover || s.image || s.thumbnail || s.thumbnail_url,
        source: s.attribution_label || s.source || "Green Builder Magazine",
        type: "pdf",
        page: s.page,
        excerpt: s.excerpt
      }));

    const videoCardsFromCards = allCards.filter(isVideoCard);
    const videoCardsFromSources = allSources.filter(isVideoCard);
    const podcastCardsFromCards = allCards.filter(isPodcastCard);
    const podcastCardsFromSources = allSources.filter(isPodcastCard);

    const articles =
      allCards.filter(c => {
        return !isPdfCard(c) && !isVideoCard(c) && !isPodcastCard(c);
      });

    const pdfs =
      dedupeByUrl([])
        .concat(payload.magazines || [])
        .concat(payload.pdfs || [])
        .concat(pdfCardsFromCards)
        .concat(pdfCardsFromSources);

    const videos =
      dedupeByUrl([])
        .concat(payload.videos || [])
        .concat(videoCardsFromCards)
        .concat(videoCardsFromSources);

    const podcasts =
      dedupeByUrl([])
        .concat(payload.podcasts || [])
        .concat(podcastCardsFromCards)
        .concat(podcastCardsFromSources);

    const hotTakeHtml = renderHotTake(payload, articles);

    messages.innerHTML = `
      ${renderQuestion(question)}

      <div class="gbm-answer-wrap">
        <div class="gbm-avatar">
          <img src="${esc(COGNITION_LOGO_URL)}" alt="COGNITION">
        </div>

        <div class="gbm-answer">
          ${esc(twoParagraphAnswer(payload.visual_summary || payload.answer || "")).replace(/\n/g,"<br>")}
        </div>
      </div>

      <div class="gbm-toggle">DIVE DEEPER WITH TEXT ONLY</div>

      ${hotTakeHtml && hotTakeHtml.trim() ? hotTakeHtml : ""}

      <div class="gbm-section-title">
  SUPPORTING RESOURCES
</div>

      <div class="gbm-grid">
        ${renderColumn("Articles", "article", articles, "No related article cards were returned for this query.")}
        ${renderColumn("PDFs & Guides", "pdf", pdfs, "No related PDF or guide cards were returned for this query.")}
        ${renderColumn("Videos", "video", videos, "Video results will appear here once the GBM YouTube index is connected.")}
        ${renderColumn("Podcasts", "podcast", podcasts, "Podcast results will appear here once the GBM podcast playlist is indexed.")}
      </div>
    `;

    const toggle = messages.querySelector(".gbm-toggle");
    if (toggle) {
      toggle.onclick = () => renderText(payload, question);
    }
  }

  function renderText(payload, question) {
    currentMode = "text";

    messages.innerHTML = `
      ${renderQuestion(question)}

      <div class="gbm-answer-wrap">
        <div class="gbm-avatar">
          <img src="${esc(COGNITION_LOGO_URL)}" alt="COGNITION">
        </div>
        <div class="gbm-answer">
          ${esc(payload.text_only_answer || payload.answer || "").replace(/\n/g,"<br>")}
        </div>
      </div>

      <div class="gbm-toggle">RETURN TO VISUAL DEEPDIVE</div>
    `;

    const toggle = messages.querySelector(".gbm-toggle");
    if (toggle) {
      toggle.onclick = () => renderVisual(payload, question);
    }
  }

  async function ask(question) {
    lastQuestion = question;
    submit.disabled = true;
    renderLoading(question);

    try {
      const res = await fetch(API_BASE.replace(/\/$/, "") + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          session_id: sessionId,
          page_url: window.location.href,
          referrer: document.referrer,
          user_agent: navigator.userAgent
        })
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }

      const payload = await res.json();
      lastPayload = payload;
      renderVisual(payload, question);
    } catch (err) {
      messages.innerHTML = `
        ${renderQuestion(question)}
        <div class="gbm-answer-wrap">
          <div class="gbm-avatar"><img src="${esc(COGNITION_LOGO_URL)}" alt="COGNITION"></div>
          <div class="gbm-answer">I’m sorry, the COGNITION DeepDive service could not complete that request. ${esc(err.message || "")}</div>
        </div>
      `;
    } finally {
      submit.disabled = false;
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    ask(question);
  });

  window.GBMDeepThink = {
    open() {
      panel.classList.add("gbm-open");
      input.focus();
    },
    close() {
      panel.classList.remove("gbm-open");
    },
    ask(question) {
      panel.classList.add("gbm-open");
      ask(question);
    },
    rerender() {
      if (!lastPayload || !lastQuestion) return;
      if (currentMode === "text") renderText(lastPayload, lastQuestion);
      else renderVisual(lastPayload, lastQuestion);
    }
  };
})();
```

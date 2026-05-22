(function () {
  if (window.GBM_DEEPTHINK_LOADED) return;
  window.GBM_DEEPTHINK_LOADED = true;

  const currentScript = document.currentScript;

  const API_BASE = (
    currentScript?.dataset.apiBase ||
    "https://gbm-visual-chatbot.onrender.com"
  ).replace(/\/$/, "");

  const CHATBOT_TITLE =
    currentScript?.dataset.chatbotTitle ||
    "COGNITION DeepDive";

  const COGNITION_LOGO_URL =
    currentScript?.dataset.logoUrl ||
    "https://www.greenbuildermedia.com/hubfs/Cognition%20DeepDive%20Images/cognition%20button.png";

  const COGNITION_SMART_DATA_URL =
    "https://www.greenbuildermedia.com/cognition-smart-data";

  const COGNITION_FALLBACK_CHART_URL =
    currentScript?.dataset.hotTakeImage ||
    "https://www.greenbuildermedia.com/hubfs/Cognition%20DeepDive%20Images/cognition%20button.png";

  const root = document.createElement("div");
  document.body.appendChild(root);

  let lastPayload = null;
  let currentMode = "visual";

  function abs(url) {
    if (!url) return "";
    const s = String(url).trim();
    if (s.startsWith("http://") || s.startsWith("https://")) return s;
    if (s.startsWith("/")) return API_BASE + s;
    return API_BASE + "/" + s.replace(/^\/+/, "");
  }

  function esc(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function icon(type) {
    const icons = {
      article: `<svg viewBox="0 0 24 24"><path d="M5 4h10l4 4v12H5z"/><path d="M15 4v5h5"/><path d="M8 13h8"/><path d="M8 17h6"/></svg>`,
      pdf: `<svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v5h5"/><path d="M8 15h2"/><path d="M13 15h2"/></svg>`,
      video: `<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9l5 3-5 3z"/></svg>`,
      podcast: `<svg viewBox="0 0 24 24"><circle cx="12" cy="11" r="3"/><path d="M6 11a6 6 0 0 1 12 0"/><path d="M12 14v7"/><path d="M9.5 21h5"/></svg>`,
      close: `<svg viewBox="0 0 24 24"><path d="M6 6l12 12"/><path d="M18 6L6 18"/></svg>`
    };
    return icons[type] || "";
  }

  root.innerHTML = `
  <style>
    .gbm-launcher {
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 999999;
      background: linear-gradient(135deg,#0087a7,#006d86);
      color: white;
      border-radius: 999px;
      padding: 10px 18px 10px 10px;
      font-family: Arial, sans-serif;
      font-weight: 900;
      letter-spacing: .02em;
      cursor: pointer;
      box-shadow: 0 10px 30px rgba(0,0,0,.25);
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .gbm-launcher-logo,
    .gbm-mark,
    .gbm-avatar {
      border-radius: 50%;
      overflow: hidden;
      position: relative;
      flex: 0 0 auto;
      background: transparent;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .gbm-launcher-logo {
      width: 60px;
      height: 60px;
    }

    .gbm-launcher-logo img {
      width: 60px;
      height: 60px;
      object-fit: contain;
      display: block;
    }

    .gbm-mark {
      width: 64px;
      height: 64px;
    }

    .gbm-mark img {
      width: 64px;
      height: 64px;
      object-fit: contain;
      display: block;
    }

    .gbm-avatar {
      width: 52px;
      height: 52px;
    }

    .gbm-avatar img {
      width: 52px;
      height: 52px;
      object-fit: contain;
      display: block;
    }

    .gbm-panel {
      position: fixed;
      top: 24px;
      bottom: 24px;
      right: 24px;
      left: auto;
      width: min(950px, calc(100vw - 80px));
      z-index: 999998;
      background: #f5f8f7;
      border-radius: 18px;
      display: none;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 30px 80px rgba(0,0,0,.35);
      border: 1px solid rgba(0,0,0,.08);
      font-family: Arial, sans-serif;
      color: #1f2937;
    }

    .gbm-header {
      background: linear-gradient(135deg,#0087a7,#006d86);
      color: white;
      padding: 18px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex: 0 0 auto;
    }

    .gbm-header-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .gbm-title {
      font-size: 22px;
      font-weight: 900;
      letter-spacing: -.02em;
    }

    .gbm-close {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      border: 0;
      background: rgba(255,255,255,.12);
      color: white;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .gbm-close svg,
    .gbm-icon svg {
      width: 18px;
      height: 18px;
      fill: none;
      stroke: currentColor;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .gbm-messages {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
    }

    .gbm-welcome {
      background: white;
      border-radius: 16px;
      border: 1px solid #dce5e2;
      padding: 18px;
      max-width: 700px;
      line-height: 1.55;
      box-shadow: 0 8px 24px rgba(0,0,0,.04);
    }

    .gbm-user {
      margin-left: auto;
      background: #e5f3ee;
      border: 1px solid #cce3db;
      border-radius: 16px;
      padding: 14px 18px;
      max-width: 70%;
      width: fit-content;
      margin-top: 22px;
      margin-bottom: 18px;
      font-weight: 700;
      line-height: 1.45;
    }

    .gbm-answer-wrap {
      display: flex;
      gap: 14px;
      align-items: flex-start;
    }

    .gbm-answer {
      flex: 1;
      background: white;
      border-radius: 16px;
      border: 1px solid #dce5e2;
      padding: 20px;
      line-height: 1.65;
      box-shadow: 0 8px 24px rgba(0,0,0,.04);
    }

    .gbm-answer a {
      color: #0087a7;
      text-decoration: none;
      font-weight: 800;
    }

.gbm-toggle {
  margin-top: 10px;
  margin-left: 102px;
  margin-bottom: 18px;
  color: #0087a7;
  font-size: 13px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: .06em;
  cursor: pointer;
  line-height: 1;
}
    .gbm-hot-take {
      margin-left: 60px;
      margin-top: 22px;
      margin-bottom: 28px;
      background: white;
      border: 1px solid #dce5e2;
      border-radius: 18px;
      box-shadow: 0 8px 24px rgba(0,0,0,.04);
      overflow: hidden;
    }

    .gbm-hot-take-inner {
      display: grid;
      grid-template-columns: minmax(0,.95fr) minmax(280px,1.05fr);
      align-items: stretch;
    }

    .gbm-hot-copy {
      padding: 22px;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }

    .gbm-hot-kicker {
      color: #0087a7;
      font-size: 13px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 10px;
    }

    .gbm-hot-title {
      font-size: 20px;
      line-height: 1.2;
      font-weight: 900;
      color: #163d35;
      margin-bottom: 12px;
    }

    .gbm-hot-caption {
      font-size: 14px;
      line-height: 1.55;
      color: #44514d;
      margin-bottom: 16px;
    }

    .gbm-hot-links {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 2px;
    }

    .gbm-hot-link {
      border-radius: 999px;
      border: 1px solid #0087a7;
      background: white;
      color: #0087a7;
      font-size: 12px;
      font-weight: 900;
      padding: 9px 13px;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .gbm-hot-link-primary {
      background: #0087a7;
      color: white;
    }

    .gbm-hot-image-wrap {
      background: #edf5f2;
      padding: 18px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 10px;
    }

    .gbm-hot-image {
      width: 100%;
      max-height: 360px;
      object-fit: contain;
      border-radius: 12px;
      background: white;
      display: block;
      box-shadow: 0 8px 24px rgba(0,0,0,.06);
    }

    .gbm-expand-image {
      align-self: flex-end;
      color: #0087a7;
      font-size: 12px;
      font-weight: 900;
      text-decoration: none;
      text-transform: uppercase;
      letter-spacing: .05em;
    }

    .gbm-section-title {
      margin-top: 24px;
      margin-bottom: 12px;
      margin-left: 60px;
      color: #0087a7;
      font-size: 14px;
      font-weight: 900;
      letter-spacing: .06em;
      text-transform: uppercase;
    }

    .gbm-grid {
      display: grid;
      grid-template-columns: repeat(4,minmax(0,1fr));
      gap: 14px;
      margin-left: 60px;
      margin-bottom: 26px;
    }

    .gbm-column {
      background: white;
      border-radius: 16px;
      border: 1px solid #dce5e2;
      padding: 14px;
      box-shadow: 0 8px 24px rgba(0,0,0,.04);
      min-width: 0;
    }

    .gbm-column-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
      font-weight: 900;
      color: #163d35;
      font-size: 14px;
    }

    .gbm-icon {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: #e6f3ee;
      color: #0087a7;
      display: flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
    }

    .gbm-count {
      margin-left: auto;
      background: #edf5f2;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 11px;
      color: #66736f;
      font-weight: 900;
    }

    .gbm-card {
      border-top: 1px solid #edf2f2;
      padding-top: 12px;
      margin-top: 12px;
    }

    .gbm-card:first-of-type {
      border-top: 0;
      padding-top: 0;
      margin-top: 0;
    }

    .gbm-thumb {
      width: 100%;
      aspect-ratio: 16/9;
      object-fit: cover;
      border-radius: 10px;
      background: #edf2f2;
      display: block;
      margin-bottom: 10px;
    }

    .gbm-card-title {
      font-size: 13px;
      line-height: 1.35;
      font-weight: 900;
      margin-bottom: 6px;
    }

    .gbm-card-meta {
      font-size: 12px;
      line-height: 1.4;
      color: #66736f;
      margin-bottom: 8px;
    }

    .gbm-button {
      width: 100%;
      border-radius: 999px;
      border: 1px solid #0087a7;
      background: white;
      color: #0087a7;
      font-size: 12px;
      font-weight: 900;
      padding: 8px 10px;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      justify-content: center;
      align-items: center;
      box-sizing: border-box;
    }

    .gbm-inputbar {
      background: white;
      border-top: 1px solid #dce5e2;
      padding: 16px;
      display: flex;
      gap: 10px;
      flex: 0 0 auto;
    }

    .gbm-input {
      flex: 1;
      border-radius: 999px;
      border: 1px solid #d4ddda;
      padding: 14px 16px;
      font-size: 15px;
      outline: none;
    }

    .gbm-send {
      width: auto;
      min-width: 86px;
      height: 48px;
      border-radius: 999px;
      border: 0;
      background: #0087a7;
      color: white;
      cursor: pointer;
      font-weight: 900;
      letter-spacing: .04em;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 18px;
    }

    .gbm-player {
      width: 100%;
      aspect-ratio: 16/9;
      border: 0;
      border-radius: 10px;
      overflow: hidden;
      margin-bottom: 10px;
      background: #111;
    }

    .gbm-empty-card {
      color: #66736f;
      font-size: 12px;
      line-height: 1.45;
      background: #f8fbfa;
      border-radius: 12px;
      padding: 12px;
      border: 1px dashed #dce5e2;
    }

    @media (max-width: 1100px) {
      .gbm-grid {
        grid-template-columns: repeat(2,minmax(0,1fr));
      }
    }
.gbm-hot-take:has(img[src*="Cognition%20Button"]),
.gbm-hot-take:has(img[src*="cognition"]),
.gbm-hot-take:has(img[src*="placeholder"]),
.gbm-hot-take:has(img[src*="fallback"]) {
  display: none !important;
}
    @media (max-width: 800px) {
      .gbm-panel {
        inset: 0;
        width: auto;
        border-radius: 0;
      }

      .gbm-grid {
        grid-template-columns: 1fr;
      }

      .gbm-hot-take-inner {
        grid-template-columns: 1fr;
      }

      .gbm-grid,
      .gbm-hot-take,
      .gbm-section-title,
      .gbm-toggle {
        margin-left: 0;
      }

      .gbm-user {
        max-width: 92%;
      }
    }
  </style>

  <div class="gbm-launcher">
    <span class="gbm-launcher-logo">
      <img src="${esc(COGNITION_LOGO_URL)}" alt="">
    </span>

    <span style="line-height:1.05;">
      COGNITION<br>
      <span style="font-weight:700;">DeepDive</span>
    </span>
  </div>

  <div class="gbm-panel">
    <div class="gbm-header">
      <div class="gbm-header-left">
        <div class="gbm-mark">
          <img src="${esc(COGNITION_LOGO_URL)}" alt="COGNITION">
        </div>
        <div class="gbm-title">COGNITION DeepDive</div>
      </div>

      <button class="gbm-close" aria-label="Close chatbot">
        ${icon("close")}
      </button>
    </div>

    <div class="gbm-messages">
      <div class="gbm-welcome">
        Make your query, and tap the power of our exclusive COGNITION SmartData,
        combining new research with 25 years of expertise in sustainable building.
      </div>
    </div>

    <div class="gbm-inputbar">
      <input class="gbm-input" placeholder="Ask us anything..." />
      <button class="gbm-send">SEND</button>
    </div>
  </div>
  `;

  const launcher = root.querySelector(".gbm-launcher");
  const panel = root.querySelector(".gbm-panel");
  const closeBtn = root.querySelector(".gbm-close");
  const messages = root.querySelector(".gbm-messages");
  const input = root.querySelector(".gbm-input");
  const sendBtn = root.querySelector(".gbm-send");

  launcher.onclick = () => {
    launcher.style.display = "none";
    panel.style.display = "flex";
    input.focus();
  };

  closeBtn.onclick = () => {
    panel.style.display = "none";
    launcher.style.display = "flex";
  };

  function renderQuestion(q) {
    return `<div class="gbm-user">${esc(q)}</div>`;
  }

  function youtubeId(url) {
    if (!url) return "";
    const watch = String(url).match(/[?&]v=([^&]+)/);
    if (watch) return watch[1];
    const short = String(url).match(/youtu\.be\/([^?&]+)/);
    if (short) return short[1];
    const embed = String(url).match(/embed\/([^?&/]+)/);
    if (embed) return embed[1];
    return "";
  }

  function isPdfCard(card) {
    const t = String(card.type || card.source_type || card.attribution_label || card.source || "").toLowerCase();
    const u = String(card.url || "").toLowerCase();
    const title = String(card.title || "").toLowerCase();

    return (
      t === "pdf" ||
      t === "magazine" ||
      t.includes("magazine") ||
      t.includes("pdf") ||
      u.includes(".pdf") ||
      u.includes("/magazines/") ||
      title.includes("(pdf") ||
      title.includes("magazine")
    );
  }

  function isVideoCard(card) {
    const t = String(card.type || card.source_type || "").toLowerCase();
    const u = String(card.url || "").toLowerCase();
    return (
      t === "video" ||
      t === "youtube" ||
      u.includes("youtube.com/watch") ||
      u.includes("youtu.be/")
    );
  }

  function isPodcastCard(card) {
    const t = String(card.type || card.source_type || "").toLowerCase();
    const u = String(card.url || "").toLowerCase();
    const title = String(card.title || "").toLowerCase();
    return (
      t === "podcast" ||
      u.includes("playlist?list=plwqacwozaqyfamz7xa2mz2acdlvaukflv") ||
      title.includes("podcast")
    );
  }

  function dedupeByUrl(items) {
    const seen = new Set();
    const out = [];

    (items || []).forEach(item => {
      const key = String(item.url || item.title || "").trim();
      if (!key || seen.has(key)) return;
      seen.add(key);
      out.push(item);
    });

    return out;
  }

  function renderColumn(title, type, items, emptyText) {
    const visible = dedupeByUrl(items || []).slice(0, 1);

    return `
      <div class="gbm-column">
        <div class="gbm-column-header">
          <div class="gbm-icon">${icon(type)}</div>
          ${esc(title)}
          <div class="gbm-count">${visible.length}</div>
        </div>

        ${visible.length ? visible.map(item => renderCard(type, item)).join("") : `
          <div class="gbm-empty-card">
            ${esc(emptyText || "No related content found yet.")}
          </div>
        `}
      </div>
    `;
  }

  function pdfCoverFromUrl(url) {
    if (!url) return "/assets/covers/fallback-magazine.jpg";

    const raw = String(url)
      .split("/magazines/")
      .pop()
      .split("?")[0]
      .split("#")[0]
      .replace(/\.pdf$/i, "");

    const decoded = decodeURIComponent(raw);

    const hyphenName = decoded
      .replace(/[^A-Za-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") + ".jpg";

    return "/assets/covers/" + hyphenName;
  }

  function renderCard(type, item) {
    const isVideo = type === "video" || type === "podcast";
    const yid = isVideo ? youtubeId(item.url || item.source_url || "") : "";

    const fallback =
      type === "pdf"
        ? "/assets/covers/fallback-magazine.jpg"
        : "/assets/thumbs/fallback-article.jpg";

    const url = item.url || item.source_url || "#";

    const img =
      type === "pdf"
        ? pdfCoverFromUrl(url)
        : (
            item.image ||
            item.thumbnail ||
            item.thumbnail_url ||
            item.cover ||
            item.remote_image ||
            (yid
              ? "https://img.youtube.com/vi/" + yid + "/hqdefault.jpg"
              : fallback)
          );

    const source =
      item.source ||
      item.issue ||
      item.category ||
      item.attribution_label ||
      (type === "podcast"
        ? "Green Builder Media Network"
        : type === "video"
        ? "Green Builder Media YouTube"
        : "Green Builder Media");

    return `
      <div class="gbm-card">
        ${
          isVideo && yid
            ? `
              <iframe
                class="gbm-player"
                src="https://www.youtube.com/embed/${esc(yid)}"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowfullscreen
              ></iframe>
            `
            : `
              <img
                class="gbm-thumb"
                src="${abs(img)}"
                onerror="this.onerror=null;this.src='${abs(fallback)}';"
              />
            `
        }

        <div class="gbm-card-title">${esc(item.title || "Untitled")}</div>

        <div class="gbm-card-meta">
          ${esc(source)}${item.page ? " · p. " + esc(item.page) : ""}
        </div>

        <a class="gbm-button" href="${abs(url)}" target="_blank" rel="noopener">
          ${
            type === "video"
              ? "Watch on YouTube ↗"
              : type === "podcast"
              ? "Listen / Watch ↗"
              : type === "pdf"
              ? "View PDF ↗"
              : "Read Article ↗"
          }
        </a>
      </div>
    `;
  }

  function twoParagraphAnswer(text) {
    const raw = String(text || "").trim();
    if (!raw) return "";

    const paragraphs = raw
      .split(/\n\s*\n/)
      .map(p => p.trim())
      .filter(Boolean);

    if (paragraphs.length >= 2) {
      return paragraphs.slice(0, 2).join("\n\n");
    }

    return raw;
  }

  function firstUsableArticle(cards) {
    return (cards || []).find(card => card && card.url && card.title) || null;
  }

  function renderHotTake(payload, articles) {
    const hot = payload.hot_take || payload.hotTake || payload.cognition_hot_take || {};
    const articleFallback = firstUsableArticle(articles);

    const title =
      hot.title ||
      hot.article_title ||
      hot.articleTitle ||
      "COGNITION SmartData";

    const articleUrl =
      hot.article_url ||
      hot.articleUrl ||
      hot.url ||
      (articleFallback ? articleFallback.url : COGNITION_SMART_DATA_URL);

    const chartImage =
      hot.chart_image ||
      hot.chartImage ||
      hot.image ||
      hot.image_url ||
      hot.thumbnail ||
      hot.thumbnail_url ||
      COGNITION_FALLBACK_CHART_URL;

    const caption =
      hot.caption ||
      hot.summary ||
      "COGNITION SmartData highlights the market signals, consumer behavior, and building-science trends behind this topic. As the Hot Take chart library is connected to the backend, this area will automatically display the most relevant data graphic for each query.";

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
                onerror="this.onerror=null;this.src='${abs(COGNITION_FALLBACK_CHART_URL)}';"
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

      ${renderHotTake(payload, articles)}

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

      <div class="gbm-toggle">RETURN TO VISUAL MODE</div>
    `;

    const toggle = messages.querySelector(".gbm-toggle");
    if (toggle) {
      toggle.onclick = () => renderVisual(payload, question);
    }
  }

  async function askQuestion() {
    const question = input.value.trim();
    if (!question) return;

    messages.innerHTML = `
      ${renderQuestion(question)}

      <div class="gbm-answer-wrap">
        <div class="gbm-avatar">
          <img src="${esc(COGNITION_LOGO_URL)}" alt="COGNITION">
        </div>

        <div class="gbm-answer">Thinking...</div>
      </div>
    `;

    input.value = "";

    try {
      const response = await fetch(API_BASE + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          session_id: "web-" + Date.now(),
          page_url: window.location.href,
          referrer: document.referrer || "",
          user_agent: navigator.userAgent || ""
        })
      });

      const payload = await response.json();
      renderVisual(payload, question);

    } catch (err) {
      messages.innerHTML = `
        ${renderQuestion(question)}

        <div class="gbm-answer-wrap">
          <div class="gbm-avatar">
            <img src="${esc(COGNITION_LOGO_URL)}" alt="COGNITION">
          </div>

          <div class="gbm-answer">
            Sorry — the chatbot encountered an error.
          </div>
        </div>
      `;
    }
  }

  sendBtn.onclick = askQuestion;

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      askQuestion();
    }
  });

})();

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
  let currentCardQuery = "";

  function abs(url) {
    if (!url) return "";
    const s = String(url).trim();
    if (s.startsWith("http://") || s.startsWith("https://")) return s;
    if (s.startsWith("/")) return API_BASE + s;
    return API_BASE + "/" + s.replace(/^\/+/, "");
  }

  function transcriptUrl(item) {
    if (!item) return "";

    const direct =
      item.transcript_url ||
      item.transcriptUrl ||
      item.google_drive_transcript ||
      item.drive_transcript_url ||
      item.driveTranscriptUrl ||
      item.transcript_drive_url ||
      item.transcriptDriveUrl ||
      item.transcript_file_url ||
      item.transcriptFileUrl ||
      item.transcript_path ||
      item.transcriptPath ||
      "";

    if (direct) return abs(direct);

    if ((item.has_transcript || item.transcript_file || item.transcript_excerpt) && item.video_id) {
      return abs(`/api/youtube-transcript/${encodeURIComponent(item.video_id)}`);
    }

    return "";
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
      display: flex;
      flex-direction: column;
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
      display: none;
    }

    .gbm-card {
      border-top: 1px solid #edf2f2;
      padding-top: 12px;
      margin-top: 12px;
      display: flex;
      flex-direction: column;
      flex: 1 1 auto;
      min-height: 100%;
    }

    .gbm-card:first-of-type {
      border-top: 0;
      padding-top: 0;
      margin-top: 0;
    }

    .gbm-card-media {
      position: relative;
      width: 100%;
      aspect-ratio: 16/9;
      margin-bottom: 10px;
    }

    .gbm-card-media .gbm-thumb,
    .gbm-card-media .gbm-player {
      margin-bottom: 0;
    }

    .gbm-transcript-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      z-index: 5;
      background: rgba(255,255,255,.96);
      border: 2px solid #0087a7;
      color: #006d86;
      text-decoration: none;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: .04em;
      padding: 6px 10px;
      border-radius: 999px;
      text-transform: uppercase;
      transition: all .18s ease;
      backdrop-filter: blur(4px);
      box-shadow: 0 2px 8px rgba(0,0,0,.15);
    }

    .gbm-transcript-btn:hover {
      background: #0087a7;
      color: white;
      transform: translateY(-1px);
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

    .gbm-card-desc {
      font-size: 12px;
      line-height: 1.4;
      color: #485955;
      margin: 2px 0 8px;
    }

    .gbm-card-actions {
      margin-top: auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
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

    .gbm-card > .gbm-button:not(.gbm-button-secondary) {
      margin-top: 0;
    }

    .gbm-button-secondary {
      margin-top: 0;
      border-color: #bfdad5;
      background: #f4fbf9;
      color: #0e6f82;
    }

    .gbm-button-secondary:hover {
      background: #e8f6f3;
    }

    .gbm-more-like-btn {
      font-family: inherit;
      text-transform: uppercase;
    }

    .gbm-down-arrow {
      display: inline-block;
      margin-left: 6px;
      line-height: 1;
    }

    .gbm-related-results {
      margin: 14px 0 0 0;
      grid-column: 1 / -1;
    }

    .gbm-related-panel {
      background: #f7fbfa;
      border: 1px solid #d8ebe7;
      border-radius: 18px;
      padding: 14px;
      margin-top: 12px;
    }

    .gbm-related-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
      color: #143b45;
      font-size: 13px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .06em;
    }

    .gbm-related-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .gbm-related-loading,
    .gbm-related-error,
    .gbm-related-empty {
      color: #66736f;
      font-size: 13px;
      line-height: 1.45;
      padding: 10px 0;
    }

    .gbm-related-close {
      border: 0;
      background: transparent;
      color: #0e6f82;
      cursor: pointer;
      font-size: 12px;
      font-weight: 900;
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
      .gbm-related-grid {
        grid-template-columns: 1fr;
      }

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

  function cardDescription(type, item) {
    const raw =
      item.card_description ||
      item.short_description ||
      item.description ||
      item.summary ||
      item.excerpt ||
      item.caption ||
      "";

    let clean = String(raw).replace(/\s+/g, " ").trim();

    if (!clean) {
      if (type === "video") return "A related Green Builder Media video on this topic.";
      if (type === "podcast") return "A related Green Builder Media podcast episode on this topic.";
      if (type === "pdf") return "A related Green Builder Media magazine or guide resource.";
      return "A related Green Builder Media article on this topic.";
    }

    const firstSentence = clean.match(/^.{35,175}?[.!?](\s|$)/);
    if (firstSentence) return firstSentence[0].trim();

    if (clean.length > 150) {
      clean = clean.slice(0, 147).replace(/\s+\S*$/, "").trim() + "...";
    }

    return clean;
  }

  function moreLikeThisUrl(type, item) {
    const base = "https://www.greenbuildermedia.com/hs-search-results";

    const rawTopic =
      currentCardQuery ||
      item.search_query ||
      item.topic ||
      item.category ||
      item.title ||
      "";

    const topic = String(rawTopic)
      .replace(/\s+/g, " ")
      .trim();

    const scopedTopic = topic || (
      type === "pdf"
        ? "green building guides"
        : type === "video"
        ? "green building videos"
        : type === "podcast"
        ? "green building podcast"
        : "green building articles"
    );

    return base + "?term=" + encodeURIComponent(scopedTopic);
  }

  function renderCard(type, item, showMore = true) {
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
        <div class="gbm-card-media">
          ${
            type === "video" && transcriptUrl(item)
              ? `
                <a
                  class="gbm-transcript-btn"
                  href="${esc(transcriptUrl(item))}"
                  target="_blank"
                  rel="noopener"
                >FULL TRANSCRIPT</a>
              `
              : ""
          }

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
        </div>

        <div class="gbm-card-title">${esc(item.title || "Untitled")}</div>

        <div class="gbm-card-desc">${esc(cardDescription(type, item))}</div>

        <div class="gbm-card-meta">
          ${esc(source)}${item.page ? " &middot; p. " + esc(item.page) : ""}
        </div>

        <div class="gbm-card-actions">
          <a class="gbm-button" href="${abs(url)}" target="_blank" rel="noopener">
            ${
              type === "video"
                ? "Watch on YouTube"
                : type === "podcast"
                ? "Listen / Watch"
                : type === "pdf"
                ? "View PDF"
                : "Read Article"
            }
          </a>

          ${
            showMore
              ? `
                <button
                  class="gbm-button gbm-button-secondary gbm-more-like-btn"
                  type="button"
                  data-more-type="${esc(type)}"
                  data-more-title="${esc(item.title || "")}"
                  data-more-url="${esc(url)}"
                >
                  MORE LIKE THIS <span class="gbm-down-arrow" aria-hidden="true">&darr;</span>
                </button>
              `
              : ""
          }
        </div>
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
                Read full analysis
              </a>
              <a class="gbm-hot-link" href="${COGNITION_SMART_DATA_URL}" target="_blank" rel="noopener">
                More COGNITION insights
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
              Expand image
            </a>
          </div>
        </div>
      </div>
    `;
  }

  function bindMoreLikeButtons() {
    messages.querySelectorAll(".gbm-more-like-btn").forEach(btn => {
      btn.addEventListener("click", () => loadMoreLikeThis(btn));
    });
  }

  async function loadMoreLikeThis(button) {
    const container = messages.querySelector("#gbm-related-results");
    if (!container) return;

    const type = button.getAttribute("data-more-type") || "article";
    const title = button.getAttribute("data-more-title") || "";
    const url = button.getAttribute("data-more-url") || "";

    container.innerHTML = `
      <div class="gbm-related-panel">
        <div class="gbm-related-head">
          <span>More like this: ${esc(title || type)}</span>
          <button class="gbm-related-close" type="button">Close</button>
        </div>
        <div class="gbm-related-loading">Finding related Green Builder Media resources...</div>
      </div>
    `;

    const closeBtn = container.querySelector(".gbm-related-close");
    if (closeBtn) {
      closeBtn.onclick = () => {
        container.innerHTML = "";
      };
    }

    try {
      const params = new URLSearchParams({
        q: currentCardQuery || "",
        type,
        title,
        url,
        limit: "4"
      });

      const response = await fetch(API_BASE + "/api/related-cards?" + params.toString());

      if (!response.ok) {
        throw new Error("Related-card search failed with HTTP " + response.status);
      }

      const payload = await response.json();
      const cards = payload.cards || [];

      if (!cards.length) {
        container.innerHTML = `
          <div class="gbm-related-panel">
            <div class="gbm-related-head">
              <span>More like this: ${esc(title || type)}</span>
              <button class="gbm-related-close" type="button">Close</button>
            </div>
            <div class="gbm-related-empty">No additional closely related resources were found.</div>
          </div>
        `;
      } else {
        container.innerHTML = `
          <div class="gbm-related-panel">
            <div class="gbm-related-head">
              <span>More like this: ${esc(title || type)}</span>
              <button class="gbm-related-close" type="button">Close</button>
            </div>
            <div class="gbm-related-grid">
              ${cards.map(card => renderCard(type, card, false)).join("")}
            </div>
          </div>
        `;
      }

      const closeAgain = container.querySelector(".gbm-related-close");
      if (closeAgain) {
        closeAgain.onclick = () => {
          container.innerHTML = "";
        };
      }
    } catch (err) {
      container.innerHTML = `
        <div class="gbm-related-panel">
          <div class="gbm-related-head">
            <span>More like this: ${esc(title || type)}</span>
            <button class="gbm-related-close" type="button">Close</button>
          </div>
          <div class="gbm-related-error">${esc(err.message || "Unable to load related resources.")}</div>
        </div>
      `;

      const closeBtn = container.querySelector(".gbm-related-close");
      if (closeBtn) {
        closeBtn.onclick = () => {
          container.innerHTML = "";
        };
      }
    }
  }

  function renderVisual(payload, question) {
    currentMode = "visual";
    lastPayload = payload;
    currentCardQuery = question || "";

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

      <div id="gbm-related-results" class="gbm-related-results"></div>
    `;

    const toggle = messages.querySelector(".gbm-toggle");
    if (toggle) {
      toggle.onclick = () => renderText(payload, question);
    }

    bindMoreLikeButtons();
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
            Sorry â€” the chatbot encountered an error.
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

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
    "GBM Deep Think";

  const GBM_YOUTUBE_CHANNEL =
    "https://www.youtube.com/user/greenbuildermedia";

  const GBM_PODCAST_PLAYLIST =
    "https://youtube.com/playlist?list=PLwQAcwOzaQyfAMZ7xA2Mz2acdLVauKFlV&si=vTbLmV5EuNhVcZy-";

  const root = document.createElement("div");
  document.body.appendChild(root);

  let lastPayload = null;
  let currentMode = "visual";

  function abs(url) {
    if (!url) return "";
    if (url.startsWith("http")) return url;
    if (url.startsWith("#")) return url;
    return API_BASE + url;
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
      article: `
        <svg viewBox="0 0 24 24">
          <path d="M5 4h10l4 4v12H5z"/>
          <path d="M15 4v5h5"/>
          <path d="M8 13h8"/>
          <path d="M8 17h6"/>
        </svg>
      `,
      pdf: `
        <svg viewBox="0 0 24 24">
          <path d="M6 3h9l4 4v14H6z"/>
          <path d="M15 3v5h5"/>
          <path d="M8 15h2"/>
          <path d="M13 15h2"/>
        </svg>
      `,
      video: `
        <svg viewBox="0 0 24 24">
          <rect x="3" y="5" width="18" height="14" rx="2"/>
          <path d="M10 9l5 3-5 3z"/>
        </svg>
      `,
      podcast: `
        <svg viewBox="0 0 24 24">
          <circle cx="12" cy="11" r="3"/>
          <path d="M6 11a6 6 0 0 1 12 0"/>
          <path d="M12 14v7"/>
          <path d="M9.5 21h5"/>
        </svg>
      `,
      insight: `
        <svg viewBox="0 0 24 24">
          <path d="M9 18h6"/>
          <path d="M10 22h4"/>
          <path d="M12 2a7 7 0 0 0-4 12.7c.7.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/>
        </svg>
      `,
      check: `
        <svg viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="9"/>
          <path d="M8 12.5l2.5 2.5L16 9"/>
        </svg>
      `,
      info: `
        <svg viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="9"/>
          <path d="M12 10v6"/>
          <path d="M12 7h.01"/>
        </svg>
      `,
      close: `
        <svg viewBox="0 0 24 24">
          <path d="M6 6l12 12"/>
          <path d="M18 6L6 18"/>
        </svg>
      `
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
      background: #007565;
      color: white;
      border-radius: 999px;
      padding: 14px 22px;
      font-family: Arial, sans-serif;
      font-weight: 900;
      letter-spacing: .04em;
      cursor: pointer;
      box-shadow: 0 10px 30px rgba(0,0,0,.25);
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
      background: linear-gradient(135deg,#007565,#005447);
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

    .gbm-mark {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: rgba(255,255,255,.18);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      font-size: 12px;
      letter-spacing: .02em;
    }

    .gbm-title {
      font-size: 22px;
      font-weight: 900;
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

    .gbm-avatar {
      width: 46px;
      height: 46px;
      border-radius: 50%;
      background: #007565;
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      font-size: 12px;
      letter-spacing: .02em;
      flex: 0 0 auto;
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
      color: #007565;
      text-decoration: none;
      font-weight: 800;
    }

    .gbm-toggle {
      margin-top: 18px;
      margin-left: 60px;
      color: #007565;
      font-size: 13px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .06em;
      cursor: pointer;
    }

    .gbm-section-title {
      margin-top: 24px;
      margin-bottom: 12px;
      margin-left: 60px;
      color: #007565;
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
      color: #007565;
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
      border: 1px solid #007565;
      background: white;
      color: #007565;
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

    .gbm-insights {
      display: grid;
      grid-template-columns: repeat(3,minmax(0,1fr));
      gap: 14px;
      margin-left: 60px;
      margin-bottom: 26px;
    }

    .gbm-insight {
      background: white;
      border-radius: 16px;
      border: 1px solid #dce5e2;
      padding: 16px;
      display: flex;
      gap: 12px;
      box-shadow: 0 8px 24px rgba(0,0,0,.04);
    }

    .gbm-insight-copy strong {
      display: block;
      margin-bottom: 6px;
      font-size: 14px;
    }

    .gbm-insight-copy {
      font-size: 13px;
      line-height: 1.45;
      color: #44514d;
    }

    .gbm-recommended {
      display: grid;
      grid-template-columns: repeat(4,minmax(0,1fr));
      gap: 14px;
      margin-left: 60px;
      margin-bottom: 26px;
    }

    .gbm-rec {
      background: white;
      border-radius: 16px;
      overflow: hidden;
      border: 1px solid #dce5e2;
      text-decoration: none;
      color: inherit;
      box-shadow: 0 8px 24px rgba(0,0,0,.04);
    }

    .gbm-rec img {
      width: 100%;
      height: 130px;
      object-fit: cover;
      display: block;
    }

    .gbm-rec-title {
      padding: 12px;
      font-size: 13px;
      line-height: 1.35;
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
      background: #007565;
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
      .gbm-grid,
      .gbm-recommended {
        grid-template-columns: repeat(2,minmax(0,1fr));
      }
    }

    @media (max-width: 800px) {

      .gbm-panel {
        inset: 0;
        width: auto;
        border-radius: 0;
      }

      .gbm-grid,
      .gbm-recommended,
      .gbm-insights {
        grid-template-columns: 1fr;
      }

      .gbm-grid,
      .gbm-recommended,
      .gbm-insights,
      .gbm-section-title,
      .gbm-toggle {
        margin-left: 0;
      }

      .gbm-user {
        max-width: 92%;
      }
    }

  </style>

  <div class="gbm-launcher">GBM DEEP THINK</div>

  <div class="gbm-panel">

    <div class="gbm-header">
      <div class="gbm-header-left">
        <div class="gbm-mark">GBM</div>
        <div class="gbm-title">${esc(CHATBOT_TITLE)}</div>
      </div>

      <button class="gbm-close" aria-label="Close chatbot">
        ${icon("close")}
      </button>
    </div>

    <div class="gbm-messages">

      <div class="gbm-welcome">
        Ask us anything about sustainable building, electrification,
        resilience, housing trends, products, climate tech,
        or Green Builder Media research.
      </div>

    </div>

    <div class="gbm-inputbar">
      <input
        class="gbm-input"
        placeholder="Ask us anything..."
      />

      <button class="gbm-send">
        SEND
      </button>
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
    launcher.style.display = "block";
  };

  function renderQuestion(q) {
    return `
      <div class="gbm-user">
        ${esc(q)}
      </div>
    `;
  }

  function renderInsights(data) {
    const insights = data.key_insights || [];
    if (!insights.length) return "";

    return `
      <div class="gbm-insights">

        ${insights.slice(0,3).map((item, idx) => {
          const iconName =
            idx === 0 ? "insight" :
            idx === 1 ? "check" :
            "info";

          return `
            <div class="gbm-insight">

              <div class="gbm-icon">
                ${icon(iconName)}
              </div>

              <div class="gbm-insight-copy">
                <strong>${esc(item.title || "Insight")}</strong>
                ${esc(item.text || "")}
              </div>

            </div>
          `;
        }).join("")}

      </div>
    `;
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
    const visible = dedupeByUrl(items || []).slice(0,2);

    return `
      <div class="gbm-column">

        <div class="gbm-column-header">

          <div class="gbm-icon">
            ${icon(type)}
          </div>

          ${esc(title)}

          <div class="gbm-count">
            ${visible.length}
          </div>

        </div>

        ${visible.length ? visible.map(item => renderCard(type, item)).join("") : `
          <div class="gbm-empty-card">
            ${esc(emptyText || "No related content found yet.")}
          </div>
        `}

      </div>
    `;
  }

  function renderCard(type, item) {
    const isVideo = type === "video" || type === "podcast";
    const yid = isVideo ? youtubeId(item.url || item.source_url || "") : "";

    const fallback =
      type === "pdf"
        ? "/assets/covers/fallback-magazine.jpg"
        : "/assets/thumbs/fallback-article.jpg";

    const img =
      item.image ||
      item.thumbnail ||
      item.thumbnail_url ||
      item.cover ||
      item.remote_image ||
      (yid
        ? "https://img.youtube.com/vi/" + yid + "/hqdefault.jpg"
        : fallback);

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

    const url = item.url || item.source_url || "#";

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

        <div class="gbm-card-title">
          ${esc(item.title || "Untitled")}
        </div>

        <div class="gbm-card-meta">
          ${esc(source)}${item.page ? " · p. " + esc(item.page) : ""}
        </div>

        <a
          class="gbm-button"
          href="${abs(url)}"
          target="_blank"
          rel="noopener"
        >
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

  function renderRecommended(cards) {
    if (!cards || !cards.length) return "";

    return `
      <div class="gbm-section-title">
        RECOMMENDED READING
      </div>

      <div class="gbm-recommended">

        ${cards.slice(0,4).map(card => {
          const img =
            card.image ||
            card.thumbnail ||
            card.thumbnail_url ||
            "/assets/thumbs/fallback-article.jpg";

          return `
            <a
              class="gbm-rec"
              href="${abs(card.url || "#")}"
              target="_blank"
              rel="noopener"
            >

              <img
                src="${abs(img)}"
                onerror="this.onerror=null;this.src='${abs('/assets/thumbs/fallback-article.jpg')}';"
              />

              <div class="gbm-rec-title">
                ${esc(card.title || "Untitled")}
              </div>

            </a>
          `;
        }).join("")}

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
          GBM
        </div>

        <div class="gbm-answer">
          ${esc(payload.visual_summary || payload.answer || "")
            .replace(/\n/g,"<br>")}
        </div>

      </div>

      ${renderInsights(payload)}

      <div class="gbm-section-title">
        DIVE DEEPER WITH TEXT ONLY
      </div>

      <div class="gbm-grid">

        ${renderColumn("Articles","article",articles,"No related article cards were returned for this query.")}

        ${renderColumn("PDFs & Guides","pdf",pdfs,"No related PDF or guide cards were returned for this query.")}

        ${renderColumn("Videos","video",videos,"Video results will appear here once the GBM YouTube index is connected.")}

        ${renderColumn("Podcasts","podcast",podcasts,"Podcast results will appear here once the GBM podcast playlist is indexed.")}

      </div>

      ${renderRecommended(articles.slice(2))}

    `;

    const toggle = messages.querySelector(".gbm-toggle");
    if (toggle) {
      toggle.onclick = () => {
        renderText(payload, question);
      };
    }
  }

  function renderText(payload, question) {
    currentMode = "text";

    messages.innerHTML = `

      ${renderQuestion(question)}

      <div class="gbm-answer-wrap">

        <div class="gbm-avatar">
          GBM
        </div>

        <div class="gbm-answer">
          ${esc(payload.text_only_answer || payload.answer || "")
            .replace(/\n/g,"<br>")}
        </div>

      </div>

      <div class="gbm-toggle">
        RETURN TO VISUAL MODE
      </div>

    `;

    const toggle = messages.querySelector(".gbm-toggle");
    if (toggle) {
      toggle.onclick = () => {
        renderVisual(payload, question);
      };
    }
  }

  async function askQuestion() {
    const question = input.value.trim();
    if (!question) return;

    messages.innerHTML = `
      ${renderQuestion(question)}

      <div class="gbm-answer-wrap">

        <div class="gbm-avatar">
          GBM
        </div>

        <div class="gbm-answer">
          Thinking...
        </div>

      </div>
    `;

    input.value = "";

    try {
      const response = await fetch(
        API_BASE + "/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            question,
            session_id: "web-" + Date.now(),
            page_url: window.location.href,
            referrer: document.referrer || "",
            user_agent: navigator.userAgent || ""
          })
        }
      );

      const payload = await response.json();

      renderVisual(
        payload,
        question
      );

    } catch (err) {
      messages.innerHTML = `
        ${renderQuestion(question)}

        <div class="gbm-answer-wrap">

          <div class="gbm-avatar">
            GBM
          </div>

          <div class="gbm-answer">
            Sorry — the chatbot encountered an error.
          </div>

        </div>
      `;
    }
  }

  sendBtn.onclick = askQuestion;

  input.addEventListener(
    "keydown",
    function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        askQuestion();
      }
    }
  );

})();

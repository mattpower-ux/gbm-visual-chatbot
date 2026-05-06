/* =========================================================
   GBM Deep Think — Visual Research UI
   Updated embed.js
   ========================================================= */

(function () {
  if (window.GBMDeepThinkLoaded) return;
  window.GBMDeepThinkLoaded = true;

  const API_BASE =
    window.GBM_CHATBOT_API ||
    "https://gbm-visual-chatbot.onrender.com";

  /* =========================
     SVG ICONS
     ========================= */

  const ICONS = {
    article: `
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 4h12l4 4v12H4z"/>
        <path d="M8 12h8"/>
        <path d="M8 16h8"/>
      </svg>
    `,
    pdf: `
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M6 2h9l5 5v15H6z"/>
        <path d="M14 2v6h6"/>
      </svg>
    `,
    video: `
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <polygon points="10,8 16,12 10,16"/>
      </svg>
    `,
    podcast: `
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 18v4"/>
        <circle cx="12" cy="11" r="3"/>
        <path d="M19 11a7 7 0 0 0-14 0"/>
      </svg>
    `,
    lightbulb: `
      💡
    `,
    check: `
      ✔️
    `,
    info: `
      ℹ️
    `,
  };

  /* =========================
     STYLES
     ========================= */

  const style = document.createElement("style");
  style.innerHTML = `
  .gbm-launcher {
    position: fixed;
    bottom: 22px;
    right: 22px;
    z-index: 999999;
    background: #006b5b;
    color: white;
    border-radius: 999px;
    padding: 14px 22px;
    font-family: Arial, sans-serif;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 8px 28px rgba(0,0,0,.25);
  }

  .gbm-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.35);
    z-index: 999998;
    display: none;
  }

  .gbm-window {
    position: fixed;
    inset: 28px;
    background: #f5f7f7;
    z-index: 999999;
    border-radius: 12px;
    overflow: hidden;
    display: none;
    flex-direction: column;
    font-family: Arial, sans-serif;
  }

  .gbm-header {
    background: #006b5b;
    color: white;
    padding: 20px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 24px;
    font-weight: 700;
  }

  .gbm-close {
    font-size: 32px;
    cursor: pointer;
  }

  .gbm-body {
    flex: 1;
    overflow-y: auto;
    padding: 28px;
  }

  .gbm-user-question {
    background: #eaf5e6;
    padding: 18px 24px;
    border-radius: 14px;
    width: fit-content;
    margin-left: auto;
    margin-bottom: 26px;
    font-size: 20px;
  }

  .gbm-answer {
    display: flex;
    gap: 18px;
    margin-bottom: 32px;
  }

  .gbm-logo {
    width: 52px;
    height: 52px;
    background: #5ba443;
    border-radius: 50%;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 28px;
    flex-shrink: 0;
  }

  .gbm-answer-text {
    font-size: 22px;
    line-height: 1.6;
    color: #222;
    max-width: 1200px;
  }

  .gbm-answer-text a {
    color: #006b5b;
    text-decoration: none;
    font-weight: 700;
  }

  .gbm-section-title {
    margin-top: 18px;
    margin-bottom: 20px;
    color: #006b5b;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: .02em;
  }

  .gbm-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0,1fr));
    gap: 16px;
    margin-bottom: 32px;
  }

  .gbm-column {
    background: white;
    border-radius: 12px;
    padding: 16px;
    border: 1px solid #d9dfdf;
  }

  .gbm-column-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 18px;
  }

  .gbm-card {
    border-bottom: 1px solid #ececec;
    padding-bottom: 14px;
    margin-bottom: 14px;
  }

  .gbm-card:last-child {
    border-bottom: none;
    margin-bottom: 0;
  }

  .gbm-card img {
    width: 100%;
    border-radius: 8px;
    margin-bottom: 10px;
  }

  .gbm-card-title {
    font-size: 16px;
    font-weight: 700;
    line-height: 1.35;
    margin-bottom: 6px;
  }

  .gbm-card-meta {
    color: #666;
    font-size: 13px;
    line-height: 1.45;
  }

  .gbm-play-btn {
    margin-top: 10px;
    background: white;
    border: 1px solid #5ba443;
    color: #2d7f3f;
    border-radius: 999px;
    padding: 10px 14px;
    font-weight: 700;
    cursor: pointer;
    width: 100%;
  }

  .gbm-insights {
    display: grid;
    grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 18px;
    margin-bottom: 34px;
  }

  .gbm-insight {
    background: white;
    border: 1px solid #dfe4e4;
    border-radius: 12px;
    padding: 18px;
  }

  .gbm-insight-title {
    font-weight: 700;
    margin-bottom: 10px;
    font-size: 18px;
  }

  .gbm-insight-body {
    line-height: 1.55;
    color: #333;
  }

  .gbm-recommended {
    display: grid;
    grid-template-columns: repeat(4, minmax(0,1fr));
    gap: 18px;
    margin-bottom: 32px;
  }

  .gbm-rec-card {
    background: white;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #dfe4e4;
  }

  .gbm-rec-card img {
    width: 100%;
    height: 160px;
    object-fit: cover;
  }

  .gbm-rec-title {
    padding: 14px;
    font-weight: 700;
    line-height: 1.4;
  }

  .gbm-input {
    border-top: 1px solid #dfe4e4;
    background: white;
    padding: 18px;
    display: flex;
    gap: 12px;
  }

  .gbm-input input {
    flex: 1;
    border-radius: 999px;
    border: 1px solid #dfe4e4;
    padding: 16px 18px;
    font-size: 16px;
  }

  .gbm-send {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    border: none;
    background: #006b5b;
    color: white;
    font-size: 20px;
    cursor: pointer;
  }

  @media(max-width:1200px){
    .gbm-grid{
      grid-template-columns: repeat(2,minmax(0,1fr));
    }

    .gbm-recommended{
      grid-template-columns: repeat(2,minmax(0,1fr));
    }
  }

  @media(max-width:800px){
    .gbm-grid,
    .gbm-insights,
    .gbm-recommended{
      grid-template-columns: 1fr;
    }

    .gbm-answer-text{
      font-size:18px;
    }

    .gbm-window{
      inset:0;
      border-radius:0;
    }
  }
  `;
  document.head.appendChild(style);

  /* =========================
     HTML
     ========================= */

  const launcher = document.createElement("div");
  launcher.className = "gbm-launcher";
  launcher.innerText = "Chat with GBM";

  const overlay = document.createElement("div");
  overlay.className = "gbm-overlay";

  const win = document.createElement("div");
  win.className = "gbm-window";

  win.innerHTML = `
    <div class="gbm-header">
      <div>GBM Deep Think</div>
      <div class="gbm-close">×</div>
    </div>

    <div class="gbm-body" id="gbm-body">
      <div class="gbm-user-question">
        How does a heat pump work?
      </div>

      <div class="gbm-answer">
        <div class="gbm-logo">gb</div>

        <div class="gbm-answer-text">
          Heat pumps work by moving heat from one place to another rather than generating heat.
          In the winter, they extract heat from the outside air and transfer it indoors.
          In the summer, the process reverses.
          <br><br>
          Sources:
          <a href="#">GBM Articles</a>,
          <a href="#">DOE</a>,
          <a href="#">Energy Star</a>
        </div>
      </div>

      <div class="gbm-section-title">
        DIVE DEEPER WITH TEXT ONLY
      </div>

      <div class="gbm-grid">

        ${buildColumn("Articles", ICONS.article)}
        ${buildColumn("PDFs & Guides", ICONS.pdf)}
        ${buildColumn("Videos", ICONS.video)}
        ${buildColumn("Podcasts", ICONS.podcast)}

      </div>

      <div class="gbm-insights">

        ${insightCard(ICONS.lightbulb, "Key Insights")}
        ${insightCard(ICONS.check, "Practical Implication")}
        ${insightCard(ICONS.info, "Related Fact")}

      </div>

      <div class="gbm-section-title">
        RECOMMENDED READING
      </div>

      <div class="gbm-recommended">
        ${recommendedCard()}
        ${recommendedCard()}
        ${recommendedCard()}
        ${recommendedCard()}
      </div>
    </div>

    <div class="gbm-input">
      <input placeholder="Type your question..." />
      <button class="gbm-send">➤</button>
    </div>
  `;

  document.body.appendChild(overlay);
  document.body.appendChild(win);
  document.body.appendChild(launcher);

  launcher.onclick = () => {
    overlay.style.display = "block";
    win.style.display = "flex";
  };

  overlay.onclick = closeWindow;
  win.querySelector(".gbm-close").onclick = closeWindow;

  function closeWindow() {
    overlay.style.display = "none";
    win.style.display = "none";
  }

  /* =========================
     HELPERS
     ========================= */

  function buildColumn(title, icon) {
    return `
      <div class="gbm-column">
        <div class="gbm-column-header">
          ${icon}
          ${title} (2)
        </div>

        ${contentCard()}
        ${contentCard()}

      </div>
    `;
  }

  function contentCard() {
    return `
      <div class="gbm-card">
        <img src="https://images.unsplash.com/photo-1581093458791-9f3c3900df4b?q=80&w=1200&auto=format&fit=crop" />

        <div class="gbm-card-title">
          Heat Pumps 101: How They Work
        </div>

        <div class="gbm-card-meta">
          Green Builder Media<br>
          Apr 18, 2023
        </div>

        <button class="gbm-play-btn">
          ▶ Play in chat
        </button>
      </div>
    `;
  }

  function insightCard(icon, title) {
    return `
      <div class="gbm-insight">
        <div class="gbm-insight-title">
          ${icon} ${title}
        </div>

        <div class="gbm-insight-body">
          Heat pumps are highly efficient systems that move heat rather than generate it.
        </div>
      </div>
    `;
  }

  function recommendedCard() {
    return `
      <div class="gbm-rec-card">
        <img src="https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?q=80&w=1200&auto=format&fit=crop" />
        <div class="gbm-rec-title">
          Choosing the Right System for Your Climate
        </div>
      </div>
    `;
  }
})();

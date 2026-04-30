(function () {
  const currentScript = document.currentScript;
  const apiBase = (currentScript?.dataset.apiBase || "").replace(/\/$/, "");
  const title = currentScript?.dataset.chatbotTitle || "GBM Deep Think";

  if (!apiBase) {
    console.error("Missing data-api-base");
    return;
  }

  const root = document.createElement("div");
  document.body.appendChild(root);

  let mode = "visual";

  function abs(url) {
    if (!url) return "";
    if (url.startsWith("http")) return url;
    return apiBase + url;
  }

  root.innerHTML = `
  <style>
    .gbm-launcher {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #006f63;
      color: white;
      padding: 14px 18px;
      border-radius: 999px;
      font-weight: 700;
      cursor: pointer;
      z-index: 999999;
    }

    .gbm-panel {
      position: fixed;
      bottom: 80px;
      right: 20px;
      width: 900px;
      max-width: calc(100vw - 30px);
      height: 720px;
      background: white;
      border-radius: 16px;
      display: none;
      flex-direction: column;
      overflow: hidden;
      z-index: 999998;
    }

    .gbm-header {
      background: linear-gradient(135deg,#007565,#005447);
      color: white;
      padding: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .gbm-title {
      font-size: 20px;
      font-weight: 800;
    }

    .gbm-close {
      font-size: 28px;
      cursor: pointer;
      border: none;
      background: none;
      color: white;
    }

    .gbm-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      background: #f7fafc;
    }

    .gbm-answer {
      margin-bottom: 16px;
      line-height: 1.5;
    }

    .gbm-insights {
      display: grid;
      grid-template-columns: repeat(4,1fr);
      gap: 10px;
      margin: 15px 0;
    }

    .gbm-insight {
      background: white;
      border: 1px solid #ddd;
      border-radius: 10px;
      padding: 10px;
      font-size: 12px;
      text-align: center;
    }

    .gbm-card-row {
      display: flex;
      gap: 12px;
      overflow-x: auto;
    }

    .gbm-card {
      min-width: 220px;
      border: 1px solid #ddd;
      border-radius: 12px;
      overflow: hidden;
      background: white;
    }

    .gbm-card img {
      width: 100%;
      height: 120px;
      object-fit: cover;
    }

    .gbm-card-body {
      padding: 10px;
    }

    .gbm-card-title {
      font-weight: 700;
      font-size: 13px;
      margin-bottom: 6px;
    }

    .gbm-card a {
      font-size: 12px;
      color: #007565;
      font-weight: 700;
      text-decoration: none;
    }

    .gbm-toggle {
      margin: 10px 0;
      font-weight: 700;
      color: #007565;
      cursor: pointer;
    }

    .gbm-input-row {
      display: flex;
      padding: 12px;
      border-top: 1px solid #eee;
      gap: 8px;
    }

    .gbm-input {
      flex: 1;
      padding: 12px;
      border-radius: 999px;
      border: 1px solid #ccc;
    }

    .gbm-send {
      background: #007565;
      color: white;
      border: none;
      padding: 0 18px;
      border-radius: 999px;
      cursor: pointer;
      font-weight: 700;
    }

    .gbm-thinking {
      font-weight: 700;
      color: #007565;
    }
  </style>

  <div class="gbm-launcher">${title}</div>

  <div class="gbm-panel">
    <div class="gbm-header">
      <div class="gbm-title">${title}</div>
      <button class="gbm-close">×</button>
    </div>

    <div class="gbm-messages"></div>

    <div class="gbm-input-row">
      <input class="gbm-input" placeholder="Ask anything..." />
      <button class="gbm-send">SEND</button>
    </div>
  </div>
  `;

  const launcher = root.querySelector(".gbm-launcher");
  const panel = root.querySelector(".gbm-panel");
  const messages = root.querySelector(".gbm-messages");
  const input = root.querySelector(".gbm-input");
  const send = root.querySelector(".gbm-send");

  launcher.onclick = () => panel.style.display = "flex";
  root.querySelector(".gbm-close").onclick = () => panel.style.display = "none";

  function renderVisual(data) {
    messages.innerHTML = `
      <div class="gbm-answer">${data.visual_summary || data.answer}</div>
      <div class="gbm-toggle">DIVE DEEPER WITH TEXT ONLY</div>
    `;

    messages.querySelector(".gbm-toggle").onclick = () => {
      mode = "text";
      renderText(data);
    };

    // insights
    if (data.key_insights) {
      const insights = document.createElement("div");
      insights.className = "gbm-insights";

      data.key_insights.slice(0,4).forEach(i => {
        insights.innerHTML += `
          <div class="gbm-insight">
            <strong>${i.title}</strong><br>${i.text}
          </div>
        `;
      });

      messages.appendChild(insights);
    }

    // blog cards
    if (data.cards) {
      const row = document.createElement("div");
      row.className = "gbm-card-row";

      data.cards.forEach(c => {
        const img = c.image || c.remote_image || "/assets/thumbs/fallback-article.jpg";

        row.innerHTML += `
          <div class="gbm-card">
            <img src="${abs(img)}"
                 onerror="this.onerror=null;this.src='${abs(c.remote_image || "/assets/thumbs/fallback-article.jpg")}'">
            <div class="gbm-card-body">
              <div class="gbm-card-title">${c.title}</div>
              <a href="${abs(c.url)}" target="_blank">Read →</a>
            </div>
          </div>
        `;
      });

      messages.appendChild(row);
    }

    // magazine cards
    if (data.magazines && data.magazines.length) {
      const title = document.createElement("h3");
      title.innerText = "From the Magazine";
      messages.appendChild(title);

      data.magazines.forEach(m => {
        messages.innerHTML += `
          <div class="gbm-card">
            <img src="${abs(m.cover)}"
                 onerror="this.src='${apiBase}/assets/covers/fallback-magazine.jpg'">
            <div class="gbm-card-body">
              <div class="gbm-card-title">${m.title}</div>
              <a href="${abs(m.url)}" target="_blank">View PDF →</a>
            </div>
          </div>
        `;
      });
    }
  }

  function renderText(data) {
    const sources = data.sources || [];

    messages.innerHTML = `
      <div class="gbm-answer">${data.text_only_answer || data.answer}</div>
      <div class="gbm-toggle">RETURN TO VISUAL MODE</div>
      ${sources.length ? `
        <div>
          <h3>Sources</h3>
          <ul>
            ${sources.map(s => `
              <li><a href="${abs(s.url)}" target="_blank">${s.title}</a></li>
            `).join("")}
          </ul>
        </div>
      ` : ""}
    `;

    messages.querySelector(".gbm-toggle").onclick = () => {
      mode = "visual";
      renderVisual(data);
    };
  }

  async function ask() {
    const q = input.value.trim();
    if (!q) return;

    messages.innerHTML = `<div class="gbm-thinking">Thinking...</div>`;

    const res = await fetch(apiBase + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q })
    });

    const data = await res.json();

    if (mode === "visual") renderVisual(data);
    else renderText(data);
  }

  send.onclick = ask;

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.keyCode === 13) {
      e.preventDefault();
      send.click();
    }
  });

})();

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

  const root = document.createElement("div");
  document.body.appendChild(root);

  function esc(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
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

    .gbm-launcher-logo {
      width: 60px;
      height: 60px;
      border-radius: 50%;
      overflow: hidden;
      position: relative;
      flex: 0 0 auto;
      background: transparent;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .gbm-launcher-logo img {
      width: 60px;
      height: 60px;
      object-fit: contain;
      display: block;
    }

    .gbm-panel {
      position: fixed;
      top: 24px;
      bottom: 24px;
      right: 24px;
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
      gap: 14px;
    }

    .gbm-mark {
      width: 64px;
      height: 64px;
      border-radius: 50%;
      overflow: hidden;
      position: relative;
      flex: 0 0 auto;
      background: transparent;
      display: flex;
      align-items: center;
      justify-content: center;
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
      border-radius: 50%;
      overflow: hidden;
      position: relative;
      flex: 0 0 auto;
      background: transparent;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .gbm-avatar img {
      width: 52px;
      height: 52px;
      object-fit: contain;
      display: block;
    }

    .gbm-title {
      font-size: 22px;
      font-weight: 900;
      letter-spacing: -.02em;
    }

    .gbm-launcher-logo::after,
    .gbm-mark::after,
    .gbm-avatar::after {
      content: "";
      position: absolute;
      inset: -20%;
      background:
        radial-gradient(
          circle at center,
          rgba(255,255,255,.9) 0%,
          rgba(255,255,255,.3) 18%,
          rgba(0,255,255,.15) 35%,
          transparent 60%
        );
      opacity: 0;
      animation: cognitionPulse 1.6s ease-out .25s 1;
      pointer-events: none;
    }

    @keyframes cognitionPulse {
      0% {
        transform: scale(.4);
        opacity: 0;
      }

      35% {
        opacity: .95;
      }

      100% {
        transform: scale(1.6);
        opacity: 0;
      }
    }

    .gbm-close {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      border: 0;
      background: rgba(255,255,255,.12);
      color: white;
      cursor: pointer;
      font-size: 22px;
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
      padding: 20px;
      max-width: 760px;
      line-height: 1.6;
      box-shadow: 0 8px 24px rgba(0,0,0,.04);
      font-size: 16px;
    }

    .gbm-answer-wrap {
      display: flex;
      gap: 14px;
      align-items: flex-start;
      margin-top: 24px;
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

    .gbm-inputbar {
      background: white;
      border-top: 1px solid #dce5e2;
      padding: 16px;
      display: flex;
      gap: 10px;
    }

    .gbm-input {
      flex: 1;
      border-radius: 999px;
      border: 1px solid #d4ddda;
      padding: 14px 18px;
      font-size: 15px;
      outline: none;
    }

    .gbm-send {
      min-width: 90px;
      height: 48px;
      border-radius: 999px;
      border: 0;
      background: #0087a7;
      color: white;
      cursor: pointer;
      font-weight: 900;
      letter-spacing: .04em;
      padding: 0 18px;
    }

    @media (max-width: 800px) {
      .gbm-panel {
        inset: 0;
        width: auto;
        border-radius: 0;
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

        <div class="gbm-title">
          COGNITION DeepDive
        </div>

      </div>

      <button class="gbm-close">×</button>

    </div>

    <div class="gbm-messages">

      <div class="gbm-welcome">
        Tap the power of COGNITION SmartData, combining our latest research with
        25 years of expertise in sustainable planning, building and products.
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
    launcher.style.display = "flex";
  };

  function addMessage(question, answer) {

    messages.innerHTML += `

      <div class="gbm-answer-wrap">

        <div class="gbm-avatar">
          <img src="${esc(COGNITION_LOGO_URL)}" alt="COGNITION">
        </div>

        <div class="gbm-answer">

          <div style="font-weight:900;margin-bottom:12px;">
            ${esc(question)}
          </div>

          ${esc(answer).replace(/\n/g,"<br>")}

        </div>

      </div>

    `;

    messages.scrollTop = messages.scrollHeight;
  }

  async function askQuestion() {

    const question = input.value.trim();
    if (!question) return;

    input.value = "";

    addMessage(question, "Thinking...");

    try {

      const response = await fetch(
        API_BASE + "/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            question
          })
        }
      );

      const payload = await response.json();

      const answers =
        root.querySelectorAll(".gbm-answer");

      const latest =
        answers[answers.length - 1];

      latest.innerHTML = `

        <div style="font-weight:900;margin-bottom:12px;">
          ${esc(question)}
        </div>

        ${esc(
          payload.visual_summary ||
          payload.answer ||
          "No response returned."
        ).replace(/\n/g,"<br>")}

      `;

    } catch (err) {

      const answers =
        root.querySelectorAll(".gbm-answer");

      const latest =
        answers[answers.length - 1];

      latest.innerHTML = `
        Sorry — the chatbot encountered an error.
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

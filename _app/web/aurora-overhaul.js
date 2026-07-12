(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);

  const BRAND_SVG = `
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id="echoBrandGradient" x1="7" y1="6" x2="57" y2="58" gradientUnits="userSpaceOnUse">
          <stop stop-color="#44e5ff"/><stop offset=".48" stop-color="#6488ff"/><stop offset="1" stop-color="#b65cff"/>
        </linearGradient>
        <filter id="echoGlow"><feGaussianBlur stdDeviation="1.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <path d="M42 8C27 11 15 22 13 36c-1 9 4 16 13 19-4-6-4-13-1-18 4-6 10-9 19-10-4 4-7 8-8 13 8-4 14-11 15-20-4 3-8 4-13 4 3-6 5-11 4-16Z" fill="none" stroke="url(#echoBrandGradient)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" filter="url(#echoGlow)"/>
      <path d="m27 27 13 7-13 7V27Z" fill="rgba(77,218,255,.14)" stroke="url(#echoBrandGradient)" stroke-width="2.6" stroke-linejoin="round"/>
      <circle cx="47.5" cy="13" r="2" fill="#7be7ff"/><circle cx="53" cy="20" r="1.2" fill="#ac72ff"/>
    </svg>`;

  const poseStack = (extraClass = "") => `
    <div class="luna-anim ${extraClass}" aria-label="Luna çalışıyor">
      <img src="./assets/luna-wave.webp" alt="" />
      <img src="./assets/luna-point.webp" alt="" />
      <img src="./assets/luna-run.webp" alt="" />
      <img src="./assets/luna-thumb.webp" alt="" />
    </div>`;

  function installBrand() {
    const mark = $(".brand-mark");
    const boot = $(".boot-logo");
    if (mark) mark.innerHTML = BRAND_SVG;
    if (boot) boot.innerHTML = BRAND_SVG;
  }

  function installAnimatedMascots() {
    const loader = $(".luna-loader");
    if (loader && !loader.querySelector(".luna-anim")) {
      loader.innerHTML = `${poseStack("compact")}<span class="luna-ring"></span>`;
    }

    const overview = $(".job-overview");
    if (overview && !overview.querySelector(".luna-work-card")) {
      const card = document.createElement("div");
      card.className = "luna-work-card";
      card.innerHTML = `${poseStack()}<span class="luna-work-copy"><strong>Luna çalışıyor</strong><small>İndirme ve dönüştürme aşamalarını canlı izliyor.</small></span>`;
      const action = overview.querySelector(":scope > .button");
      overview.insertBefore(card, action || null);
    }
  }

  function installFocusHint() {
    if ($(".focus-mode-hint")) return;
    const hint = document.createElement("div");
    hint.className = "focus-mode-hint";
    hint.innerHTML = `<b>ODAK MODU</b><span>Yalnızca ders alanı açık · Çıkış: Esc</span>`;
    document.body.appendChild(hint);
  }

  function refreshTourSpotlight() {
    const title = $("#tour-title")?.textContent || "";
    const spot = $("#tour-spotlight");
    if (!spot) return;
    const focus = /odak modu/i.test(title);
    spot.dataset.label = focus ? "ODAK MODU DÜĞMESİ" : "BURAYA BAK";
    spot.classList.toggle("is-focus-step", focus);
  }

  function watchTour() {
    const title = $("#tour-title");
    if (!title) return;
    refreshTourSpotlight();
    new MutationObserver(refreshTourSpotlight).observe(title, { childList: true, characterData: true, subtree: true });
  }

  function decorateQueue() {
    const list = $("#queue-list");
    if (!list) return;
    const apply = () => {
      [...list.children].forEach((item, index) => {
        item.style.setProperty("--queue-aurora-x", `${22 + (index % 4) * 19}%`);
      });
    };
    apply();
    new MutationObserver(apply).observe(list, { childList: true, subtree: true });
  }

  let cancelPoll = 0;
  let cancelStartedAt = 0;

  function setText(selector, value) {
    const node = $(selector);
    if (node) node.textContent = value;
  }

  function showCancelPending() {
    const view = $("#downloads-view");
    if (!view) return;
    cancelStartedAt = Date.now();
    view.classList.remove("cancel-complete");
    view.classList.add("cancel-pending");
    setText("#job-label", "DURDURULUYOR");
    setText("#job-title", "Aktif işlem güvenli biçimde kapatılıyor");
    setText("#job-detail", "Yarım dosyalar korunuyor; işlem kapanana kadar birkaç saniye bekle.");
    setText("#log-summary-title", "Durdurma isteği alındı");
    setText("#log-summary-detail", "Aktif video aracı ve alt işlemler kapatılıyor.");
    startCancelPolling();
  }

  function showCancelComplete() {
    const view = $("#downloads-view");
    if (!view) return;
    view.classList.remove("cancel-pending");
    view.classList.add("cancel-complete");
    setText("#job-label", "DURDURULDU");
    setText("#job-title", "İşlem durduruldu");
    setText("#job-detail", "Yarım dosyalar korundu; daha sonra yeniden deneyebilirsin.");
    setText("#job-percent", "—");
    setText("#log-summary-title", "Durduruldu");
    setText("#log-summary-detail", "Arka planda çalışan indirme veya dönüştürme kalmadı.");
    setText("#log-summary-percent", "—");
    window.clearInterval(cancelPoll);
    cancelPoll = 0;
    window.setTimeout(() => view.classList.remove("cancel-complete"), 4500);
  }

  async function pollCancelState() {
    try {
      const response = await fetch("/api/state", { cache: "no-store" });
      if (!response.ok) return;
      const state = await response.json();
      if (!state?.job?.busy && Date.now() - cancelStartedAt > 400) showCancelComplete();
    } catch (_) {
      // Existing app handles connection errors; this visual helper stays silent.
    }
  }

  function startCancelPolling() {
    window.clearInterval(cancelPoll);
    pollCancelState();
    cancelPoll = window.setInterval(pollCancelState, 550);
    window.setTimeout(() => {
      if ($("#downloads-view")?.classList.contains("cancel-pending")) {
        setText("#job-detail", "İşlem normalden uzun sürüyor; çalışan video aracı kapanması bekleniyor.");
      }
    }, 7000);
  }

  function bindCancelFeedback() {
    document.addEventListener("click", (event) => {
      const button = event.target.closest("#confirm-accept");
      if (!button) return;
      const title = $("#confirm-title")?.textContent || "";
      if (/durdur/i.test(button.textContent || "") || /durdur/i.test(title)) {
        window.setTimeout(showCancelPending, 20);
      }
    });
  }

  function keepDecorationsAlive() {
    const root = $("#app");
    if (!root) return;
    let timer = 0;
    new MutationObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        installBrand();
        installAnimatedMascots();
        refreshTourSpotlight();
      }, 80);
    }).observe(root, { childList: true, subtree: true });
  }

  function init() {
    document.documentElement.classList.add("aurora-ui");
    installBrand();
    installAnimatedMascots();
    installFocusHint();
    watchTour();
    decorateQueue();
    bindCancelFeedback();
    keepDecorationsAlive();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();

(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);

  const BRAND_SVG = `
    <svg viewBox="0 0 72 72" aria-hidden="true">
      <defs>
        <linearGradient id="ew-brand-gradient" x1="8" y1="6" x2="64" y2="67" gradientUnits="userSpaceOnUse">
          <stop stop-color="#45ecff"/><stop offset=".46" stop-color="#5d83ff"/><stop offset="1" stop-color="#b35cff"/>
        </linearGradient>
        <filter id="ew-brand-glow"><feGaussianBlur stdDeviation="1.8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <path d="M47 8C31 10 16 23 13 39c-2 11 5 21 17 25-6-7-7-16-3-23 4-7 11-11 22-13-5 5-9 11-10 17 10-5 18-14 19-25-5 4-10 6-16 6 4-7 6-13 5-18Z" fill="rgba(77,218,255,.07)" stroke="url(#ew-brand-gradient)" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" filter="url(#ew-brand-glow)"/>
      <path d="m29 30 15 8-15 8V30Z" fill="rgba(88,221,255,.16)" stroke="url(#ew-brand-gradient)" stroke-width="2.8" stroke-linejoin="round"/>
      <circle cx="54" cy="14" r="2.4" fill="#80edff"/><circle cx="61" cy="22" r="1.4" fill="#c377ff"/>
    </svg>`;

  const ICONS = {
    account: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4.5 21c.8-4.5 3.2-7 7.5-7s6.7 2.5 7.5 7"/></svg>',
    scan: '<svg viewBox="0 0 24 24"><path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4"/><path d="M8 12h8"/></svg>',
    download: '<svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 5-5m-5 5-5-5"/><path d="M4 19h16"/></svg>',
    play: '<svg viewBox="0 0 24 24"><path d="m8 5 11 7-11 7V5Z"/></svg>',
    transcript: '<svg viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
    quiz: '<svg viewBox="0 0 24 24"><path d="M4 5h16v14H4z"/><path d="m8 10 2 2 4-4M8 16h8"/></svg>'
  };

  const mascot = (src = "luna-point.webp", className = "") => `
    <div class="luna-static ${className}">
      <img src="./assets/${src}" alt="Luna" />
    </div>`;

  function installBrand() {
    const mark = $(".brand-mark");
    const boot = $(".boot-logo");
    if (mark && mark.dataset.overhauled !== "1") {
      mark.innerHTML = BRAND_SVG;
      mark.dataset.overhauled = "1";
    }
    if (boot && boot.dataset.overhauled !== "1") {
      boot.innerHTML = BRAND_SVG;
      boot.dataset.overhauled = "1";
    }
  }

  function installStaticMascots() {
    const loader = $(".luna-loader");
    if (loader && !loader.querySelector(".luna-static")) {
      loader.innerHTML = `${mascot("luna-chibi-work.webp", "is-small")}<span class="luna-ring"></span>`;
    }

    const overview = $("#downloads-view .job-overview");
    if (overview && !overview.querySelector(".download-luna-card")) {
      const card = document.createElement("aside");
      card.className = "download-luna-card";
      card.innerHTML = `${mascot("luna-chibi-work.webp", "is-download")}<span><strong>Luna çalışıyor</strong><small>İndirme ve dönüştürme aşamalarını senin için izliyor.</small></span>`;
      overview.appendChild(card);
    }

    const helpImage = $("#help-view .help-hero > img");
    if (helpImage) {
      helpImage.src = "./assets/luna-chibi-celebrate.webp";
      helpImage.alt = "EchoWraith rehberi Luna";
      helpImage.classList.add("help-luna-static");
    }
  }

  function updateLunaState(state, active) {
    const busy = Boolean(state.job?.busy || active);
    const ready = (state.lessons || []).some((lesson) => lesson.status === "Tamamlandı");
    const image = busy ? "luna-chibi-work.webp" : ready ? "luna-chibi-celebrate.webp" : "luna-chibi-discover.webp";
    const title = busy ? "Luna çalışıyor" : ready ? "Luna arşivi hazırladı" : "Luna hazır";
    const detail = busy
      ? "İndirme ve dönüştürme aşamalarını senin için izliyor."
      : ready
        ? "Hazır derslerin güvenle arşivde; kaldığın yerden devam edebilirsin."
        : "Bir ders seçtiğinde arşivi düzenlemeye başlayacak.";
    const card = $("#downloads-view .download-luna-card");
    const cardImage = card ? $("img", card) : null;
    if (card) card.dataset.state = busy ? "busy" : ready ? "ready" : "idle";
    if (cardImage) cardImage.src = `./assets/${image}`;
    setText("#downloads-view .download-luna-card strong", title);
    setText("#downloads-view .download-luna-card small", detail);
    const loaderImage = $("#downloads-view .luna-loader .luna-static img");
    if (loaderImage) loaderImage.src = `./assets/${image}`;
  }

  function installLibraryHero() {
    const heading = $("#library-view .page-heading");
    if (!heading || heading.querySelector(".library-luna-static")) return;
    heading.classList.add("aurora-library-heading");
    const art = document.createElement("div");
    art.className = "library-luna-static";
    art.innerHTML = `<span class="library-luna-glow"></span><img src="./assets/luna-point.webp" alt="Luna" />`;
    heading.appendChild(art);
  }

  function hashText(value) {
    let hash = 0;
    for (const char of String(value || "")) hash = ((hash << 5) - hash + char.charCodeAt(0)) | 0;
    return Math.abs(hash);
  }

  function decorateLessonCards() {
    const cards = $$("#lesson-list .lesson-card");
    cards.forEach((card, index) => {
      const key = card.dataset.key || String(index);
      const theme = hashText(key) % 8;
      card.dataset.theme = String(theme);
      const cover = $(".lesson-cover", card);
      if (cover) {
        cover.style.setProperty("--cover-shift", `${12 + (theme * 11) % 77}%`);
        cover.style.setProperty("--cover-hue", `${theme * 18}deg`);
      }
    });
  }

  function installHelpStepIcons() {
    $$("#help-view .help-steps article").forEach((card, index) => {
      if (card.querySelector(".help-step-icon")) return;
      const icon = document.createElement("span");
      icon.className = "help-step-icon";
      icon.innerHTML = [ICONS.account, ICONS.scan, ICONS.download, ICONS.play][index] || ICONS.play;
      const number = card.querySelector(":scope > b");
      if (number) number.insertAdjacentElement("afterend", icon);
      else card.prepend(icon);
    });
  }

  function installStudyArtwork() {
    const transcript = $("#study-transcript-list .study-placeholder");
    if (transcript && !transcript.querySelector(".study-empty-visual")) {
      const visual = document.createElement("div");
      visual.className = "study-empty-visual transcript-visual";
      visual.innerHTML = `${ICONS.transcript}<i></i><i></i>`;
      transcript.prepend(visual);
    }
    const quiz = $("#quiz-body .study-placeholder");
    if (quiz && !quiz.querySelector(".study-empty-visual")) {
      const visual = document.createElement("div");
      visual.className = "study-empty-visual quiz-visual";
      visual.innerHTML = `${ICONS.quiz}<i></i><i></i>`;
      quiz.prepend(visual);
    }
  }

  function ensureDownloadHero() {
    const overview = $("#downloads-view .job-overview");
    if (!overview) return;
    overview.classList.add("aurora-download-hero");

    if (!overview.querySelector(".download-progress-zone")) {
      const copy = overview.querySelector(".job-copy");
      const progress = document.createElement("div");
      progress.className = "download-progress-zone";
      progress.innerHTML = `
        <div class="download-progress-track"><i id="overhaul-job-progress"></i></div>
        <div class="download-metrics">
          <span><b id="overhaul-speed">—</b><small>İndirme hızı</small></span>
          <span><b id="overhaul-bytes">—</b><small>İlerleme</small></span>
          <span><b id="overhaul-eta">—</b><small>Kalan süre</small></span>
        </div>`;
      if (copy) copy.insertAdjacentElement("afterend", progress);
      else overview.appendChild(progress);
    }

    const logCard = $("#downloads-view .log-card");
    if (logCard && !logCard.querySelector(".download-status-list")) {
      const list = document.createElement("div");
      list.className = "download-status-list";
      list.innerHTML = `
        <div><span>Aşama</span><strong id="overhaul-stage">Hazır</strong></div>
        <div><span>İlerleme</span><strong id="overhaul-status-bytes">—</strong></div>
        <div><span>Hız</span><strong id="overhaul-status-speed">—</strong></div>
        <div><span>Kalan süre</span><strong id="overhaul-status-eta">—</strong></div>
        <div><span>Tahmini bitiş</span><strong id="overhaul-finish">—</strong></div>`;
      const summary = $("#log-summary", logCard);
      if (summary) summary.insertAdjacentElement("afterend", list);
      else logCard.appendChild(list);
    }
  }

  function decorateQueue() {
    $$("#queue-list .queue-item").forEach((item, index) => {
      if (!item.querySelector(".queue-thumb")) {
        const thumb = document.createElement("span");
        thumb.className = `queue-thumb queue-thumb-${index % 6}`;
        const anchor = item.querySelector(".queue-index");
        if (anchor) anchor.insertAdjacentElement("afterend", thumb);
        else item.prepend(thumb);
      }
    });
  }

  function parsePercent(value) {
    const match = String(value || "").replace(",", ".").match(/([0-9]+(?:\.[0-9]+)?)/);
    return match ? Math.max(0, Math.min(100, Number(match[1]))) : 0;
  }

  function formatBytes(value) {
    const amount = Number(value || 0);
    if (!amount) return "—";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let unit = 0;
    let size = amount;
    while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
    return `${size >= 10 || unit < 2 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
  }

  function formatSeconds(value) {
    let seconds = Math.max(0, Math.round(Number(value || 0)));
    if (!seconds) return "—";
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;
    return hours ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}` : `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
  }

  function setText(selector, value) {
    const node = $(selector);
    if (node) node.textContent = value;
  }

  // Progress history keyed by lesson so pace/ETA can be derived on the client.
  // BBB renders are frame-based, not byte streams, so the server often has no
  // download_speed/bytes/eta to report; we compute a smoothed pace from how
  // fast `progress` itself moves, which always works while it advances.
  let paceKey = "";
  let paceSamples = [];

  function derivePace(key, progress) {
    const now = Date.now();
    if (key !== paceKey) {
      paceKey = key;
      paceSamples = [];
    }
    paceSamples.push({ t: now, p: progress });
    // Keep a ~25s window so a brief stall does not zero the pace instantly.
    while (paceSamples.length > 2 && now - paceSamples[0].t > 25000) paceSamples.shift();
    const first = paceSamples[0];
    const last = paceSamples[paceSamples.length - 1];
    const dt = (last.t - first.t) / 1000;
    const dp = last.p - first.p;
    if (dt < 1.5 || dp <= 0) return { velocity: 0, remaining: 0 };
    const velocity = dp / dt; // fraction per second
    const remaining = velocity > 0 ? Math.max(0, (1 - last.p) / velocity) : 0;
    return { velocity, remaining };
  }

  async function refreshDownloadDetails() {
    if (!$("#downloads-view.is-active")) return;
    try {
      const response = await fetch("/api/state", { cache: "no-store" });
      if (!response.ok) return;
      const state = await response.json();
      const active = (state.lessons || []).find((lesson) => ["İndiriliyor", "Birleştiriliyor", "Dönüştürülüyor", "Kaynak aranıyor"].includes(lesson.status));
      updateLunaState(state, active);

      // The lesson's own progress (0..1) is the source of truth; fall back to
      // the header percent only when no active lesson is exposed yet.
      let fraction = active && typeof active.progress === "number" ? active.progress : parsePercent($("#job-percent")?.textContent || "0%") / 100;
      fraction = Math.max(0, Math.min(1, fraction || 0));
      const percent = Math.round(fraction * 100);

      const pace = active ? derivePace(active.key || "job", fraction) : { velocity: 0, remaining: 0 };

      // Prefer a real server ETA; otherwise use the client-derived remaining.
      const etaSeconds = active?.eta_seconds > 0 ? active.eta_seconds : pace.remaining;
      const eta = etaSeconds > 0 ? formatSeconds(etaSeconds) : "—";

      // Byte-stream downloads report speed/size; renders do not, so show the
      // processing pace as %/dk instead of a blank so the field is never dead.
      let speed;
      if (active?.download_speed > 0) speed = `${formatBytes(active.download_speed)}/sn`;
      else if (pace.velocity > 0) speed = `%${(pace.velocity * 100 * 60).toFixed(1)}/dk`;
      else speed = "—";

      let progressText;
      if (active?.known_size && active?.bytes_downloaded) progressText = `${formatBytes(active.bytes_downloaded)} / ${formatBytes(active.known_size)}`;
      else if (active) progressText = `%${percent}`;
      else progressText = "—";

      const stage = active?.status || (state.job?.busy ? state.job?.label || "İşlem sürüyor" : "Hazır");

      const bar = $("#overhaul-job-progress");
      if (bar) bar.style.width = `${percent}%`;
      setText("#overhaul-speed", speed);
      setText("#overhaul-bytes", progressText);
      setText("#overhaul-eta", eta);
      setText("#overhaul-stage", stage);
      setText("#overhaul-status-bytes", progressText);
      setText("#overhaul-status-speed", speed);
      setText("#overhaul-status-eta", eta);

      if (etaSeconds > 0) {
        const finish = new Date(Date.now() + etaSeconds * 1000);
        setText("#overhaul-finish", finish.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }));
      } else {
        setText("#overhaul-finish", "—");
      }
    } catch (_) {
      // Main app owns network error handling.
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
    const art = $(".tour-art");
    if (art) art.classList.toggle("is-final-step", /hazırsın/i.test(title));
  }

  let cancelPoll = 0;
  let cancelStartedAt = 0;

  function showCancelPending() {
    const view = $("#downloads-view");
    if (!view) return;
    cancelStartedAt = Date.now();
    view.classList.remove("cancel-complete");
    view.classList.add("cancel-pending");
    setText("#job-label", "DURDURULUYOR");
    setText("#job-title", "Aktif işlem güvenli biçimde kapatılıyor");
    setText("#job-detail", "Yarım dosyalar korunuyor; çalışan araçların kapanması bekleniyor.");
    window.clearInterval(cancelPoll);
    cancelPoll = window.setInterval(async () => {
      try {
        const response = await fetch("/api/state", { cache: "no-store" });
        const state = response.ok ? await response.json() : null;
        if (state && !state.job?.busy && Date.now() - cancelStartedAt > 400) {
          view.classList.remove("cancel-pending");
          view.classList.add("cancel-complete");
          setText("#job-label", "DURDURULDU");
          setText("#job-title", "İşlem durduruldu");
          setText("#job-detail", "Yarım dosyalar korundu; daha sonra yeniden deneyebilirsin.");
          window.clearInterval(cancelPoll);
          cancelPoll = 0;
          window.setTimeout(() => view.classList.remove("cancel-complete"), 4500);
        }
      } catch (_) { }
    }, 600);
  }

  function bindCancelFeedback() {
    document.addEventListener("click", (event) => {
      const button = event.target.closest("#confirm-accept");
      if (!button) return;
      const title = $("#confirm-title")?.textContent || "";
      if (/durdur/i.test(button.textContent || "") || /durdur/i.test(title)) window.setTimeout(showCancelPending, 20);
    });
  }

  function applyOverhaul() {
    installBrand();
    installStaticMascots();
    installLibraryHero();
    installHelpStepIcons();
    installStudyArtwork();
    ensureDownloadHero();
    decorateLessonCards();
    decorateQueue();
    refreshTourSpotlight();
  }

  function observeUi() {
    const root = $("#app");
    if (!root) return;
    let timer = 0;
    new MutationObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(applyOverhaul, 70);
    }).observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
  }

  function init() {
    document.documentElement.classList.add("aurora-ui-v3");
    applyOverhaul();
    installFocusHint();
    bindCancelFeedback();
    observeUi();
    const tourTitle = $("#tour-title");
    if (tourTitle) new MutationObserver(refreshTourSpotlight).observe(tourTitle, { childList: true, characterData: true, subtree: true });
    window.setInterval(refreshDownloadDetails, 1200);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();

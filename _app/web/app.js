(() => {
  "use strict";

  const PREVIEW = new URLSearchParams(location.search).get("preview") === "1";
  const API = "/api";

  const icons = {
    library: '<svg viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11a3 3 0 0 1 3 3v15a3 3 0 0 0-3-3H4V5.5Z"/><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H14v18a3 3 0 0 1 3-3h3V5.5Z"/></svg>',
    download: '<svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 5-5m-5 5-5-5"/><path d="M4 18v2h16v-2"/></svg>',
    history: '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>',
    search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
    chevron: '<svg viewBox="0 0 24 24"><path d="m8 10 4 4 4-4"/></svg>',
    calendar: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>',
    settings: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1v.1h-4V21a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1-.4h-.1v-4H3A1.7 1.7 0 0 0 4.6 8.5a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1v-.1h4V3A1.7 1.7 0 0 0 15.5 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.12.38.33.72.6 1 .28.28.62.48 1 .6h.1v4H21c-.4.02-.77.16-1.06.4-.27.28-.48.62-.6 1Z"/></svg>',
    keyboard: '<svg viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M10 13h.01M14 13h4M7 16h10"/></svg>',
    menu: '<svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
    refresh: '<svg viewBox="0 0 24 24"><path d="M20 6v5h-5"/><path d="M19 11a7 7 0 1 0 .1 3"/></svg>',
    play: '<svg viewBox="0 0 24 24"><path d="m8 5 11 7-11 7V5Z"/></svg>',
    pause: '<svg viewBox="0 0 24 24"><path d="M8 5v14M16 5v14"/></svg>',
    rewind: '<svg viewBox="0 0 24 24"><path d="M8 8H4V4"/><path d="M4 8a9 9 0 1 1-1 6"/><path d="M10 10v5M14 10v5"/></svg>',
    forward: '<svg viewBox="0 0 24 24"><path d="M16 8h4V4"/><path d="M20 8a9 9 0 1 0 1 6"/><path d="M10 10v5M14 10v5"/></svg>',
    volume: '<svg viewBox="0 0 24 24"><path d="M5 9v6h4l5 4V5L9 9H5Z"/><path d="M17 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12"/></svg>',
    muted: '<svg viewBox="0 0 24 24"><path d="M5 9v6h4l5 4V5L9 9H5Z"/><path d="m18 9 4 4m0-4-4 4"/></svg>',
    bookmark: '<svg viewBox="0 0 24 24"><path d="M6 3h12v18l-6-4-6 4V3Z"/></svg>',
    pip: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><rect x="12" y="11" width="7" height="5" rx="1"/></svg>',
    theater: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 8h10v8H7z"/></svg>',
    fullscreen: '<svg viewBox="0 0 24 24"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg>',
    collapse: '<svg viewBox="0 0 24 24"><path d="m7 14 5-5 5 5"/></svg>',
    target: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M22 12h-3M12 22v-3M2 12h3"/></svg>',
    send: '<svg viewBox="0 0 24 24"><path d="m3 3 18 9-18 9 3-9-3-9Z"/><path d="M6 12h15"/></svg>',
    grid: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
    list: '<svg viewBox="0 0 24 24"><path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></svg>',
    check: '<svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg>',
    clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    video: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="14" height="14" rx="2"/><path d="m17 10 4-2v8l-4-2"/></svg>',
    folder: '<svg viewBox="0 0 24 24"><path d="M3 6h7l2 2h9v11H3V6Z"/></svg>',
    info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
    close: '<svg viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>',
    trash: '<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6"/></svg>',
    login: '<svg viewBox="0 0 24 24"><path d="M10 4H5v16h5M14 8l4 4-4 4M8 12h10"/></svg>',
    alert: '<svg viewBox="0 0 24 24"><path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v5M12 17h.01"/></svg>',
    star: '<svg viewBox="0 0 24 24"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/></svg>',
    open: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v7H4V6h7"/></svg>',
    brain: '<svg viewBox="0 0 24 24"><path d="M9.5 4.5A3.5 3.5 0 0 0 6 8v.4A3.7 3.7 0 0 0 4 12a3.8 3.8 0 0 0 2.3 3.5V16a3.5 3.5 0 0 0 3.5 3.5c.9 0 1.7-.3 2.2-.8V5.3a3.4 3.4 0 0 0-2.5-.8Z"/><path d="M14.5 4.5A3.5 3.5 0 0 1 18 8v.4a3.7 3.7 0 0 1 2 3.6 3.8 3.8 0 0 1-2.3 3.5V16a3.5 3.5 0 0 1-3.5 3.5c-.9 0-1.7-.3-2.2-.8M8 9.5c1.2 0 2 .7 2 1.8M16 9.5c-1.2 0-2 .7-2 1.8M8.5 15c1 0 1.5-.4 1.5-1.2M15.5 15c-1 0-1.5-.4-1.5-1.2"/></svg>',
    pulse: '<svg viewBox="0 0 24 24"><path d="M3 12h4l2-6 4 12 2-6h6"/></svg>',
    help: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.4 2.4 0 1 1 3.7 2c-1 .6-1.5 1.1-1.5 2M12 17h.01"/></svg>',
    spark: '<svg viewBox="0 0 24 24"><path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3ZM19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14ZM5 3l.7 1.8L7.5 5.5l-1.8.7L5 8l-.7-1.8-1.8-.7 1.8-.7L5 3Z"/></svg>',
    shield: '<svg viewBox="0 0 24 24"><path d="M12 3 4.5 6v5.3c0 4.5 3 7.8 7.5 9.7 4.5-1.9 7.5-5.2 7.5-9.7V6L12 3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></svg>',
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
  const clamp = (value, min, max) => Math.min(Math.max(Number(value) || 0, min), max);

  const ui = {
    view: PREVIEW ? "watch" : "library",
    search: "",
    type: "all",
    year: "all",
    status: "all",
    sort: "date-desc",
    compact: localStorage.getItem("echowraith-density") === "compact",
    currentKey: null,
    chatQuery: "",
    chatFollow: true,
    companionTab: "chat",
    eventsSince: 0,
    logs: [],
    playerCleanup: null,
    previewTime: 181,
    previewDuration: 4515,
    previewPlaying: false,
    previewTick: 0,
    lastProgressSave: 0,
    confirmAction: null,
    transcript: [],
    transcriptQuery: "",
    quiz: [],
    quizIndex: 0,
    quizScore: 0,
    quizAnswered: false,
    studyKey: "",
    logFilter: "all",
    tourIndex: 0,
  };

  let model = {
    authenticated: false,
    settings: {
      output_dir: "C:\\Users\\Kullanıcı\\Downloads\\EchoWraith Dersleri",
      save_chat: true,
      quality: "Dengeli (720p)",
      encoder: "libx264 (uyumlu)",
      headless_first: true,
      auto_thumbnail: true,
      segment_threads: 4,
      idle_shutdown_minutes: 3,
      transcript_model: "base",
    },
    storage: { free: 857 * 1024 ** 3, total: 2 * 1024 ** 4, used: 1.2 * 1024 ** 4 },
    job: { busy: false, paused: false, label: "İşlem yok", detail: "", done: 0, total: 0, title: "" },
    lessons: [],
    profile: {},
    team: "Restless",
  };

  const tourSteps = [
    { title: "Şefim, arşivin sana ihtiyacı var.", text: "Ben Echo. Adım adım göstereceğim; hiçbir teknik bilgiye gerek yok. Site hesabını bağlayıp derslerini düzenli ve çevrimdışı bir arşive dönüştüreceğiz." },
    { title: "1) Önce hesabını bağla.", text: "Sağ üstteki dişli (Ayarlar) düğmesine gir, Efsane Uzem e-posta ve şifreni bir kez yaz, “Oturumu aç” de. Şifren hiçbir yere kaydedilmez." },
    { title: "2) Dersleri tara.", text: "Kütüphanedeki “Dersleri tara” düğmesine bas. Tüm ders listen otomatik bulunur. Gerekirse kısa bir tarayıcı penceresi açılıp kendiliğinden kapanır." },
    { title: "3) Seç ve indir.", text: "İstediğin derslerin köşesindeki kutucuğu işaretle, sonra “Seçilenleri indir” de. Hızı, yüzdeyi ve kalan süreyi “İndirmeler” bölümünde canlı izleyebilirsin." },
    { title: "4) Dersi izle.", text: "İndirilen bir derse tıkla. Ana ders videosu, öğretmen kamerası ve sohbet ayrı ama tam senkron oynar. Oynat/duraklat, 10 sn ileri-geri ve oynatma hızını alttaki çubuktan kullan." },
    { title: "Sağdaki panel: sohbet, notlar, kamera.", text: "Sağ tarafta dersin sohbetini okuyabilir, istediğin ana kendi notunu ekleyebilir ve öğretmen kamerasını küçültüp büyütebilirsin. Bir mesaja tıklarsan video o ana gider." },
    { title: "Odak Modu ve Tam Ekran.", text: "Alttaki “Odak Modu” düğmesi her şeyi gizleyip yalnızca ders videosunu büyütür; kamera küçük bir köşe penceresi olarak kalır. Çıkmak için Esc’e bas. Yanındaki düğme ise Tam Ekran açar." },
    { title: "Kaldığın yerden devam.", text: "Nerede bıraktığın otomatik hatırlanır. Kütüphanenin üstündeki “Kaldığın yerden” kartından veya “İzleme Geçmişi” bölümünden tek dokunuşla devam edebilirsin." },
    { title: "Transkript ve Test (Deneysel).", text: "“Transkript & Test” bölümünde bir dersi yazıya çevirip kendine çoktan seçmeli test çıkarabilirsin. Bu özellik hâlâ geliştiriliyor (deneysel); sonuçlar zaman zaman eksik olabilir." },
    { title: "Hazırsın, şefim.", text: "Bir sorun olursa bekle; EchoWraith uygun çözümü kendi dener. Bu rehberi istediğin an Ayarlar’dan yeniden başlatabilirsin. İyi çalışmalar!" },
  ];

  const demoChats = [
    { time: 623, sender: "Zeynep A.", text: "Hocam katılım hakkı tam olarak neyi kapsıyor?" },
    { time: 684, sender: "Ahmet Y.", text: "Örnek verebilir misiniz?" },
    { time: 745, sender: "Elif D.", text: "Çok açıklayıcı oldu, teşekkürler hocam. 👍" },
    { time: 806, sender: "Mehmet K.", text: "Sözleşme kaç maddeden oluşuyor?" },
    { time: 867, sender: "Öğretmen", text: "Toplam 54 maddeden oluşur. Temel ilkeler tüm maddelerin ruhunu oluşturur.", teacher: true },
    { time: 1012, sender: "Ayşe N.", text: "Bu bölüm sınavda sık geliyor mu hocam?" },
    { time: 1115, sender: "Öğretmen", text: "Özellikle dört temel ilke mutlaka bilinmeli.", teacher: true },
  ];

  const demoTranscript = [
    { id: 1, start: 181, end: 196, text: "Çocuk haklarının dört temel ilkesi ayrım gözetmeme, çocuğun üstün yararı, yaşama ve gelişme ile katılım hakkıdır." },
    { id: 2, start: 623, end: 642, text: "Katılım hakkı çocuğun kendisini ilgilendiren konularda görüşünü özgürce ifade edebilmesini kapsar." },
    { id: 3, start: 867, end: 885, text: "Birleşmiş Milletler Çocuk Haklarına Dair Sözleşme toplam elli dört maddeden oluşur." },
    { id: 4, start: 1115, end: 1132, text: "Sınav açısından özellikle dört temel ilkenin birlikte ve örnekleriyle bilinmesi önemlidir." },
  ];

  const demoQuiz = [
    { id: "q1", question: "Çocuk haklarının temel ilkelerinden biri hangisidir?", options: ["Katılım hakkı", "Sınırsız yetki", "Yalnızca korunma", "Mutlak sessizlik"], answer: 0, answer_text: "Katılım hakkı", explanation: "Katılım hakkı, sözleşmenin dört temel ilkesinden biridir.", time: 181 },
    { id: "q2", question: "Çocuk Haklarına Dair Sözleşme kaç maddeden oluşur?", options: ["24", "36", "54", "72"], answer: 2, answer_text: "54", explanation: "Ders transkriptinde sözleşmenin toplam 54 maddeden oluştuğu açıklanır.", time: 867 },
  ];

  function demoLessons() {
    const rows = [
      ["demo-1", "2026 ÖABT Hap Bilgi Kampı — Çocuk Hakları", "11.07.2026", "BBB / TUES", "Tamamlandı", 4515, 181, true, demoChats],
      ["demo-2", "Gelişim Psikolojisi — Erken Çocukluk Dönemi", "09.07.2026", "BBB / TUES", "Tamamlandı", 5320, 1840, true, demoChats.slice(0, 4)],
      ["demo-3", "2026 EB Sözel Mantık — 1. Hafta", "07.07.2026", "Zoom", "Tamamlandı", 6040, 0, false, []],
      ["demo-4", "Anne Baba Eğitimi — Temel Yaklaşımlar", "05.07.2026", "BBB / TUES", "Bekliyor", 0, 0, false, []],
      ["demo-5", "Okul Öncesi Eğitime Giriş", "04.07.2026", "Zoom", "Hata", 0, 0, false, []],
      ["demo-6", "Drama — Yaratıcı Süreç ve Uygulama", "03.07.2026", "Bilinmiyor", "Bekliyor", 0, 0, false, []],
      ["demo-7", "Çocuk Edebiyatı — Türler ve Özellikleri", "02.07.2026", "Doğrudan video", "Tamamlandı", 3890, 3890, false, []],
      ["demo-8", "Yöntem Yaklaşım ve Programlar", "01.07.2026", "BBB / TUES", "İndiriliyor", 4900, 0, true, []],
    ];
    return rows.map(([key, title, date, source_type, status, duration, last_position, has_webcam, chat], index) => ({
      key, title, date, source_type, status, duration, last_position, has_webcam, has_chat: chat.length > 0,
      chat, selected: index < 3, progress: status === "İndiriliyor" ? 0.43 : status === "Tamamlandı" ? 1 : 0,
      thumbnail_url: status === "Tamamlandı" ? "./assets/echo-background.webp" : "", has_transcript: index === 0, has_quiz: index === 0,
      known_size: status === "Tamamlandı" ? (700 + index * 84) * 1024 ** 2 : null,
      output_path: status === "Tamamlandı" ? `Dersler/${title}.mp4` : "", error: status === "Hata" ? "Download bağlantısı zaman aşımına uğradı." : "",
      last_watched_at: last_position ? new Date(Date.now() - index * 3600000).toISOString() : "",
      completed: duration > 0 && last_position >= duration - 5,
      favorite: index === 0,
      bookmarks: index === 0 ? [{ id: "note-1", time: 725, text: "Dört temel ilkeyi tekrar et." }] : [],
      category: title.includes("Gelişim") ? "Gelişim Psikolojisi" : title.includes("Drama") ? "Drama" : "ÖABT",
      year: "2026",
    }));
  }

  function injectIcons(root = document) {
    $$('[data-icon]', root).forEach((node) => {
      const name = node.dataset.icon;
      if (icons[name]) node.innerHTML = icons[name];
    });
  }

  function humanBytes(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    let size = Number(value);
    const units = ["B", "KB", "MB", "GB", "TB"];
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
    return `${size < 10 && unit > 1 ? size.toFixed(1) : Math.round(size)} ${units[unit]}`;
  }

  function formatSpeed(value) {
    return Number(value) > 0 ? `${humanBytes(value)}/sn` : "—";
  }

  function formatEta(value) {
    const seconds = Math.max(0, Math.round(Number(value) || 0));
    return seconds ? `${formatTime(seconds)} kaldı` : "";
  }

  function formatTime(seconds) {
    const value = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    const secs = value % 60;
    return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}` : `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }

  function parseDate(date) {
    const match = String(date || "").match(/(\d{2})\.(\d{2})\.(\d{4})/);
    if (!match) return 0;
    return new Date(`${match[3]}-${match[2]}-${match[1]}T00:00:00`).getTime();
  }

  function progressOf(lesson) {
    if (!lesson.duration) return lesson.completed ? 1 : 0;
    return clamp(lesson.last_position / lesson.duration, 0, 1);
  }

  function categoryOf(lesson) {
    if (lesson.category) return lesson.category;
    const title = lesson.title.toLowerCase();
    if (title.includes("gelişim")) return "Gelişim Psikolojisi";
    if (title.includes("drama")) return "Drama";
    if (title.includes("mantık")) return "Sözel Mantık";
    if (title.includes("çocuk hak")) return "Çocuk Hakları";
    return "Ders Arşivi";
  }

  function initials(title) {
    return String(title || "D").replace(/\b(202\d|öabt|meb|ags|kampı|dersi|ve|—|-|\([^)]*\))/gi, " ").trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toLocaleUpperCase("tr-TR") || "D";
  }

  function statusInfo(lesson) {
    const value = lesson.status || "Bekliyor";
    if (value === "Tamamlandı") return { className: "ready", icon: "check", label: "Çevrimdışı hazır" };
    if (value === "Hata") return { className: "error", icon: "alert", label: "Hata" };
    if (["İndiriliyor", "Birleştiriliyor", "Dönüştürülüyor", "Kaynak aranıyor"].includes(value)) return { className: "active", icon: "refresh", label: lesson.progress ? `${value} · %${Math.round(lesson.progress * 100)}` : value };
    return { className: "pending", icon: "clock", label: value };
  }

  async function request(path, options = {}) {
    if (PREVIEW) return previewRequest(path, options);
    const init = { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options };
    if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
    const response = await fetch(`${API}${path}`, init);
    const type = response.headers.get("content-type") || "";
    const data = type.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) throw new Error(data?.error || data?.message || data || `HTTP ${response.status}`);
    return data;
  }

  async function previewRequest(path, options) {
    await new Promise((resolve) => setTimeout(resolve, path.includes("events") ? 600 : 120));
    if (path === "/state") return structuredClone(model);
    if (path.includes("/chat")) {
      const key = path.split("/")[2];
      return { messages: model.lessons.find((lesson) => lesson.key === key)?.chat || [] };
    }
    if (path.includes("/transcript")) return { segments: demoTranscript, ready: true, started: true };
    if (path.includes("/quiz")) return { questions: demoQuiz, ready: true, count: demoQuiz.length };
    if (path.startsWith("/logs")) return { entries: ui.logs };
    if (path === "/delete") {
      const payload = typeof options.body === "string" ? JSON.parse(options.body || "{}") : (options.body || {});
      model.lessons.forEach((lesson) => { if ((payload.keys || []).includes(lesson.key)) { lesson.status = "Bekliyor"; lesson.output_path = ""; lesson.thumbnail_url = ""; } });
      return { ok: true, files: 1, records: 0 };
    }
    if (["/heartbeat", "/open-logs", "/shutdown"].includes(path)) return { ok: true };
    if (path.includes("/progress")) return { ok: true };
    if (path.includes("/bookmark")) return { ok: true };
    if (path === "/settings" && options.method === "PATCH") {
      const payload = typeof options.body === "string" ? JSON.parse(options.body || "{}") : (options.body || {});
      model.settings = { ...model.settings, ...payload };
      return { settings: model.settings };
    }
    if (path === "/choose-folder") return { path: model.settings.output_dir };
    if (["/auth", "/scan", "/download"].includes(path)) {
      model.job.busy = true;
      setTimeout(() => { model.job.busy = false; model.authenticated = true; renderAll(); }, 1200);
      return { started: true };
    }
    return { ok: true };
  }

  function toast(title, message = "", type = "info", timeout = 3200) {
    const item = document.createElement("div");
    item.className = `toast ${type}`;
    item.innerHTML = `<span class="toast-icon" data-icon="${type === "success" ? "check" : type === "error" ? "alert" : "info"}"></span><span><strong>${escapeHtml(title)}</strong>${message ? `<small>${escapeHtml(message)}</small>` : ""}</span>`;
    $("#toast-region").append(item);
    injectIcons(item);
    setTimeout(() => { item.classList.add("is-leaving"); setTimeout(() => item.remove(), 190); }, timeout);
  }

  function showConfirm(title, copy, acceptLabel, action) {
    $("#confirm-title").textContent = title;
    $("#confirm-copy").textContent = copy;
    $("#confirm-accept").textContent = acceptLabel;
    ui.confirmAction = action;
    $("#confirm-modal").classList.remove("is-hidden");
  }

  function hideConfirm() {
    ui.confirmAction = null;
    $("#confirm-modal").classList.add("is-hidden");
  }

  function setView(view, key = null) {
    const leavingWatch = ui.view === "watch" && view !== "watch";
    if (leavingWatch && typeof ui.playerCleanup === "function") {
      ui.playerCleanup();
      ui.playerCleanup = null;
    }
    if (leavingWatch) exitTheater();
    if (view === "watch" && key) ui.currentKey = key;
    ui.view = view;
    $$('[data-view-panel]').forEach((panel) => panel.classList.toggle("is-active", panel.dataset.viewPanel === view));
    $$('[data-view]').forEach((button) => button.classList.toggle("is-active", button.dataset.view === view || (view === "watch" && button.dataset.view === "library")));
    document.body.classList.remove("sidebar-open");
    if (view === "watch") renderWatch();
    if (view === "library") renderLibrary();
    if (view === "downloads") renderDownloads();
    if (view === "history") renderHistory();
    if (view === "study") { renderStudy(); if (ui.studyKey) loadStudyData(ui.studyKey); }
    if (view === "diagnostics") renderDiagnostics();
    const hash = view === "watch" ? `#/watch/${encodeURIComponent(ui.currentKey)}` : `#/${view}`;
    if (location.hash !== hash) history.replaceState(null, "", hash);
  }

  function renderStorage() {
    const { free = 0, total = 0, used = Math.max(0, total - free) } = model.storage || {};
    const ratio = total ? clamp(used / total, 0, 1) : 0;
    $("#storage-copy").textContent = total ? `${humanBytes(used)} / ${humanBytes(total)}` : "Bilgi alınamadı";
    $("#storage-percent").textContent = total ? `%${Math.round(ratio * 100)}` : "—";
    $("#storage-meter").style.width = `${ratio * 100}%`;
  }

  function filteredLessons() {
    const query = ui.search.trim().toLocaleLowerCase("tr-TR");
    let lessons = model.lessons.filter((lesson) => {
      if (query && !`${lesson.title} ${lesson.date} ${lesson.source_type} ${categoryOf(lesson)}`.toLocaleLowerCase("tr-TR").includes(query)) return false;
      if (ui.type !== "all") {
        if (ui.type === "unknown" && lesson.source_type !== "Bilinmiyor") return false;
        if (ui.type !== "unknown" && !String(lesson.source_type || "").includes(ui.type)) return false;
      }
      if (ui.year !== "all" && !String(lesson.date || lesson.year || "").includes(ui.year)) return false;
      if (ui.status === "ready" && lesson.status !== "Tamamlandı") return false;
      if (ui.status === "error" && lesson.status !== "Hata") return false;
      if (ui.status === "pending" && ["Tamamlandı", "Hata"].includes(lesson.status)) return false;
      return true;
    });
    lessons = [...lessons].sort((a, b) => {
      if (ui.sort === "date-asc") return parseDate(a.date) - parseDate(b.date);
      if (ui.sort === "title") return a.title.localeCompare(b.title, "tr");
      if (ui.sort === "progress") return progressOf(b) - progressOf(a);
      return parseDate(b.date) - parseDate(a.date);
    });
    return lessons;
  }

  function lessonCard(lesson) {
    const status = statusInfo(lesson);
    const progress = progressOf(lesson);
    const canWatch = lesson.status === "Tamamlandı" && (lesson.output_path || PREVIEW);
    const coverClass = lesson.thumbnail_url ? "lesson-cover has-thumbnail" : "lesson-cover";
    const coverStyle = lesson.thumbnail_url ? ` style="--thumb:url('${escapeHtml(lesson.thumbnail_url)}')"` : "";
    const liveMeta = lesson.download_speed ? `<span>${formatSpeed(lesson.download_speed)}${lesson.eta_seconds ? ` · ${formatEta(lesson.eta_seconds)}` : ""}</span>` : "";
    return `<article class="lesson-card ${lesson.selected ? "is-selected" : ""}" data-key="${escapeHtml(lesson.key)}">
      <div class="${coverClass}"${coverStyle}>
        <span class="cover-type">${escapeHtml(lesson.source_type || "Bilinmiyor")}</span>
        <button class="card-select ${lesson.selected ? "is-checked" : ""}" data-action="toggle-select" data-key="${escapeHtml(lesson.key)}" type="button" aria-label="${lesson.selected ? "Seçimi kaldır" : "Dersi seç"}"><span data-icon="check"></span></button>
        <span class="cover-letter">${escapeHtml(initials(lesson.title))}</span>
      </div>
      <div class="lesson-card-body">
        <button class="lesson-card-title" data-action="${canWatch ? "watch-lesson" : "toggle-select"}" data-key="${escapeHtml(lesson.key)}" type="button">${escapeHtml(lesson.title)}</button>
        <div class="lesson-meta"><span data-icon="calendar"></span><span>${escapeHtml(lesson.date || "Tarih yok")}</span><span>•</span><span>${escapeHtml(categoryOf(lesson))}</span>${lesson.duration ? `<span>•</span><span>${formatTime(lesson.duration)}</span>` : ""}</div>
        <div class="lesson-card-footer"><span class="status-chip ${status.className}"><span data-icon="${status.icon}"></span>${escapeHtml(status.label)}</span>${liveMeta || (lesson.known_size ? `<span>${humanBytes(lesson.known_size)}</span>` : "")}<button class="card-action" data-action="${canWatch ? "watch-lesson" : "download-one"}" data-key="${escapeHtml(lesson.key)}" type="button" aria-label="${canWatch ? "Dersi izle" : "Dersi indir"}"><span data-icon="${canWatch ? "play" : "download"}"></span></button></div>
      </div>
      <div class="lesson-card-progress"><i style="width:${Math.round(progress * 100)}%"></i></div>
    </article>`;
  }

  function renderLibrary() {
    const all = model.lessons;
    const ready = all.filter((lesson) => lesson.status === "Tamamlandı").length;
    const errors = all.filter((lesson) => lesson.status === "Hata").length;
    const pending = all.length - ready - errors;
    $("#count-all").textContent = all.length;
    $("#count-ready").textContent = ready;
    $("#count-pending").textContent = pending;
    $("#count-error").textContent = errors;
    $("#library-summary").textContent = all.length ? `${all.length} ders · ${ready} çevrimdışı hazır · ${all.filter((lesson) => lesson.selected).length} seçili` : "Henüz ders taranmadı. Efsane Uzem hesabına bağlanıp kütüphaneyi oluştur.";
    const lessons = filteredLessons();
    $("#lesson-list").classList.toggle("is-compact", ui.compact);
    $("#lesson-list").innerHTML = lessons.map(lessonCard).join("");
    $("#library-empty").classList.toggle("is-hidden", lessons.length > 0);
    injectIcons($("#lesson-list"));

    const resume = [...all].filter((lesson) => lesson.last_position > 10 && !lesson.completed && lesson.status === "Tamamlandı").sort((a, b) => String(b.last_watched_at).localeCompare(String(a.last_watched_at)))[0];
    $("#resume-card").classList.toggle("is-hidden", !resume);
    if (resume) {
      $("#resume-card").dataset.key = resume.key;
      $("#resume-title").textContent = resume.title;
      $("#resume-meta").textContent = `${formatTime(resume.last_position)} konumunda · ${Math.round(progressOf(resume) * 100)}% izlendi`;
      $("#resume-progress-bar").style.width = `${progressOf(resume) * 100}%`;
    }
  }

  function updateYearOptions() {
    const years = [...new Set(model.lessons.map((lesson) => String(lesson.date || lesson.year || "").match(/20\d{2}/)?.[0]).filter(Boolean))].sort().reverse();
    const select = $("#year-filter");
    const current = ui.year;
    select.innerHTML = '<option value="all">Tüm yıllar</option>' + years.map((year) => `<option value="${year}">${year}</option>`).join("");
    select.value = years.includes(current) ? current : "all";
  }

  function mediaTime() {
    return PREVIEW ? ui.previewTime : ($("#main-video")?.currentTime || 0);
  }

  function mediaDuration() {
    const lesson = currentLesson();
    if (PREVIEW) return ui.previewDuration;
    return Number.isFinite($("#main-video")?.duration) ? $("#main-video").duration : (lesson?.duration || 0);
  }

  function mediaPaused() {
    return PREVIEW ? !ui.previewPlaying : $("#main-video").paused;
  }

  function setMediaTime(value) {
    const time = clamp(value, 0, mediaDuration() || 0);
    if (PREVIEW) ui.previewTime = time;
    else {
      $("#main-video").currentTime = time;
      const webcam = $("#webcam-video");
      if (webcam?.src) webcam.currentTime = time;
    }
    updatePlayerUi();
  }

  function setPlaying(shouldPlay) {
    if (PREVIEW) {
      ui.previewPlaying = shouldPlay;
      if (shouldPlay && !ui.previewTick) ui.previewTick = window.setInterval(() => { ui.previewTime = Math.min(ui.previewTime + 0.25 * Number($("#speed-select").value || 1), ui.previewDuration); if (ui.previewTime >= ui.previewDuration) ui.previewPlaying = false; updatePlayerUi(); }, 250);
      updatePlayerUi();
      return;
    }
    const main = $("#main-video");
    if (shouldPlay) main.play().catch(() => toast("Oynatma başlatılamadı", "Video dosyasını veya tarayıcı izinlerini kontrol et.", "error"));
    else main.pause();
  }

  function currentLesson() {
    return model.lessons.find((lesson) => lesson.key === ui.currentKey) || null;
  }

  function chaptersFor(lesson) {
    if (Array.isArray(lesson.chapters) && lesson.chapters.length) return lesson.chapters;
    const duration = lesson.duration || ui.previewDuration || 1;
    return [
      { time: 0, title: "Giriş ve temel kavramlar" },
      { time: duration * 0.2, title: "Temel ilkeler" },
      { time: duration * 0.43, title: "Çocuğun üstün yararı" },
      { time: duration * 0.68, title: "Katılım hakkı" },
      { time: duration * 0.86, title: "Sınavda dikkat edilecekler" },
    ];
  }

  function renderWatchHeader(lesson) {
    const status = statusInfo(lesson);
    $("#watch-header").innerHTML = `<div class="watch-title-copy"><div class="breadcrumb"><button data-action="go-library" type="button">Kütüphane</button><span>/</span><span>${escapeHtml(categoryOf(lesson))}</span></div><h1>${escapeHtml(lesson.title)}</h1><div class="watch-title-meta"><span class="meta-pill ${status.className === "ready" ? "success" : ""}"><span data-icon="${status.icon}"></span>${escapeHtml(status.label)}</span><span class="meta-pill"><span data-icon="clock"></span>${lesson.duration ? formatTime(lesson.duration) : "Süre hesaplanıyor"}</span><span class="meta-pill">${escapeHtml(lesson.source_type || "Bilinmiyor")}</span></div></div><div class="watch-actions"><button class="button secondary" data-action="previous-lesson" type="button">← Önceki</button><button class="button secondary" data-action="next-lesson" type="button">Sonraki →</button><button class="icon-button" data-action="open-file" type="button" aria-label="Dosyayı aç"><span data-icon="open"></span></button></div>`;
    injectIcons($("#watch-header"));
  }

  function renderStatusStrip(lesson) {
    const size = lesson.known_size ? humanBytes(lesson.known_size) : "Hesaplanmadı";
    const source = lesson.source_type || "Bilinmiyor";
    const watched = progressOf(lesson);
    $("#watch-status-strip").innerHTML = `<div class="status-strip-item"><span class="strip-icon success" data-icon="check"></span><span class="strip-copy"><strong>Çevrimdışı hazır</strong><small>İnternet olmadan izleyebilirsin</small></span></div><div class="status-strip-item"><span class="strip-icon" data-icon="download"></span><span class="strip-copy"><strong>${size}</strong><small>Ders boyutu</small></span></div><div class="status-strip-item"><span class="strip-icon" data-icon="library"></span><span class="strip-copy"><strong>${escapeHtml(source)}</strong><small>Kayıt kaynağı</small></span></div><div class="status-strip-item"><span class="strip-icon ${watched > 0 ? "success" : ""}" data-icon="${watched > 0 ? "history" : "info"}"></span><span class="strip-copy"><strong>${watched ? `%${Math.round(watched * 100)} izlendi` : "Henüz başlanmadı"}</strong><small>${lesson.last_watched_at ? `Son izleme: ${new Date(lesson.last_watched_at).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" })}` : "İlerlemen otomatik kaydedilir"}</small></span></div>`;
    injectIcons($("#watch-status-strip"));
  }

  function renderChapters(lesson) {
    const duration = lesson.duration || ui.previewDuration || 1;
    $("#chapter-rail").innerHTML = `<div class="chapter-track"></div>${chaptersFor(lesson).map((chapter, index) => `<button class="chapter-dot" data-action="seek-chapter" data-time="${chapter.time}" data-title="${escapeHtml(chapter.title)}" style="left:${clamp(chapter.time / duration, 0, 1) * 100}%" type="button" aria-label="${escapeHtml(chapter.title)}"></button>`).join("")}`;
  }

  async function loadChat(lesson) {
    if (PREVIEW) {
      lesson.chat = lesson.chat || demoChats;
      renderChat();
      return;
    }
    try {
      const data = await request(`/lessons/${encodeURIComponent(lesson.key)}/chat`);
      lesson.chat = data.messages || [];
    } catch (error) {
      lesson.chat = [];
    }
    renderChat();
  }

  async function loadTranscript(lesson, renderStudyToo = false) {
    try {
      const data = PREVIEW ? { segments: demoTranscript } : await request(`/lessons/${encodeURIComponent(lesson.key)}/transcript`);
      lesson.transcript = data.segments || [];
      ui.transcript = lesson.transcript;
    } catch (error) {
      lesson.transcript = [];
      ui.transcript = [];
    }
    renderPlayerTranscript();
    if (renderStudyToo) renderStudyTranscript();
  }

  function renderPlayerTranscript() {
    const lesson = currentLesson();
    const segments = lesson?.transcript || [];
    $("#transcript-count").textContent = segments.length;
    $("#player-transcript-list").innerHTML = segments.length
      ? segments.map((item) => `<button class="transcript-mini-item" data-action="seek-transcript" data-time="${Number(item.start) || 0}" type="button"><time>${formatTime(item.start)}</time><span>${escapeHtml(item.text)}</span></button>`).join("")
      : '<div class="notes-empty">Bu dersin transkripti henüz yok.<br>Aşağıdaki düğmeyle cihazında oluşturabilirsin.</div>';
  }

  function renderChat() {
    const lesson = currentLesson();
    if (!lesson) return;
    const query = ui.chatQuery.toLocaleLowerCase("tr-TR");
    const messages = (lesson.chat || []).filter((message) => !query || `${message.sender} ${message.text}`.toLocaleLowerCase("tr-TR").includes(query));
    $("#chat-count").textContent = lesson.chat?.length || 0;
    $("#chat-list").innerHTML = messages.length ? messages.map((message, index) => `<button class="chat-message ${message.teacher ? "is-teacher" : ""}" data-chat-index="${index}" data-time="${Number(message.time) || 0}" type="button"><span class="message-time">${formatTime(message.time)}</span><span class="message-body"><strong class="message-author">${escapeHtml(message.sender || "Katılımcı")}</strong><span class="message-text">${escapeHtml(message.text || "")}</span></span></button>`).join("") : '<div class="chat-empty">Bu kayıt için sohbet bulunamadı.<br>Notlar sekmesini ders çalışırken kullanabilirsin.</div>';
    updateActiveChat();
  }

  function renderNotes() {
    const lesson = currentLesson();
    if (!lesson) return;
    const notes = lesson.bookmarks || [];
    $("#notes-count").textContent = notes.length;
    $("#notes-list").innerHTML = notes.length ? notes.slice().sort((a, b) => a.time - b.time).map((note) => `<div class="note-item"><button class="message-time" data-action="seek-note" data-time="${Number(note.time) || 0}" type="button">${formatTime(note.time)}</button><span class="message-body"><strong class="message-author">Ders Notu</strong><span class="message-text">${escapeHtml(note.text)}</span></span><button class="delete-note" data-action="delete-note" data-id="${escapeHtml(note.id)}" type="button" aria-label="Notu sil"><span data-icon="trash"></span></button></div>`).join("") : '<div class="notes-empty">Henüz not yok.<br>Oynatıcıdaki yer imi düğmesiyle bu ana not ekleyebilirsin.</div>';
    injectIcons($("#notes-list"));
  }

  function updateActiveChat() {
    const time = mediaTime();
    const nodes = $$('.chat-message', $("#chat-list"));
    let active = null;
    nodes.forEach((node) => {
      const isActive = Number(node.dataset.time) <= time && (!active || Number(node.dataset.time) > Number(active.dataset.time));
      if (isActive) active = node;
      node.classList.remove("is-active");
    });
    if (active) {
      active.classList.add("is-active");
      if (ui.chatFollow && !mediaPaused()) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  function renderWatch() {
    const lesson = currentLesson() || model.lessons.find((item) => item.status === "Tamamlandı") || model.lessons[0];
    if (!lesson) { setView("library"); toast("İzlenecek ders yok", "Önce dersleri tarayıp indir.", "error"); return; }
    ui.currentKey = lesson.key;
    renderWatchHeader(lesson);
    renderStatusStrip(lesson);
    renderChapters(lesson);
    renderNotes();
    setupPlayer(lesson);
    loadChat(lesson);
    loadTranscript(lesson);
  }

  function setupPlayer(lesson) {
    if (typeof ui.playerCleanup === "function") ui.playerCleanup();
    const main = $("#main-video");
    const webcam = $("#webcam-video");
    const previewPresentation = $("#preview-presentation");
    const previewWebcam = $("#preview-webcam");
    const hasWebcam = PREVIEW ? Boolean(lesson.has_webcam) : Boolean(lesson.has_webcam || lesson.webcam_url);
    $("#webcam-card").classList.toggle("is-hidden", !hasWebcam);
    $("#webcam-card").classList.remove("is-collapsed");
    $("#media-rail").classList.remove("webcam-collapsed");
    $('[data-action="hide-webcam"]')?.classList.remove("is-active");
    $("#media-rail").classList.toggle("no-webcam", !hasWebcam);
    $("#watch-layout").classList.toggle("no-rail", false);
    if (PREVIEW) {
      main.removeAttribute("src");
      webcam.removeAttribute("src");
      main.classList.add("is-hidden");
      previewPresentation.classList.remove("is-hidden");
      previewWebcam.classList.toggle("is-hidden", !hasWebcam);
      ui.previewDuration = lesson.duration || 4515;
      ui.previewTime = lesson.last_position || 181;
      ui.previewPlaying = false;
      ui.playerCleanup = () => {
        ui.previewPlaying = false;
        if (ui.previewTick) window.clearInterval(ui.previewTick);
        ui.previewTick = 0;
        updatePlayerUi();
      };
      updatePlayerUi();
      return;
    }
    previewPresentation.classList.add("is-hidden");
    previewWebcam.classList.add("is-hidden");
    main.classList.remove("is-hidden");
    main.src = lesson.media_url || `${API}/media/${encodeURIComponent(lesson.key)}`;
    if (hasWebcam) webcam.src = lesson.webcam_url || `${API}/webcam/${encodeURIComponent(lesson.key)}`;
    else webcam.removeAttribute("src");
    main.volume = Number($("#volume-slider").value || 0.8);
    const syncWebcam = (threshold = 0) => {
      if (!hasWebcam) return;
      try {
        webcam.playbackRate = main.playbackRate;
        if (webcam.readyState > 0 && Math.abs(webcam.currentTime - main.currentTime) > threshold) webcam.currentTime = main.currentTime;
      } catch (error) { /* metadata is still loading; the next timeupdate retries */ }
    };
    const onPlay = () => { if (hasWebcam) { syncWebcam(0); webcam.play().catch(() => {}); } updatePlayerUi(); };
    const onPause = () => { webcam.pause(); updatePlayerUi(); saveProgress(false); };
    const onSeeking = () => { syncWebcam(0.2); updatePlayerUi(); };
    const onRate = () => { syncWebcam(Number.POSITIVE_INFINITY); };
    const onTime = () => { if (hasWebcam && !main.paused && Math.abs(webcam.currentTime - main.currentTime) > 0.45) { syncWebcam(0.45); $("#sync-state").classList.add("warning"); setTimeout(() => $("#sync-state").classList.remove("warning"), 700); } updatePlayerUi(); if (Date.now() - ui.lastProgressSave > 8000) saveProgress(false); };
    const onMeta = () => {
      lesson.duration = main.duration || lesson.duration;
      const resumeAt = clamp(lesson.last_position || 0, 0, Math.max(0, main.duration - 10));
      if (resumeAt > 10) { main.currentTime = resumeAt; $("#resume-toast").classList.remove("is-hidden"); setTimeout(() => $("#resume-toast").classList.add("is-hidden"), 3000); }
      renderChapters(lesson); updatePlayerUi();
    };
    const onEnded = () => saveProgress(true);
    main.addEventListener("play", onPlay);
    main.addEventListener("pause", onPause);
    main.addEventListener("seeking", onSeeking);
    main.addEventListener("ratechange", onRate);
    main.addEventListener("timeupdate", onTime);
    main.addEventListener("loadedmetadata", onMeta);
    main.addEventListener("ended", onEnded);
    ui.playerCleanup = () => {
      saveProgress(false);
      main.pause(); webcam.pause();
      main.removeEventListener("play", onPlay); main.removeEventListener("pause", onPause); main.removeEventListener("seeking", onSeeking); main.removeEventListener("ratechange", onRate); main.removeEventListener("timeupdate", onTime); main.removeEventListener("loadedmetadata", onMeta); main.removeEventListener("ended", onEnded);
      main.removeAttribute("src"); webcam.removeAttribute("src"); main.load(); webcam.load();
    };
  }

  function updatePlayerUi() {
    if (ui.view !== "watch") return;
    const time = mediaTime();
    const duration = mediaDuration();
    const ratio = duration ? clamp(time / duration, 0, 1) : 0;
    $("#time-copy").textContent = `${formatTime(time)} / ${formatTime(duration)}`;
    $("#seek-slider").value = Math.round(ratio * 1000);
    $("#seek-slider").style.setProperty("--range-progress", `${ratio * 100}%`);
    const paused = mediaPaused();
    $("#play-toggle").innerHTML = icons[paused ? "play" : "pause"];
    $("#play-toggle").setAttribute("aria-label", paused ? "Oynat" : "Duraklat");
    $("#center-play").classList.toggle("is-playing", !paused);
    updateActiveChat();
  }

  async function saveProgress(completed) {
    const lesson = currentLesson();
    if (!lesson || lesson.status !== "Tamamlandı") return;
    lesson.last_position = mediaTime();
    lesson.duration = mediaDuration() || lesson.duration;
    lesson.completed = Boolean(completed || (lesson.duration && lesson.last_position >= lesson.duration - 8));
    lesson.last_watched_at = new Date().toISOString();
    ui.lastProgressSave = Date.now();
    if (!PREVIEW) request(`/lessons/${encodeURIComponent(lesson.key)}/progress`, { method: "PATCH", body: { position: lesson.last_position, duration: lesson.duration, completed: lesson.completed } }).catch(() => {});
  }

  async function addBookmark(text = "") {
    const lesson = currentLesson();
    if (!lesson) return;
    const noteText = text.trim() || prompt("Bu ana eklemek istediğin not:", "")?.trim();
    if (!noteText) return;
    const bookmark = { id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, time: mediaTime(), text: noteText };
    lesson.bookmarks = [...(lesson.bookmarks || []), bookmark];
    renderNotes();
    if (!PREVIEW) await request(`/lessons/${encodeURIComponent(lesson.key)}/bookmarks`, { method: "POST", body: bookmark });
    toast("Not kaydedildi", `${formatTime(bookmark.time)} konumuna eklendi.`, "success");
  }

  function renderDownloads() {
    const selected = model.lessons.filter((lesson) => lesson.selected || ["İndiriliyor", "Birleştiriliyor", "Dönüştürülüyor", "Hata"].includes(lesson.status));
    $("#queue-summary").textContent = `${selected.length} ders`;
    $("#queue-list").innerHTML = selected.length ? selected.map((lesson, index) => {
      const progress = lesson.status === "Tamamlandı" ? 1 : lesson.progress || 0;
      const transfer = lesson.download_speed ? ` · ${formatSpeed(lesson.download_speed)}${lesson.eta_seconds ? ` · ${formatEta(lesson.eta_seconds)}` : ""}` : "";
      return `<div class="queue-item"><span class="queue-index">${String(index + 1).padStart(2, "0")}</span><span class="queue-copy"><strong>${escapeHtml(lesson.title)}</strong><small>${escapeHtml(lesson.status || "Bekliyor")}${transfer}${lesson.error ? ` · ${escapeHtml(lesson.error)}` : ""}</small></span><span class="queue-progress"><span class="meter"><i style="width:${progress * 100}%"></i></span><span>%${Math.round(progress * 100)}</span></span><button class="retry-button" data-action="${lesson.status === "Hata" ? "retry-one" : "toggle-select"}" data-key="${escapeHtml(lesson.key)}" type="button" aria-label="${lesson.status === "Hata" ? "Tekrar dene" : "Kuyruktan çıkar"}"><span data-icon="${lesson.status === "Hata" ? "refresh" : "close"}"></span></button></div>`;
    }).join("") : '<div class="empty-state"><span data-icon="download"></span><h2>Kuyruk boş</h2><p>Kütüphaneden ders seçerek indirmeyi başlat.</p></div>';
    injectIcons($("#queue-list"));
    renderJob();
    renderLogs();
  }

  function renderJob() {
    const job = model.job || {};
    const active = model.lessons.find((lesson) => ["İndiriliyor", "Birleştiriliyor", "Dönüştürülüyor", "Kaynak aranıyor"].includes(lesson.status));
    const ratio = job.total ? clamp(((job.done || 0) + (active?.progress || 0)) / job.total, 0, 1) : (active?.progress || 0);
    $("#job-percent").textContent = `${Math.round(ratio * 100)}%`;
    $("#job-ring-progress").style.strokeDashoffset = `${113.1 * (1 - ratio)}`;
    $("#job-label").textContent = job.busy ? (job.paused ? "DURAKLATILDI" : "İŞLEM SÜRÜYOR") : "İŞLEM YOK";
    $("#job-title").textContent = job.title || (job.busy ? job.label : "Kuyruk hazır");
    $("#job-detail").textContent = job.detail || (job.busy ? `${job.done || 0}/${job.total || 0} tamamlandı` : "Kütüphaneden ders seçerek indirmeyi başlatabilirsin.");
    $("#pause-job").innerHTML = `<span data-icon="${job.paused ? "play" : "pause"}"></span>${job.paused ? "Devam et" : "Duraklat"}`;
    injectIcons($("#pause-job"));
    $("#connection-banner").classList.toggle("is-hidden", !job.busy);
    $("#connection-copy").textContent = job.paused ? "İşlem duraklatıldı" : (job.title || job.label || "İşlem sürüyor…");
    const activeCount = model.lessons.filter((lesson) => ["İndiriliyor", "Birleştiriliyor", "Dönüştürülüyor", "Kaynak aranıyor"].includes(lesson.status)).length;
    $("#download-badge").textContent = activeCount;
    $("#download-badge").classList.toggle("is-hidden", !activeCount);
  }

  function renderLogs() {
    $("#log-list").innerHTML = ui.logs.length ? ui.logs.slice(-250).map((entry) => `<div class="log-entry ${escapeHtml(String(entry.level || "info").toLowerCase())}"><time>${escapeHtml(entry.time || "")}</time><span>${escapeHtml(entry.message || "")}</span></div>`).join("") : '<div class="chat-empty">Henüz günlük kaydı yok.</div>';
    $("#log-list").scrollTop = $("#log-list").scrollHeight;
  }

  function renderHistory() {
    const lessons = model.lessons.filter((lesson) => lesson.last_position > 0 || lesson.completed).sort((a, b) => String(b.last_watched_at).localeCompare(String(a.last_watched_at)));
    $("#history-empty").classList.toggle("is-hidden", lessons.length > 0);
    $("#history-list").innerHTML = lessons.map((lesson) => `<article class="history-item"><div class="history-thumb">${escapeHtml(initials(lesson.title))}</div><div class="history-copy"><strong>${escapeHtml(lesson.title)}</strong><small>${escapeHtml(categoryOf(lesson))} · ${lesson.last_watched_at ? new Date(lesson.last_watched_at).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" }) : ""}</small></div><div class="history-progress"><span class="meter"><i style="width:${progressOf(lesson) * 100}%"></i></span><span>%${Math.round(progressOf(lesson) * 100)}</span></div><button class="button secondary compact" data-action="watch-lesson" data-key="${escapeHtml(lesson.key)}" type="button"><span data-icon="play"></span>${lesson.completed ? "Yeniden izle" : "Devam et"}</button></article>`).join("");
    injectIcons($("#history-list"));
  }

  function renderSettings() {
    $("#output-input").value = model.settings.output_dir || "";
    $("#quality-input").value = model.settings.quality || "Dengeli (720p)";
    $("#encoder-input").value = model.settings.encoder || "libx264 (uyumlu)";
    $("#chat-switch").checked = Boolean(model.settings.save_chat);
    $("#headless-switch").checked = model.settings.headless_first !== false;
    $("#thumbnail-switch").checked = model.settings.auto_thumbnail !== false;
    $("#segments-input").value = String(model.settings.segment_threads || 4);
    $("#idle-input").value = String(model.settings.idle_shutdown_minutes || 3);
    $("#transcript-model-input").value = model.settings.transcript_model || "base";
    $("#study-model-select").value = model.settings.transcript_model || "base";
    $("#auth-state").textContent = model.authenticated ? "Oturum hazır" : "Giriş gerekli";
    $("#auth-state").className = `state-pill ${model.authenticated ? "success" : "warning"}`;
    renderProfile();
  }

  function renderProfile() {
    const profile = model.profile || {};
    const name = profile.display_name || (model.authenticated ? "Öğrenci Hesabı" : "Yerel Hesap");
    const fields = Array.isArray(profile.fields) ? profile.fields : [];
    const email = fields.find((item) => /e-?posta|mail/i.test(item.label || ""))?.value || (model.authenticated ? "Efsane Uzem bağlı" : "Giriş yapılmadı");
    $("#account-name").textContent = name;
    $("#account-meta").innerHTML = `<i class="online-dot"></i> ${escapeHtml(email)}`;
    const initialsText = initials(name);
    const head = $("#profile-summary .profile-summary-head");
    head.innerHTML = `<span class="avatar">${escapeHtml(initialsText)}</span><span><strong>${escapeHtml(name)}</strong><small>${escapeHtml(profile.source || (model.authenticated ? "Efsane Uzem üyeliği" : "Oturum bekleniyor"))}</small></span>`;
    const extra = [...fields, ...(profile.packages || []).slice(0, 4).map((value) => ({ label: "Paket / üyelik", value }))];
    $("#profile-fields").innerHTML = extra.length ? extra.slice(0, 16).map((item) => `<span class="profile-field"><small>${escapeHtml(item.label)}</small><span title="${escapeHtml(item.value)}">${escapeHtml(item.value)}</span></span>`).join("") : '<span class="profile-field"><small>Durum</small><span>Oturum açınca güncellenecek</span></span>';
  }

  function studyReadyLessons() {
    return model.lessons.filter((lesson) => lesson.status === "Tamamlandı" && (lesson.output_exists || lesson.output_path || PREVIEW));
  }

  function renderStudy() {
    const lessons = studyReadyLessons();
    const select = $("#study-lesson-select");
    const previous = ui.studyKey || select.value;
    select.innerHTML = `<option value="">İndirilmiş bir ders seç…</option>${lessons.map((lesson) => `<option value="${escapeHtml(lesson.key)}">${escapeHtml(lesson.title)}</option>`).join("")}`;
    ui.studyKey = lessons.some((lesson) => lesson.key === previous) ? previous : (lessons[0]?.key || "");
    select.value = ui.studyKey;
    renderStudyTranscript();
    renderQuiz();
  }

  async function loadStudyData(key = ui.studyKey) {
    ui.studyKey = key;
    if (!key) { ui.transcript = []; ui.quiz = []; renderStudy(); return; }
    try {
      const [transcript, quiz] = await Promise.all([
        request(`/lessons/${encodeURIComponent(key)}/transcript`),
        request(`/lessons/${encodeURIComponent(key)}/quiz`),
      ]);
      ui.transcript = transcript.segments || [];
      ui.quiz = quiz.questions || [];
      ui.quizIndex = 0;
      ui.quizScore = 0;
      ui.quizAnswered = false;
    } catch (error) {
      ui.transcript = [];
      ui.quiz = [];
    }
    renderStudyTranscript();
    renderQuiz();
  }

  function renderStudyTranscript() {
    const query = ui.transcriptQuery.toLocaleLowerCase("tr-TR");
    const rows = (ui.transcript || []).filter((item) => !query || String(item.text || "").toLocaleLowerCase("tr-TR").includes(query));
    $("#transcript-summary").textContent = ui.transcript.length ? `${ui.transcript.length} bölüm · zaman damgalı` : "Henüz oluşturulmadı";
    $("#study-transcript-list").innerHTML = rows.length
      ? rows.map((item) => `<button class="study-transcript-item" data-action="open-transcript-time" data-time="${Number(item.start) || 0}" type="button"><time>${formatTime(item.start)}</time><span>${escapeHtml(item.text)}</span></button>`).join("")
      : '<div class="study-placeholder"><span data-icon="brain"></span><strong>Transkript henüz yok</strong><p>Dersi seçip “Transkript oluştur” düğmesine bas. İlk model hazırlığı biraz sürebilir.</p></div>';
    injectIcons($("#study-transcript-list"));
  }

  function renderQuiz() {
    const body = $("#quiz-body");
    const items = ui.quiz || [];
    $("#quiz-summary").textContent = items.length ? `${items.length} soru · skor ${ui.quizScore}` : "Transkriptten otomatik hazırlanır";
    if (!items.length) {
      body.innerHTML = '<div class="study-placeholder"><span data-icon="spark"></span><strong>Henüz test yok</strong><p>Transkript hazırlandıktan sonra “Yeni test üret” düğmesine bas.</p></div>';
      injectIcons(body);
      return;
    }
    if (ui.quizIndex >= items.length) {
      const rate = Math.round(ui.quizScore / items.length * 100);
      body.innerHTML = `<div class="quiz-score"><span><small>TEST TAMAMLANDI</small><strong>%${rate}</strong><h3>${ui.quizScore} / ${items.length} doğru</h3><p>${rate >= 80 ? "Harika gidiyorsun." : rate >= 55 ? "İyi başlangıç; yanlış açıklamalarını tekrar et." : "Transkripti gözden geçirip bir test daha oluştur."}</p><button class="button primary" data-action="reset-quiz" type="button">Tekrar çöz</button></span></div>`;
      return;
    }
    const item = items[ui.quizIndex];
    const letters = ["A", "B", "C", "D", "E"];
    body.innerHTML = `<div class="quiz-question"><span class="quiz-question-number">SORU ${ui.quizIndex + 1} / ${items.length}</span><h3>${escapeHtml(item.question)}</h3><div class="quiz-options">${(item.options || []).map((option, index) => { const className = ui.quizAnswered ? (index === Number(item.answer) ? "is-correct" : index === ui.quizChoice ? "is-wrong" : "") : ""; return `<button class="quiz-option ${className}" data-action="answer-quiz" data-index="${index}" type="button" ${ui.quizAnswered ? "disabled" : ""}><b>${letters[index]}</b><span>${escapeHtml(option)}</span></button>`; }).join("")}</div>${ui.quizAnswered ? `<div class="quiz-explanation"><strong>Doğru cevap: ${escapeHtml(item.answer_text || item.options[item.answer])}</strong><br>${escapeHtml(item.explanation || "Cevap transkriptteki ilgili bölümden alınmıştır.")}</div><div class="quiz-footer"><button class="button ghost" data-action="open-transcript-time" data-time="${Number(item.time) || 0}" type="button">İlgili ana git</button><button class="button primary" data-action="next-quiz" type="button">${ui.quizIndex + 1 >= items.length ? "Sonucu gör" : "Sonraki soru"}</button></div>` : ""}</div>`;
  }

  async function startTranscript(key = ui.studyKey || ui.currentKey) {
    if (!key) { toast("Ders seçilmedi", "İndirilmiş bir ders seç.", "error"); return; }
    ui.studyKey = key;
    setView("study");
    $("#study-lesson-select").value = key;
    $("#study-progress").classList.remove("is-hidden");
    $("#study-progress-title").textContent = "Transkript hazırlanıyor, lütfen bekleyin…";
    $("#study-progress-copy").textContent = "Konuşmalar bu bilgisayarda analiz ediliyor.";
    $("#study-progress-bar").style.width = "2%";
    try {
      await request(`/lessons/${encodeURIComponent(key)}/transcribe`, { method: "POST", body: { model: $("#study-model-select").value } });
      toast("Transkript başladı", "İlerlemeyi bu ekranda izleyebilirsin.", "success");
    } catch (error) {
      $("#study-progress").classList.add("is-hidden");
      toast("Transkript başlatılamadı", error.message, "error", 6000);
    }
  }

  async function generateQuiz() {
    if (!ui.studyKey) { toast("Ders seçilmedi", "Önce bir ders seç.", "error"); return; }
    try {
      const data = await request(`/lessons/${encodeURIComponent(ui.studyKey)}/quiz`, { method: "POST", body: { count: 10 } });
      ui.quiz = data.questions || [];
      ui.quizIndex = 0; ui.quizScore = 0; ui.quizAnswered = false;
      renderQuiz();
      toast("Test hazır", `${ui.quiz.length} soru üretildi.`, "success");
    } catch (error) { toast("Test üretilemedi", error.message, "error", 6000); }
  }

  function renderDiagnostics() {
    const entries = ui.logs || [];
    const filtered = entries.filter((entry) => ui.logFilter === "all" || String(entry.level || "").toUpperCase() === ui.logFilter);
    $("#diag-job").textContent = model.job?.busy ? (model.job.title || model.job.label || "İşlem sürüyor") : "Sistem hazır";
    $("#diag-stage").textContent = `Son aşama: ${entries[entries.length - 1]?.stage || model.job?.detail || "Hazır"}`;
    $("#diagnostic-log-list").innerHTML = filtered.length ? filtered.slice(-500).reverse().map((entry) => { const level = String(entry.level || "INFO").toLowerCase(); const stamp = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString("tr-TR") : (entry.time || ""); return `<div class="diagnostic-entry is-${level}"><time>${escapeHtml(stamp)}</time><span class="diag-stage">${escapeHtml(entry.stage || "GENEL")}</span><div><strong>${escapeHtml(entry.message || "")}</strong>${entry.suggestion ? `<p>${escapeHtml(entry.suggestion)}</p>` : ""}</div></div>`; }).join("") : '<div class="study-placeholder"><span data-icon="pulse"></span><strong>Henüz tanılama kaydı yok</strong><p>Bir işlem başladığında bütün aşamalar burada görünür.</p></div>';
    injectIcons($("#diagnostic-log-list"));
  }

  function showRecovery(payload = {}) {
    const overlay = $("#recovery-overlay");
    overlay.classList.toggle("is-hidden", payload.active === false);
    if (payload.active !== false) {
      $("#recovery-title").textContent = payload.message || "Lütfen bekleyin…";
      $("#recovery-copy").textContent = payload.suggestion || "EchoWraith daha uyumlu bir yöntem deniyor.";
    }
  }

  function showTour(force = false) {
    if (!force && localStorage.getItem("echowraith-tour-4") === "done") return;
    ui.tourIndex = 0;
    $("#tour-overlay").classList.remove("is-hidden");
    renderTour();
  }

  function renderTour() {
    const step = tourSteps[ui.tourIndex];
    $("#tour-title").textContent = step.title;
    $("#tour-text").textContent = step.text;
    $("#tour-dots").innerHTML = tourSteps.map((_item, index) => `<i class="${index === ui.tourIndex ? "is-active" : ""}"></i>`).join("");
    $("#tour-next").textContent = ui.tourIndex + 1 >= tourSteps.length ? "EchoWraith’i aç" : "Devam et";
  }

  function closeTour() {
    localStorage.setItem("echowraith-tour-4", "done");
    $("#tour-overlay").classList.add("is-hidden");
  }

  function renderAll() {
    renderStorage();
    updateYearOptions();
    renderSettings();
    renderJob();
    if (ui.view === "library") renderLibrary();
    if (ui.view === "watch") renderWatch();
    if (ui.view === "downloads") renderDownloads();
    if (ui.view === "history") renderHistory();
    if (ui.view === "study") renderStudy();
    if (ui.view === "diagnostics") renderDiagnostics();
  }

  async function refreshState(silent = false) {
    try {
      const data = await request("/state");
      model = { ...model, ...data, settings: { ...model.settings, ...(data.settings || {}) }, job: { ...model.job, ...(data.job || {}) } };
      renderAll();
      return true;
    } catch (error) {
      if (!silent) toast("Bağlantı kurulamadı", error.message, "error");
      return false;
    }
  }

  async function startAuth(manual = false) {
    const email = manual ? "" : $("#email-input").value.trim();
    const password = manual ? "" : $("#password-input").value;
    try {
      await request("/auth", { method: "POST", body: { email, password } });
      $("#password-input").value = "";
      toast("Oturum açılıyor", manual ? "Açılan Chrome penceresinde girişi tamamla." : "Bilgiler kontrol ediliyor.", "info");
      $("#settings-dialog").close();
      await refreshState(true);
    } catch (error) { toast("Giriş başlatılamadı", error.message, "error"); }
  }

  async function startScan() {
    try {
      await request("/scan", { method: "POST", body: { email: $("#email-input").value.trim(), password: $("#password-input").value } });
      $("#password-input").value = "";
      toast("Tarama başlatıldı", "Tüm ders sayfaları otomatik gezilecek.", "success");
      setView("downloads");
      await refreshState(true);
    } catch (error) { toast("Tarama başlatılamadı", error.message, "error"); }
  }

  async function startDownload(keys = null) {
    const selected = keys || model.lessons.filter((lesson) => lesson.selected).map((lesson) => lesson.key);
    if (!selected.length) { toast("Ders seçilmedi", "Kütüphaneden en az bir ders seç.", "error"); return; }
    try {
      await request("/download", { method: "POST", body: { keys: selected, email: $("#email-input").value.trim(), password: $("#password-input").value } });
      $("#password-input").value = "";
      toast("İndirme kuyruğu başladı", `${selected.length} ders işlenecek.`, "success");
      setView("downloads");
      await refreshState(true);
    } catch (error) { toast("İndirme başlatılamadı", error.message, "error"); }
  }

  async function setSelection(keys, selected) {
    model.lessons.forEach((lesson) => { if (keys.includes(lesson.key)) lesson.selected = selected; });
    renderLibrary();
    renderDownloads();
    if (!PREVIEW) request("/selection", { method: "PATCH", body: { keys, selected } }).catch((error) => toast("Seçim kaydedilemedi", error.message, "error"));
  }

  function selectAdjacent(direction) {
    const ready = model.lessons.filter((lesson) => lesson.status === "Tamamlandı" && (lesson.output_path || PREVIEW));
    const index = ready.findIndex((lesson) => lesson.key === ui.currentKey);
    if (!ready.length) return;
    const next = ready[(index + direction + ready.length) % ready.length];
    saveProgress(false);
    setView("watch", next.key);
  }

  function showDialog(selector) {
    const dialog = $(selector);
    if (!dialog.open) dialog.showModal();
  }

  function exitTheater() {
    if (!document.body.classList.contains("theater-mode")) return;
    document.body.classList.remove("theater-mode");
    $('[data-action="theater"]')?.classList.remove("is-active");
  }

  async function handleAction(action, target) {
    const key = target.dataset.key;
    if (action === "go-library") return setView("library");
    if (action === "show-downloads") return setView("downloads");
    if (action === "open-settings") { renderSettings(); return showDialog("#settings-dialog"); }
    if (action === "open-shortcuts") return showDialog("#shortcuts-dialog");
    if (action === "toggle-sidebar") return document.body.classList.toggle("sidebar-open");
    if (action === "close-sidebar") return document.body.classList.remove("sidebar-open");
    if (action === "scan") return startScan();
    if (action === "download-selected") return startDownload();
    if (action === "delete-selected") {
      const keys = model.lessons.filter((lesson) => lesson.selected).map((lesson) => lesson.key);
      if (!keys.length) return toast("Ders seçilmedi", "Silmek için en az bir ders seç.", "error");
      return showConfirm("Seçilen dosyalar silinsin mi?", `${keys.length} dersin video, webcam, sohbet, önizleme, transkript ve test dosyaları kalıcı olarak silinecek. Ders adları kütüphanede kalır.`, "Dosyaları sil", async () => { await request("/delete", { method: "POST", body: { keys, remove_records: false } }); await refreshState(true); toast("Dosyalar silindi", "Dersleri istersen yeniden indirebilirsin.", "success"); });
    }
    if (action === "toggle-select") { const lesson = model.lessons.find((item) => item.key === key); if (lesson) return setSelection([key], !lesson.selected); }
    if (action === "select-all") return setSelection(filteredLessons().map((lesson) => lesson.key), true);
    if (action === "select-none") return setSelection(model.lessons.map((lesson) => lesson.key), false);
    if (action === "clear-filters") { ui.search = ""; ui.type = "all"; ui.year = "all"; ui.status = "all"; $("#global-search").value = ""; $("#type-filter").value = "all"; $("#year-filter").value = "all"; $$('[data-status-filter]').forEach((button) => button.classList.toggle("is-active", button.dataset.statusFilter === "all")); return renderLibrary(); }
    if (action === "toggle-density") { ui.compact = !ui.compact; localStorage.setItem("echowraith-density", ui.compact ? "compact" : "grid"); target.innerHTML = icons[ui.compact ? "list" : "grid"]; return renderLibrary(); }
    if (action === "watch-lesson") return setView("watch", key);
    if (action === "resume-last") { const resume = $("#resume-card").dataset.key; if (resume) return setView("watch", resume); }
    if (action === "download-one") return startDownload([key]);
    if (action === "retry-one") return startDownload([key]);
    if (action === "retry-errors") return startDownload(model.lessons.filter((lesson) => lesson.status === "Hata").map((lesson) => lesson.key));
    if (action === "previous-lesson") return selectAdjacent(-1);
    if (action === "next-lesson") return selectAdjacent(1);
    if (action === "rewind") return setMediaTime(mediaTime() - 10);
    if (action === "forward") return setMediaTime(mediaTime() + 10);
    if (action === "bookmark") return addBookmark();
    if (["seek-chapter", "seek-note", "seek-transcript"].includes(action)) return setMediaTime(Number(target.dataset.time));
    if (action === "transcribe-current") return startTranscript(ui.currentKey);
    if (action === "start-transcript") return startTranscript();
    if (action === "generate-quiz") return generateQuiz();
    if (action === "answer-quiz") { if (!ui.quizAnswered) { ui.quizChoice = Number(target.dataset.index); ui.quizAnswered = true; if (ui.quizChoice === Number(ui.quiz[ui.quizIndex]?.answer)) ui.quizScore += 1; renderQuiz(); } return; }
    if (action === "next-quiz") { ui.quizIndex += 1; ui.quizAnswered = false; ui.quizChoice = -1; renderQuiz(); return; }
    if (action === "reset-quiz") { ui.quizIndex = 0; ui.quizScore = 0; ui.quizAnswered = false; ui.quizChoice = -1; renderQuiz(); return; }
    if (action === "open-transcript-time") { const time = Number(target.dataset.time) || 0; const lessonKey = ui.studyKey || ui.currentKey; if (lessonKey) { setView("watch", lessonKey); setTimeout(() => setMediaTime(time), 80); } return; }
    if (action === "open-help-study") return setView("help");
    if (action === "pip") { if (PREVIEW) return toast("Resim içinde resim", "Gerçek video açıldığında kullanılabilir.", "info"); const video = $("#main-video"); if (document.pictureInPictureElement) document.exitPictureInPicture(); else if (document.pictureInPictureEnabled) video.requestPictureInPicture().catch(() => toast("PiP açılamadı", "Tarayıcı bu video için izin vermedi.", "error")); return; }
    if (action === "theater") { const on = document.body.classList.toggle("theater-mode"); target.classList.toggle("is-active", on); toast("Odak modu", on ? "Yalnızca ders videosuna odaklandın. Çıkmak için Esc’e bas veya düğmeye yeniden dokun." : "Normal görünüme dönüldü.", "info", 2600); return; }
    if (action === "fullscreen") { const shell = $("#main-media-shell"); if (!document.fullscreenElement) shell.requestFullscreen?.(); else document.exitFullscreen?.(); return; }
    if (action === "hide-webcam") { const card = $("#webcam-card"); const collapsed = card.classList.toggle("is-collapsed"); $("#media-rail").classList.toggle("webcam-collapsed", collapsed); target.classList.toggle("is-active", collapsed); target.setAttribute("aria-label", collapsed ? "Kamerayı göster" : "Kamerayı gizle"); return; }
    if (action === "toggle-chat-follow") { ui.chatFollow = !ui.chatFollow; target.classList.toggle("is-active", ui.chatFollow); toast("Sohbet takibi", ui.chatFollow ? "Oynatılırken etkin mesaj izlenecek." : "Otomatik kaydırma kapatıldı.", "info"); return; }
    if (action === "pause-job") { try { await request("/pause", { method: "POST" }); await refreshState(true); } catch (error) { toast("İşlem değiştirilemedi", error.message, "error"); } return; }
    if (action === "cancel-job") return showConfirm("İşlem durdurulsun mu?", "Yarım dosyalar korunur; daha sonra kaldığı yerden devam edebilirsin.", "Durdur", async () => { await request("/cancel", { method: "POST" }); await refreshState(true); toast("Durdurma isteği gönderildi", "Aktif adım güvenli biçimde kapatılıyor.", "info"); });
    if (action === "clear-log") { ui.logs = []; return renderLogs(); }
    if (action === "login") return startAuth(false);
    if (action === "browser-login") return startAuth(true);
    if (action === "choose-folder") { try { const data = await request("/choose-folder", { method: "POST" }); if (data.path) $("#output-input").value = data.path; } catch (error) { toast("Klasör seçilemedi", error.message, "error"); } return; }
    if (action === "save-settings") { try { const settings = { output_dir: $("#output-input").value.trim(), quality: $("#quality-input").value, encoder: $("#encoder-input").value, save_chat: $("#chat-switch").checked, headless_first: $("#headless-switch").checked, auto_thumbnail: $("#thumbnail-switch").checked, segment_threads: Number($("#segments-input").value), idle_shutdown_minutes: Number($("#idle-input").value), transcript_model: $("#transcript-model-input").value }; const data = await request("/settings", { method: "PATCH", body: settings }); model.settings = { ...model.settings, ...(data.settings || settings) }; $("#settings-dialog").close(); renderAll(); toast("Ayarlar kaydedildi", "Yeni işlemlerde uygulanacak.", "success"); } catch (error) { toast("Ayarlar kaydedilemedi", error.message, "error"); } return; }
    if (action === "open-output") { try { await request("/open-output", { method: "POST" }); } catch (error) { toast("Klasör açılamadı", error.message, "error"); } return; }
    if (action === "open-logs") { try { await request("/open-logs", { method: "POST" }); } catch (error) { toast("Log klasörü açılamadı", error.message, "error"); } return; }
    if (action === "shutdown-app") return showConfirm("EchoWraith kapatılsın mı?", "Aktif işlem yoksa yerel panel ve bütün arka plan kaynakları kapanacak.", "Kapat", async () => { await request("/shutdown", { method: "POST" }); document.body.innerHTML = '<div class="boot-screen"><strong>EchoWraith kapatıldı</strong><span>Bu sekmeyi kapatabilirsin.</span></div>'; });
    if (action === "replay-tour") { $("#settings-dialog")?.close(); showTour(true); return; }
    if (action === "skip-tour") { closeTour(); return; }
    if (action === "next-tour") { if (ui.tourIndex + 1 >= tourSteps.length) closeTour(); else { ui.tourIndex += 1; renderTour(); } return; }
    if (action === "open-file") { try { await request(`/lessons/${encodeURIComponent(ui.currentKey)}/open`, { method: "POST" }); } catch (error) { toast("Dosya açılamadı", error.message, "error"); } return; }
    if (action === "delete-note") { const lesson = currentLesson(); const id = target.dataset.id; lesson.bookmarks = (lesson.bookmarks || []).filter((note) => note.id !== id); renderNotes(); if (!PREVIEW) request(`/lessons/${encodeURIComponent(lesson.key)}/bookmarks/${encodeURIComponent(id)}`, { method: "DELETE" }).catch(() => {}); return; }
    if (action === "confirm-cancel") return hideConfirm();
  }

  function processEvent(kind, payload) {
    if (kind === "log") { ui.logs.push(payload); if (ui.logs.length > 1000) ui.logs.splice(0, 200); renderLogs(); if (ui.view === "diagnostics") renderDiagnostics(); return; }
    if (kind === "status") { model.job.title = String(payload || ""); renderJob(); return; }
    if (kind === "stage") { model.job.detail = payload.message || payload.stage; renderJob(); if (ui.view === "diagnostics") renderDiagnostics(); return; }
    if (kind === "recovery") { showRecovery(payload); return; }
    if (kind === "profile_update") { model.profile = payload || {}; renderProfile(); return; }
    if (kind === "auth_ok") { model.authenticated = true; renderSettings(); toast("Oturum hazır", "Site bağlantısı başarıyla kuruldu.", "success"); return; }
    if (kind === "needs_login") { toast("Tarayıcı girişi bekleniyor", "Açılan Chrome penceresinde öğrenci girişini tamamla.", "info", 6000); return; }
    if (kind === "job_started") { model.job.busy = true; model.job.label = String(payload || "İşlem sürüyor"); renderJob(); return; }
    if (["job_done", "job_cancelled"].includes(kind)) { model.job.busy = false; model.job.title = String(payload || "Tamamlandı"); showRecovery({ active: false }); $("#study-progress").classList.add("is-hidden"); toast(kind === "job_done" ? "İşlem tamamlandı" : "İşlem durduruldu", String(payload || ""), kind === "job_done" ? "success" : "info"); refreshState(true).then(() => { if (ui.view === "study" && ui.studyKey) loadStudyData(ui.studyKey); }); return; }
    if (kind === "job_error") { model.job.busy = false; showRecovery({ active: false }); $("#study-progress").classList.add("is-hidden"); toast("İşlem hatası", `${payload.message || String(payload)}${payload.suggestion ? ` ${payload.suggestion}` : ""}`, "error", 8500); refreshState(true); return; }
    if (kind === "scan_progress") { model.job.detail = `Sayfa ${payload.page} · ${payload.count} ders bulundu`; renderJob(); return; }
    if (kind === "scan_complete") { refreshState(true); return; }
    if (kind === "lesson_update") { const index = model.lessons.findIndex((lesson) => lesson.key === payload.key); if (index >= 0) model.lessons[index] = { ...model.lessons[index], ...payload }; else model.lessons.push(payload); renderAll(); return; }
    if (kind === "item_progress") { const lesson = model.lessons.find((item) => item.key === payload.key); if (lesson) Object.assign(lesson, { progress: payload.progress || 0, download_speed: payload.speed || 0, eta_seconds: payload.eta || 0, bytes_downloaded: payload.bytes_done || lesson.bytes_downloaded || 0, known_size: payload.bytes_total || lesson.known_size }); renderDownloads(); if (ui.view === "library") renderLibrary(); return; }
    if (kind === "transcript_progress") { if (payload.key === ui.studyKey) { $("#study-progress").classList.remove("is-hidden"); $("#study-progress-title").textContent = payload.message || "Transkript hazırlanıyor…"; $("#study-progress-copy").textContent = payload.stage === "MODEL" ? "İlk kullanımda model hazırlanırken biraz beklemek normaldir." : "Video bu bilgisayarda analiz ediliyor."; $("#study-progress-bar").style.width = `${Math.round((payload.progress || 0) * 100)}%`; } return; }
    if (kind === "transcript_ready") { if (payload.key === ui.studyKey) loadStudyData(payload.key); return; }
    if (kind === "overall_progress") { model.job.done = payload.done; model.job.total = payload.total; model.job.title = payload.title; renderJob(); }
  }

  async function pollEvents() {
    if (PREVIEW) return;
    try {
      const data = await request(`/events?since=${ui.eventsSince}`);
      ui.eventsSince = data.last_id || ui.eventsSince;
      (data.events || []).forEach((event) => processEvent(event.kind, event.payload));
    } catch (error) {
      await new Promise((resolve) => setTimeout(resolve, 1800));
    }
    setTimeout(pollEvents, 80);
  }

  function bindEvents() {
    document.addEventListener("click", async (event) => {
      const nav = event.target.closest("[data-view]");
      if (nav) { event.preventDefault(); return setView(nav.dataset.view); }
      const actionNode = event.target.closest("[data-action]");
      if (actionNode) { event.preventDefault(); try { await handleAction(actionNode.dataset.action, actionNode); } catch (error) { toast("İşlem tamamlanamadı", error.message, "error"); } }
      const chat = event.target.closest(".chat-message");
      if (chat) setMediaTime(Number(chat.dataset.time));
      const tab = event.target.closest("[data-companion-tab]");
      if (tab) {
        ui.companionTab = tab.dataset.companionTab;
        $$('[data-companion-tab]').forEach((node) => node.classList.toggle("is-active", node === tab));
        $("#chat-panel").classList.toggle("is-active", ui.companionTab === "chat");
        $("#notes-panel").classList.toggle("is-active", ui.companionTab === "notes");
        $("#transcript-panel").classList.toggle("is-active", ui.companionTab === "transcript");
      }
      const logFilter = event.target.closest("[data-log-filter]");
      if (logFilter) { ui.logFilter = logFilter.dataset.logFilter; $$('[data-log-filter]').forEach((node) => node.classList.toggle("is-active", node === logFilter)); renderDiagnostics(); }
      const statusFilter = event.target.closest("[data-status-filter]");
      if (statusFilter) { ui.status = statusFilter.dataset.statusFilter; $$('[data-status-filter]').forEach((node) => node.classList.toggle("is-active", node === statusFilter)); renderLibrary(); }
      const chapter = event.target.closest(".chapter-dot");
      if (chapter) setMediaTime(Number(chapter.dataset.time));
    });

    $("#confirm-accept").addEventListener("click", async () => { const action = ui.confirmAction; hideConfirm(); if (action) { try { await action(); } catch (error) { toast("İşlem tamamlanamadı", error.message, "error"); } } });
    $("#global-search").addEventListener("input", (event) => { ui.search = event.target.value; if (ui.view !== "library") setView("library"); else renderLibrary(); });
    $("#type-filter").addEventListener("change", (event) => { ui.type = event.target.value; renderLibrary(); });
    $("#year-filter").addEventListener("change", (event) => { ui.year = event.target.value; renderLibrary(); });
    $("#sort-filter").addEventListener("change", (event) => { ui.sort = event.target.value; renderLibrary(); });
    $("#chat-search").addEventListener("input", (event) => { ui.chatQuery = event.target.value; renderChat(); });
    $("#transcript-search").addEventListener("input", (event) => { ui.transcriptQuery = event.target.value; renderStudyTranscript(); });
    $("#study-lesson-select").addEventListener("change", (event) => { ui.studyKey = event.target.value; loadStudyData(ui.studyKey); });
    $("#study-model-select").addEventListener("change", (event) => { $("#transcript-model-input").value = event.target.value; });
    $("#play-toggle").addEventListener("click", () => setPlaying(mediaPaused()));
    $("#center-play").addEventListener("click", () => setPlaying(mediaPaused()));
    $("#main-media-shell").addEventListener("dblclick", () => handleAction("fullscreen", $("#main-media-shell")));
    $("#seek-slider").addEventListener("input", (event) => setMediaTime(mediaDuration() * Number(event.target.value) / 1000));
    $("#volume-slider").addEventListener("input", (event) => { const value = Number(event.target.value); if (!PREVIEW) $("#main-video").volume = value; event.target.style.setProperty("--range-progress", `${value * 100}%`); $("#mute-toggle").innerHTML = icons[value ? "volume" : "muted"]; });
    $("#mute-toggle").addEventListener("click", () => { if (PREVIEW) return; const video = $("#main-video"); video.muted = !video.muted; $("#mute-toggle").innerHTML = icons[video.muted ? "muted" : "volume"]; });
    $("#speed-select").addEventListener("change", (event) => { if (!PREVIEW) { $("#main-video").playbackRate = Number(event.target.value); $("#webcam-video").playbackRate = Number(event.target.value); } });
    $("#note-form").addEventListener("submit", (event) => { event.preventDefault(); const input = $("#note-input"); const text = input.value.trim(); if (text) { addBookmark(text); input.value = ""; } });
    $$('.chapter-dot').forEach(() => {});
    document.addEventListener("mouseover", (event) => { const chapter = event.target.closest(".chapter-dot"); if (!chapter) return; const tip = $("#chapter-tooltip"); tip.textContent = `${chapter.dataset.title} · ${formatTime(chapter.dataset.time)}`; tip.classList.remove("is-hidden"); });
    document.addEventListener("mouseout", (event) => { if (event.target.closest(".chapter-dot")) $("#chapter-tooltip").classList.add("is-hidden"); });
    document.addEventListener("keydown", (event) => {
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); $("#global-search").focus(); return; }
      if (event.key === "Escape" && document.body.classList.contains("theater-mode")) { event.preventDefault(); exitTheater(); return; }
      if (typing || ui.view !== "watch") return;
      const key = event.key.toLowerCase();
      if (key === " " || key === "k") { event.preventDefault(); setPlaying(mediaPaused()); }
      if (key === "j" || event.key === "ArrowLeft") { event.preventDefault(); setMediaTime(mediaTime() - (key === "j" ? 10 : 5)); }
      if (key === "l" || event.key === "ArrowRight") { event.preventDefault(); setMediaTime(mediaTime() + (key === "l" ? 10 : 5)); }
      if (key === "m") $("#mute-toggle").click();
      if (key === "f") handleAction("fullscreen", $("#main-media-shell"));
      if (key === "b") addBookmark();
      if (key === "[") { const select = $("#speed-select"); select.selectedIndex = Math.max(0, select.selectedIndex - 1); select.dispatchEvent(new Event("change")); toast("Oynatma hızı", select.options[select.selectedIndex].text, "info", 1500); }
      if (key === "]") { const select = $("#speed-select"); select.selectedIndex = Math.min(select.options.length - 1, select.selectedIndex + 1); select.dispatchEvent(new Event("change")); toast("Oynatma hızı", select.options[select.selectedIndex].text, "info", 1500); }
    });
    window.addEventListener("beforeunload", () => saveProgress(false));
    window.addEventListener("hashchange", routeFromHash);
  }

  function routeFromHash() {
    const match = location.hash.match(/^#\/watch\/(.+)$/);
    if (match) return setView("watch", decodeURIComponent(match[1]));
    const view = location.hash.replace(/^#\//, "");
    if (["library", "downloads", "history", "study", "diagnostics", "help"].includes(view)) setView(view);
  }

  async function init() {
    injectIcons();
    bindEvents();
    if (PREVIEW) {
      model.authenticated = true;
      model.lessons = demoLessons();
      model.profile = { display_name: "Demo Öğrenci", source: "Efsane Uzem", fields: [{ label: "E-posta", value: "ogrenci@example.com" }, { label: "Üyelik", value: "Aktif öğrenci" }], packages: ["2026 ÖABT Hap Bilgi Kampı"] };
      ui.currentKey = model.lessons[0].key;
      ui.studyKey = model.lessons[0].key;
      ui.transcript = demoTranscript;
      ui.quiz = demoQuiz;
      ui.logs = [
        { time: "10:14:54", level: "SUCCESS", stage: "AUTH", message: "Kayıtlı arka plan oturumu kullanıldı." },
        { time: "10:15:02", level: "INFO", stage: "SCAN", message: "57 tablo sayfası tarandı; 568 ders bulundu." },
        { time: "10:15:09", level: "WARNING", stage: "RECOVERY", message: "Doğrudan yöntem yanıt vermedi; oynatıcı ağı taranıyor.", suggestion: "Kullanıcı işlemi gerekmiyor." },
        { time: "10:15:16", level: "SUCCESS", stage: "COMPLETE", message: "Çocuk Hakları: BBB / TUES kaydı hazır." },
      ];
      renderAll();
    } else {
      const ok = await refreshState();
      if (!ok) {
        model.lessons = [];
        renderAll();
      }
      try { const logs = await request("/logs?limit=500"); ui.logs = logs.entries || []; } catch (error) { ui.logs = []; }
      pollEvents();
      setInterval(() => request("/heartbeat").catch(() => {}), 15000);
    }
    routeFromHash();
    if (!location.hash) setView(PREVIEW ? "watch" : "library", PREVIEW ? model.lessons[0]?.key : null);
    $("#app").classList.remove("is-loading");
    $("#boot-screen").classList.add("is-done");
    if (!PREVIEW) setTimeout(() => showTour(false), 380);
  }

  init().catch((error) => {
    console.error(error);
    $("#app").classList.remove("is-loading");
    $("#boot-screen").classList.add("is-done");
    toast("Panel başlatılamadı", error.message, "error", 10000);
  });
})();

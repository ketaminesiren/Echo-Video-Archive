import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(root, "_app/web/index.html"), "utf8").replace(/<script src="\.\/app\.js" defer><\/script>/, "");
const rawScript = fs.readFileSync(path.join(root, "_app/web/app.js"), "utf8");
const rawOverhaulScript = fs.readFileSync(path.join(root, "_app/web/aurora-overhaul.js"), "utf8");
const script = rawScript
  .replace("const RECOVERY_AUTO_HIDE_MS = 7000;", "const RECOVERY_AUTO_HIDE_MS = 40;")
  .replace("  function showTour(force = false) {", "  window.__showRecoveryForTests = showRecovery;\n\n  function showTour(force = false) {");
const dom = new JSDOM(html, {
  url: "http://127.0.0.1:8765/?preview=1#/watch/demo-1",
  runScripts: "dangerously",
  pretendToBeVisual: true,
});
const { window } = dom;
const { document } = window;
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let beacons = 0;

window.console.error = (...args) => { throw new Error(args.join(" ")); };
window.navigator.sendBeacon = () => { beacons += 1; return true; };
window.HTMLDialogElement.prototype.showModal = function showModal() { this.open = true; };
window.HTMLDialogElement.prototype.close = function close() { this.open = false; };
window.HTMLMediaElement.prototype.play = function play() { this.__paused = false; return Promise.resolve(); };
window.HTMLMediaElement.prototype.pause = function pause() { this.__paused = true; };
Object.defineProperty(window.HTMLMediaElement.prototype, "paused", { configurable: true, get() { return this.__paused !== false; } });
Object.defineProperty(window.HTMLMediaElement.prototype, "duration", { configurable: true, get() { return 4515; } });
window.HTMLElement.prototype.requestFullscreen = function requestFullscreen() { document.__fullscreen = this; return Promise.resolve(); };
document.exitFullscreen = () => { document.__fullscreen = null; return Promise.resolve(); };
Object.defineProperty(document, "fullscreenElement", { configurable: true, get() { return document.__fullscreen || null; } });

window.eval(script);
await wait(420);

assert(document.querySelector("#boot-screen").classList.contains("is-done"), "boot screen should finish");
assert.equal(document.querySelector("#tour-text").textContent.includes("Luna"), true, "Luna should introduce herself");
assert.equal(document.querySelector("#recovery-copy").textContent.includes("Luna"), true, "recovery guidance must speak as Luna");

window.__showRecoveryForTests({ active: true, message: "Uyumlu yöntem hazırlanıyor", suggestion: "Luna deniyor." });
assert(!document.querySelector("#recovery-overlay").classList.contains("is-hidden"), "recovery banner should become visible");
await wait(300);
assert(document.querySelector("#recovery-overlay").classList.contains("is-hidden"), "recovery banner must auto-dismiss");

const theater = document.querySelector('[data-action="theater"]');
theater.click();
assert(document.body.classList.contains("theater-mode"), "focus mode should open");
assert(!document.querySelector("#webcam-card").classList.contains("is-hidden"), "focus mode must keep an available teacher camera");
theater.click();
assert(!document.body.classList.contains("theater-mode"), "focus mode should close cleanly");

document.querySelector('[data-action="open-shortcuts"]').click();
assert(document.querySelector("#shortcuts-dialog").open, "shortcut dialog should open");
document.querySelector('[data-shortcut="mute"]').click();
document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "x", bubbles: true }));
assert.equal(JSON.parse(window.localStorage.getItem("echowraith-shortcuts")).mute, "x", "shortcut should be rebindable");

document.querySelector('[data-view="library"]').click();
const density = document.querySelector('[data-action="toggle-density"]');
density.click();
assert.equal(window.localStorage.getItem("echowraith-density"), "compact", "grid/list preference should persist");
assert(document.querySelector("#lesson-list").classList.contains("is-compact"), "compact list should render");

document.querySelector('[data-view="downloads"]').click();
const queueText = document.querySelector("#queue-list").textContent;
assert(queueText.includes("43.0%"), "active download must show an explicit precise percentage");
assert.equal(document.querySelector("#job-percent").textContent, "43.0%", "overall ring must show a precise numeric percentage");

window.dispatchEvent(new window.PageTransitionEvent("pagehide"));
assert.equal(beacons, 0, "preview mode must not send a real shutdown beacon");

const css = fs.readFileSync(path.join(root, "_app/web/styles.css"), "utf8");
assert(css.includes("view-in") && css.includes("luna-spin"), "view and Luna loading animations should exist");
assert(css.includes('body.theater-mode .companion-card'), "focus mode should hide only the companion panel");
const overhaulCss = fs.readFileSync(path.join(root, "_app/web/aurora-overhaul.css"), "utf8");
assert(overhaulCss.includes("recovery-life") && overhaulCss.includes("empty-luna"), "Luna recovery and empty-state visuals should exist");
assert(overhaulCss.includes(".recovery-overlay.is-hidden"), "the presentation layer must preserve the recovery hidden state");
assert(overhaulCss.includes(".help-hero > img.help-luna-static"), "help Luna positioning must override the legacy hero rule");
assert(overhaulCss.includes(".help-steps article > .help-step-icon"), "help step icons must use the centered high-specificity rule");
assert(overhaulCss.includes("animation: ew-aurora-drift 13s") && overhaulCss.includes("@keyframes ew-library-aurora"), "global and library aurora layers must stay animated");
assert(overhaulCss.includes("mix-blend-mode: screen") && overhaulCss.includes("ellipse 50% 64%"), "library Luna should blend into the hero without hard image edges");
assert(!/%\$\{/.test(rawScript) && !/%\$\{/.test(rawOverhaulScript), "percentages must use the conventional number-before-sign format");
assert(html.includes("luna-launcher-icon.png"), "the browser should use Luna's launcher icon");
for (const asset of ["luna-chibi-work.webp", "luna-chibi-celebrate.webp", "luna-chibi-discover.webp"]) {
  assert(fs.existsSync(path.join(root, "_app/web/assets", asset)), `${asset} should be bundled`);
}
for (const asset of ["luna-launcher-icon.png", "luna-launcher-icon.ico"]) {
  assert(fs.existsSync(path.join(root, "_app/web/assets", asset)), `${asset} should be bundled`);
}
for (const asset of ["guide", "library", "download", "watch", "study", "diagnostics", "history", "success"].map((name) => `luna-aurora-${name}.webp`)) {
  assert(fs.existsSync(path.join(root, "_app/web/assets", asset)), `${asset} should be bundled`);
  assert(html.includes(asset) || rawScript.includes(asset) || rawOverhaulScript.includes(asset), `${asset} should be used by the interface`);
}

dom.window.close();
console.log("frontend smoke: ok");

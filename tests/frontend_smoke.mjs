import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(root, "_app/web/index.html"), "utf8").replace(/<script src="\.\/app\.js" defer><\/script>/, "");
const script = fs.readFileSync(path.join(root, "_app/web/app.js"), "utf8");
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
assert.equal(document.querySelector("#job-percent").textContent, "43%", "overall ring must show a numeric percentage");

window.dispatchEvent(new window.PageTransitionEvent("pagehide"));
assert.equal(beacons, 0, "preview mode must not send a real shutdown beacon");

const css = fs.readFileSync(path.join(root, "_app/web/styles.css"), "utf8");
assert(css.includes("view-in") && css.includes("luna-spin"), "view and Luna loading animations should exist");
assert(css.includes('body.theater-mode .companion-card'), "focus mode should hide only the companion panel");

dom.window.close();
console.log("frontend smoke: ok");

import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { JSDOM } from "../web/node_modules/jsdom/lib/api.js";

const html = await fs.readFile(new URL("../web/index.html", import.meta.url), "utf8");
const dom = new JSDOM(html, { url: "http://127.0.0.1:8000/", pretendToBeVisual: true });
const { window } = dom;
window.HTMLElement.prototype.scrollIntoView = () => {};

Object.assign(globalThis, {
  window,
  document: window.document,
  location: window.location,
  CustomEvent: window.CustomEvent,
  Event: window.Event,
  addEventListener: window.addEventListener.bind(window),
});

const nativeFetch = globalThis.fetch;
globalThis.fetch = (input, init) => nativeFetch(new URL(String(input), window.location.href), init);
const calls = { selected: [], cleared: 0 };
globalThis.OpenBIMViewer = {
  async loadIfcGeometry() { return 5; },
  selectExpressID(id) { calls.selected.push(id); return true; },
  clearSelection() { calls.cleared += 1; },
};

await import(`../web/app.js?frontend-test=${Date.now()}`);
document.querySelector("#demoButton").click();

const deadline = Date.now() + 5000;
while (document.querySelectorAll(".issue-action").length === 0 && Date.now() < deadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}

assert.equal(document.querySelector("#workspace").classList.contains("hidden"), false, "demo analysis opens the workspace");
assert.match(document.querySelector("#viewerStatus").textContent, /5 mesh groups/, "geometry result is reported");

const issue = document.querySelector('.issue-action[data-entity-id="73"]');
assert.ok(issue, "QC issue for wall #73 is keyboard-accessible button content");
assert.equal(issue.tagName, "BUTTON", "QC issue uses native keyboard-accessible button semantics");
assert.match(issue.getAttribute("aria-label"), /Highlight IFCWALL 73/, "QC issue has a useful accessible label");
issue.click();
assert.deepEqual(calls.selected, [73], "clicking a QC issue selects the matching IFC element");
assert.equal(issue.classList.contains("selected"), true, "clicked issue receives synchronized selected state");
assert.equal(document.querySelector('.model-node[data-entity-id="73"]').classList.contains("selected"), true, "issue selection synchronizes the data map");
assert.match(document.querySelector("#viewerStatus").textContent, /WALL #73/, "viewer status identifies selected element");
assert.equal(document.querySelector("#clearSelectionButton").classList.contains("hidden"), false, "clear-selection control becomes visible");

window.dispatchEvent(new window.CustomEvent("ifc-element-selected", { detail: { expressID: 85 } }));
assert.equal(document.querySelector('.issue-action[data-entity-id="85"]').classList.contains("selected"), true, "direct 3D selection synchronizes the issue list");

document.querySelector("#clearSelectionButton").click();
assert.equal(calls.cleared > 0, true, "clear selection calls the viewer reset");
assert.equal(document.querySelectorAll(".issue-action.selected").length, 0, "clear selection removes issue highlighting");
assert.equal(document.querySelector("#clearSelectionButton").classList.contains("hidden"), true, "clear-selection control hides after reset");

document.querySelector("#sampleIdsButton").click();
const idsDeadline = Date.now() + 5000;
while (document.querySelector("#idsStatus").classList.contains("hidden") && Date.now() < idsDeadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}
assert.equal(document.querySelector("#idsStatus").classList.contains("hidden"), false, "sample IDS validation reports its status");
assert.match(document.querySelector("#idsStatus").textContent, /1 failure/, "IDS failure count is visible");
assert.ok(document.querySelector('[data-rule-id="ids:wall-name"][data-entity-id="73"]'), "IDS issue remains linked to wall #73");
assert.equal(document.querySelector("#bcfButton").disabled, false, "BCF export is available after analysis");

console.log("frontend interaction tests passed");

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { JSDOM } from "../web/node_modules/jsdom/lib/api.js";

const projectRoot = fileURLToPath(new URL("..", import.meta.url));
let serverProcess = null;
try {
  const health = await fetch("http://127.0.0.1:8000/api/health");
  if (!health.ok) throw new Error("server unavailable");
} catch {
  serverProcess = spawn("python3", ["server.py"], { cwd: projectRoot, stdio: "ignore" });
  process.on("exit", () => serverProcess?.kill());
  const serverDeadline = Date.now() + 15000;
  while (Date.now() < serverDeadline) {
    try {
      const health = await fetch("http://127.0.0.1:8000/api/health");
      if (health.ok) break;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

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
const calls = { selected: [], cleared: 0, modes: [] };
globalThis.OpenBIMViewer = {
  async loadIfcGeometry() { return 5; },
  getGeometryDiagnostics() {
    return {
      engine: "web-ifc",
      origin_mode: "model-centred",
      element_ids: [57, 68, 73, 77, 85, 103, 104],
      element_extents_metres: {
        57: [8, 0.2, 3], 68: [0.2, 6, 3], 73: [8, 0.2, 3],
        77: [0.2, 6, 3], 85: [8, 6, 0.2], 103: [0.2, 1, 0.2],
        104: [8, 0.2, 3],
      },
    };
  },
  selectExpressIDs(ids) { calls.selected.push(...ids); return true; },
  selectExpressID(id) { calls.selected.push(id); return true; },
  clearSelection() { calls.cleared += 1; },
  setSelectionMode(mode) { calls.modes.push(mode); return true; },
  async runGpuValidation() {
    return {
      passed: true,
      rendering_capability_passed: true,
      interactive_performance_passed: true,
      probe_duration_ms: 2000,
      probe_frames: 120,
      average_fps: 60,
      geometry: { mesh_groups: 5, triangles: 1200 },
      renderer: { webgl_version: "WebGL 2", renderer: "Test GPU" },
      checks: [
        { id: "webgl_context", passed: true, message: "WebGL 2 context is active." },
        { id: "visible_meshes", passed: true, message: "5 mesh groups are loaded." },
      ],
      claim_boundary: "Browser rendering evidence only.",
    };
  },
};

await import(`../web/app.js?frontend-test=${Date.now()}`);
document.querySelector("#demoButton").click();

const deadline = Date.now() + 15000;
while (document.querySelectorAll(".issue-action").length === 0 && Date.now() < deadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}

assert.equal(
  document.querySelector("#workspace").classList.contains("hidden"),
  false,
  `demo analysis opens the workspace (${document.querySelector("#toast").textContent || "no UI error"})`,
);
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
assert.equal(document.querySelector("#selectionModeSelect").classList.contains("hidden"), false, "selection visibility control becomes visible");
document.querySelector("#selectionModeSelect").value = "isolate";
document.querySelector("#selectionModeSelect").dispatchEvent(new window.Event("change"));
assert.equal(calls.modes.at(-1), "isolate", "isolate mode is forwarded to the viewer");

window.dispatchEvent(new window.CustomEvent("ifc-element-selected", { detail: { expressID: 85 } }));
assert.equal(document.querySelector('.issue-action[data-entity-id="85"]').classList.contains("selected"), true, "direct 3D selection synchronizes the issue list");

document.querySelector("#clearSelectionButton").click();
assert.equal(calls.cleared > 0, true, "clear selection calls the viewer reset");
assert.equal(document.querySelectorAll(".issue-action.selected").length, 0, "clear selection removes issue highlighting");
assert.equal(document.querySelector("#clearSelectionButton").classList.contains("hidden"), true, "clear-selection control hides after reset");
assert.equal(document.querySelector("#selectionModeSelect").classList.contains("hidden"), true, "selection visibility control hides after reset");

document.querySelector("#sampleIdsButton").click();
const idsDeadline = Date.now() + 5000;
while (document.querySelector("#idsStatus").classList.contains("hidden") && Date.now() < idsDeadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}
assert.equal(document.querySelector("#idsStatus").classList.contains("hidden"), false, "sample IDS validation reports its status");
assert.match(document.querySelector("#idsStatus").textContent, /1 failure/, "IDS failure count is visible");
assert.ok(document.querySelector('[data-rule-id="ids:wall-name"][data-entity-id="73"]'), "IDS issue remains linked to wall #73");
assert.equal(document.querySelector("#bcfButton").disabled, false, "BCF export is available after analysis");

assert.equal(document.querySelector("#gpuValidationButton").disabled, false, "GPU check unlocks after geometry loads");
document.querySelector("#gpuValidationButton").click();
const gpuDeadline = Date.now() + 5000;
while (!/Browser rendering and interactive performance passed/.test(document.querySelector("#gpuValidationStatus").textContent) && Date.now() < gpuDeadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}
assert.match(document.querySelector("#gpuValidationStatus").textContent, /Browser rendering and interactive performance passed/, "GPU evidence is visible");
assert.match(document.querySelector("#gpuValidationStatus").textContent, /60 average FPS/, "GPU frame probe result is visible");

assert.equal(document.querySelector("#geometryCheckButton").disabled, true, "experimental checks are gated before Stage 1 validation");
const capabilityDeadline = Date.now() + 5000;
while (document.querySelector("#geometryDiagnosticsButton").disabled && Date.now() < capabilityDeadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}
assert.equal(document.querySelector("#geometryDiagnosticsButton").disabled, false, "Stage 1 validation is enabled when IfcOpenShell is ready");
document.querySelector("#geometryDiagnosticsButton").click();
const diagnosticDeadline = Date.now() + 10000;
while (!/Stage 1 extraction evidence (passed|needs attention)/.test(document.querySelector("#geometryDiagnosticsStatus").textContent) && Date.now() < diagnosticDeadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}
assert.equal(document.querySelector("#geometryDiagnosticsStatus").classList.contains("hidden"), false, "Stage 1 diagnostic status becomes visible");
assert.match(document.querySelector("#geometryDiagnosticsStatus").textContent, /Stage 1 extraction evidence passed/, "geometry extraction evidence explicitly passes");
assert.match(document.querySelector("#geometryDiagnosticsStatus").textContent, /7\/7 represented shapes \(100%\)/, "shape coverage is visible");
assert.match(document.querySelector("#geometryDiagnosticsStatus").textContent, /Known-answer matrix: 6\/6 cases passed/, "known-answer factual matrix is visible");
assert.match(document.querySelector("#geometryDiagnosticsStatus").textContent, /does not prove that the model matches drawings/, "claim boundary is visible");
assert.equal(document.querySelector("#geometryCheckButton").disabled, false, "experimental checks unlock only after Stage 1 passes");
assert.equal(document.querySelector("#geometryEvidenceButton").disabled, false, "evidence export unlocks after validation");

document.querySelector("#geometryCheckButton").click();
const geometryDeadline = Date.now() + 10000;
while (document.querySelector("#geometryStatus").classList.contains("hidden") && Date.now() < geometryDeadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}
assert.equal(document.querySelector("#geometryStatus").classList.contains("hidden"), false, "coordination check status becomes visible");
assert.match(document.querySelector("#geometryStatus").textContent, /1 candidate pair/, "exact duplicate candidate count is visible");
assert.match(document.querySelector("#geometryStatus").textContent, /4\/4 assertions passed/, "Stage 2 known-answer matrix is visible");
const duplicateIssue = document.querySelector('[data-rule-id="exact_duplicate_candidate"][data-entity-id="104"]');
assert.ok(duplicateIssue, "exact duplicate wall pair is linked to geometry");
duplicateIssue.click();
assert.deepEqual(calls.selected.slice(-2), [104, 57], "duplicate issue highlights both elements in the pair");
assert.ok(document.querySelector('[data-rule-id="ids:wall-name"]'), "IDS findings remain after geometry checks");

serverProcess?.kill();
console.log("frontend interaction tests passed");

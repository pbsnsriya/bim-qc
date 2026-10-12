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
  localStorage: window.localStorage,
  addEventListener: window.addEventListener.bind(window),
});

const nativeFetch = globalThis.fetch;
globalThis.fetch = (input, init) => nativeFetch(new URL(String(input), window.location.href), init);
const testBackend = await (await fetch('/api/geometry-diagnostics', {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({content: await fs.readFile(new URL('../samples/geometry_demo.ifc', import.meta.url), 'utf8')}),
})).json();
const calls = { selected: [], cleared: 0, modes: [] };
calls.markers = [];
globalThis.OpenBIMViewer = {
  async loadIfcGeometry() { return 5; },
  getGeometryDiagnostics() {
    return {
      engine: "web-ifc",
      origin_mode: "model-centred",
      bounds_frame: "IFC world Z-up metres",
      element_bounds_metres: Object.fromEntries(Object.entries(testBackend.element_bounds_metres)),
      element_shape_metrics: testBackend.element_shape_metrics,
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
  showOpeningBoundsMarker(bounds) { if (!bounds) return false; calls.markers.push(bounds); return true; },
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
      renderer: { webgl_version: "WebGL 2", renderer: "Test GPU", render_calls: 3, rendering: { render_batches: 2 }, selected_element_ids: [] },
      checks: [
        { id: "webgl_context", passed: true, message: "WebGL 2 context is active." },
        { id: "visible_meshes", passed: true, message: "5 mesh groups are loaded." },
      ],
      claim_boundary: "Browser rendering evidence only.",
    };
  },
};

const appModule = await import(`../web/app.js?frontend-test=${Date.now()}`);
assert.equal(
  appModule.duplicateStageAvailable({ ready: false, stage2_ready: true }),
  true,
  "Stage 2 can run when its prerequisites pass even if strict Stage 1 extent evidence needs attention",
);
assert.equal(
  appModule.duplicateStageAvailable({ ready: true, stage2_ready: false }),
  false,
  "strict Stage 1 status cannot bypass failed Stage 2 prerequisites",
);
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
assert.equal(document.querySelector("#gpuEvidenceButton").disabled, false, "standalone GPU export unlocks without waiting for Stage 1 extraction");
assert.match(document.querySelector("#gpuValidationStatus").textContent, /2 render batches.*3 draw calls/, "batch and measured draw counts are visible");
let exportedBlob;
let exportedName;
const createObjectURL = URL.createObjectURL;
const anchorClick = window.HTMLAnchorElement.prototype.click;
URL.createObjectURL = blob => { exportedBlob = blob; return createObjectURL(blob); };
window.HTMLAnchorElement.prototype.click = function () { exportedName = this.download; };
document.querySelector("#gpuEvidenceButton").click();
const exportedGpu = JSON.parse(await exportedBlob.text());
assert.match(exportedName, /-gpu-evidence\.json$/);
assert.equal(exportedGpu.report_type, "OpenBIM QC browser/GPU evidence");
assert.equal(exportedGpu.exporter_version, "0.7.16");
assert.equal(exportedGpu.browser_gpu_validation.average_fps, 60);
assert.match(exportedGpu.claim_boundary, /backend extraction.*not evaluated/);
URL.createObjectURL = createObjectURL;
window.HTMLAnchorElement.prototype.click = anchorClick;
let framed = 0;
globalThis.OpenBIMViewer.frameModel = () => { framed++; return true; };
document.querySelector("#frameModelButton").click();
assert.equal(framed, 1, "frame model returns to a full-model performance comparison view");

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
assert.match(document.querySelector("#geometryDiagnosticsStatus").textContent, /Known-answer matrix: 10\/10 cases passed/, "known-answer factual matrix is visible");
assert.match(document.querySelector("#geometryDiagnosticsStatus").textContent, /does not prove that the model matches drawings/, "claim boundary is visible");
assert.equal(document.querySelector("#geometryCheckButton").disabled, false, "experimental checks unlock only after Stage 1 passes");
assert.match(document.querySelector('#geometryDiagnosticsStatus').textContent, /Project compliance: NOT EVALUATED/, 'project compliance stays separate from extraction evidence');
assert.match(document.querySelector('#geometryDiagnosticsStatus').textContent, /Acceptance rules and measurements/, 'rule sources and measured values are available in the UI');
assert.match(document.querySelector('#geometryDiagnosticsStatus').textContent, /Critical unresolved geometry: 0/, 'critical geometry is visible even at full coverage');
assert.equal(document.querySelector("#geometryEvidenceButton").disabled, false, "evidence export unlocks after validation");

document.querySelector("#geometryCheckButton").click();
const geometryDeadline = Date.now() + 10000;
while (document.querySelector("#geometryStatus").classList.contains("hidden") && Date.now() < geometryDeadline) {
  await new Promise((resolve) => setTimeout(resolve, 25));
}
assert.equal(document.querySelector("#geometryStatus").classList.contains("hidden"), false, "coordination check status becomes visible");
assert.match(document.querySelector("#geometryStatus").textContent, /1 candidate pair/, "exact duplicate candidate count is visible");
assert.match(document.querySelector("#geometryStatus").textContent, /6\/6 assertions passed/, "Stage 2 known-answer matrix is visible");
assert.equal(document.querySelector("#ruleFilter").value, "duplicate_review", "Stage 2 automatically filters Quality Review to all duplicate candidate types");
assert.equal(document.querySelectorAll('.issue-action[data-rule-id="exact_duplicate_candidate"]').length, 1, "filtered duplicate findings are immediately visible");
const duplicateIssue = document.querySelector('[data-rule-id="exact_duplicate_candidate"][data-entity-id="104"]');
assert.ok(duplicateIssue, "exact duplicate wall pair is linked to geometry");
let comparisonRequestCount = 0;
const fetchWithComparison = globalThis.fetch;
globalThis.fetch = (input, init) => {
  if (String(input) === "/api/compare-elements" && ++comparisonRequestCount === 1) {
    return Promise.resolve(new Response(JSON.stringify({ error: "Temporary comparison failure" }), {
      status: 500, headers: { "Content-Type": "application/json" },
    }));
  }
  return fetchWithComparison(input, init);
};
duplicateIssue.click();
assert.deepEqual(calls.selected.slice(-2), [104, 57], "duplicate issue highlights both elements in the pair");
const reviewRow = duplicateIssue.closest(".duplicate-review-row");
assert.ok(reviewRow, "duplicate candidate exposes a review workflow");
const retryDeadline = Date.now() + 10000;
while (!reviewRow.querySelector(".comparison-retry") && Date.now() < retryDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.match(reviewRow.querySelector(".pair-comparison-content").textContent, /Temporary comparison failure/, "failure is visible rather than an empty panel");
reviewRow.querySelector(".comparison-retry").click();
const comparisonDeadline = Date.now() + 10000;
while (!reviewRow.querySelector(".pair-table") && Date.now() < comparisonDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.ok(reviewRow.querySelector(".pair-comparison").open, "selecting a duplicate opens its comparison panel");
assert.ok(reviewRow.querySelector(".pair-table"), "side-by-side fields load from the stored model API");
assert.match(reviewRow.querySelector('[data-field="dimensions_mm"]').textContent, /Same/, "duplicate dimensions compare as matching");
assert.match(reviewRow.querySelector('[data-field="global_id"]').textContent, /Identity differs/, "distinct GlobalIds are separated from physical differences");
assert.match(reviewRow.querySelector('[data-field="phase_status"]').textContent, /Not evaluated/, "missing phase information is not reported as passing");
assert.equal(reviewRow.querySelector(".review-decision").value, "unresolved", "comparison does not change the review decision");
const reviewNote = reviewRow.querySelector(".review-note");
const reviewDecision = reviewRow.querySelector(".review-decision");
reviewNote.value = "Confirmed accidental overlapping wall";
reviewDecision.value = "confirmed_duplicate";
reviewDecision.dispatchEvent(new window.Event("change", { bubbles: true }));
assert.match(document.querySelector("#duplicateReviewSummary").textContent, /1 confirmed/, "truth-matrix summary updates after review");
assert.match(document.querySelector("#duplicateReviewSummary").textContent, /confirmation rate 100%/, "review decisions are labelled as a confirmation rate");
assert.match(document.querySelector("#duplicateReviewSummary").textContent, /not measured detection accuracy/, "a review rate does not certify accuracy");
assert.equal(document.querySelector(".duplicate-review-row.confirmed_duplicate") !== null, true, "confirmed review receives visible state");
assert.ok(document.querySelector(".pair-comparison").open, "saving review keeps the comparison open");
assert.ok(document.querySelector(".pair-table"), "cached comparison survives review rerender");
assert.equal(comparisonRequestCount, 2, "saving a decision reuses the successful comparison after a retry");
const reviewStorageKey = Object.keys(window.localStorage).find((key) => key.startsWith("openbim-qc:duplicate-reviews:v1:"));
assert.ok(reviewStorageKey, "review ledger is persisted for the loaded IFC");
const persistedReviews = JSON.parse(window.localStorage.getItem(reviewStorageKey));
assert.equal(persistedReviews["exact_duplicate_candidate|57|104"].review_status, "confirmed_duplicate", "persisted ledger stores the decision by canonical pair key");
assert.equal(persistedReviews["exact_duplicate_candidate|57|104"].review_note, "Confirmed accidental overlapping wall", "persisted ledger stores reviewer evidence");
const truthRows = appModule.buildDuplicateTruthMatrix([{
  rule_id: "exact_duplicate_candidate", entity_id: 104, related_entity_id: 57,
  selection_ids: [104, 57], review_status: "confirmed_duplicate", review_note: "Confirmed overlap",
}], "geometry_demo.ifc", "2026-10-03T00:00:00.000Z");
assert.deepEqual(truthRows[0], {
  model_filename: "geometry_demo.ifc", exported_at: "2026-10-03T00:00:00.000Z",
  pair_key: "exact_duplicate_candidate|57|104", rule_id: "exact_duplicate_candidate",
  candidate_type: "physical_element", entity_id: 104, related_entity_id: 57,
  opening_ids: [], host_entity_ids: [], selection_ids: [104, 57],
  review_status: "confirmed_duplicate", review_note: "Confirmed overlap", reviewed_at: "",
  confidence: "", tolerance_mm: "", detection_basis: "",
  placement_offset_mm: "", translation_mm: [], shape_residual_mm: "", shape_tolerance_mm: "",
}, "truth-matrix export preserves the reviewed decision and evidence");
document.querySelector("#ruleFilter").value = "ids:wall-name";
document.querySelector("#ruleFilter").dispatchEvent(new window.Event("change"));
assert.ok(document.querySelector('[data-rule-id="ids:wall-name"]'), "IDS findings remain available after geometry checks");

// Exercise the real opening fixture through upload, Stage 1, Stage 2 and comparison API.
globalThis.fetch = fetchWithComparison;
const openingText = await fs.readFile(new URL('../samples/golden/duplicate_exact_matrix.ifc', import.meta.url), 'utf8');
const openingBackend = await (await fetch('/api/geometry-diagnostics', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: openingText}),
})).json();
globalThis.OpenBIMViewer.getGeometryDiagnostics = () => ({
  engine: 'web-ifc', origin_mode: 'model-centred', bounds_frame: 'IFC world Z-up metres', mesh_groups: 6,
  element_bounds_metres: openingBackend.element_bounds_metres,
  element_shape_metrics: openingBackend.element_shape_metrics,
  element_ids: Object.keys(openingBackend.element_extents_metres).map(Number),
  element_extents_metres: openingBackend.element_extents_metres,
});
const uploadInput = document.querySelector('#fileInput');
Object.defineProperty(uploadInput, 'files', {configurable: true, value: [new File([openingText], 'duplicate_exact_matrix.ifc')]});
uploadInput.dispatchEvent(new window.Event('change'));
let hostDeadline = Date.now() + 10000;
while (!document.querySelector('.model-node[data-entity-id="48"]') && Date.now() < hostDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.ok(document.querySelector('.model-node[data-entity-id="48"]'), 'opening fixture is uploaded as a new source');
document.querySelector('#geometryDiagnosticsButton').click();
hostDeadline = Date.now() + 10000;
while (document.querySelector('#geometryCheckButton').disabled && Date.now() < hostDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.equal(document.querySelector('#geometryCheckButton').disabled, false, 'opening fixture passes its readiness prerequisites');
document.querySelector('#geometryCheckButton').click();
hostDeadline = Date.now() + 10000;
while (!document.querySelector('[data-rule-id="duplicate_opening_candidate"]') && Date.now() < hostDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
const openingIssue = document.querySelector('[data-rule-id="duplicate_opening_candidate"]');
assert.ok(openingIssue, 'Stage 2 returns the known coincident opening pair');
openingIssue.click();
const openingReview = openingIssue.closest('.duplicate-review-row');
hostDeadline = Date.now() + 10000;
while (!openingReview.querySelector('.comparison-highlight-hosts') && Date.now() < hostDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
const hostButton = openingReview.querySelector('.comparison-highlight-hosts');
assert.ok(hostButton, 'opening comparison offers the host control');
assert.equal(hostButton.tagName, 'BUTTON', 'host selection uses a native keyboard-accessible button');
assert.equal(hostButton.disabled, false);
assert.match(openingReview.querySelector('[data-field="opening_hosts"]').textContent, /#48.*Opening host A.*#49.*Opening host B.*Different hosts/s);
assert.match(openingReview.querySelector('[data-field="material"]').textContent, /Not applicable/);
assert.match(openingReview.querySelector('[data-field="phase_status"]').textContent, /Not evaluated/);
const selectedBeforeHosts = calls.selected.length;
hostButton.click();
assert.deepEqual(calls.selected.slice(selectedBeforeHosts), [48, 49], 'host button selects the two host elements, not subtraction voids');
assert.match(document.querySelector('#viewerStatus').textContent, /Opening hosts #48 ↔ #49.*Highlighted/);
assert.equal(document.querySelector('.model-node[data-entity-id="48"]').classList.contains('selected'), true, 'primary host remains synchronized with the data map');
assert.equal(openingReview.querySelector('.review-decision').value, 'unresolved', 'highlighting does not decide author intent');
assert.equal(openingReview.querySelector('.review-note').value, '', 'highlighting does not invent reviewer evidence');
const openingHostButton = openingReview.querySelector('.comparison-highlight-opening-host');
assert.ok(openingHostButton, 'each measured opening-host relationship has a native selection button');
assert.equal(openingHostButton.tagName, 'BUTTON');
assert.match(openingReview.querySelector('.opening-host-evidence').textContent, /Unresolved — bounds overlap or touch/);
assert.match(openingReview.querySelector('.opening-host-evidence').textContent, /not an industry or project acceptance standard/);
assert.match(openingReview.querySelector('.opening-host-evidence').textContent, /Independent of near-duplicate placement tolerance/);
const selectedBeforeOpeningHost = calls.selected.length;
globalThis.OpenBIMViewer.getRenderingDiagnostics = () => ({selected_element_ids: [48]});
openingHostButton.click();
assert.deepEqual(calls.selected.slice(selectedBeforeOpeningHost), [44, 48], 'request the opening itself and its explicit host, not the two candidate hosts');
assert.match(document.querySelector('#viewerStatus').textContent, /Opening #44 \+ host #48.*Partial highlight; geometry unavailable for #44.*Cyan opening bounds marker; not opening geometry/);
assert.ok(calls.markers.at(-1), 'unrendered opening receives a measured bounds marker');
assert.equal(openingReview.querySelector('.review-decision').value, 'unresolved', 'screening and locating must not decide duplication');
globalThis.OpenBIMViewer.getRenderingDiagnostics = () => ({selected_element_ids: [44, 48]});
const markersBefore = calls.markers.length;
openingHostButton.click();
assert.match(document.querySelector('#viewerStatus').textContent, /Opening #44 \+ host #48 · Highlighted/);
assert.equal(calls.markers.length, markersBefore, 'a rendered opening does not need a fallback marker');
// Successfully opened comparisons, including source fingerprint and numerical
// evidence, are preserved in JSON; unopened cards are not silently certified.
URL.createObjectURL = blob => { exportedBlob = blob; return createObjectURL(blob); };
window.HTMLAnchorElement.prototype.click = () => {};
document.querySelector('#jsonButton').click();
const openingJson = JSON.parse(await exportedBlob.text());
const exportedComparison = openingJson.pair_comparisons[openingReview.querySelector('.pair-comparison').dataset.comparisonKey];
assert.ok(exportedComparison?.opening_host_checks, 'JSON includes measured opening-host evidence');
assert.equal(exportedComparison.source_sha256, openingJson.model_sha256);
assert.match(openingJson.pair_comparison_export_scope, /unopened or failed comparisons are not evaluated/);
URL.createObjectURL = createObjectURL;
window.HTMLAnchorElement.prototype.click = anchorClick;
globalThis.OpenBIMViewer.getRenderingDiagnostics = () => ({selected_element_ids: [48]});
hostButton.click();
assert.match(document.querySelector('#viewerStatus').textContent, /Some geometry is unavailable \(#49\)/, 'partial selection is disclosed');
const selectHosts = globalThis.OpenBIMViewer.selectExpressIDs;
globalThis.OpenBIMViewer.selectExpressIDs = () => false;
hostButton.click();
assert.match(document.querySelector('#viewerStatus').textContent, /Geometry is not currently selectable/, 'unavailable host geometry is not reported as highlighted');
globalThis.OpenBIMViewer.selectExpressIDs = selectHosts;
delete globalThis.OpenBIMViewer.getRenderingDiagnostics;
document.querySelector('#clearSelectionButton').click();
assert.equal(document.querySelectorAll('.model-node.selected').length, 0, 'clear resets host selection');

// Missing explicit relationships must remain visible, with no enabled host action.
const {renderPairComparison} = await import('../web/pair-comparison.js');
const withoutHosts = openingText.replace(/^#(?:46|47)=.*\n/gm, '');
const missingHostResult = await (await fetch('/api/compare-elements', {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({content: withoutHosts, element_ids: [44, 45]}),
})).json();
const missingHostDom = document.createElement('div');
missingHostDom.innerHTML = renderPairComparison(missingHostResult);
assert.equal(missingHostDom.querySelectorAll('.host-check-not_evaluated').length, 2);
assert.equal(missingHostDom.querySelector('.comparison-highlight-opening-host').disabled, true);
const separatedText = await fs.readFile(new URL('../samples/golden/opening_host_matrix.ifc', import.meta.url), 'utf8');
const separatedResult = await (await fetch('/api/compare-elements', {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({content: separatedText, element_ids: [32, 57]}),
})).json();
const separatedDom = document.createElement('div');
separatedDom.innerHTML = renderPairComparison(separatedResult);
assert.match(separatedDom.querySelector('.host-check-separated').textContent, /Opening #57.*Host #45.*Measured separation.*8000 mm/s);
assert.match(separatedDom.querySelector('.host-check-method').textContent, /Overlapping bounds are Unresolved, never a valid-cut PASS/);
assert.equal(separatedDom.querySelectorAll('.host-check-bounds_overlap').length, 1);
assert.equal(missingHostDom.querySelector('.comparison-highlight-hosts').disabled, true);
assert.match(missingHostDom.querySelector('[data-field="opening_hosts"]').textContent, /Not evaluated/);
assert.equal(missingHostDom.querySelectorAll('.comparison-warning').length, 2, 'each opening without a host gets an explicit warning');

// Run the supplied near-duplicate matrix end to end using real backend geometry.
const nearText = await fs.readFile(new URL('../samples/golden/duplicate_near_matrix.ifc', import.meta.url), 'utf8');
const nearBackend = await (await fetch('/api/geometry-diagnostics', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: nearText}),
})).json();
globalThis.OpenBIMViewer.getGeometryDiagnostics = () => ({
  engine: 'web-ifc', origin_mode: 'model-centred', bounds_frame: 'IFC world Z-up metres', mesh_groups: 21,
  element_bounds_metres: nearBackend.element_bounds_metres,
  element_shape_metrics: nearBackend.element_shape_metrics,
  element_ids: Object.keys(nearBackend.element_extents_metres).map(Number),
  element_extents_metres: nearBackend.element_extents_metres,
});
Object.defineProperty(uploadInput, 'files', {configurable: true, value: [new File([nearText], 'duplicate_near_matrix.ifc')]});
uploadInput.dispatchEvent(new window.Event('change'));
let nearDeadline = Date.now() + 10000;
while (document.querySelector('#modelName').textContent !== 'duplicate_near_matrix.ifc' && Date.now() < nearDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.equal(document.querySelector('#modelName').textContent, 'duplicate_near_matrix.ifc');
document.querySelector('#geometryDiagnosticsButton').click();
nearDeadline = Date.now() + 10000;
while (document.querySelector('#geometryCheckButton').disabled && Date.now() < nearDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.equal(document.querySelector('#nearDuplicateTolerance').value, '5', 'review tolerance starts at 5 mm');
document.querySelector('#geometryCheckButton').click();
nearDeadline = Date.now() + 10000;
while (!document.querySelector('[data-rule-id="near_duplicate_candidate"]') && Date.now() < nearDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.equal(document.querySelectorAll('[data-rule-id="near_duplicate_candidate"]').length, 4, '5 mm fixture produces four known near pairs');
assert.match(document.querySelector('#geometryStatus').textContent, /Near-duplicate reference matrix: 12\/12 assertions passed/);
const nearIssue = document.querySelector('[data-rule-id="near_duplicate_candidate"]');
const nearIDs = nearIssue.dataset.selectionIds.split(',').map(Number);
const beforeNear = calls.selected.length;
nearIssue.click();
assert.deepEqual(calls.selected.slice(beforeNear), nearIDs, 'near pair highlights both elements');
let nearReview = nearIssue.closest('.duplicate-review-row');
assert.match(nearReview.querySelector('.near-pair-evidence').textContent, /Centre offset.*configured limit 5 mm.*surface residual/s);
nearDeadline = Date.now() + 10000;
while (!nearReview.querySelector('.pair-table') && Date.now() < nearDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.ok(nearReview.querySelector('.pair-comparison').open);
assert.match(nearReview.querySelector('[data-field="dimensions_mm"]').textContent, /Same/);
assert.match(nearReview.querySelector('[data-field="position_metres"]').textContent, /Different/);
assert.equal(nearReview.querySelector('.review-decision').value, 'unresolved');
const nearKey = nearReview.querySelector('[data-review-key]').dataset.reviewKey;
nearReview.querySelector('.review-note').value = 'Intentional placement retained for test review';
nearReview.querySelector('.review-decision').value = 'intentional_not_duplicate';
nearReview.querySelector('.review-decision').dispatchEvent(new window.Event('change', {bubbles: true}));
assert.equal(document.querySelector(`[data-review-key="${nearKey}"] .review-decision`).value, 'intentional_not_duplicate');
const ledgerKey = Object.keys(localStorage).find(key => key.startsWith('openbim-qc:duplicate-reviews:v1:') && JSON.parse(localStorage.getItem(key))[nearKey]);
assert.equal(JSON.parse(localStorage.getItem(ledgerKey))[nearKey].review_note, 'Intentional placement retained for test review');

URL.createObjectURL = blob => { exportedBlob = blob; return createObjectURL(blob); };
window.HTMLAnchorElement.prototype.click = function () { exportedName = this.download; };
document.querySelector('#truthMatrixButton').click();
const nearCsv = await exportedBlob.text();
assert.match(nearCsv, /placement_offset_mm.*translation_mm.*shape_residual_mm.*shape_tolerance_mm/);
assert.match(nearCsv, /near_physical_element/);
assert.match(nearCsv, /Intentional placement retained for test review/);
document.querySelector('#jsonButton').click();
const nearJson = JSON.parse(await exportedBlob.text());
assert.equal(nearJson.geometry_validation.near_duplicate_scan.tolerance_mm, 5);
assert.equal(nearJson.geometry_validation.near_duplicate_acceptance_matrix.passed_cases, 12);
assert.equal(nearJson.model_sha256.length, 64);
assert.equal(nearJson.exporter_version, '0.7.16');
assert.equal(nearJson.duplicate_review_summary.detection_accuracy_status, 'not_measured_by_review_decisions_alone');
URL.createObjectURL = createObjectURL;
window.HTMLAnchorElement.prototype.click = anchorClick;

document.querySelector('#nearDuplicateTolerance').value = '1';
document.querySelector('#nearDuplicateTolerance').dispatchEvent(new window.Event('change'));
assert.equal(document.querySelector('#duplicateSettingsHint').classList.contains('hidden'), false);
document.querySelector('#geometryCheckButton').click();
nearDeadline = Date.now() + 10000;
while ((document.querySelector('#geometryCheckButton').disabled || !/placement limit 1 mm/.test(document.querySelector('#geometryStatus').textContent)) && Date.now() < nearDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.equal(document.querySelectorAll('[data-rule-id="near_duplicate_candidate"]').length, 0, '1 mm excludes all shifted fixture pairs');
assert.equal(document.querySelector('#duplicateSettingsHint').classList.contains('hidden'), true);
document.querySelector('#nearDuplicateTolerance').value = '5';
document.querySelector('#nearDuplicateTolerance').dispatchEvent(new window.Event('change'));
document.querySelector('#geometryCheckButton').click();
nearDeadline = Date.now() + 10000;
while (!document.querySelector(`[data-review-key="${nearKey}"]`) && Date.now() < nearDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.equal(document.querySelector(`[data-review-key="${nearKey}"] .review-decision`).value, 'intentional_not_duplicate', 'review survives tolerance changes and reruns');
document.querySelector('#nearDuplicatesCheckbox').checked = false;
document.querySelector('#nearDuplicatesCheckbox').dispatchEvent(new window.Event('change'));
assert.equal(document.querySelector('#nearDuplicateTolerance').disabled, true);
document.querySelector('#geometryCheckButton').click();
nearDeadline = Date.now() + 10000;
while (!/Near-duplicate scan disabled/.test(document.querySelector('#geometryStatus').textContent) && Date.now() < nearDeadline) {
  await new Promise(resolve => setTimeout(resolve, 25));
}
assert.equal(document.querySelectorAll('[data-rule-id="near_duplicate_candidate"]').length, 0);
assert.equal(document.querySelectorAll('[data-rule-id="exact_duplicate_candidate"]').length, 1, 'disabling near checks retains exact detection');

// The Stage 3 reference probe must expose, rather than hide, known engine misses.
document.querySelector('#hardClashReferenceButton').click();
let clashDeadline = Date.now()+10000;
while (document.querySelector('#hardClashEvidenceButton').disabled && Date.now()<clashDeadline) {
  await new Promise(resolve => setTimeout(resolve,25));
}
assert.match(document.querySelector('#hardClashReferenceStatus').textContent,/REFERENCE PASS.*30\/30/);
assert.equal(document.querySelectorAll('#hardClashReferenceStatus tbody tr').length,30);
assert.equal(document.querySelector('#hardClashModelButton').disabled,false);
assert.match(document.querySelector('#hardClashReferenceStatus').textContent,/Original kernel baseline: 14\/18/);
URL.createObjectURL = blob => {exportedBlob=blob; return createObjectURL(blob);};
window.HTMLAnchorElement.prototype.click = function () {exportedName=this.download;};
document.querySelector('#hardClashEvidenceButton').click();
const clashJson=JSON.parse(await exportedBlob.text());
assert.equal(exportedName,'stage3-hard-clash-reference.json');
assert.equal(clashJson.exporter_version,'0.7.16');
assert.equal(clashJson.model_clash_checking_enabled,true);
assert.equal(clashJson.failed_cases,0);
document.querySelector('#jsonButton').click();
const withReference=JSON.parse(await exportedBlob.text());
assert.equal(withReference.hard_clash_reference.failed_cases,0);
assert.equal(withReference.model_hard_clash_status,'not_evaluated');
// Exercise the bounded pilot with a simulated viewer evidence mapping. These
// assertions test UI integration, not a real GPU or independent viewer truth.
const pilotText=await fs.readFile(new URL('../samples/golden/hard_clash_pilot.ifc',import.meta.url),'utf8');
const pilotBackend=await (await fetch('/api/geometry-diagnostics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:pilotText})})).json();
const omissions=new Set(pilotBackend.cross_engine.expected_browser_omissions.map(e=>e.step_id));
const mapped=Object.keys(pilotBackend.element_extents_metres).map(Number).filter(id=>!omissions.has(id));
const priorDiagnostics=globalThis.OpenBIMViewer.getGeometryDiagnostics;
globalThis.OpenBIMViewer.getGeometryDiagnostics=()=>({engine:'web-ifc',mesh_groups:mapped.length,element_ids:mapped,
  element_extents_metres:Object.fromEntries(mapped.map(id=>[id,pilotBackend.element_extents_metres[id]])),
  element_bounds_metres:Object.fromEntries(mapped.map(id=>[id,pilotBackend.element_bounds_metres[id]])),
  element_shape_metrics:Object.fromEntries(mapped.map(id=>[id,pilotBackend.element_shape_metrics[id]]))});
document.querySelector('#hardClashSampleButton').click();
let pilotDeadline=Date.now()+10000;
while(document.querySelector('#modelName').textContent!=='hard_clash_pilot.ifc' && Date.now()<pilotDeadline) await new Promise(resolve=>setTimeout(resolve,25));
assert.equal(document.querySelector('#modelName').textContent,'hard_clash_pilot.ifc');
assert.equal(document.querySelector('#hardClashModelButton').disabled,true,'new model resets extraction readiness');
document.querySelector('#geometryDiagnosticsButton').click();
pilotDeadline=Date.now()+10000;
while(document.querySelector('#hardClashModelButton').disabled && Date.now()<pilotDeadline) await new Promise(resolve=>setTimeout(resolve,25));
assert.equal(document.querySelector('#hardClashModelButton').disabled,false,'reference and extraction readiness unlock pilot');
document.querySelector('#hardClashModelButton').click();
pilotDeadline=Date.now()+15000;
while(!/5 hard-clash candidate/.test(document.querySelector('#hardClashModelStatus').textContent) && Date.now()<pilotDeadline) await new Promise(resolve=>setTimeout(resolve,25));
assert.match(document.querySelector('#hardClashModelStatus').textContent,/needs attention.*5 hard-clash candidate.*1 unresolved intersection/s);
assert.equal(document.querySelector('#ruleFilter').value,'hard_clash_review');
assert.equal(document.querySelectorAll('[data-rule-id="hard_clash"]').length,5);
assert.equal(document.querySelectorAll('[data-rule-id="hard_clash_depth_unresolved"]').length,1);
const clashCard=document.querySelector('[data-rule-id="hard_clash"]');
const beforeClash=calls.selected.length;
clashCard.click();
assert.deepEqual(calls.selected.slice(beforeClash),clashCard.dataset.selectionIds.split(',').map(Number),'hard-clash card requests both elements');
document.querySelector('#clearSelectionButton').click();
document.querySelector('#jsonButton').click();
const pilotReport=JSON.parse(await exportedBlob.text());
assert.equal(pilotReport.hard_clash_validation.summary.candidate_pairs,5);
assert.equal(pilotReport.hard_clash_validation.source_sha256,pilotReport.model_sha256);
assert.equal(pilotReport.model_hard_clash_status,'selected_scope_needs_attention');
document.querySelector('#hardClashIds').value='20, 32';
document.querySelector('#hardClashIds').dispatchEvent(new window.Event('change'));
assert.equal(document.querySelector('#hardClashSettingsHint').classList.contains('hidden'),false);
document.querySelector('#hardClashModelButton').click();
pilotDeadline=Date.now()+15000;
while(!/scope evaluated.*1 hard-clash candidate/.test(document.querySelector('#hardClashModelStatus').textContent) && Date.now()<pilotDeadline) await new Promise(resolve=>setTimeout(resolve,25));
assert.match(document.querySelector('#hardClashModelStatus').textContent,/scope evaluated.*1 hard-clash candidate.*explicit subset only/s);
assert.equal(document.querySelector('#hardClashSettingsHint').classList.contains('hidden'),true);
document.querySelector('#jsonButton').click();
const selectedPilot=JSON.parse(await exportedBlob.text());
assert.deepEqual(selectedPilot.hard_clash_validation.selected_element_ids,[20,32]);
assert.equal(selectedPilot.model_hard_clash_status,'selected_scope_evaluated');
globalThis.OpenBIMViewer.getGeometryDiagnostics=priorDiagnostics;
const currentFetch=globalThis.fetch;
globalThis.fetch=(input,init)=>String(input)==='/api/hard-clash-reference'
  ? Promise.resolve(new Response(JSON.stringify({error:'Simulated reference failure'}),{status:500,headers:{'Content-Type':'application/json'}})) : currentFetch(input,init);
document.querySelector('#hardClashReferenceButton').click();
await new Promise(resolve=>setTimeout(resolve,25));
assert.match(document.querySelector('#hardClashReferenceStatus').textContent,/Simulated reference failure.*remains blocked/);
assert.equal(document.querySelector('#hardClashEvidenceButton').disabled,true,'failed rerun cannot export a stale matrix');
assert.equal(document.querySelector('#hardClashReferenceButton').disabled,false,'failed reference test can be retried');
assert.equal(document.querySelector('#hardClashModelButton').disabled,true);
globalThis.fetch=currentFetch;
// Simulate the identified persisted test record without uploading the large
// office IFC. A storage write failure must not discard its archived history.
const officeSha='f99b62ccadd9d625c64c4b68f89eda544ea8cac5986970d0a21473d9fcb3fd76';
const officeReviewKey='duplicate_opening_candidate|66076|108748';
const officeStorageKey=`openbim-qc:duplicate-reviews:v1:sha256:${officeSha}`;
const testReview={review_status:'confirmed_duplicate',review_note:'Synthetic reference case: expected matching geometry and offset verified against the configured tolerance. Decision recorded to test review persistence.',reviewed_at:'2026-10-08T07:42:14Z'};
localStorage.setItem(officeStorageKey,JSON.stringify({[officeReviewKey]:testReview}));
const nativeSetItem=window.Storage.prototype.setItem;
window.Storage.prototype.setItem=function () {throw new Error('Simulated storage quota');};
let migrationFilename='review-migration-storage-failure.ifc';
globalThis.fetch=(input,init)=>String(input)==='/api/models'
  ? Promise.resolve(new Response(JSON.stringify({model_id:'migration-fixture',model_sha256:officeSha,
      analysis:{...nearJson,filename:migrationFilename,issues:[]}}),{status:201,headers:{'Content-Type':'application/json'}})) : currentFetch(input,init);
const uploadMigration=async()=>{
  Object.defineProperty(uploadInput,'files',{configurable:true,value:[new File([nearText],migrationFilename)]});
  uploadInput.dispatchEvent(new window.Event('change'));
  const deadline=Date.now()+10000;
  while(document.querySelector('#modelName').textContent!==migrationFilename && Date.now()<deadline) {
    await new Promise(resolve=>setTimeout(resolve,25));
  }
  assert.equal(document.querySelector('#modelName').textContent,migrationFilename);
};
await uploadMigration();
document.querySelector('#jsonButton').click();
const corrected=JSON.parse(await exportedBlob.text());
assert.equal(corrected.duplicate_review_ledger[officeReviewKey].review_status,'unresolved');
assert.equal(corrected.duplicate_review_ledger[officeReviewKey].review_history.length,1);
assert.equal(corrected.duplicate_review_ledger[officeReviewKey].review_history[0].review_note,testReview.review_note);
assert.equal(JSON.parse(localStorage.getItem(officeStorageKey))[officeReviewKey].review_status,'confirmed_duplicate','failed save retains the original disk record');
window.Storage.prototype.setItem=nativeSetItem;
migrationFilename='review-migration-success.ifc';
await uploadMigration();
const savedCorrection=JSON.parse(localStorage.getItem(officeStorageKey))[officeReviewKey];
assert.equal(savedCorrection.review_status,'unresolved');
assert.equal(savedCorrection.review_history.length,1);
migrationFilename='review-migration-idempotence.ifc';
await uploadMigration();
assert.deepEqual(JSON.parse(localStorage.getItem(officeStorageKey))[officeReviewKey],savedCorrection,'reopening does not add another archive or change timestamps');
globalThis.fetch=currentFetch;
URL.createObjectURL=createObjectURL;
window.HTMLAnchorElement.prototype.click=anchorClick;
serverProcess?.kill();
console.log("frontend interaction tests passed");

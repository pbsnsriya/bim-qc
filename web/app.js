const state = { result: null, selectedEntityId: null, viewerBaseStatus: "", baseIssues: [], idsValidation: null, geometryDiagnostics: null, geometryValidation: null, ifcopenshellAvailable: false };
state.source = null;
const $ = (id) => document.getElementById(id);

const dropzone = $("dropzone");
const fileInput = $("fileInput");

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.remove("hidden");
  setTimeout(() => node.classList.add("hidden"), 2600);
}

function setBusy(busy, message = "Drop an IFC model here") {
  state.busy = busy;
  dropzone.setAttribute("aria-busy", String(busy));
  dropzone.classList.toggle("busy", busy);
  fileInput.disabled = busy;
  $("demoButton").disabled = busy;
  $("uploadStatus").textContent = message;
}

async function readJsonResponse(response, fallback) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error("The analysis API returned a web page instead of data. Restart server.py and open http://127.0.0.1:8000.");
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || fallback);
  return result;
}

function rebuildIssues() {
  if (!state.result) return;
  state.result.issues = [
    ...state.baseIssues,
    ...(state.geometryValidation?.issues || []),
    ...(state.idsValidation?.issues || []),
  ];
  const counts = { error: 0, warning: 0, info: 0 };
  state.result.issues.forEach((issue) => { counts[issue.severity] = (counts[issue.severity] || 0) + 1; });
  Object.assign(state.result.summary, counts, { issues: state.result.issues.length });
}

async function analyzeFile(file) {
  if (!file) throw new Error("No IFC file was received. Please choose the file again.");
  if (!file.name.toLowerCase().endsWith(".ifc")) throw new Error("Please choose an .ifc file.");
  if (file.size > 24 * 1024 * 1024) throw new Error("This version accepts IFC files below 24 MB.");
  setBusy(true, `Reading ${file.name}…`);
  let content;
  try {
    content = await file.text();
  } catch {
    setBusy(false, "The file could not be read");
    throw new Error("The browser could not read that IFC file.");
  }
  return requestAnalysis({ filename: file.name, content });
}

async function requestAnalysis(payload) {
  setBusy(true, `Analysing ${payload.filename || "model.ifc"}…`);
  try {
    state.source = { filename: payload.filename, content: payload.content };
    payload.profile = payload.profile || $("profileSelect").value;
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await readJsonResponse(response, "Analysis failed.");
    state.result = result;
    state.baseIssues = [...result.issues];
    state.idsValidation = null;
    state.geometryDiagnostics = null;
    state.geometryValidation = null;
    $("idsStatus").classList.add("hidden");
    $("geometryDiagnosticsStatus").classList.add("hidden");
    $("geometryStatus").classList.add("hidden");
    $("geometryCheckButton").disabled = true;
    $("geometryCheckButton").title = "Stage 1 geometry validation must pass first";
    clearEntitySelection();
    render();
    await renderGeometry(payload.content);
    setBusy(false, `${result.filename} analysed successfully`);
  } catch (error) {
    setBusy(false, "Upload failed — see the message below");
    throw error;
  }
}

async function loadDemo() {
  const response = await fetch("/api/demo-file");
  if (!response.ok) throw new Error("Demo could not be loaded.");
  const content = await response.text();
  await requestAnalysis({ filename: "geometry_demo.ifc", content });
}

async function validateIds(idsFilename, idsContent) {
  if (!state.source || !state.result) throw new Error("Load an IFC model before validating IDS requirements.");
  const response = await fetch("/api/validate-ids", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: state.source.content,
      filename: state.source.filename,
      ids_filename: idsFilename,
      ids_content: idsContent,
    }),
  });
  const validation = await readJsonResponse(response, "IDS validation failed.");
  state.idsValidation = validation;
  rebuildIssues();
  render();
  const status = $("idsStatus");
  const unsupported = validation.summary.unsupported_facets;
  status.innerHTML = `<strong>${escapeHtml(validation.filename)}</strong> · ${validation.summary.specifications} specification(s), ${validation.summary.failed} failure(s)` +
    (unsupported ? ` · ${unsupported} unsupported facet(s); result is partial` : " · supported subset fully evaluated");
  status.classList.remove("hidden");
  toast(`IDS validation found ${validation.summary.failed} failure(s)`);
}

async function runGeometryChecks() {
  if (!state.source || !state.result) throw new Error("Load an IFC model before running coordination checks.");
  if (!state.geometryDiagnostics?.ready) throw new Error("Validate the Stage 1 geometry foundation first.");
  const button = $("geometryCheckButton");
  button.disabled = true;
  button.textContent = "Checking geometry…";
  try {
    const response = await fetch("/api/geometry-checks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: state.source.content,
        config: {
          hard_clashes: $("hardClashCheck").checked,
          hard_tolerance_mm: Number($("hardToleranceInput").value),
          clearance_clashes: $("clearanceCheck").checked,
          clearance_mm: Number($("clearanceInput").value),
          alignment_tolerance_degrees: Number($("alignmentInput").value),
          minimum_dimension_mm: Number($("dimensionInput").value),
        },
      }),
    });
    const validation = await readJsonResponse(response, "Geometry checks failed.");
    state.geometryValidation = validation;
    rebuildIssues();
    render();
    const rules = Object.entries(validation.by_rule)
      .map(([rule, count]) => `${humanize(rule)}: ${count}`)
      .join(" · ");
    const status = $("geometryStatus");
    status.innerHTML = `<strong>Coordination checks complete</strong> · ${validation.summary.geometric_products} geometric products · ${validation.summary.issues} finding(s)` +
      (rules ? `<br>${escapeHtml(rules)}` : " · No coordination findings") +
      (validation.summary.connectivity_unverifiable ? `<br>${validation.summary.connectivity_unverifiable} MEP element(s) had no IFC ports, so connectivity is partial.` : "");
    status.classList.remove("hidden");
    toast(`Coordination checks found ${validation.summary.issues} issue(s)`);
  } finally {
    button.disabled = false;
    button.textContent = "Run experimental checks";
  }
}

function vectorText(values) {
  return values ? values.map((value) => Number(value).toFixed(2)).join(", ") : "unavailable";
}

async function runGeometryDiagnostics() {
  if (!state.source || !state.result) throw new Error("Load an IFC model before validating its geometry foundation.");
  if (!state.ifcopenshellAvailable) throw new Error("IfcOpenShell is not available on the local server.");
  const button = $("geometryDiagnosticsButton");
  const coordinationButton = $("geometryCheckButton");
  button.disabled = true;
  coordinationButton.disabled = true;
  button.textContent = "Validating foundation…";
  try {
    const response = await fetch("/api/geometry-diagnostics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: state.source.content }),
    });
    const result = await readJsonResponse(response, "Geometry foundation validation failed.");
    state.geometryDiagnostics = result;
    const status = $("geometryDiagnosticsStatus");
    const checkRows = result.checks.map((check) =>
      `<li class="diagnostic-${check.status}"><strong>${check.status === "pass" ? "PASS" : "FAIL"}</strong> ${escapeHtml(check.message)}</li>`
    ).join("");
    const failures = result.failed_elements.length
      ? `<details><summary>${result.failed_elements.length} failed element(s)</summary><ul>${result.failed_elements.map((item) => `<li>#${item.step_id} ${escapeHtml(item.type)} · ${escapeHtml(item.error)}</li>`).join("")}</ul></details>`
      : "";
    const warnings = result.warnings.length
      ? `<p><strong>Review:</strong> ${result.warnings.map(escapeHtml).join(" ")}</p>`
      : "";
    status.classList.toggle("diagnostics-pass", result.ready);
    status.classList.toggle("diagnostics-fail", !result.ready);
    status.innerHTML = `<strong>${result.ready ? "Stage 1 passed" : "Stage 1 needs attention"}</strong> · ${escapeHtml(result.schema)} · ${escapeHtml(result.units.length)} (${result.units.metres_per_project_unit} m/unit) · ${result.duration_ms} ms<br>` +
      `${result.counts.generated_shapes}/${result.counts.represented_products} represented shapes (${result.coverage_percent}%) · ${result.counts.vertices} vertices · ${result.counts.triangles} triangles<br>` +
      `Bounds min [${vectorText(result.bounds_metres.minimum)}] m · max [${vectorText(result.bounds_metres.maximum)}] m` +
      `<ul class="diagnostic-checks">${checkRows}</ul>${warnings}${failures}`;
    status.classList.remove("hidden");
    coordinationButton.disabled = !result.ready;
    coordinationButton.title = result.ready ? "Stage 1 passed; experimental rule prototypes are available" : "Stage 1 must pass first";
    toast(result.ready ? "Stage 1 geometry foundation passed" : "Stage 1 found geometry foundation problems");
  } finally {
    button.disabled = false;
    button.textContent = "Validate geometry foundation";
  }
}

async function loadSampleIds() {
  if (!state.source) throw new Error("Load the demo or another IFC model first.");
  const response = await fetch("/api/demo-ids-file");
  if (!response.ok) throw new Error("Sample IDS could not be loaded.");
  await validateIds("wall-naming.ids", await response.text());
}

async function renderGeometry(content) {
  $("viewerStatus").textContent = "Loading geometry…";
  try {
    // The viewer loads independently so QC remains usable if WebGL is unavailable.
    const loadIfcGeometry = globalThis.OpenBIMViewer?.loadIfcGeometry;
    if (!loadIfcGeometry) throw new Error("Viewer module did not start");
    const count = await loadIfcGeometry(new TextEncoder().encode(content), $("viewer"));
    if (count > 0) {
      $("modelMap").classList.add("hidden");
      setViewerStatus(`${count} mesh groups · Click an issue or model element`);
    } else {
      $("modelMap").classList.remove("hidden");
      renderMap();
      setViewerStatus("No geometry · Showing data map");
    }
  } catch (error) {
    $("modelMap").classList.remove("hidden");
    renderMap();
    const detail = error instanceof Error ? error.message : String(error);
    setViewerStatus(`3D error: ${detail.slice(0, 90)} · Showing data map`);
    $("viewerStatus").title = detail;
    console.warn(error);
  }
}

function render() {
  const { result } = state;
  $("workspace").classList.remove("hidden");
  $("emptyState").classList.add("hidden");
  $("modelName").textContent = result.filename;
  $("schemaBadge").textContent = result.schema;
  const metrics = [
    [result.summary.products, "Products"],
    [result.summary.issues, "Total issues"],
    [result.summary.error, "Errors"],
    [result.summary.warning, "Warnings"],
    [result.summary.info, "Information"],
  ];
  $("metrics").innerHTML = metrics.map(([value, label]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join("");
  renderMap();
  renderTypes();
  configureRuleFilter();
  renderIssues();
  $("workspace").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderMap() {
  const elements = state.result.elements;
  $("modelMap").innerHTML = elements.length
    ? elements.slice(0, 40).map((element) => `<button type="button" class="model-node" data-entity-id="${element.step_id}" title="Select ${escapeHtml(element.name || "unnamed element")}"><strong>${escapeHtml(shortType(element.type))}</strong><small>#${element.step_id} · ${escapeHtml(element.name || "Unnamed")}</small></button>`).join("")
    : `<p class="muted">No supported product elements were identified.</p>`;
}

function renderTypes() {
  const rows = state.result.type_counts;
  const max = Math.max(...rows.map((item) => item.count), 1);
  $("typeChart").innerHTML = rows.map((item) => `<div class="bar-row"><div class="bar-label"><span>${escapeHtml(shortType(item.type))}</span><strong>${item.count}</strong></div><div class="bar-track"><div class="bar" style="width:${(item.count / max) * 100}%"></div></div></div>`).join("");
}

function configureRuleFilter() {
  const rules = [...new Set(state.result.issues.map((issue) => issue.rule_id))].sort();
  $("ruleFilter").innerHTML = `<option value="all">All rules</option>` + rules.map((rule) => `<option value="${rule}">${humanize(rule)}</option>`).join("");
}

function renderIssues() {
  if (!state.result) return;
  const severity = $("severityFilter").value;
  const rule = $("ruleFilter").value;
  const issues = state.result.issues.filter((issue) => (severity === "all" || issue.severity === severity) && (rule === "all" || issue.rule_id === rule));
  $("issueList").innerHTML = issues.length ? issues.map((issue) => {
    const selectable = issue.entity_id != null;
    const tag = selectable ? "button" : "div";
    const attributes = selectable ? `type="button" data-entity-id="${issue.entity_id}" data-rule-id="${escapeHtml(issue.rule_id)}" aria-label="Highlight ${escapeHtml(issue.entity_type || "element")} ${issue.entity_id} in the model"` : `data-rule-id="${escapeHtml(issue.rule_id)}"`;
    return `<${tag} class="issue ${selectable ? "issue-action" : ""}" ${attributes}><span class="severity ${issue.severity}">${issue.severity}</span><div><strong>${escapeHtml(issue.title)}</strong><p>${escapeHtml(issue.message)}</p></div><span class="entity-ref">${escapeHtml(issue.entity_type || "MODEL")} ${issue.entity_id ? `#${issue.entity_id}` : ""}</span></${tag}>`;
  }).join("") : `<div class="issue"><p>No issues match the selected filters.</p></div>`;
  updateSelectionUi();
}

function setViewerStatus(message) {
  state.viewerBaseStatus = message;
  $("viewerStatus").textContent = message;
}

function selectEntity(entityID, { fromViewer = false } = {}) {
  const numericID = Number(entityID);
  if (!Number.isInteger(numericID)) return;
  const highlighted = fromViewer || globalThis.OpenBIMViewer?.selectExpressID(numericID);
  state.selectedEntityId = numericID;
  updateSelectionUi();
  const element = state.result?.elements.find((item) => item.step_id === numericID);
  $("viewerStatus").textContent = `Selected ${shortType(element?.type || "IFC element")} #${numericID}`;
  $("clearSelectionButton").classList.remove("hidden");
  if (!highlighted && !$("modelMap").classList.contains("hidden")) return;
  if (!highlighted) toast(`Element #${numericID} has no renderable geometry.`);
}

function clearEntitySelection() {
  globalThis.OpenBIMViewer?.clearSelection();
  state.selectedEntityId = null;
  updateSelectionUi();
  $("clearSelectionButton")?.classList.add("hidden");
  if ($("viewerStatus") && state.viewerBaseStatus) $("viewerStatus").textContent = state.viewerBaseStatus;
}

function updateSelectionUi() {
  document.querySelectorAll("[data-entity-id]").forEach((node) => {
    node.classList.toggle("selected", Number(node.dataset.entityId) === state.selectedEntityId);
  });
}

function exportCsv() {
  if (!state.result) return;
  const header = ["severity", "rule_id", "title", "entity_id", "entity_type", "global_id", "name", "message"];
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = [header.join(","), ...state.result.issues.map((issue) => header.map((key) => quote(issue[key])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${state.result.filename.replace(/\.ifc$/i, "")}-qc-report.csv`;
  link.click();
  URL.revokeObjectURL(url);
  toast("QC report exported");
}

function exportJson() {
  if (!state.result) return;
  downloadText(
    JSON.stringify(state.result, null, 2),
    `${state.result.filename.replace(/\.ifc$/i, "")}-qc-report.json`,
    "application/json",
  );
  toast("JSON report exported");
}

async function exportBcf() {
  if (!state.result) return;
  const base = state.result.filename.replace(/\.ifc$/i, "");
  const response = await fetch("/api/export-bcf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: `${base}-qc-issues.bcfzip`, issues: state.result.issues }),
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.error || "BCF export failed.");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `${base}-qc-issues.bcfzip`;
  link.click();
  URL.revokeObjectURL(url);
  toast(`${state.result.issues.length} BCF topic(s) exported`);
}

function downloadText(content, filename, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function shortType(value) { return value.replace(/^IFC/, "").replaceAll("_", " "); }
function humanize(value) { return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function escapeHtml(value) { const div = document.createElement("div"); div.textContent = value; return div.innerHTML; }

fileInput.addEventListener("change", async (event) => {
  if (!event.target.files[0]) return;
  try { await analyzeFile(event.target.files[0]); } catch (error) { toast(error.message); }
});
$("demoButton").addEventListener("click", async () => { try { await loadDemo(); } catch (error) { toast(error.message); } });
$("exportButton").addEventListener("click", exportCsv);
$("jsonButton").addEventListener("click", exportJson);
$("bcfButton").addEventListener("click", async () => { try { await exportBcf(); } catch (error) { toast(error.message); } });
$("sampleIdsButton").addEventListener("click", async () => { try { await loadSampleIds(); } catch (error) { toast(error.message); } });
$("geometryDiagnosticsButton").addEventListener("click", async () => { try { await runGeometryDiagnostics(); } catch (error) { toast(error.message); } });
$("geometryCheckButton").addEventListener("click", async () => { try { await runGeometryChecks(); } catch (error) { toast(error.message); } });
$("idsInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    if (!/\.(ids|xml)$/i.test(file.name)) throw new Error("Please choose an .ids or .xml requirements file.");
    await validateIds(file.name, await file.text());
  } catch (error) { toast(error.message); }
  event.target.value = "";
});
$("profileSelect").addEventListener("change", async () => {
  if (!state.source) return;
  try { await requestAnalysis({ ...state.source, profile: $("profileSelect").value }); }
  catch (error) { toast(error.message); }
});
$("severityFilter").addEventListener("change", renderIssues);
$("ruleFilter").addEventListener("change", renderIssues);
$("clearSelectionButton").addEventListener("click", clearEntitySelection);
$("issueList").addEventListener("click", (event) => {
  const issue = event.target.closest("[data-entity-id]");
  if (issue) selectEntity(issue.dataset.entityId);
});
$("modelMap").addEventListener("click", (event) => {
  const element = event.target.closest("[data-entity-id]");
  if (element) selectEntity(element.dataset.entityId);
});
globalThis.addEventListener("ifc-element-selected", (event) => selectEntity(event.detail.expressID, { fromViewer: true }));
dropzone.addEventListener("click", (event) => { if (!event.target.closest("button, label")) fileInput.click(); });
dropzone.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") fileInput.click(); });
["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add("dragging"); }));
["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove("dragging"); }));
dropzone.addEventListener("drop", async (event) => { try { await analyzeFile(event.dataTransfer.files[0]); } catch (error) { toast(error.message); } });

async function checkServer() {
  if (location.protocol === "file:") return;
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error();
    const capabilityResponse = await fetch("/api/capabilities");
    if (capabilityResponse.ok) {
      const engines = await capabilityResponse.json();
      state.ifcopenshellAvailable = engines.ifcopenshell_available;
      $("backendBadge").textContent = engines.ifcopenshell_available ? "IfcOpenShell ready" : "Lightweight + IDS subset";
      $("backendBadge").title = `Semantics: ${engines.semantic_backend}; IDS: ${engines.ids_backend}`;
      $("geometryDiagnosticsButton").disabled = !engines.ifcopenshell_available;
      $("geometryDiagnosticsButton").title = engines.ifcopenshell_available ? "Run Stage 1 diagnostics" : "Install IfcOpenShell to enable geometry diagnostics";
      $("geometryCheckButton").disabled = true;
      $("geometryCheckButton").title = engines.ifcopenshell_available ? "Stage 1 geometry validation must pass first" : "Install IfcOpenShell to enable geometry checks";
    }
    setBusy(false, "Drop an IFC model here");
  } catch {
    setBusy(false, "Server connection failed — restart the application");
    toast("Cannot reach the local analysis server.");
  }
}

checkServer();

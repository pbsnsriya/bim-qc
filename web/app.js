const state = { result: null, selectedEntityId: null, viewerBaseStatus: "", baseIssues: [], idsValidation: null, geometryDiagnostics: null, geometryValidation: null, viewerDiagnostics: null, gpuValidation: null, ifcopenshellAvailable: false, activeGeometryJobId: null };
state.source = null;
const $ = (id) => document.getElementById(id);

const dropzone = $("dropzone");
const fileInput = $("fileInput");
const ISSUE_RENDER_LIMIT = 250;

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
  if (file.size > 100 * 1024 * 1024) throw new Error("This version accepts IFC files up to 100 MB.");
  setBusy(true, `Uploading ${file.name} once…`);
  const form = new FormData();
  form.append("profile", $("profileSelect").value);
  form.append("file", file, file.name);
  try {
    const response = await fetch("/api/models", { method: "POST", body: form });
    const payload = await readJsonResponse(response, "Upload analysis failed.");
    state.source = { filename: file.name, file, modelId: payload.model_id, size: file.size };
    applyAnalysis(payload.analysis);
    await renderGeometry(file);
    if (file.size > 25 * 1024 * 1024) {
      $("geometryDiagnosticsButton").title = "Large-model validation runs as a cancellable one-worker background job";
    }
    setBusy(false, `${payload.analysis.filename} analysed successfully`);
  } catch (error) {
    setBusy(false, "Upload failed — see the message below");
    throw error;
  }
}

function applyAnalysis(result) {
  state.result = result;
  state.baseIssues = [...result.issues];
  state.idsValidation = null;
  state.geometryDiagnostics = null;
  state.geometryValidation = null;
  state.viewerDiagnostics = null;
  state.gpuValidation = null;
  state.activeGeometryJobId = null;
  $("idsStatus").classList.add("hidden");
  $("geometryDiagnosticsStatus").classList.add("hidden");
  $("geometryStatus").classList.add("hidden");
  $("gpuValidationStatus").classList.add("hidden");
  $("geometryCancelButton").classList.add("hidden");
  $("geometryCheckButton").disabled = true;
  $("geometryEvidenceButton").disabled = true;
  $("gpuValidationButton").disabled = true;
  $("geometryCheckButton").title = "Stage 1 geometry validation must pass first";
  clearEntitySelection();
  render();
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
    applyAnalysis(result);
    await renderGeometry(payload.content);
    if (payload.content.length > 25 * 1024 * 1024) {
      $("geometryDiagnosticsButton").title = "Large-model validation uses one geometry worker and may take several minutes";
    }
    setBusy(false, `${result.filename} analysed successfully`);
  } catch (error) {
    setBusy(false, "Upload failed — see the message below");
    throw error;
  }
}

async function loadDemo() {
  const response = await fetch("/api/demo-file");
  if (!response.ok) throw new Error("Demo could not be loaded.");
  const file = await response.blob();
  Object.defineProperty(file, "name", { value: "geometry_demo.ifc" });
  await analyzeFile(file);
}

async function validateIds(idsFilename, idsContent) {
  if (!state.source || !state.result) throw new Error("Load an IFC model before validating IDS requirements.");
  const response = await fetch("/api/validate-ids", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model_id: state.source.modelId,
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
        model_id: state.source.modelId,
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
  if (!state.source.modelId) throw new Error("Re-upload this model to create a background-analysis session.");
  const button = $("geometryDiagnosticsButton");
  const coordinationButton = $("geometryCheckButton");
  const status = $("geometryDiagnosticsStatus");
  button.disabled = true;
  coordinationButton.disabled = true;
  button.textContent = "Validating foundation…";
  status.classList.remove("hidden", "diagnostics-pass", "diagnostics-fail");
  status.innerHTML = "<strong>Starting isolated geometry worker…</strong>";
  try {
    const startResponse = await fetch("/api/geometry-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: state.source.modelId, browser_evidence: state.viewerDiagnostics }),
    });
    const started = await readJsonResponse(startResponse, "Geometry foundation validation could not start.");
    state.activeGeometryJobId = started.job_id;
    $("geometryCancelButton").classList.remove("hidden");
    let job;
    while (state.activeGeometryJobId === started.job_id) {
      const response = await fetch(`/api/geometry-jobs/${started.job_id}`);
      job = await readJsonResponse(response, "Geometry job status could not be read.");
      const count = job.total == null ? "" : ` · ${Number(job.processed || 0).toLocaleString()}/${Number(job.total).toLocaleString()}`;
      const percent = job.percent == null ? "" : ` · ${job.percent}%`;
      status.innerHTML = `<strong>${escapeHtml(job.message || "Geometry validation is running.")}</strong>${count}${percent}<div class="progress-track"><span style="width:${Math.max(0, Math.min(100, Number(job.percent || 0)))}%"></span></div>`;
      if (["completed", "failed", "cancelled", "timed_out"].includes(job.state)) break;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (state.activeGeometryJobId !== started.job_id) return;
    if (!job || job.state === "cancelled") return;
    if (job.state !== "completed" || !job.result) throw new Error(job.error || "Geometry validation did not complete.");
    const acceptanceResponse = await fetch("/api/geometry-acceptance");
    const acceptance = await readJsonResponse(acceptanceResponse, "Known-answer acceptance matrix failed.");
    finishGeometryDiagnostics(job.result, acceptance);
  } finally {
    state.activeGeometryJobId = null;
    $("geometryCancelButton").classList.add("hidden");
    button.disabled = false;
    button.textContent = "Verify extraction evidence";
  }
}

function finishGeometryDiagnostics(result, acceptance) {
  result.acceptance_matrix = acceptance;
  result.ready = result.ready && acceptance.passed;
  state.geometryDiagnostics = result;
  const status = $("geometryDiagnosticsStatus");
  const checkRows = result.checks.map((check) => {
    const label = check.status === "pass" ? "PASS" : check.status === "fail" ? "FAIL" : "NOT RUN";
    return `<li class="diagnostic-${check.status}"><strong>${label}</strong> ${escapeHtml(check.message)}</li>`;
  }).join("");
  const failures = result.failed_elements.length
    ? `<details><summary>${result.failed_elements.length} failed element(s)</summary><ul>${result.failed_elements.map((item) => `<li>#${item.step_id} ${escapeHtml(item.type)} · ${escapeHtml(item.error)}</li>`).join("")}</ul></details>`
    : "";
  const warnings = result.warnings.length ? `<p><strong>Review:</strong> ${result.warnings.map(escapeHtml).join(" ")}</p>` : "";
  status.classList.toggle("diagnostics-pass", result.ready);
  status.classList.toggle("diagnostics-fail", !result.ready);
  const matrixRows = acceptance.cases.map((item) =>
    `<li class="diagnostic-${item.passed ? "pass" : "fail"}"><strong>${item.passed ? "PASS" : "FAIL"}</strong> ${escapeHtml(item.purpose)}</li>`
  ).join("");
  status.innerHTML = `<strong>${result.ready ? "Stage 1 extraction evidence passed" : "Stage 1 extraction evidence needs attention"}</strong> · ${escapeHtml(result.schema)} · ${escapeHtml(result.units.length)} (${result.units.metres_per_project_unit} m/unit) · ${result.duration_ms} ms<br>` +
    `${result.counts.generated_shapes}/${result.counts.represented_products} represented shapes (${result.coverage_percent}%) · ${result.counts.vertices} vertices · ${result.counts.triangles} triangles<br>` +
    `Bounds min [${vectorText(result.bounds_metres.minimum)}] m · max [${vectorText(result.bounds_metres.maximum)}] m` +
    `<ul class="diagnostic-checks">${checkRows}</ul>` +
    `<details open><summary><strong>Known-answer matrix: ${acceptance.passed_cases}/${acceptance.total_cases} cases passed</strong> · tolerance ${acceptance.tolerance_metres * 1000} mm</summary><ul class="diagnostic-checks">${matrixRows}</ul></details>` +
    `<p class="evidence-boundary"><strong>Claim boundary:</strong> ${escapeHtml(result.claim_boundary)}</p>${warnings}${failures}`;
  $("geometryCheckButton").disabled = !result.ready;
  $("geometryEvidenceButton").disabled = false;
  $("geometryCheckButton").title = result.ready ? "Stage 1 extraction evidence passed; experimental rule prototypes are available" : "Stage 1 extraction evidence must pass first";
  toast(result.ready ? "Stage 1 extraction evidence passed" : "Stage 1 found extraction evidence problems");
}

async function cancelGeometryDiagnostics() {
  if (!state.activeGeometryJobId) return;
  const jobId = state.activeGeometryJobId;
  const response = await fetch(`/api/geometry-jobs/${jobId}/cancel`, { method: "POST" });
  await readJsonResponse(response, "Geometry validation could not be cancelled.");
  state.activeGeometryJobId = null;
  $("geometryDiagnosticsStatus").innerHTML = "<strong>Geometry validation was cancelled.</strong> Semantic QC and the 3D viewer remain available.";
  toast("Geometry validation cancelled");
}

async function loadSampleIds() {
  if (!state.source) throw new Error("Load the demo or another IFC model first.");
  const response = await fetch("/api/demo-ids-file");
  if (!response.ok) throw new Error("Sample IDS could not be loaded.");
  await validateIds("wall-naming.ids", await response.text());
}

async function renderGeometry(source) {
  $("viewerStatus").textContent = "Loading geometry…";
  try {
    // The viewer loads independently so QC remains usable if WebGL is unavailable.
    const loadIfcGeometry = globalThis.OpenBIMViewer?.loadIfcGeometry;
    if (!loadIfcGeometry) throw new Error("Viewer module did not start");
    const bytes = source instanceof Uint8Array
      ? source
      : typeof source === "string"
        ? new TextEncoder().encode(source)
        : new Uint8Array(await source.arrayBuffer());
    const count = await loadIfcGeometry(bytes, $("viewer"));
    state.viewerDiagnostics = globalThis.OpenBIMViewer?.getGeometryDiagnostics?.() || null;
    if (count > 0) {
      $("modelMap").classList.add("hidden");
      setViewerStatus(`${count} mesh groups · Click an issue or model element`);
      $("gpuValidationButton").disabled = false;
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

async function runBrowserGpuValidation() {
  const runGpuValidation = globalThis.OpenBIMViewer?.runGpuValidation;
  if (!runGpuValidation) throw new Error("The browser/GPU evidence probe is unavailable. Refresh the application.");
  const button = $("gpuValidationButton");
  const status = $("gpuValidationStatus");
  button.disabled = true;
  button.textContent = "Testing browser/GPU…";
  status.classList.remove("hidden", "diagnostics-pass", "diagnostics-fail");
  status.innerHTML = "<strong>Rendering a two-second frame probe…</strong> Keep this tab visible.";
  try {
    const result = await runGpuValidation(2000);
    state.gpuValidation = result;
    status.classList.toggle("diagnostics-pass", result.rendering_capability_passed && result.interactive_performance_passed);
    status.classList.toggle("diagnostics-fail", !result.rendering_capability_passed || !result.interactive_performance_passed);
    const checks = result.checks.map((check) =>
      `<li class="diagnostic-${check.passed ? "pass" : "fail"}"><strong>${check.passed ? "PASS" : "FAIL"}</strong> ${escapeHtml(check.message)}</li>`
    ).join("");
    const verdict = !result.rendering_capability_passed
      ? "Browser rendering capability failed"
      : result.interactive_performance_passed
        ? "Browser rendering and interactive performance passed"
        : "Browser rendering passed · performance needs attention";
    status.innerHTML = `<strong>${verdict}</strong> · ${escapeHtml(result.renderer.webgl_version)} · ${escapeHtml(result.renderer.renderer || "renderer hidden by browser")}<br>` +
      `${result.probe_frames} frames in ${result.probe_duration_ms} ms · ${result.average_fps} average FPS · ${Number(result.geometry.mesh_groups || 0).toLocaleString()} mesh groups · ${Number(result.geometry.triangles || 0).toLocaleString()} loaded triangles` +
      `<ul class="diagnostic-checks">${checks}</ul><p class="evidence-boundary"><strong>Claim boundary:</strong> ${escapeHtml(result.claim_boundary)}</p>`;
    toast(verdict);
  } finally {
    button.disabled = false;
    button.textContent = "Run browser/GPU check";
  }
}

function exportGeometryEvidence() {
  if (!state.geometryDiagnostics || !state.source) return;
  const report = {
    report_type: "OpenBIM QC Stage 1 extraction evidence",
    generated_at: new Date().toISOString(),
    model_filename: state.source.filename,
    conclusion: state.geometryDiagnostics.ready ? "pass" : "needs_attention",
    browser_gpu_validation: state.gpuValidation,
    ...state.geometryDiagnostics,
  };
  downloadText(
    JSON.stringify(report, null, 2),
    `${state.source.filename.replace(/\.ifc$/i, "")}-stage1-evidence.json`,
    "application/json",
  );
  toast("Stage 1 evidence report exported");
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
    ? elements.slice(0, 40).map((element) => {
      const selectionIds = element.selection_ids || [];
      const disabled = selectionIds.length ? "" : "aria-disabled=\"true\"";
      return `<button type="button" class="model-node" data-entity-id="${element.step_id}" data-selection-ids="${selectionIds.join(",")}" ${disabled} title="${escapeHtml(element.geometry_message || `Select ${element.name || "unnamed element"}`)}"><strong>${escapeHtml(shortType(element.type))}</strong><small>#${element.step_id} · ${escapeHtml(element.name || "Unnamed")}</small></button>`;
    }).join("")
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
  const visibleIssues = issues.slice(0, ISSUE_RENDER_LIMIT);
  $("issueList").innerHTML = issues.length ? visibleIssues.map((issue) => {
    const element = state.result.elements.find((item) => item.step_id === issue.entity_id);
    const selectionIds = issue.selection_ids || element?.selection_ids || [];
    const selectable = issue.entity_id != null && selectionIds.length > 0;
    const tag = selectable ? "button" : "div";
    const attributes = selectable ? `type="button" data-entity-id="${issue.entity_id}" data-selection-ids="${selectionIds.join(",")}" data-rule-id="${escapeHtml(issue.rule_id)}" aria-label="Highlight ${escapeHtml(issue.entity_type || "element")} ${issue.entity_id} in the model"` : `data-rule-id="${escapeHtml(issue.rule_id)}" title="${escapeHtml(issue.geometry_message || "This issue has no 3D selection target")}"`;
    return `<${tag} class="issue ${selectable ? "issue-action" : ""}" ${attributes}><span class="severity ${issue.severity}">${issue.severity}</span><div><strong>${escapeHtml(issue.title)}</strong><p>${escapeHtml(issue.message)}</p></div><span class="entity-ref">${escapeHtml(issue.entity_type || "MODEL")} ${issue.entity_id ? `#${issue.entity_id}` : ""}</span></${tag}>`;
  }).join("") + (issues.length > visibleIssues.length
    ? `<div class="issue-limit-note">Showing the first ${visibleIssues.length.toLocaleString()} of ${issues.length.toLocaleString()} matching issues. JSON and CSV exports still contain every issue; use the filters to narrow the review.</div>`
    : "") : `<div class="issue"><p>No issues match the selected filters.</p></div>`;
  updateSelectionUi();
}

function setViewerStatus(message) {
  state.viewerBaseStatus = message;
  $("viewerStatus").textContent = message;
}

function geometryFailureMessage(element, targetIDs) {
  if (!targetIDs.length) return element?.geometry_message || "This IFC record has no 3D selection target.";
  const backendExtents = state.geometryDiagnostics?.element_extents_metres || {};
  const browserIDs = new Set(state.viewerDiagnostics?.element_ids || []);
  const backendHas = targetIDs.some((id) => backendExtents[String(id)]);
  const browserHas = targetIDs.some((id) => browserIDs.has(id));
  if (backendHas && !browserHas) return "IfcOpenShell extracted this geometry, but web-ifc did not render a selectable mesh.";
  if (backendHas && browserHas) return "Both engines found geometry, but the viewer ID-to-mesh mapping failed.";
  const failure = state.geometryDiagnostics?.failed_elements?.find((item) => targetIDs.includes(item.step_id));
  if (failure) return `The IFC has a representation, but geometry extraction failed: ${failure.error}`;
  return element?.geometry_message || "The geometry is not currently selectable in the viewer.";
}

function selectEntity(entityID, { fromViewer = false, selectionIDs = null } = {}) {
  const numericID = Number(entityID);
  if (!Number.isInteger(numericID)) return;
  const element = state.result?.elements.find((item) => item.step_id === numericID);
  const targetIDs = selectionIDs?.length ? selectionIDs.map(Number) : (element?.selection_ids || [numericID]);
  if (!fromViewer) globalThis.OpenBIMViewer?.setSelectionMode?.($("selectionModeSelect").value);
  const highlighted = fromViewer || (
    globalThis.OpenBIMViewer?.selectExpressIDs?.(targetIDs)
    ?? (targetIDs.length === 1 && globalThis.OpenBIMViewer?.selectExpressID(targetIDs[0]))
  );
  state.selectedEntityId = numericID;
  updateSelectionUi();
  const viaChildren = element?.geometry_status === "children" ? ` via ${targetIDs.length} geometric child element(s)` : "";
  $("viewerStatus").textContent = `Selected ${shortType(element?.type || "IFC element")} #${numericID}${viaChildren}`;
  $("clearSelectionButton").classList.toggle("hidden", !highlighted);
  $("selectionModeSelect").classList.toggle("hidden", !highlighted);
  if (!highlighted) toast(geometryFailureMessage(element, targetIDs));
}

function clearEntitySelection() {
  globalThis.OpenBIMViewer?.clearSelection();
  state.selectedEntityId = null;
  updateSelectionUi();
  $("clearSelectionButton")?.classList.add("hidden");
  $("selectionModeSelect")?.classList.add("hidden");
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
  if (state.result.issues.length > 5000) {
    throw new Error("BCF export is limited to 5,000 topics. Use JSON/CSV for the full result or narrow the QC profile first.");
  }
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
$("gpuValidationButton").addEventListener("click", async () => { try { await runBrowserGpuValidation(); } catch (error) { toast(error.message); } });
$("geometryCancelButton").addEventListener("click", async () => { try { await cancelGeometryDiagnostics(); } catch (error) { toast(error.message); } });
$("geometryEvidenceButton").addEventListener("click", exportGeometryEvidence);
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
  try {
    if (!state.source.modelId) {
      await requestAnalysis({ ...state.source, profile: $("profileSelect").value });
      return;
    }
    setBusy(true, `Applying ${$("profileSelect").value.replaceAll("_", " ")} profile…`);
    const response = await fetch(`/api/models/${state.source.modelId}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: $("profileSelect").value }),
    });
    applyAnalysis(await readJsonResponse(response, "Profile analysis failed."));
    state.viewerDiagnostics = globalThis.OpenBIMViewer?.getGeometryDiagnostics?.() || null;
    $("gpuValidationButton").disabled = !state.viewerDiagnostics?.mesh_groups;
    setBusy(false, `${state.source.filename} analysed successfully`);
  } catch (error) {
    setBusy(false, "Profile analysis failed");
    toast(error.message);
  }
});
$("severityFilter").addEventListener("change", renderIssues);
$("ruleFilter").addEventListener("change", renderIssues);
$("clearSelectionButton").addEventListener("click", clearEntitySelection);
$("selectionModeSelect").addEventListener("change", (event) => {
  if (globalThis.OpenBIMViewer?.setSelectionMode?.(event.target.value)) {
    toast(`${event.target.options[event.target.selectedIndex].text} mode applied`);
  }
});
$("issueList").addEventListener("click", (event) => {
  const issue = event.target.closest("[data-entity-id]");
  if (issue) selectEntity(issue.dataset.entityId, { selectionIDs: issue.dataset.selectionIds.split(",").filter(Boolean).map(Number) });
});
$("modelMap").addEventListener("click", (event) => {
  const element = event.target.closest("[data-entity-id]");
  if (element) selectEntity(element.dataset.entityId, { selectionIDs: element.dataset.selectionIds.split(",").filter(Boolean).map(Number) });
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

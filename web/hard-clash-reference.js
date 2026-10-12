function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = String(value);
  return node.innerHTML;
}

export function renderHardClashReference(report) {
  const rows = report.cases.map(item => `<tr class="${item.passed ? "" : "comparison-warning"}"><th scope="row">${escapeHtml(item.name)}<br><small>${escapeHtml(item.unit)}</small></th><td>${item.expected_candidate ? "Candidate" : "No candidate"}</td><td>${item.measured_candidate ? "Candidate" : "No candidate"}${item.kernel_distance_mm == null ? "" : `<br>${Number(item.kernel_distance_mm).toFixed(3)} mm kernel distance`}</td><td>${escapeHtml(item.result)}</td><td>${escapeHtml(item.reference_basis)}</td></tr>`).join("");
  return `<strong>${report.passed ? "REFERENCE PASS" : "FAIL"} · ${report.passed_cases}/${report.total_cases} reference cases passed</strong><p>IfcOpenShell ${escapeHtml(report.engine_version)} · 2 mm application screening threshold · Model clash checking remains blocked in this release.</p><p>Expected answers come from specified box coordinates and an explicit opening. Missing an expected clash is an engine/probe failure, not a model defect. These cases do not evaluate your uploaded model.</p><div class="pair-table-scroll"><table class="pair-table"><caption>Stage 3 factual matrix: expected versus measured</caption><thead><tr><th scope="col">Known case / IFC units</th><th scope="col">Expected</th><th scope="col">Measured</th><th scope="col">Result</th><th scope="col">Reference basis</th></tr></thead><tbody>${rows}</tbody></table></div><p>${escapeHtml(report.claim_boundary)}</p>`;
}

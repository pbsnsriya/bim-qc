const escape = (value) => String(value).replace(/[&<>"']/g, char => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));

function valueText(value) {
  if (value == null) return "Not supplied";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(10)));
  if (Array.isArray(value)) return value.map(valueText).join(" / ");
  if (typeof value === "object" && "step_id" in value) return `#${value.step_id} · ${value.class} · ${value.name || "Unnamed"}${value.type_name ? ` · Type: ${value.type_name}` : ""}`;
  if (typeof value === "object" && "name" in value && "global_id" in value) return `${value.name || "Unnamed"} · ${value.global_id}`;
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function table(rows, a, b) {
  const statusLabels = {same: "Same", different: "Different", missing: "Missing value", not_evaluated: "Not evaluated", not_applicable: "Not applicable"};
  return `<div class="pair-table-scroll"><table class="pair-table"><caption class="sr-only">Comparison of #${a.step_id} and #${b.step_id}</caption><thead><tr><th scope="col">Field</th><th scope="col">#${a.step_id}</th><th scope="col">#${b.step_id}</th><th scope="col">Result</th></tr></thead><tbody>${rows.map(row => {
    const identityDiff = row.category === "identity" && row.status === "different";
    const contextDiff = row.category === "context" && row.status === "different";
    const status = identityDiff ? "Identity differs" : contextDiff ? "Different hosts" : statusLabels[row.status] || "Not evaluated";
    const side = (value, applicable) => applicable === false ? "Not applicable" : valueText(value);
    return `<tr class="comparison-${escape(identityDiff ? "identity-different" : contextDiff ? "context-different" : row.status)}" data-field="${escape(row.key)}"><th scope="row">${escape(row.label)}</th><td>${escape(side(row.a, row.a_applicable))}</td><td>${escape(side(row.b, row.b_applicable))}</td><td>${escape(status)}</td></tr>`;
  }).join("")}</tbody></table></div>`;
}

export function renderPairComparison(result) {
  const [a, b] = result.elements;
  const openings = result.elements.filter(e => e.is_opening);
  const missingHosts = openings.filter(e => !e.opening_hosts?.length);
  const hostControls = openings.length ? `<div class="pair-host-controls"><button type="button" class="comparison-highlight-hosts"${result.host_entity_ids?.length ? "" : " disabled"}>Highlight hosts</button><p class="muted">Hosts come from explicit IFC void relationships. Different hosts may explain intentional coincident openings; they do not prove intent.</p></div>` +
    missingHosts.map(e => `<p class="comparison-warning">#${e.step_id}: Host relationship not supplied. Host comparison is not evaluated.</p>`).join("") +
    `<p class="muted">Absent type, material and load-bearing fields are marked Not applicable for opening voids. Exported values, when present, remain visible. Missing phase/status and assembly information remain Not evaluated.</p>` : "";
  return `<p class="pair-summary"><strong>${result.physical_difference_count} physical field difference(s)</strong> · ${result.property_difference_count} property value difference(s) · ${result.not_evaluated_count} physical field(s) missing or not evaluated${result.not_applicable_count ? ` · ${result.not_applicable_count} not applicable` : ""}.</p>` +
    `<div class="pair-names"><span>#${a.step_id} · ${escape(a.name || "Unnamed")}</span><span>#${b.step_id} · ${escape(b.name || "Unnamed")}</span></div>` +
    table(result.rows, a, b) + hostControls +
    `<details class="pair-properties"><summary>Source properties and quantities (${result.property_rows_total})</summary><p class="muted">Source IFC values; length unit scale to metres: ${escape(result.length_unit_scale_to_metres)}. Quantity/property units follow the IFC definitions. Property-set record IDs are excluded.</p>` +
    table(result.property_rows, a, b) + (result.property_rows_truncated ? `<p>Showing the first 500 property fields.</p>` : "") + `</details>` +
    `<p class="pair-measurement"><strong>Measurement:</strong> Bounds along each occurrence's axes are measured dimensions, not nominal sizes. Position is the world bounds centre in IFC Z-up coordinates.</p>` +
    result.elements.filter(e => e.geometry_status !== "measured").map(e => `<p class="comparison-warning">#${e.step_id}: ${escape(e.geometry_message)}</p>`).join("") +
    `<p class="claim-boundary">${escape(result.claim_boundary)}</p>`;
}

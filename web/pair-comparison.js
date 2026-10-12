const escape = (value) => String(value).replace(/[&<>"']/g, char => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));

function valueText(value) {
  if (value == null) return "Not supplied";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(10)));
  if (Array.isArray(value)) return value.map(valueText).join(" / ");
  if (typeof value === "object" && "name" in value && "global_id" in value) return `${value.name || "Unnamed"} · ${value.global_id}`;
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function table(rows, a, b) {
  const statusLabels = {same: "Same", different: "Different", missing: "Missing value", not_evaluated: "Not evaluated"};
  return `<div class="pair-table-scroll"><table class="pair-table"><caption class="sr-only">Comparison of #${a.step_id} and #${b.step_id}</caption><thead><tr><th scope="col">Field</th><th scope="col">#${a.step_id}</th><th scope="col">#${b.step_id}</th><th scope="col">Result</th></tr></thead><tbody>${rows.map(row => {
    const identityDiff = row.category === "identity" && row.status === "different";
    const status = identityDiff ? "Identity differs" : statusLabels[row.status] || "Not evaluated";
    return `<tr class="comparison-${escape(identityDiff ? "identity-different" : row.status)}" data-field="${escape(row.key)}"><th scope="row">${escape(row.label)}</th><td>${escape(valueText(row.a))}</td><td>${escape(valueText(row.b))}</td><td>${escape(status)}</td></tr>`;
  }).join("")}</tbody></table></div>`;
}

export function renderPairComparison(result) {
  const [a, b] = result.elements;
  return `<p class="pair-summary"><strong>${result.physical_difference_count} physical field difference(s)</strong> · ${result.property_difference_count} property value difference(s) · ${result.not_evaluated_count} physical field(s) missing or not evaluated.</p>` +
    `<div class="pair-names"><span>#${a.step_id} · ${escape(a.name || "Unnamed")}</span><span>#${b.step_id} · ${escape(b.name || "Unnamed")}</span></div>` +
    table(result.rows, a, b) +
    `<details class="pair-properties"><summary>Source properties and quantities (${result.property_rows_total})</summary><p class="muted">Source IFC values; length unit scale to metres: ${escape(result.length_unit_scale_to_metres)}. Quantity/property units follow the IFC definitions. Property-set record IDs are excluded.</p>` +
    table(result.property_rows, a, b) + (result.property_rows_truncated ? `<p>Showing the first 500 property fields.</p>` : "") + `</details>` +
    `<p class="pair-measurement"><strong>Measurement:</strong> Bounds along each occurrence's axes are measured dimensions, not nominal sizes. Position is the world bounds centre in IFC Z-up coordinates.</p>` +
    result.elements.filter(e => e.geometry_status !== "measured").map(e => `<p class="comparison-warning">#${e.step_id}: ${escape(e.geometry_message)}</p>`).join("") +
    `<p class="claim-boundary">${escape(result.claim_boundary)}</p>`;
}

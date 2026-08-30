// External file rather than inline, so the page needs no 'unsafe-inline' in CSP.
//
// The pasted message is deliberately NOT persisted anywhere. An earlier version
// wrote it to the Cache Storage API, which is on-disk and survives restarts --
// on a shared workstation that exposed one user's message to the next.

const $ = (id) => document.getElementById(id);

const input = $("hl7-message");
const fieldsBox = $("out-fields");
const jsonPre = $("out-json");
const errorBox = $("error");
const statusEl = $("status");
const submitBtn = $("convert");
const sampleSelect = $("sample");
const diagnosticsBox = $("diagnostics");
const metaBox = $("meta");

// Last successful payloads, so switching JSON shape needs no refetch.
let lastCanonical = null;
let lastSimple = null;
let jsonShape = "canonical";

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  // textContent everywhere: every string below derives from user input.
  if (text !== undefined) node.textContent = text;
  return node;
};

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}

function resetOutput() {
  fieldsBox.innerHTML = "";
  jsonPre.textContent = "";
  diagnosticsBox.innerHTML = "";
  metaBox.innerHTML = "";
  lastCanonical = null;
  lastSimple = null;
}

function renderMeta(meta) {
  metaBox.innerHTML = "";
  if (!meta) return;
  for (const [label, value] of [
    ["Version", meta.version],
    ["Type", meta.messageType],
    ["Control ID", meta.controlId],
    ["Segments", String(meta.segmentCount)],
    ["Framing", meta.framing],
  ]) {
    if (!value) continue;
    const chip = el("span", "chip", label + " ");
    chip.appendChild(el("strong", null, value));
    metaBox.appendChild(chip);
  }
}

function renderDiagnostics(diagnostics) {
  diagnosticsBox.innerHTML = "";
  if (!diagnostics || diagnostics.length === 0) return;
  const counts = { error: 0, warning: 0, info: 0 };
  for (const d of diagnostics) counts[d.severity] = (counts[d.severity] || 0) + 1;
  const parts = [];
  if (counts.error) parts.push(`${counts.error} error${counts.error === 1 ? "" : "s"}`);
  if (counts.warning) parts.push(`${counts.warning} warning${counts.warning === 1 ? "" : "s"}`);
  if (counts.info) parts.push(`${counts.info} note${counts.info === 1 ? "" : "s"}`);
  diagnosticsBox.appendChild(el("h2", null, `Validation: ${parts.join(", ")}`));
  for (const d of diagnostics) {
    const row = el("div", `diag ${d.severity}`);
    row.append(el("code", null, d.path ? `${d.code} ${d.path}` : d.code),
               el("span", null, d.message));
    diagnosticsBox.appendChild(row);
  }
}

// --- Field inspector -------------------------------------------------------

function valueCell(sub) {
  const cell = el("td", "val");
  if (sub.presence === "null") {
    cell.appendChild(el("span", "null-val", '"" (explicit null)'));
    return cell;
  }
  if (sub.presence === "empty" || sub.value === "") {
    cell.appendChild(el("span", "empty-val", "(empty)"));
    return cell;
  }
  cell.appendChild(document.createTextNode(sub.value));
  if (sub.meaning) {
    cell.append(" ", el("span", "meaning", sub.meaning));
  }
  return cell;
}

function fieldRows(field) {
  const rows = [];
  for (const rep of field.reps) {
    const components = rep.components;
    const multiRep = field.reps.length > 1;
    const label = multiRep ? `${field.path}[${rep.index}]` : field.path;

    // A single unnamed component with one subcomponent is just a scalar value.
    const scalar = components.length === 1 && components[0].subs.length === 1;

    const head = el("tr");
    head.appendChild(el("td", "path", label));
    const nameCell = el("td", "fname", field.name || "");
    if (field.required) nameCell.appendChild(el("span", "req", " *"));
    if (field.name) nameCell.title = `${field.dataType || ""} ${field.optionality || ""}` +
      (field.length ? ` len ${field.length}` : "");
    head.appendChild(nameCell);
    head.appendChild(scalar ? valueCell(components[0].subs[0]) : el("td", "val", ""));
    rows.push(head);

    if (scalar) continue;

    for (const component of components) {
      for (const sub of component.subs) {
        // Skip the noise of empty components; the JSON pane has everything.
        if (sub.presence !== "present" || sub.value === "") continue;
        const row = el("tr", "comp");
        const suffix = component.subs.length > 1 ? `.${component.index}.${sub.index}` : `.${component.index}`;
        row.appendChild(el("td", "path", label + suffix));
        row.appendChild(el("td", "fname", component.name || ""));
        row.appendChild(valueCell(sub));
        rows.push(row);
      }
    }
  }
  return rows;
}

function renderFields(annotations) {
  fieldsBox.innerHTML = "";

  if (!annotations || !annotations.available) {
    const note = el("div", "banner", annotations?.reason ||
      "Field definitions are unavailable.");
    note.style.margin = "12px";
    fieldsBox.appendChild(note);
    return;
  }

  for (const segment of annotations.segments) {
    const section = el("div", "seg");
    const head = el("div", "seg-head");
    head.appendChild(el("span", "seg-id", segment.id));
    head.appendChild(el("span", "seg-name", segment.name || ""));
    if (!segment.known) head.appendChild(el("span", "badge-unknown", "not in spec"));
    if (segment.occurrence > 0) {
      head.appendChild(el("span", "seg-occ", `occurrence ${segment.occurrence + 1}`));
    }
    section.appendChild(head);

    const table = el("table", "fields");
    const body = el("tbody");
    for (const field of segment.fields) {
      // Hide fields that carry nothing at all.
      const anyValue = field.reps.some((rep) =>
        rep.components.some((c) => c.subs.some((s) => s.presence === "present" && s.value !== "")));
      const isNull = field.reps.some((rep) =>
        rep.components.some((c) => c.subs.some((s) => s.presence === "null")));
      if (!anyValue && !isNull) continue;
      for (const row of fieldRows(field)) body.appendChild(row);
    }
    table.appendChild(body);
    section.appendChild(table);
    fieldsBox.appendChild(section);
  }
}

function renderJson() {
  const payload = jsonShape === "simple" ? lastSimple : lastCanonical;
  jsonPre.textContent = payload ? JSON.stringify(payload, null, 2) : "";
}

for (const [id, shape] of [["tab-canonical", "canonical"], ["tab-simple", "simple"]]) {
  $(id).addEventListener("click", () => {
    jsonShape = shape;
    $("tab-canonical").setAttribute("aria-selected", String(shape === "canonical"));
    $("tab-simple").setAttribute("aria-selected", String(shape === "simple"));
    renderJson();
  });
}

// --- Samples ---------------------------------------------------------------

function sampleLoadFailed(reason) {
  // Silently leaving the dropdown empty gives the user nothing to act on.
  // The tool still works without samples, so this is a note, not an error.
  const placeholder = sampleSelect.options[0];
  if (placeholder) placeholder.textContent = "Samples unavailable";
  sampleSelect.disabled = true;
  const hint = sampleSelect.parentElement.querySelector(".hint");
  if (hint) hint.textContent = reason;
}

async function loadSamples() {
  try {
    const response = await fetch("/api/v2/samples");
    if (!response.ok) {
      sampleLoadFailed(`Could not load samples (HTTP ${response.status}). ` +
        "Paste a message instead.");
      return;
    }
    const body = await response.json();
    const samples = body.samples || [];
    if (samples.length === 0) {
      sampleLoadFailed(body.problem ||
        "The server returned no samples. Paste a message instead.");
      return;
    }
    for (const s of samples) {
      const option = el("option", null, s.title);
      option.value = s.id;
      option.title = s.description;
      sampleSelect.appendChild(option);
    }
  } catch (error) {
    sampleLoadFailed(`Could not reach the server for samples (${error.message}). ` +
      "Paste a message instead.");
  }
}

sampleSelect.addEventListener("change", async () => {
  const id = sampleSelect.value;
  if (!id) return;
  try {
    const response = await fetch(`/api/v2/samples/${encodeURIComponent(id)}`);
    if (!response.ok) return;
    const sample = await response.json();
    input.value = sample.message;
    clearError();
    resetOutput();
    statusEl.textContent = sample.description || "";
  } catch (error) {
    showError(`Could not load the sample: ${error.message}`);
  }
});

$("clear").addEventListener("click", () => {
  input.value = "";
  sampleSelect.value = "";
  statusEl.textContent = "";
  clearError();
  resetOutput();
  input.focus();
});

for (const button of document.querySelectorAll(".copy")) {
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($(button.dataset.target).textContent);
      const original = button.textContent;
      button.textContent = "Copied";
      setTimeout(() => { button.textContent = original; }, 1200);
    } catch {
      showError("Copying needs clipboard permission, or a secure (HTTPS) context.");
    }
  });
}

// --- Parse -----------------------------------------------------------------

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  const typed = input.value;
  if (!typed.trim()) {
    showError("Paste an HL7 message first, or pick a sample.");
    return;
  }

  // A <textarea> normalises every line ending to LF per the HTML spec, so by
  // the time we read .value the original terminators are gone -- a CR-delimited
  // paste is indistinguishable from an LF-delimited one. Sending LF would make
  // the server warn "segments were separated by LF" on every single parse,
  // which says nothing about the user's actual file. Normalise to CR here; the
  // warning stays meaningful for API callers, where the bytes are real.
  const message = typed.replace(/\r\n|\n/g, "\r");
  const body = JSON.stringify({ message });
  const post = (url) =>
    fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body });

  submitBtn.disabled = true;
  statusEl.textContent = "Parsing...";

  try {
    const [annotatedRes, simpleRes] = await Promise.all([
      post("/api/v2/parse?annotate=true&validate=true"),
      post("/api/v2/parse?shape=simple"),
    ]);

    const payload = await annotatedRes.json().catch(() => null);

    if (!annotatedRes.ok) {
      // Surface the real problem rather than rendering the string "undefined".
      let detail = payload && (payload.detail || payload.error);
      if (Array.isArray(detail)) {
        detail = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      }
      showError(`Could not parse the message (HTTP ${annotatedRes.status}): ${detail || "unknown error"}`);
      resetOutput();
      statusEl.textContent = "";
      return;
    }

    lastCanonical = payload;
    lastSimple = simpleRes.ok ? await simpleRes.json() : null;

    renderMeta(payload.meta);
    renderDiagnostics(payload.diagnostics);
    renderFields(payload.annotations);
    renderJson();

    const diagnostics = payload.diagnostics || [];
    const errors = diagnostics.filter((d) => d.severity === "error").length;
    const warnings = diagnostics.filter((d) => d.severity === "warning").length;
    if (errors) {
      statusEl.textContent = `${errors} error${errors === 1 ? "" : "s"}` +
        (warnings ? `, ${warnings} warning${warnings === 1 ? "" : "s"}.` : ".");
    } else if (warnings) {
      statusEl.textContent = `Valid, with ${warnings} warning${warnings === 1 ? "" : "s"}.`;
    } else {
      statusEl.textContent = diagnostics.length
        ? `Valid. ${diagnostics.length} note${diagnostics.length === 1 ? "" : "s"}.`
        : "Valid, no findings.";
    }
  } catch (error) {
    showError(`Could not reach the server: ${error.message}`);
    statusEl.textContent = "";
  } finally {
    submitBtn.disabled = false;
  }
});

loadSamples();

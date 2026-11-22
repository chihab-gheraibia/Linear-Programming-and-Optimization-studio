const state = {
  examples: [],
  currentExample: null,
  varSigns: null,
  proposed: null,
  model: null,
  result: null,
  dual: null,
  sensitivity: null,
  compare: null,
  mode: "text",
  theme: "light",
  parseToken: 0,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function pretty(value) {
  const text = String(value);
  return text.replace(/(\d+)$/, "<sub>$1</sub>");
}

async function api(path, body) {
  const options = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch (error) {
    throw new Error("The server returned an unreadable answer.");
  }
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `Request failed (${response.status}).`);
  }
  return data;
}

function toast(message, kind = "") {
  const node = document.createElement("div");
  node.className = `toast ${kind}`.trim();
  node.textContent = message;
  $("#toasts").appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

function setTheme(theme) {
  state.theme = theme;
  document.documentElement.dataset.theme = theme;
  const toggle = $("#theme-toggle");
  toggle.setAttribute("aria-pressed", String(theme === "dark"));
  toggle.textContent = theme === "dark" ? "☀" : "◐";
  localStorage.setItem("lp-theme", theme);
}

function initTheme() {
  const saved = localStorage.getItem("lp-theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  setTheme(saved || (prefersDark ? "dark" : "light"));
}

function pulseStep(number) {
  const step = $(`.step[data-step="${number}"]`);
  step.classList.remove("is-pulsing");
  void step.offsetWidth;
  step.classList.add("is-pulsing");
}

function goToStep(number) {
  $$(".step").forEach((button) => {
    const active = Number(button.dataset.step) === number;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
  });
  $$(".step-panel").forEach((panel) => panel.classList.toggle("is-active", Number(panel.dataset.panel) === number));
  localStorage.setItem("lp-step", String(number));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function selectResultTab(name) {
  $$(".result-tab").forEach((button) => {
    const active = button.dataset.tab === name;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $$(".result-panel").forEach((panel) => panel.classList.toggle("is-active", panel.id === `panel-${name}`));
}

function updateLineNumbers() {
  const count = $("#lp-text").value.split("\n").length;
  $("#line-numbers").textContent = Array.from({ length: count }, (_, index) => index + 1).join("\n");
}

function showParseError(message) {
  const box = $("#parse-error");
  const textarea = $("#lp-text");
  box.textContent = message;
  box.hidden = false;
  textarea.setAttribute("aria-invalid", "true");
  $("#parse-status").textContent = "Needs a fix";
  $("#parse-status").className = "pill bad";
  const match = message.match(/Line (\d+)/i);
  $$("#line-numbers > *").forEach((node) => node.classList.remove("error-line"));
  $("#line-numbers").textContent = Array.from(
    { length: $("#lp-text").value.split("\n").length },
    (_, index) => index + 1,
  ).join("\n");
  if (match) {
    const target = Number(match[1]);
    const lines = $("#line-numbers").textContent.split("\n");
    lines[target - 1] = `<span class="error-line">${target}</span>`;
    $("#line-numbers").innerHTML = lines.join("\n");
  }
}

function clearParseError() {
  $("#parse-error").hidden = true;
  $("#lp-text").removeAttribute("aria-invalid");
}

function renderUnderstood() {
  const model = state.model;
  if (!model) return;
  const objective = `${model.sense === "max" ? "Maximise" : "Minimise"} z = ` +
    model.c.map((coefficient, index) => `${coefficient}${escapeHtml(model.var_names[index])}`).join(" + ");
  const rows = model.constraints.map((row) => `<div class="lp-line">${escapeHtml(row.text)}</div>`).join("");
  $("#understood").innerHTML = `
    <div class="lp-line"><strong>${escapeHtml(objective)}</strong></div>
    ${rows}
    <div class="lp-line muted">${model.var_names.map((name) => pretty(name)).join(", ")} ≥ 0</div>
  `;
  $("#parse-status").textContent = `${model.var_names.length} variable${model.var_names.length === 1 ? "" : "s"} · ${model.constraints.length} constraint${model.constraints.length === 1 ? "" : "s"}`;
  $("#parse-status").className = "pill";
  clearParseError();
}

async function parseModel(showErrors = false) {
  const text = $("#lp-text").value.trim();
  if (!text) {
    state.model = null;
    $("#understood").className = "understood empty-state";
    $("#understood").textContent = "Start typing a model. The parsed problem appears here instantly.";
    $("#parse-status").textContent = "Waiting for input";
    $("#parse-status").className = "pill warn";
    return false;
  }
  const token = ++state.parseToken;
  try {
    const data = await api("/api/parse", { text });
    if (token !== state.parseToken) return false;
    state.model = data.model;
    $("#understood").className = "understood";
    renderUnderstood();
    if (state.mode === "form") renderForm(data.model);
    saveSession();
    return true;
  } catch (error) {
    if (token !== state.parseToken) return false;
    if (showErrors) showParseError(error.message);
    return false;
  }
}

function debounce(callback, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => callback(...args), delay);
  };
}

function renderForm(model) {
  const names = model.var_names;
  $("#vars-grid").style.setProperty("--cols", 2);
  $("#vars-grid").innerHTML = names.map((name, index) => `
    <div class="form-line">
      <span class="mini-label">x${index + 1}</span>
      <input class="mini-input" data-var-name="${index}" value="${escapeHtml(name)}" aria-label="Variable ${index + 1} name">
      <input class="mini-input" data-obj="${index}" value="${escapeHtml(model.c[index])}" aria-label="Objective coefficient ${index + 1}">
      <span></span>
    </div>
  `).join("");
  $("#constraints-grid").style.setProperty("--cols", Math.max(names.length + 2, 3));
  $("#constraints-grid").innerHTML = model.constraints.map((row, index) => `
    <div class="form-line" data-constraint="${index}">
      <span class="mini-label">Row ${index + 1}</span>
      ${row.coeffs.map((coefficient, variable) => `<input class="mini-input" data-coeff="${index}-${variable}" value="${escapeHtml(coefficient)}" aria-label="Row ${index + 1} coefficient ${variable + 1}">`).join("")}
      <select class="mini-input" data-op="${index}" aria-label="Row ${index + 1} operator">
        ${["<=", ">=", "="].map((op) => `<option ${op === row.op ? "selected" : ""}>${op}</option>`).join("")}
      </select>
      <input class="mini-input" data-rhs="${index}" value="${escapeHtml(row.rhs)}" aria-label="Row ${index + 1} right hand side">
      <button class="icon-tiny" data-remove-constraint="${index}" type="button" aria-label="Remove row ${index + 1}">✕</button>
    </div>
  `).join("");
  $("#form-sense").value = model.sense;
  $$("[data-remove-constraint]").forEach((button) => button.addEventListener("click", () => {
    const index = Number(button.dataset.removeConstraint);
    const rows = $$("#constraints-grid .form-line");
    if (rows.length > 1) rows[index].remove();
    renumberFormRows();
  }));
}

function renumberFormRows() {
  $$("#constraints-grid .form-line").forEach((row, index) => {
    $(".mini-label", row).textContent = `Row ${index + 1}`;
  });
}

function formToPayload() {
  const names = $$("[data-var-name]").map((input) => input.value.trim() || `x${Number(input.dataset.varName) + 1}`);
  const c = $$("[data-obj]").map((input) => input.value.trim() || "0");
  const rows = $$("#constraints-grid .form-line");
  const A = rows.map((row, index) => names.map((_, variable) => $(`[data-coeff="${index}-${variable}"]`, row)?.value || "0"));
  const ops = rows.map((row, index) => $(`[data-op="${index}"]`, row)?.value || "<=");
  const b = rows.map((row, index) => $(`[data-rhs="${index}"]`, row)?.value || "0");
  return { sense: $("#form-sense").value, c, A, ops, b, names };
}

function setMode(mode) {
  state.mode = mode;
  $$(".segment").forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $("#mode-text").hidden = mode !== "text";
  $("#mode-form").hidden = mode !== "form";
  if (mode === "form") {
    if (state.model) renderForm(state.model);
    else parseModel(false).then((ok) => { if (ok) renderForm(state.model); });
  }
}

async function loadExamples() {
  try {
    const data = await api("/api/examples");
    state.examples = data.items;
    renderExamples();
  } catch (error) {
    $("#examples-grid").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

function renderExamples() {
  $("#examples-grid").innerHTML = state.examples.map((example) => `
    <button class="example-card" data-example="${escapeHtml(example.key)}" type="button">
      <strong>${escapeHtml(example.name)}</strong>
      <span>${escapeHtml(example.description)}</span>
    </button>
  `).join("");
  $$("[data-example]").forEach((button) => button.addEventListener("click", () => loadExample(button.dataset.example)));
}

async function loadExample(key) {
  const example = state.examples.find((item) => item.key === key);
  if (!example) return;
  try {
    const response = await fetch("/api/examples");
    const data = await response.json();
    const full = data.items[key];
    state.currentExample = key;
    state.varSigns = full.var_signs || null;
    state.proposed = full.proposed || null;
    $("#lp-text").value = full.text;
    $("#problem-notes").value = full.description || "";
    updateLineNumbers();
    await parseModel(true);
    goToStep(2);
    toast(`Loaded ${example.name}.`, "success");
    saveSession();
  } catch (error) {
    toast(error.message, "error");
  }
}

function saveSession() {
  try {
    localStorage.setItem("lp-session", JSON.stringify({
      text: $("#lp-text").value,
      notes: $("#problem-notes").value,
      result: state.result,
      dual: state.dual,
      sensitivity: state.sensitivity,
      currentExample: state.currentExample,
      varSigns: state.varSigns,
      proposed: state.proposed,
    }));
  } catch (error) {
    localStorage.removeItem("lp-session");
  }
}

function restoreSession() {
  let session;
  try {
    session = JSON.parse(localStorage.getItem("lp-session") || "null");
  } catch (error) {
    return;
  }
  if (!session) return;
  $("#lp-text").value = session.text || "";
  $("#problem-notes").value = session.notes || "";
  state.currentExample = session.currentExample || null;
  state.varSigns = session.varSigns || null;
  state.proposed = session.proposed || null;
  state.result = session.result || null;
  state.dual = session.dual || null;
  state.sensitivity = session.sensitivity || null;
  updateLineNumbers();
  parseModel(false);
  if (state.result) renderAllViews();
}

async function solveModel() {
  let modelReady = false;
  if (state.mode === "text") {
    modelReady = await parseModel(true);
  } else {
    try {
      const data = await api("/api/parse", formToPayload());
      state.model = data.model;
      renderUnderstood();
      modelReady = true;
    } catch (error) {
      showParseError(error.message);
    }
  }
  if (!modelReady) return;

  $("#solve-skeleton").hidden = false;
  $("#result-empty").hidden = true;
  $("#result-content").hidden = true;
  goToStep(3);
  const payload = state.mode === "text" ? { text: $("#lp-text").value } : formToPayload();
  if (state.varSigns) payload.var_signs = state.varSigns;
  try {
    const result = await api("/api/solve", payload);
    state.result = result;
    const dualRequest = api("/api/dual", payload).catch(() => null);
    const sensitivityRequest = api("/api/sensitivity", payload).catch(() => null);
    const [dual, sensitivity] = await Promise.all([dualRequest, sensitivityRequest]);
    state.dual = dual;
    state.sensitivity = sensitivity;
    renderAllViews();
    pulseStep(3);
    toast(result.status === "optimal" ? "Optimal solution found." : `Status: ${result.status}.`, "success");
  } catch (error) {
    $("#result-empty").hidden = false;
    $("#result-empty").textContent = error.message;
    toast(error.message, "error");
  } finally {
    $("#solve-skeleton").hidden = true;
    saveSession();
  }
}

function renderAllViews() {
  $("#result-empty").hidden = true;
  $("#result-content").hidden = false;
  if (typeof renderSolution === "function") renderSolution(state.result);
  if (typeof renderSimplex === "function") renderSimplex(state.result);
  if (typeof renderGraph === "function") renderGraph(state.result);
  if (typeof renderDual === "function") renderDual(state.dual);
  if (typeof renderSensitivity === "function") renderSensitivity(state.sensitivity);
  if (typeof renderInterpret === "function") renderInterpret();
}

function clearAll() {
  $("#lp-text").value = "";
  $("#problem-notes").value = "";
  state.model = null;
  state.result = null;
  state.dual = null;
  state.sensitivity = null;
  state.compare = null;
  state.currentExample = null;
  state.varSigns = null;
  state.proposed = null;
  updateLineNumbers();
  parseModel(false);
  $("#result-content").hidden = true;
  $("#result-empty").hidden = false;
  $("#result-empty").textContent = "Solve a model to see the results here.";
  $("#understood").className = "understood empty-state";
  $("#understood").textContent = "Start typing a model. The parsed problem appears here instantly.";
  localStorage.removeItem("lp-session");
  goToStep(1);
}

function bindCoreEvents() {
  $("#theme-toggle").addEventListener("click", () => setTheme(state.theme === "dark" ? "light" : "dark"));
  $$(".step").forEach((button) => button.addEventListener("click", () => goToStep(Number(button.dataset.step))));
  $$(".segment").forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
  $$(".result-tab").forEach((button) => button.addEventListener("click", () => selectResultTab(button.dataset.tab)));
  $("#lp-text").addEventListener("input", debounce(() => { updateLineNumbers(); parseModel(false); }, 350));
  $("#solve-button").addEventListener("click", solveModel);
  $("#clear-button").addEventListener("click", clearAll);
  $("#examples-refresh").addEventListener("click", loadExamples);
  $("#examples-menu").addEventListener("click", () => { goToStep(1); $("#examples-grid").scrollIntoView({ behavior: "smooth" }); });
  $("#help-button").addEventListener("click", () => toast("Syntax: one objective like 'Max z = 3x1 + 2x2', then one constraint per line with <=, >= or =."));
  $("#load-example-button").addEventListener("click", () => { goToStep(1); $("#examples-grid").scrollIntoView({ behavior: "smooth" }); });
  $("#add-var").addEventListener("click", () => {
    const count = $$("[data-var-name]").length + 1;
    $("#vars-grid").insertAdjacentHTML("beforeend", `
      <div class="form-line">
        <span class="mini-label">x${count}</span>
        <input class="mini-input" data-var-name="${count - 1}" value="x${count}" aria-label="Variable ${count} name">
        <input class="mini-input" data-obj="${count - 1}" value="0" aria-label="Objective coefficient ${count}">
        <span></span>
      </div>
    `);
    $$("#constraints-grid .form-line").forEach((row, index) => {
      const input = document.createElement("input");
      input.className = "mini-input";
      input.dataset.coeff = `${index}-${count - 1}`;
      input.value = "0";
      input.setAttribute("aria-label", `Row ${index + 1} coefficient ${count}`);
      row.insertBefore(input, row.querySelector("[data-op]"));
    });
  });
  $("#add-constraint").addEventListener("click", () => {
    const variableCount = $$("[data-var-name]").length;
    const index = $$("#constraints-grid .form-line").length;
    $("#constraints-grid").insertAdjacentHTML("beforeend", `
      <div class="form-line">
        <span class="mini-label">Row ${index + 1}</span>
        ${Array.from({ length: variableCount }, (_, variable) => `<input class="mini-input" data-coeff="${index}-${variable}" value="0" aria-label="Row ${index + 1} coefficient ${variable + 1}">`).join("")}
        <select class="mini-input" data-op="${index}" aria-label="Row ${index + 1} operator">
          <option>&lt;=</option><option>&gt;=</option><option>=</option>
        </select>
        <input class="mini-input" data-rhs="${index}" value="0" aria-label="Row ${index + 1} right hand side">
        <button class="icon-tiny" data-remove-constraint="${index}" type="button" aria-label="Remove row ${index + 1}">✕</button>
      </div>
    `);
    $(`[data-remove-constraint="${index}"]`).addEventListener("click", (event) => {
      event.currentTarget.closest(".form-line").remove();
      renumberFormRows();
    });
  });
  $("#problem-notes").addEventListener("input", saveSession);
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  bindCoreEvents();
  loadExamples();
  const savedStep = Number(localStorage.getItem("lp-step") || 1);
  goToStep(savedStep >= 1 && savedStep <= 4 ? savedStep : 1);
  restoreSession();
});

function statusLabel(status) {
  return {
    optimal: "Optimal",
    infeasible: "Infeasible",
    unbounded: "Unbounded",
  }[status] || status;
}

function renderSolution(result) {
  if (!result) return;
  const names = state.model ? state.model.var_names : (result.x || []).map((_, index) => `x${index + 1}`);
  const variables = result.x ? result.x.map((value, index) => `
    <tr><td>${pretty(names[index] || `x${index + 1}`)}</td><td>${escapeHtml(value)}</td><td>${Number(result.x_float[index]).toFixed(6)}</td></tr>
  `).join("") : "";
  const flags = [
    result.degenerate ? '<span class="pill warn">Degenerate</span>' : "",
    result.multiple_optima ? '<span class="pill warn">Alternative optima</span>' : "",
    result.status === "optimal" ? '<span class="pill">Exact arithmetic</span>' : "",
  ].join("");
  const notes = (result.notes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("");
  $("#panel-solution").innerHTML = `
    <div class="card-head row">
      <span class="status-badge status-${escapeHtml(result.status)}">${escapeHtml(statusLabel(result.status))}</span>
      <span class="muted">${result.iterations} iteration${result.iterations === 1 ? "" : "s"}</span>
    </div>
    ${result.z === null ? `<div class="empty-state">${escapeHtml((result.notes || []).join(" ") || "No objective value for this status.")}</div>` : `
      <div class="z-hero"><span class="value">${escapeHtml(result.z)}</span><span class="label">= maximum / minimum of z (exact)</span></div>
      <table class="data-table"><thead><tr><th>Variable</th><th>Exact value</th><th>Decimal</th></tr></thead><tbody>${variables}</tbody></table>
    `}
    <div class="flag-row">${flags}</div>
    ${notes ? `<ul class="rule-list">${notes}</ul>` : ""}
  `;
}

function renderTableau(step) {
  const head = step.col_names.map((name, index) => `
    <th class="${name === step.pivot?.col ? "entering-col" : ""}">${pretty(name)}<br><span class="muted">${escapeHtml(step.cj[index])}</span></th>
  `).join("");
  const rows = step.rows.map((row, index) => `
    <tr class="${step.leaving && step.basis[index] === step.leaving ? "leaving-row" : ""}">
      <td>${pretty(step.basis[index])}</td><td>${escapeHtml(step.cb[index])}</td>
      ${row.map((value, column) => {
        const isPivot = step.pivot && step.pivot.row === index + 1 && step.pivot.col === step.col_names[column];
        const isEntering = step.pivot && step.pivot.col === step.col_names[column];
        return `<td class="${isPivot ? "pivot-cell" : isEntering ? "entering-col" : ""}">${escapeHtml(value)}</td>`;
      }).join("")}
      <td>${escapeHtml(step.b[index])}</td><td class="muted">${escapeHtml(step.ratio_by_row[index])}</td>
    </tr>
  `).join("");
  const markerRow = (label, values) => `<tr><td><strong>${label}</strong></td><td></td>${values.map((value) => `<td>${escapeHtml(value)}</td>`).join("")}<td></td><td></td></tr>`;
  return `
    <div class="tableau-scroll"><table class="tableau">
      <thead><tr><th>Basis</th><th>Cb</th>${head}<th>b</th><th>Ratio</th></tr></thead>
      <tbody>${rows}${markerRow("Zj", step.zj)}${markerRow("Δj", step.delta)}</tbody>
    </table></div>
  `;
}

function renderSimplex(result) {
  clearInterval(state.playerTimer);
  state.playerTimer = null;
  const steps = (result && result.steps) || [];
  if (!steps.length) {
    $("#panel-simplex").innerHTML = '<div class="empty-state">No simplex tableau is available for this status.</div>';
    return;
  }
  let index = 0;
  const panel = $("#panel-simplex");
  const draw = () => {
    const step = steps[index];
    panel.innerHTML = `
      <div class="player-controls">
        <button class="button button-ghost" data-player="first" type="button">⏮</button>
        <button class="button button-ghost" data-player="prev" type="button">◀</button>
        <button class="button button-primary" data-player="play" type="button">▶ Play</button>
        <button class="button button-ghost" data-player="next" type="button">▶</button>
        <button class="button button-ghost" data-player="last" type="button">⏭</button>
        <strong>Iteration ${step.iteration} / ${steps.length - 1}</strong>
        <span class="muted">z = ${escapeHtml(step.z)}</span>
      </div>
      <input type="range" min="0" max="${steps.length - 1}" value="${index}" data-player-range aria-label="Simplex iteration">
      <div class="progress"><span style="width:${(index / Math.max(steps.length - 1, 1)) * 100}%"></span></div>
      ${renderTableau(step)}
      <div class="player-message">${escapeHtml(step.message)}</div>
      ${step.ratios.length ? `<p class="muted">Ratios: ${step.ratios.map((ratio) => `row ${escapeHtml(ratio.row)} → ${escapeHtml(ratio.value)}`).join(" · ")}</p>` : ""}
    `;
    $$("[data-player]", panel).forEach((button) => button.addEventListener("click", () => {
      const action = button.dataset.player;
      if (action === "play") {
        if (state.playerTimer) {
          clearInterval(state.playerTimer);
          state.playerTimer = null;
          draw();
          return;
        }
        $('[data-player="play"]', panel).textContent = "❚❚ Pause";
        state.playerTimer = setInterval(() => {
          if (index >= steps.length - 1) {
            clearInterval(state.playerTimer);
            state.playerTimer = null;
            draw();
          } else {
            index += 1;
            draw();
          }
        }, 900);
        return;
      }
      if (action === "first") index = 0;
      if (action === "prev") index = Math.max(0, index - 1);
      if (action === "next") index = Math.min(steps.length - 1, index + 1);
      if (action === "last") index = steps.length - 1;
      draw();
    }));
    $("[data-player-range]", panel).addEventListener("input", (event) => {
      clearInterval(state.playerTimer);
      state.playerTimer = null;
      index = Number(event.target.value);
      draw();
    });
  };
  draw();
}

function niceStep(range) {
  const rough = range / 8;
  const power = Math.pow(10, Math.floor(Math.log10(Math.max(rough, 1e-9))));
  const scaled = rough / power;
  const factor = scaled >= 5 ? 10 : scaled >= 2 ? 5 : scaled >= 1 ? 2 : 1;
  return factor * power;
}

function graphBounds(graphical) {
  const xs = [0];
  const ys = [0];
  graphical.lines.forEach((line) => {
    if (line.x_intercept !== null) xs.push(line.x_intercept);
    if (line.y_intercept !== null) ys.push(line.y_intercept);
  });
  graphical.polygon.forEach((point) => { xs.push(point.x); ys.push(point.y); });
  let minX = Math.min(...xs);
  let maxX = Math.max(...xs);
  let minY = Math.min(...ys);
  let maxY = Math.max(...ys);
  if (maxX - minX < 6) { minX -= 3; maxX += 3; }
  if (maxY - minY < 6) { minY -= 3; maxY += 3; }
  const padX = (maxX - minX) * 0.12;
  const padY = (maxY - minY) * 0.12;
  return {
    minX: minX - padX, maxX: maxX + padX,
    minY: minY - padY, maxY: maxY + padY,
  };
}

function lineEndpoints(a, b, rhs, bounds, project, width, height) {
  const points = [];
  const add = (x, y) => {
    if (x >= bounds.minX - 1e-7 && x <= bounds.maxX + 1e-7
      && y >= bounds.minY - 1e-7 && y <= bounds.maxY + 1e-7) {
      const [px, py] = project(x, y);
      if (px >= -1 && px <= width + 1 && py >= -1 && py <= height + 1) points.push([px, py]);
    }
  };
  if (Math.abs(b) > 1e-9) {
    add(bounds.minX, (rhs - a * bounds.minX) / b);
    add(bounds.maxX, (rhs - a * bounds.maxX) / b);
  }
  if (Math.abs(a) > 1e-9) {
    add((rhs - b * bounds.minY) / a, bounds.minY);
    add((rhs - b * bounds.maxY) / a, bounds.maxY);
  }
  if (points.length < 2) return null;
  return [points[0], points[points.length - 1]];
}

function renderGraph(result) {
  const panel = $("#panel-graph");
  const g = result && result.graphical;
  if (!g) {
    panel.innerHTML = '<div class="empty-state">The graph is available for models with exactly two variables.</div>';
    return;
  }
  const W = 720;
  const H = 480;
  const margin = 56;
  const bounds = graphBounds(g);
  const project = (x, y) => [
    margin + ((x - bounds.minX) / (bounds.maxX - bounds.minX)) * (W - 2 * margin),
    H - margin - ((y - bounds.minY) / (bounds.maxY - bounds.minY)) * (H - 2 * margin),
  ];
  const [originX, originY] = project(0, 0);
  const constraints = g.lines.map((line) => {
    const ends = lineEndpoints(line.a, line.b, line.rhs, bounds, project, W, H);
    if (!ends) return "";
    return `<line class="constraint-line ${line.op === "=" ? "equality" : ""}" x1="${ends[0][0]}" y1="${ends[0][1]}" x2="${ends[1][0]}" y2="${ends[1][1]}"><title>${escapeHtml(line.label)}</title></line>`;
  }).join("");
  const polygon = g.polygon.map((point) => project(point.x, point.y).join(",")).join(" ");
  const vertices = g.polygon.map((point) => {
    const [cx, cy] = project(point.x, point.y);
    return `<circle class="graph-vertex ${point.optimal ? "is-optimal" : ""}" cx="${cx}" cy="${cy}" r="${point.optimal ? 6 : 3.5}"><title>${escapeHtml(point.tooltip)}</title></circle>`;
  }).join("");
  const stepX = niceStep(bounds.maxX - bounds.minX);
  const stepY = niceStep(bounds.maxY - bounds.minY);
  const grid = [];
  for (let x = Math.ceil(bounds.minX / stepX) * stepX; x <= bounds.maxX; x += stepX) {
    const [px] = project(x, 0);
    grid.push(`<line class="grid-line" x1="${px}" y1="${margin}" x2="${px}" y2="${H - margin}"/><text x="${px}" y="${H - margin + 18}" text-anchor="middle">${Number(x.toFixed(2))}</text>`);
  }
  for (let y = Math.ceil(bounds.minY / stepY) * stepY; y <= bounds.maxY; y += stepY) {
    const [, py] = project(0, y);
    grid.push(`<line class="grid-line" x1="${margin}" y1="${py}" x2="${W - margin}" y2="${py}"/><text x="${margin - 10}" y="${py + 4}" text-anchor="end">${Number(y.toFixed(2))}</text>`);
  }
  const c = g.objective.c.map(Number);
  const corners = [[bounds.minX, bounds.minY], [bounds.minX, bounds.maxY], [bounds.maxX, bounds.minY], [bounds.maxX, bounds.maxY]];
  const objectives = corners.map((point) => c[0] * point[0] + c[1] * point[1])
    .concat(g.polygon.map((point) => point.z));
  let kMin = Math.min(...objectives);
  let kMax = Math.max(...objectives);
  if (kMax - kMin < 1e-9) { kMin -= 1; kMax += 1; }
  const startK = g.z === null ? (kMin + kMax) / 2 : Number(g.z);
  panel.innerHTML = `
    <div class="graph-wrap">
      <svg class="graph-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Graphical solution">
        ${grid.join("")}
        <line class="axis" x1="${margin}" y1="${originY}" x2="${W - margin + 8}" y2="${originY}"/>
        <line class="axis" x1="${originX}" y1="${H - margin}" x2="${originX}" y2="${margin - 8}"/>
        <text x="${W - margin + 12}" y="${originY + 4}">x₁</text>
        <text x="${originX + 8}" y="${margin - 12}">x₂</text>
        ${polygon ? `<polygon class="feasible-region" points="${polygon}"/>` : ""}
        ${constraints}
        <line id="objective-line" class="objective-line" x1="0" y1="0" x2="0" y2="0"/>
        <text id="objective-label" class="objective-label" x="${W - margin}" y="${margin - 18}" text-anchor="end"></text>
        ${vertices}
      </svg>
    </div>
    <div class="slider-row">
      <label for="objective-slider">Objective z</label>
      <input id="objective-slider" type="range" min="${kMin}" max="${kMax}" step="${(kMax - kMin) / 200}" value="${startK}">
      <span id="objective-value" class="range-value">z = ${Number(startK).toFixed(2)}</span>
    </div>
    <p class="muted">${g.region_bounded ? "The feasible region is bounded; the optimum is at a vertex." : "The feasible region is unbounded; the arrow of improving z never stops."}</p>
  `;
  const objectiveLine = $("#objective-line");
  const objectiveLabel = $("#objective-label");
  const objectiveValue = $("#objective-value");
  const updateObjective = (k) => {
    const ends = lineEndpoints(c[0], c[1], k, bounds, project, W, H);
    if (!ends) return;
    objectiveLine.setAttribute("x1", ends[0][0]);
    objectiveLine.setAttribute("y1", ends[0][1]);
    objectiveLine.setAttribute("x2", ends[1][0]);
    objectiveLine.setAttribute("y2", ends[1][1]);
    objectiveLabel.textContent = `z = ${Number(k).toFixed(2)}`;
    objectiveValue.textContent = `z = ${Number(k).toFixed(2)}`;
  };
  updateObjective(startK);
  $("#objective-slider").addEventListener("input", (event) => {
    state.graphK = Number(event.target.value);
    updateObjective(state.graphK);
  });
}

function renderCheckResult(check) {
  const box = $("#check-output");
  if (!box) return;
  if (!check) {
    box.innerHTML = '<div class="empty-state">Enter a point and press Check.</div>';
    return;
  }
  const verdictClass = check.verdict === "optimal" ? "pill" : "pill bad";
  const y = check.y ? check.y.map((value, index) => `<tr><td>y${index + 1}</td><td>${escapeHtml(value)}</td></tr>`).join("") : "";
  const steps = (check.steps || []).map((step) => `<li>${escapeHtml(typeof step === "string" ? step : JSON.stringify(step))}</li>`).join("");
  box.innerHTML = `
    <div class="card-head row">
      <span class="${verdictClass}">${escapeHtml(check.verdict)}</span>
      <span class="muted">primal ${check.primal_feasible ? "feasible" : "not feasible"} · dual ${check.dual_feasible ? "feasible" : "not feasible"}</span>
    </div>
    ${y ? `<table class="data-table"><thead><tr><th>Dual variable</th><th>Exact value</th></tr></thead><tbody>${y}</tbody></table>` : ""}
    ${steps ? `<ul class="rule-list">${steps}</ul>` : ""}
  `;
}

function renderDual(dual) {
  const panel = $("#panel-dual");
  if (!dual) {
    panel.innerHTML = '<div class="empty-state">The dual is unavailable for this model.</div>';
    return;
  }
  const primalText = state.model
    ? `${state.model.sense === "max" ? "Max" : "Min"} z = ${state.model.c.map((value, index) => `${value}${state.model.var_names[index]}`).join(" + ")}\n${state.model.constraints.map((row) => row.text).join("\n")}`
    : "";
  const y = dual.y ? dual.y.map((value, index) => `<tr><td>${pretty(dual.dual.var_names[index])}</td><td>${escapeHtml(value)}</td><td>${Number(dual.y_float[index]).toFixed(6)}</td></tr>`).join("") : "";
  const shadows = dual.shadow_prices.map((price, index) => {
    const label = state.model && state.model.constraints[index]
      ? state.model.constraints[index].text : `Constraint ${index + 1}`;
    return `<div class="shadow-card"><span class="muted">${escapeHtml(label)}</span><br><strong>${price === null ? "—" : escapeHtml(price)}</strong></div>`;
  }).join("");
  const rules = (dual.rules || []).map((rule) => `<li>${escapeHtml(rule)}</li>`).join("");
  const proposed = state.proposed || (state.result && state.result.x) || [];
  panel.innerHTML = `
    <div class="dual-grid">
      <div class="dual-card primal"><h3>Primal</h3><pre>${escapeHtml(primalText)}</pre></div>
      <div class="dual-arrows" aria-hidden="true">Aᵀ ⟷ c<br>b ⟷ cᵀ<br>≤ ⟷ ≥</div>
      <div class="dual-card dual-problem"><h3>Dual</h3><pre>${escapeHtml(dual.dual.text)}</pre></div>
    </div>
    <h3 style="margin-top:20px">Solution of the dual</h3>
    ${y ? `<table class="data-table"><thead><tr><th>Variable</th><th>Exact</th><th>Decimal</th></tr></thead><tbody>${y}</tbody></table>` : '<div class="empty-state">The dual has no optimal solution.</div>'}
    <div class="z-hero"><span class="value">${dual.w === null ? "—" : escapeHtml(dual.w)}</span><span class="label">w = ${dual.strong_duality ? "equals z (strong duality)" : "dual objective"}</span></div>
    <h3>Shadow prices</h3>
    <div class="shadow-grid">${shadows || '<div class="empty-state">Not available.</div>'}</div>
    <ul class="rule-list">${rules}</ul>
    <h3 style="margin-top:20px">Complementary slackness</h3>
    <label class="field-label" for="check-input">Proposed x values (comma separated)</label>
    <div class="row">
      <input id="check-input" class="input" value="${escapeHtml(proposed.join(", "))}" placeholder="0, 4/3, 2/3">
      <button id="check-button" class="button button-primary" type="button">Check</button>
    </div>
    <div id="check-output" style="margin-top:12px"></div>
  `;
  renderCheckResult(null);
  $("#check-button").addEventListener("click", async () => {
    const payload = state.mode === "text" ? { text: $("#lp-text").value } : formToPayload();
    payload.x = $("#check-input").value.split(/[\s,;]+/).filter(Boolean);
    try {
      renderCheckResult(await api("/api/check", payload));
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

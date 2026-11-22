const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "..", "static", "js", "app.js"), "utf8");
const elements = {
  "#lp-text": { value: "" },
  "#problem-notes": { value: "" },
  "#line-numbers": { textContent: "" },
};
const sandbox = {
  console,
  document: { addEventListener() {}, querySelector: (selector) => elements[selector] },
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  window: { matchMedia: () => ({ matches: false }) },
  setTimeout,
  clearTimeout,
};
vm.createContext(sandbox);
vm.runInContext(`${source}
globalThis.__helpers = {
  normaliseExamples, applyExample, requireResult, formatDecimal, hintHtml,
  objectiveLabel, verdictPillClass, dualStateText, degenerateDualNote, state,
};`, sandbox);
const {
  normaliseExamples, applyExample, requireResult, formatDecimal, hintHtml,
  objectiveLabel, verdictPillClass, dualStateText, degenerateDualNote, state,
} = sandbox.__helpers;

const cards = normaliseExamples({ examples: [{ id: "a", title: "A", description: "desc", text: "Max z = x" }] });
assert.strictEqual(cards.length, 1);
assert.deepStrictEqual(Object.keys(cards[0]).sort(), ["description", "id", "text", "title"]);
assert.deepStrictEqual(normaliseExamples([cards[0]]), cards);

const legacy = normaliseExamples({ items: { b: { name: "B", description: "old", text: "Min z = y" } } });
assert.strictEqual(legacy[0].id, "b");
assert.strictEqual(legacy[0].title, "B");

state.examples = cards;
applyExample(cards[0]);
assert.strictEqual(elements["#lp-text"].value, "Max z = x");
assert.strictEqual(elements["#problem-notes"].value, "desc");
assert.strictEqual(elements["#line-numbers"].textContent, "1");

let lastToast = "";
sandbox.toast = (message) => { lastToast = message; };
state.result = null;
assert.strictEqual(requireResult(), false);
assert.strictEqual(lastToast, "Solve a model first");
state.result = { status: "optimal" };
assert.strictEqual(requireResult(), true);

assert.strictEqual(formatDecimal(5), "5");
assert.strictEqual(formatDecimal(1000 / 3), "333.333333");
assert.strictEqual(formatDecimal(2.5, 2), "2.5");
assert.strictEqual(hintHtml(["'<' is treated as '<='"]),
  '<div class="lp-line hint-line">&#39;&lt;&#39; is treated as &#39;&lt;=&#39;</div>');
assert.strictEqual(objectiveLabel("min"), "minimum of z");
assert.strictEqual(objectiveLabel("max"), "maximum of z");
assert.strictEqual(verdictPillClass({ verdict: "optimal" }), "pill");
assert.strictEqual(verdictPillClass({ verdict: "not optimal" }), "pill bad");
assert.strictEqual(verdictPillClass({ verdict: "undetermined" }), "pill warn");
assert.strictEqual(dualStateText({ verdict: "not optimal", y: null }), "no dual vector derived");
assert.strictEqual(dualStateText({ verdict: "not optimal", y: ["1"] }), "dual not feasible");
assert.strictEqual(
  degenerateDualNote({ degenerate: true, alternative_ys: [["400", "0"], ["0", "1000/3"]] }),
  "Degenerate primal: the dual has several optimal solutions, e.g. (400, 0) and (0, 1000/3); shadow prices are not unique."
);
assert.strictEqual(degenerateDualNote({ degenerate: false, alternative_ys: [] }), "");

console.log("frontend helper tests passed");

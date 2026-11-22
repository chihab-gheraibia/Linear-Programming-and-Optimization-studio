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
vm.runInContext(`${source}\nglobalThis.__helpers = { normaliseExamples, applyExample, state };`, sandbox);
const { normaliseExamples, applyExample, state } = sandbox.__helpers;

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

console.log("frontend helper tests passed (examples)");

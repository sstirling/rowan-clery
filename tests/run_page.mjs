// Executes the built page's script against a minimal DOM stub.
//
// `node --check` only parses. It cannot catch a ReferenceError from an identifier that
// was renamed or deleted — which is how `YEARS is not defined` shipped a page whose
// headings rendered and whose every chart was empty. This runs the script for real and
// reports anything it throws, plus whether the mount points actually received content.
//
// Usage: node tests/run_page.mjs <path-to-built-index.html>

import fs from "node:fs";

const file = process.argv[2];
const html = fs.readFileSync(file, "utf8");

const payload = html.split('type="application/json">')[1].split("</script>")[0];
const scripts = [...html.matchAll(/<script>\s*\n([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const source = scripts.sort((a, b) => b.length - a.length)[0];

// Every element records what was written to it, so the harness can tell "rendered
// nothing" from "rendered something".
const written = {};
function makeEl(id = "") {
  const el = {
    id,
    style: {},
    dataset: {},
    options: [],
    children: [],
    classList: { add() {}, remove() {}, contains: () => false },
    get innerHTML() {
      return written[id] || "";
    },
    set innerHTML(v) {
      written[id] = String(v);
    },
    set textContent(v) {
      written[id] = String(v);
    },
    get textContent() {
      return written[id] || "";
    },
    value: "",
    closest: () => makeEl(),
    appendChild() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {},
    getBoundingClientRect: () => ({ x: 0, y: 0, width: 600, height: 400, top: 0, left: 0 }),
    scrollIntoView() {},
    querySelector: () => makeEl(),
    querySelectorAll: () => [],
    setAttribute() {},
    getAttribute: () => null,
    hasAttribute: () => false,
    removeAttribute() {},
    insertBefore() {},
  };
  return el;
}

const registry = new Map();
const byId = (id) => {
  if (!registry.has(id)) registry.set(id, makeEl(id));
  return registry.get(id);
};

const payloadEl = makeEl("payload");
Object.defineProperty(payloadEl, "textContent", { get: () => payload, set() {} });
registry.set("payload", payloadEl);

const SELECTOR_ID = /^#([\w-]+)$/;
globalThis.document = {
  documentElement: makeEl("html"),
  body: makeEl("body"),
  getElementById: byId,
  querySelector(sel) {
    const m = SELECTOR_ID.exec(sel);
    return m ? byId(m[1]) : makeEl();
  },
  querySelectorAll: () => [],
  createElement: () => makeEl(),
  addEventListener() {},
};
globalThis.window = globalThis;
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
globalThis.getComputedStyle = () => ({ getPropertyValue: () => "#2a78d6", fill: "#000" });
globalThis.requestAnimationFrame = (fn) => fn();
globalThis.innerWidth = 1280;
globalThis.innerHeight = 900;
globalThis.scrollY = 0;
globalThis.scrollTo = () => {};

try {
  // Indirect eval keeps the script in global scope, as a <script> tag would be.
  (0, eval)(source);
} catch (err) {
  console.error("THREW: " + (err && err.stack ? err.stack.split("\n")[0] : err));
  process.exit(1);
}

// A page that throws nothing but renders nothing is the failure we actually shipped.
const required = ["stats", "chart-month", "chart-cat", "chart-trend", "chart-loc", "chart-disp", "scope"];
const empty = required.filter((id) => !written[id] || written[id].length < 20);
if (empty.length) {
  console.error("EMPTY: these mount points received no content: " + empty.join(", "));
  process.exit(2);
}

console.log("OK " + required.map((id) => `${id}:${written[id].length}b`).join(" "));

// Executes a built page's script against a minimal DOM stub.
//
// `node --check` only parses. It cannot catch a ReferenceError from an identifier that
// was renamed or deleted — which is how `YEARS is not defined` shipped a page whose
// headings rendered and whose every chart was empty. This runs the script for real and
// reports anything it throws, plus whether the mount points actually received content.
//
// Usage: node tests/run_page.mjs <path-to-built-page.html>
//
// Each page is checked against its OWN expectations, keyed by filename: about.html has
// no charts and changes.html has no incident table, so one shared list of required
// mounts would either fail on them or stop guarding the overview.

import fs from "node:fs";
import path from "node:path";

const file = process.argv[2];
if (!file) {
  console.error("usage: node tests/run_page.mjs <built page>");
  process.exit(64);
}
const html = fs.readFileSync(file, "utf8");
const name = path.basename(file);

// What each page must end up showing. `charts` are the export registrations behind the
// "Copy data" buttons — a chart that draws but exports nothing is a silently dead button.
const EXPECT = {
  "index.html": {
    mounts: ["stats", "activity", "banners", "scope", "chart-month", "chart-cat",
             "chart-trend", "chart-loc", "chart-disp", "tbl tbody", "foot"],
    charts: ["month", "cat", "trend", "loc", "disp", "table"],
  },
  "changes.html": {
    mounts: ["feedsub", "feed", "quality", "foot"],
    charts: ["changes"],
  },
  "about.html": {
    mounts: ["foot"],
    charts: [],
  },
};
const expect = EXPECT[name];
if (!expect) {
  console.error(`UNKNOWN PAGE: ${name} has no entry in EXPECT — add one so it is actually checked`);
  process.exit(64);
}

const payloadParts = html.split('type="application/json">');
if (payloadParts.length < 2) {
  console.error(`NO PAYLOAD: ${name} has no <script id="payload" type="application/json"> block`);
  process.exit(5);
}
const payload = payloadParts[1].split("</script>")[0];

// Selected by an explicit marker, not by being the longest <script> on the page. The
// pages now carry a small theme script in <head> too, and "longest wins" would be a
// coin flip the day someone adds a third.
const mainMatch = /<script data-main>\s*\n([\s\S]*?)<\/script>/.exec(html);
if (!mainMatch) {
  console.error(`NO SCRIPT: ${name} has no <script data-main> block`);
  process.exit(5);
}
const source = mainMatch[1];

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
    set className(v) {
      this._class = String(v);
    },
    get className() {
      return this._class || "";
    },
    value: "",
    href: "",
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
    remove() {},
    select() {},
    click() {},
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

// "#tbl tbody" and the like resolve to one stub keyed by the whole selector, so a write
// into the table body is still observable.
const SELECTOR_ID = /^#([\w-]+)$/;
const SELECTOR_ID_DESC = /^#([\w-]+)\s+([\w-]+)$/;
globalThis.document = {
  documentElement: makeEl("html"),
  body: makeEl("body"),
  getElementById: byId,
  querySelector(sel) {
    const direct = SELECTOR_ID.exec(sel);
    if (direct) return byId(direct[1]);
    const desc = SELECTOR_ID_DESC.exec(sel);
    if (desc) return byId(`${desc[1]} ${desc[2]}`);
    return makeEl();
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
  // `const` at top level creates a LEXICAL global, not a property on globalThis, so the
  // export registry has to be handed out explicitly from inside the same evaluation.
  (0, eval)(source +
    "\n;globalThis.__CHART_DATA = typeof CHART_DATA !== 'undefined' ? CHART_DATA : null;" +
    "\n;globalThis.__RENDER = typeof render !== 'undefined' ? render : null;");
} catch (err) {
  console.error("THREW: " + (err && err.stack ? err.stack.split("\n")[0] : err));
  process.exit(1);
}

// A page that throws nothing but renders nothing is the failure we actually shipped.
const empty = expect.mounts.filter((id) => !written[id] || written[id].length < 20);
if (empty.length) {
  console.error("EMPTY: these mount points received no content: " + empty.join(", "));
  process.exit(2);
}

// Every export button must have rows behind it. The table registers a function, because
// its rows change with the filters, so resolve whatever shape is registered.
const data = globalThis.__CHART_DATA || {};
const resolve = (id) => {
  const d = data[id];
  return typeof d === "function" ? d() : d;
};
const missing = expect.charts.filter((id) => {
  const d = resolve(id);
  return !d || !d.rows || !d.rows.length;
});
if (missing.length) {
  console.error("NO DATA: these exports registered no rows: " + missing.join(", "));
  process.exit(3);
}
const ragged = expect.charts.filter((id) => {
  const d = resolve(id);
  return d.rows.some((r) => r.length !== d.header.length);
});
if (ragged.length) {
  console.error("RAGGED: rows do not match the header width in: " + ragged.join(", "));
  process.exit(4);
}

// The whole point of the table's export buttons is that they follow the filters. A
// snapshot registered once at load would pass every check above and still hand the
// reader all 208 rows when they asked for October.
if (name === "index.html") {
  const search = registry.get("q");
  const month = registry.get("f-month");
  const rowCount = () => resolve("table").rows.length;
  const unfiltered = rowCount();

  search.value = "harassment";
  globalThis.__RENDER();
  const searched = rowCount();

  search.value = "";
  month.value = "October 2026";
  globalThis.__RENDER();
  const byMonth = rowCount();

  month.value = "";
  globalThis.__RENDER();
  const restored = rowCount();

  const problems = [];
  if (!(searched > 0 && searched < unfiltered)) problems.push(`search gave ${searched} of ${unfiltered}`);
  if (!(byMonth > 0 && byMonth < unfiltered)) problems.push(`month filter gave ${byMonth} of ${unfiltered}`);
  if (restored !== unfiltered) problems.push(`clearing filters gave ${restored}, not ${unfiltered}`);
  if (problems.length) {
    console.error("EXPORT IGNORES FILTERS: " + problems.join("; "));
    process.exit(6);
  }
}

console.log(
  `OK ${name} | ` + expect.mounts.map((id) => `${id}:${written[id].length}b`).join(" ") +
  (expect.charts.length
    ? " | export " + expect.charts.map((id) => `${id}:${resolve(id).rows.length}r`).join(" ")
    : " | no exports")
);

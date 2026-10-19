/**
 * "The record that vanished" — a 30-slide conference talk (30-45 min).
 *
 * Walks a non-technical newsroom audience through building an append-only archive of a
 * public record, using github.com/sstirling/rowan-clery as the worked example, and
 * introducing the terminal, Claude Code and GitHub as the story needs them.
 *
 * EVERY FIGURE IN THIS DECK IS MEASURED, not illustrative. The numbers were read out of
 * the live archive on 2026-10-18 (see FACTS below, and `talk/README.md` for the commands
 * that reproduce them). If the archive moves, re-run those and update FACTS.
 *
 * Build:  npm install pptxgenjs && node build_deck.js
 */

const pptxgen = require("pptxgenjs");
const path = require("path");
const { applyTheme } = require(path.join(
  process.env.SKILL_DIR || ".",
  "scripts/apply_theme.js"
));

const OUT = process.env.OUT_PPTX || "the-record-that-vanished.pptx";
const AS_OF = "October 18, 2026";

// ---- measured facts ------------------------------------------------------------
// Read from data/archive/ on 2026-10-18 at commit 6b3bb0f.
const F = {
  archiveTotal: "2,434",
  backfill: "2,167",
  live: "267",
  rangeStart: "Dec. 2017",
  rangeEnd: "Oct. 2026",
  added: "2,449",
  amended: "129",
  sourceRemoved: "14",
  commits: "55",
  snapshots: "24",
  natureTokens: "259",
  categories: "42",
  dispTokens: "101",
  dispFlags: "28",
  tests: "174",
  testLines: "2,454",
  pipeLines: "3,125",
  gpdLag: "13.7",
  rupdLag: "0.0",
  csaLag: "0.3",
  gpdWithin24: "1%",
  rupdWithin24: "89%",
  monthLabels: ["June", "July", "Aug.", "Sept.", "Oct."],
  reported: [14, 23, 42, 109, 79],
  occurred: [11, 23, 49, 144, 28],
};

// ---- palette -------------------------------------------------------------------
// Ink and paper dominate; vermillion is the single sharp accent, used only where the
// talk is about something failing or disappearing. Teal is the "preserved" colour.
const INK = "141A1F";
const PANEL = "1F2831";
const PAPER = "FFFFFF";
const SLATE = "2E3A44";
const MIST = "F1F3F5";
const VERM = "C8453C";
const TEAL = "1F6F6B";      // on light grounds
const TEAL_L = "48A89E";    // on the dark panels only
const AMBER = "A8761B";
const AMBER_L = "E0A94A"; // amber for dark panels only
const GREY = "5A6B78";
const GREY_L = "9AA9B5";    // muted, but legible on the dark grounds
const DEEP = "2A4D6E";

const THEME = {
  name: "Public Record",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: INK,
    lt1: PAPER,
    dk2: SLATE,
    lt2: MIST,
    accent1: VERM,
    accent2: TEAL,
    accent3: AMBER,
    accent4: GREY,
    accent5: DEEP,
    accent6: PANEL,
    hlink: TEAL,
    folHlink: GREY,
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 — must be set before any slide is added
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Stephen Stirling";
pres.title = "The record that vanished";
pres.subject = "Building an append-only public-records archive with Claude Code";

const C = pres.SchemeColor;
const MONO = "Courier New"; // deliberate exception to the theme fonts: terminal output

// ---- geometry ------------------------------------------------------------------
const M = 0.7; // side margin
const W = 13.333 - M * 2; // usable width: 11.933
const BODY_TOP = 2.05;
const BODY_BOT = 6.75;

// ---- layouts -------------------------------------------------------------------
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text1 },
  objects: [
    {
      placeholder: {
        options: { name: "title", type: "title", margin: 0, x: M, y: 2.35, w: W, h: 2.1,
          fontSize: 54, bold: true, color: C.background1, align: "left",
          valign: "bottom" },
        text: "",
      },
    },
    {
      placeholder: {
        options: { name: "body", type: "body", margin: 0, x: M, y: 4.6, w: 10.6, h: 1.3,
          fontSize: 19, color: C.background2, valign: "top", lineSpacingMultiple: 1.2 },
        text: "",
      },
    },
  ],
});

pres.defineSlideMaster({
  title: "SECTION_DARK",
  background: { color: C.text1 },
  objects: [
    {
      placeholder: {
        options: { name: "title", type: "title", margin: 0, x: M, y: 2.9, w: W, h: 1.5,
          fontSize: 44, bold: true, color: C.background1, align: "left",
          valign: "bottom" },
        text: "",
      },
    },
    {
      placeholder: {
        options: { name: "body", type: "body", margin: 0, x: M, y: 4.55, w: 10.2, h: 1.1,
          fontSize: 17, color: C.background2, valign: "top" },
        text: "",
      },
    },
  ],
});

// Title at an identical position on every light content slide.
const lightTitle = {
  options: { name: "title", type: "title", margin: 0, x: M, y: 0.92, w: W, h: 0.95,
    fontSize: 33, bold: true, color: C.text1, align: "left", valign: "middle" },
  text: "",
};
const lightFooter = [
  {
    text: {
      text: "github.com/sstirling/rowan-clery",
      options: { x: M, y: 6.98, w: 6, h: 0.3, fontSize: 10, color: C.accent4,
        isTextBox: true, margin: 0 },
    },
  },
  {
    placeholder: {
      options: { name: "slideNum", type: "sldNum", x: 12.35, y: 6.98, w: 0.6, h: 0.3,
        fontSize: 10, color: C.accent4, align: "right" },
      text: "",
    },
  },
];

pres.defineSlideMaster({
  title: "CONTENT_LIGHT",
  background: { color: C.background1 },
  objects: [
    { placeholder: lightTitle },
    {
      placeholder: {
        options: { name: "body", type: "body", margin: 0, x: M, y: BODY_TOP, w: W, h: 4.6,
          fontSize: 16, color: C.text2, valign: "top" },
        text: "",
      },
    },
    ...lightFooter,
  ],
});

pres.defineSlideMaster({
  title: "TITLE_ONLY_LIGHT",
  background: { color: C.background1 },
  objects: [{ placeholder: lightTitle }, ...lightFooter],
});

pres.defineSlideMaster({
  title: "CHART_LIGHT",
  background: { color: C.background1 },
  objects: [
    { placeholder: lightTitle },
    {
      placeholder: {
        options: { name: "chart", type: "chart", x: M, y: BODY_TOP, w: 7.75, h: 4.5,
          color: C.text2 },
        text: "",
      },
    },
    {
      placeholder: {
        options: { name: "body", type: "body", margin: 0, x: 8.75, y: BODY_TOP, w: 3.85, h: 4.5,
          fontSize: 15, color: C.text2, valign: "top" },
        text: "",
      },
    },
    ...lightFooter,
  ],
});

pres.defineSlideMaster({
  title: "STAT_DARK",
  background: { color: C.text1 },
  objects: [
    {
      placeholder: {
        options: { name: "title", type: "title", margin: 0, x: M, y: 0.92, w: W, h: 0.95,
          fontSize: 33, bold: true, color: C.background1, align: "left",
          valign: "middle" },
        text: "",
      },
    },
    {
      placeholder: {
        options: { name: "slideNum", type: "sldNum", x: 12.35, y: 6.98, w: 0.6, h: 0.3,
          fontSize: 10, color: C.accent4, align: "right" },
        text: "",
      },
    },
  ],
});

// ---- composition helpers -------------------------------------------------------

/** The deck's one repeated motif: a monospace kicker chip, like a terminal label. */
function chip(slide, text, opts = {}) {
  const x = opts.x ?? M;
  const y = opts.y ?? 0.5;
  const fill = opts.fill ?? INK;
  const color = opts.color ?? PAPER;
  const w = opts.w ?? Math.max(1.0, 0.115 * text.length + 0.34);
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 0.32, fill: { color: fill }, rectRadius: 0.05,
    line: { type: "none" }, objectName: `chip-bg-${text.slice(0, 14)}`,
  });
  slide.addText(text, {
    x, y, w, h: 0.32, fontSize: 10, bold: true, fontFace: MONO, color,
    align: "center", valign: "middle", charSpacing: 1, isTextBox: true, margin: 0,
    objectName: `chip-${text.slice(0, 14)}`,
  });
}

/** A terminal block. Lines are monospace on a dark panel. */
function terminal(slide, lines, o) {
  const h = o.h ?? 0.34 * lines.length + 0.46;
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h, fill: { color: o.fill ?? INK }, rectRadius: 0.04,
    line: { type: "none" },
    shadow: { type: "outer", color: "000000", blur: 10, offset: 2, angle: 90, opacity: 0.18 },
    objectName: o.name ?? "terminal",
  });
  slide.addText(
    lines.map((l, i) => ({
      text: l.text ?? l,
      options: {
        fontSize: o.fontSize ?? 13,
        fontFace: MONO,
        color: l.color ?? (o.color ?? MIST),
        bold: !!l.bold,
        breakLine: i !== lines.length - 1,
      },
    })),
    { x: o.x + 0.26, y: o.y + 0.22, w: o.w - 0.5, h: h - 0.44, valign: "top",
      isTextBox: true, margin: 0, lineSpacingMultiple: 1.15,
      objectName: (o.name ?? "terminal") + "-text" }
  );
  return h;
}

/** A tinted card. Set apart by background tint and shadow — never an edge stripe. */
function card(slide, o) {
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h, fill: { color: o.fill ?? MIST }, rectRadius: 0.04,
    line: { type: "none" },
    shadow: { type: "outer", color: "000000", blur: 8, offset: 1, angle: 90, opacity: 0.10 },
    objectName: o.name ?? "card",
  });
  let y = o.y + 0.26;
  if (o.num != null) {
    slide.addShape(pres.ShapeType.ellipse, {
      x: o.x + 0.26, y, w: 0.42, h: 0.42, fill: { color: o.accent ?? TEAL },
      line: { type: "none" }, objectName: (o.name ?? "card") + "-num-bg",
    });
    slide.addText(String(o.num), {
      x: o.x + 0.26, y, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: PAPER,
      align: "center", valign: "middle", isTextBox: true, margin: 0,
      objectName: (o.name ?? "card") + "-num",
    });
  }
  const tx = o.num != null ? o.x + 0.84 : o.x + 0.3;
  const tw = o.w - (o.num != null ? 1.14 : 0.6);
  if (o.head) {
    slide.addText(o.head, {
      x: tx, y: o.num != null ? y - 0.04 : y, w: tw, h: 0.5,
      fontSize: o.headSize ?? 16, bold: true,
      color: o.headColor ?? (o.fill === PANEL ? PAPER : INK),
      valign: "middle", isTextBox: true, margin: 0,
      objectName: (o.name ?? "card") + "-head",
    });
    y += 0.52;
  }
  if (o.text) {
    slide.addText(o.text, {
      x: tx, y, w: tw, h: o.textH ?? (o.y + o.h - y - 0.22),
      fontSize: o.textSize ?? 14, color: o.textColor ?? (o.fill === PANEL ? MIST : SLATE),
      valign: "top", isTextBox: true, margin: 0, lineSpacingMultiple: 1.18,
      objectName: (o.name ?? "card") + "-text",
    });
  }
}

/** A big measured number with its label underneath. */
function stat(slide, o) {
  slide.addText(o.value, {
    x: o.x, y: o.y, w: o.w, h: o.vh ?? 1.15, fontSize: o.size ?? 62, bold: true,
    color: o.color ?? VERM, align: o.align ?? "left", valign: "bottom",
    isTextBox: true, margin: 0, objectName: `stat-${o.label.slice(0, 12)}`,
  });
  slide.addText(o.label, {
    x: o.x, y: o.y + (o.vh ?? 1.15) + 0.04, w: o.w, h: o.lh ?? 0.95,
    fontSize: o.labelSize ?? 14, color: o.labelColor ?? MIST, align: o.align ?? "left",
    valign: "top", isTextBox: true, margin: 0, lineSpacingMultiple: 1.15,
    objectName: `statlabel-${o.label.slice(0, 12)}`,
  });
}

function bullets(slide, items, o = {}) {
  const ov = o.override || {};
  const box = ov.w
    ? { x: M + 0.22, y: BODY_TOP, w: ov.w - 0.22, h: BODY_BOT - BODY_TOP,
        fontSize: ov.fontSize ?? 16, color: SLATE, valign: "top",
        isTextBox: true, margin: 0, objectName: ov.objectName ?? "bullets" }
    : { placeholder: "body" };
  slide.addText(
    items.map((t, i) => ({
      text: t,
      options: { bullet: { indent: 13 }, breakLine: i !== items.length - 1,
        paraSpaceAfter: o.gap ?? 10 },
    })),
    box
  );
}

const chartBase = () => ({
  showLegend: false,
  showTitle: false,
  catAxisLabelColor: SLATE,
  valAxisLabelColor: GREY,
  catAxisLabelFontFace: "+mn-lt",
  valAxisLabelFontFace: "+mn-lt",
  catAxisLabelFontSize: 12,
  valAxisLabelFontSize: 11,
  dataLabelColor: INK,
  dataLabelFontFace: "+mn-lt",
  dataLabelFontSize: 12,
  dataLabelFontBold: true,
  catGridLine: { style: "none" },
  valGridLine: { color: "E3E7EA", size: 1 },
  catAxisLineShow: false,
  valAxisLineShow: false,
});

// ================================================================================
// SECTION 1 — the record that vanished
// ================================================================================
pres.addSection({ title: "Opening" });

let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Opening" });
chip(s, "PUBLIC RECORDS  ·  CLAUDE CODE", { y: 1.75, fill: VERM });
s.addText("The record that vanished", { placeholder: "title" });
s.addText(
  "How to build an archive of a public record that keeps changing — " +
    "with a terminal, Claude Code, and a free robot",
  { placeholder: "body" }
);
s.addText("Stephen Stirling", {
  x: M, y: 6.25, w: 8, h: 0.4, fontSize: 14, bold: true, color: TEAL_L,
  isTextBox: true, margin: 0, objectName: "byline",
});
s.addNotes(
  "Open with the story, not the tooling. The point of the talk: the hard part of this " +
    "project was never the code. It was deciding what counts as a number you can defend."
);

s = pres.addSlide({ masterName: "STAT_DARK", sectionTitle: "Opening" });
chip(s, "01  THE HOOK", { fill: VERM });
s.addText("On October 1, this public record stopped being public", {
  placeholder: "title",
});
terminal(
  s,
  [
    { text: "$ python run.py all", color: TEAL_L },
    "! June 2026 Daily Crime Log REMOVED:",
    "  .../1TLdzJn6iUkT.../export?format=csv",
    { text: "  failed after 4 attempts: HTTP Error 401: Unauthorized", color: VERM },
  ],
  { x: M, y: 2.2, w: 7.5, fill: PANEL, name: "term-401" }
);
stat(s, {
  x: 8.75, y: 2.3, w: 3.9, value: "14", color: VERM,
  label: "incidents in that month's log. The sheet is still there — Rowan just " +
    "stopped sharing it. Those rows now exist in one public place, and it isn't Rowan's.",
  lh: 1.9,
});
s.addText(
  "The pipeline had been saving a copy twice a day since June. That is the only reason " +
    "this slide has numbers on it.",
  { x: M, y: 5.5, w: 7.5, h: 0.9, fontSize: 15, color: MIST, italic: true,
    isTextBox: true, margin: 0, objectName: "note-401" }
);
s.addNotes(
  "Don't allege bad intent — we don't know why sharing changed. The journalistic point " +
    "is simply that a record which was public is no longer, and without an independent " +
    "copy there would be nothing to compare against."
);

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Opening" });
chip(s, "02  THE RECORD");
s.addText("Every US campus has to publish a daily crime log", { placeholder: "title" });
bullets(s, [
  "The Clery Act requires any college that takes federal student aid to keep one — " +
    "and to make it open to the public.",
  "Each entry: the nature of the incident, when it was reported, when it occurred, " +
    "the general location, and the disposition.",
  "New entries within two business days. It is one of the few crime records you can " +
    "read without filing anything.",
], { override: { w: 7.1, fontSize: 16 } });
card(s, {
  x: 8.1, y: BODY_TOP, w: 4.53, h: 2.05, fill: MIST, name: "card-why",
  head: "Why reporters care",
  text: "It is the closest thing to a running police blotter for a campus — " +
    "assaults, thefts, drug and alcohol enforcement, and how each was resolved.",
});
card(s, {
  x: 8.1, y: BODY_TOP + 2.25, w: 4.53, h: 2.05, fill: MIST, name: "card-catch",
  head: "And the catch",
  headColor: VERM,
  text: "The law says publish it. It does not say keep what you published, " +
    "or note when you change your mind.",
});
s.addNotes("Keep this slide short — it is context, not the argument.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Opening" });
chip(s, "03  HOW IT IS PUBLISHED");
s.addText("Rowan publishes it as a Google Sheet", { placeholder: "title" });
const howCards = [
  ["One sheet per month", "A new file each month, linked from a Drive folder."],
  ["Typed by hand", "Same offense, different spelling, month to month."],
  ["Edited in place", "Dispositions and times get revised after publication."],
  ["No history", "Nothing on the page says a row ever changed."],
];
howCards.forEach(([head, text], i) => {
  card(s, {
    x: M + i * 3.03, y: BODY_TOP, w: 2.83, h: 2.3, fill: MIST,
    name: `how-${i}`, num: i + 1, accent: i === 3 ? VERM : TEAL,
    head, text, headSize: 15, textSize: 13,
  });
});
terminal(
  s,
  [
    { text: "# what a \"publication\" actually is", color: GREY },
    "docs.google.com/spreadsheets/d/<id>/export?format=csv",
  ],
  { x: M, y: 4.75, w: W, fill: INK, name: "term-url", fontSize: 13 }
);
s.addText(
  "That URL is the whole dependency. It is also the thing that returned 401.",
  { x: M, y: 6.05, w: W, h: 0.5, fontSize: 15, color: SLATE, italic: true,
    isTextBox: true, margin: 0, objectName: "note-url" }
);
s.addNotes("The export URL is worth showing — most people don't know a Sheet has one.");

s = pres.addSlide({ masterName: "STAT_DARK", sectionTitle: "Opening" });
chip(s, "04  THE PROBLEM", { fill: VERM });
s.addText("A public record you cannot cite", { placeholder: "title" });
stat(s, { x: M, y: 2.3, w: 3.7, value: F.amended, color: AMBER_L,
  label: "rows the university revised after publishing them — new dispositions, " +
    "changed times, reclassified offenses" });
stat(s, { x: 4.75, y: 2.3, w: 3.7, value: F.sourceRemoved, color: VERM,
  label: "rows whose source file stopped being shared, now preserved only in this archive" });
stat(s, { x: 8.9, y: 2.3, w: 3.7, value: "0", color: GREY_L,
  label: "of those changes appear anywhere on Rowan's own pages" });
s.addText(
  "If you quote a figure today and the sheet reads differently next month, " +
    "you have no way to show you were right.",
  { x: M, y: 5.05, w: 11.2, h: 0.9, fontSize: 19, bold: true, color: PAPER,
    isTextBox: true, margin: 0, objectName: "thesis" }
);
s.addNotes(
  "This is the thesis slide. Everything after it is in service of being able to say: " +
    "here is what the record said on this date, and here is what it says now."
);

// ================================================================================
// SECTION 2 — what we built
// ================================================================================
pres.addSection({ title: "What we built" });

s = pres.addSlide({ masterName: "SECTION_DARK", sectionTitle: "What we built" });
chip(s, "PART ONE", { y: 2.45, fill: TEAL });
s.addText("An archive that remembers", { placeholder: "title" });
s.addText(
  `${F.archiveTotal} incidents · ${F.rangeStart} to ${F.rangeEnd} · checked twice a day · ` +
    "every version kept",
  { placeholder: "body" }
);
s.addNotes("Transition: so what do you actually build to fix that?");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "What we built" });
chip(s, "05  ARCHITECTURE");
s.addText("Four layers, and only one of them is allowed to change", {
  placeholder: "title",
});
const layers = [
  ["Raw", "The bytes, exactly as downloaded, in a dated file.", "Never edited", TEAL],
  ["Archive", "One row per incident, with every revision recorded.", "Append only", DEEP],
  ["Derived", "Categories, counts, lags — rebuilt from scratch each run.", "Disposable", SLATE],
  ["Site", "The pages people read.", "Disposable", SLATE],
];
layers.forEach(([name, desc, rule, accent], i) => {
  const x = M + i * 3.03;
  card(s, { x, y: BODY_TOP, w: 2.83, h: 2.55, fill: MIST, name: `layer-${i}`,
    head: name, text: desc, headSize: 18, textSize: 13, textH: 1.1 });
  slideBadge(s, rule, x + 0.3, BODY_TOP + 2.0, accent, `layer-rule-${i}`);
  if (i < 3) {
    s.addText("→", { x: x + 2.76, y: BODY_TOP + 0.9, w: 0.34, h: 0.4, fontSize: 16,
      color: GREY, align: "center", isTextBox: true, margin: 0,
      objectName: `arrow-${i}` });
  }
});
s.addText(
  "The rule that makes it an archive rather than a scraper: if the derived layers burn " +
    "down, you rebuild them from raw. If raw burns down, the record is gone.",
  { x: M, y: 5.2, w: W, h: 0.85, fontSize: 16, color: SLATE, isTextBox: true,
    margin: 0, objectName: "note-layers" }
);
s.addNotes(
  "This is the single most portable idea in the talk. It applies to any scrape: " +
    "keep the bytes, derive everything else."
);

function slideBadge(slide, text, x, y, color, name) {
  const w = Math.max(0.9, 0.085 * text.length + 0.3);
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 0.28, fill: { color }, rectRadius: 0.05, line: { type: "none" },
    objectName: `${name}-bg`,
  });
  slide.addText(text.toUpperCase(), {
    x, y, w, h: 0.28, fontSize: 9, bold: true, fontFace: MONO, color: PAPER,
    align: "center", valign: "middle", charSpacing: 0.6, isTextBox: true, margin: 0,
    objectName: name,
  });
}

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "What we built" });
chip(s, "06  THE OUTPUT");
s.addText("What a reader gets", { placeholder: "title" });
card(s, { x: M, y: BODY_TOP, w: 5.8, h: 2.1, fill: MIST, name: "out-1",
  head: "A site that explains itself",
  text: "Charts by month, category and location — plus a page listing every change " +
    "the archive has caught, with the old value beside the new one." });
card(s, { x: M, y: BODY_TOP + 2.3, w: 5.8, h: 2.1, fill: MIST, name: "out-2",
  head: "Data you can take away",
  text: "Every chart exports the exact rows behind it as CSV, so a reader can check " +
    "the number rather than trust it." });
terminal(
  s,
  [
    { text: "# one commit per run, change or no change", color: GREY },
    "data: +31 added, 0 amended, 0 missing,",
    "      0 withdrawn, 0 source-removed — 2026-10-09",
    "",
    { text: "# and the receipts underneath", color: GREY },
    "data/raw/<sheet-id>/2026-10-09.csv",
  ],
  { x: 6.95, y: BODY_TOP, w: 5.68, h: 4.4, fill: INK, name: "term-commit", fontSize: 12.5 }
);
s.addNotes(
  "Show the live site here if the wifi holds; otherwise this slide stands in for it."
);

// ================================================================================
// SECTION 3 — the tools
// ================================================================================
pres.addSection({ title: "The tools" });

s = pres.addSlide({ masterName: "SECTION_DARK", sectionTitle: "The tools" });
chip(s, "PART TWO", { y: 2.45, fill: TEAL });
s.addText("Three tools, no computer science degree", { placeholder: "title" });
s.addText(
  "A terminal, Claude Code, and GitHub. Each one earns its place the moment you " +
    "actually need it — so that is the order we will meet them in.",
  { placeholder: "body" }
);
s.addNotes("Reassure the room. Nobody here needs to become an engineer.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The tools" });
chip(s, "07  THE TERMINAL");
s.addText("The terminal is a text conversation with your computer", {
  placeholder: "title",
});
bullets(s, [
  "You type an instruction, press enter, and it answers. That is the whole interface.",
  "It is already on your machine: Terminal on a Mac, PowerShell on Windows.",
  "Why bother, when you could click? Because a command is a thing you can write " +
    "down, hand to a colleague, and run again next year. A click is not.",
  "That is the same reason we prefer a script to a spreadsheet: it can be re-run, " +
    "and so it can be checked.",
], { override: { w: 7.1, fontSize: 16 } });
terminal(
  s,
  [
    { text: "$ cd Documents/rowan-clery", color: TEAL_L },
    "$ ls",
    "config/  data/  docs/  rowan_clery/  tests/",
    { text: "$ python run.py build", color: TEAL_L },
    "built page data: 267 archived,",
    "  253 published, 14 no longer published",
  ],
  { x: 8.1, y: BODY_TOP, w: 4.53, h: 2.6, fill: INK, name: "term-intro", fontSize: 11.5 }
);
s.addText(
  "Reproducibility is a journalistic standard, not an engineering one.",
  { x: 8.1, y: 4.85, w: 4.53, h: 0.8, fontSize: 15, italic: true, color: SLATE,
    isTextBox: true, margin: 0, objectName: "note-repro" }
);
s.addNotes(
  "If anyone looks frightened, say: you will use four commands, and Claude Code will " +
    "tell you which one."
);

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The tools" });
chip(s, "08  DAY ONE");
s.addText("The commands you actually need on day one", { placeholder: "title" });
terminal(
  s,
  [
    { text: "cd rowan-clery", bold: true, color: TEAL_L },
    { text: "    move into the project folder", color: GREY },
    "",
    { text: "ls", bold: true, color: TEAL_L },
    { text: "    what is in here?", color: GREY },
    "",
    { text: "python run.py all", bold: true, color: TEAL_L },
    { text: "    fetch, archive, rebuild the site", color: GREY },
    "",
    { text: "git log --oneline -5", bold: true, color: TEAL_L },
    { text: "    what changed recently?", color: GREY },
  ],
  { x: M, y: BODY_TOP, w: 7.1, h: 4.35, fill: INK, name: "term-day1", fontSize: 13 }
);
card(s, { x: 8.4, y: BODY_TOP, w: 4.23, h: 1.95, fill: MIST, name: "d1-a",
  head: "Four commands",
  text: "That is the barrier to entry. Everything else in this project, " +
    "Claude Code wrote while I watched." });
card(s, { x: 8.4, y: BODY_TOP + 2.15, w: 4.23, h: 2.2, fill: PANEL, name: "d1-b",
  head: "The one habit",
  headColor: AMBER_L,
  text: "Read what it proposes before you say yes. You are the editor. " +
    "The tool is a very fast, very literal reporter." });
s.addNotes("Linger here. This slide is the one that makes people think they could try.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The tools" });
chip(s, "09  CLAUDE CODE");
s.addText("Claude Code lives in that terminal", { placeholder: "title" });
bullets(s, [
  "It reads and writes the files in your project, runs commands, reads the errors " +
    "that come back, and fixes them.",
  "It asks before it changes anything or runs something consequential.",
  "It can see the whole project at once — which is why it finds every instance of a " +
    "problem rather than the first one.",
  "It costs money per use. Budget for it like a database subscription, not like a " +
    "free plugin.",
], { override: { w: 7.1, fontSize: 16 } });
terminal(
  s,
  [
    { text: "$ claude", color: TEAL_L },
    "",
    { text: "> the scheduled run failed overnight.", color: PAPER },
    { text: "  here is the error. can you", color: PAPER },
    { text: "  investigate?", color: PAPER },
    "",
    { text: "  [pasted log]", color: GREY },
  ],
  { x: 8.1, y: BODY_TOP, w: 4.53, h: 2.75, fill: INK, name: "term-cc", fontSize: 12 }
);
s.addText(
  "That prompt is a real one. It is also the entire workflow.",
  { x: 8.1, y: 5.0, w: 4.53, h: 0.7, fontSize: 15, italic: true, color: SLATE,
    isTextBox: true, margin: 0, objectName: "note-cc" }
);
s.addNotes("Be honest about cost. Newsroom budgets are the first objection you'll get.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The tools" });
chip(s, "10  THE LOOP");
s.addText("What the loop actually looks like", { placeholder: "title" });
terminal(
  s,
  [
    { text: "MappingError: Unmapped Nature token(s):", color: VERM },
    { text: "  ['Possession of open container CDS", color: VERM },
    { text: "   (prohibited drug) in vehicle']", color: VERM },
  ],
  { x: M, y: BODY_TOP, w: 5.79, h: 1.25, fill: PANEL, name: "term-maperr", fontSize: 12.5 }
);
const loop = [
  ["The robot stops", "A wording the project has never seen takes the run down. Nothing is published."],
  ["I paste the error in", "No diagnosis of my own. Just the log."],
  ["It checks everything", "Scans all four live sheets for every unknown wording — not only the one reported."],
  ["It proves the fix", "Writes a failing test, adds the mapping, shows the test passing."],
];
loop.forEach(([head, text], i) => {
  card(s, { x: M + (i % 2) * 6.14, y: 3.55 + Math.floor(i / 2) * 1.6, w: 5.79, h: 1.45,
    fill: MIST, name: `loop-${i}`, num: i + 1, accent: i === 0 ? VERM : TEAL,
    head, text, headSize: 15, textSize: 13 });
});
card(s, { x: 6.84, y: BODY_TOP, w: 5.79, h: 1.25, fill: MIST, name: "loop-note",
  head: "Ten minutes, start to finish", headSize: 15,
  text: "The judgment took longer than the code.", textSize: 13 });
s.addNotes(
  "Step 3 is the one worth dwelling on — the first run of this talk's example reported " +
    "one unknown wording and there were four."
);

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The tools" });
chip(s, "11  THE SHIFT");
s.addText("The mental shift that matters", { placeholder: "title" });
card(s, { x: M, y: BODY_TOP, w: 5.8, h: 3.9, fill: MIST, name: "shift-a",
  head: "Not this", headColor: VERM, headSize: 18,
  text: "“Write me a scraper for this crime log.”\n\n" +
    "You get something that works today, makes a hundred silent decisions, " +
    "and you cannot defend any of them." });
card(s, { x: 7.25, y: BODY_TOP, w: 5.38, h: 3.9, fill: PANEL, name: "shift-b",
  head: "This", headColor: TEAL_L, headSize: 18,
  text: "“The occurred-date column sometimes just says Unknown. " +
    "Never guess a month from one. Count those rows separately and " +
    "put the number on the page.”\n\n" +
    "You supply the editorial judgment. It supplies the typing." });
s.addText(
  "You are not short of code. You are short of someone to argue with about " +
    "what the number means.",
  { x: M, y: 6.15, w: W, h: 0.5, fontSize: 16, italic: true, color: SLATE,
    isTextBox: true, margin: 0, objectName: "note-shift" }
);
s.addNotes("The second quote is close to a real prompt from this project.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The tools" });
chip(s, "12  GITHUB");
s.addText("GitHub does two jobs here", { placeholder: "title" });
card(s, { x: M, y: BODY_TOP, w: 5.8, h: 2.45, fill: MIST, name: "gh-1", num: 1,
  accent: DEEP, head: "A public, timestamped audit trail",
  text: `${F.commits} commits so far. Each is a dated receipt saying what the archive ` +
    "looked like at that moment. Anyone can check your work against it — including " +
    "the institution you are writing about." });
card(s, { x: 7.25, y: BODY_TOP, w: 5.38, h: 2.45, fill: MIST, name: "gh-2", num: 2,
  accent: TEAL, head: "A free robot",
  text: "GitHub Actions runs the whole pipeline twice a day on someone else's " +
    "computer. Your laptop can be shut. This costs nothing for a public repository." });
card(s, { x: M, y: BODY_TOP + 2.65, w: 11.93, h: 1.6, fill: PANEL, name: "gh-3",
  head: "The part people miss", headColor: AMBER_L, headSize: 16,
  text: "Publishing the archive publicly is itself an editorial act. It means the " +
    "record survives you losing interest, changing jobs, or losing a laptop." });
s.addNotes("Mention that a private repo works too, but then you are the single point of failure.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The tools" });
chip(s, "13  GIT");
s.addText("Git, in one idea", { placeholder: "title" });
s.addText("A commit is a labeled snapshot you can always go back to", {
  x: M, y: BODY_TOP, w: W, h: 0.7, fontSize: 24, bold: true, color: INK,
  isTextBox: true, margin: 0, objectName: "git-idea",
});
terminal(
  s,
  [
    { text: "$ git log --oneline -4", color: TEAL_L },
    "6b3bb0f New category",
    "4e37154 data: +5 added, 4 amended, 1 missing — 2026-10-15",
    "a4460ca update mapping",
    "1c8dabc data: +0 added, 0 amended, 0 missing — 2026-10-12",
  ],
  { x: M, y: 3.0, w: 11.93, h: 2.05, fill: INK, name: "term-git", fontSize: 12.5 }
);
s.addText(
  "The robot writes one of these every run, change or no change — so the log itself " +
    "becomes the audit trail. A quiet day is evidence too.",
  { x: M, y: 5.3, w: 11.93, h: 0.85, fontSize: 16, color: SLATE, isTextBox: true,
    margin: 0, objectName: "note-git" }
);
s.addNotes(
  "You do not need branches, merges or pull requests to do this work. " +
    "One branch and honest commit messages is plenty."
);

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The tools" });
chip(s, "14  AUTOMATION");
s.addText("Cron with receipts", { placeholder: "title" });
terminal(
  s,
  [
    { text: "# .github/workflows/daily.yml", color: GREY },
    "on:",
    "  schedule:",
    { text: "    - cron: \"17 9 * * *\"", color: TEAL_L },
    { text: "    - cron: \"17 21 * * *\"", color: TEAL_L },
  ],
  { x: M, y: BODY_TOP, w: 6.1, h: 1.95, fill: INK, name: "term-cron", fontSize: 13 }
);
card(s, { x: 7.35, y: BODY_TOP, w: 5.28, h: 1.95, fill: MIST, name: "cron-a",
  head: "Why twice", headSize: 16,
  text: "Scheduled runs on free infrastructure get delayed and sometimes skipped " +
    "entirely. The second run is cheap insurance.", textSize: 13 });
card(s, { x: M, y: 4.35, w: 6.1, h: 1.85, fill: MIST, name: "cron-b",
  head: "Why an odd minute", headSize: 16,
  text: "Everyone schedules on the hour. Queueing at :17 gets you served sooner.",
  textSize: 13 });
card(s, { x: 7.35, y: 4.35, w: 5.28, h: 1.85, fill: PANEL, name: "cron-c",
  head: "Why commit even when nothing changed", headColor: AMBER_L, headSize: 15,
  text: "GitHub switches off scheduled jobs after 60 days of no commits. A silent " +
    "scraper that has quietly stopped is worse than no scraper.", textSize: 13 });
s.addNotes(
  "That last card is a genuinely nasty trap and worth saying out loud — it would " +
    "have switched this project off during a quiet stretch."
);

// ================================================================================
// SECTION 4 — the decisions
// ================================================================================
pres.addSection({ title: "The decisions" });

s = pres.addSlide({ masterName: "SECTION_DARK", sectionTitle: "The decisions" });
chip(s, "PART THREE", { y: 2.45, fill: TEAL });
s.addText("The code was the easy part", { placeholder: "title" });
s.addText(
  "Five rules. Every one of them exists because the convenient shortcut would have " +
    "produced a number I could not defend in print.",
  { placeholder: "body" }
);
s.addNotes("This is the heart of the talk. Budget the most time here.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The decisions" });
chip(s, "RULE 1", { fill: TEAL });
s.addText("Raw capture is immutable", { placeholder: "title" });
const r1 = [
  ["Download", "Fetch the CSV exactly as the server sends it."],
  ["Write once", "Save the bytes to a dated file and never touch them again."],
  ["Verify", "A step in every run checks that raw was only added to, never modified."],
];
r1.forEach(([head, text], i) => {
  card(s, { x: M + i * 4.03, y: BODY_TOP, w: 3.83, h: 2.1, fill: MIST,
    name: `r1-${i}`, num: i + 1, accent: TEAL, head, text, headSize: 16, textSize: 13 });
});
stat(s, { x: M, y: 4.55, w: 3.3, value: F.snapshots, color: TEAL, size: 52,
  label: "dated snapshots on disk", labelColor: SLATE, vh: 0.9 });
s.addText(
  "Every transformation produces a new file. If a category turns out to be wrong, " +
    "you re-derive from raw — you do not repair the archive and hope nobody asks.",
  { x: 4.4, y: 4.65, w: 8.23, h: 1.4, fontSize: 16, color: SLATE, isTextBox: true,
    margin: 0, objectName: "note-r1", lineSpacingMultiple: 1.2 }
);
s.addNotes("Raw data is immutable is the oldest rule in data journalism. It still holds.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The decisions" });
chip(s, "RULE 2", { fill: TEAL });
s.addText("Nothing is ever deleted", { placeholder: "title" });
stat(s, { x: M, y: BODY_TOP, w: 3.5, value: F.added, color: DEEP, size: 54,
  label: "incidents added", labelColor: SLATE, vh: 0.95, lh: 0.5 });
stat(s, { x: 4.9, y: BODY_TOP, w: 3.5, value: F.amended, color: AMBER, size: 54,
  label: "revised after publication", labelColor: SLATE, vh: 0.95, lh: 0.5 });
stat(s, { x: 9.1, y: BODY_TOP, w: 3.5, value: F.sourceRemoved, color: VERM, size: 54,
  label: "whose source stopped being shared", labelColor: SLATE, vh: 0.95, lh: 0.5 });
card(s, { x: M, y: 4.05, w: 5.8, h: 2.15, fill: MIST, name: "r2-a",
  head: "A row that vanishes is marked, not removed",
  text: "It keeps its place, with a flag saying the source stopped listing it and " +
    "the date that happened." });
card(s, { x: 7.25, y: 4.05, w: 5.38, h: 2.15, fill: PANEL, name: "r2-b",
  head: "And only after three strikes", headColor: AMBER_L,
  text: "Live sheets get edited mid-day. A row missing once is usually a typo in " +
    "progress — so it takes three consecutive runs to call it gone." });
s.addNotes(
  "The three-strike ladder came from observation: a row went missing at 9am and was " +
    "back by mid-afternoon."
);

s = pres.addSlide({ masterName: "STAT_DARK", sectionTitle: "The decisions" });
chip(s, "RULE 3", { fill: VERM });
s.addText("Fail loudly", { placeholder: "title" });
terminal(
  s,
  [
    { text: "MappingError: Unmapped Nature token(s):", color: VERM },
    { text: "  ['Offensive Language']", color: VERM },
    "",
    { text: "Add them to config/category_map.csv with a role", color: MIST },
    { text: "and categories. Refusing to guess, because a wrong", color: MIST },
    { text: "guess silently undercounts a category.", color: MIST },
  ],
  { x: M, y: 2.2, w: 11.93, h: 2.35, fill: PANEL, name: "term-fail", fontSize: 14 }
);
s.addText(
  "An offense wording the project has never seen takes the entire build down. " +
    "On purpose.",
  { x: M, y: 4.85, w: 11.93, h: 0.6, fontSize: 20, bold: true, color: PAPER,
    isTextBox: true, margin: 0, objectName: "fail-caption" }
);
s.addText(
  "That message is written to the person who will read it at 7am — including the " +
    "reason, so the fix is not a guess either.",
  { x: M, y: 5.55, w: 11.93, h: 0.7, fontSize: 15, color: MIST, italic: true,
    isTextBox: true, margin: 0, objectName: "fail-note" }
);
s.addNotes("Read the error message aloud. It is the argument of the whole talk in three lines.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The decisions" });
chip(s, "RULE 3  ·  WHY");
s.addText("Why crashing is the right behaviour", { placeholder: "title" });
card(s, { x: M, y: BODY_TOP, w: 5.8, h: 3.4, fill: MIST, name: "why-a",
  head: "The convenient option", headColor: VERM, headSize: 18,
  text: "Put anything unrecognised in “Other”.\n\n" +
    "The build stays green. Nobody gets woken up. And you publish a crime category " +
    "that is quietly short by however many incidents used a new wording that month." });
card(s, { x: 7.25, y: BODY_TOP, w: 5.38, h: 3.4, fill: PANEL, name: "why-b",
  head: "The option we took", headColor: TEAL_L, headSize: 18,
  text: "Stop everything.\n\n" +
    "Nothing publishes until a human has looked at the wording and decided which " +
    "category it belongs in. The archive is never silently wrong." });
s.addText(
  "An undercount published as a finding is the failure that would embarrass a " +
    "reporter most. So it is the one the system is built to make impossible.",
  { x: M, y: 5.65, w: W, h: 0.9, fontSize: 17, bold: true, color: INK,
    isTextBox: true, margin: 0, objectName: "why-note" }
);
s.addNotes("If you take one idea home, take this one.");

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The decisions" });
chip(s, "RULE 3  ·  THE BILL");
s.addText("What that choice costs, honestly", { placeholder: "title" });
stat(s, { x: M, y: BODY_TOP, w: 3.5, value: "4", color: VERM, size: 56,
  label: "breakages in eight days, Oct. 9 to 16", labelColor: SLATE, vh: 0.95 });
stat(s, { x: 4.9, y: BODY_TOP, w: 3.5, value: F.natureTokens, color: DEEP, size: 56,
  label: `distinct wordings mapped by hand, into ${F.categories} categories`,
  labelColor: SLATE, vh: 0.95 });
stat(s, { x: 9.1, y: BODY_TOP, w: 3.5, value: "13", color: AMBER, size: 56,
  label: "spellings of “trespass notice” alone", labelColor: SLATE, vh: 0.95 });
card(s, { x: M, y: 4.45, w: 11.93, h: 1.75, fill: MIST, name: "bill",
  head: "This is the maintenance bill for not guessing",
  text: "Someone has to read the alarm and make a call, every few days. " +
    "If nobody in your newsroom will own that, build something simpler — " +
    "an unmaintained archive that fails silently is worse than none." });
s.addNotes(
  "Be straight about this. It is the main reason these projects die, and pretending " +
    "otherwise does the audience no favours."
);

s = pres.addSlide({ masterName: "CHART_LIGHT", sectionTitle: "The decisions" });
chip(s, "RULE 4", { fill: TEAL });
s.addText("The source lies in interesting ways", { placeholder: "title" });
s.addChart(
  pres.ChartType.bar,
  [
    {
      name: "Median days from incident to report",
      labels: ["Campus police", "Security authorities", "Glassboro PD"],
      values: [Number(F.rupdLag), Number(F.csaLag), Number(F.gpdLag)],
    },
  ],
  {
    placeholder: "chart",
    ...chartBase(),
    barDir: "bar",
    chartColors: [DEEP, GREY, VERM],
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelFormatCode: '0.0" days"',
    valAxisMaxVal: 17,
    barGapWidthPct: 55,
  }
);
s.addText(
  [
    { text: "One log, two very different clocks.\n", options: { bold: true, breakLine: true } },
    { text: `Campus police file ${F.rupdWithin24} of their reports within a day. ` +
        `Glassboro's borough police file ${F.gpdWithin24} within a day — their median ` +
        `is ${F.gpdLag}\u00A0days.\n`, options: { breakLine: true } },
    { text: "Nothing on the page tells you this. You only find it by measuring.",
      options: { italic: true } },
  ],
  { placeholder: "body" }
);
s.addNotes(
  "Measured over incidents where both timestamps are precise to the minute: " +
    "156 campus police, 83 Glassboro, 36 security authorities."
);

s = pres.addSlide({ masterName: "CHART_LIGHT", sectionTitle: "The decisions" });
chip(s, "RULE 4  ·  SO WHAT");
s.addText("“When” depends on which date you count", { placeholder: "title" });
s.addChart(
  pres.ChartType.bar,
  [
    { name: "By date reported", labels: F.monthLabels, values: F.reported },
    { name: "By date it happened", labels: F.monthLabels, values: F.occurred },
  ],
  {
    placeholder: "chart",
    ...chartBase(),
    barDir: "col",
    barGrouping: "clustered",
    chartColors: [GREY, TEAL],
    showValue: true,
    dataLabelPosition: "outEnd",
    showLegend: true,
    legendPos: "t",
    legendColor: SLATE,
    legendFontFace: "+mn-lt",
    legendFontSize: 11,
    valAxisMaxVal: 165,
    barGapWidthPct: 45,
  }
);
s.addText(
  [
    { text: "September: 109 reported, 144 happened.\n",
      options: { bold: true, breakLine: true } },
    { text: "October reads 28 and will keep climbing for weeks as Glassboro files.\n",
      options: { breakLine: true } },
    { text: "The site counts by when things happened, because that is the honest " +
        "answer to “when was there crime” — and says on the page that recent " +
        "months are incomplete.", options: {} },
  ],
  { placeholder: "body" }
);
s.addNotes(
  "This is the slide that shows why the choice of date column is editorial, not " +
    "technical. Both series are correct; they answer different questions."
);

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The decisions" });
chip(s, "RULE 5", { fill: TEAL });
s.addText("Tests are editorial infrastructure", { placeholder: "title" });
stat(s, { x: M, y: BODY_TOP, w: 2.9, value: F.tests, color: TEAL, size: 54,
  label: "automated checks", labelColor: SLATE, vh: 0.95, lh: 0.5 });
stat(s, { x: 4.3, y: BODY_TOP, w: 4.0, value: F.testLines, color: DEEP, size: 54,
  label: "lines of tests", labelColor: SLATE, vh: 0.95, lh: 0.5 });
stat(s, { x: 9.0, y: BODY_TOP, w: 3.6, value: F.pipeLines, color: GREY, size: 54,
  label: "lines of actual pipeline", labelColor: SLATE, vh: 0.95, lh: 0.5 });
const tests = [
  ["One runs the page in a fake browser",
    "A JavaScript typo ships a page that returns 200 with every chart silently empty. That happened twice."],
  ["One checks the caveat's arithmetic",
    "Every incident must be either on the chart or counted in the note saying what is missing."],
  ["One refuses to let a number drift",
    "Change the data a test is pinned to, and you must state the new figure deliberately."],
];
tests.forEach(([head, text], i) => {
  card(s, { x: M + i * 4.03, y: 4.0, w: 3.83, h: 2.2, fill: MIST, name: `t-${i}`,
    head, text, headSize: 14, textSize: 12.5 });
});
s.addNotes(
  "Tests in a newsroom are not engineering hygiene. They are the thing that stops you " +
    "publishing a chart with no data in it."
);

// ================================================================================
// SECTION 5 — what to steal
// ================================================================================
pres.addSection({ title: "What to steal" });

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "What to steal" });
chip(s, "15  THE DIVISION OF LABOUR");
s.addText("What the tool did, and what it could not", { placeholder: "title" });
card(s, { x: M, y: BODY_TOP, w: 5.8, h: 3.2, fill: MIST, name: "lab-a",
  head: "Claude Code was good at", headColor: TEAL, headSize: 17,
  text: "The boilerplate. The tests. The documentation. Reading a stack trace. " +
    "Finding every instance of a problem instead of the first one. " +
    "Explaining its own reasoning well enough to argue with." });
card(s, { x: 7.25, y: BODY_TOP, w: 5.38, h: 3.2, fill: PANEL, name: "lab-b",
  head: "It could not decide", headColor: AMBER_L, headSize: 17,
  text: "A new wording arrived: “Possession of open container CDS " +
    "(prohibited drug) in vehicle.”\n\n" +
    "It reads like the alcohol open-container rule. CDS means controlled dangerous " +
    "substance — a drug offense." });
s.addText(
  "File it as alcohol and you inflate one crime category while undercounting another. " +
    "No tool knows which you meant. That is your job, and it is the actual work.",
  { x: M, y: 5.5, w: W, h: 0.95, fontSize: 17, bold: true, color: INK,
    isTextBox: true, margin: 0, objectName: "lab-note" }
);
s.addNotes(
  "Good closing beat for the tools section: the machine removed the typing, " +
    "not the judgment."
);

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "What to steal" });
chip(s, "16  YOUR BEAT");
s.addText("Pick a record worth preserving", { placeholder: "title" });
const criteria = [
  ["Already public", "No FOIA, no login. If you have to fight for it, that is a different project."],
  ["Overwritten in place", "The current version replaces the last one, and nothing keeps the old."],
  ["Consequential", "Someone would care if the numbers changed quietly."],
];
criteria.forEach(([head, text], i) => {
  card(s, { x: M + i * 4.03, y: BODY_TOP, w: 3.83, h: 2.0, fill: MIST,
    name: `crit-${i}`, num: i + 1, accent: TEAL, head, text, headSize: 16, textSize: 13 });
});
card(s, { x: M, y: 4.35, w: 11.93, h: 1.85, fill: PANEL, name: "examples",
  head: "Records that fit, in most states", headColor: PAPER, headSize: 16,
  text: "Restaurant inspection scores  ·  jail rosters and daily booking logs  ·  " +
    "school board agendas and minutes  ·  building permits and code violations  ·  " +
    "campus crime logs  ·  lobbyist registries  ·  water quality notices  ·  " +
    "nursing home inspection results", textColor: MIST, textSize: 14 });
s.addNotes(
  "Invite the room to name one from their own beat. Jail rosters are the usual " +
    "lightbulb — they change hourly and nobody keeps yesterday's."
);

s = pres.addSlide({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "What to steal" });
chip(s, "17  START");
s.addText("How to start this week", { placeholder: "title" });
const steps = [
  ["Find the URL that holds the data today", "The export link behind the page. Often a CSV or JSON you can see in your browser."],
  ["Save it to a dated file", "That is an archive. You have already done the irreplaceable part."],
  ["Put it on GitHub", "That is an audit trail, and it outlives your laptop."],
  ["Add a schedule", "Now it is a scraper, and it runs without you."],
  ["Only then make it look nice", "Charts are the last 10% and the first thing people want to build."],
];
steps.forEach(([head, text], i) => {
  const y = BODY_TOP + i * 0.92;
  slideNumBadge(s, i + 1, M, y);
  s.addText(head, { x: M + 0.62, y, w: 4.85, h: 0.6, fontSize: 16, bold: true,
    color: INK, valign: "middle", isTextBox: true, margin: 0, objectName: `step-h-${i}` });
  s.addText(text, { x: 6.3, y, w: 6.33, h: 0.6, fontSize: 13.5, color: SLATE,
    valign: "middle", isTextBox: true, margin: 0, objectName: `step-t-${i}` });
});
s.addText(
  "Steps one to three are an afternoon. Everything after that is optional.",
  { x: M, y: 6.42, w: W, h: 0.42, fontSize: 16, bold: true, italic: true, color: TEAL,
    isTextBox: true, margin: 0, objectName: "note-steps" }
);
s.addNotes("End on how small step one is. The archive starts the day you save one file.");

function slideNumBadge(slide, n, x, y) {
  slide.addShape(pres.ShapeType.ellipse, {
    x, y: y + 0.03, w: 0.38, h: 0.38, fill: { color: TEAL_L }, line: { type: "none" },
    objectName: `stepnum-bg-${n}`,
  });
  slide.addText(String(n), {
    x, y: y + 0.03, w: 0.38, h: 0.38, fontSize: 13, bold: true, color: PAPER,
    align: "center", valign: "middle", isTextBox: true, margin: 0,
    objectName: `stepnum-${n}`,
  });
}

s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "What to steal" });
chip(s, "TAKE IT APART", { y: 1.75, fill: TEAL });
s.addText("The archive is the story", { placeholder: "title" });
s.addText(
  "The site is just how you read it. Everything here is public — the code, " +
    "the raw snapshots, the methodology, and every change the archive has caught.",
  { placeholder: "body" }
);
terminal(
  s,
  [
    { text: "github.com/sstirling/rowan-clery", color: TEAL_L, bold: true },
    "  METHODOLOGY.md   what counts, and what does not",
    "  data/raw/        every byte, exactly as downloaded",
  ],
  { x: M, y: 5.72, w: 9.4, h: 1.22, fill: PANEL, name: "term-close", fontSize: 11.5 }
);
s.addNotes(
  "Offer to help anyone who wants to try it on their own beat. " +
    `Figures on these slides were measured on ${AS_OF}.`
);

// ---- write ---------------------------------------------------------------------
(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log(`wrote ${OUT}`);
})();

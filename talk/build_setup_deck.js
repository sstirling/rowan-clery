/**
 * "Four commands and a folder" — an 18-slide walkthrough for college students who have
 * never opened a terminal, used git or run Claude Code.
 *
 * The deck teaches exactly one skill: open a terminal, get to the folder where your
 * repos live, and start Claude Code there. Everything else is cut.
 *
 * Install commands, keyboard shortcuts, error strings and account requirements were
 * taken from code.claude.com/docs on 2026-10-19 (setup, quickstart, terminal-guide).
 * They change: re-check those three pages before presenting.
 *
 * Fonts are Georgia / Arial / Courier New. All three ship with both macOS and
 * Microsoft Office, so the deck renders the same on a presenter's laptop as it does here.
 *
 * Build:  node build_setup_deck.js
 */

const pptxgen = require("pptxgenjs");
const path = require("path");
const { applyTheme } = require(path.join(
  process.env.SKILL_DIR || ".",
  "scripts/apply_theme.js"
));

const OUT = process.env.OUT_PPTX || "four-commands-and-a-folder.pptx";

// ---- palette -------------------------------------------------------------------
// Ink dominates: the terminal pane is the subject, so it carries most of the visual
// weight on most slides. Ochre marks the one thing to type; blue marks anything that
// lives on github.com rather than on your laptop; green is output that worked.
const INK = "12191C";
const PANEL = "1E292F";
const PAPER = "FFFFFF";
const MIST = "EDF1F2";
const SLATE = "33444D";
const OCHRE = "9E5E0D";      // on light grounds
const OCHRE_L = "E5A24A";    // on the ink panes only
const BLUE = "1F5B7A";
const BLUE_L = "6FB2D6";
const GREEN = "2C6E49";
const GREEN_L = "73BF95";
const GREY = "5E6E78";
const GREY_L = "9FAEB7";

const THEME = {
  name: "Terminal Basics",
  headFontFace: "Georgia",
  bodyFontFace: "Arial",
  colors: {
    dk1: INK, lt1: PAPER, dk2: SLATE, lt2: MIST,
    accent1: OCHRE, accent2: BLUE, accent3: GREEN, accent4: GREY,
    accent5: PANEL, accent6: MIST, hlink: BLUE, folHlink: GREY,
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 — before any slide is added
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Stephen Stirling";
pres.title = "Four commands and a folder";
pres.subject = "Getting set up with the terminal, GitHub and Claude Code";

const C = pres.SchemeColor;
const MONO = "Courier New";

// ---- geometry ------------------------------------------------------------------
const M = 0.7;
const W = 13.333 - M * 2; // 11.933
const BODY_TOP = 2.05;
const BODY_BOT = 6.75;

// ---- layouts -------------------------------------------------------------------
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", margin: 0, x: M, y: 2.0,
        w: W, h: 2.0, fontSize: 54, bold: true, color: C.background1, align: "left",
        valign: "bottom" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", margin: 0, x: M, y: 4.2,
        w: 9.6, h: 1.2, fontSize: 19, color: C.background2, valign: "top",
        lineSpacingMultiple: 1.2 }, text: "" } },
  ],
});

const lightTitle = {
  options: { name: "title", type: "title", margin: 0, x: M, y: 0.88, w: W, h: 0.95,
    fontSize: 33, bold: true, color: C.text1, align: "left", valign: "middle" },
  text: "",
};
const lightFooter = [
  { text: { text: "Four commands and a folder", options: { x: M, y: 6.98, w: 6, h: 0.3,
      fontSize: 10, color: C.accent4, isTextBox: true, margin: 0 } } },
  { placeholder: { options: { name: "slideNum", type: "sldNum", x: 12.35, y: 6.98,
      w: 0.6, h: 0.3, fontSize: 10, color: C.accent4, align: "right" }, text: "" } },
];

pres.defineSlideMaster({
  title: "CONTENT_LIGHT",
  background: { color: C.background1 },
  objects: [
    { placeholder: lightTitle },
    { placeholder: { options: { name: "body", type: "body", margin: 0, x: M, y: BODY_TOP,
        w: W, h: 4.6, fontSize: 16, color: C.text2, valign: "top" }, text: "" } },
    ...lightFooter,
  ],
});

pres.defineSlideMaster({
  title: "TITLE_ONLY_LIGHT",
  background: { color: C.background1 },
  objects: [{ placeholder: lightTitle }, ...lightFooter],
});

pres.defineSlideMaster({
  title: "TITLE_ONLY_DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", margin: 0, x: M, y: 0.88,
        w: W, h: 0.95, fontSize: 33, bold: true, color: C.background1, align: "left",
        valign: "middle" }, text: "" } },
    { placeholder: { options: { name: "slideNum", type: "sldNum", x: 12.35, y: 6.98,
        w: 0.6, h: 0.3, fontSize: 10, color: C.accent4, align: "right" }, text: "" } },
  ],
});

// ---- composition helpers -------------------------------------------------------

/** A monospace kicker chip — the deck's one repeated motif. */
function chip(slide, text, opts = {}) {
  const x = opts.x ?? M;
  const y = opts.y ?? 0.5;
  const fill = opts.fill ?? OCHRE;
  const color = opts.color ?? PAPER;
  const w = opts.w ?? Math.max(1.0, 0.1 * text.length + 0.36);
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 0.3, fill: { color: fill }, rectRadius: 0.05,
    line: { type: "none" }, objectName: `chip-bg-${text.slice(0, 14)}`,
  });
  slide.addText(text, {
    x, y, w, h: 0.3, fontSize: 10, bold: true, fontFace: MONO, color,
    align: "center", valign: "middle", charSpacing: 1, isTextBox: true, margin: 0,
    objectName: `chip-${text.slice(0, 14)}`,
  });
}

/**
 * A terminal pane. Each line is {text, color, bold} or a bare string.
 * Lines are monospace on ink, which is how the students will actually see them.
 */
function terminal(slide, lines, o) {
  const fs = o.fontSize ?? 14;
  const lineH = (l) => (l.size ?? fs) * 0.017; // fontSize * 1.22 / 72, in inches
  const h = o.h ?? lines.reduce((t, l) => t + lineH(l), 0) + 0.36;
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h, fill: { color: o.fill ?? INK }, rectRadius: 0.035,
    line: { type: "none" },
    shadow: { type: "outer", color: "000000", blur: 10, offset: 2, angle: 90, opacity: 0.18 },
    objectName: o.name ?? "terminal",
  });
  slide.addText(
    lines.map((l, i) => ({
      text: l.text ?? l,
      options: {
        fontSize: l.size ?? fs, fontFace: MONO,
        color: l.color ?? (o.color ?? MIST),
        bold: !!l.bold,
        breakLine: i !== lines.length - 1,
      },
    })),
    { x: o.x + 0.28, y: o.y + 0.2, w: o.w - 0.56, h: h - 0.4, valign: "top",
      isTextBox: true, margin: 0, lineSpacingMultiple: 1.12,
      objectName: (o.name ?? "terminal") + "-text" }
  );
  return h;
}

/** A tinted card. Separated by fill and shadow, never by an edge stripe. */
function card(slide, o) {
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h, fill: { color: o.fill ?? MIST }, rectRadius: 0.035,
    line: { type: "none" },
    shadow: { type: "outer", color: "000000", blur: 8, offset: 1, angle: 90, opacity: 0.10 },
    objectName: o.name ?? "card",
  });
  const dark = o.fill === PANEL || o.fill === INK;
  let y = o.y + 0.22;
  if (o.num != null) {
    slide.addShape(pres.ShapeType.ellipse, {
      x: o.x + 0.26, y, w: 0.42, h: 0.42, fill: { color: o.accent ?? OCHRE },
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
      x: tx, y: o.num != null ? y - 0.05 : y, w: tw, h: o.headH ?? 0.44,
      fontSize: o.headSize ?? 16, bold: true,
      fontFace: o.headMono ? MONO : undefined,
      color: o.headColor ?? (dark ? PAPER : INK),
      valign: "middle", isTextBox: true, margin: 0,
      objectName: (o.name ?? "card") + "-head",
    });
    y += (o.headH ?? 0.44) + 0.02;
  }
  if (o.text) {
    slide.addText(o.text, {
      x: tx, y, w: tw, h: o.textH ?? (o.y + o.h - y - 0.16),
      fontSize: o.textSize ?? 14, color: o.textColor ?? (dark ? MIST : SLATE),
      valign: "top", isTextBox: true, margin: 0, lineSpacingMultiple: 1.18,
      objectName: (o.name ?? "card") + "-text",
    });
  }
}

/** A standalone caption under a pane. */
function caption(slide, text, o) {
  slide.addText(text, {
    x: o.x, y: o.y, w: o.w, h: o.h ?? 0.5, fontSize: o.fontSize ?? 15,
    color: o.color ?? SLATE, italic: !!o.italic, valign: "top", align: o.align ?? "left",
    isTextBox: true, margin: 0, lineSpacingMultiple: 1.18,
    objectName: o.name ?? "caption",
  });
}

/** A key-cap, for Cmd + Space and friends. */
function keycap(slide, label, o) {
  const w = o.w ?? Math.max(0.46, 0.092 * label.length + 0.3);
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w, h: 0.38, fill: { color: PAPER }, rectRadius: 0.06,
    line: { color: GREY_L, width: 1 },
    shadow: { type: "outer", color: "000000", blur: 3, offset: 1, angle: 90, opacity: 0.15 },
    objectName: `cap-bg-${label}`,
  });
  slide.addText(label, {
    x: o.x, y: o.y, w, h: 0.38, fontSize: 12, bold: true, color: INK,
    align: "center", valign: "middle", isTextBox: true, margin: 0,
    objectName: `cap-${label}`,
  });
  return w;
}

/** A row of key-caps joined by plus signs. Returns the total width drawn. */
function keyrow(slide, keys, o) {
  let x = o.x;
  keys.forEach((k, i) => {
    x += keycap(slide, k, { x, y: o.y }) + 0.06;
    if (i !== keys.length - 1) {
      slide.addText("+", { x, y: o.y, w: 0.22, h: 0.38, fontSize: 13, color: GREY,
        align: "center", valign: "middle", isTextBox: true, margin: 0,
        objectName: `plus-${o.name ?? ""}-${i}` });
      x += 0.26;
    }
  });
  return x - o.x;
}

function bullets(slide, items, o = {}) {
  slide.addText(
    items.map((t, i) => ({
      text: t,
      options: { bullet: { indent: 13 }, breakLine: i !== items.length - 1,
        paraSpaceAfter: o.gap ?? 10 },
    })),
    { x: o.x ?? M + 0.22, y: o.y ?? BODY_TOP, w: o.w ?? W - 0.22,
      h: o.h ?? BODY_BOT - BODY_TOP, fontSize: o.fontSize ?? 16,
      color: o.color ?? SLATE, valign: "top", isTextBox: true, margin: 0,
      objectName: o.name ?? "bullets" }
  );
}

// Declare each section the first time a slide claims it; a slide whose sectionTitle
// was never declared lands in a stray "Default-N" section instead.
let _section = null;
const S = (opts) => {
  if (opts.sectionTitle && opts.sectionTitle !== _section) {
    pres.addSection({ title: opts.sectionTitle });
    _section = opts.sectionTitle;
  }
  return pres.addSlide(opts);
};

// Prompt colouring used throughout: the path part in grey, what you type in ochre.
const typed = (t) => ({ text: t, color: OCHRE_L, bold: true });
const out = (t) => ({ text: t, color: MIST });
const dim = (t) => ({ text: t, color: GREY_L });
const ok = (t) => ({ text: t, color: GREEN_L });
const bad = (t) => ({ text: t, color: "E8766C" });
const blank = () => ({ text: " ", color: INK, size: 7 }); // a half-line of air

// =================================================================================
// 1. Title
// =================================================================================
{
  const s = S({ masterName: "TITLE_DARK", sectionTitle: "Start here" });
  chip(s, "~/Documents/GitHub", { y: 1.35, fill: OCHRE });
  s.addText("Four commands and a folder", { placeholder: "title" });
  s.addText(
    "Getting set up with the terminal, GitHub and Claude Code. " +
    "No prior experience assumed — we start by opening a window.",
    { placeholder: "body" }
  );
  terminal(s, [
    dim("laptop ~ % "), 
  ], { x: M, y: 5.75, w: 4.4, h: 0.62, fontSize: 14, name: "title-term" });
  caption(s, "That blinking cursor is the whole barrier. It goes away in about a minute.",
    { x: 5.35, y: 5.86, w: 7.2, color: GREY_L, fontSize: 14 });
  s.addNotes(
    "Set expectations in one sentence: by the end of this you will be able to open a " +
    "terminal, get to the folder where your projects live, and start Claude Code there.\n\n" +
    "That is genuinely the whole skill. Everything that feels intimidating about the " +
    "terminal is unfamiliarity, not difficulty — there are four commands in this deck " +
    "and you only need two of them most days.\n\n" +
    "Say up front what we are NOT doing: not learning to code, not learning git properly, " +
    "not configuring anything. Just getting to a working prompt."
  );
}

// =================================================================================
// 2. The end state
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Start here" });
  s.addText("Here is where we're going", { placeholder: "title" });
  terminal(s, [
    typed("laptop ~ % cd Documents/GitHub/rowan-clery"),
    typed("laptop rowan-clery % claude"),
    blank(),
    dim("  \u2726 Welcome to Claude Code"),
    dim("    cwd: /Users/you/Documents/GitHub/rowan-clery"),
    blank(),
    out("> what does this project do?"),
  ], { x: M, y: BODY_TOP, w: 7.5, fontSize: 15, name: "goal-term" });
  card(s, { x: 8.55, y: BODY_TOP, w: 4.08, h: 1.45, num: 1, accent: OCHRE,
    head: "Go to the folder", headSize: 15,
    text: "One command. The folder holds the project you want to work on.",
    textSize: 13, name: "goal-c1" });
  card(s, { x: 8.55, y: BODY_TOP + 1.57, w: 4.08, h: 1.45, num: 2, accent: OCHRE,
    head: "Type claude", headSize: 15, 
    text: "One word. It starts in that folder and reads the files there.",
    textSize: 13, name: "goal-c2" });
  card(s, { x: 8.55, y: BODY_TOP + 3.14, w: 4.08, h: 1.45, num: 3, accent: OCHRE,
    head: "Ask in plain English", headSize: 15,
    text: "No syntax to learn. Full sentences work better than keywords.",
    textSize: 13, name: "goal-c3" });
  caption(s, "Two commands, then a conversation. The rest of this deck is how to get here.",
    { x: M, y: 4.45, w: 7.5, fontSize: 15, italic: true, color: GREY });
  s.addNotes(
    "Show the destination before the journey, so every command that follows has an " +
    "obvious purpose.\n\n" +
    "Point at the two ochre lines: that is all the typing. One line moves you to a " +
    "folder, one line starts Claude Code. Everything after that is typed in English.\n\n" +
    "The 'cwd' line matters and we come back to it on slide 14: Claude Code works on the " +
    "folder you started it in. Starting in the right place is the single most important " +
    "habit in this deck."
  );
}

// =================================================================================
// 3. What the terminal is
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The terminal" });
  s.addText("A window where you type instead of click", { placeholder: "title" });
  card(s, { x: M, y: BODY_TOP, w: 5.82, h: 1.5, fill: MIST,
    head: "Finder, or File Explorer", 
    text: "You see your files as icons. You open a folder by double-clicking it. " +
          "You move a file by dragging it.", name: "t-gui" });
  card(s, { x: 7.22, y: BODY_TOP, w: 5.41, h: 1.5, fill: PANEL,
    head: "The terminal",
    text: "You see a line of text. You open a folder by naming it. " +
          "You move a file by saying where it goes.", name: "t-cli" });
  caption(s,
    "Same computer. Same files. The only difference is whether you point at them or " +
    "name them.", { x: M, y: 3.85, w: W, fontSize: 19, color: INK });
  card(s, { x: M, y: 4.6, w: W, h: 1.45, fill: MIST,
    head: "So why learn it at all?", headSize: 15,
    text: "Because the tools worth learning next — Claude Code, git, anything that runs " +
          "on a schedule — all live here. The terminal is the door, not the destination.",
    textSize: 14, name: "t-why" });
  s.addNotes(
    "The most useful thing you can do in the first two minutes is demystify this. The " +
    "terminal is not a different computer, not a hacker tool, not a place where mistakes " +
    "are irreversible. It is a text interface to the same files they already have.\n\n" +
    "The analogy that lands: Finder is pointing, the terminal is naming. If you can say " +
    "where something is, you can work in the terminal.\n\n" +
    "Be honest about the payoff. Nobody should learn the terminal for its own sake. They " +
    "are learning it because Claude Code runs there."
  );
}

// =================================================================================
// 4. Open one
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The terminal" });
  s.addText("Open one", { placeholder: "title" });

  card(s, { x: M, y: BODY_TOP, w: 5.82, h: 1.85, fill: MIST, head: "On a Mac",
    text: "", name: "o-mac" });
  keyrow(s, ["Cmd", "Space"], { x: M + 0.3, y: BODY_TOP + 0.82, name: "mac" });
  caption(s, "then type  Terminal  and press Return",
    { x: M + 0.3, y: BODY_TOP + 1.38, w: 5.2, fontSize: 14, color: SLATE });

  card(s, { x: 7.22, y: BODY_TOP, w: 5.41, h: 1.85, fill: MIST, head: "On Windows",
    text: "", name: "o-win" });
  keyrow(s, ["Win", "X"], { x: 7.52, y: BODY_TOP + 0.82, name: "win" });
  caption(s, "then choose  Windows PowerShell  or  Terminal",
    { x: 7.52, y: BODY_TOP + 1.38, w: 4.8, fontSize: 14, color: SLATE });

  terminal(s, [
    dim("Last login: Mon Oct 19 09:14:02"),
    dim("laptop ~ % "),
  ], { x: M, y: 4.4, w: 6.4, fontSize: 14, name: "o-term" });
  caption(s,
    "A window with a blinking cursor. Nothing is wrong — it is waiting for you.",
    { x: 7.22, y: 4.57, w: 5.41, fontSize: 15, color: SLATE });
  s.addNotes(
    "Do this live and slowly, and wait for the room to catch up. On a Mac, Spotlight is " +
    "the fastest route and the one they will remember.\n\n" +
    "On Windows, flag the PowerShell versus CMD distinction now, because it decides which " +
    "install command works on slide 13. PowerShell shows 'PS' at the start of the line; " +
    "CMD does not.\n\n" +
    "If anyone's window looks different — different colours, a '$' instead of a '%' — " +
    "that is fine and expected. Terminals are configurable and none of it changes what " +
    "we type."
  );
}

// =================================================================================
// 5. Reading the prompt
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "The terminal" });
  s.addText("Read the line before you type on it", { placeholder: "title" });
  terminal(s, [{ text: "laptop  ~  %", color: MIST, bold: true }],
    { x: M, y: BODY_TOP, w: W, h: 1.05, fontSize: 26, name: "p-term" });
  card(s, { x: M, y: 3.35, w: 3.84, h: 1.75, fill: MIST, head: "laptop", headMono: true,
    headSize: 17, text: "Which computer you are on. Yours will show your own name.",
    textSize: 14, name: "p-c1" });
  card(s, { x: 4.74, y: 3.35, w: 3.84, h: 1.75, fill: MIST, head: "~", headMono: true,
    headSize: 17, text: "The folder you are standing in right now. The ~ is shorthand " +
    "for your home folder.", textSize: 14, name: "p-c2" });
  card(s, { x: 8.79, y: 3.35, w: 3.84, h: 1.75, fill: MIST, head: "%", headMono: true,
    headSize: 17, text: "Your turn. Everything you type goes after this, and runs when " +
    "you press Return.", textSize: 14, name: "p-c3" });
  card(s, { x: M, y: 5.35, w: W, h: 1.35, fill: PANEL,
    head: "The middle part changes as you move, and that is the point", headSize: 15,
    text: "On Windows the same line reads PS C:\\Users\\you> — different punctuation, " +
          "identical job. Watch that folder name every time before you press Return.",
    textSize: 14, name: "p-note" });
  s.addNotes(
    "Spend a real minute here. Almost every beginner mistake in the terminal is running " +
    "a correct command in the wrong folder, and the prompt is already telling them which " +
    "folder they are in.\n\n" +
    "Have them look at their own prompt and read the three parts off it out loud.\n\n" +
    "The tilde is worth naming explicitly. It appears constantly in instructions online, " +
    "and nobody tells you it just means your home folder — /Users/yourname on a Mac."
  );
}

// =================================================================================
// 6. pwd
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Four commands" });
  chip(s, "command 1 of 4", { fill: GREY });
  s.addText("pwd — where am I?", { placeholder: "title" });
  terminal(s, [
    typed("laptop ~ % pwd"),
    ok("/Users/you"),
  ], { x: M, y: BODY_TOP, w: 7.5, fontSize: 17, name: "pwd-term" });
  card(s, { x: 8.55, y: BODY_TOP, w: 4.08, h: 1.4, fill: MIST,
    head: "Print working directory", headSize: 15,
    text: "Directory is the old word for folder.", textSize: 14, name: "pwd-c1" });
  caption(s,
    "It answers one question and changes nothing. When you are lost, this is the command.",
    { x: M, y: 3.25, w: 7.5, fontSize: 16, color: SLATE });
  card(s, { x: M, y: 4.1, w: W, h: 1.5, fill: MIST,
    head: "A path is just a set of nested folders, read left to right", headSize: 15,
    text: "/Users/you/Documents/GitHub  means: the Users folder, then your folder, then " +
          "Documents, then GitHub. The slashes are the steps inward. That is the entire " +
          "concept, and it is the only one you need.", textSize: 14, name: "pwd-path" });
  s.addNotes(
    "Four commands in this deck. This is the first and the least risky: it reads your " +
    "location and prints it. Nothing can go wrong.\n\n" +
    "Use it to introduce paths, because paths are the actual idea students need. Read one " +
    "out loud, slash by slash, as nested folders.\n\n" +
    "Tell them the translation out loud: ~ and /Users/you are the same place. The prompt " +
    "shows the short form; pwd shows the long one."
  );
}

// =================================================================================
// 7. ls
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Four commands" });
  chip(s, "command 2 of 4", { fill: GREY });
  s.addText("ls — what's in here?", { placeholder: "title" });
  terminal(s, [
    typed("laptop ~ % ls"),
    out("Applications   Desktop     Documents"),
    out("Downloads      Movies      Music"),
    out("Pictures       Public"),
  ], { x: M, y: BODY_TOP, w: 7.5, fontSize: 16, name: "ls-term" });
  card(s, { x: 8.55, y: BODY_TOP, w: 4.08, h: 1.4, fill: MIST, head: "List",
    headSize: 15, text: "Two letters: lowercase L, lowercase S.", textSize: 14,
    name: "ls-c1" });
  card(s, { x: 8.55, y: BODY_TOP + 1.55, w: 4.08, h: 1.4, fill: MIST,
    head: "Nothing came back?", headSize: 15,
    text: "Then the folder is empty. Silence is a real answer here.", textSize: 14,
    name: "ls-c2" });
  caption(s,
    "The same folders you see in Finder, in the same home folder. Open a Finder window " +
    "beside the terminal and compare the two lists — they match.",
    { x: M, y: 3.7, w: 7.5, h: 0.85, fontSize: 16, color: SLATE });
  s.addNotes(
    "Do the Finder comparison live if you can. Putting the two windows side by side is " +
    "what makes the terminal stop feeling like a separate machine.\n\n" +
    "The 'silence is an answer' point saves a lot of confusion later. Terminal commands " +
    "that succeed often print nothing at all, which beginners read as a failure.\n\n" +
    "Mention that files starting with a dot are hidden from both ls and Finder by default. " +
    "They will meet one on slide 11."
  );
}

// =================================================================================
// 8. cd
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Four commands" });
  chip(s, "command 3 of 4", { fill: GREY });
  s.addText("cd — move", { placeholder: "title" });
  terminal(s, [
    typed("laptop ~ % cd Documents"),
    typed("laptop Documents % cd .."),
    typed("laptop ~ % "),
  ], { x: M, y: BODY_TOP, w: 7.5, fontSize: 16, name: "cd-term" });
  caption(s, "Watch the middle of the prompt change. That is how you know it worked.",
    { x: M, y: 3.4, w: 7.5, fontSize: 15, color: SLATE, italic: true });
  card(s, { x: 8.55, y: BODY_TOP, w: 4.08, h: 1.0, fill: MIST, head: "cd Documents",
    headMono: true, headSize: 14, headH: 0.32,
    text: "Go into a folder you can see", textSize: 13, name: "cd-c1" });
  card(s, { x: 8.55, y: BODY_TOP + 1.12, w: 4.08, h: 1.0, fill: MIST, head: "cd ..",
    headMono: true, headSize: 14, headH: 0.32,
    text: "Go back up one level", textSize: 13, name: "cd-c2" });
  card(s, { x: 8.55, y: BODY_TOP + 2.24, w: 4.08, h: 1.0, fill: MIST, head: "cd ~",
    headMono: true, headSize: 14, headH: 0.32,
    text: "Go straight home from anywhere", textSize: 13, name: "cd-c3" });
  card(s, { x: M, y: 4.0, w: 7.5, h: 1.65, fill: PANEL,
    head: "Press Tab instead of finishing the word", headSize: 15,
    text: "Type cd Doc and press Tab — the terminal completes it to Documents. It only " +
          "completes names that really exist, so Tab is also how you check your spelling " +
          "before you commit to it.", textSize: 14, name: "cd-tab" });
  s.addNotes(
    "This is the one command they will use every single day, and the only one worth " +
    "drilling. Have the room run all three forms.\n\n" +
    "Teach Tab completion here rather than as a tip at the end. It prevents typos, it is " +
    "faster, and it quietly teaches them which folders exist. Beginners who learn Tab " +
    "early stop fearing long paths.\n\n" +
    "The two-dots form confuses people the first time. Say it plainly: one dot is here, " +
    "two dots is the folder above here."
  );
}

// =================================================================================
// 9. The four commands
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_DARK", sectionTitle: "Four commands" });
  s.addText("The whole vocabulary", { placeholder: "title" });
  const rows = [
    ["pwd", "Where am I?", GREEN_L],
    ["ls", "What is in here?", GREEN_L],
    ["cd", "Go somewhere else", OCHRE_L],
    ["mkdir", "Make a new folder", OCHRE_L],
  ];
  rows.forEach((r, i) => {
    const y = BODY_TOP + i * 0.78;
    s.addText(r[0], { x: M, y, w: 2.6, h: 0.6, fontSize: 24, bold: true, fontFace: MONO,
      color: r[2], valign: "middle", isTextBox: true, margin: 0,
      objectName: `vocab-cmd-${r[0]}` });
    s.addText(r[1], { x: 3.5, y, w: 9.1, h: 0.6, fontSize: 19, color: MIST,
      valign: "middle", isTextBox: true, margin: 0, objectName: `vocab-def-${r[0]}` });
  });
  caption(s, "Two of them only look. Two of them act. None of them can delete anything.",
    { x: M, y: 5.35, w: W, fontSize: 16, color: GREY_L, italic: true });
  card(s, { x: M, y: 5.95, w: 3.84, h: 0.62, fill: PANEL, head: "Tab  completes a name",
    headSize: 14, headH: 0.3, name: "k-tab" });
  card(s, { x: 4.74, y: 5.95, w: 3.84, h: 0.62, fill: PANEL,
    head: "\u2191  brings back the last command", headSize: 14, headH: 0.3, name: "k-up" });
  card(s, { x: 8.79, y: 5.95, w: 3.84, h: 0.62, fill: PANEL,
    head: "Ctrl + C  stops anything", headSize: 14, headH: 0.3, name: "k-ctrlc" });
  s.addNotes(
    "The slide to photograph. Tell them to take a picture of this one now, so they stop " +
    "worrying about remembering.\n\n" +
    "Make the safety point explicitly: none of the four commands in this deck deletes " +
    "anything. The command that does delete is rm, it is not in this deck, and they " +
    "should be careful the day they meet it.\n\n" +
    "Ctrl+C is the escape hatch. If the terminal ever seems stuck or is printing forever, " +
    "Ctrl+C gets them back to a prompt. Knowing that removes most of the fear of typing " +
    "something wrong."
  );
}

// =================================================================================
// 10. One folder for all your code
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "A folder" });
  chip(s, "command 4 of 4", { fill: GREY });
  s.addText("Make one folder where all your projects live", { placeholder: "title" });
  terminal(s, [
    typed("laptop ~ % cd Documents"),
    typed("laptop Documents % mkdir GitHub"),
    typed("laptop Documents % cd GitHub"),
    dim("laptop GitHub % "),
  ], { x: M, y: BODY_TOP, w: 7.5, fontSize: 16, name: "mk-term" });
  caption(s, "Three lines, once, and you never do it again.",
    { x: M, y: 3.65, w: 7.5, h: 0.4, fontSize: 15, color: SLATE, italic: true });
  card(s, { x: 8.55, y: BODY_TOP, w: 4.08, h: 1.4, fill: MIST, head: "mkdir",
    headMono: true, headSize: 16, text: "Make directory. It creates the folder and " +
    "says nothing when it works.", textSize: 13, name: "mk-c1" });
  card(s, { x: 8.55, y: BODY_TOP + 1.55, w: 4.08, h: 1.4, fill: MIST,
    head: "Already have one?", headSize: 15,
    text: "Then skip mkdir and just cd into it. GitHub Desktop makes this same folder.",
    textSize: 13, name: "mk-c2" });
  card(s, { x: M, y: 4.1, w: 7.5, h: 2.1, fill: PANEL,
    head: "Why one folder, and why this one", headSize: 16,
    text: "Every project in the same place means one path to remember and one place to " +
          "look. Documents/GitHub is also where GitHub's own desktop app puts things, so " +
          "you stay compatible with the tool you may add later. The name is yours to " +
          "choose — code, projects, dev all work. Pick one today and keep it.",
    textSize: 14, name: "mk-why" });
  s.addNotes(
    "This is the 'folder' in the title of the talk, and it is a habit rather than a " +
    "technical step.\n\n" +
    "The reason to insist on one folder: six months from now they will have eight " +
    "projects, and the difference between a tidy Documents/GitHub and eight folders " +
    "scattered across the Desktop and Downloads is whether they can find their own work.\n\n" +
    "Say that mkdir printing nothing means success, and tie it back to slide 7. If they " +
    "want proof, run ls."
  );
}

// =================================================================================
// 11. What GitHub is
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "GitHub" });
  s.addText("What GitHub actually is", { placeholder: "title" });
  card(s, { x: M, y: BODY_TOP, w: 3.84, h: 2.05, fill: MIST, num: 1, accent: BLUE,
    head: "A repository", headSize: 16,
    text: "A project folder that keeps its own history. Usually called a repo. The " +
          "history lives in a hidden .git folder inside it.", textSize: 14, name: "gh-c1" });
  card(s, { x: 4.74, y: BODY_TOP, w: 3.84, h: 2.05, fill: MIST, num: 2, accent: BLUE,
    head: "A copy that isn't yours", headSize: 16,
    text: "github.com holds a copy on the internet. Your laptop is no longer the only " +
          "place your work exists.", textSize: 14, name: "gh-c2" });
  card(s, { x: 8.79, y: BODY_TOP, w: 3.84, h: 2.05, fill: MIST, num: 3, accent: BLUE,
    head: "Every version, kept", headSize: 16,
    text: "Each saved change records what changed, who changed it and when. You can read " +
          "any earlier version back.", textSize: 14, name: "gh-c3" });
  caption(s,
    "Think of it as version history for a folder of files, with a copy stored somewhere " +
    "other than your laptop.",
    { x: M, y: 4.32, w: W, h: 0.7, fontSize: 19, color: INK });
  card(s, { x: M, y: 5.15, w: W, h: 1.3, fill: PANEL,
    head: "Two names, two things", headSize: 15,
    text: "Git is the program on your laptop that records the history. GitHub is a " +
          "website that stores a copy and lets other people see it. An account is free.",
    textSize: 14, name: "gh-note" });
  s.addNotes(
    "Students conflate git and GitHub constantly, so separate them in one sentence and " +
    "move on. Git is local and does the work; GitHub is a website that holds a copy.\n\n" +
    "The version-history framing is the one that lands with people who have used Google " +
    "Docs. Same idea, applied to a whole folder, with the history under your control.\n\n" +
    "You do not need to teach commit, push, branch or pull request today. They can ask " +
    "Claude Code to do all of it in English, and they will learn the words by watching " +
    "what it runs. Say that out loud — it gives them permission to start before they " +
    "understand everything."
  );
}

// =================================================================================
// 12. Clone a repo
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "GitHub" });
  s.addText("Put a project on your laptop", { placeholder: "title" });
  terminal(s, [
    typed("laptop GitHub % git clone https://github.com/sstirling/rowan-clery.git"),
    out("Cloning into 'rowan-clery'..."),
    out("Receiving objects: 100% (1,284/1,284), done."),
    typed("laptop GitHub % cd rowan-clery"),
    dim("laptop rowan-clery % "),
  ], { x: M, y: BODY_TOP, w: W, fontSize: 15, name: "clone-term" });
  caption(s,
    "Clone copies the project and its whole history down into a new folder named after " +
    "the repo. You get the URL from the green Code button on any GitHub page.",
    { x: M, y: 3.88, w: W, h: 0.6, fontSize: 16, color: SLATE });
  card(s, { x: M, y: 4.65, w: 3.84, h: 1.55, fill: MIST,
    head: "First git on a Mac?", headSize: 15,
    text: "macOS offers to install developer tools. Click install and wait.",
    textSize: 13, name: "cl-c1" });
  card(s, { x: 4.74, y: 4.65, w: 3.84, h: 1.55, fill: MIST, head: "On Windows",
    headSize: 15, text: "Install Git for Windows from git-scm.com first. Accept every " +
    "default.", textSize: 13, name: "cl-c2" });
  card(s, { x: 8.79, y: 4.65, w: 3.84, h: 1.55, fill: MIST, head: "No project yet?",
    headSize: 15, text: "Then mkdir my-project, cd into it, and let Claude Code set up " +
    "the rest.", textSize: 13, name: "cl-c3" });
  s.addNotes(
    "Use a real public repo so the command actually works in the room. Any public repo " +
    "clones without a login.\n\n" +
    "Point out that clone creates the folder for them, so they should run it from inside " +
    "Documents/GitHub and not make an empty folder first. Cloning into the wrong place is " +
    "the most common stumble here, and the fix is pwd.\n\n" +
    "Private repos need authentication, which is a separate session. Keep today public."
  );
}

// =================================================================================
// 13. Install Claude Code
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Claude Code" });
  s.addText("Install Claude Code", { placeholder: "title" });
  caption(s, "Copy one line. Paste it. Press Return. Which line depends on your computer.",
    { x: M, y: 1.78, w: W, fontSize: 15, color: SLATE });
  s.addText("macOS or Linux", { x: M, y: 2.28, w: 6.2, h: 0.3, fontSize: 13, bold: true,
    color: GREY, isTextBox: true, margin: 0, charSpacing: 1, objectName: "lbl-mac" });
  terminal(s, [typed("curl -fsSL https://claude.ai/install.sh | bash")],
    { x: M, y: 2.62, w: 6.2, h: 0.6, fontSize: 13, name: "inst-mac" });
  s.addText("Windows PowerShell", { x: 7.13, y: 2.28, w: 5.5, h: 0.3, fontSize: 13,
    bold: true, color: GREY, isTextBox: true, margin: 0, charSpacing: 1,
    objectName: "lbl-win" });
  terminal(s, [typed("irm https://claude.ai/install.ps1 | iex")],
    { x: 7.13, y: 2.62, w: 5.5, h: 0.6, fontSize: 13, name: "inst-win" });
  s.addText("Then check it landed", { x: M, y: 3.62, w: 6.2, h: 0.3, fontSize: 13,
    bold: true, color: GREY, isTextBox: true, margin: 0, charSpacing: 1,
    objectName: "lbl-ver" });
  terminal(s, [typed("claude --version"), ok("2.1.302 (Claude Code)")],
    { x: M, y: 3.96, w: 6.2, fontSize: 13, name: "inst-ver" });
  card(s, { x: 7.13, y: 3.96, w: 5.5, h: 1.08, fill: MIST,
    head: "Nothing appears to happen", headSize: 15,
    text: "No progress bar appears. Leave it alone and wait.",
    textSize: 13, name: "inst-c1" });
  card(s, { x: M, y: 5.15, w: 6.2, h: 1.55, fill: PANEL,
    head: "This one needs a paid plan", headSize: 15,
    text: "Claude Code requires Pro, Max, Team, Enterprise or a Console account. The free " +
          "claude.ai plan does not include it. Check for a student or campus plan before " +
          "you pay.", textSize: 13, name: "inst-plan" });
  card(s, { x: 7.13, y: 5.15, w: 5.5, h: 1.55, fill: MIST,
    head: "command not found: claude", headMono: true, headSize: 14,
    text: "It installed, but your terminal does not know where to look yet. Slide 17 has " +
          "the fix. Open a new window and try again first.", textSize: 13,
    name: "inst-c2" });
  s.addNotes(
    "Say the plan requirement out loud and early. Students on the free plan will hit a " +
    "wall at login, and finding that out after installing feels like a bait and switch. " +
    "Check what your campus provides before the session.\n\n" +
    "The silence during download trips up almost everyone. Warn them before they run it, " +
    "not after they have force-quit the window.\n\n" +
    "These commands come from the official install docs, which do change. Re-check " +
    "code.claude.com/docs/en/terminal-guide the week you present this.\n\n" +
    "Worth naming: pasting a command that downloads and runs a script is a real trust " +
    "decision. It is fine here because the address is claude.ai, Anthropic's own domain. " +
    "Teach them to read the domain in any install line before they run it."
  );
}

// =================================================================================
// 14. Start it in the folder
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Claude Code" });
  s.addText("Where you start it is what it can see", { placeholder: "title" });
  terminal(s, [
    typed("laptop ~ % cd Documents/GitHub/rowan-clery"),
    typed("laptop rowan-clery % claude"),
  ], { x: M, y: BODY_TOP, w: W, fontSize: 17, name: "start-term" });
  card(s, { x: M, y: 3.25, w: 5.82, h: 1.8, fill: MIST,
    head: "Started inside the project", headSize: 16, headColor: GREEN,
    text: "Claude Code reads that project's files, runs its tests, and works on the thing " +
          "you are actually doing.", textSize: 14, name: "st-good" });
  card(s, { x: 7.22, y: 3.25, w: 5.41, h: 1.8, fill: MIST,
    head: "Started in your home folder", headSize: 16, headColor: OCHRE,
    text: "It is now pointed at everything you own — your whole Documents folder, your " +
          "Desktop, all of it. Slower, and far broader than you meant.", textSize: 14,
    name: "st-bad" });
  card(s, { x: M, y: 5.35, w: W, h: 0.9, fill: PANEL,
    head: "The habit worth building: cd first, then claude.", headSize: 17,
    headH: 0.42, name: "st-rule" });
  s.addNotes(
    "If the students remember one thing from the Claude Code half of this deck, make it " +
    "this. Everything else they can look up.\n\n" +
    "The welcome screen prints the working directory. Teach them to read that line before " +
    "typing their first message, the same way they read the prompt on slide 5.\n\n" +
    "Starting in the home folder is not dangerous so much as unfocused — but scope is also " +
    "a safety habit. Keeping the tool pointed at one project is how you keep it away from " +
    "everything else you own."
  );
}

// =================================================================================
// 15. First five minutes
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Claude Code" });
  s.addText("Your first five minutes in a session", { placeholder: "title" });
  caption(s, "It logs you in through your browser once, then you just type in English.",
    { x: M, y: 1.78, w: W, fontSize: 15, color: SLATE });
  terminal(s, [
    out("> what does this project do?"),
    blank(),
    out("> explain the folder structure"),
    blank(),
    out("> what files have I changed?"),
    blank(),
    out("> add a hello world page and show me"),
  ], { x: M, y: 2.3, w: 7.5, fontSize: 15, name: "first-term" });
  card(s, { x: 8.55, y: 2.3, w: 4.08, h: 0.92, fill: MIST, head: "Return sends",
    headSize: 14, headH: 0.3, text: "Full sentences beat keywords.", textSize: 13,
    name: "fm-c1" });
  card(s, { x: 8.55, y: 3.3, w: 4.08, h: 0.92, fill: MIST, head: "Esc interrupts",
    headSize: 14, headH: 0.3, text: "Stops it mid-answer.", textSize: 13, name: "fm-c2" });
  card(s, { x: 8.55, y: 4.3, w: 4.08, h: 0.92, fill: MIST, head: "/help lists commands",
    headSize: 14, headH: 0.3, text: "Anything starting with / is a command.", textSize: 13,
    name: "fm-c3" });
  card(s, { x: 8.55, y: 5.3, w: 4.08, h: 0.92, fill: MIST, head: "exit leaves",
    headSize: 14, headH: 0.3, text: "Or Ctrl + D twice.", textSize: 13, name: "fm-c4" });
  card(s, { x: M, y: 4.7, w: 7.5, h: 1.3, fill: PANEL,
    head: "Ask it about itself", headSize: 15,
    text: "\u201cWhat can you do?\u201d and \u201chow do I undo that?\u201d are both " +
          "reasonable first questions. It knows its own documentation.", textSize: 13,
    name: "fm-ask" });
  s.addNotes(
    "Start with a question rather than a task. Asking it to explain the project proves it " +
    "can read the files, and it costs nothing if the answer is wrong.\n\n" +
    "The mental shift that takes longest: you are describing an outcome, not issuing a " +
    "command. Vague in, vague out. 'Fix the bug' is weak; 'the page shows a blank screen " +
    "after I log in with a bad password — fix that' is strong.\n\n" +
    "You cannot click in the terminal. Arrow keys move, and the mouse does nothing. Warn " +
    "them before someone starts clicking at a menu that will not respond."
  );
}

// =================================================================================
// 16. It asks first
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "Claude Code" });
  s.addText("It asks before it changes your files", { placeholder: "title" });
  terminal(s, [
    dim("  Edit file"),
    dim("  index.html"),
    bad("  -  <h1>Hello</h1>"),
    ok("  +  <h1>Hello, Rowan</h1>"),
    blank(),
    out("  Do you want to make this edit?"),
    { text: "  \u276f 1. Yes", color: OCHRE_L, bold: true },
    dim("    2. No, tell Claude what to do differently"),
  ], { x: M, y: BODY_TOP, w: 7.5, fontSize: 13, name: "perm-term" });
  card(s, { x: 8.55, y: BODY_TOP, w: 4.08, h: 1.55, fill: MIST,
    head: "Read the red and green", headSize: 15,
    text: "Red is what leaves, green is what arrives. This is the habit that keeps you in " +
          "charge.", textSize: 13, name: "pm-c1" });
  card(s, { x: 8.55, y: BODY_TOP + 1.7, w: 4.08, h: 1.55, fill: MIST,
    head: "Saying no is useful", headSize: 15,
    text: "Choosing no lets you explain what you wanted instead. It is a conversation, " +
          "not a refusal.", textSize: 13, name: "pm-c2" });
  card(s, { x: 8.55, y: BODY_TOP + 3.37, w: 4.08, h: 1.3, fill: MIST,
    head: "Shift + Tab", headSize: 15,
    text: "Cycles how much it asks. Leave it alone until you trust it.", textSize: 13,
    name: "pm-c3" });
  card(s, { x: M, y: 4.45, w: 7.5, h: 1.5, fill: PANEL,
    head: "Two things to keep out of the terminal", headSize: 15,
    text: "Passwords and API keys. Do not paste them into a session and do not save them " +
          "into a project you might put on GitHub — a public repo publishes them to " +
          "everyone.", textSize: 13, name: "pm-sec" });
  s.addNotes(
    "The permission prompt is the slide that converts the nervous people in the room. " +
    "Nothing changes on their disk without them pressing yes.\n\n" +
    "Teach the diff format properly: minus and red is the old line, plus and green is the " +
    "new one. They will read hundreds of these.\n\n" +
    "Make the point that 'no' is the more interesting answer, because it opens a " +
    "conversation about what they actually wanted. Students assume no means the tool gives " +
    "up.\n\n" +
    "The credentials warning is worth 20 seconds. The classic first-week mistake is " +
    "committing a key to a public repo, and it is tedious to undo."
  );
}

// =================================================================================
// 17. When it breaks
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_LIGHT", sectionTitle: "When it breaks" });
  s.addText("The three errors you will actually hit", { placeholder: "title" });

  const EX = 6.25;        // explanations start here, clear of the 5.0" panes
  const EW = W + M - EX;  // and run to the right margin

  terminal(s, [bad("command not found: claude")],
    { x: M, y: BODY_TOP, w: 5.0, h: 0.68, fontSize: 14, name: "e1" });
  caption(s, "It installed, but your terminal does not know where to look. Run this once, " +
    "then open a new window:", { x: EX, y: BODY_TOP - 0.02, w: EW, h: 0.6,
    fontSize: 13.5, color: SLATE });
  terminal(s, [typed("echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.zshrc")],
    { x: EX, y: BODY_TOP + 0.62, w: EW, h: 0.58, fontSize: 11.5, name: "e1fix" });

  terminal(s, [bad("no such file or directory")],
    { x: M, y: 3.5, w: 5.0, h: 0.68, fontSize: 14, name: "e2" });
  caption(s, "You are not where you think you are, or the name is misspelled. Run pwd to " +
    "see where you are and ls to see what is really there. Then use Tab.",
    { x: EX, y: 3.46, w: EW, h: 0.75, fontSize: 13.5, color: SLATE });

  terminal(s, [bad("'irm' is not recognized")],
    { x: M, y: 4.72, w: 5.0, h: 0.68, fontSize: 14, name: "e3" });
  caption(s, "You are in CMD, not PowerShell. Close it, press Win + X, and choose " +
    "Windows PowerShell. The line with PS at the front is the right window.",
    { x: EX, y: 4.68, w: EW, h: 0.75, fontSize: 13.5, color: SLATE });

  card(s, { x: M, y: 5.9, w: W, h: 0.7, fill: PANEL,
    head: "Or paste the error straight into Claude Code and ask what it means.",
    headSize: 15, headH: 0.3, name: "e-ask" });
  s.addNotes(
    "Pre-empting these three saves the whole room. They are the errors that make beginners " +
    "quit, and each one has a one-line fix.\n\n" +
    "The PATH error is the most common and sounds the most alarming. Reassure them: the " +
    "install worked. The terminal just has not been told where the program went, and a new " +
    "window after that line fixes it.\n\n" +
    "Teach the habit on the last line. An error message pasted into Claude Code usually " +
    "gets explained and fixed on the spot, and reading error messages instead of fearing " +
    "them is most of what separates a beginner from an intermediate."
  );
}

// =================================================================================
// 18. The whole sequence
// =================================================================================
{
  const s = S({ masterName: "TITLE_ONLY_DARK", sectionTitle: "When it breaks" });
  s.addText("Everything, in order", { placeholder: "title" });
  const steps = [
    ["1", "Open a terminal", "Cmd + Space, type Terminal", OCHRE],
    ["2", "Install Claude Code, once", "curl -fsSL https://claude.ai/install.sh | bash", OCHRE],
    ["3", "Make your projects folder, once", "cd Documents  then  mkdir GitHub", BLUE],
    ["4", "Get a project into it", "cd ~/Documents/GitHub  then  git clone <url>", BLUE],
    ["5", "Start Claude Code inside it", "cd <project>  then  claude", GREEN],
  ];
  steps.forEach((st, i) => {
    const y = BODY_TOP - 0.1 + i * 0.84;
    s.addShape(pres.ShapeType.ellipse, { x: M, y: y + 0.08, w: 0.44, h: 0.44,
      fill: { color: st[3] }, line: { type: "none" }, objectName: `seq-bg-${i}` });
    s.addText(st[0], { x: M, y: y + 0.08, w: 0.44, h: 0.44, fontSize: 14, bold: true,
      color: PAPER, align: "center", valign: "middle", isTextBox: true, margin: 0,
      objectName: `seq-n-${i}` });
    s.addText(st[1], { x: 1.34, y, w: 4.5, h: 0.6, fontSize: 17, bold: true, color: PAPER,
      valign: "middle", isTextBox: true, margin: 0, objectName: `seq-h-${i}` });
    s.addText(st[2], { x: 5.95, y, w: 6.68, h: 0.6, fontSize: 14, fontFace: MONO,
      color: GREY_L, valign: "middle", isTextBox: true, margin: 0,
      objectName: `seq-c-${i}` });
  });
  caption(s, "Steps 2 and 3 you do once, ever. After that it is two lines to start work.",
    { x: M, y: 6.1, w: W, fontSize: 16, color: MIST });
  s.addNotes(
    "Close by collapsing the whole session into five lines, and tell them again to " +
    "photograph it.\n\n" +
    "The honest summary: two of these steps are one-time setup, and daily use is cd then " +
    "claude. That is the reason this was worth 30 minutes.\n\n" +
    "Leave them with one assignment rather than a reading list: clone any public repo " +
    "tonight, start Claude Code in it, and ask what the project does. Nothing breaks, and " +
    "the fear is gone after the first time.\n\n" +
    "Source for every command here: code.claude.com/docs — the terminal guide and the " +
    "quickstart."
  );
}

pres.writeFile({ fileName: OUT })
  .then(() => applyTheme(OUT, THEME))
  .then(() => console.log("wrote " + OUT))
  .catch((e) => { console.error(e); process.exit(1); });

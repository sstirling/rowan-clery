/* Shared across all three pages: payload access, theme, tooltip, data export, footer.
   Nothing here may assume a chart, a table or a feed exists — about.html loads this and
   nothing else. */

const D = JSON.parse(document.getElementById("payload").textContent);
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const SERIES = ["--s1","--s2","--s3","--s4","--s5","--s6","--s7","--s8"];
const cssvar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const clip = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

/* Statuses meaning "the source still publishes this row". */
const LIVE = new Set(["active", "missing"]);
/* Rowan keeps roughly 90-120 days of the log online, so a whole monthly sheet dropping
   out is routine retention, not a withdrawal. A single row vanishing from a sheet that
   is STILL published is a different thing, and the only one worth flagging. */
const AGED_OUT = "source_removed";

/* ---- months ---- */
// Months arrive in two labellings: "August 2026" (Drive) and "2022-09" (legacy).
function monthKey(m) {
  if (/^\d{4}-\d{2}$/.test(m)) return m;
  const d = new Date(m + " 1");
  return isNaN(d) ? m : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function shortMonth(m) {
  const k = monthKey(m);
  if (!/^\d{4}-\d{2}$/.test(k)) return m;
  return MON[+k.slice(5) - 1] + " " + k.slice(2, 4);
}
// Collapse a year's captured months into a readable range in ACADEMIC order (Aug->Jul).
// "2/12" was the earlier label and read as a date — people see "1/12" and think January.
function coverageLabel(months, chronological) {
  if (!months.length) return "none";
  if (months.length === 12 && !chronological) return "all 12 months";
  // Within one school year, order academically (August is 0, July is 11). A window that
  // crosses school years is ordered by date instead, or Jun-Sep 2026 reads "Aug-Sep,
  // Jun-Jul".
  const pos = chronological
    ? m => (+m.slice(0, 4)) * 12 + (+m.slice(5))
    : m => (+m.slice(5) - 8 + 12) % 12;
  const sorted = months.slice().sort((a, b) => pos(a) - pos(b));
  const runs = [];
  sorted.forEach(m => {
    const last = runs[runs.length - 1];
    if (last && pos(m) === pos(last[last.length - 1]) + 1) last.push(m);
    else runs.push([m]);
  });
  const name = m => MON[+m.slice(5) - 1];
  return runs.map(r => r.length === 1 ? name(r[0]) : `${name(r[0])}–${name(r[r.length - 1])}`).join(", ");
}

/* ---- theme ----
   The <head> script already resolved and applied the theme before first paint. This only
   handles changes made after load. */
let REDRAW = null;              // charts register a repaint here; other pages leave it null
const setRedraw = (fn) => { REDRAW = fn; };

const themeButton = $("#theme");
if (themeButton) {
  themeButton.onclick = () => {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
    try { localStorage.setItem("theme", dark ? "light" : "dark"); } catch {}
    // Chart fills are baked in as resolved hex, so they have to be redrawn. A page with
    // no charts has nothing to repaint — and calling drawAll() unconditionally here used
    // to throw on exactly that page.
    if (REDRAW) REDRAW();
  };
}
// Follow the OS only while the reader has not chosen for themselves.
if (window.matchMedia) {
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
    let stored = null;
    try { stored = localStorage.getItem("theme"); } catch {}
    if (stored === "light" || stored === "dark") return;
    document.documentElement.setAttribute("data-theme", e.matches ? "dark" : "light");
    if (REDRAW) REDRAW();
  });
}

/* ---- tooltip ---- */
const tip = $("#tip");
function showTip(e, html) {
  if (!tip) return;
  tip.innerHTML = html; tip.style.opacity = 1;
  const r = tip.getBoundingClientRect();
  let x = e.clientX + 13, y = e.clientY + 13;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 13;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 13;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
const hideTip = () => { if (tip) tip.style.opacity = 0; };

/* ---- exportable data ----
   Every chart, and the incident table, registers the rows it is showing. The buttons emit
   TSV (which Datawrapper, Sheets and Excel all accept on paste) or a CSV file — so a view
   here can become a published graphic without anyone re-typing numbers or re-deriving a
   filter. */
const CHART_DATA = {};
function register(id, header, rows) { CHART_DATA[id] = { header, rows }; }
// The table's rows change with every keystroke in the filter bar, so it registers a
// function and is resolved at the moment the button is pressed.
function registerLive(id, fn) { CHART_DATA[id] = fn; }
function exportData(id) {
  const d = CHART_DATA[id];
  return typeof d === "function" ? d() : d;
}

const cell = (v) => String(v ?? "").replace(/[\t\r\n]+/g, " ");

function toTSV(d) {
  return [d.header.join("\t")].concat(d.rows.map(r => r.map(cell).join("\t"))).join("\n");
}

function toCSV(d) {
  // RFC 4180 quoting. Narratives routinely contain commas and quotation marks, and a
  // naive join would shift every later column on those rows.
  const q = (v) => {
    const s = cell(v);
    return /[",]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [d.header.map(q).join(",")].concat(d.rows.map(r => r.map(q).join(","))).join("\r\n");
}

async function copyData(id, button) {
  const d = exportData(id);
  if (!d) return;
  const text = toTSV(d);
  const label = button.dataset.label || button.textContent;
  button.dataset.label = label;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // The clipboard API needs a secure context; file:// and plain http fail. Fall back to
    // a selectable textarea so the data is never actually unreachable.
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch {}
    ta.remove();
  }
  flash(button, `Copied ${d.rows.length} rows`);
}

function downloadData(id, button) {
  const d = exportData(id);
  if (!d) return;
  // A UTF-8 BOM, because the most likely destination is Excel, which otherwise mangles
  // the en-dashes and curly quotes that come straight out of the source narratives.
  const blob = new Blob(["﻿" + toCSV(d)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${id === "table" ? "rowan-clery-incidents" : "rowan-clery-" + id}-${D.generated_utc.slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  if (button) flash(button, `${d.rows.length} rows`);
}

function flash(button, message) {
  const label = button.dataset.label || button.textContent;
  button.dataset.label = label;
  button.textContent = message;
  button.classList.add("done");
  setTimeout(() => { button.textContent = label; button.classList.remove("done"); }, 2000);
}

document.addEventListener("click", (e) => {
  const button = e.target.closest("button.copy");
  if (!button) return;
  if (button.dataset.copy) copyData(button.dataset.copy, button);
  else if (button.dataset.download) downloadData(button.dataset.download, button);
});

/* The about page links the source folder; the URL lives in the payload, not the markup. */
const srclink = $("#srclink");
if (srclink) srclink.href = D.source_folder;

/* ---- footer ----
   The provenance line. Rendered rather than written into the template because it carries
   live counts and the build timestamp. */
const foot = $("#foot");
if (foot) {
  foot.innerHTML =
    `Source: Rowan University daily crime log, published as Google Sheets at
     <a href="${esc(D.source_folder)}">drive.google.com</a>. Archived independently because the source
     folder is a rolling window — only the most recent months stay online — so this is the longer
     record. Archive began ${esc(D.archive_started)}; it cannot attest to anything before that date.
     Covers the log as published since ${esc(D.published_era.since)} —
     ${D.counts.total_archived} incidents · built
     ${esc(D.generated_utc.replace("T", " ").replace("+00:00", " UTC"))} ·
     method, keying and known source errors are in METHODOLOGY.md.`;
}

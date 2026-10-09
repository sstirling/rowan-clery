/* Overview page: recent activity, context banners, stat tiles, charts, incident table. */

/* ---- recent activity ----
   A rolling window of what the source has done lately. The counts are computed in
   build.py (see `_activity`) so this page does not have to carry the whole changelog. */
function renderActivity() {
  const mount = $("#activity");
  if (!mount) return;
  const a = D.activity;
  const metric = (n, one, many) => `<span class="m"><b>${n}</b><span>${esc(n === 1 ? one : many)}</span></span>`;
  const moved = a.added + a.amended + a.withdrawn;

  mount.className = "activity" + (moved || a.aged_out ? "" : " quiet");
  mount.innerHTML =
    `<span class="flag">${moved || a.aged_out
        ? `Last ${a.window_days} days`
        : `No changes in the last ${a.window_days} days`}</span>` +
    `<div class="row">` +
      metric(a.added, "incident added", "incidents added") +
      metric(a.amended, "record amended", "records amended") +
      metric(a.withdrawn, "record pulled from a live sheet", "records pulled from live sheets") +
    `</div>` +
    `<div class="when">${esc(a.since)} to ${esc(a.until)} · checked ` +
      `${a.runs_in_window} time${a.runs_in_window === 1 ? "" : "s"} in this window, ` +
      `${a.checked_total} in total` +
      (a.staleness_days !== null && a.staleness_days > 0
        ? ` · last check ${a.staleness_days} day${a.staleness_days === 1 ? "" : "s"} ago` : "") +
      (a.aged_out
        ? ` · ${a.aged_out} record${a.aged_out === 1 ? "" : "s"} aged out of Rowan's rolling
            window in this period and ${a.aged_out === 1 ? "remains" : "remain"} here in full`
        : "") +
      `.</div>`;
}

/* ---- context banners ---- */
const c = D.counts;
const banners = [];
const curYear = D.school_years.find(y => y.year === D.current_school_year);

const staleDays = D.status.staleness_days;
if (staleDays !== null && staleDays > 2) {
  banners.push(`<div class="banner alarm"><strong>This page is ${staleDays} days stale.</strong>
    The last successful run was ${esc(D.status.last_successful_run)}. The scraper may be broken — check the workflow.</div>`);
}

// A whole sheet ageing out is routine and gets no alarm. A single row disappearing from a
// sheet Rowan is still publishing is not routine, and federal guidance says to update a
// crime log entry rather than remove it — so that one keeps a notice.
const pulled = D.incidents.filter(i => i.status === "withdrawn");
if (pulled.length) {
  const months = [...new Set(pulled.map(i => i.month))].map(esc).join(", ");
  banners.push(`<div class="banner warn">
    <strong>${pulled.length} record${pulled.length === 1 ? " has" : "s have"} been removed from a
    sheet Rowan is still publishing.</strong> ${months}. That is different from a month ageing
    out of the rolling window: these rows were taken out of a log that remains online. Every
    field is preserved here and the rows are listed below, struck through.
    Worth putting to the Clery Compliance Office.</div>`);
}

// Anything else the run flagged, minus the rolling-window expiry it explains below.
const otherAlarms = (D.status.alarms || []).filter(a => !/treating the source file as removed/.test(a));
if (otherAlarms.length) {
  banners.push(`<div class="banner warn"><strong>From the last run</strong>
    <ul>${otherAlarms.map(a => `<li>${esc(a)}</li>`).join("")}</ul></div>`);
}

const agedOut = D.incidents.filter(i => i.status === AGED_OUT).length;
banners.push(`<div class="callout">
  <strong>Why this archive exists.</strong> Rowan posts the daily crime log as a rolling window.
  Its annual security report says the most recent 90 days are available; in practice the folder
  has held a little more. Either way, older months come down as a matter of course.
  Nothing here is lost when they do${agedOut
    ? `: ${agedOut} incident${agedOut === 1 ? "" : "s"} the source no longer shows ${agedOut === 1 ? "is" : "are"}
       still listed below, struck through` : ""}.
  This is the longer record, built one daily capture at a time since ${esc(D.archive_started)}.</div>`);

if (curYear) {
  banners.push(`<div class="banner note">
    <strong>${esc(D.current_school_year)} school year, in progress.</strong>
    ${curYear.incidents} incidents across ${esc(coverageLabel(curYear.months))}.
    This page covers the daily crime log as Rowan publishes it now — Google Sheets,
    from ${esc(D.published_era.since)}, ${D.published_era.count} incidents in total.</div>`);
}

banners.push(`<div class="banner note">
  <strong>Read these counts carefully.</strong> They are counts of <em>logged incidents</em>, not of
  crime, and academic terms move them hard — June 2026 holds ${monthCount("June 2026")} and
  September ${monthCount("September 2026")}, which is a campus filling up, not a crime wave.
  Of the ${c.total_archived} incidents, ${agencyCount("RUPD")} carry a Rowan University police
  reference, ${agencyCount("GPD")} a Glassboro municipal police reference and ${agencyCount("CSA")}
  a Campus Security Authority reference, so "campus police handled ${c.total_archived} incidents"
  would be wrong. This archive can attest only to what it has <em>observed</em> since
  ${esc(D.archive_started)}.</div>`);

if ($("#banners")) $("#banners").innerHTML = banners.join("");

function monthCount(m) { return D.incidents.filter(i => i.month === m).length; }
function agencyCount(a) { return D.incidents.filter(i => i.agencies.includes(a)).length; }

function renderStats(scoped) {
  const mount = $("#stats");
  if (!mount) return;
  const amended = scoped.filter(i => i.revision > 1).length;
  const gone = scoped.filter(i => !LIVE.has(i.status) && i.status !== "superseded").length;
  const arrests = scoped.filter(i => i.disposition_flags.includes("arrested")).length;
  const open = scoped.filter(i => i.disposition_flags.includes("open_active")).length;
  mount.innerHTML = [
    ["Incidents", scoped.length],
    ["Ended in an arrest", arrests],
    ["Still open / active", open],
    ["Amended after publication", amended],
    ["No longer in the source", gone],
  ].map(([l, n]) => `<div class="stat"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("");
}

/* ---- chart helpers ---- */
function svg(h, w) { return `<svg viewBox="0 0 ${w || 600} ${h}" preserveAspectRatio="xMinYMin meet" role="img">`; }

function hbars(sel, rows, color, fmt, id, header) {
  if (id) register(id, header || ["Label", "Incidents"], rows.map(r => [r[0], r[1]]));
  if (!$(sel)) return;
  if (!rows.length) { $(sel).innerHTML = `<div class="empty">No data.</div>`; return; }
  const LW = 168, BW = 600 - LW - 46, BH = 19, GAP = 7, max = Math.max(...rows.map(r => r[1])) || 1;
  const h = rows.length * (BH + GAP) + 6;
  let s = svg(h);
  rows.forEach(([label, n], i) => {
    const y = i * (BH + GAP), w = Math.max(2, (n / max) * BW);
    s += `<text class="axis" x="${LW - 8}" y="${y + BH / 2 + 4}" text-anchor="end">${esc(clip(label, 30))}</text>`;
    // 4px rounded data-end, anchored square to the baseline
    s += `<path d="M${LW} ${y} H${LW + w - 4} a4 4 0 0 1 4 4 v${BH - 8} a4 4 0 0 1 -4 4 H${LW} Z"
           fill="${color}" data-t="${esc(label)}: ${fmt ? fmt(n) : n}"/>`;
    s += `<text class="vlabel" x="${LW + w + 7}" y="${y + BH / 2 + 4}">${fmt ? fmt(n) : n}</text>`;
  });
  $(sel).innerHTML = s + "</svg>";
  wireTips(sel);
}
function wireTips(sel) {
  if (!$(sel)) return;
  $(sel).querySelectorAll("[data-t]").forEach(el => {
    el.style.cursor = "crosshair";
    el.addEventListener("mousemove", e => showTip(e, esc(el.dataset.t)));
    el.addEventListener("mouseleave", hideTip);
  });
}

/* ---- scope ----
   The page is built around the school year in progress. Campus crime tracks the academic
   calendar, so an August-to-July window keeps a year's population cycle intact; the full
   archive stays one selection away. */
const ERA_INCIDENTS = D.incidents;

/* ---- binning ----
   Two ways to put an incident in a month: when Rowan PUBLISHED it (the sheet it appeared
   in) or when it actually HAPPENED. Those differ for about a third of the log, because
   Glassboro police report on a median lag of roughly two weeks while campus police log
   same-day. Occurrence is the default: it is the honest answer to "when was there crime".

   The trade is completeness. A month's occurred count keeps rising as late reports
   arrive, so the newest month always reads short. That is stated in the note rather than
   hidden by dropping the month. */
let BINNING = (D.binning && D.binning.default) || "reported";
const binMonth = (i) => BINNING === "occurred" ? i.occurred_month : i.month;
const binKey   = (i) => BINNING === "occurred" ? i.occurred_month_key : i.month_key;
const binYear  = (i) => BINNING === "occurred" ? i.occurred_school_year : i.school_year;
// An incident with no bin under the active binning is charted nowhere. It is still
// counted, in the note, with the reason.
const binnable = (i) => !!binMonth(i);
const yearsFor = () => (BINNING === "occurred" ? D.school_years_occurred : D.school_years) || [];
// Offer only school years that BEGAN inside the published window. The log starts partway
// through 2025-26, so this page holds just that year's June-July tail; listing it as
// "2025-26 — 37 incidents" would describe a school year as if it were two months long.
// Those incidents are still counted under "The whole log".
const FIRST_MONTH = D.facets.months.map(m => monthKey(m.value)).filter(Boolean).sort()[0];
const eraYears = () => yearsFor()
  .map(y => y.year)
  .filter(y => `${y.slice(0, 4)}-08` >= FIRST_MONTH)
  .sort().reverse();
const CURRENT = D.current_school_year;
let SCOPE = eraYears().includes(CURRENT) ? CURRENT : (eraYears()[0] || "era");

// Rebuilt whenever the binning changes: the per-year counts and month coverage are
// properties of the binning, not constants. Leaving them fixed was the trap here — a
// scope labelled from publication months while the bars came from occurrence months can
// draw a bar in a month outside its own academic range.
function renderScope() {
  const years = eraYears();
  if (!years.includes(SCOPE) && SCOPE !== "era") SCOPE = years[0] || "era";
  const binned = ERA_INCIDENTS.filter(binnable);
  if (!$("#scope")) return;
  $("#scope").innerHTML =
    years.map(y => {
      const rows = binned.filter(i => binYear(i) === y);
      const ms = [...new Set(rows.map(binKey))].filter(Boolean);
      return `<option value="${esc(y)}"${y === SCOPE ? " selected" : ""}>`
        + `${esc(y)} school year — ${rows.length} incidents (${esc(coverageLabel(ms))})</option>`;
    }).join("")
    + `<option value="era"${SCOPE === "era" ? " selected" : ""}>The whole log — ${binned.length} incidents`
    + ` (${esc(coverageLabel([...new Set(binned.map(binKey))].filter(Boolean), true))})</option>`;
  $("#scope").onchange = () => { SCOPE = $("#scope").value; drawAll(); };
}

const BIN_OPTIONS = [
  ["occurred", "When the incident occurred"],
  ["reported", "When Rowan reported it"],
];

function renderBinning() {
  if (!$("#binning")) return;
  $("#binning").innerHTML = BIN_OPTIONS.map(([v, label]) =>
    `<option value="${esc(v)}"${v === BINNING ? " selected" : ""}>${esc(label)}</option>`).join("");
  $("#binning").onchange = () => {
    BINNING = $("#binning").value;
    renderScope();
    drawAll();
  };
}

// What the chosen binning leaves out. Every figure comes from the payload, so the note
// cannot drift away from the bars it is explaining.
function renderBinNote() {
  const el = $("#binnote");
  if (!el || !D.binning) return;
  const b = D.binning;
  if (BINNING !== "occurred") {
    el.textContent = "Counted by the month Rowan published each incident in. "
      + `Every one of the ${b.total} incidents is included.`;
    return;
  }
  const missing = b.excluded_no_date + b.excluded_before_window;
  const why = [];
  // Not "no date": one of these is a real date given only as a year. What disqualifies
  // them all is that none names a month, and inventing one would be a guess.
  if (b.excluded_no_date)
    why.push(`${b.excluded_no_date} have no date precise enough to place in a month`);
  if (b.excluded_before_window)
    why.push(`${b.excluded_before_window} occurred before ${b.window_start_label}`);
  const gpd = b.lag_median_days && b.lag_median_days.GPD;
  const lag = gpd
    ? ` Recent months are still filling in: Glassboro police report a median ${gpd} days`
      + " after an incident, so the latest month will rise as reports arrive."
    : " Recent months are still filling in, so the latest month will rise as reports arrive.";
  el.textContent = "Counted by when each incident occurred, not when it was reported."
    + (missing ? ` ${missing} of ${b.total} incidents are not shown: ${why.join(", ")}.` : "")
    + lag;
}

// Nothing outside the current format is ever charted.
const inScope = (i) => binnable(i) && (SCOPE === "era" || binYear(i) === SCOPE);
function scopeLabel() {
  return SCOPE === "era" ? "every month in the log" : `the ${SCOPE} school year`;
}

/* ---- charts ---- */
// Round an axis maximum up to a readable tick value, so the gridlines read 0/30/60/90/120
// rather than 0/27/53/80/107.
function niceMax(v) {
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  for (const step of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10])
    if (v <= step * mag) return step * mag;
  return 10 * mag;
}

function drawMonth() {
  const scoped = D.incidents.filter(inScope);
  const months = [...new Set(scoped.map(binMonth))].filter(Boolean).sort(monthKeyCmp);
  const top = topCategories(scoped, 7);
  const keys = top.concat(["Other"]);
  if ($("#monthsub")) $("#monthsub").textContent =
    `${scopeLabel()} · ${coverageLabel(months.map(monthKey), SCOPE === "era")}`
    + ` · each incident counted once, under its first-listed offense`;

  const data = months.map(m => {
    const rows = scoped.filter(i => binMonth(i) === m);
    const o = { m, total: rows.length, era: rows.length ? rows[0].era : "" };
    keys.forEach(k => o[k] = 0);
    rows.forEach(i => {
      const primary = i.categories.find(k => top.includes(k));
      o[primary || "Other"]++;
    });
    return o;
  });

  const PAD = 34, BOT = 42, H = 250, W = 600;
  const max = niceMax(Math.max(...data.map(d => d.total), 1));
  const slot = (W - PAD - 6) / data.length;
  const bw = Math.max(2, slot - 2);
  let s = svg(H);
  for (let g = 0; g <= 4; g++) {
    const y = 10 + (H - BOT - 10) * (g / 4);
    s += `<line class="gridline" x1="${PAD}" y1="${y}" x2="${W}" y2="${y}"/>
          <text class="axis" x="${PAD - 7}" y="${y + 4}" text-anchor="end">${Math.round(max * (1 - g / 4))}</text>`;
  }

  data.forEach((d, i) => {
    const x = PAD + 4 + i * slot;
    let acc = 0;
    keys.forEach((k, ki) => {
      if (!d[k]) return;
      const hgt = (d[k] / max) * (H - BOT - 10);
      acc += hgt;
      s += `<rect x="${x}" y="${H - BOT - acc}" width="${bw}" height="${Math.max(1, hgt - (slot > 8 ? 1 : 0))}"
             rx="1" fill="${cssvar(SERIES[ki])}" data-t="${esc(d.m)} — ${esc(k)}: ${d[k]} of ${d.total}"/>`;
    });
  });

  data.forEach((d, i) => {
    s += `<text class="axis" x="${PAD + 4 + i * slot + bw / 2}" y="${H - BOT + 15}"`
       + ` text-anchor="middle">${esc(shortMonth(d.m))}</text>`;
  });

  register("month", ["Month", ...keys, "Total"],
    data.map(d => [d.m, ...keys.map(k => d[k]), d.total]));
  if ($("#chart-month")) $("#chart-month").innerHTML = s + "</svg>";
  if ($("#legend-month")) $("#legend-month").innerHTML = keys.map((k, i) =>
    `<span><i class="swatch" style="background:${cssvar(SERIES[i])}"></i>${esc(k)}</span>`).join("");
  wireTips("#chart-month");
}

// Rank categories within whatever is in scope, so a year's own chart reflects that year
// rather than inheriting the whole archive's ordering.
function topCategories(rows, n) {
  const counts = {};
  rows.forEach(i => i.categories.forEach(k => counts[k] = (counts[k] || 0) + 1));
  return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, n).map(e => e[0]);
}
function countBy(rows, pick) {
  const counts = {};
  rows.forEach(i => [].concat(pick(i)).forEach(v => { if (v) counts[v] = (counts[v] || 0) + 1; }));
  return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}
const monthKeyCmp = (a, b) => monthKey(a) < monthKey(b) ? -1 : monthKey(a) > monthKey(b) ? 1 : 0;

// One sparkline per offense, month by month. Small multiples rather than a single
// multi-series line: twelve lines on one axis is unreadable, and the question here is
// "is THIS offense moving", which each panel answers on its own.
function drawTrend() {
  const scoped = D.incidents.filter(inScope);
  const months = [...new Set(scoped.map(binMonth))].filter(Boolean).sort(monthKeyCmp);
  const cats = topCategories(scoped, 12);

  if ($("#trendsub")) $("#trendsub").textContent = months.length < 2
    ? `${scopeLabel()} · only ${months.length} month of data so far — trends appear as the year fills in`
    : `${scopeLabel()} · ${months.length} months · each panel on its own scale, peak labelled`;

  register("trend", ["Offense", ...months],
    cats.map(cat => [cat, ...months.map(m =>
      scoped.filter(i => binMonth(i) === m && i.categories.includes(cat)).length)]));

  if (!$("#chart-trend")) return;
  if (!cats.length) { $("#chart-trend").innerHTML = `<div class="empty">No incidents in scope.</div>`; return; }

  const W = 165, H = 54, PADL = 4, PADB = 13;
  $("#chart-trend").innerHTML = `<div class="smallmult">` + cats.map(cat => {
    const series = months.map(m => scoped.filter(i => binMonth(i) === m && i.categories.includes(cat)).length);
    const total = series.reduce((a, b) => a + b, 0);
    const peak = Math.max(...series, 1);
    const bw = Math.max(2, (W - PADL * 2) / series.length - 2);
    let bars = "";
    series.forEach((n, i) => {
      const x = PADL + i * ((W - PADL * 2) / series.length);
      const h = Math.max(n ? 2 : 1, (n / peak) * (H - PADB - 12));
      // Plain baseline-anchored rects. An earlier version rotated a rounded path to
      // flip it and mangled the geometry; at these widths a rect with rx reads the same
      // and cannot go wrong.
      bars += `<rect x="${x}" y="${H - PADB - h}" width="${bw}" height="${h}" rx="1"
                fill="${cssvar("--s1")}" opacity="${n ? 1 : 0.15}"
                data-t="${esc(cat)} — ${esc(months[i])}: ${n}"/>`;
    });
    bars += `<line x1="${PADL}" y1="${H - PADB}" x2="${W - PADL}" y2="${H - PADB}" class="gridline"/>`;
    // Label only the first and last month: a label per bar is noise.
    const tick = (i, anchor) => months.length > 1
      ? `<text class="axis" x="${anchor === "start" ? PADL : W - PADL}" y="${H - 2}"
          text-anchor="${anchor}" font-size="9">${esc(shortMonth(months[i]))}</text>` : "";
    return `<div class="sm">
      <div class="nm"><span>${esc(clip(cat, 20))}</span><span class="tot">${total}</span></div>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMinYMin meet">
        <text class="axis" x="${PADL}" y="9" font-size="9">peak ${peak}</text>
        ${bars}${tick(0, "start")}${tick(months.length - 1, "end")}
      </svg></div>`;
  }).join("") + `</div>`;
  wireTips("#chart-trend");
}

const DISP_LABEL = {
  arrested:"Subject arrested", summons_issued:"Summons issued", trespass_notice:"Trespass notice/warning",
  open_active:"Open / active", closed:"Closed", referred_university:"Referred to a university department",
  not_reported_to_rupd:"Not reported to campus police", glassboro_pd:"Glassboro police case",
  rp_declined:"Reporting party declined", property_recovered:"Property recovered", charged:"Charged",
  investigation_completed:"Investigation completed", unsolved:"Unsolved", inactive:"Inactive",
  no_further_action:"No further action", juvenile_involved:"Juvenile involved", warned:"Subject warned",
  building_ban:"Building ban", tro_issued:"Restraining order issued", no_contact:"Left before police arrived",
  referred_prosecutor:"Referred to county prosecutor", rp_referred_to_complaint:"Citizen's complaint info given",
  rp_provided_resources:"Resources provided",
  barred: "Subject barred from campus",
  other_agency: "Referred to another agency",
  station_house_adjustment: "Juvenile station house adjustment",
  title_ix: "Title IX / equity office",
  unfounded: "Determined unfounded",
};

function drawAll() {
  const scoped = D.incidents.filter(inScope);
  if ($("#scopenote")) $("#scopenote").textContent = `${scoped.length} incidents`;
  if ($("#catsub")) $("#catsub").textContent =
    `${scopeLabel()} · incidents may carry more than one offense, so the total exceeds the incident count`;

  renderBinNote();
  drawMonth();
  drawTrend();
  hbars("#chart-cat", countBy(scoped, i => i.categories).slice(0, 14), cssvar("--s1"),
        null, "cat", ["Offense", "Incidents"]);
  hbars("#chart-loc", countBy(scoped, i => i.location).slice(0, 15), cssvar("--s3"),
        null, "loc", ["Location", "Incidents"]);
  hbars("#chart-disp", countBy(scoped, i => i.disposition_flags).slice(0, 12)
    .map(([k, n]) => [DISP_LABEL[k] || k, n]), cssvar("--s7"),
        null, "disp", ["Outcome", "Incidents"]);
  renderStats(scoped);
}

/* ---- table ---- */
const FILTERS = [
  ["#f-month", "months", "All months"], ["#f-cat", "categories", "All offenses"],
  ["#f-campus", "campuses", "All campuses"], ["#f-agency", "agencies", "All agencies"],
  ["#f-status", "statuses", "All records"],
];
const STATUS_LABEL = {
  active: "Still published", missing: "Missing from source",
  withdrawn: "Pulled from a live sheet", source_removed: "Aged out of the source window",
  superseded: "Replaced by a corrected record",
};
FILTERS.forEach(([sel, facet, all]) => {
  if (!$(sel)) return;
  $(sel).innerHTML = `<option value="">${all}</option>` + D.facets[facet]
    .map(o => `<option value="${esc(o.value)}">${esc(STATUS_LABEL[o.value] || o.value)} (${o.count})</option>`).join("");
  $(sel).onchange = render;
});
if ($("#q")) $("#q").oninput = render;

let sortKey = "reported", sortDir = -1;
document.querySelectorAll("#tbl th").forEach(th => th.onclick = () => {
  const k = th.dataset.k;
  sortDir = sortKey === k ? -sortDir : 1; sortKey = k; render();
});

let TABLE_ROWS = [];
const TABLE_HEADER = ["Reported", "Case number", "Agencies", "Offenses", "Nature (raw)", "Narrative",
                      "Campus", "Location", "Disposition (raw)", "Outcomes", "Status", "Month",
                      "School year", "First seen by archive", "Revision"];

// Registered as a function, not a snapshot: the export buttons must emit whatever the
// filters and the search box are showing at the moment they are pressed.
registerLive("table", () => ({
  header: TABLE_HEADER,
  rows: TABLE_ROWS.map(i => [
    i.reported.value || i.reported.raw, i.case_number, i.agencies.join("; "),
    i.categories.join("; "), i.nature_raw, i.narrative, i.campus, i.location,
    i.disposition_raw, i.disposition_flags.map(f => DISP_LABEL[f] || f).join("; "),
    STATUS_LABEL[i.status] || i.status, i.month, i.school_year, i.first_seen_by_archive, i.revision,
  ]),
}));

function render() {
  if (!$("#tbl")) return;
  const term = ($("#q") ? $("#q").value : "").trim().toLowerCase();
  const [m, cat, camp, ag, st] = FILTERS.map(([sel]) => ($(sel) ? $(sel).value : ""));
  let rows = D.incidents.filter(i =>
    (!m || i.month === m) && (!cat || i.categories.includes(cat)) &&
    (!camp || i.campus === camp) && (!ag || i.agencies.includes(ag)) && (!st || i.status === st) &&
    (!term || [i.narrative, i.case_number, i.location, i.nature_raw, i.disposition_raw]
      .join(" ").toLowerCase().includes(term)));

  rows.sort((a, b) => {
    const get = o => sortKey === "reported" ? (o.reported.value || "") : String(o[sortKey] ?? "");
    return get(a) < get(b) ? -sortDir : get(a) > get(b) ? sortDir : 0;
  });

  TABLE_ROWS = rows;
  if ($("#tcount")) $("#tcount").textContent = `${rows.length} of ${D.incidents.length}`;
  $("#tbl tbody").innerHTML = rows.map(i => {
    const gone = !LIVE.has(i.status);
    const agedOutRow = i.status === AGED_OUT;
    return `<tr class="${gone ? "gone" : ""}">
      <td style="white-space:nowrap">${esc((i.reported.value || i.reported.raw).replace("T", " ").slice(0, 16))}</td>
      <td class="case">${esc(i.case_number)}${i.agencies.map(a => `<br><span class="tag">${a}</span>`).join("")}</td>
      <td>${i.categories.map(k => `<span class="tag cat">${esc(k)}</span>`).join("") || esc(i.nature_raw)}
          ${i.reclassified_from.length ? `<span class="tag amend">reclassified</span>` : ""}</td>
      <td class="narr">${esc(i.narrative)}
          ${gone ? `<br><span class="tag ${agedOutRow ? "aged" : "bad"}">${esc(STATUS_LABEL[i.status] || i.status)}${
              i.missing_since ? " since " + esc(i.missing_since) : ""}</span>` : ""}
          ${i.revision > 1 ? `<span class="tag amend">amended ×${i.revision - 1}</span>` : ""}
          ${i.flags.includes("near_duplicate") ? `<span class="tag bad">possible duplicate</span>` : ""}
          ${i.flags.includes("possible_duplicate_identity") ? `<span class="tag bad">possible duplicate identity</span>` : ""}
</td>
      <td>${esc(i.campus)}</td>
      <td>${esc(i.location)}</td>
      <td>${esc(i.disposition_raw)}${i.disposition_amended ? `<br><span class="tag amend">updated by source</span>` : ""}</td>
    </tr>`;
  }).join("") || `<tr><td colspan="7" class="empty">No incidents match these filters.</td></tr>`;
}

setRedraw(drawAll);
renderActivity();
renderBinning();
renderScope();
drawAll();
render();

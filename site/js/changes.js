/* Data & changes page: the changelog feed and the data-quality audit.
   Audit material, kept off the overview so the front page leads with the data. */

const LABEL = {
  added: "Added", amended: "Amended", withdrawn: "Pulled from a live sheet",
  source_removed: "Monthly sheet aged out of the source window", reappeared: "Reappeared",
  missing: "Missing", relocated: "Moved to another file",
  superseded_identity: "Republished under a corrected case number",
  absent_in_later_capture: "Absent from a later capture — needs review",
};

/* ---- what changed ---- */
// Cosmetic date reformats are kept in the changelog but out of the feed: in February
// 2022 alone there are 35, and they would bury the amendments worth reading.
const cosmeticCount = D.changelog.filter(e => e.cosmetic).length;
const feed = D.changelog
  .filter(e => e.change_type !== "added" && !e.cosmetic)
  .slice().reverse().slice(0, 300);

if ($("#feedsub")) {
  $("#feedsub").textContent =
    `${feed.length} amendment${feed.length === 1 ? "" : "s"}, removal${feed.length === 1 ? "" : "s"} and `
    + `corrections observed by this archive, most recent first`
    + (cosmeticCount ? ` · ${cosmeticCount} cosmetic date reformats recorded but hidden here` : "");
}

if ($("#feed")) {
  $("#feed").innerHTML = feed.length ? feed.map(e => `
    <div class="ev ${esc(e.change_type)}">
      <div><strong>${esc(LABEL[e.change_type] || e.change_type)}</strong>
        — ${esc(e.case_number || e.old_case_number || e.incident_uid)}</div>
      <div class="meta">${esc(e.observed_date)}${e.field ? " · " + esc(e.field) : ""}</div>
      ${e.field ? `<div class="diff"><span class="old">${esc(e.old) || "(blank)"}</span>
         → <span class="new">${esc(e.new) || "(blank)"}</span></div>` : ""}
      ${e.last_known_disposition ? `<div class="diff">Last known disposition: ${esc(e.last_known_disposition)}</div>` : ""}
      ${e.change_type === "superseded_identity" ? `<div class="diff"><span class="old">${esc(e.old_case_number)} · ${esc(e.old_date_reported)}</span>
         → <span class="new">${esc(e.new_case_number)} · ${esc(e.new_date_reported)}</span></div>` : ""}
      ${e.change_type === "absent_in_later_capture" ? `<div class="diff">Last seen in the ${esc(e.source_month)} log. Preserved in full; not treated as a deletion.</div>` : ""}
    </div>`).join("")
    : `<div class="empty">No substantive amendments or removals observed yet. The archive started on ${esc(D.archive_started)};
       everything recorded so far is the initial capture.</div>`;
}

/* ---- data quality ---- */
const q = D.quality;
if ($("#quality")) {
  $("#quality").innerHTML = [
    ["Impossible dates in the source", q.invalid_dates,
     r => `${r.case_number} — <code>${esc(r.raw)}</code>`,
     "A date that does not exist on the calendar. Worth raising with Rowan."],
    ["Offenses reclassified after publication", q.reclassified,
     r => `${r.case_number} — ${r.from.join(", ")} → ${r.to.join(", ") || "(none)"}`,
     "The source marks these inline with “Nature updated”. This archive counts only the current classification."],
    ["Incident time not known precisely", q.imprecise_occurred,
     r => `${r.case_number} — <code>${esc(r.raw)}</code> (${r.precision})`,
     "Excluded from anything binned on when the incident occurred."],
    ["Possible duplicate records", q.near_duplicates,
     r => `${r.case_number}`,
     "Same case number, identical narrative, disposition and location, different dates. Could be two real incidents or a source copy-paste error. Both are preserved."],
    ["Reported before it occurred", q.occurred_after_reported,
     r => `${r.case_number} — ${r.hours}h`,
     "The occurrence timestamp is later than the report timestamp."],
    ["Offense terms not in the category map", q.unclassified_offenses,
     r => `${r.case_number} — ${r.tokens.map(esc).join(", ")}`,
     "Counted here rather than folded into a category, so nothing is silently miscounted."],
    ["Disposition terms not in the map", q.unclassified_dispositions,
     r => `${r.case_number} — ${r.tokens.map(esc).join(", ")}`,
     "Wording the disposition map does not recognise. The raw text is still shown in the table."],
    ["Possible duplicate identities", q.duplicate_candidates,
     r => `${r.month} — ${r.case_number}`,
     "Rows that may be the same incident republished under a corrected case number. Flagged, never merged — a wider rule was tested and rejected because it collapsed genuinely distinct same-minute police summonses."],
    ["Dates outside the expected year window", q.year_warnings,
     r => `${r.case_number} — ${esc(r.warning)}`,
     "Checked against the year of the log the row appears in, not against today."],
  ].filter(([, rows]) => rows.length).map(([title, rows, fmt, note]) => `
    <details class="q"><summary><strong>${rows.length}</strong> ${esc(title)}</summary>
      <p class="sub" style="margin:6px 0 0">${note}</p>
      <ul>${rows.slice(0, 40).map(r => `<li>${fmt(r)}</li>`).join("")}</ul>
    </details>`).join("") || `<div class="empty">No data-quality problems detected.</div>`;
}

/* ---- export ----
   The feed is the thing a reporter would most want out of this page: one row per
   observed change, which is the amendment history Rowan's own log does not publish. */
register("changes",
  ["Observed", "Change", "Case number", "Field", "Old value", "New value", "Month"],
  feed.map(e => [
    e.observed_date,
    LABEL[e.change_type] || e.change_type,
    e.case_number || e.old_case_number || e.incident_uid,
    e.field || "",
    e.field ? e.old : (e.change_type === "superseded_identity" ? e.old_case_number : ""),
    e.field ? e.new : (e.change_type === "superseded_identity" ? e.new_case_number : ""),
    e.source_month || "",
  ]));

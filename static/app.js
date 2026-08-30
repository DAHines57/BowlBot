/* Unified stats page.
 *
 * Talks to /api/meta and /api/leaderboard, renders everything client-side.
 * State lives in three places, by intent:
 *   - URL query string: shareable view (range, mode, tab, sort)
 *   - sessionStorage:   this tab's working state, survives reload
 *   - localStorage:     durable preferences set in Settings (defaults only)
 */
(function () {
  "use strict";

  var SESSION_KEY = "bowlbot-app-v1";
  var PREFS_KEY = "bowlbot-app-prefs-v1";
  var DESKTOP_MQ = window.matchMedia("(min-width: 900px)");

  /* Every average pools the individual games inside the selected range. The
   * range itself is the only control over what gets counted. */
  var AGG_MODE = "range";

  /* Which half of the schedule counts. Was a boolean before, so stored
   * sessions and old links still carry true/false and 1/0. */
  var VIEWS = ["players", "teams", "bests", "playoffs"];

  var PLAYOFF_MODES = ["regular", "both", "only"];
  var PLAYOFFS_DEFAULT = "both";
  var PLAYOFF_LABELS = { regular: "Regular", both: "All", only: "Playoffs" };

  function normalizePlayoffs(raw) {
    if (raw === true || raw === "1" || raw === "true") return "both";
    if (raw === false || raw === "0" || raw === "false") return "regular";
    return PLAYOFF_MODES.indexOf(raw) >= 0 ? raw : null;
  }

  /* Sort fields per view. `dir` is the direction chosen when you pick the
   * field; `numeric` fields sort nulls last regardless of direction. */
  var SORT_FIELDS = {
    players: [
      { key: "player", label: "Name", dir: "asc", numeric: false },
      { key: "team", label: "Team", dir: "asc", numeric: false },
      { key: "average", label: "Average", dir: "desc", numeric: true },
      { key: "highest_game", label: "High game", dir: "desc", numeric: true },
      { key: "lowest_game", label: "Low game", dir: "asc", numeric: true },
      { key: "std_dev", label: "Std dev", dir: "asc", numeric: true },
      { key: "games", label: "Games played", dir: "desc", numeric: true },
      { key: "absences", label: "Absences", dir: "desc", numeric: true },
      { key: "par", label: "PAR", dir: "desc", numeric: true, needsPar: true }
    ],
    teams: [
      { key: "team", label: "Team", dir: "asc", numeric: false },
      { key: "avg_per_game", label: "Team average", dir: "desc", numeric: true },
      { key: "total_pins", label: "Total pins", dir: "desc", numeric: true },
      { key: "high_game", label: "High game", dir: "desc", numeric: true },
      { key: "high_week_avg", label: "High week avg", dir: "desc", numeric: true },
      { key: "low_week_avg", label: "Low week avg", dir: "asc", numeric: true },
      { key: "games", label: "Games", dir: "desc", numeric: true },
      { key: "weeks", label: "Weeks", dir: "desc", numeric: true }
    ]
  };

  /* How each numeric sort field renders as a row figure: which row property
   * holds it, how many decimals it takes, its value colour, and a short label
   * for the narrow fourth column where the sort menu's wording is too long. */
  var FIGURE_SPECS = {
    players: {
      average: { key: "average", digits: 2, label: "Avg" },
      highest_game: { key: "highest_game", cls: "fig-good", label: "High" },
      lowest_game: { key: "lowest_game", cls: "fig-bad", label: "Low" },
      std_dev: { key: "std_dev", digits: 2, label: "St dev" },
      games: { key: "games", label: "Games" },
      absences: { key: "absences", label: "Abs" },
      par: { key: "par", label: "PAR" }
    },
    teams: {
      avg_per_game: { key: "avg_per_game", digits: 2, label: "Avg" },
      week_avg: { key: "week_avg", digits: 2, label: "Avg" },
      total_pins: { key: "total_pins", label: "Pins" },
      high_game: { key: "high_game", cls: "fig-good", label: "High game" },
      high_week_avg: {
        key: "high_week_avg", digits: 2, cls: "fig-good", label: "High week"
      },
      low_week_avg: {
        key: "low_week_avg", digits: 2, cls: "fig-bad", label: "Low week"
      },
      games: { key: "games", label: "Games" },
      weeks: { key: "weeks", label: "Weeks" }
    }
  };

  var DENSITIES = [
    { key: "comfortable", label: "Comfortable" },
    { key: "compact", label: "Compact" }
  ];

  /* How many rows the board renders before the Show all button. Zero is no
   * limit, which is the default so the page behaves as it always has. */
  var ROW_LIMITS = [
    { key: 10, label: "Top 10" },
    { key: 25, label: "Top 25" },
    { key: 50, label: "Top 50" },
    { key: 0, label: "All" }
  ];

  /* Order and presentation of the record lists. `digits` and `unit` describe
   * the headline value; `sub` names an extra field shown after the value. */
  var BEST_SECTIONS = [
    { key: "games", title: "Best games", unit: "" },
    { key: "weeks", title: "Best weeks", digits: 2, unit: "avg" },
    { key: "seasons", title: "Best seasons", digits: 2, unit: "avg" },
    { key: "most_200s", title: "Most 200s", unit: "games" },
    { key: "streaks", title: "Longest 200+ streak", unit: "in a row" },
    { key: "consistent", title: "Most consistent", digits: 2, unit: "st dev" },
    { key: "career_nights", title: "Biggest career night", digits: 2, unit: "over avg" },
    { key: "improved", title: "Most improved", digits: 2, unit: "gain" },
    { key: "team_weeks", title: "Best team weeks", digits: 2, unit: "avg" },
    { key: "team_seasons", title: "Best team seasons", digits: 2, unit: "avg" }
  ];

  var BESTS_PREVIEW = 5;

  /* `bestsOpen` is a set of record lists the reader has opened. Every list
   * starts closed, so the Bests tab opens as a short index. */
  var DEFAULT_PREFS = {
    sortPlayers: "average",
    sortPlayersDir: "desc",
    sortTeams: "avg_per_game",
    sortTeamsDir: "desc",
    density: "comfortable",
    rowLimit: 0,
    bestsOpen: {}
  };

  /* A fresh copy every time. Handing out DEFAULT_PREFS.bestsOpen itself would
   * let a toggle mutate the defaults, so the reset button would stop working. */
  function defaultPrefs() {
    var out = {};
    for (var k in DEFAULT_PREFS) out[k] = DEFAULT_PREFS[k];
    out.bestsOpen = {};
    return out;
  }

  var meta = null;
  var prefs = loadPrefs();
  var state = null;
  var payload = null;
  var detailCache = {};
  var openRow = null;
  // Set by the Show all button, cleared whenever the list underneath changes.
  var showAllRows = false;
  var fetchToken = 0;
  // Records are fetched only when the Bests tab is opened, then kept per scope
  // so flipping back and forth costs nothing.
  var bestsCache = {};
  var bestsToken = 0;
  // Which record lists the reader has expanded; each expands on its own.
  var bestsExpanded = {};
  // The bracket is season-scoped rather than range-scoped, so it keeps its own
  // selected season and caches by that instead of by the range query.
  var playoffsCache = {};
  var playoffsToken = 0;
  var playoffSeason = null;
  /* Which playoff sections are open. Only the standings card starts open; round
   * keys carry a week number and so differ per season, which is why this is
   * session state rather than a stored preference. */
  var playoffsOpen = { standings: true };

  /* Which expanded rows have their profile chart open, keyed the same way as
   * `detailCache`. Session state: a chart is a look, not a setting. */
  var profilesOpen = {};

  var el = {};

  /* ---------------- storage ---------------- */

  function loadPrefs() {
    var out = defaultPrefs();
    try {
      var raw = localStorage.getItem(PREFS_KEY);
      if (raw) {
        var parsed = JSON.parse(raw);
        for (var key in DEFAULT_PREFS) {
          if (parsed[key] !== undefined && parsed[key] !== null) out[key] = parsed[key];
        }
      }
    } catch (err) { /* preferences are optional */ }
    // A stored default can name a field that no longer exists (Rank, once it
    // was retired). Left alone it would make sortRows give up, so drop it.
    if (!findField("players", out.sortPlayers)) {
      out.sortPlayers = DEFAULT_PREFS.sortPlayers;
    }
    if (!findField("teams", out.sortTeams)) {
      out.sortTeams = DEFAULT_PREFS.sortTeams;
    }
    // Stored as a number, but a stale or hand-edited entry could be anything.
    out.rowLimit = parseInt(out.rowLimit, 10);
    if (!isRowLimit(out.rowLimit)) out.rowLimit = DEFAULT_PREFS.rowLimit;
    // Rebuilt rather than trusted, so a retired or hand-edited record key
    // cannot linger in the stored set.
    var open = out.bestsOpen;
    out.bestsOpen = {};
    if (open && typeof open === "object") {
      for (var i = 0; i < BEST_SECTIONS.length; i++) {
        var key = BEST_SECTIONS[i].key;
        if (open[key]) out.bestsOpen[key] = true;
      }
    }
    return out;
  }

  function isRowLimit(value) {
    for (var i = 0; i < ROW_LIMITS.length; i++) {
      if (ROW_LIMITS[i].key === value) return true;
    }
    return false;
  }

  function savePrefs() {
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); }
    catch (err) { /* private mode */ }
  }

  function readSession() {
    try {
      var raw = sessionStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (err) { return null; }
  }

  function saveSession() {
    try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(state)); }
    catch (err) { /* private mode */ }
  }

  /* ---------------- helpers ---------------- */

  function pos(season, week) { return { season: season, week: week }; }

  function posText(p) { return "S" + p.season + " W" + p.week; }

  function posParam(p) { return p.season + "." + p.week; }

  function parsePosParam(raw) {
    if (!raw) return null;
    var bits = String(raw).split(".");
    var s = parseInt(bits[0], 10);
    var w = bits.length > 1 ? parseInt(bits[1], 10) : 1;
    if (!s || s < 1 || !w || w < 1) return null;
    return pos(s, w);
  }

  function comparePos(a, b) {
    if (a.season !== b.season) return a.season - b.season;
    return a.week - b.week;
  }

  function seasonByNumber(num) {
    if (!meta) return null;
    for (var i = 0; i < meta.seasons.length; i++) {
      if (meta.seasons[i].number === num) return meta.seasons[i];
    }
    return null;
  }

  function weeksFor(num) {
    var s = seasonByNumber(num);
    return s && s.weeks && s.weeks.length ? s.weeks : [1];
  }

  function clampPos(p) {
    var season = seasonByNumber(p.season) ? p.season : (meta.current_season_number || meta.seasons[0].number);
    var weeks = weeksFor(season);
    var week = p.week;
    if (weeks.indexOf(week) === -1) {
      week = week < weeks[0] ? weeks[0] : weeks[weeks.length - 1];
    }
    return pos(season, week);
  }

  function fmt(value, digits) {
    if (value === null || value === undefined || value === "") return "\u2014";
    if (typeof value === "number") {
      if (digits === undefined) digits = 0;
      return value.toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      });
    }
    return String(value);
  }

  function esc(text) {
    return String(text === null || text === undefined ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* Over one week the high and low week are the same number as the average,
   * so those fields drop out of the teams list entirely. */
  var SINGLE_WEEK_HIDDEN = { high_week_avg: true, low_week_avg: true };

  /* The Bests lists carry their own fixed ordering, so that view has no sort
   * fields at all and every sort helper has to tolerate an empty list. */
  function isBests() { return !!state && state.view === "bests"; }
  function isPlayoffs() { return !!state && state.view === "playoffs"; }

  function fieldsFor(view) {
    if (view === "bests" || view === "playoffs") return [];
    var list = SORT_FIELDS[view] || SORT_FIELDS.players;
    if (view !== "teams" || !isSingle()) return list;
    return list.filter(function (f) { return !SINGLE_WEEK_HIDDEN[f.key]; });
  }

  function findField(view, key) {
    var list = fieldsFor(view);
    for (var i = 0; i < list.length; i++) if (list[i].key === key) return list[i];
    return null;
  }

  /* ---------------- state ---------------- */

  function defaultState() {
    var current = meta.current_season_number || (meta.seasons[0] && meta.seasons[0].number) || 1;
    var weeks = weeksFor(current);
    var latest = weeks[weeks.length - 1];
    return {
      span: "multi",
      start: pos(current, weeks[0]),
      end: pos(current, latest),
      week: pos(current, latest),
      playoffs: PLAYOFFS_DEFAULT,
      view: "players",
      sort: prefs.sortPlayers,
      dir: prefs.sortPlayersDir
    };
  }

  // Called from fieldsFor during preference loading, before state exists.
  function isSingle() { return !!state && state.span === "single"; }

  /* One week makes high week, low week, and the average the same number, so
   * the row shows the player-average form of the average. */
  function teamAvgKey() { return isSingle() ? "week_avg" : "avg_per_game"; }

  function initState() {
    state = defaultState();

    var stored = readSession();
    if (stored) {
      if (stored.span === "single" || stored.span === "multi") state.span = stored.span;
      if (stored.start) state.start = stored.start;
      if (stored.end) state.end = stored.end;
      if (stored.week) state.week = stored.week;
      var storedPo = normalizePlayoffs(stored.playoffs);
      if (storedPo) state.playoffs = storedPo;
      if (VIEWS.indexOf(stored.view) >= 0) state.view = stored.view;
      if (stored.sort) state.sort = stored.sort;
      if (stored.dir) state.dir = stored.dir;
    }

    // An explicit URL wins over stored state so links are shareable.
    var q = new URLSearchParams(window.location.search);
    var from = parsePosParam(q.get("from"));
    var to = parsePosParam(q.get("to"));
    var week = parsePosParam(q.get("week"));
    if (from) state.start = from;
    if (to) state.end = to;
    if (week) state.week = week;
    if (q.get("span") === "single" || q.get("span") === "multi") state.span = q.get("span");
    var urlPo = normalizePlayoffs(q.get("playoffs"));
    if (urlPo) state.playoffs = urlPo;
    if (VIEWS.indexOf(q.get("view")) >= 0) state.view = q.get("view");
    if (q.get("sort")) state.sort = q.get("sort");
    if (q.get("dir") === "asc" || q.get("dir") === "desc") state.dir = q.get("dir");

    state.start = clampPos(state.start);
    state.end = clampPos(state.end);
    state.week = clampPos(state.week);
    if (comparePos(state.start, state.end) > 0) {
      var tmp = state.start;
      state.start = state.end;
      state.end = tmp;
    }
    ensureSortField();
  }

  /* A sort field can vanish under the current span (the week figures in
   * single-week view), so fall back to the preferred field, then the default. */
  function ensureSortField() {
    if (isBests() || isPlayoffs()) return;
    if (findField(state.view, state.sort)) return;
    var isTeams = state.view === "teams";
    state.sort = isTeams ? prefs.sortTeams : prefs.sortPlayers;
    if (findField(state.view, state.sort)) return;
    state.sort = isTeams ? DEFAULT_PREFS.sortTeams : DEFAULT_PREFS.sortPlayers;
    var field = findField(state.view, state.sort);
    if (field) state.dir = field.dir;
  }

  function syncUrl() {
    var q = new URLSearchParams();
    if (isSingle()) {
      q.set("span", "single");
      q.set("week", posParam(state.week));
    }
    q.set("from", posParam(state.start));
    q.set("to", posParam(state.end));
    if (state.playoffs !== PLAYOFFS_DEFAULT) q.set("playoffs", state.playoffs);
    if (state.view !== "players") q.set("view", state.view);
    q.set("sort", state.sort);
    q.set("dir", state.dir);
    var next = window.location.pathname + "?" + q.toString();
    window.history.replaceState(null, "", next);
  }

  function persist() {
    saveSession();
    syncUrl();
  }

  /* ---------------- data ---------------- */

  /* Single-week collapses the range to one position, so the API needs no
   * notion of span - it just receives from === to. */
  function apiQuery() {
    var from = isSingle() ? state.week : state.start;
    var to = isSingle() ? state.week : state.end;
    var q = new URLSearchParams();
    q.set("from", posParam(from));
    q.set("to", posParam(to));
    q.set("mode", AGG_MODE);
    // The filter is hidden for a single week, so it must not silently apply -
    // asking for regular-season rows inside a playoff week returns nothing.
    // state.playoffs is left alone so flipping back to Range restores it.
    q.set("playoffs", isSingle() ? PLAYOFFS_DEFAULT : state.playoffs);
    return q.toString();
  }

  function setStatus(text, isError) {
    if (!text) {
      el.status.hidden = true;
      return;
    }
    el.status.hidden = false;
    el.status.textContent = text;
    el.status.classList.toggle("status--error", !!isError);
  }

  function load() {
    var token = ++fetchToken;
    detailCache = {};
    // Records are derived from the same facts, so a reload must not serve the
    // previous answer for an unchanged range.
    bestsCache = {};
    playoffsCache = {};
    openRow = null;
    showAllRows = false;
    setStatus("Loading\u2026");
    fetch("/api/leaderboard?" + apiQuery(), { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok) throw new Error(body.error || "Request failed");
          return body;
        });
      })
      .then(function (body) {
        if (token !== fetchToken) return;
        payload = body;
        assignRanks();
        setStatus("");
        renderAll();
      })
      .catch(function (err) {
        if (token !== fetchToken) return;
        payload = null;
        el.board.innerHTML = "";
        setStatus(err.message || "Could not load stats.", true);
      });
  }

  /* Canonical rank is assigned once from the API's default ordering, so
   * re-sorting the view never relabels who is #1. */
  function assignRanks() {
    ["players", "teams"].forEach(function (key) {
      (payload[key] || []).forEach(function (row, i) {
        row.rank = i + 1;
      });
    });
  }

  /* ---------------- sorting ---------------- */

  function sortRows(rows) {
    var field = findField(state.view, state.sort);
    if (!field) return rows.slice();
    var dir = state.dir === "asc" ? 1 : -1;
    // Order by whichever average is on screen, or the two disagree.
    var key = field.key === "avg_per_game" ? teamAvgKey() : field.key;

    return rows.slice().sort(function (a, b) {
      var av = a[key];
      var bv = b[key];

      // Missing values sort last in both directions, not as zero.
      var aMissing = av === null || av === undefined || av === "";
      var bMissing = bv === null || bv === undefined || bv === "";
      if (aMissing && bMissing) return a.rank - b.rank;
      if (aMissing) return 1;
      if (bMissing) return -1;

      var cmp;
      if (field.numeric) {
        cmp = av - bv;
      } else {
        cmp = String(av).localeCompare(String(bv), undefined, { sensitivity: "base" });
      }
      if (cmp === 0) return a.rank - b.rank;
      return cmp * dir;
    });
  }

  /* ---------------- rendering ---------------- */

  function renderAll() {
    renderRangeText();
    syncPresets();
    renderHighlights();
    renderTiles();
    renderSortControl();
    renderBoard();
    syncViewPanels();
  }

  /* Bests and Playoffs replace the leaderboard rather than sitting beside it,
   * and both make the sort bar and the highlight strip redundant. */
  function syncViewPanels() {
    var bests = isBests();
    var playoffs = isPlayoffs();
    el.panelLeaderboard.hidden = bests || playoffs;
    el.panelBests.hidden = !bests;
    el.panelPlayoffs.hidden = !playoffs;
    el.panelHighlights.hidden = bests || playoffs;
    if (el.panelLeague) el.panelLeague.hidden = bests || playoffs;
    // The bracket follows its own season selector, so the week/range flip has
    // nothing to act on. Greyed out rather than hidden so the tabbar holds its
    // shape as the reader moves between tabs.
    el.spanflip.classList.toggle("is-locked", playoffs);
    el.spanButtons.forEach(function (btn) { btn.disabled = playoffs; });
    if (playoffs) {
      el.spanflip.title = "The Playoffs tab uses its own season selector";
    } else {
      el.spanflip.removeAttribute("title");
    }
    if (bests) loadBests();
    if (playoffs) {
      syncPlayoffSeason();
      loadPlayoffs();
    }
  }

  function loadBests() {
    var key = apiQuery();
    if (bestsCache[key]) {
      renderBests(bestsCache[key]);
      return;
    }
    var token = ++bestsToken;
    setBestsStatus("Loading\u2026");
    el.bests.innerHTML = "";
    fetch("/api/bests?" + key, { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok) throw new Error(body.error || "Request failed");
          return body;
        });
      })
      .then(function (body) {
        if (token !== bestsToken) return;
        bestsCache[key] = body;
        setBestsStatus("");
        renderBests(body);
      })
      .catch(function (err) {
        if (token !== bestsToken) return;
        el.bests.innerHTML = "";
        setBestsStatus(err.message || "Could not load records.", true);
      });
  }

  function bestRow(entry, spec, place) {
    var name = entry.player || entry.team;
    // A player row names their team underneath; a team row is already named.
    var sub = entry.player ? entry.team : "";
    var tint = entry.color ? ' style="color:' + esc(entry.color) + '"' : "";
    var detail = entry.when || "";
    if (entry.average !== undefined) {
      detail = fmt(entry.average, 2) + (detail ? " \u00b7 " + detail : "");
    }
    return (
      '<li class="best-row">' +
      '<span class="best-place">' + place + "</span>" +
      '<span class="best-id">' +
      '<span class="best-name"' + (entry.player ? "" : tint) + ">" + esc(name) + "</span>" +
      (sub ? '<span class="best-sub"' + tint + ">" + esc(sub) + "</span>" : "") +
      "</span>" +
      '<span class="best-value">' + fmt(entry.score, spec.digits) +
      (spec.unit ? '<span class="best-unit">' + esc(spec.unit) + "</span>" : "") +
      "</span>" +
      (detail ? '<span class="best-when">' + esc(detail) + "</span>" : "") +
      "</li>"
    );
  }

  function bestSection(spec, entries) {
    var expanded = !!bestsExpanded[spec.key];
    var open = !!prefs.bestsOpen[spec.key];
    var bodyId = "bests-body-" + spec.key;
    var shown = expanded ? entries : entries.slice(0, BESTS_PREVIEW);
    var more = entries.length > BESTS_PREVIEW
      ? '<div class="best-more"><button type="button" class="btn btn--ghost" ' +
        'data-bests-more="' + esc(spec.key) + '">' +
        (expanded ? "Show fewer" : "Show all " + entries.length) + "</button></div>"
      : "";
    return (
      '<section class="best-card' + (open ? " is-open" : "") + '">' +
      '<h3 class="best-head-wrap">' +
      '<button type="button" class="best-head" data-bests-toggle="' + esc(spec.key) + '" ' +
      'aria-expanded="' + (open ? "true" : "false") + '" aria-controls="' + bodyId + '">' +
      '<span class="best-title">' + esc(spec.title) + "</span>" +
      '<span class="best-count">' + entries.length + "</span>" +
      '<span class="chev" aria-hidden="true"></span>' +
      "</button></h3>" +
      '<div class="best-body" id="' + bodyId + '"' + (open ? "" : " hidden") + ">" +
      '<ol class="best-list">' +
      shown.map(function (e, i) { return bestRow(e, spec, i + 1); }).join("") +
      "</ol>" + more +
      "</div></section>"
    );
  }

  function renderBests(data) {
    var cats = (data && data.categories) || {};
    var html = BEST_SECTIONS.map(function (spec) {
      var entries = cats[spec.key] || [];
      // An empty list means the range cannot support that record at all, most
      // often most-improved inside a single season. Saying nothing beats an
      // empty card.
      return entries.length ? bestSection(spec, entries) : "";
    }).join("");

    el.bests.innerHTML = html;
    if (!html) setBestsStatus("No records in this range.");
  }

  function setBestsStatus(text, isError) {
    if (!text) {
      el.bestsStatus.hidden = true;
      return;
    }
    el.bestsStatus.hidden = false;
    el.bestsStatus.textContent = text;
    el.bestsStatus.classList.toggle("status--error", !!isError);
  }

  /* ---------------- playoffs ---------------- */

  function syncPlayoffSeason() {
    if (!playoffSeason) {
      playoffSeason = meta.current_season ||
        (meta.seasons[0] && meta.seasons[0].label) || null;
    }
    if (!el.playoffSeason.options.length) {
      el.playoffSeason.innerHTML = meta.seasons.map(function (s) {
        return '<option value="' + esc(s.label) + '">' + esc(s.label) + "</option>";
      }).join("");
    }
    if (playoffSeason) el.playoffSeason.value = playoffSeason;
  }

  function loadPlayoffs() {
    var season = playoffSeason || "";
    if (playoffsCache[season]) {
      renderPlayoffs(playoffsCache[season]);
      return;
    }
    var token = ++playoffsToken;
    setPlayoffsStatus("Loading\u2026");
    el.playoffUpcoming.innerHTML = "";
    el.playoffRounds.innerHTML = "";
    el.playoffSeeds.innerHTML = "";
    el.playoffHistory.innerHTML = "";
    fetch("/api/playoffs?season=" + encodeURIComponent(season), {
      headers: { Accept: "application/json" }
    })
      .then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok) throw new Error(body.error || "Request failed");
          return body;
        });
      })
      .then(function (body) {
        if (token !== playoffsToken) return;
        playoffsCache[season] = body;
        setPlayoffsStatus("");
        renderPlayoffs(body);
      })
      .catch(function (err) {
        if (token !== playoffsToken) return;
        setPlayoffsStatus(err.message || "Could not load playoffs.", true);
      });
  }

  function setPlayoffsStatus(text, isError) {
    if (!text) {
      el.playoffsStatus.hidden = true;
      return;
    }
    el.playoffsStatus.hidden = false;
    el.playoffsStatus.textContent = text;
    el.playoffsStatus.classList.toggle("status--error", !!isError);
  }

  /* Always a cell, empty or not, so seedless rows keep the columns aligned. */
  function seedTag(seed) {
    return '<span class="mu-seed">' + (seed ? seed : "") + "</span>";
  }

  /* `record` is where the team stood going into this week; `scoreHtml` is the
   * matchup score, which the caller puts on one row only. */
  function matchupSide(name, seed, color, record, scoreHtml, result) {
    if (!name) {
      return '<div class="mu-side is-bye"><span class="mu-team">Bye</span></div>';
    }
    var tint = color ? ' style="color:' + esc(color) + '"' : "";
    var mark = result && result !== "\u2014"
      ? '<span class="mu-mark mu-mark--' + esc(result.toLowerCase()) + '">' +
        esc(result) + "</span>"
      : "";
    return (
      '<div class="mu-side' + (result === "W" ? " is-winner" : "") + '">' +
      seedTag(seed) +
      '<span class="mu-team"' + tint + ">" + esc(name) + "</span>" +
      // Its own cell, so the name's ellipsis cannot eat the record. Always
      // emitted, even when empty, to keep the two sides' grids in step.
      '<span class="mu-record">' + esc(record || "") + "</span>" +
      (scoreHtml || "") +
      mark +
      "</div>"
    );
  }

  /* Games won by each side, each number in its own team's colour. It belongs to
   * the matchup rather than a side, so it is drawn once on the top row and the
   * bottom row gets an empty cell to keep the two grids in step. */
  function matchupScore(m) {
    if (typeof m.home_game_wins !== "number" ||
        typeof m.away_game_wins !== "number") {
      return "";
    }
    function part(wins, color) {
      var tint = color ? ' style="color:' + esc(color) + '"' : "";
      return "<span" + tint + ">" + wins + "</span>";
    }
    return (
      '<span class="mu-games">' +
      part(m.home_game_wins, m.home_color) + "-" +
      part(m.away_game_wins, m.away_color) +
      "</span>"
    );
  }

  function matchupCard(m) {
    var score = matchupScore(m);
    return (
      '<div class="matchup' + (m.projected ? " is-projected" : "") + '">' +
      (m.label ? '<div class="mu-label">' + esc(m.label) + "</div>" : "") +
      matchupSide(m.home, m.home_seed, m.home_color, m.home_record,
                  score, m.home_result) +
      matchupSide(m.away, m.away_seed, m.away_color, m.away_record,
                  score ? '<span class="mu-games"></span>' : "", m.away_result) +
      (m.record_overridden ? '<div class="mu-note">Adjusted record</div>' : "") +
      "</div>"
    );
  }

  /* Every playoff section is one collapsible card. `title` and `flag` are
   * already-escaped HTML because a round title mixes text with a week number. */
  function poSection(key, title, flag, body, extraClass) {
    var open = !!playoffsOpen[key];
    var bodyId = "po-body-" + key;
    return (
      '<section class="po-card' + (extraClass ? " " + extraClass : "") +
      (open ? " is-open" : "") + '">' +
      '<h3 class="po-head-wrap">' +
      '<button type="button" class="po-head" data-po-toggle="' + esc(key) + '" ' +
      'aria-expanded="' + (open ? "true" : "false") + '" aria-controls="' + bodyId + '">' +
      '<span class="po-title">' + title + "</span>" +
      (flag || "") +
      '<span class="chev" aria-hidden="true"></span>' +
      "</button></h3>" +
      '<div class="po-body" id="' + bodyId + '"' + (open ? "" : " hidden") + ">" +
      body +
      "</div></section>"
    );
  }

  function roundSection(group, key, extraClass) {
    var title = esc(group.label || "Playoffs") +
      (group.week ? " \u00b7 Week " + group.week : "");
    return poSection(
      key,
      title,
      group.projected ? '<span class="po-flag">Projected</span>' : "",
      '<div class="mu-list">' +
        (group.matchups || []).map(matchupCard).join("") +
        "</div>",
      extraClass
    );
  }

  function renderPlayoffs(data) {
    var upcoming = data && data.upcoming;
    el.playoffUpcoming.innerHTML = upcoming
      ? roundSection(upcoming, "next", "")
      : "";

    var rounds = (data && data.rounds) || [];
    // Newest round first so the reader lands on the most recent results.
    el.playoffRounds.innerHTML = rounds
      .slice()
      .reverse()
      .map(function (r) { return roundSection(r, "round-" + r.week, ""); })
      .join("");

    /* Seed order and numbers come from the frozen playoff seeding, but the
     * records shown run through the newest week bowled. */
    var standings = (data && (data.standings || data.seeds)) || [];
    var throughWeek = data && (data.last_week || data.last_regular_week);
    el.playoffSeeds.innerHTML = standings.length
      ? poSection(
          "standings",
          "Standings",
          throughWeek
            ? '<span class="po-flag">Through week ' + throughWeek + "</span>"
            : "",
          '<ol class="seed-list">' +
            standings.map(function (row) {
              var tint = row.color ? ' style="color:' + esc(row.color) + '"' : "";
              return (
                '<li class="seed-row">' +
                '<span class="mu-seed">' + row.seed + "</span>" +
                '<span class="seed-team"' + tint + ">" + esc(row.team) + "</span>" +
                '<span class="seed-record">' + esc(row.record || "") + "</span>" +
                '<span class="seed-pins">' + fmt(row.pins_for, 0) + "</span>" +
                "</li>"
              );
            }).join("") +
            "</ol>"
        )
      : "";

    var history = ((data && data.history) || []).filter(function (h) {
      return !!h.champion;
    });
    el.playoffHistory.innerHTML = history.length
      ? poSection(
          "history",
          "Season Winners",
          "",
          '<ol class="champ-list">' +
            history.map(function (h) {
              var tint = h.champion_color
                ? ' style="color:' + esc(h.champion_color) + '"'
                : "";
              return (
                '<li class="champ-row">' +
                '<span class="champ-season">' + esc(h.season) + "</span>" +
                '<span class="champ-team"' + tint + ">\uD83C\uDFC6 " +
                esc(h.champion) + "</span></li>"
              );
            }).join("") +
            "</ol>"
        )
      : "";

    if (!upcoming && !rounds.length && !standings.length) {
      setPlayoffsStatus("No playoff data for this season yet.");
    }
  }

  function renderRangeText() {
    var text;
    if (isSingle()) {
      text = posText(state.week);
    } else {
      text = posText(state.start) + " \u2013 " + posText(state.end);
    }
    el.rangePillText.textContent = text;
    // Shown inside the panel so the range stays visible when the panel is
    // inline in the desktop rail and the pill is hidden.
    if (el.filterRangeText) el.filterRangeText.textContent = text;

    // Mirrors the weeks-counted control, so it goes quiet alongside it.
    var tag = isSingle() ? "" : PLAYOFF_LABELS[state.playoffs];
    [el.rangePillTag, el.filterRangeTag].forEach(function (node) {
      if (!node) return;
      node.textContent = tag;
      node.hidden = !tag;
    });

    var covered = payload && payload.scope && payload.scope.seasons_covered;
    if (covered && covered.length) {
      el.rangeHint.textContent =
        covered.length === 1
          ? "Season " + covered[0]
          : covered.length + " seasons: " + covered.join(", ");
    } else {
      el.rangeHint.textContent = "";
    }
  }

  /* `o.teamLine` names which of the two text lines holds the team, so the
   * team's colour lands on it. Inline because .hl-sub sets its own colour. */
  function highlightCard(o) {
    function line(cls, text, isTeam) {
      if (!text) return "";
      var tint = isTeam && o.color ? ' style="color:' + esc(o.color) + '"' : "";
      return '<div class="' + cls + '"' + tint + ">" + esc(text) + "</div>";
    }
    return (
      '<article class="hl-card ' + o.cls + '">' +
      '<div class="hl-head"><span aria-hidden="true">' + o.icon + "</span>" +
      /* One span, because .hl-head is a flex row and its gap would otherwise
       * detach the suffix from the label it belongs to. */
      '<span>' + esc(o.head) +
      (o.headSuffix
        ? '<span class="hl-head-plain">' + esc(o.headSuffix) + "</span>"
        : "") +
      "</span></div>" +
      '<div class="hl-score">' + esc(o.score) +
      (o.unit ? '<span class="hl-score-unit">' + esc(o.unit) + "</span>" : "") +
      "</div>" +
      line("hl-name", o.name, o.teamLine === "name") +
      line("hl-sub", o.sub, o.teamLine === "sub") +
      line("hl-when", o.when, false) +
      "</article>"
    );
  }

  /* The strip follows the tab: player scores on Players, team weeks on Teams. */
  function renderHighlights() {
    var h = (payload && payload.highlights) || {};
    var cards = [];

    if (state.view === "teams") {
      if (h.team_high) {
        cards.push(highlightCard({
          cls: "hl-card--violet", icon: "\u{1F4C8}", head: "Team High Week",
          score: fmt(h.team_high.score, 2), unit: "avg", name: h.team_high.team,
          when: h.team_high.when, color: h.team_high.color, teamLine: "name"
        }));
      }
      if (h.team_low) {
        cards.push(highlightCard({
          cls: "hl-card--bad", icon: "\u{1F4C9}", head: "Team Low Week",
          score: fmt(h.team_low.score, 2), unit: "avg", name: h.team_low.team,
          when: h.team_low.when, color: h.team_low.color, teamLine: "name"
        }));
      }
      el.highlights.innerHTML = cards.length
        ? cards.join("")
        : '<p class="detail-empty">No games in this range.</p>';
      return;
    }

    if (h.high_game) {
      cards.push(highlightCard({
        cls: "hl-card--good", icon: "\u{1F3C6}", head: "High Game",
        score: fmt(h.high_game.score), name: h.high_game.player,
        sub: h.high_game.team, when: h.high_game.when,
        color: h.high_game.color, teamLine: "sub"
      }));
    }
    if (h.low_game) {
      cards.push(highlightCard({
        cls: "hl-card--bad", icon: "\u{1F4C9}", head: "Low Game",
        score: fmt(h.low_game.score), name: h.low_game.player,
        sub: h.low_game.team, when: h.low_game.when,
        color: h.low_game.color, teamLine: "sub"
      }));
    }

    /* Over one night these three either duplicate a leaderboard column or rest
     * on a three-game sample, so they are range-only. */
    if (!isSingle()) {
      if (h.high_week) {
        cards.push(highlightCard({
          cls: "hl-card--violet", icon: "\u{1F525}", head: "High Week",
          score: fmt(h.high_week.score, 2), unit: "avg",
          name: h.high_week.player, sub: h.high_week.team,
          when: h.high_week.when, color: h.high_week.color, teamLine: "sub"
        }));
      }
      if (h.most_200s) {
        cards.push(highlightCard({
          cls: "hl-card--good", icon: "\u{1F3AF}", head: "Most 200",
          headSuffix: "s",
          score: fmt(h.most_200s.score), unit: "games",
          name: h.most_200s.player, sub: h.most_200s.team,
          color: h.most_200s.color, teamLine: "sub"
        }));
      }
      if (h.consistent) {
        cards.push(highlightCard({
          cls: "hl-card--violet", icon: "\u{1F4CF}", head: "Most Consistent",
          score: fmt(h.consistent.score, 2), unit: "st dev",
          name: h.consistent.player, sub: h.consistent.team,
          color: h.consistent.color, teamLine: "sub"
        }));
      }
    }

    el.highlights.innerHTML = cards.length
      ? cards.join("")
      : '<p class="detail-empty">No games in this range.</p>';
  }

  function renderTiles() {
    var lg = (payload && payload.league) || {};
    // The count follows the tab, so the strip is about whatever is listed.
    var countTile = state.view === "teams"
      ? { value: fmt(lg.total_teams), label: "Teams" }
      : { value: fmt(lg.total_players), label: "Players" };
    var tiles = [
      { value: fmt(lg.league_avg, 2), label: "League Avg" },
      countTile,
      { value: fmt(lg.games_200_plus), label: "200+ Games" },
      { value: fmt(lg.total_games), label: "Total Games" }
    ];
    el.leagueTiles.innerHTML = tiles
      .map(function (t) {
        return (
          '<div class="tile"><div class="tile-value">' + esc(t.value) +
          '</div><div class="tile-label">' + esc(t.label) + "</div></div>"
        );
      })
      .join("");
  }

  function renderSortControl() {
    var list = fieldsFor(state.view);
    var parAvailable = !payload || payload.par_available !== false;

    el.sortField.innerHTML = list
      .map(function (f) {
        var disabled = f.needsPar && !parAvailable;
        return (
          '<option value="' + esc(f.key) + '"' +
          (disabled ? " disabled" : "") +
          (state.sort === f.key ? " selected" : "") +
          ">" + esc(f.label) + (disabled ? " (single season only)" : "") + "</option>"
        );
      })
      .join("");

    var asc = state.dir === "asc";
    el.sortDirArrow.textContent = asc ? "\u2191" : "\u2193";
    var field = findField(state.view, state.sort);
    if (field && !field.numeric) {
      el.sortDirText.textContent = asc ? "A \u2192 Z" : "Z \u2192 A";
    } else {
      el.sortDirText.textContent = asc ? "Low \u2192 high" : "High \u2192 low";
    }
  }

  function isSubOnly(row) {
    return !!row.sub_games && row.sub_games === row.games;
  }

  /* Sub games count toward the average, so a sub-only player ranks normally;
   * the tag explains that every one of those games came filling in. */
  function playerRowTag(row) {
    if (isSubOnly(row)) return '<span class="row-tag row-tag--sub">SUB</span>';
    if (!row.games && row.absences) {
      return '<span class="row-tag row-tag--abs">ABS</span>';
    }
    return "";
  }

  /* The team on a sub-only row is just whoever they last filled in for, which
   * is misleading on its own, so name the player instead. */
  function playerRowSubtitle(row) {
    if (isSubOnly(row) && row.sub_for && row.sub_for.length) {
      return "sub for " + row.sub_for.join(", ");
    }
    return row.team;
  }

  function figureLine(label, value, o) {
    o = o || {};
    var cls =
      "fig-line" +
      (o.extra ? " fig-line--extra" : "") +
      (o.sorted ? " fig-line--sorted" : "");
    return (
      '<div class="' + cls + '"><span class="' +
      (o.keyLabel ? "fig-key" : "fig-label") + '">' + esc(label) +
      '</span> <span class="' + (o.cls || "fig-val") + '">' +
      fmt(value, o.digits) + "</span></div>"
    );
  }

  /* The row property the board is ordered by, or null when it is ordered by a
   * name. Resolves the team average the same way sortRows does, so the figure
   * marked as sorted is the one actually doing the ordering. */
  function sortedFigureKey() {
    var field = findField(state.view, state.sort);
    if (!field || !field.numeric) return null;
    // A disabled PAR sort leaves every row null; nothing worth showing.
    if (field.needsPar && payload && payload.par_available === false) return null;
    return field.key === "avg_per_game" ? teamAvgKey() : field.key;
  }

  /* The fourth figure follows the sort whenever the first three do not already
   * show it, so the number the list is ranked by is visible without expanding
   * the row. In its default form it stays desktop-only, but it comes along to
   * mobile while carrying the sort, since there it is the point of the view. */
  function sortSlotFigure(view, shownKeys, sortedKey, row, fallback) {
    var spec = sortedKey && shownKeys.indexOf(sortedKey) < 0
      ? FIGURE_SPECS[view][sortedKey]
      : null;
    if (spec) {
      return figureLine(spec.label, row[spec.key], {
        digits: spec.digits, cls: spec.cls, sorted: true
      });
    }
    return figureLine(fallback.label, row[fallback.key], {
      extra: true, sorted: sortedKey === fallback.key
    });
  }

  function playerFigures(row) {
    var sorted = sortedFigureKey();
    // A credited average is not a bowled one. The tinted value carries that on
    // its own, so the label stays the same as every other row's.
    var credited = row.average_from_absences;
    var lines = [
      figureLine("Avg", row.average, {
        digits: 2,
        keyLabel: true,
        cls: credited ? "fig-val fig-val--credited" : "fig-val",
        sorted: sorted === "average"
      }),
      figureLine("High", row.highest_game, {
        cls: "fig-good", sorted: sorted === "highest_game"
      }),
      figureLine("Low", row.lowest_game, {
        cls: "fig-bad", sorted: sorted === "lowest_game"
      })
    ];
    lines.push(
      sortSlotFigure(
        "players",
        ["average", "highest_game", "lowest_game"],
        sorted,
        row,
        { key: "games", label: "Games" }
      )
    );
    return lines.join("");
  }

  function teamFigures(row) {
    var sorted = sortedFigureKey();
    var avgKey = teamAvgKey();
    var shown = [avgKey, "high_game"];
    var lines = [
      figureLine("Avg", row[avgKey], {
        digits: 2, keyLabel: true, sorted: sorted === avgKey
      })
    ];
    if (!isSingle()) {
      shown.push("high_week_avg");
      lines.push(
        figureLine("High week", row.high_week_avg, {
          digits: 2, cls: "fig-good", sorted: sorted === "high_week_avg"
        })
      );
    }
    lines.push(
      figureLine("High game", row.high_game, {
        cls: "fig-good", sorted: sorted === "high_game"
      })
    );
    lines.push(
      sortSlotFigure("teams", shown, sorted, row, {
        key: "total_pins", label: "Pins"
      })
    );
    return lines.join("");
  }

  /* Shown only when a cap is actually in play, so it offers the way back once
   * the list is expanded rather than disappearing at the moment it is needed. */
  function renderBoardMore(total) {
    var capped = prefs.rowLimit > 0 && total > prefs.rowLimit;
    el.boardMore.hidden = !capped;
    el.boardMore.innerHTML = capped
      ? '<button type="button" class="btn btn--ghost" id="board-more-btn">' +
        (showAllRows ? "Show fewer" : "Show all " + total) + "</button>"
      : "";
  }

  function renderBoard() {
    if (!payload) return;
    var isTeams = state.view === "teams";
    var rows = sortRows((isTeams ? payload.teams : payload.players) || []);

    if (!rows.length) {
      el.board.innerHTML = "";
      el.boardMore.hidden = true;
      el.boardMore.innerHTML = "";
      setStatus("No " + (isTeams ? "teams" : "players") + " in this range.");
      return;
    }
    setStatus("");

    var total = rows.length;
    if (!showAllRows && prefs.rowLimit > 0) rows = rows.slice(0, prefs.rowLimit);
    renderBoardMore(total);

    el.board.innerHTML = rows
      .map(function (row) {
        var id = isTeams ? row.team : row.player;
        var name = id;
        // One week needs no week count, and "1 weeks" reads badly.
        var sub = isTeams
          ? (isSingle() ? "" : row.weeks + " weeks")
          : playerRowSubtitle(row);
        var tag = isTeams ? "" : playerRowTag(row);
        var figs = isTeams ? teamFigures(row) : playerFigures(row);

        // The team's own colour goes on whichever line carries the team name.
        var tint = row.color ? ' style="color:' + esc(row.color) + '"' : "";
        var subLine = (sub || tag)
          ? '<span class="row-team"' + (isTeams ? "" : tint) + ">" + esc(sub) +
            tag + "</span>"
          : "";

        return (
          '<li class="row" data-id="' + esc(id) + '">' +
          '<button type="button" class="row-main" aria-expanded="false">' +
          '<span class="rank">#' + row.rank + "</span>" +
          '<span class="row-id">' +
          '<span class="row-name"' + (isTeams ? tint : "") + ">" + esc(name) + "</span>" +
          subLine +
          "</span>" +
          '<span class="row-figs">' + figs + "</span>" +
          '<span class="chev" aria-hidden="true"></span>' +
          "</button>" +
          '<div class="row-detail" hidden></div>' +
          "</li>"
        );
      })
      .join("");
  }

  /* ---------------- row expansion ---------------- */

  function rowData(id) {
    var list = (state.view === "teams" ? payload.teams : payload.players) || [];
    for (var i = 0; i < list.length; i++) {
      if ((state.view === "teams" ? list[i].team : list[i].player) === id) return list[i];
    }
    return null;
  }

  /* Namespaced so a team and a player sharing a name cannot collide. */
  function detailKey(row) {
    return state.view + ":" + (state.view === "teams" ? row.team : row.player);
  }

  function statBlock(pairs) {
    return (
      '<div class="detail-grid">' +
      pairs
        .map(function (p) {
          return (
            '<div class="detail-stat"><div class="detail-stat-label">' + esc(p[0]) +
            '</div><div class="detail-stat-value">' + esc(p[1]) + "</div></div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  /* A scaled-to-fit line chart over `points`, each {value, label, tone}. The
   * two dashed reference lines are the series' own average and the league's.
   * Dots carry a native title tooltip, so the chart needs no script. */
  function trendChart(points, opts) {
    var live = (points || []).filter(function (p) {
      return typeof p.value === "number" && !isNaN(p.value);
    });
    if (live.length < 2) return "";

    var o = opts || {};
    var W = 420, H = 200;
    var ml = 34, mr = 8, mt = 10, mb = 22;
    var plotW = W - ml - mr;
    var plotH = H - mt - mb;

    var values = live.map(function (p) { return p.value; });
    var refs = [o.average, o.leagueAverage].filter(function (v) {
      return typeof v === "number" && v > 0;
    });
    var lo = Math.min.apply(null, values.concat(refs));
    var hi = Math.max.apply(null, values.concat(refs));
    // A flat series would give a zero-height plot, so always keep some spread.
    var pad = Math.max(10, (hi - lo) * 0.15);
    lo = Math.max(0, Math.floor((lo - pad) / 10) * 10);
    hi = Math.ceil((hi + pad) / 10) * 10;

    function x(i) {
      return live.length < 2
        ? ml + plotW / 2
        : ml + (plotW * i) / (live.length - 1);
    }
    function y(v) {
      return mt + plotH - ((v - lo) / (hi - lo)) * plotH;
    }

    var parts = [];
    [hi, (hi + lo) / 2, lo].forEach(function (v) {
      var gy = y(v).toFixed(1);
      parts.push(
        '<line class="prof-grid" x1="' + ml + '" y1="' + gy +
        '" x2="' + (W - mr) + '" y2="' + gy + '"></line>',
        '<text class="prof-axis" x="' + (ml - 6) + '" y="' + (y(v) + 3).toFixed(1) +
        '" text-anchor="end">' + Math.round(v) + "</text>"
      );
    });

    refs.forEach(function (v, idx) {
      var cls = idx === 0 && typeof o.average === "number" && o.average > 0
        ? "prof-avg"
        : "prof-league";
      parts.push(
        '<line class="' + cls + '" x1="' + ml + '" y1="' + y(v).toFixed(1) +
        '" x2="' + (W - mr) + '" y2="' + y(v).toFixed(1) + '"></line>'
      );
    });

    parts.push(
      '<polyline class="prof-line" points="' +
      live.map(function (p, i) { return x(i).toFixed(1) + "," + y(p.value).toFixed(1); })
        .join(" ") +
      '"></polyline>'
    );

    /* A 3px dot in a chart scaled down to card width is far too small to point
     * at, so each one is paired with an invisible, much larger target. The
     * reading itself rides on the group as `data-tip`; a native <title> would
     * never show on touch and takes a long hover on a desktop. */
    live.forEach(function (p, i) {
      var cls = "prof-dot" + (p.tone ? " prof-dot--" + esc(p.tone) : "");
      var cx = x(i).toFixed(1);
      var cy = y(p.value).toFixed(1);
      parts.push(
        '<g class="prof-point" tabindex="0" data-tip="' +
        esc((p.label ? p.label + " \u00b7 " : "") + fmt(p.value, o.decimals || 0)) +
        '"><circle class="' + cls + '" cx="' + cx + '" cy="' + cy + '" r="3"></circle>' +
        '<circle class="prof-hit" cx="' + cx + '" cy="' + cy + '" r="11"></circle>' +
        "</g>"
      );
    });

    // Only the ends are labelled; one label per point crowds a narrow card.
    parts.push(
      '<text class="prof-axis" x="' + ml + '" y="' + (H - 6) +
      '" text-anchor="start">' + esc(live[0].label || "") + "</text>",
      '<text class="prof-axis" x="' + (W - mr) + '" y="' + (H - 6) +
      '" text-anchor="end">' + esc(live[live.length - 1].label || "") + "</text>"
    );

    return (
      // The wrapper is the tooltip's positioning context.
      '<div class="prof-plot"><div class="prof-tip" hidden></div>' +
      // No role="img": that hides the points, and with them their tooltips.
      '<svg class="prof-chart" viewBox="0 0 ' + W + " " + H +
      '" aria-label="' + esc(o.label || "Trend") + '">' +
      parts.join("") +
      "</svg></div>" +
      '<p class="prof-legend">' +
      (typeof o.average === "number" && o.average > 0
        ? '<span class="prof-key prof-key--avg"></span>own avg ' +
          fmt(o.average, 2) + " "
        : "") +
      (typeof o.leagueAverage === "number" && o.leagueAverage > 0
        ? '<span class="prof-key prof-key--league"></span>league avg ' +
          fmt(o.leagueAverage, 2)
        : "") +
      "</p>"
    );
  }

  /* The tooltip is placed from measured geometry rather than the viewBox, since
   * the chart is scaled to whatever width the card happens to have. */
  function showChartTip(point) {
    var plot = point.closest(".prof-plot");
    if (!plot) return;
    var tip = plot.querySelector(".prof-tip");
    if (!tip) return;

    var prev = plot.querySelector(".prof-point--active");
    if (prev) prev.classList.remove("prof-point--active");
    point.classList.add("prof-point--active");

    tip.textContent = point.getAttribute("data-tip") || "";
    tip.hidden = false;

    var pr = plot.getBoundingClientRect();
    var gr = point.getBoundingClientRect();
    var half = tip.offsetWidth / 2;
    var cx = gr.left - pr.left + gr.width / 2;
    // Kept inside the card, so an end point does not hang off the edge.
    tip.style.left = Math.min(Math.max(cx, half + 2), pr.width - half - 2) + "px";
    tip.style.top = gr.top - pr.top + "px";
  }

  function hideChartTip(plot) {
    if (!plot) return;
    var tip = plot.querySelector(".prof-tip");
    if (tip) tip.hidden = true;
    var active = plot.querySelector(".prof-point--active");
    if (active) active.classList.remove("prof-point--active");
  }

  /* One block per season, since a range can cross a roster change. `groups`
   * comes straight from the API as [{label, members: [{name, sub}]}]. */
  function membersSection(key, title, groups) {
    if (!groups || !groups.length) return "";
    var body = groups
      .map(function (g) {
        return (
          '<div class="mem-season">' + esc(g.label) + "</div>" +
          '<div class="mem-list">' +
          (g.members || [])
            .map(function (m) {
              return (
                '<span class="mem">' + esc(m.name) +
                (m.sub ? ' <span class="wk-tag wk-tag--sub">sub</span>' : "") +
                "</span>"
              );
            })
            .join("") +
          "</div>"
        );
      })
      .join("");
    return profileSection(key, title, body);
  }

  /* Collapsible, same open/close vocabulary as the bests and playoff cards. */
  function profileSection(key, title, bodyHtml) {
    if (!bodyHtml) return "";
    var open = !!profilesOpen[key];
    var bodyId = "prof-body-" + key.replace(/[^a-zA-Z0-9_-]/g, "-");
    return (
      '<div class="prof' + (open ? " is-open" : "") + '">' +
      '<button type="button" class="prof-toggle" data-prof-toggle="' + esc(key) + '" ' +
      'aria-expanded="' + (open ? "true" : "false") + '" aria-controls="' + bodyId + '">' +
      "<span>" + esc(title) + "</span>" +
      '<span class="chev" aria-hidden="true"></span>' +
      "</button>" +
      '<div class="prof-body" id="' + bodyId + '"' + (open ? "" : " hidden") + ">" +
      bodyHtml +
      "</div></div>"
    );
  }

  /* Weeks the player sat out carry no games, so they are merged in by
   * (season, week) rather than appended, keeping the gap in its real place. */
  function groupByWeek(games, absentWeeks) {
    var byWeek = {};
    var order = [];

    function bucket(label, season, week) {
      if (!byWeek[label]) {
        byWeek[label] = {
          label: label,
          season: season,
          week: week,
          games: [],
          absent: false,
          absentAverage: null,
          absentGames: []
        };
        order.push(byWeek[label]);
      }
      return byWeek[label];
    }

    games.forEach(function (g) {
      bucket(g.label, g.season, g.week).games.push(g);
    });
    (absentWeeks || []).forEach(function (w) {
      var b = bucket(w.label, w.season, w.week);
      b.absent = true;
      b.absentAverage = w.average;
      b.absentGames = w.games || [];
    });

    order.sort(function (a, b) {
      return a.season - b.season || a.week - b.week;
    });
    return order;
  }

  function gameChips(games, high, low) {
    return games
      .map(function (g) {
        var cls = "game-chip";
        var title;
        if (g.game_absent) {
          cls += " game-chip--miss";
          title = "Missed game " + g.game + " \u2014 book average taken";
        } else {
          if (g.score === high) cls += " game-chip--hi";
          else if (g.score === low) cls += " game-chip--lo";
        }
        if (g.is_substitute) {
          cls += " game-chip--sub";
          title = g.substituted_for ? "Subbing for " + g.substituted_for : "Subbing in";
        }
        var attr = title ? ' title="' + esc(title) + '"' : "";
        return '<span class="' + cls + '"' + attr + ">" + fmt(g.score) + "</span>";
      })
      .join("");
  }

  /* Single-week shows every game; a multi-week range would run to dozens of
   * chips, so it collapses to one summary line per week instead. */
  function subbedForIn(games) {
    var names = [];
    games.forEach(function (g) {
      if (g.is_substitute && g.substituted_for && names.indexOf(g.substituted_for) < 0) {
        names.push(g.substituted_for);
      }
    });
    return names;
  }

  function weekTags(week) {
    var tags = "";
    if (week.games.some(function (g) { return g.is_substitute; })) {
      var names = subbedForIn(week.games);
      var label = names.length ? "sub for " + names.join(", ") : "sub";
      tags += '<span class="wk-tag wk-tag--sub">' + esc(label) + "</span>";
    }
    if (week.games.some(function (g) { return g.game_absent; })) {
      tags += '<span class="wk-tag wk-tag--miss">miss</span>';
    }
    return tags;
  }

  function gamesLegend(weeks) {
    var anySub = false;
    var anyMiss = false;
    var anyAbsent = false;
    weeks.forEach(function (w) {
      if (w.absent) anyAbsent = true;
      w.games.forEach(function (g) {
        if (g.is_substitute) anySub = true;
        if (g.game_absent) anyMiss = true;
      });
    });
    // Text only: a sample chip here reads as a bowled score.
    var parts = [];
    if (anySub) parts.push("dashed = subbing in");
    if (anyMiss) parts.push("struck through = missed, book average taken");
    if (anyAbsent) {
      parts.push("absent weeks show the average credited, not bowled");
    }
    if (!parts.length) return "";
    return (
      '<div class="games-legend">' + esc(parts.join(" \u00b7 ")) + "</div>"
    );
  }

  /* An absent week still has a credited score, filled from the player's book
   * average, so show it rather than leaving the week blank. */
  function absentLabel(week) {
    if (week.absentAverage === null || week.absentAverage === undefined) {
      return "Absent";
    }
    return "Absent \u00b7 " + fmt(week.absentAverage, 1) + " credited";
  }

  function absentBody(week) {
    var chips = (week.absentGames || [])
      .map(function (score) {
        return (
          '<span class="game-chip game-chip--miss" title="Credited, not bowled">' +
          fmt(score) + "</span>"
        );
      })
      .join("");
    return (
      '<div class="games-absent">' + esc(absentLabel(week)) + "</div>" +
      (chips ? '<div class="games">' + chips + "</div>" : "")
    );
  }

  function gamesMarkup(games, high, low, absentWeeks) {
    games = games || [];
    if (!games.length && !(absentWeeks && absentWeeks.length)) return "";
    var weeks = groupByWeek(games, absentWeeks);

    if (isSingle()) {
      var groups = weeks.map(function (w) {
        var body = w.games.length
          ? '<div class="games">' + gameChips(w.games, high, low) + "</div>"
          : absentBody(w);
        return (
          '<div class="games-group"><div class="games-group-label">' + esc(w.label) +
          weekTags(w) + "</div>" + body + "</div>"
        );
      });
      return (
        '<div class="detail-sub">Individual games</div>' +
        gamesLegend(weeks) +
        groups.join("")
      );
    }

    var lines = weeks.map(function (w) {
      // Book-average fills would drag a week's avg/high/low around, so the
      // summary line is built from counting games only.
      var scores = w.games
        .filter(function (g) { return g.counts !== false; })
        .map(function (g) { return g.score; });

      if (!scores.length) {
        return (
          '<div class="week-line week-line--absent">' +
          '<span class="week-line-label">' + esc(w.label) + weekTags(w) + "</span>" +
          '<span class="week-line-note">' +
          esc(w.absent ? absentLabel(w) : "No counting games") +
          "</span></div>"
        );
      }

      var avg = scores.reduce(function (a, b) { return a + b; }, 0) / scores.length;
      return (
        '<div class="week-line">' +
        '<span class="week-line-label">' + esc(w.label) + weekTags(w) + "</span>" +
        '<span class="week-line-avg">' + fmt(avg, 1) + "</span>" +
        '<span class="week-line-range">' +
        '<span class="fig-good">' + fmt(Math.max.apply(null, scores)) + "</span>" +
        '<span class="week-line-sep" aria-hidden="true">/</span>' +
        '<span class="fig-bad">' + fmt(Math.min.apply(null, scores)) + "</span>" +
        "</span>" +
        '<span class="week-line-games">' + scores.length + "g</span>" +
        "</div>"
      );
    });

    return (
      '<div class="detail-sub">Weekly breakdown ' +
      '<span class="detail-sub-note">avg &middot; high / low</span></div>' +
      gamesLegend(weeks) +
      '<div class="week-lines">' + lines.join("") + "</div>"
    );
  }

  /* Opponents and W-L only exist inside a single season, so a cross-season
   * range falls back to pins-only columns. */
  function weekTableMarkup(detail) {
    if (!detail || !detail.weeks || !detail.weeks.length) return "";
    var records = !!detail.records_available;

    var slots = 0;
    if (records) {
      detail.weeks.forEach(function (w) {
        var n = (w.game_pins || []).length;
        if (n > slots) slots = n;
      });
    }

    var gameHeads = [];
    for (var i = 1; i <= slots; i++) gameHeads.push("G" + i);

    // Per-game columns need a single matchup, so a range spanning seasons
    // carries the record without them and falls back to a games count.
    var head = records
      ? ["Wk", "Opponent", "W-L"].concat(slots ? gameHeads : ["Games"], ["Avg"])
      : ["Wk", "Pins", "Games", "Avg"];

    var body = detail.weeks
      .map(function (w) {
        var cells = ['<td class="wk-wk">' + esc(w.label) + "</td>"];
        if (records) {
          var style = w.opponent_color ? ' style="color:' + w.opponent_color + '"' : "";
          var rec = (w.wins || 0) + "-" + (w.losses || 0) + (w.ties ? "-" + w.ties : "");
          var recCls = "wk-rec";
          if ((w.wins || 0) > (w.losses || 0)) recCls += " fig-good";
          else if ((w.wins || 0) < (w.losses || 0)) recCls += " fig-bad";
          cells.push(
            '<td class="wk-opp"' + style + ">" + esc(w.opponent || "\u2014") + "</td>",
            '<td class="' + recCls + '">' + esc(rec) + "</td>"
          );
          var pins = w.game_pins || [];
          for (var s = 0; s < slots; s++) {
            var game = pins[s];
            var cls = "wk-num wk-g";
            if (game && game.result === "W") cls += " fig-good";
            // Both sides stack in the cell, ours over theirs, so a week reads
            // game by game the way the weekly results screen does.
            var body = game
              ? '<span class="wk-g-ours">' + fmt(game.pins) + "</span>" +
                '<span class="wk-g-opp">' +
                (game.opp_pins ? fmt(game.opp_pins) : "\u2014") + "</span>"
              : "\u2014";
            cells.push('<td class="' + cls + '">' + body + "</td>");
          }
          if (!slots) cells.push('<td class="wk-num">' + fmt(w.games) + "</td>");
        } else {
          cells.push(
            '<td class="wk-num">' + fmt(w.pins) + "</td>",
            '<td class="wk-num">' + fmt(w.games) + "</td>"
          );
        }
        cells.push('<td class="wk-num wk-avg">' + fmt(w.avg, 2) + "</td>");
        // Narrow screens leave the opponent column no usable width, so the name
        // also rides on its own full-width line that CSS swaps in there. The
        // span counts only the columns visible at that width: a colspan past
        // the column count makes the browser widen the table for that row.
        var oppRow = records
          ? '<tr class="wk-opp-row"><td class="wk-opp-line" colspan="' +
            (head.length - (slots ? 2 : 1)) + '"' + style + ">" +
            esc(w.opponent ? "vs " + w.opponent : "\u2014") + "</td></tr>"
          : "";
        return "<tr>" + cells.join("") + "</tr>" + oppRow;
      })
      .join("");

    return (
      '<div class="detail-sub">Week by week</div>' +
      '<table class="wk-table' + (slots ? " wk-table--pergame" : "") +
      '"><thead><tr>' +
      head
        .map(function (h) {
          return '<th class="wk-h-' + h.toLowerCase().replace(/[^a-z0-9]/g, "") + '">' +
            esc(h) + "</th>";
        })
        .join("") +
      "</tr></thead><tbody>" + body + "</tbody></table>"
    );
  }

  function renderTeamDetail(box, row, detail) {
    var pairs = [
      [isSingle() ? "Avg" : "Avg/game", fmt(row[teamAvgKey()], 2)],
      ["Total pins", fmt(row.total_pins)],
      ["High game", fmt(row.high_game)]
    ];
    if (!isSingle()) {
      pairs.push(
        ["High week", fmt(row.high_week_avg, 2)],
        ["Low week", fmt(row.low_week_avg, 2)]
      );
    }
    pairs.push(["Weeks", fmt(row.weeks)], ["Games", fmt(row.games)]);
    if (detail && detail.record) pairs.push(["Record", detail.record]);

    var weekPoints = ((detail && detail.weeks) || []).map(function (w) {
      return { value: w.avg, label: w.label };
    });
    box.innerHTML =
      statBlock(pairs) +
      profileSection(
        detailKey(row),
        "Graph",
        trendChart(weekPoints, {
          average: row[teamAvgKey()],
          leagueAverage: payload.league ? payload.league.league_avg : null,
          label: "Weekly average by week for " + row.team,
          decimals: 2
        })
      ) +
      membersSection(
        detailKey(row) + ":members",
        "Roster",
        detail && detail.rosters
      ) +
      weekTableMarkup(detail);
  }

  function renderPlayerDetail(box, row, detail) {
    var pairs = [
      [row.average_from_absences ? "Avg credited" : "Avg", fmt(row.average, 2)],
      ["High", fmt(row.highest_game)],
      ["Low", fmt(row.lowest_game)],
      ["St dev", fmt(row.std_dev, 2)],
      ["Games", fmt(row.games)],
      ["Weeks", fmt(row.weeks_played)],
      ["Absences", fmt(row.absences)]
    ];
    if (row.absent_average !== null && row.absent_average !== undefined &&
        !row.average_from_absences) {
      pairs.push(["Absent avg", fmt(row.absent_average, 2)]);
    }
    if (row.sub_games) pairs.push(["Sub games", fmt(row.sub_games)]);
    if (row.sub_for && row.sub_for.length) {
      pairs.push(["Sub for", row.sub_for.join(", ")]);
    }
    if (payload.par_available) pairs.push(["PAR", fmt(row.par)]);

    var seasonTeams = (detail && detail.teams_by_season) || [];
    var gamePoints = ((detail && detail.games) || []).map(function (g) {
      return {
        value: g.score,
        label: g.label + " G" + g.game,
        tone: g.game_absent ? "miss" : (g.is_substitute ? "sub" : "")
      };
    });
    box.innerHTML =
      statBlock(pairs) +
      profileSection(
        detailKey(row),
        "Graph",
        trendChart(gamePoints, {
          average: row.average,
          leagueAverage: payload.league ? payload.league.league_avg : null,
          label: "Game scores over the range for " + row.player
        })
      ) +
      // Inside one season this would only repeat the team on the row itself.
      (seasonTeams.length > 1
        ? membersSection(detailKey(row) + ":members", "Teams", seasonTeams)
        : "") +
      gamesMarkup(
        detail ? detail.games : null,
        row.highest_game,
        row.lowest_game,
        detail ? detail.absent_weeks : null
      );
  }

  function openDetail(li) {
    var id = li.getAttribute("data-id");
    var box = li.querySelector(".row-detail");
    var btn = li.querySelector(".row-main");
    var row = rowData(id);
    if (!row) return;

    li.classList.add("is-open");
    btn.setAttribute("aria-expanded", "true");
    box.hidden = false;

    var teams = state.view === "teams";
    var render = teams ? renderTeamDetail : renderPlayerDetail;
    var key = detailKey(row);

    if (detailCache[key]) {
      render(box, row, detailCache[key]);
      return;
    }

    box.innerHTML =
      '<p class="detail-empty">Loading ' + (teams ? "weeks" : "games") + "\u2026</p>";
    fetch(
      "/api/" + (teams ? "team" : "player") + "/" + encodeURIComponent(id) +
        "?" + apiQuery(),
      { headers: { Accept: "application/json" } }
    )
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (detail) {
        if (detail) detailCache[key] = detail;
        if (li.classList.contains("is-open")) render(box, row, detail);
      })
      .catch(function () {
        if (li.classList.contains("is-open")) render(box, row, null);
      });
  }

  function closeDetail(li) {
    li.classList.remove("is-open");
    li.querySelector(".row-main").setAttribute("aria-expanded", "false");
    li.querySelector(".row-detail").hidden = true;
  }

  function toggleRow(li) {
    if (openRow && openRow !== li) closeDetail(openRow);
    if (li.classList.contains("is-open")) {
      closeDetail(li);
      openRow = null;
    } else {
      openDetail(li);
      openRow = li;
    }
  }

  /* ---------------- filter panel ---------------- */

  function fillSeasonSelect(select, selected) {
    select.innerHTML = meta.seasons
      .map(function (s) {
        return (
          '<option value="' + s.number + '"' +
          (s.number === selected ? " selected" : "") +
          ">S" + s.number + "</option>"
        );
      })
      .join("");
  }

  function fillWeekSelect(select, seasonNum, selected) {
    var weeks = weeksFor(seasonNum);
    select.innerHTML = weeks
      .map(function (w) {
        return (
          '<option value="' + w + '"' +
          (w === selected ? " selected" : "") +
          ">W" + w + "</option>"
        );
      })
      .join("");
    if (weeks.indexOf(selected) === -1) select.value = String(weeks[0]);
  }

  /* In single-week mode the picker collapses to its second column, which then
   * drives state.week instead of state.end. */
  function syncSpanUi() {
    var single = isSingle();
    el.rangePicker.classList.toggle("is-single", single);
    el.startCol.hidden = single;
    el.rangePickerDash.hidden = single;
    el.endHead.textContent = single ? "Week" : "End";
    // One week is either a playoff week or it isn't, so there is nothing to
    // filter. apiQuery neutralises the stored choice to match.
    el.playoffGroup.hidden = single;
    el.spanButtons.forEach(function (btn) {
      var on = btn.getAttribute("data-span") === state.span;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  /* The whole of one season, or every season on record. Season order from
   * /api/meta is newest-first, so take the extremes rather than the ends. */
  function presetRange(key) {
    var numbers = meta.seasons.map(function (s) { return s.number; });
    var first = key === "all"
      ? Math.min.apply(null, numbers)
      : (meta.current_season_number || numbers[0]);
    var last = key === "all" ? Math.max.apply(null, numbers) : first;
    var firstWeeks = weeksFor(first);
    var lastWeeks = weeksFor(last);
    return {
      start: pos(first, firstWeeks[0]),
      end: pos(last, lastWeeks[lastWeeks.length - 1])
    };
  }

  function syncPresets() {
    el.presetButtons.forEach(function (btn) {
      var target = presetRange(btn.getAttribute("data-preset"));
      var active =
        !isSingle() &&
        comparePos(state.start, target.start) === 0 &&
        comparePos(state.end, target.end) === 0;
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function syncFilterPanel() {
    syncSpanUi();
    syncPresets();
    var end = isSingle() ? state.week : state.end;
    fillSeasonSelect(el.startSeason, state.start.season);
    fillWeekSelect(el.startWeek, state.start.season, state.start.week);
    fillSeasonSelect(el.endSeason, end.season);
    fillWeekSelect(el.endWeek, end.season, end.week);

    el.playoffButtons.forEach(function (btn) {
      btn.setAttribute(
        "aria-pressed",
        btn.getAttribute("data-playoffs") === state.playoffs ? "true" : "false"
      );
    });
  }

  function readRangeFromPanel() {
    var end = pos(parseInt(el.endSeason.value, 10), parseInt(el.endWeek.value, 10));
    if (isSingle()) {
      state.week = end;
      return;
    }
    var start = pos(parseInt(el.startSeason.value, 10), parseInt(el.startWeek.value, 10));
    if (comparePos(start, end) > 0) {
      var t = start; start = end; end = t;
    }
    state.start = start;
    state.end = end;
  }

  /* ---------------- settings panel ---------------- */

  function syncSettingsPanel() {
    function fill(select, view, selected) {
      select.innerHTML = fieldsFor(view)
        .map(function (f) {
          return (
            '<option value="' + esc(f.key) + '"' +
            (f.key === selected ? " selected" : "") + ">" + esc(f.label) + "</option>"
          );
        })
        .join("");
    }
    fill(el.defaultSortPlayers, "players", prefs.sortPlayers);
    fill(el.defaultSortTeams, "teams", prefs.sortTeams);
    el.defaultSortPlayersDir.value = prefs.sortPlayersDir;
    el.defaultSortTeamsDir.value = prefs.sortTeamsDir;

    el.densityRadios.innerHTML = DENSITIES.map(function (d) {
      return (
        '<button type="button" class="radio-row" role="radio" data-density="' + d.key + '" ' +
        'aria-checked="' + (prefs.density === d.key ? "true" : "false") + '">' +
        '<span class="radio-dot" aria-hidden="true"></span><span>' + esc(d.label) +
        "</span></button>"
      );
    }).join("");

    el.rowLimitRadios.innerHTML = ROW_LIMITS.map(function (r) {
      return (
        '<button type="button" class="radio-row" role="radio" data-rowlimit="' + r.key + '" ' +
        'aria-checked="' + (prefs.rowLimit === r.key ? "true" : "false") + '">' +
        '<span class="radio-dot" aria-hidden="true"></span><span>' + esc(r.label) +
        "</span></button>"
      );
    }).join("");
  }

  function applyDensity() {
    document.body.classList.toggle("density-compact", prefs.density === "compact");
  }

  /* ---------------- popovers ---------------- */

  function closePopovers() {
    /* On desktop the filter panel is inline in the rail, not a popover. */
    if (!DESKTOP_MQ.matches) {
      el.filterPanel.hidden = true;
      el.rangePill.setAttribute("aria-expanded", "false");
    }
    el.settingsPanel.hidden = true;
    el.settingsBtn.setAttribute("aria-expanded", "false");
    el.scrim.hidden = true;
  }

  function openFilter() {
    syncFilterPanel();
    el.filterPanel.hidden = false;
    el.rangePill.setAttribute("aria-expanded", "true");
    el.scrim.hidden = DESKTOP_MQ.matches;
  }

  function openSettings() {
    syncSettingsPanel();
    el.settingsPanel.hidden = false;
    el.settingsBtn.setAttribute("aria-expanded", "true");
    el.scrim.hidden = DESKTOP_MQ.matches;
  }

  /* On desktop the filter panel lives inline in the rail; on mobile it is a
   * popover under the range pill. Move the same node between the two. */
  var railFilters = null;

  function syncFilterPlacement() {
    if (DESKTOP_MQ.matches) {
      if (!railFilters) {
        railFilters = document.createElement("section");
        railFilters.className = "panel rail-filters";
      }
      if (el.filterPanel.parentNode !== railFilters) {
        railFilters.appendChild(el.filterPanel);
        el.rail.insertBefore(railFilters, el.rail.firstChild);
      }
      el.filterPanel.hidden = false;
      syncFilterPanel();
    } else {
      if (railFilters && railFilters.parentNode) railFilters.parentNode.removeChild(railFilters);
      if (el.filterPanel.parentNode !== el.rangeField) {
        el.rangeField.appendChild(el.filterPanel);
      }
      el.filterPanel.hidden = true;
      el.rangePill.setAttribute("aria-expanded", "false");
    }
  }

  /* ---------------- events ---------------- */

  function bind() {
    el.rangePill.addEventListener("click", function () {
      if (el.filterPanel.hidden) openFilter();
      else closePopovers();
    });

    el.settingsBtn.addEventListener("click", function () {
      if (el.settingsPanel.hidden) openSettings();
      else closePopovers();
    });

    el.scrim.addEventListener("click", closePopovers);
    el.filterClose.addEventListener("click", closePopovers);
    el.settingsClose.addEventListener("click", closePopovers);

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closePopovers();
    });

    el.playoffFlip.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-playoffs]");
      if (!btn) return;
      var choice = btn.getAttribute("data-playoffs");
      if (choice === state.playoffs) return;
      state.playoffs = choice;
      syncFilterPanel();
      persist();
      load();
    });

    [el.startSeason, el.endSeason].forEach(function (sel) {
      sel.addEventListener("change", function () {
        var isStart = sel === el.startSeason;
        var num = parseInt(sel.value, 10);
        var weekSel = isStart ? el.startWeek : el.endWeek;
        var current = isStart
          ? state.start.week
          : (isSingle() ? state.week.week : state.end.week);
        fillWeekSelect(weekSel, num, current);
        readRangeFromPanel();
        persist();
        load();
      });
    });

    [el.startWeek, el.endWeek].forEach(function (sel) {
      sel.addEventListener("change", function () {
        readRangeFromPanel();
        persist();
        load();
      });
    });

    el.spanflip.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-span]");
      if (!btn) return;
      var span = btn.getAttribute("data-span");
      if (span === state.span) return;
      state.span = span;
      if (isSingle()) state.week = clampPos(state.week);
      ensureSortField();
      syncFilterPanel();
      persist();
      load();
    });

    // A preset is a range, so choosing one moves out of single-week mode.
    el.rangePresets.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-preset]");
      if (!btn) return;
      var target = presetRange(btn.getAttribute("data-preset"));
      state.span = "multi";
      state.start = target.start;
      state.end = target.end;
      syncFilterPanel();
      persist();
      load();
    });

    el.filterReset.addEventListener("click", function () {
      var fresh = defaultState();
      state.span = fresh.span;
      state.start = fresh.start;
      state.end = fresh.end;
      state.week = fresh.week;
      state.playoffs = fresh.playoffs;
      syncFilterPanel();
      persist();
      load();
    });

    el.tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var view = tab.getAttribute("data-view");
        if (view === state.view) return;
        state.view = view;
        // Bests and Playoffs have no sort, so the stored sort preference is
        // left untouched and restored as-is on return to a board view.
        if (view !== "bests" && view !== "playoffs") {
          state.sort = view === "teams" ? prefs.sortTeams : prefs.sortPlayers;
          state.dir = view === "teams" ? prefs.sortTeamsDir : prefs.sortPlayersDir;
        }
        el.tabs.forEach(function (t) {
          t.setAttribute("aria-selected", t === tab ? "true" : "false");
        });
        openRow = null;
        showAllRows = false;
        renderSortControl();
        renderHighlights();
        renderTiles();
        renderBoard();
        syncViewPanels();
        persist();
      });
    });

    el.playoffSeason.addEventListener("change", function () {
      playoffSeason = el.playoffSeason.value;
      loadPlayoffs();
    });

    el.sortField.addEventListener("change", function () {
      state.sort = el.sortField.value;
      var field = findField(state.view, state.sort);
      if (field) state.dir = field.dir;
      openRow = null;
      renderSortControl();
      renderBoard();
      persist();
    });

    el.sortDir.addEventListener("click", function () {
      state.dir = state.dir === "asc" ? "desc" : "asc";
      openRow = null;
      renderSortControl();
      renderBoard();
      persist();
    });

    // Hover for a mouse, tap or keyboard focus for everything else.
    el.board.addEventListener("mouseover", function (e) {
      var point = e.target.closest(".prof-point");
      if (point) showChartTip(point);
    });
    el.board.addEventListener("mouseout", function (e) {
      var point = e.target.closest(".prof-point");
      if (point) hideChartTip(point.closest(".prof-plot"));
    });
    el.board.addEventListener("focusin", function (e) {
      var point = e.target.closest(".prof-point");
      if (point) showChartTip(point);
    });
    el.board.addEventListener("focusout", function (e) {
      var point = e.target.closest(".prof-point");
      if (point) hideChartTip(point.closest(".prof-plot"));
    });

    el.board.addEventListener("click", function (e) {
      var point = e.target.closest(".prof-point");
      if (point) {
        showChartTip(point);
        return;
      }
      var prof = e.target.closest("[data-prof-toggle]");
      if (prof) {
        var card = prof.closest(".prof");
        var profOpen = !card.classList.contains("is-open");
        card.classList.toggle("is-open", profOpen);
        prof.setAttribute("aria-expanded", profOpen ? "true" : "false");
        card.querySelector(".prof-body").hidden = !profOpen;
        profilesOpen[prof.getAttribute("data-prof-toggle")] = profOpen;
        return;
      }
      var btn = e.target.closest(".row-main");
      if (!btn) return;
      toggleRow(btn.closest(".row"));
    });

    // Settings
    el.defaultSortPlayers.addEventListener("change", function () {
      prefs.sortPlayers = el.defaultSortPlayers.value; savePrefs();
    });
    el.defaultSortPlayersDir.addEventListener("change", function () {
      prefs.sortPlayersDir = el.defaultSortPlayersDir.value; savePrefs();
    });
    el.defaultSortTeams.addEventListener("change", function () {
      prefs.sortTeams = el.defaultSortTeams.value; savePrefs();
    });
    el.defaultSortTeamsDir.addEventListener("change", function () {
      prefs.sortTeamsDir = el.defaultSortTeamsDir.value; savePrefs();
    });
    el.densityRadios.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-density]");
      if (!btn) return;
      prefs.density = btn.getAttribute("data-density");
      savePrefs();
      applyDensity();
      syncSettingsPanel();
    });
    el.rowLimitRadios.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-rowlimit]");
      if (!btn) return;
      prefs.rowLimit = parseInt(btn.getAttribute("data-rowlimit"), 10);
      savePrefs();
      // A row expanded past the new cap would otherwise vanish while open.
      openRow = null;
      showAllRows = false;
      renderBoard();
      syncSettingsPanel();
    });
    el.playoffs.addEventListener("click", function (e) {
      var head = e.target.closest("[data-po-toggle]");
      if (!head) return;
      var card = head.closest(".po-card");
      var open = !card.classList.contains("is-open");
      card.classList.toggle("is-open", open);
      head.setAttribute("aria-expanded", open ? "true" : "false");
      card.querySelector(".po-body").hidden = !open;
      playoffsOpen[head.getAttribute("data-po-toggle")] = open;
    });
    el.bests.addEventListener("click", function (e) {
      // Collapsing flips the one card in place, so the other lists hold still.
      var head = e.target.closest("[data-bests-toggle]");
      if (head) {
        var card = head.closest(".best-card");
        var open = !card.classList.contains("is-open");
        card.classList.toggle("is-open", open);
        head.setAttribute("aria-expanded", open ? "true" : "false");
        card.querySelector(".best-body").hidden = !open;
        if (open) prefs.bestsOpen[head.getAttribute("data-bests-toggle")] = true;
        else delete prefs.bestsOpen[head.getAttribute("data-bests-toggle")];
        savePrefs();
        return;
      }

      var btn = e.target.closest("[data-bests-more]");
      if (!btn) return;
      var cached = bestsCache[apiQuery()];
      if (!cached) return;
      var key = btn.getAttribute("data-bests-more");
      bestsExpanded[key] = !bestsExpanded[key];
      renderBests(cached);
    });
    el.boardMore.addEventListener("click", function (e) {
      if (!e.target.closest("#board-more-btn")) return;
      showAllRows = !showAllRows;
      openRow = null;
      renderBoard();
    });
    el.settingsReset.addEventListener("click", function () {
      prefs = defaultPrefs();
      savePrefs();
      applyDensity();
      openRow = null;
      showAllRows = false;
      renderBoard();
      // The records on screen still carry the old open set.
      var records = bestsCache[apiQuery()];
      if (records) renderBests(records);
      syncSettingsPanel();
    });

    if (typeof DESKTOP_MQ.addEventListener === "function") {
      DESKTOP_MQ.addEventListener("change", syncFilterPlacement);
    } else if (typeof DESKTOP_MQ.addListener === "function") {
      DESKTOP_MQ.addListener(syncFilterPlacement);
    }
  }

  /* ---------------- boot ---------------- */

  function cache() {
    el.rangePill = document.getElementById("range-pill");
    el.rangePillText = document.getElementById("range-pill-text");
    el.rangePillTag = document.getElementById("range-pill-tag");
    el.rangeField = document.querySelector(".range-field");
    el.filterPanel = document.getElementById("filter-panel");
    el.rangeHint = document.getElementById("range-hint");
    el.rangePresets = document.getElementById("range-presets");
    el.presetButtons = Array.prototype.slice.call(
      document.querySelectorAll("[data-preset]")
    );
    el.filterRangeText = document.getElementById("filter-range-text");
    el.filterRangeTag = document.getElementById("filter-range-tag");
    el.startSeason = document.getElementById("start-season");
    el.startWeek = document.getElementById("start-week");
    el.endSeason = document.getElementById("end-season");
    el.endWeek = document.getElementById("end-week");
    el.rangePicker = document.getElementById("range-picker");
    el.rangePickerDash = document.getElementById("range-picker-dash");
    el.startCol = document.getElementById("start-col");
    el.endHead = document.getElementById("end-head");
    el.spanflip = document.getElementById("spanflip");
    el.spanButtons = Array.prototype.slice.call(
      document.querySelectorAll("[data-span]")
    );
    el.filterReset = document.getElementById("filter-reset");
    el.filterClose = document.getElementById("filter-close");
    el.playoffGroup = document.getElementById("playoff-group");
    el.playoffFlip = document.getElementById("playoff-flip");
    el.playoffButtons = Array.prototype.slice.call(
      document.querySelectorAll("[data-playoffs]")
    );
    el.tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
    el.settingsBtn = document.getElementById("settings-btn");
    el.settingsPanel = document.getElementById("settings-panel");
    el.settingsClose = document.getElementById("settings-close");
    el.settingsReset = document.getElementById("settings-reset");
    el.defaultSortPlayers = document.getElementById("default-sort-players");
    el.defaultSortPlayersDir = document.getElementById("default-sort-players-dir");
    el.defaultSortTeams = document.getElementById("default-sort-teams");
    el.defaultSortTeamsDir = document.getElementById("default-sort-teams-dir");
    el.densityRadios = document.getElementById("density-radios");
    el.rowLimitRadios = document.getElementById("rowlimit-radios");
    el.boardMore = document.getElementById("board-more");
    el.rail = document.querySelector(".rail");
    el.highlights = document.getElementById("highlights");
    el.leagueTiles = document.getElementById("league-tiles");
    el.sortField = document.getElementById("sort-field");
    el.sortDir = document.getElementById("sort-dir");
    el.sortDirArrow = document.getElementById("sort-dir-arrow");
    el.sortDirText = document.getElementById("sort-dir-text");
    el.status = document.getElementById("status");
    el.panelLeaderboard = document.getElementById("panel-leaderboard");
    el.panelBests = document.getElementById("panel-bests");
    el.panelHighlights = document.getElementById("panel-highlights");
    el.panelLeague = document.getElementById("panel-league");
    el.bests = document.getElementById("bests");
    el.bestsStatus = document.getElementById("bests-status");
    el.panelPlayoffs = document.getElementById("panel-playoffs");
    el.playoffsStatus = document.getElementById("playoffs-status");
    el.playoffs = document.getElementById("playoffs");
    el.playoffSeason = document.getElementById("playoff-season");
    el.playoffUpcoming = document.getElementById("playoff-upcoming");
    el.playoffRounds = document.getElementById("playoff-rounds");
    el.playoffSeeds = document.getElementById("playoff-seeds");
    el.playoffHistory = document.getElementById("playoff-history");
    el.board = document.getElementById("leaderboard");
    el.scrim = document.getElementById("scrim");
  }

  function boot() {
    cache();
    applyDensity();
    setStatus("Loading\u2026");

    fetch("/api/meta", { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json().then(function (b) {
          if (!r.ok) throw new Error(b.error || "Could not load seasons.");
          return b;
        });
      })
      .then(function (body) {
        meta = body;
        if (!meta.seasons || !meta.seasons.length) {
          throw new Error("No seasons available yet.");
        }
        initState();
        bind();
        el.tabs.forEach(function (t) {
          t.setAttribute("aria-selected", t.getAttribute("data-view") === state.view ? "true" : "false");
        });
        syncFilterPanel();
        syncSettingsPanel();
        syncFilterPlacement();
        persist();
        load();
      })
      .catch(function (err) {
        setStatus(err.message || "Could not start.", true);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

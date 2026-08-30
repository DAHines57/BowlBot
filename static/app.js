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

  var DEFAULT_PREFS = {
    sortPlayers: "average",
    sortPlayersDir: "desc",
    sortTeams: "avg_per_game",
    sortTeamsDir: "desc",
    density: "comfortable",
    rowLimit: 0
  };

  var meta = null;
  var prefs = loadPrefs();
  var state = null;
  var payload = null;
  var detailCache = {};
  var openRow = null;
  // Set by the Show all button, cleared whenever the list underneath changes.
  var showAllRows = false;
  var fetchToken = 0;

  var el = {};

  /* ---------------- storage ---------------- */

  function loadPrefs() {
    var out = {};
    for (var k in DEFAULT_PREFS) out[k] = DEFAULT_PREFS[k];
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

  function fieldsFor(view) {
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
      if (stored.view) state.view = stored.view;
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
    if (q.get("view") === "teams" || q.get("view") === "players") state.view = q.get("view");
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
  }

  function renderRangeText() {
    var text;
    if (isSingle()) {
      text = posText(state.week);
    } else {
      text = posText(state.start) + " \u2013 " + posText(state.end);
    }
    el.rangePillText.textContent = text;
    if (el.highlightsTitle) {
      el.highlightsTitle.textContent = isSingle() ? "Weekly Summary" : "Range Summary";
    }
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
    var tiles = [
      { value: fmt(lg.league_avg, 2), label: "League Avg" },
      { value: fmt(lg.total_players), label: "Players" },
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
    // A credited average is not a bowled one; label it so the ranking reads honestly.
    var credited = row.average_from_absences;
    var lines = [
      figureLine(credited ? "Avg cr" : "Avg", row.average, {
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
        // also rides on its own full-width line that CSS swaps in there.
        var oppRow = records
          ? '<tr class="wk-opp-row"><td class="wk-opp-line" colspan="' +
            head.length + '"' + style + ">" +
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

    box.innerHTML = statBlock(pairs) + weekTableMarkup(detail);
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

    box.innerHTML =
      statBlock(pairs) +
      gamesMarkup(
        detail ? detail.games : null,
        row.highest_game,
        row.lowest_game,
        detail ? detail.absent_weeks : null
      ) +
      '<a class="detail-link" href="/player/' + encodeURIComponent(row.player) +
      "?season=" + encodeURIComponent("Season " + (isSingle() ? state.week : state.end).season) +
      '">View player profile</a>';
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
    // Namespaced so a team and a player sharing a name cannot collide.
    var key = state.view + ":" + id;

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
        state.sort = view === "teams" ? prefs.sortTeams : prefs.sortPlayers;
        state.dir = view === "teams" ? prefs.sortTeamsDir : prefs.sortPlayersDir;
        el.tabs.forEach(function (t) {
          t.setAttribute("aria-selected", t === tab ? "true" : "false");
        });
        openRow = null;
        showAllRows = false;
        renderSortControl();
        renderHighlights();
        renderBoard();
        persist();
      });
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

    el.board.addEventListener("click", function (e) {
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
    el.boardMore.addEventListener("click", function (e) {
      if (!e.target.closest("#board-more-btn")) return;
      showAllRows = !showAllRows;
      openRow = null;
      renderBoard();
    });
    el.settingsReset.addEventListener("click", function () {
      prefs = {};
      for (var k in DEFAULT_PREFS) prefs[k] = DEFAULT_PREFS[k];
      savePrefs();
      applyDensity();
      openRow = null;
      showAllRows = false;
      renderBoard();
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
    el.highlightsTitle = document.getElementById("highlights-title");
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

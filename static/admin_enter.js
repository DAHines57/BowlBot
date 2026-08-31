/* Week score entry. The grid is a CSS grid of [data-row] blocks; substitute
   rows are built by createSubRow for both existing and newly added subs so the
   markup has one source. Saving posts JSON without navigating, so a rejected
   payload never costs the typed grid. */
(function () {
  "use strict";

  var form = document.getElementById("save-form");
  if (!form) return;

  var cfgEl = document.getElementById("entry-config");
  var CFG = JSON.parse((cfgEl && cfgEl.textContent) || "{}");

  var season = CFG.season;
  var week = CFG.week;
  var teamFilter = CFG.team_filter || null;
  var ALL_TEAMS = CFG.all_teams || [];
  var ALL_PLAYERS = Array.isArray(CFG.all_players) ? CFG.all_players : [];
  var GAME_MIN = CFG.game_min;
  var GAME_MAX = CFG.game_max;
  var ABSENT_FILL = CFG.absent_fill || {};
  var ABSENT_FILL_META = CFG.absent_fill_meta || {};
  var TEAM_GAME5 = CFG.team_game5 || {};
  var SCAN_URL = CFG.scan_url;
  var SAVE_URL = CFG.save_url;
  var SCORE_HINT = "Enter a whole number from " + GAME_MIN + " to " + GAME_MAX + ", or leave blank.";
  var NEW_PLAYER_VALUE = "__NEW__";

  var syncingOpponents = false;
  var dirty = false;
  var saving = false;

  var DRAFT_KEY = "bowlbot.entry-draft." + season + ".w" + week + "." + (teamFilter || "all");

  function rows() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-row]"));
  }

  function rosterRows() {
    return Array.prototype.slice.call(
      document.querySelectorAll('[data-row][data-substitute="false"]')
    );
  }

  function subRows(scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(".sub-row"));
  }

  var draftTimer = null;

  function markDirty() {
    dirty = true;
    if (draftTimer) window.clearTimeout(draftTimer);
    draftTimer = window.setTimeout(saveDraft, 400);
  }

  /* ---------- validation ---------- */

  function rowErrorEl(tr) {
    return tr.querySelector(".field-error");
  }

  function setRowError(tr, message) {
    var el = rowErrorEl(tr);
    tr.classList.toggle("has-error", !!message);
    if (!el) return;
    el.textContent = message || "";
    el.hidden = !message;
  }

  function clearAllRowErrors() {
    rows().forEach(function (tr) {
      setRowError(tr, "");
      tr.querySelectorAll("input.game").forEach(function (inp) {
        inp.classList.remove("is-bad");
      });
    });
  }

  function validateGameInput(inp) {
    var v = inp.value.trim();
    if (v === "") {
      inp.setCustomValidity("");
      inp.classList.remove("is-bad");
      return true;
    }
    var n = Number(v);
    if (!Number.isInteger(n) || n < GAME_MIN || n > GAME_MAX) {
      inp.setCustomValidity(SCORE_HINT);
      inp.classList.add("is-bad");
      return false;
    }
    inp.setCustomValidity("");
    inp.classList.remove("is-bad");
    return true;
  }

  /* ---------- game 5 ---------- */

  function setTeamGame5Visible(block, show) {
    if (!block) return;
    block.classList.toggle("hide-game5", !show);
    var toggle = block.querySelector(".team-game5-toggle");
    if (toggle) toggle.checked = show;
    var team = block.getAttribute("data-team");
    if (team) TEAM_GAME5[team] = show;
  }

  function initTeamGame5Toggles() {
    document.querySelectorAll(".team-block").forEach(function (block) {
      var team = block.getAttribute("data-team");
      var show = TEAM_GAME5[team] === true;
      var toggle = block.querySelector(".team-game5-toggle");
      if (toggle) {
        toggle.addEventListener("change", function () {
          setTeamGame5Visible(block, toggle.checked);
          markDirty();
        });
      }
      setTeamGame5Visible(block, show);
    });
  }

  function teamShowsGame5(tr) {
    var block = tr.closest(".team-block");
    return block && !block.classList.contains("hide-game5");
  }

  /* ---------- absences ---------- */

  function absentFillInputs(tr) {
    var sel = "input.game-main";
    if (teamShowsGame5(tr)) sel += ", input.game5";
    return tr.querySelectorAll(sel);
  }

  function fillAbsentScores(tr, force) {
    var player = tr.getAttribute("data-player");
    var avg = player ? ABSENT_FILL[player] : null;
    if (avg == null) return;
    if (!force) {
      var hasScore = false;
      absentFillInputs(tr).forEach(function (inp) {
        if (inp.value.trim() !== "") hasScore = true;
      });
      if (hasScore) return;
    }
    absentFillInputs(tr).forEach(function (inp) {
      inp.value = String(avg);
      validateGameInput(inp);
    });
    tr.classList.remove("row-incomplete");
    tr.removeAttribute("title");
  }

  function updateAbsentFillHint(tr, on) {
    var hint = tr.querySelector(".absent-fill-hint");
    if (!hint) return;
    if (!on) {
      hint.hidden = true;
      hint.textContent = "";
      return;
    }
    var player = tr.getAttribute("data-player");
    var meta = player ? ABSENT_FILL_META[player] : null;
    if (!meta || meta.base == null) {
      hint.hidden = true;
      return;
    }
    hint.textContent = meta.base + " \u00d7 " + meta.penalty_percent + "%";
    hint.hidden = false;
  }

  function setWeekAbsentRow(tr, on) {
    tr.classList.toggle("week-absent", on);
    tr.setAttribute("data-week-out", on ? "true" : "false");
    tr.querySelectorAll("input.game-absent").forEach(function (cb) {
      if (on) cb.checked = false;
      cb.disabled = on;
    });
    updateAbsentFillHint(tr, on);
  }

  function isWeekOut(tr) {
    if (tr.getAttribute("data-week-out") === "true") return true;
    var absentCb = tr.querySelector("input.absent");
    return !!(absentCb && absentCb.checked);
  }

  function syncWeekOutRowFromDom(tr) {
    var absentInp = tr.querySelector("input.absent");
    if (!absentInp) return false;
    if (tr.getAttribute("data-week-out") === "true" && !absentInp.checked) {
      absentInp.checked = true;
    }
    var on = isWeekOut(tr);
    setWeekAbsentRow(tr, on);
    return on;
  }

  function applyWeekOutUi(tr) {
    if (!syncWeekOutRowFromDom(tr)) return;
    fillAbsentScores(tr, false);
    refreshGameMissRow(tr);
  }

  function fillGameAbsentScore(inp, tr) {
    var player = tr.getAttribute("data-player");
    var avg = player ? ABSENT_FILL[player] : null;
    if (avg == null) return;
    if (inp.value.trim() === "") inp.value = String(avg);
    validateGameInput(inp);
  }

  function refreshGameMissRow(tr) {
    var any = false;
    tr.querySelectorAll("input.game-absent").forEach(function (cb) {
      if (cb.checked && !cb.disabled) any = true;
    });
    tr.classList.toggle("has-game-miss", any);
  }

  /* ---------- substitutes ---------- */

  function rosterNamesForBlock(block) {
    var raw = block.getAttribute("data-roster-names") || "[]";
    try {
      var parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length) return parsed;
    } catch (e) { /* fall through to the DOM */ }
    var names = [];
    block.querySelectorAll('[data-row][data-substitute="false"]').forEach(function (tr) {
      var n = tr.getAttribute("data-player");
      if (n) names.push(n);
    });
    return names;
  }

  function findSubRowForPlayer(block, playerName) {
    if (!block || !playerName) return null;
    var found = null;
    subRows(block).forEach(function (tr) {
      var sel = tr.querySelector(".sub-for");
      var slot = (sel && sel.value.trim()) || (tr.getAttribute("data-sub-for") || "").trim();
      if (slot === playerName) found = tr;
    });
    return found;
  }

  function ensureWeekOut(tr) {
    var absentInp = tr.querySelector("input.absent");
    if (!absentInp) return;
    if (!absentInp.checked) absentInp.checked = true;
    setWeekAbsentRow(tr, true);
    fillAbsentScores(tr, true);
    refreshGameMissRow(tr);
  }

  function updateSubSectionVisibility(block) {
    var section = block.querySelector(".sub-section");
    if (!section) return;
    var hasSubs = subRows(block).length > 0;
    var hasSubbed = false;
    block.querySelectorAll(".roster-row input.subbed").forEach(function (cb) {
      if (cb.checked) hasSubbed = true;
    });
    section.classList.toggle("visible", hasSubs || hasSubbed);
  }

  function setSubbedForPlayer(block, playerName, on) {
    if (!block || !playerName) return;
    block.querySelectorAll(".roster-row").forEach(function (tr) {
      if (tr.getAttribute("data-player") === playerName) {
        var cb = tr.querySelector("input.subbed");
        if (cb) cb.checked = on;
      }
    });
    updateSubSectionVisibility(block);
  }

  function removeSubForPlayer(block, playerName) {
    if (!playerName) return;
    subRows(block).forEach(function (tr) {
      var sel = tr.querySelector(".sub-for");
      if (sel && sel.value === playerName) tr.remove();
    });
  }

  function takenSubForSlots(block, exceptTr) {
    var taken = [];
    subRows(block).forEach(function (tr) {
      if (tr === exceptTr) return;
      var sel = tr.querySelector(".sub-for");
      var slot = (sel && sel.value.trim()) || (tr.getAttribute("data-sub-for") || "").trim();
      if (slot) taken.push(slot);
    });
    return taken;
  }

  function buildSubPickSelect(selected) {
    var sel = document.createElement("select");
    sel.className = "sub-pick-select";
    sel.setAttribute("aria-label", "Sub player");
    var opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "\u2014 select \u2014";
    sel.appendChild(opt0);
    if (selected && ALL_PLAYERS.indexOf(selected) < 0) {
      var cur = document.createElement("option");
      cur.value = selected;
      cur.textContent = selected;
      cur.selected = true;
      sel.appendChild(cur);
    }
    ALL_PLAYERS.forEach(function (n) {
      var o = document.createElement("option");
      o.value = n;
      o.textContent = n;
      if (n === selected) o.selected = true;
      sel.appendChild(o);
    });
    var neu = document.createElement("option");
    neu.value = NEW_PLAYER_VALUE;
    neu.textContent = "New player\u2026";
    sel.appendChild(neu);
    return sel;
  }

  function buildSubForSelect(names, selected, taken) {
    var sel = document.createElement("select");
    sel.className = "sub-for";
    sel.setAttribute("aria-label", "Sub for");
    var opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "\u2014 pick \u2014";
    sel.appendChild(opt0);
    names.forEach(function (n) {
      var o = document.createElement("option");
      o.value = n;
      o.textContent = n;
      if (n === selected) o.selected = true;
      if (taken.indexOf(n) >= 0 && n !== selected) o.disabled = true;
      sel.appendChild(o);
    });
    return sel;
  }

  function subPlayerNameFromRow(tr) {
    var sel = tr.querySelector(".sub-pick-select");
    var newInp = tr.querySelector(".sub-pick-new");
    if (sel && sel.value === NEW_PLAYER_VALUE && newInp) return newInp.value.trim();
    if (sel && sel.value && sel.value !== NEW_PLAYER_VALUE) return sel.value.trim();
    return tr.getAttribute("data-player") || "";
  }

  function refreshSubForOptions(block) {
    var names = rosterNamesForBlock(block);
    subRows(block).forEach(function (tr) {
      var sel = tr.querySelector(".sub-for");
      if (!sel) return;
      var cur = sel.value;
      var taken = takenSubForSlots(block, tr);
      var parent = sel.parentNode;
      var nu = buildSubForSelect(names, cur, taken);
      parent.replaceChild(nu, sel);
      nu.addEventListener("change", function () {
        tr.setAttribute("data-sub-for", nu.value);
        refreshSubForOptions(block);
        updateSubSectionVisibility(block);
        markDirty();
      });
    });
  }

  function appendGameCell(tr, value, extraClass) {
    var cell = document.createElement("div");
    cell.className = "egrid-cell game-cell" + (extraClass ? " " + extraClass : "");
    cell.setAttribute("role", "cell");
    var inp = document.createElement("input");
    inp.type = "number";
    inp.inputMode = "numeric";
    inp.min = String(GAME_MIN);
    inp.max = String(GAME_MAX);
    inp.step = "1";
    inp.className = "game " + (extraClass === "game5-col" ? "game5" : "game-main");
    if (value != null && value !== "") inp.value = String(value);
    cell.appendChild(inp);
    tr.appendChild(cell);
  }

  function createSubRow(block, data) {
    data = data || {};
    var team = block.getAttribute("data-team");
    var tr = document.createElement("div");
    tr.className = "egrid-row sub-row";
    tr.setAttribute("role", "row");
    tr.setAttribute("data-row", "");
    tr.setAttribute("data-team", team);
    tr.setAttribute("data-substitute", "true");
    tr.setAttribute("data-player", data.player || "");
    tr.setAttribute("data-sub-for", data.subFor || "");

    var nameCell = document.createElement("div");
    nameCell.className = "egrid-cell egrid-cell--name";
    nameCell.setAttribute("role", "cell");
    var label = document.createElement("span");
    label.className = "sub-label";
    label.textContent = "Sub";
    nameCell.appendChild(label);
    nameCell.appendChild(buildSubPickSelect(data.player || ""));
    var newInp = document.createElement("input");
    newInp.type = "text";
    newInp.className = "sub-pick-new";
    newInp.placeholder = "New name";
    newInp.autocomplete = "off";
    if (data.player && ALL_PLAYERS.indexOf(data.player) < 0) {
      newInp.value = data.player;
      newInp.style.display = "block";
    } else {
      newInp.style.display = "none";
    }
    nameCell.appendChild(newInp);
    tr.appendChild(nameCell);

    var forCell = document.createElement("div");
    forCell.className = "egrid-cell";
    forCell.setAttribute("role", "cell");
    forCell.appendChild(
      buildSubForSelect(rosterNamesForBlock(block), data.subFor || "", takenSubForSlots(block, null))
    );
    tr.appendChild(forCell);

    var countCell = document.createElement("div");
    countCell.className = "egrid-cell";
    countCell.setAttribute("role", "cell");
    var countCb = document.createElement("input");
    countCb.type = "checkbox";
    countCb.className = "sub-count";
    countCb.setAttribute("aria-label", "Use sub score");
    if (data.count) countCb.checked = true;
    countCell.appendChild(countCb);
    tr.appendChild(countCell);

    appendGameCell(tr, data.game1, "");
    appendGameCell(tr, data.game2, "");
    appendGameCell(tr, data.game3, "");
    appendGameCell(tr, data.game4, "");
    appendGameCell(tr, data.game5, "game5-col");

    var rmCell = document.createElement("div");
    rmCell.className = "egrid-cell";
    rmCell.setAttribute("role", "cell");
    var rmBtn = document.createElement("button");
    rmBtn.type = "button";
    rmBtn.className = "remove-sub-btn";
    rmBtn.title = "Remove sub";
    rmBtn.textContent = "\u2715";
    rmCell.appendChild(rmBtn);
    tr.appendChild(rmCell);
    return tr;
  }

  function bindSubPickCell(tr) {
    var sel = tr.querySelector(".sub-pick-select");
    var newInp = tr.querySelector(".sub-pick-new");
    if (!sel) return;
    sel.addEventListener("change", function () {
      if (newInp) {
        if (sel.value === NEW_PLAYER_VALUE) {
          newInp.style.display = "block";
          newInp.focus();
        } else {
          newInp.style.display = "none";
          newInp.value = "";
        }
      }
      tr.setAttribute("data-player", subPlayerNameFromRow(tr));
      markDirty();
    });
    if (newInp) {
      newInp.addEventListener("input", function () {
        tr.setAttribute("data-player", newInp.value.trim());
        markDirty();
      });
    }
  }

  function bindGameInputs(tr) {
    tr.querySelectorAll("input.game").forEach(function (inp) {
      inp.addEventListener("input", function () {
        validateGameInput(inp);
        setRowError(tr, "");
        markDirty();
      });
      inp.addEventListener("blur", function () { validateGameInput(inp); });
    });
  }

  function bindSubRow(tr, block) {
    var removeBtn = tr.querySelector(".remove-sub-btn");
    if (removeBtn) {
      removeBtn.addEventListener("click", function () {
        var subForSel = tr.querySelector(".sub-for");
        var subFor = (subForSel && subForSel.value.trim()) || (tr.getAttribute("data-sub-for") || "").trim();
        tr.remove();
        if (subFor) setSubbedForPlayer(block, subFor, false);
        refreshSubForOptions(block);
        updateSubSectionVisibility(block);
        markDirty();
      });
    }
    var countCb = tr.querySelector(".sub-count");
    if (countCb) countCb.addEventListener("change", markDirty);
    bindSubPickCell(tr);
    bindGameInputs(tr);
  }

  function addSubRow(block, data) {
    var host = block.querySelector(".sub-rows");
    if (!host) return null;
    var tr = createSubRow(block, data || {});
    host.appendChild(tr);
    bindSubRow(tr, block);
    refreshSubForOptions(block);
    updateSubSectionVisibility(block);
    return tr;
  }

  function bindSubbedRow(tr) {
    var subbedCb = tr.querySelector("input.subbed");
    if (!subbedCb) return;
    subbedCb.addEventListener("change", function () {
      var block = tr.closest(".team-block");
      if (!block) return;
      var player = tr.getAttribute("data-player");
      if (subbedCb.checked) {
        ensureWeekOut(tr);
        if (!findSubRowForPlayer(block, player)) addSubRow(block, { subFor: player });
        var section = block.querySelector(".sub-section");
        if (section) section.scrollIntoView({ behavior: "smooth", block: "nearest" });
        var subTr = findSubRowForPlayer(block, player);
        if (subTr) {
          var sel = subTr.querySelector(".sub-pick-select");
          if (sel) sel.focus();
        }
      } else {
        removeSubForPlayer(block, player);
      }
      updateSubSectionVisibility(block);
      markDirty();
    });
    if (subbedCb.checked) {
      var block = tr.closest(".team-block");
      var player = tr.getAttribute("data-player");
      ensureWeekOut(tr);
      if (block && !findSubRowForPlayer(block, player)) addSubRow(block, { subFor: player });
      if (block) updateSubSectionVisibility(block);
    }
  }

  function bindAbsentRow(tr) {
    var absentInp = tr.querySelector("input.absent");
    if (!absentInp) return;
    absentInp.addEventListener("change", function () {
      setWeekAbsentRow(tr, absentInp.checked);
      if (absentInp.checked) {
        fillAbsentScores(tr, true);
      } else {
        var block = tr.closest(".team-block");
        var player = tr.getAttribute("data-player");
        if (block) {
          removeSubForPlayer(block, player);
          var subbedCb = tr.querySelector("input.subbed");
          if (subbedCb) subbedCb.checked = false;
          updateSubSectionVisibility(block);
        }
      }
      refreshGameMissRow(tr);
      markDirty();
    });
    applyWeekOutUi(tr);
  }

  function bindGameAbsentBoxes(tr) {
    tr.querySelectorAll("input.game-absent").forEach(function (cb) {
      cb.addEventListener("change", function () {
        if (cb.checked) {
          var cell = cb.closest(".game-cell");
          var inp = cell && cell.querySelector("input.game");
          if (inp) fillGameAbsentScore(inp, tr);
        }
        refreshGameMissRow(tr);
        markDirty();
      });
    });
    refreshGameMissRow(tr);
  }

  function initExistingSubRows() {
    document.querySelectorAll(".team-block").forEach(function (block) {
      var host = block.querySelector(".sub-rows");
      if (!host) return;
      var saved = [];
      try {
        saved = JSON.parse(host.getAttribute("data-subs") || "[]") || [];
      } catch (err) { saved = []; }
      host.removeAttribute("data-subs");
      saved.forEach(function (row) {
        addSubRow(block, {
          player: row.player_display_name || "",
          subFor: row.substituted_for || "",
          count: !!row.substitute_scores_count,
          game1: row.game1,
          game2: row.game2,
          game3: row.game3,
          game4: row.game4,
          game5: row.game5
        });
      });
      refreshSubForOptions(block);
      updateSubSectionVisibility(block);
    });
  }

  /* ---------- opponents ---------- */

  function findTeamBlock(teamName) {
    var blocks = document.querySelectorAll(".team-block");
    for (var i = 0; i < blocks.length; i++) {
      if (blocks[i].getAttribute("data-team") === teamName) return blocks[i];
    }
    return null;
  }

  function collectPairedTeams() {
    var paired = new Set();
    document.querySelectorAll(".team-block").forEach(function (block) {
      var team = block.getAttribute("data-team");
      var sel = block.querySelector(".team-opponent");
      var opp = sel && sel.value.trim();
      if (team && opp) {
        paired.add(team);
        paired.add(opp);
      }
    });
    return paired;
  }

  function refreshOpponentOptions() {
    var paired = collectPairedTeams();
    document.querySelectorAll(".team-block").forEach(function (block) {
      var team = block.getAttribute("data-team");
      var sel = block.querySelector(".team-opponent");
      if (!sel || !team) return;
      var current = sel.value.trim();
      sel.innerHTML = "";
      var empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "\u2014";
      sel.appendChild(empty);
      ALL_TEAMS.forEach(function (t) {
        if (t === team) return;
        if (paired.has(t) && t !== current) return;
        var opt = document.createElement("option");
        opt.value = t;
        opt.textContent = t;
        if (t === current) opt.selected = true;
        sel.appendChild(opt);
      });
      if (current) sel.value = current;
    });
  }

  function setOpponentSelect(teamName, opponentName, skipTeam) {
    var block = findTeamBlock(teamName);
    if (!block || teamName === skipTeam) return;
    var sel = block.querySelector(".team-opponent");
    if (!sel) return;
    syncingOpponents = true;
    sel.value = opponentName || "";
    sel.setAttribute("data-prev-opponent", opponentName || "");
    syncingOpponents = false;
  }

  function initOpponents() {
    document.querySelectorAll(".team-opponent").forEach(function (sel) {
      sel.setAttribute("data-prev-opponent", sel.value.trim());
      sel.addEventListener("change", function () {
        if (syncingOpponents) return;
        var block = sel.closest(".team-block");
        if (!block) return;
        var team = block.getAttribute("data-team");
        var opponent = sel.value.trim();
        var prev = sel.getAttribute("data-prev-opponent") || "";

        if (prev && prev !== opponent) {
          var prevBlock = findTeamBlock(prev);
          if (prevBlock) {
            var prevSel = prevBlock.querySelector(".team-opponent");
            if (prevSel && prevSel.value.trim() === team) {
              syncingOpponents = true;
              prevSel.value = "";
              prevSel.setAttribute("data-prev-opponent", "");
              syncingOpponents = false;
            }
          }
        }

        if (opponent) setOpponentSelect(opponent, team, team);
        sel.setAttribute("data-prev-opponent", opponent);
        refreshOpponentOptions();
        markDirty();
      });
    });
    refreshOpponentOptions();
  }

  /* ---------- keyboard flow ---------- */

  function gameInputsInColumn(inp) {
    var cell = inp.closest(".egrid-cell");
    var grid = inp.closest(".egrid, .sgrid");
    if (!cell || !grid) return [];
    var row = cell.parentElement;
    var index = Array.prototype.indexOf.call(row.children, cell);
    var out = [];
    Array.prototype.slice.call(grid.querySelectorAll("[data-row]")).forEach(function (r) {
      var c = r.children[index];
      var candidate = c && c.querySelector("input.game");
      if (candidate) out.push(candidate);
    });
    return out;
  }

  function moveInColumn(inp, delta) {
    var column = gameInputsInColumn(inp);
    var at = column.indexOf(inp);
    if (at < 0) return;
    var next = column[at + delta];
    if (!next) return;
    next.focus();
    next.select();
  }

  function initKeyboardFlow() {
    document.addEventListener("keydown", function (e) {
      var inp = e.target;
      if (!(inp instanceof HTMLInputElement) || !inp.classList.contains("game")) return;
      if (e.key === "Enter" || e.key === "ArrowDown") {
        e.preventDefault();
        moveInColumn(inp, 1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        moveInColumn(inp, -1);
      }
    });
  }

  /* ---------- drafts ---------- */

  function snapshot() {
    var out = { playoffs: playoffsChecked(), teams: {}, rows: [] };
    document.querySelectorAll(".team-block").forEach(function (block) {
      var team = block.getAttribute("data-team");
      var sel = block.querySelector(".team-opponent");
      out.teams[team] = {
        opponent: sel ? sel.value.trim() : "",
        game5: !block.classList.contains("hide-game5")
      };
    });
    rows().forEach(function (tr) {
      out.rows.push(rowPayload(tr));
    });
    return out;
  }

  function saveDraft() {
    if (!window.localStorage) return;
    try {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify({
        at: Date.now(),
        data: snapshot()
      }));
    } catch (err) { /* a full quota just means no draft */ }
  }

  function clearDraft() {
    if (!window.localStorage) return;
    try { window.localStorage.removeItem(DRAFT_KEY); } catch (err) { /* ignore */ }
  }

  function offerDraft() {
    if (!window.localStorage) return;
    var raw;
    try { raw = window.localStorage.getItem(DRAFT_KEY); } catch (err) { return; }
    if (!raw) return;
    var parsed;
    try { parsed = JSON.parse(raw); } catch (err) { clearDraft(); return; }
    if (!parsed || !parsed.data) return;

    var notice = document.getElementById("draft-notice");
    if (!notice) return;
    var text = notice.querySelector("[data-flash-text]");
    var when = parsed.at ? new Date(parsed.at).toLocaleString() : "earlier";
    if (text) {
      text.textContent = "Unsaved changes from " + when + " are still here. ";
      var restore = document.createElement("button");
      restore.type = "button";
      restore.className = "secondary";
      restore.textContent = "Restore";
      restore.addEventListener("click", function () {
        restoreDraft(parsed.data);
        notice.hidden = true;
      });
      var discard = document.createElement("button");
      discard.type = "button";
      discard.textContent = "Discard";
      discard.style.marginLeft = "0.4rem";
      discard.addEventListener("click", function () {
        clearDraft();
        notice.hidden = true;
      });
      text.appendChild(restore);
      text.appendChild(discard);
    }
    notice.hidden = false;
  }

  function restoreDraft(data) {
    if (!data) return;
    var playoffsCb = document.getElementById("week-playoffs");
    if (playoffsCb) playoffsCb.checked = !!data.playoffs;

    Object.keys(data.teams || {}).forEach(function (team) {
      var block = findTeamBlock(team);
      if (!block) return;
      setTeamGame5Visible(block, !!data.teams[team].game5);
      var sel = block.querySelector(".team-opponent");
      if (sel) {
        syncingOpponents = true;
        sel.value = data.teams[team].opponent || "";
        sel.setAttribute("data-prev-opponent", sel.value);
        syncingOpponents = false;
      }
    });
    refreshOpponentOptions();

    // Roster rows match on team plus player; subs are rebuilt from scratch.
    document.querySelectorAll(".sub-rows").forEach(function (host) { host.innerHTML = ""; });

    (data.rows || []).forEach(function (saved) {
      if (saved.substitute) {
        var block = findTeamBlock(saved.team);
        if (!block) return;
        addSubRow(block, {
          player: saved.player_display_name || "",
          subFor: saved.substituted_for || "",
          count: !!saved.substitute_scores_count,
          game1: saved.game1, game2: saved.game2, game3: saved.game3,
          game4: saved.game4, game5: saved.game5
        });
        return;
      }
      var tr = document.querySelector(
        '[data-row][data-substitute="false"][data-team="' + CSS.escape(saved.team || "") +
        '"][data-player="' + CSS.escape(saved.player_display_name || "") + '"]'
      );
      if (!tr) return;
      var inputs = tr.querySelectorAll("input.game");
      [saved.game1, saved.game2, saved.game3, saved.game4, saved.game5].forEach(function (v, i) {
        if (inputs[i]) {
          inputs[i].value = v == null ? "" : String(v);
          validateGameInput(inputs[i]);
        }
      });
      var absentCb = tr.querySelector("input.absent");
      if (absentCb) absentCb.checked = !!saved.absent;
      setWeekAbsentRow(tr, !!saved.absent);
      var misses = tr.querySelectorAll("input.game-absent");
      [saved.game1_absent, saved.game2_absent, saved.game3_absent,
       saved.game4_absent, saved.game5_absent].forEach(function (on, i) {
        if (misses[i] && !misses[i].disabled) misses[i].checked = !!on;
      });
      refreshGameMissRow(tr);
    });
    dirty = true;
  }

  /* ---------- payload ---------- */

  function playoffsChecked() {
    var cb = document.getElementById("week-playoffs");
    return !!(cb && cb.checked);
  }

  function teamOpponentMap() {
    var teamOpponents = {};
    document.querySelectorAll(".team-block").forEach(function (block) {
      var team = block.getAttribute("data-team");
      var sel = block.querySelector(".team-opponent");
      if (team && sel) {
        var v = sel.value.trim();
        if (v) teamOpponents[team] = v;
      }
    });
    Object.keys(teamOpponents).forEach(function (team) {
      var opp = teamOpponents[team];
      if (opp) teamOpponents[opp] = team;
    });
    return teamOpponents;
  }

  function rowPayload(tr, teamOpponents) {
    var games = [];
    tr.querySelectorAll("input.game").forEach(function (inp) {
      var v = inp.value.trim();
      games.push(v === "" ? null : parseInt(v, 10));
    });
    var isSub = tr.getAttribute("data-substitute") === "true";
    var absentInp = tr.querySelector("input.absent");
    var weekOut = absentInp ? absentInp.checked : false;
    var misses = tr.querySelectorAll("input.game-absent");
    var team = tr.getAttribute("data-team");
    var subForSel = tr.querySelector(".sub-for");
    var subCountCb = tr.querySelector(".sub-count");
    var opponents = teamOpponents || {};
    return {
      team: team,
      player_display_name: isSub ? subPlayerNameFromRow(tr) : tr.getAttribute("data-player"),
      opponent: opponents[team] || null,
      game1: games[0], game2: games[1], game3: games[2], game4: games[3], game5: games[4],
      absent: weekOut,
      game1_absent: !weekOut && !!(misses[0] && misses[0].checked),
      game2_absent: !weekOut && !!(misses[1] && misses[1].checked),
      game3_absent: !weekOut && !!(misses[2] && misses[2].checked),
      game4_absent: !weekOut && !!(misses[3] && misses[3].checked),
      game5_absent: !weekOut && !!(misses[4] && misses[4].checked),
      substitute: isSub,
      substituted_for: isSub && subForSel ? (subForSel.value.trim() || null) : null,
      substitute_scores_count: isSub && subCountCb ? subCountCb.checked : false
    };
  }

  function buildPayload() {
    var teamOpponents = teamOpponentMap();
    return {
      season: season,
      week: week,
      playoffs: playoffsChecked(),
      team_opponents: teamOpponents,
      team: teamFilter || null,
      rows: rows().map(function (tr) { return rowPayload(tr, teamOpponents); })
    };
  }

  /* ---------- save ---------- */

  var successBox = document.getElementById("save-success");
  var errorBox = document.getElementById("save-error");
  var errorList = document.getElementById("save-error-list");

  function showSuccess(message) {
    if (errorBox) errorBox.hidden = true;
    if (!successBox) return;
    var text = successBox.querySelector("[data-flash-text]");
    if (text) text.textContent = message || "Saved.";
    successBox.hidden = false;
    successBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function showErrors(message, problems) {
    if (successBox) successBox.hidden = true;
    if (!errorBox) {
      window.alert(message);
      return;
    }
    var text = errorBox.querySelector("[data-flash-text]");
    if (text) text.textContent = message || "Could not save.";
    if (errorList) {
      errorList.innerHTML = "";
      (problems || []).forEach(function (problem) {
        var li = document.createElement("li");
        if (problem.element) {
          var link = document.createElement("a");
          link.href = "#";
          link.textContent = problem.message;
          link.addEventListener("click", function (e) {
            e.preventDefault();
            problem.element.scrollIntoView({ behavior: "smooth", block: "center" });
            var focusable = problem.element.querySelector("input.game.is-bad")
              || problem.element.querySelector("input.game, select");
            if (focusable) focusable.focus();
          });
          li.appendChild(link);
        } else {
          li.textContent = problem.message;
        }
        errorList.appendChild(li);
      });
      errorList.hidden = !(problems || []).length;
    }
    errorBox.hidden = false;
    errorBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function localProblems() {
    var problems = [];
    clearAllRowErrors();

    rows().forEach(function (tr) {
      var bad = [];
      tr.querySelectorAll("input.game").forEach(function (inp) {
        if (!validateGameInput(inp)) bad.push(inp);
      });
      if (bad.length) {
        var who = tr.getAttribute("data-player") || "This row";
        setRowError(tr, SCORE_HINT);
        problems.push({
          message: who + ": " + SCORE_HINT,
          element: tr
        });
      }
    });

    subRows().forEach(function (tr) {
      var name = subPlayerNameFromRow(tr);
      var subForSel = tr.querySelector(".sub-for");
      var subFor = subForSel ? subForSel.value.trim() : "";
      var msg = null;
      if (!name) msg = "Each sub must select a player.";
      else if (!subFor) msg = "Each sub must pick who they subbed for.";
      if (msg) {
        setRowError(tr, msg);
        problems.push({ message: (name || "Substitute") + ": " + msg, element: tr });
      }
    });

    return problems;
  }

  function problemsFromServer(body) {
    var out = [];
    (body.problems || []).forEach(function (p) {
      var tr = null;
      if (typeof p.row_index === "number") {
        var all = rows();
        tr = all[p.row_index] || null;
      }
      if (tr) setRowError(tr, p.message);
      out.push({ message: p.message, element: tr });
    });
    return out;
  }

  function setSaving(on) {
    saving = on;
    var pending = document.getElementById("save-pending");
    var saveBtn = document.getElementById("save-btn");
    if (pending) pending.style.display = on ? "inline" : "none";
    if (saveBtn) saveBtn.disabled = on;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (saving) return;

    var problems = localProblems();
    if (problems.length) {
      showErrors(problems.length + " problem(s) to fix before saving.", problems);
      if (problems[0].element) {
        problems[0].element.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      return;
    }

    var payload = buildPayload();
    document.getElementById("payload-field").value = JSON.stringify(payload);
    setSaving(true);

    fetch(SAVE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
      credentials: "same-origin"
    })
      .then(function (res) {
        return res.json().then(
          function (body) { return { ok: res.ok, body: body }; },
          function () { return { ok: false, body: { error: "Unexpected server response." } }; }
        );
      })
      .then(function (result) {
        if (!result.ok || result.body.error) {
          showErrors(result.body.error || "Could not save.", problemsFromServer(result.body));
          return;
        }
        dirty = false;
        clearDraft();
        showSuccess(result.body.message || "Saved.");
      })
      .catch(function () {
        showErrors("Network error. Nothing was saved - your entries are still here.", []);
      })
      .finally(function () {
        setSaving(false);
      });
  });

  window.addEventListener("beforeunload", function (e) {
    if (!dirty || saving) return;
    e.preventDefault();
    e.returnValue = "";
    return "";
  });

  /* ---------- debug fill ---------- */

  function randomDebugScore() {
    return Math.floor(Math.random() * 71) + 150;
  }

  var debugFill = document.getElementById("debug-fill-scores");
  if (debugFill) {
    debugFill.addEventListener("click", function () {
      rows().forEach(function (tr) {
        var block = tr.closest(".team-block");
        var showG5 = block && !block.classList.contains("hide-game5");
        tr.querySelectorAll("input.game-main").forEach(function (inp) {
          inp.value = String(randomDebugScore());
        });
        if (showG5) {
          tr.querySelectorAll("input.game5").forEach(function (inp) {
            inp.value = String(randomDebugScore());
          });
        }
        tr.classList.remove("row-incomplete");
        tr.removeAttribute("title");
      });
      markDirty();
    });
  }

  /* ---------- scoreboard scan ---------- */

  function initScoreboardScan() {
    var fileInput = document.getElementById("scan-image");
    var runBtn = document.getElementById("scan-run");
    if (!fileInput || !runBtn) return;

    var statusEl = document.getElementById("scan-status");
    var loadingEl = document.getElementById("scan-loading");
    var reviewEl = document.getElementById("scan-review");
    var previewEl = document.getElementById("scan-preview");
    var errorsEl = document.getElementById("scan-errors");
    var teamsReview = document.getElementById("scan-teams-review");
    var applyBtn = document.getElementById("scan-apply");
    var cropStage = document.getElementById("scan-crop-stage");
    var cropImg = document.getElementById("scan-crop-img");
    var cropBox = document.getElementById("scan-crop-box");
    var cropDim = document.getElementById("scan-crop-dim");
    var cropHint = document.getElementById("scan-crop-hint");
    var recropBtn = document.getElementById("scan-recrop");
    var previewUrl = null;
    var fileObjectUrl = null;
    var cropRect = null;
    var dragStart = null;
    var scanTeams = [];
    var allTeamNames = ALL_TEAMS || [];

    function setStatus(msg, isError) {
      statusEl.textContent = msg || "";
      statusEl.className = "scan-status" + (isError ? " error" : "");
    }

    function setScanLoading(on) {
      if (loadingEl) {
        loadingEl.classList.toggle("visible", on);
        loadingEl.setAttribute("aria-hidden", on ? "false" : "true");
      }
      fileInput.disabled = on;
    }

    function clearPreviewUrl() {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
      }
    }

    function clearFileUrl() {
      if (fileObjectUrl) {
        URL.revokeObjectURL(fileObjectUrl);
        fileObjectUrl = null;
      }
    }

    function defaultCropRect() {
      return { x: 0, y: 0, w: 1, h: 1 };
    }

    function clampCrop(rect) {
      var minSize = 0.05;
      rect.w = Math.max(minSize, Math.min(1 - rect.x, rect.w));
      rect.h = Math.max(minSize, Math.min(1 - rect.y, rect.h));
      rect.x = Math.max(0, Math.min(1 - rect.w, rect.x));
      rect.y = Math.max(0, Math.min(1 - rect.h, rect.y));
      return rect;
    }

    function updateCropBox() {
      if (!cropRect || !cropImg.clientWidth) return;
      var left = cropRect.x * 100;
      var top = cropRect.y * 100;
      var width = cropRect.w * 100;
      var height = cropRect.h * 100;
      cropBox.style.left = left + "%";
      cropBox.style.top = top + "%";
      cropBox.style.width = width + "%";
      cropBox.style.height = height + "%";
      var ready = cropRect.w >= 0.05 && cropRect.h >= 0.05;
      cropBox.classList.toggle("ready", ready);
      if (cropDim) {
        cropDim.classList.toggle("ready", ready);
        if (ready) {
          var right = left + width;
          var bottom = top + height;
          cropDim.style.clipPath =
            "polygon(evenodd, 0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%, "
            + left + "% " + top + "%, " + right + "% " + top + "%, "
            + right + "% " + bottom + "%, " + left + "% " + bottom + "%, "
            + left + "% " + top + "%)";
        } else {
          cropDim.style.clipPath = "";
        }
      }
    }

    function hideCropUI(showRecropBtn) {
      cropStage.classList.remove("visible");
      cropHint.style.display = "none";
      cropBox.classList.remove("ready");
      if (cropDim) {
        cropDim.classList.remove("ready");
        cropDim.style.clipPath = "";
      }
      if (recropBtn) {
        recropBtn.style.display = showRecropBtn && cropImg.src ? "" : "none";
      }
    }

    function showCropUI() {
      if (!cropImg.src) return;
      cropStage.classList.add("visible");
      cropHint.style.display = "block";
      if (recropBtn) recropBtn.style.display = "none";
      updateCropBox();
    }

    function cropReady() {
      return cropRect && cropRect.w >= 0.05 && cropRect.h >= 0.05 && cropImg.naturalWidth > 0;
    }

    function refreshScanButton() {
      runBtn.disabled = !cropReady();
    }

    if (recropBtn) {
      recropBtn.addEventListener("click", function () {
        reviewEl.classList.remove("visible");
        showCropUI();
        setStatus("Adjust the crop box, then scan again.");
        refreshScanButton();
      });
    }

    function pointerToNorm(clientX, clientY) {
      var r = cropStage.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(1, (clientX - r.left) / r.width)),
        y: Math.max(0, Math.min(1, (clientY - r.top) / r.height))
      };
    }

    function onCropPointerDown(e) {
      if (!cropImg.src) return;
      e.preventDefault();
      dragStart = pointerToNorm(e.clientX, e.clientY);
      cropRect = { x: dragStart.x, y: dragStart.y, w: 0, h: 0 };
      updateCropBox();
      cropStage.setPointerCapture(e.pointerId);
    }

    function onCropPointerMove(e) {
      if (!dragStart) return;
      var p = pointerToNorm(e.clientX, e.clientY);
      cropRect = clampCrop({
        x: Math.min(dragStart.x, p.x),
        y: Math.min(dragStart.y, p.y),
        w: Math.abs(p.x - dragStart.x),
        h: Math.abs(p.y - dragStart.y)
      });
      updateCropBox();
      refreshScanButton();
    }

    function onCropPointerUp(e) {
      if (!dragStart) return;
      dragStart = null;
      try { cropStage.releasePointerCapture(e.pointerId); } catch (err) { /* ignore */ }
      if (cropRect) cropRect = clampCrop(cropRect);
      updateCropBox();
      refreshScanButton();
    }

    cropStage.addEventListener("pointerdown", onCropPointerDown);
    cropStage.addEventListener("pointermove", onCropPointerMove);
    cropStage.addEventListener("pointerup", onCropPointerUp);
    cropStage.addEventListener("pointercancel", onCropPointerUp);
    cropImg.addEventListener("load", function () {
      updateCropBox();
      refreshScanButton();
    });

    function exportCroppedBlob(callback) {
      var nw = cropImg.naturalWidth;
      var nh = cropImg.naturalHeight;
      var sx = Math.round(cropRect.x * nw);
      var sy = Math.round(cropRect.y * nh);
      var sw = Math.max(1, Math.round(cropRect.w * nw));
      var sh = Math.max(1, Math.round(cropRect.h * nh));
      var canvas = document.createElement("canvas");
      canvas.width = sw;
      canvas.height = sh;
      var ctx = canvas.getContext("2d");
      ctx.drawImage(cropImg, sx, sy, sw, sh, 0, 0, sw, sh);
      canvas.toBlob(function (blob) {
        callback(blob);
      }, "image/jpeg", 0.92);
    }

    fileInput.addEventListener("change", function () {
      clearPreviewUrl();
      clearFileUrl();
      scanTeams = [];
      reviewEl.classList.remove("visible");
      hideCropUI(false);
      errorsEl.innerHTML = "";
      if (teamsReview) teamsReview.innerHTML = "";
      cropImg.removeAttribute("src");
      cropRect = null;
      var file = fileInput.files && fileInput.files[0];
      if (!file) {
        refreshScanButton();
        setStatus("");
        return;
      }
      fileObjectUrl = URL.createObjectURL(file);
      cropImg.src = fileObjectUrl;
      cropRect = defaultCropRect();
      showCropUI();
      if (recropBtn) recropBtn.style.display = "none";
      setStatus("Full photo selected. Drag to crop if needed, then scan.");
      refreshScanButton();
    });

    function rosterForTeam(teamName) {
      var block = teamName ? findTeamBlock(teamName) : null;
      if (!block) return [];
      try {
        var raw = block.getAttribute("data-roster-names");
        return raw ? JSON.parse(raw) : [];
      } catch (err) {
        return [];
      }
    }

    function buildTeamSelect(selected, ocrName) {
      var sel = document.createElement("select");
      sel.className = "scan-team-assign";
      var empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "\u2014 choose team \u2014";
      sel.appendChild(empty);
      (allTeamNames || []).forEach(function (name) {
        var opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        if (name === selected) opt.selected = true;
        sel.appendChild(opt);
      });
      if (ocrName) sel.setAttribute("data-ocr-team", ocrName);
      return sel;
    }

    function buildOpponentSelect(selected, selfTeam) {
      var sel = document.createElement("select");
      sel.className = "scan-opponent-assign";
      var empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "\u2014 none \u2014";
      sel.appendChild(empty);
      (allTeamNames || []).forEach(function (name) {
        if (selfTeam && name === selfTeam) return;
        var opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        if (name === selected) opt.selected = true;
        sel.appendChild(opt);
      });
      return sel;
    }

    function syncScanOpponentDefaults() {
      if (!teamsReview) return;
      var blocks = teamsReview.querySelectorAll(".scan-team-block");
      if (blocks.length !== 2) return;
      var teamA = blocks[0].querySelector("select.scan-team-assign");
      var teamB = blocks[1].querySelector("select.scan-team-assign");
      var oppA = blocks[0].querySelector("select.scan-opponent-assign");
      var oppB = blocks[1].querySelector("select.scan-opponent-assign");
      var a = teamA && teamA.value.trim();
      var b = teamB && teamB.value.trim();
      if (!a || !b || a === b) return;
      // Rebuild options excluding self, then default to the other board team.
      function refill(oppSel, selfName, otherName) {
        if (!oppSel) return;
        var keep = oppSel.value.trim() || otherName;
        var next = buildOpponentSelect(keep === selfName ? otherName : keep, selfName);
        next.className = oppSel.className;
        oppSel.replaceWith(next);
      }
      refill(oppA, a, b);
      refill(oppB, b, a);
    }

    function buildAssignSelect(roster, selected) {
      var sel = document.createElement("select");
      sel.className = "scan-assign";
      var empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "\u2014 skip \u2014";
      sel.appendChild(empty);
      (roster || []).forEach(function (name) {
        var opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        if (name === selected) opt.selected = true;
        sel.appendChild(opt);
      });
      sel.addEventListener("change", highlightDuplicateAssigns);
      return sel;
    }

    function highlightDuplicateAssigns() {
      if (!teamsReview) return;
      teamsReview.querySelectorAll(".scan-team-block").forEach(function (block) {
        var seen = {};
        block.querySelectorAll("[data-scan-idx]").forEach(function (tr) {
          tr.classList.remove("duplicate-assign");
          var sel = tr.querySelector("select.scan-assign");
          var v = sel && sel.value.trim();
          if (!v) return;
          if (seen[v]) {
            tr.classList.add("duplicate-assign");
            seen[v].classList.add("duplicate-assign");
          } else {
            seen[v] = tr;
          }
        });
      });
    }

    function scanGameCell(row, key) {
      var cell = document.createElement("div");
      cell.className = "egrid-cell" + (key === "game5" ? " game5-col" : "");
      var inp = document.createElement("input");
      inp.type = "number";
      inp.inputMode = "numeric";
      inp.min = String(GAME_MIN);
      inp.max = String(GAME_MAX);
      inp.step = "1";
      inp.className = "scan-game";
      if (row[key] != null) inp.value = String(row[key]);
      cell.appendChild(inp);
      return cell;
    }

    function refillPlayerSelects(block) {
      var teamSel = block.querySelector("select.scan-team-assign");
      var teamName = teamSel && teamSel.value.trim();
      var roster = rosterForTeam(teamName);
      block.querySelectorAll("[data-scan-idx]").forEach(function (tr) {
        var assignCell = tr.querySelector(".scan-assign-cell");
        if (!assignCell) return;
        var prev = assignCell.querySelector("select.scan-assign");
        var prevVal = prev ? prev.value : "";
        var suggested = tr.getAttribute("data-suggested") || "";
        var pick = prevVal || suggested;
        if (pick && roster.indexOf(pick) < 0) pick = "";
        assignCell.innerHTML = "";
        assignCell.appendChild(buildAssignSelect(roster, pick));
      });
      highlightDuplicateAssigns();
    }

    function renderTeamBlock(teamData, teamIdx) {
      var wrap = document.createElement("div");
      wrap.className = "scan-team-block";
      wrap.setAttribute("data-team-idx", String(teamIdx));

      var title = document.createElement("h3");
      var ocr = teamData.ocr_name || ("Team " + (teamIdx + 1));
      title.textContent = ocr;
      wrap.appendChild(title);

      var matchRow = document.createElement("div");
      matchRow.className = "scan-team-match";
      var teamLabel = document.createElement("label");
      teamLabel.textContent = "Match to ";
      var matched = teamData.matched_team || "";
      var teamSel = buildTeamSelect(matched, ocr);
      teamSel.addEventListener("change", function () {
        refillPlayerSelects(wrap);
        syncScanOpponentDefaults();
      });
      teamLabel.appendChild(teamSel);
      matchRow.appendChild(teamLabel);

      var oppLabel = document.createElement("label");
      oppLabel.textContent = "Opponent ";
      var suggestedOpp = teamData.suggested_opponent || "";
      var oppSel = buildOpponentSelect(suggestedOpp, matched);
      oppLabel.appendChild(oppSel);
      matchRow.appendChild(oppLabel);
      wrap.appendChild(matchRow);

      var scroll = document.createElement("div");
      scroll.className = "grid-scroll";
      var grid = document.createElement("div");
      grid.className = "scan-grid";
      var head = document.createElement("div");
      head.className = "egrid-row";
      ["Board", "Assign to", "G1", "G2", "G3", "G4"].forEach(function (label) {
        var cell = document.createElement("div");
        cell.className = "egrid-cell egrid-cell--head";
        cell.textContent = label;
        head.appendChild(cell);
      });
      var g5Head = document.createElement("div");
      g5Head.className = "egrid-cell egrid-cell--head game5-col";
      g5Head.textContent = "G5";
      head.appendChild(g5Head);
      grid.appendChild(head);

      var roster = rosterForTeam(matched);
      if (!roster.length) roster = teamData.roster_players || [];
      (teamData.players || []).forEach(function (row, idx) {
        var tr = document.createElement("div");
        tr.className = "egrid-row";
        tr.dataset.scanIdx = String(idx);
        if (row.suggested_player) tr.setAttribute("data-suggested", row.suggested_player);

        var nameCell = document.createElement("div");
        nameCell.className = "egrid-cell egrid-cell--name";
        var ocrSpan = document.createElement("span");
        ocrSpan.className = "scan-ocr-name";
        ocrSpan.textContent = row.ocr_name || ("Row " + (idx + 1));
        ocrSpan.title = row.ocr_name || "";
        nameCell.appendChild(ocrSpan);
        tr.appendChild(nameCell);

        var assignCell = document.createElement("div");
        assignCell.className = "egrid-cell scan-assign-cell";
        assignCell.appendChild(buildAssignSelect(roster, row.suggested_player || ""));
        tr.appendChild(assignCell);

        ["game1", "game2", "game3", "game4", "game5"].forEach(function (k) {
          tr.appendChild(scanGameCell(row, k));
        });
        grid.appendChild(tr);
      });
      scroll.appendChild(grid);
      wrap.appendChild(scroll);

      var teamBlock = matched ? findTeamBlock(matched) : null;
      if (teamBlock) {
        grid.classList.toggle("hide-game5", teamBlock.classList.contains("hide-game5"));
      }
      return wrap;
    }

    function renderReview(data, previewBlob) {
      scanTeams = data.teams || [];
      if (data.all_teams && data.all_teams.length) {
        allTeamNames = data.all_teams;
      }
      errorsEl.innerHTML = "";
      (data.validation_errors || []).forEach(function (err) {
        var li = document.createElement("li");
        li.textContent = err;
        errorsEl.appendChild(li);
      });
      if (teamsReview) {
        teamsReview.innerHTML = "";
        scanTeams.forEach(function (teamData, idx) {
          teamsReview.appendChild(renderTeamBlock(teamData, idx));
        });
        syncScanOpponentDefaults();
      }
      highlightDuplicateAssigns();
      hideCropUI(true);
      clearPreviewUrl();
      if (previewBlob) {
        previewUrl = URL.createObjectURL(previewBlob);
        previewEl.src = previewUrl;
      }
      reviewEl.classList.add("visible");
      var errCount = (data.validation_errors || []).length;
      var nTeams = scanTeams.length;
      setStatus(
        errCount
          ? ("Review " + nTeams + " team(s) (" + errCount + " warning(s)).")
          : ("Review matches for " + nTeams + " team(s), then apply to the grid.")
      );
    }

    runBtn.addEventListener("click", function () {
      if (!cropReady()) return;
      runBtn.disabled = true;
      setScanLoading(true);
      setStatus("");
      exportCroppedBlob(function (blob) {
        if (!blob) {
          setScanLoading(false);
          setStatus("Could not prepare image.", true);
          runBtn.disabled = false;
          return;
        }
        var fd = new FormData();
        fd.append("image", blob, "scoreboard-crop.jpg");
        fd.append("season", season);
        fd.append("week", String(week));
        fetch(SCAN_URL, { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (res) {
            return res.json().then(function (body) {
              return { ok: res.ok, body: body };
            });
          })
          .then(function (result) {
            if (!result.ok) {
              setStatus(result.body.error || "Scan failed.", true);
              return;
            }
            renderReview(result.body, blob);
          })
          .catch(function () {
            setStatus("Network error during scan.", true);
          })
          .finally(function () {
            setScanLoading(false);
            refreshScanButton();
          });
      });
    });

    applyBtn.addEventListener("click", function () {
      highlightDuplicateAssigns();
      if (teamsReview && teamsReview.querySelector(".duplicate-assign")) {
        setStatus("Each player can only be assigned once per team.", true);
        return;
      }
      var applied = 0;
      var missingTeam = 0;
      var opponentPairs = [];
      if (!teamsReview) return;
      teamsReview.querySelectorAll(".scan-team-block").forEach(function (block) {
        var teamSel = block.querySelector("select.scan-team-assign");
        var teamName = teamSel && teamSel.value.trim();
        if (!teamName) {
          missingTeam += 1;
          return;
        }
        var oppSel = block.querySelector("select.scan-opponent-assign");
        var oppName = oppSel && oppSel.value.trim();
        if (oppName && oppName !== teamName) {
          opponentPairs.push({ team: teamName, opponent: oppName });
        }
        block.querySelectorAll("[data-scan-idx]").forEach(function (tr) {
          var sel = tr.querySelector("select.scan-assign");
          var player = sel && sel.value.trim();
          if (!player) return;
          var gridRow = document.querySelector(
            '[data-row][data-team="' + CSS.escape(teamName) + '"][data-player="' + CSS.escape(player) + '"]'
          );
          if (!gridRow) return;
          var teamBlock = findTeamBlock(teamName);
          var showG5 = teamBlock && !teamBlock.classList.contains("hide-game5");
          var inputs = gridRow.querySelectorAll("input.game");
          tr.querySelectorAll("input.scan-game").forEach(function (inp, gi) {
            if (gi === 4 && !showG5) return;
            var v = inp.value.trim();
            if (inputs[gi]) {
              inputs[gi].value = v;
              validateGameInput(inputs[gi]);
            }
          });
          gridRow.classList.remove("row-incomplete");
          gridRow.removeAttribute("title");
          applied += 1;
        });
      });
      opponentPairs.forEach(function (pair) {
        setOpponentSelect(pair.team, pair.opponent, null);
        setOpponentSelect(pair.opponent, pair.team, null);
      });
      if (opponentPairs.length) refreshOpponentOptions();
      if (!applied && missingTeam) {
        setStatus("Match each scanned team to a roster team first.", true);
        return;
      }
      if (applied) markDirty();
      setStatus(
        applied
          ? ("Applied " + applied + " player row(s)"
            + (opponentPairs.length ? " and opponents" : "")
            + ". Save when ready.")
          : "Choose a player for each row you want to apply."
      );
    });
  }

  /* ---------- boot ---------- */

  // Saved subs are placed first so a checked "Sub" box finds its existing row
  // instead of adding a duplicate.
  initExistingSubRows();
  rosterRows().forEach(function (tr) {
    bindAbsentRow(tr);
    bindSubbedRow(tr);
    bindGameAbsentBoxes(tr);
    bindGameInputs(tr);
    var subbed = tr.querySelector("input.subbed");
    if (subbed) subbed.addEventListener("change", markDirty);
  });
  rosterRows().forEach(applyWeekOutUi);
  initTeamGame5Toggles();
  initOpponents();
  initKeyboardFlow();
  initScoreboardScan();
  offerDraft();

  var playoffsCb = document.getElementById("week-playoffs");
  if (playoffsCb) playoffsCb.addEventListener("change", markDirty);

  if (successBox && !successBox.hidden) {
    successBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
})();

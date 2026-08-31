/* Season roster editor. Player rows and team cards are built from the two
   <template> elements only, so there is a single source for that markup. */
(function () {
  "use strict";

  var playersData = document.getElementById("all-players-data");
  var editor = document.getElementById("teams-editor");
  if (!editor) return;

  var ALL_PLAYERS = JSON.parse((playersData && playersData.textContent) || "[]");
  if (!Array.isArray(ALL_PLAYERS)) ALL_PLAYERS = [];

  var addTeamBtn = document.getElementById("add-team-btn");
  var teamTpl = document.getElementById("team-template").innerHTML;
  var playerRowTpl = document.getElementById("player-row-template").innerHTML;
  var NEW_PLAYER_VALUE = "__NEW__";

  function fieldName(teamIdx) {
    return "teams[" + teamIdx + "][player_pick][]";
  }

  function fillPlayerSelect(sel, selected, teamIdx) {
    sel.innerHTML = "";
    var empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "\u2014 select \u2014";
    sel.appendChild(empty);
    if (selected && selected !== NEW_PLAYER_VALUE && ALL_PLAYERS.indexOf(selected) < 0) {
      var legacy = document.createElement("option");
      legacy.value = selected;
      legacy.textContent = selected;
      legacy.selected = true;
      sel.appendChild(legacy);
    }
    ALL_PLAYERS.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      if (p === selected) opt.selected = true;
      sel.appendChild(opt);
    });
    var neu = document.createElement("option");
    neu.value = NEW_PLAYER_VALUE;
    neu.textContent = "New player\u2026";
    sel.appendChild(neu);
    sel.setAttribute("name", fieldName(teamIdx));
  }

  function playerNameFromRow(row) {
    var inp = row.querySelector(".player-pick-new");
    if (inp && inp.offsetParent !== null) return (inp.value || "").trim();
    var sel = row.querySelector(".player-pick-select");
    if (!sel || !sel.value || sel.value === NEW_PLAYER_VALUE) return "";
    return sel.value.trim();
  }

  function setRowNewPlayerMode(row, on, teamIdx) {
    var sel = row.querySelector(".player-pick-select");
    var inp = row.querySelector(".player-pick-new");
    if (!sel || !inp) return;
    var name = fieldName(teamIdx);
    if (on) {
      row.classList.add("player-row--new");
      sel.style.display = "none";
      sel.disabled = true;
      sel.removeAttribute("name");
      sel.removeAttribute("required");
      inp.style.display = "";
      inp.setAttribute("name", name);
      inp.setAttribute("required", "required");
      inp.focus();
    } else {
      row.classList.remove("player-row--new");
      inp.style.display = "none";
      inp.removeAttribute("name");
      inp.removeAttribute("required");
      inp.value = "";
      sel.style.display = "";
      sel.disabled = false;
      sel.setAttribute("name", name);
      sel.setAttribute("required", "required");
    }
  }

  function syncCaptainHidden(card) {
    var hidden = card.querySelector(".captain-hidden");
    if (!hidden) return;
    var checked = card.querySelector(".captain-cb:checked");
    hidden.value = checked ? playerNameFromRow(checked.closest(".player-row")) : "";
  }

  function bindCaptainCheckbox(cb, card) {
    cb.addEventListener("change", function () {
      if (cb.checked) {
        card.querySelectorAll(".captain-cb").forEach(function (other) {
          if (other !== cb) other.checked = false;
        });
      }
      syncCaptainHidden(card);
    });
  }

  function bindPlayerRow(row, card) {
    var teamIdx = card.getAttribute("data-team-index");
    row.querySelector(".remove-player").addEventListener("click", function () {
      var cb = row.querySelector(".captain-cb");
      var wasCaptain = cb && cb.checked;
      row.remove();
      if (wasCaptain) syncCaptainHidden(card);
    });
    var sel = row.querySelector(".player-pick-select");
    if (sel) {
      sel.addEventListener("change", function () {
        if (sel.value === NEW_PLAYER_VALUE) setRowNewPlayerMode(row, true, teamIdx);
        syncCaptainHidden(card);
      });
    }
    var inp = row.querySelector(".player-pick-new");
    if (inp) {
      inp.addEventListener("input", function () {
        var cb = row.querySelector(".captain-cb");
        if (cb && cb.checked) syncCaptainHidden(card);
      });
    }
    var cb = row.querySelector(".captain-cb");
    if (cb) bindCaptainCheckbox(cb, card);
  }

  function addPlayerRow(teamIdx, listEl, card, selected, isCaptain) {
    listEl.insertAdjacentHTML("beforeend", playerRowTpl.replace(/__TIDX__/g, String(teamIdx)));
    var row = listEl.lastElementChild;
    var sel = row.querySelector(".player-pick-select");
    fillPlayerSelect(sel, selected || "", teamIdx);
    if (selected && selected !== NEW_PLAYER_VALUE && ALL_PLAYERS.indexOf(selected) < 0) {
      setRowNewPlayerMode(row, true, teamIdx);
      row.querySelector(".player-pick-new").value = selected;
    }
    if (isCaptain) {
      card.querySelectorAll(".captain-cb").forEach(function (c) { c.checked = false; });
      var cb = row.querySelector(".captain-cb");
      if (cb) cb.checked = true;
    }
    bindPlayerRow(row, card);
    syncCaptainHidden(card);
    return row;
  }

  function bindTeamCard(card) {
    var teamIdx = card.getAttribute("data-team-index");
    var listEl = card.querySelector(".players-list");
    var addBtn = card.querySelector(".add-player");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        addPlayerRow(teamIdx, listEl, card, "", false);
      });
    }

    var players = [];
    var captain = "";
    try {
      players = JSON.parse(listEl.getAttribute("data-players") || "[]") || [];
      captain = JSON.parse(listEl.getAttribute("data-captain") || '""') || "";
    } catch (err) { /* an empty card is fine */ }

    players.forEach(function (name) {
      addPlayerRow(teamIdx, listEl, card, name || "", !!name && name === captain);
    });
    syncCaptainHidden(card);
    if (!listEl.children.length) addPlayerRow(teamIdx, listEl, card, "", false);
  }

  function nextTeamIndex() {
    var max = -1;
    editor.querySelectorAll("[data-team-index]").forEach(function (c) {
      var n = parseInt(c.getAttribute("data-team-index"), 10);
      if (n > max) max = n;
    });
    return max + 1;
  }

  if (addTeamBtn) {
    addTeamBtn.addEventListener("click", function () {
      var idx = nextTeamIndex();
      editor.insertAdjacentHTML("beforeend", teamTpl.replace(/__IDX__/g, String(idx)));
      bindTeamCard(editor.lastElementChild);
    });
  }

  editor.querySelectorAll(".team-card").forEach(bindTeamCard);
  if (addTeamBtn && !editor.children.length) addTeamBtn.click();
})();

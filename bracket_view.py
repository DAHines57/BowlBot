"""Playoff bracket page rendering.

Parked module: nothing imports this today. The bracket was retired from the UI
pending a redesign; restoring it means re-adding the route and nav link that
call ``build_playoff_bracket_html`` / ``build_bracket_index_html``.
"""
import html as html_module
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from placement_bracket import (
    expected_week2_cross_sets,
    matchups_by_cross_ordered_groups,
    order_matchups_by_labeled_groups,
)
from image_generator import (
    _LIST_CSS,
    _format_avg,
    _list_section,
    _render_list_page,
    _team_color_style,
    _team_name_cell_html,
)


from playoff_champion import (
    BracketSlot,
    _best_w3_groups,
    _match_matchups_to_theoretical_round,
    _matchup_identity,
    _pick_best_eight_team_placement_model,
    _playoff_losses_through_prior_rounds,
    _playoff_matchups_with_opponent,
    _resolve_two_week_parallel_playoffs,
    _week3_match_count,
    champion_from_playoff_snapshots,
    qf_matchups_in_bracket_slot_order,
)


def _matchup_winner_summary_html(m: dict) -> str:
    """Bold one-line 'Who won' for bracket view."""
    home = m["home"]
    away = m.get("away")
    hn, hstyle = html_module.escape(home["name"]), _team_color_style(home["name"])
    if not away:
        return (
            f'<div class="bracket-outcome bracket-outcome--bye">'
            f'<span class="bracket-outcome-main" style="{hstyle}">{hn}</span> advances'
            f"</div>"
        )
    an, astyle = html_module.escape(away["name"]), _team_color_style(away["name"])
    hr, ar = home.get("result", ""), away.get("result", "")
    if hr == "W" and ar == "L":
        main = f'<span class="bracket-outcome-main" style="{hstyle}">{hn}</span>'
        sub = f'<span class="bracket-outcome-sub">def. <span style="{astyle}">{an}</span></span>'
    elif ar == "W" and hr == "L":
        main = f'<span class="bracket-outcome-main" style="{astyle}">{an}</span>'
        sub = f'<span class="bracket-outcome-sub">def. <span style="{hstyle}">{hn}</span></span>'
    elif hr == "T" and ar == "T":
        return (
            f'<div class="bracket-outcome bracket-outcome--tie">'
            f"Tie: <span style=\"{hstyle}\">{hn}</span> &nbsp;·&nbsp; <span style=\"{astyle}\">{an}</span>"
            f"</div>"
        )
    else:
        return (
            f'<div class="bracket-outcome bracket-outcome--pending">'
            f"<span style=\"{hstyle}\">{hn}</span> vs <span style=\"{astyle}\">{an}</span>"
            f"</div>"
        )
    return f'<div class="bracket-outcome">{main} {sub}</div>'


def _bracket_zoom_viewport_html(inner: str) -> str:
    """Wrap bracket markup in a zoom/pan viewport (toolbar + stage)."""
    return (
        '<div class="bracket-zoom-controls" role="toolbar" aria-label="Bracket zoom">'
        '<button type="button" class="bracket-zoom-btn" data-zoom-action="out" '
        'title="Zoom out" aria-label="Zoom out">−</button>'
        '<button type="button" class="bracket-zoom-btn" data-zoom-action="fit" '
        'title="Zoom to fit" aria-label="Zoom to fit">Fit</button>'
        '<button type="button" class="bracket-zoom-btn" data-zoom-action="in" '
        'title="Zoom in" aria-label="Zoom in">+</button>'
        '<span class="bracket-zoom-label" aria-live="polite">—</span>'
        "</div>"
        '<div class="bracket-zoom-viewport">'
        '<div class="bracket-zoom-spacer">'
        f'<div class="bracket-zoom-stage">{inner}</div>'
        "</div></div>"
    )

_BRACKET_PAN_SCRIPT = r"""<script>
(function () {
  var THRESH = 5;
  var ZMIN = 0.2;
  var ZMAX = 2.5;
  var ZSTEP = 1.12;
  var activePopOuter = null;
  var pendingTap = null;

  function matchOuterFrom(el) {
    return el && el.closest ? el.closest(".bracket-cl-outer, .bracket-pair-wrap") : null;
  }

  function clamp(z) {
    return Math.max(ZMIN, Math.min(ZMAX, z));
  }

  function popLayer() {
    var layer = document.getElementById("bracket-pop-layer");
    if (!layer) {
      layer = document.createElement("div");
      layer.id = "bracket-pop-layer";
      document.body.appendChild(layer);
    }
    return layer;
  }

  function viewportSize() {
    var doc = document.documentElement;
    return {
      w: Math.min(window.innerWidth, doc.clientWidth || window.innerWidth),
      h: Math.min(window.innerHeight, doc.clientHeight || window.innerHeight),
    };
  }

  function measurePop(pop) {
    pop.style.position = "fixed";
    pop.style.display = "block";
    pop.style.visibility = "hidden";
    pop.style.left = "0";
    pop.style.top = "0";
    pop.style.right = "auto";
    pop.style.bottom = "auto";
    pop.style.maxHeight = "none";
    pop.style.overflowY = "";
    var rect = pop.getBoundingClientRect();
    return {
      w: rect.width || pop.scrollWidth || 280,
      h: rect.height || pop.scrollHeight || 180,
    };
  }

  function layoutFloatedPop(outer, pop) {
    var gap = 8;
    var pad = 10;
    var vp = viewportSize();
    var anchor = outer.getBoundingClientRect();
    var size = measurePop(pop);
    var w = size.w;
    var h = size.h;

    var spaceBelow = vp.h - pad - (anchor.bottom + gap);
    var spaceAbove = anchor.top - gap - pad;
    var placeAbove = spaceBelow < h && spaceAbove >= spaceBelow;
    if (spaceBelow < h && spaceAbove < h) {
      placeAbove = spaceAbove > spaceBelow;
    }

    var left = Math.max(pad, Math.min(anchor.left, vp.w - w - pad));
    var top = placeAbove ? anchor.top - h - gap : anchor.bottom + gap;

    if (placeAbove && top < pad) {
      top = pad;
    }
    if (!placeAbove && top + h > vp.h - pad) {
      top = Math.max(pad, anchor.top - h - gap);
      placeAbove = true;
    }

    pop.style.position = "fixed";
    pop.style.display = "block";
    pop.style.visibility = "visible";
    pop.style.left = left + "px";
    pop.style.top = top + "px";
    pop.style.right = "auto";
    pop.style.bottom = "auto";
    pop.classList.toggle("bracket-pop--above", placeAbove);

    var placed = pop.getBoundingClientRect();
    if (placed.bottom > vp.h - pad) {
      top = Math.max(pad, vp.h - pad - placed.height);
      pop.style.top = top + "px";
    }
    if (placed.top < pad) {
      pop.style.top = pad + "px";
    }
    placed = pop.getBoundingClientRect();
    if (placed.height > vp.h - pad * 2) {
      pop.style.maxHeight = vp.h - pad * 2 + "px";
      pop.style.overflowY = "auto";
    } else {
      pop.style.maxHeight = "";
      pop.style.overflowY = "";
    }
  }

  function placePop(outer) {
    var pop = outer._bracketPopEl || outer.querySelector(".bracket-pop");
    if (!pop) return;
    if (outer._bracketPopShown && pop.classList.contains("bracket-pop--floated")) {
      layoutFloatedPop(outer, pop);
      return;
    }
    outer._bracketPopEl = pop;
    pop._bracketPopHome = outer;
    popLayer().appendChild(pop);
    pop.classList.add("bracket-pop--floated");
    layoutFloatedPop(outer, pop);
    outer._bracketPopShown = true;
  }

  function clearPop(outer) {
    if (!outer._bracketPopShown) return;
    var pop = outer._bracketPopEl;
    var home = (pop && pop._bracketPopHome) || outer;
    if (!pop) return;
    pop.classList.remove("bracket-pop--floated");
    pop.classList.remove("bracket-pop--above");
    pop.style.position = "";
    pop.style.left = "";
    pop.style.top = "";
    pop.style.right = "";
    pop.style.bottom = "";
    pop.style.display = "";
    pop.style.visibility = "";
    pop.style.maxHeight = "";
    pop.style.overflowY = "";
    home.appendChild(pop);
    outer._bracketPopShown = false;
    outer._bracketPopEl = null;
    outer.classList.remove("bracket-match--tap-active");
    if (activePopOuter === outer) activePopOuter = null;
  }

  function clearActivePop() {
    if (activePopOuter) clearPop(activePopOuter);
  }

  function togglePopTap(outer) {
    if (activePopOuter === outer) {
      clearActivePop();
      return;
    }
    clearActivePop();
    placePop(outer);
    activePopOuter = outer;
    outer.classList.add("bracket-match--tap-active");
  }

  function viewportInsets(viewport) {
    var cs = window.getComputedStyle(viewport);
    return {
      l: parseFloat(cs.paddingLeft) || 0,
      t: parseFloat(cs.paddingTop) || 0,
      r: parseFloat(cs.paddingRight) || 0,
      b: parseFloat(cs.paddingBottom) || 0,
    };
  }

  function measureNatural(wrap) {
    var stage = wrap.querySelector(".bracket-zoom-stage");
    var spacer = wrap.querySelector(".bracket-zoom-spacer");
    if (!stage) return;
    stage.style.transform = "none";
    if (spacer) {
      spacer.style.width = "";
      spacer.style.height = "";
    }
    var shell = stage.querySelector(".bracket-shell");
    var sel =
      ".bracket-headers-row,.bracket-hcell,.bracket-subsec-h," +
      ".bracket-cl-outer,.bracket-cl-pending,.bracket-pair-wrap";
    var nodes = stage.querySelectorAll(sel);
    var minL = Infinity;
    var minT = Infinity;
    var maxR = -Infinity;
    var maxB = -Infinity;
    for (var i = 0; i < nodes.length; i++) {
      var r = nodes[i].getBoundingClientRect();
      if (r.width < 2 && r.height < 2) continue;
      minL = Math.min(minL, r.left);
      minT = Math.min(minT, r.top);
      maxR = Math.max(maxR, r.right);
      maxB = Math.max(maxB, r.bottom);
    }
    if (maxR > minL && maxB > minT) {
      wrap._bracketNaturalW = Math.ceil(maxR - minL + 20);
      wrap._bracketNaturalH = Math.ceil(maxB - minT + 20);
      return;
    }
    if (shell) {
      var dw = parseFloat(shell.getAttribute("data-bracket-w"));
      var dh = parseFloat(shell.getAttribute("data-bracket-h"));
      if (dw > 0 && dh > 0) {
        wrap._bracketNaturalW = dw;
        wrap._bracketNaturalH = dh;
        return;
      }
    }
    var w = stage.scrollWidth || stage.offsetWidth;
    var h = stage.scrollHeight || stage.offsetHeight;
    if (w > 0 && h > 0) {
      wrap._bracketNaturalW = w;
      wrap._bracketNaturalH = h;
    }
  }

  function setZoom(wrap, z, opts) {
    opts = opts || {};
    var stage = wrap.querySelector(".bracket-zoom-stage");
    var spacer = wrap.querySelector(".bracket-zoom-spacer");
    var viewport = wrap.querySelector(".bracket-zoom-viewport");
    var label = wrap.querySelector(".bracket-zoom-label");
    if (!stage || !spacer || !viewport) return;
    var nw = wrap._bracketNaturalW || stage.offsetWidth;
    var nh = wrap._bracketNaturalH || stage.offsetHeight;
    z = clamp(z);
    wrap._bracketZoom = z;
    stage.style.transform = "scale(" + z + ")";
    spacer.style.width = Math.ceil(nw * z) + "px";
    spacer.style.height = Math.ceil(nh * z) + "px";
    if (label) label.textContent = Math.round(z * 100) + "%";
    if (opts.center) {
      var ins = viewportInsets(viewport);
      var vw = viewport.clientWidth - ins.l - ins.r;
      var vh = viewport.clientHeight - ins.t - ins.b;
      var sl = spacer.offsetWidth;
      var st = spacer.offsetHeight;
      viewport.scrollLeft = sl > vw ? Math.max(0, (sl - vw) / 2) : 0;
      viewport.scrollTop = st > vh ? Math.max(0, (st - vh) / 2) : 0;
    }
  }

  function setZoomAt(wrap, z, clientX, clientY) {
    var viewport = wrap.querySelector(".bracket-zoom-viewport");
    if (!viewport) return;
    var oldZ = wrap._bracketZoom || 1;
    z = clamp(z);
    if (Math.abs(z - oldZ) < 0.0001) return;
    var rect = viewport.getBoundingClientRect();
    var ins = viewportInsets(viewport);
    var localX = clientX - rect.left - ins.l;
    var localY = clientY - rect.top - ins.t;
    var ratio = z / oldZ;
    var sl = viewport.scrollLeft;
    var st = viewport.scrollTop;
    setZoom(wrap, z, { center: false });
    viewport.scrollLeft = (sl + localX) * ratio - localX;
    viewport.scrollTop = (st + localY) * ratio - localY;
  }

  function fitZoom(wrap) {
    var viewport = wrap.querySelector(".bracket-zoom-viewport");
    if (!viewport) return;
    measureNatural(wrap);
    var nw = wrap._bracketNaturalW;
    var nh = wrap._bracketNaturalH;
    if (!nw || !nh) return;
    var ins = viewportInsets(viewport);
    var availW = viewport.clientWidth - ins.l - ins.r;
    var availH = viewport.clientHeight - ins.t - ins.b;
    var z = Math.min(availW / nw, availH / nh);
    if (!isFinite(z) || z <= 0) z = 1;
    wrap._bracketFitMode = true;
    setZoom(wrap, z, { center: true });
  }

  document.querySelectorAll(".bracket-wrap").forEach(function (wrap) {
    var viewport = wrap.querySelector(".bracket-zoom-viewport");
    if (!viewport) return;

    wrap._bracketZoom = 1;
    wrap._bracketFitMode = true;

    wrap.querySelectorAll("[data-zoom-action]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var act = btn.getAttribute("data-zoom-action");
        if (act === "fit") {
          fitZoom(wrap);
          return;
        }
        wrap._bracketFitMode = false;
        var cur = wrap._bracketZoom || 1;
        if (act === "in") setZoom(wrap, cur * ZSTEP, { center: false });
        else if (act === "out") setZoom(wrap, cur / ZSTEP, { center: false });
      });
    });

    function initFit() {
      measureNatural(wrap);
      fitZoom(wrap);
    }
    requestAnimationFrame(function () {
      requestAnimationFrame(initFit);
    });

    var resizeTimer;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        if (wrap._bracketFitMode) fitZoom(wrap);
      }, 120);
    });

    var dragging = false;
    var moved = false;
    var startX = 0;
    var startY = 0;
    var scroll0 = 0;
    var scroll0Y = 0;
    var pid = null;
    var pointers = new Map();
    var pinching = false;
    var pinchStartDist = 0;
    var pinchStartZoom = 1;

    function pinchDistance() {
      var pts = Array.from(pointers.values());
      if (pts.length < 2) return 0;
      var dx = pts[1].x - pts[0].x;
      var dy = pts[1].y - pts[0].y;
      return Math.sqrt(dx * dx + dy * dy);
    }

    function pinchCenter() {
      var pts = Array.from(pointers.values());
      return {
        x: (pts[0].x + pts[1].x) / 2,
        y: (pts[0].y + pts[1].y) / 2,
      };
    }

    function beginPinch() {
      pendingTap = null;
      endDrag();
      pinching = true;
      moved = true;
      wrap._bracketFitMode = false;
      pinchStartDist = pinchDistance();
      pinchStartZoom = wrap._bracketZoom || 1;
      wrap.classList.add("bracket-wrap--pinching");
    }

    function endPinch() {
      if (!pinching) return;
      pinching = false;
      pinchStartDist = 0;
      wrap.classList.remove("bracket-wrap--pinching");
    }

    function endDrag() {
      if (!dragging) return;
      dragging = false;
      wrap.classList.remove("bracket-wrap--dragging");
      try {
        if (pid !== null) viewport.releasePointerCapture(pid);
      } catch (e) {}
      pid = null;
    }

    viewport.addEventListener(
      "pointerdown",
      function (e) {
        if (e.target.closest(".bracket-zoom-controls")) return;
        if (e.pointerType === "mouse" && e.button !== 0) return;
        pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (pointers.size >= 2) {
          beginPinch();
          return;
        }
        var match = matchOuterFrom(e.target);
        if (match) {
          pendingTap = {
            outer: match,
            x: e.clientX,
            y: e.clientY,
            pid: e.pointerId,
            wrap: wrap,
            viewport: viewport,
          };
          return;
        }
        clearActivePop();
        dragging = true;
        moved = false;
        startX = e.clientX;
        startY = e.clientY;
        scroll0 = viewport.scrollLeft;
        scroll0Y = viewport.scrollTop;
        pid = e.pointerId;
        wrap.classList.add("bracket-wrap--dragging");
        viewport.setPointerCapture(e.pointerId);
      },
      { passive: true }
    );

    viewport.addEventListener(
      "pointermove",
      function (e) {
        if (pointers.has(e.pointerId)) {
          pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
        }
        if (pinching && pointers.size >= 2) {
          var dist = pinchDistance();
          if (pinchStartDist > 8 && dist > 0) {
            var center = pinchCenter();
            setZoomAt(
              wrap,
              pinchStartZoom * (dist / pinchStartDist),
              center.x,
              center.y
            );
          }
          e.preventDefault();
          return;
        }
        if (pendingTap && e.pointerId === pendingTap.pid) {
          var dx0 = e.clientX - pendingTap.x;
          var dy0 = e.clientY - pendingTap.y;
          if (Math.sqrt(dx0 * dx0 + dy0 * dy0) < THRESH) return;
          dragging = true;
          moved = true;
          startX = pendingTap.x;
          startY = pendingTap.y;
          scroll0 = viewport.scrollLeft;
          scroll0Y = viewport.scrollTop;
          pid = e.pointerId;
          pendingTap = null;
          wrap.classList.add("bracket-wrap--dragging");
          try {
            viewport.setPointerCapture(e.pointerId);
          } catch (err) {}
          viewport.scrollLeft = scroll0 - dx0;
          viewport.scrollTop = scroll0Y - dy0;
          e.preventDefault();
          return;
        }
        if (!dragging || e.pointerId !== pid) return;
        var dx = e.clientX - startX;
        var dy = e.clientY - startY;
        if (!moved && Math.sqrt(dx * dx + dy * dy) < THRESH) return;
        moved = true;
        viewport.scrollLeft = scroll0 - dx;
        viewport.scrollTop = scroll0Y - dy;
        e.preventDefault();
      },
      { passive: false }
    );

    function finishPointer(e) {
      var wasPinching = pinching;
      pointers.delete(e.pointerId);
      if (pinching && pointers.size < 2) endPinch();
      if (wasPinching) {
        pendingTap = null;
        endDrag();
        return;
      }
      if (pendingTap && e.pointerId === pendingTap.pid) {
        togglePopTap(pendingTap.outer);
        pendingTap = null;
        return;
      }
      if (dragging) endDrag();
      if (!dragging && !pendingTap && activePopOuter) {
        var pop = activePopOuter._bracketPopEl;
        if (!activePopOuter.contains(e.target) && !(pop && pop.contains(e.target))) {
          clearActivePop();
        }
      }
    }

    viewport.addEventListener("pointerup", finishPointer);
    viewport.addEventListener("pointercancel", function (e) {
      pointers.delete(e.pointerId);
      if (pinching && pointers.size < 2) endPinch();
      pendingTap = null;
      endDrag();
    });
    viewport.addEventListener("lostpointercapture", endDrag);

    viewport.addEventListener(
      "click",
      function (e) {
        if (moved) {
          e.preventDefault();
          e.stopImmediatePropagation();
          moved = false;
        }
      },
      true
    );

    viewport.addEventListener("scroll", function () {
      if (activePopOuter && activePopOuter._bracketPopEl) {
        layoutFloatedPop(activePopOuter, activePopOuter._bracketPopEl);
      }
    });
  });
})();
</script>"""

def build_bracket_index_html(seasons: List[str], *, embed: bool = False) -> str:
    """Index of /bracket?season=… links for each sheet season."""
    from urllib.parse import quote

    embed_qs = "&embed=1" if embed else ""
    items = []
    for s in seasons:
        items.append(
            f'<li><a href="/bracket?season={quote(s)}{embed_qs}">'
            f"{html_module.escape(s)}</a></li>"
        )
    extra = "\n.bracket-index-list { margin: 0; padding-left: 1.25rem; line-height: 1.9; }\n"
    inner = (
        '<div class="section"><div class="section-title">Seasons</div>'
        '<ul class="bracket-index-list">'
        f'{"".join(items)}</ul></div>'
    )
    return _render_list_page(
        css=_LIST_CSS + extra,
        title="🏆 PLAYOFFS",
        subtitle="Choose a season — bracket and playoff week scores on one page",
        sections=inner,
    )

BRACKET_COL_W_PX = 260

BRACKET_GAP_PX = 20

BRACKET_MATCH_SLOT_PX = 58

BRACKET_HEADER_ROW_PX = 52

def _bracket_center_rows(n_first: int, slot_px: float) -> List[List[float]]:
    rows: List[List[float]] = []
    n = n_first
    cur = [(i + 0.5) * slot_px for i in range(n)]
    rows.append(cur)
    while n > 1:
        n //= 2
        cur = [(rows[-1][2 * j] + rows[-1][2 * j + 1]) / 2 for j in range(n)]
        rows.append(cur)
    return rows

def _bracket_connectors_svg(
    center_rows: List[List[float]],
    n_rounds_draw: int,
    w_px: float,
    h_px: float,
    *,
    stroke: str = "#7c6ec4",
    stroke_opacity: float = 0.95,
) -> str:
    if n_rounds_draw < 2 or len(center_rows) < 2:
        return ""
    COL_W, GAP = BRACKET_COL_W_PX, BRACKET_GAP_PX
    d_parts: List[str] = []
    for r in range(min(n_rounds_draw - 1, len(center_rows) - 1)):
        for j in range(len(center_rows[r + 1])):
            y_lo = center_rows[r][2 * j]
            y_hi = center_rows[r][2 * j + 1]
            y_mid = (y_lo + y_hi) / 2
            xR = r * (COL_W + GAP) + COL_W - 14
            xM = r * (COL_W + GAP) + COL_W + GAP / 2
            xN = (r + 1) * (COL_W + GAP) + 16
            d_parts.append(f"M{xR:.1f},{y_lo:.1f}H{xM:.1f}")
            d_parts.append(f"M{xR:.1f},{y_hi:.1f}H{xM:.1f}")
            d_parts.append(f"M{xM:.1f},{y_lo:.1f}V{y_hi:.1f}")
            d_parts.append(f"M{xM:.1f},{y_mid:.1f}H{xN:.1f}")
    path_d = "".join(d_parts)
    return (
        f'<svg class="bracket-lines" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {w_px:.0f} {h_px:.0f}" width="100%" height="100%" '
        f'style="min-height:{h_px:.0f}px" '
        f'preserveAspectRatio="xMinYMin meet" aria-hidden="true">'
        f'<path d="{path_d}" fill="none" stroke="{stroke}" stroke-width="1.65" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="{stroke_opacity}"/></svg>'
    )

_BRACKET_EXTRA_CSS = """
html { overflow-x: hidden; }
body { overflow-y: auto; min-width: 0; }
.container { max-width: none; overflow: visible; }
.bracket-wrap {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin: 0 -6px;
  padding: 6px 12px 16px 12px;
  max-width: 100%;
  max-height: min(72vh, 760px);
  min-height: 360px;
}
.bracket-zoom-controls {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.bracket-zoom-btn {
  font: inherit;
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  min-width: 2rem;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #4a4068;
  background: #1e1a32;
  color: #d4cce8;
  cursor: pointer;
}
.bracket-zoom-btn:hover { border-color: #7c6ec4; color: #fff; }
.bracket-zoom-btn[data-zoom-action="fit"] {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 6px 12px;
}
.bracket-zoom-label {
  font-size: 11px;
  color: #8b849c;
  min-width: 3.2rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.bracket-zoom-viewport {
  flex: 1 1 auto;
  min-height: 280px;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  border-radius: 8px;
  background: rgba(10, 9, 16, 0.35);
  box-sizing: border-box;
  padding: 14px 12px 10px 18px;
}
.bracket-wrap.bracket-wrap--dragging .bracket-zoom-viewport,
.bracket-wrap.bracket-wrap--pinching .bracket-zoom-viewport {
  cursor: grabbing;
  user-select: none;
}
.bracket-wrap.bracket-wrap--dragging .bracket-zoom-viewport *,
.bracket-wrap.bracket-wrap--pinching .bracket-zoom-viewport * {
  user-select: none;
}
.bracket-zoom-spacer {
  position: relative;
  display: block;
}
.bracket-zoom-stage {
  transform-origin: 0 0;
  display: inline-block;
  vertical-align: top;
}
.bracket-shell { display: flex; flex-direction: column; gap: 4px; overflow: visible; }
.bracket-winners-title {
  font-size: 10px; font-weight: bold; letter-spacing: 1px; color: #6b6b80;
  text-transform: uppercase; margin: 6px 0 2px 0;
}
.bracket-headers-row {
  display: flex; flex-direction: row;
  gap: """ + str(BRACKET_GAP_PX) + """px;
  align-items: flex-end;
}
.bracket-hcell {
  width: """ + str(BRACKET_COL_W_PX) + """px;
  flex: 0 0 """ + str(BRACKET_COL_W_PX) + """px;
  min-height: 2.75rem;
}
.bracket-grid-main {
  position: relative;
  overflow: visible;
}
.bracket-main-tracks {
  position: relative;
  min-height: calc(var(--bf-slots, 4) * """ + str(BRACKET_MATCH_SLOT_PX) + """px);
  overflow: visible;
}
.bracket-tracks-row {
  display: flex; flex-direction: row;
  align-items: stretch;
  gap: """ + str(BRACKET_GAP_PX) + """px;
  position: relative;
  z-index: 1;
  min-height: calc(var(--bf-slots, 4) * """ + str(BRACKET_MATCH_SLOT_PX) + """px);
  overflow: visible;
}
.bracket-tcell {
  width: """ + str(BRACKET_COL_W_PX) + """px;
  flex: 0 0 """ + str(BRACKET_COL_W_PX) + """px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 10px;
  background: transparent;
  border-radius: 0;
  padding: 4px 0 8px 1px;
  box-sizing: border-box;
  overflow: visible;
}
.bracket-tcell .bracket-pair-wrap {
  flex: 0 0 auto;
  width: 100%;
  min-height: 3.65rem;
  box-sizing: border-box;
}
.bracket-tcell-inner {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  justify-content: flex-start;
}
.bracket-format-note {
  font-size: 12px;
  line-height: 1.5;
  color: #9a94b0;
  margin: 0 0 8px 0;
  padding: 8px 10px;
  background: rgba(26, 23, 48, 0.65);
  border-radius: 6px;
  border-left: 3px solid #7c6ec4;
}
.bracket-lines {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 0;
  pointer-events: none;
  overflow: visible;
}
.bracket-champion {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2d1b69 0%, #1a1730 100%);
  border: 1px solid #ffb86c44;
  text-align: center;
}
.bracket-champion-label {
  display: block;
  font-size: 10px;
  letter-spacing: 0.15em;
  color: #888;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.bracket-champion-name { font-size: 1.15rem; font-weight: 800; }
.bracket-losers-section table.bracket-losers-table { font-size: 12px; }
.bracket-losers-table td, .bracket-losers-table th { padding: 6px 8px; color: #ddd; }
.bracket-losers-table tbody tr:nth-child(even) { background: #1a1730; }
.bracket-pair-wrap {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: auto;
  overflow: visible;
  cursor: pointer;
}
.bracket-pair-wrap:hover,
.bracket-pair-wrap:focus-within { z-index: 80; }
.bracket-pair {
  cursor: default;
  border: none;
  border-right: 2px solid rgba(124, 110, 196, 0.55);
  border-radius: 0;
  padding: 7px 10px 7px 4px;
  background: rgba(15, 14, 22, 0.35);
  margin: 0 2px 0 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  transition: background 0.12s ease;
}
.bracket-pair-wrap:hover .bracket-pair,
.bracket-pair-wrap:focus-within .bracket-pair {
  background: rgba(45, 27, 105, 0.25);
}
.bracket-pair--bye {
  border-right-color: rgba(90, 84, 120, 0.45);
  background: rgba(15, 14, 22, 0.2);
}
.bracket-pair--pending { border-right-color: rgba(100, 92, 140, 0.4); }
.bracket-pair--path-title { border-right-color: rgba(212, 184, 122, 0.65); background: rgba(45, 35, 20, 0.2); }
.bracket-pair--path-place { border-right-color: rgba(120, 130, 155, 0.5); background: rgba(20, 22, 32, 0.35); }
.bracket-pair--path-mixed { border-right-color: rgba(154, 138, 191, 0.45); }
.bracket-path-chip {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 3px;
  color: #8b849c;
}
.bracket-path-chip--title { color: #d4b87a; }
.bracket-path-chip--place { color: #95a0b8; }
.bracket-path-chip--mixed { color: #b8a8d8; }
.bracket-subsec {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding-bottom: 4px;
}
.bracket-subsec-h {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 4px 0 8px 2px;
  margin-bottom: 4px;
  border-bottom: 1px solid #2a2445;
  color: #7a7394;
}
.bracket-subsec-h--title { color: #d4b87a; border-bottom-color: #4a3d28; }
.bracket-subsec-h--place { color: #8b93a8; border-bottom-color: #2a3040; }
.bracket-subsec-h--mixed { color: #9a8abf; border-bottom-color: #352a55; }
.bracket-pair-side {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
}
.bracket-pair-line { line-height: 1.35; margin: 1px 0; }
.bracket-pair-line--row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.bracket-pair-line--row .bracket-line {
  flex: 1 1 auto;
  min-width: 0;
}
.bracket-line-with-hint {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  flex: 1 1 auto;
  min-width: 0;
}
.bracket-pair-line--champ {
  border-left: 3px solid rgba(212, 184, 122, 0.9);
  padding-left: 8px;
  margin-left: 0;
  border-radius: 0 5px 5px 0;
  background: linear-gradient(
    90deg,
    rgba(212, 184, 122, 0.12) 0%,
    rgba(212, 184, 122, 0.02) 55%,
    transparent 100%
  );
}
.bracket-pair-line--place {
  border-left: 3px solid rgba(139, 147, 168, 0.65);
  padding-left: 8px;
  margin-left: 0;
  border-radius: 0 5px 5px 0;
  background: linear-gradient(
    90deg,
    rgba(100, 110, 140, 0.14) 0%,
    rgba(100, 110, 140, 0.03) 55%,
    transparent 100%
  );
}
.bracket-track-hint {
  flex-shrink: 0;
  display: inline-block;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 3px 7px;
  border-radius: 4px;
  line-height: 1.15;
}
.bracket-track-hint--champ {
  color: #f0dfb8;
  background: rgba(212, 184, 122, 0.22);
  border: 1px solid rgba(232, 210, 160, 0.45);
  box-shadow: 0 0 0 1px rgba(212, 184, 122, 0.12);
}
.bracket-track-hint--place {
  color: #c8ccd8;
  background: rgba(105, 115, 145, 0.28);
  border: 1px solid rgba(139, 147, 168, 0.45);
  box-shadow: 0 0 0 1px rgba(90, 100, 130, 0.15);
}
.bracket-badge {
  flex-shrink: 0;
  display: inline-block;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1.15;
}
.bracket-badge--w {
  background: rgba(80, 250, 123, 0.2);
  color: #7bf5a8;
  border: 1px solid rgba(80, 250, 123, 0.45);
}
.bracket-badge--l {
  background: rgba(255, 107, 129, 0.12);
  color: #ff9aaa;
  border: 1px solid rgba(255, 107, 129, 0.4);
}
.bracket-badge--t {
  background: rgba(255, 184, 108, 0.16);
  color: #ffc890;
  border: 1px solid rgba(255, 184, 108, 0.4);
}
.bracket-pair-mid {
  text-align: center;
  font-size: 8px;
  color: #4a4860;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 1px 0;
}
.bracket-line {
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.35;
}
.bracket-cl-row-main .bracket-line,
.bracket-pair-line--row .bracket-line {
  white-space: nowrap;
}
.bracket-line--ghost { color: #555; font-style: italic; font-weight: 500; font-size: 11px; }
.bracket-line--mini { font-size: 10px; color: #a8a4bc; font-weight: 500; }
.bracket-line--pending { color: #666; font-style: italic; font-size: 10.5px; font-weight: 500; }
.bracket-name--w { font-weight: 800; }
.bracket-name--l { opacity: 1; font-weight: 600; }
.bracket-name--tie { font-weight: 700; color: #e8c490; }
.bracket-name--pending { opacity: 0.7; }
.bracket-bye-note, .bracket-bye-tag {
  font-size: 9px;
  color: #5c5a70;
  font-style: italic;
  text-align: left;
  margin-top: 1px;
}
#bracket-pop-layer {
  position: fixed;
  inset: 0;
  width: 0;
  height: 0;
  overflow: visible;
  pointer-events: none;
  z-index: 2147483646;
}
.bracket-pop--floated {
  position: fixed !important;
  left: 0;
  top: 0;
  opacity: 1 !important;
  visibility: visible !important;
  pointer-events: auto;
  z-index: 2147483647;
  max-width: min(320px, calc(100vw - 24px));
}
.bracket-cl-outer.bracket-match--tap-active,
.bracket-pair-wrap.bracket-match--tap-active {
  outline: 2px solid #7c6ec4;
  outline-offset: 2px;
  z-index: 75;
}
.bracket-pop--floated.bracket-pop--above {
  box-shadow: 0 -8px 28px rgba(0,0,0,0.5);
}
.bracket-pop {
  position: absolute;
  left: 0;
  right: auto;
  top: calc(100% + 6px);
  bottom: auto;
  transform: none;
  width: max-content;
  max-width: min(320px, calc(100vw - 24px));
  padding: 9px 11px;
  background: linear-gradient(180deg, #252038 0%, #171528 100%);
  border: 1px solid #6a5f9e;
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0,0,0,0.55);
  font-size: 11px;
  line-height: 1.4;
  color: #dcd6ec;
  text-align: left;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.12s ease, visibility 0.12s ease;
  pointer-events: none;
  z-index: 2;
}
.bracket-cl-outer .bracket-pop {
  left: calc(1.1rem + 6px);
}
.bracket-pop-path {
  font-size: 10px;
  line-height: 1.4;
  color: #c4b8e8;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #322a50;
}
.bracket-pop-h {
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #8b849c;
  margin-bottom: 6px;
  padding-bottom: 5px;
  border-bottom: 1px solid #322a50;
}
.bracket-pop-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-top: 3px;
}
.bracket-pop-n { font-weight: 700; flex: 1; min-width: 0; font-size: 11px; }
.bracket-pop-pins { font-variant-numeric: tabular-nums; color: #ada5c8; font-size: 10px; }
.bracket-pop-res { font-weight: 800; width: 1.1rem; text-align: right; color: #ffb86c; font-size: 11px; }
.bracket-pop-meta { color: #948ca8; font-size: 10px; margin-top: 5px; }
.record-override-mark {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  color: #9b8ec4;
  cursor: help;
  line-height: 1;
}
.list-table .record-override-mark { font-size: 11px; margin-left: 3px; }
.bracket-cl-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bracket-cl-trail {
  flex: 0 0 auto;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 5px;
}
.bracket-cl-override-slot {
  flex: 0 0 0.65rem;
  width: 0.65rem;
  text-align: center;
  line-height: 1;
}
.bracket-cl-trail .record-override-mark { margin: 0; }
.bracket-pop-gh {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6d6785;
  margin: 8px 0 3px 0;
}
.bracket-pop-g {
  font-size: 10px;
  color: #aaa;
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}
.bracket-pop-gr { color: #7d7694; }
.bracket-pop-seed {
  font-size: 10px;
  color: #b4aecc;
  margin-top: 4px;
}
.bracket-pop-seed-l {
  display: inline-block;
  min-width: 3.5rem;
  color: #6d6788;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.bracket-idle {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #4a4858;
}
.bracket-wrap--classic {
  background: #232329;
  background-image: radial-gradient(circle at center, rgba(255,255,255,0.07) 1px, transparent 1px);
  background-size: 11px 11px;
  border-radius: 12px;
  border: 1px solid #353540;
  padding: 10px 8px 14px 8px;
}
.bracket-cl-outer {
  position: relative;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 6px;
  margin-bottom: 12px;
  z-index: 1;
  cursor: pointer;
}
.bracket-cl-outer:hover,
.bracket-cl-outer:focus-within { z-index: 80; }
.bracket-cl-outer:last-child { margin-bottom: 0; }
.bracket-cl-outer:focus { outline: 2px solid #7c6ec4; outline-offset: 2px; }
.bracket-cl-match {
  flex: 1 1 auto;
  min-width: 0;
  border-radius: 8px;
  border: 1px solid #3d3d48;
  background: linear-gradient(180deg, #2c2c34 0%, #25252d 100%);
  overflow: hidden;
  cursor: help;
}
.bracket-cl-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0;
  min-height: 1.75rem;
  border-bottom: 1px solid #1a1a22;
}
.bracket-cl-row:last-child { border-bottom: none; }
.bracket-cl-seed {
  flex: 0 0 1.65rem;
  width: 1.65rem;
  text-align: center;
  font-size: 10px;
  font-weight: 800;
  color: #d0ccd8;
  background: #3a3a44;
  border-right: 1px solid #2a2a32;
  align-self: stretch;
  display: flex;
  align-items: center;
  justify-content: center;
}
.bracket-cl-seed--empty { color: #5c5a68; font-weight: 600; }
.bracket-cl-row-main {
  flex: 1 1 auto;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 4px 10px;
  min-width: 0;
}
.bracket-cl-pending {
  font-size: 11px;
  color: #6d6a7a;
  font-style: italic;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px dashed #454254;
  margin-bottom: 10px;
}
.bracket-grid-main--classic .bracket-lines path {
  stroke: rgba(238, 240, 252, 0.78);
}
.bracket-note { font-size: 13px; color: #888; line-height: 1.5; margin-bottom: 18px; }
.bracket-hcell .wk-chip {
  font-size: 9px; color: #c9a86a; font-weight: 600; letter-spacing: 0.04em;
  margin: -2px 0 6px 0;
}
"""

def _backfill_ordered_matchups(
    ordered: List[Tuple[str, Optional[dict]]],
    rest: List[dict],
) -> List[Tuple[str, Optional[dict]]]:
    pool = list(rest)
    out: List[Tuple[str, Optional[dict]]] = []
    for label, mm in ordered:
        if mm is None and pool:
            mm = pool.pop(0)
        out.append((label, mm))
    return out

def _matchup_seed_sort_key(m: dict, seed_rank: Dict[str, int]) -> Tuple[int, int, str]:
    h = m["home"]["name"]
    a = m.get("away")
    if not a:
        return (seed_rank.get(h, 999), 999, h)
    an = a["name"]
    i1, i2 = seed_rank.get(h, 999), seed_rank.get(an, 999)
    return (min(i1, i2), max(i1, i2), h)

def _sort_matchups_with_alignment(
    matchups: List[dict], aligned: List[bool], seed_rank: Dict[str, int]
) -> Tuple[List[dict], List[bool]]:
    paired = list(zip(matchups, aligned))
    paired.sort(key=lambda p: _matchup_seed_sort_key(p[0], seed_rank))
    if not paired:
        return [], []
    ms, flags = zip(*paired)
    return list(ms), list(flags)

def _should_show_row_track_hints(ri: int, nr: int, aligned_to_slot: bool) -> bool:
    """When to show 1st/Lower row chrome: not first round; final round all; middle = aligned only."""
    if nr < 1:
        return False
    if ri == 0:
        return False
    if ri >= nr - 1:
        return True
    return aligned_to_slot

def _path_band(
    losses_before: Dict[str, int], hn: str, an: str
) -> Tuple[str, str, str]:
    """(short label, css suffix, hover blurb)."""
    la, lb = losses_before.get(hn, 0), losses_before.get(an, 0)
    if la == 0 and lb == 0:
        return (
            "1st place",
            "title",
            "Neither team had a playoff loss before this week — winner can still finish 1st.",
        )
    if la >= 1 and lb >= 1:
        return (
            "5th–8th place",
            "place",
            "Both teams already had a playoff loss — this game sorts the bottom half of the standings.",
        )
    return (
        "2nd–4th place",
        "mixed",
        "One team was still unbeaten in the playoffs and one had one loss before this week.",
    )

def _seed_rank_map(sorted_teams: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, int]:
    return {name: i for i, (name, _) in enumerate(sorted_teams)}

def _use_single_elim_connectors(
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    snapshots: List[Optional[dict]],
) -> bool:
    """False when the sheet runs a full field each week (everyone plays; placement rounds)."""
    nr = len(rounds)
    if nr < 2:
        return False
    for ri in range(nr):
        snap = snapshots[ri] if ri < len(snapshots) else None
        if not snap or not snap.get("matchups"):
            continue
        if len(snap["matchups"]) != len(rounds[ri]):
            return False
    return True

def _enriched_path_keys_distinct(enriched: List[Tuple[dict, Optional[str], Optional[str], Optional[str]]]) -> bool:
    keys = {e[2] for e in enriched if e[2]}
    return len(keys) > 1

def _slot_short_label(slot: BracketSlot) -> str:
    """Plain label for tooltips / compact bracket."""
    if slot is None:
        return "BYE"
    if isinstance(slot, str):
        return slot
    L, R = slot
    if isinstance(L, str) and isinstance(R, str):
        return f"{L} · {R}"
    return "Winner TBD"

def _theoretical_hover_inner_html(left: BracketSlot, right: BracketSlot) -> str:
    tl = html_module.escape(_slot_short_label(left))
    tr = html_module.escape(_slot_short_label(right))
    return (
        '<div class="bracket-pop-h">Seeded matchup</div>'
        f'<div class="bracket-pop-seed"><span class="bracket-pop-seed-l">Top</span>{tl}</div>'
        f'<div class="bracket-pop-seed"><span class="bracket-pop-seed-l">Bottom</span>{tr}</div>'
        '<div class="bracket-pop-meta">Winner advances to the next round.</div>'
    )

def _simple_theoretical_pair_html(left: BracketSlot, right: BracketSlot) -> str:
    def side_block(slot: BracketSlot) -> str:
        if slot is None:
            return '<span class="bracket-line bracket-line--ghost">—</span>'
        if isinstance(slot, str):
            st = _team_color_style(slot)
            return (
                f'<span class="bracket-line bracket-line--team" style="{st}">'
                f"{html_module.escape(slot)}</span>"
            )
        Ls, Rs = slot
        if isinstance(Ls, str) and isinstance(Rs, str):
            return (
                f'<span class="bracket-line bracket-line--mini">'
                f"{html_module.escape(Ls)} · {html_module.escape(Rs)}</span>"
            )
        return '<span class="bracket-line bracket-line--pending">Winner TBD</span>'

    extra = ""
    if (left is None) != (right is None):
        extra = '<span class="bracket-bye-tag">bye</span>'
    face = (
        f'<div class="bracket-pair bracket-pair--pending">'
        f'<div class="bracket-pair-side">{side_block(left)}</div>'
        f'<div class="bracket-pair-mid">vs</div>'
        f'<div class="bracket-pair-side">{side_block(right)}</div>'
        f"{extra}</div>"
    )
    pop = f'<aside class="bracket-pop">{_theoretical_hover_inner_html(left, right)}</aside>'
    return f'<div class="bracket-pair-wrap" tabindex="0">{face}{pop}</div>'

def _hover_game_line_html(
    game_num: int,
    h_p: int,
    a_p: int,
    h_r: str,
    a_r: str,
    home_name: str,
    away_name: str,
) -> str:
    if h_p <= 0 and a_p <= 0:
        return ""
    if h_r == "W":
        winner_html = (
            f'<span style="{_team_color_style(home_name)}">'
            f"{html_module.escape(home_name)}</span>"
        )
    elif a_r == "W":
        winner_html = (
            f'<span style="{_team_color_style(away_name)}">'
            f"{html_module.escape(away_name)}</span>"
        )
    elif h_r == "T":
        winner_html = '<span class="bracket-pop-gr">Tie</span>'
    else:
        winner_html = '<span class="bracket-pop-gr">—</span>'
    return (
        f'<div class="bracket-pop-g">G{game_num}: {h_p:,}–{a_p:,} · {winner_html}</div>'
    )

def _matchup_hover_inner_html(m: dict, *, extra_meta: Optional[str] = None) -> str:
    """Structured HTML for bracket hover card (not a native tooltip)."""
    meta = ""
    if extra_meta:
        meta = f'<div class="bracket-pop-path">{html_module.escape(extra_meta)}</div>'
    home = m["home"]
    away = m.get("away")
    if not away:
        hp = int(home.get("pins", 0))
        nm = home["name"]
        return (
            meta
            + '<div class="bracket-pop-h">Bye</div>'
            f'<div class="bracket-pop-n" style="{_team_color_style(nm)}">{html_module.escape(nm)}</div>'
            f'<div class="bracket-pop-meta">Advances · Total pins {hp:,}</div>'
        )
    hn, an = home["name"], away["name"]
    hp, ap = int(home.get("pins", 0)), int(away.get("pins", 0))
    hr, ar = home.get("result", ""), away.get("result", "")

    def score_row(name: str, pins: int, res: str, style: str) -> str:
        return (
            f'<div class="bracket-pop-row">'
            f'<span class="bracket-pop-n" style="{style}">{html_module.escape(name)}</span>'
            f'<span class="bracket-pop-pins">{pins:,}</span>'
            f'<span class="bracket-pop-res">{html_module.escape(res)}</span></div>'
        )

    head = '<div class="bracket-pop-h">Match totals</div>'
    body = score_row(hn, hp, hr, _team_color_style(hn)) + score_row(an, ap, ar, _team_color_style(an))
    gbits: List[str] = []
    for i, row in enumerate(m.get("game_results") or []):
        if len(row) >= 4:
            line = _hover_game_line_html(i + 1, row[2], row[3], row[0], row[1], hn, an)
            if line:
                gbits.append(line)
    gp_h = home.get("game_pins") or []
    gp_a = away.get("game_pins") or []
    if (len(gp_h) > 4 or len(gp_a) > 4) and len(m.get("game_results") or []) < 5:
        hp5 = int(gp_h[4]) if len(gp_h) > 4 else 0
        ap5 = int(gp_a[4]) if len(gp_a) > 4 else 0
        if hp5 > 0 or ap5 > 0:
            if hp5 > ap5:
                h5_r, a5_r = "W", "L"
            elif ap5 > hp5:
                h5_r, a5_r = "L", "W"
            else:
                h5_r, a5_r = "T", "T"
            line = _hover_game_line_html(5, hp5, ap5, h5_r, a5_r, hn, an)
            if line:
                gbits.append(line)
    games_h = ""
    if gbits:
        games_h = '<div class="bracket-pop-gh">Games</div>' + "".join(gbits)
    return meta + head + body + games_h

def _bracket_name_result_class(res: str) -> str:
    if res == "W":
        return "bracket-name--w"
    if res == "L":
        return "bracket-name--l"
    if res == "T":
        return "bracket-name--tie"
    return "bracket-name--pending"

def _record_override_marker_html() -> str:
    return (
        '<span class="record-override-mark" '
        'title="Regular-season win–loss from sheet override (pin totals unchanged)">†</span>'
    )

def _bracket_result_badge_html(res: str) -> str:
    """Small inline badge so winners/losers are obvious without hovering."""
    if res == "W":
        return '<span class="bracket-badge bracket-badge--w" title="Won match">W</span>'
    if res == "L":
        return '<span class="bracket-badge bracket-badge--l" title="Lost match">L</span>'
    if res == "T":
        return '<span class="bracket-badge bracket-badge--t" title="Tie">T</span>'
    return ""

def _matchup_series_games_won(side: Optional[dict], matchup: dict) -> Optional[int]:
    """Games won in this week's head-to-head (e.g. 3 in a 3–2 series)."""
    if not side:
        return None
    if not matchup.get("game_results") and side.get("result") in ("—", "", None):
        return None
    return int(side.get("wins", 0) or 0)

def _classic_team_row_cl(
    name: str,
    res: str,
    games_won: Optional[int],
    *,
    show_override_mark: bool = False,
) -> str:
    seed_el = (
        f'<span class="bracket-cl-seed" title="Games won in this matchup">{games_won}</span>'
        if games_won is not None
        else '<span class="bracket-cl-seed bracket-cl-seed--empty" title="Games won in this matchup">—</span>'
    )
    override_slot = (
        f'<span class="bracket-cl-override-slot">{_record_override_marker_html()}</span>'
        if show_override_mark
        else ""
    )
    trail = (
        f'<span class="bracket-cl-trail">'
        f"{override_slot}{_bracket_result_badge_html(res)}"
        f"</span>"
    )
    return (
        f'<div class="bracket-cl-row">'
        f"{seed_el}"
        f'<div class="bracket-cl-row-main">'
        f'<span class="bracket-line bracket-cl-name {_bracket_name_result_class(res)}" '
        f'style="{_team_color_style(name)}">{html_module.escape(name)}</span>'
        f"{trail}</div></div>"
    )

def _classic_match_block_html(
    m: dict,
    *,
    extra_meta: Optional[str] = None,
) -> str:
    overridden = bool(m.get("record_overridden"))
    away = m.get("away")
    if not away:
        nm = m["home"]["name"]
        row = _classic_team_row_cl(
            nm,
            m["home"].get("result", ""),
            _matchup_series_games_won(m["home"], m),
            show_override_mark=overridden,
        )
        pop = f'<aside class="bracket-pop">{_matchup_hover_inner_html(m, extra_meta=extra_meta)}</aside>'
        return (
            f'<div class="bracket-cl-outer" tabindex="0">'
            f'<div class="bracket-cl-match">{row}</div>{pop}</div>'
        )
    home = m["home"]
    hn, an = home["name"], away["name"]
    hr, ar = home.get("result", ""), away.get("result", "")
    rowh = _classic_team_row_cl(
        hn, hr, _matchup_series_games_won(home, m), show_override_mark=overridden
    )
    rowa = _classic_team_row_cl(
        an, ar, _matchup_series_games_won(away, m), show_override_mark=overridden
    )
    pop = f'<aside class="bracket-pop">{_matchup_hover_inner_html(m, extra_meta=extra_meta)}</aside>'
    return (
        f'<div class="bracket-cl-outer" tabindex="0">'
        f'<div class="bracket-cl-match">{rowh}{rowa}</div>{pop}</div>'
    )

def _classic_pending_line(label: str) -> str:
    return f'<div class="bracket-cl-pending">{html_module.escape(label)}</div>'

def _eight_team_week0_classic_column(
    snap: dict,
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
) -> str:
    slots = qf_matchups_in_bracket_slot_order(list(snap["matchups"]), rounds[0])
    parts: List[str] = []
    for i, m in enumerate(slots):
        if m is None:
            parts.append(
                _classic_pending_line(
                    "Quarterfinal slot — not on the sheet yet, or pairings differ from standard seeds."
                )
            )
            continue
        meta = "Quarterfinal — winners bracket"
        if m.get("_bye_pair"):
            meta = "Quarterfinal bye — both teams advance without a head-to-head week"
        parts.append(
            _classic_match_block_html(
                m,
                extra_meta=meta,
            )
        )
    return "".join(parts)

def _eight_team_week2_cross_layout_html(
    cross_ord: List[Optional[dict]],
    cross_sets: List[Optional[FrozenSet[str]]],
    rest: List[dict],
) -> str:
    sec: List[str] = []
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--title">'
        "Winners bracket — playing for 1st–4th place</div>"
    )
    for i, match_idx in enumerate((1, 2), start=1):
        mm = cross_ord[match_idx] if match_idx < len(cross_ord) else None
        meta = (
            "Semifinal on the winners side: the winner is still alive for 1st; "
            "the loser can still finish as high as 4th after finals week."
        )
        cs = cross_sets[match_idx] if match_idx < len(cross_sets) else None
        if mm:
            sec.append(
                _classic_match_block_html(
                    mm,
                    extra_meta=meta,
                )
            )
        elif cs is not None:
            sec.append(
                _classic_pending_line(
                    "Expected semifinal — not on the sheet yet, or quarterfinals still incomplete."
                )
            )
    sec.append("</div>")
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--place">'
        "Losers bracket — playing for 5th–8th place</div>"
    )
    for i, match_idx in enumerate((0, 3), start=1):
        mm = cross_ord[match_idx] if match_idx < len(cross_ord) else None
        meta = (
            "Semifinal on the losers side: both teams already lost a quarterfinal; "
            "this week sorts who can still reach 5th vs who is in the 7th–8th game next week."
        )
        cs = cross_sets[match_idx] if match_idx < len(cross_sets) else None
        if mm:
            sec.append(
                _classic_match_block_html(
                    mm,
                    extra_meta=meta,
                )
            )
        elif cs is not None:
            sec.append(
                _classic_pending_line(
                    "Expected semifinal — not on the sheet yet, or quarterfinals still incomplete."
                )
            )
    sec.append("</div>")
    for m in rest:
        sec.append(
            _classic_match_block_html(
                m,
                extra_meta="Playoff game (could not match to winners/losers semifinal slots).",
            )
        )
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'

def _eight_team_week2_parallel_layout_html(
    wb_ord: List[Optional[dict]],
    lb_ord: List[Optional[dict]],
    rest: List[dict],
) -> str:
    sec: List[str] = []
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--title">Winners bracket — playing for 1st–4th place</div>'
    )
    for idx, mm in enumerate(wb_ord):
        meta = "Winners bracket semifinal — quarterfinal winners from the same half of the draw"
        if mm:
            sec.append(_classic_match_block_html(mm, extra_meta=meta))
        elif idx < 2:
            sec.append(
                _classic_pending_line(
                    "Expected semifinal — not on the sheet yet, or quarterfinals still incomplete."
                )
            )
    sec.append("</div>")
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--place">Losers bracket — playing for 5th–8th place</div>'
    )
    for idx, mm in enumerate(lb_ord):
        meta = (
            "Losers bracket semifinal — quarterfinal losers from the same half of the draw "
            "(same pattern as the winners semifinal in that half)."
        )
        if mm:
            sec.append(_classic_match_block_html(mm, extra_meta=meta))
        elif idx < 2:
            sec.append(
                _classic_pending_line(
                    "Expected semifinal — not on the sheet yet, or quarterfinals still incomplete."
                )
            )
    sec.append("</div>")
    for m in rest:
        sec.append(
            _classic_match_block_html(
                m,
                extra_meta="Playoff game (could not match to semifinal slots).",
            )
        )
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'

def _eight_team_week2_loss_bucket_column(
    snap: dict,
    snapshots: List[Optional[dict]],
) -> str:
    """When QF pairings are non-standard, split week-2 games by playoff-loss count before this week."""
    losses_before = _playoff_losses_through_prior_rounds(snapshots, 1)
    ms = list(snap["matchups"])
    upper: List[dict] = []
    lower: List[dict] = []
    upper_solos: List[dict] = []
    lower_solos: List[dict] = []
    for m in ms:
        away = m.get("away")
        if not away:
            continue
        hn, an = m["home"]["name"], away["name"]
        la, lb = losses_before.get(hn, 0), losses_before.get(an, 0)
        if la >= 1 and lb >= 1:
            lower.append(m)
        else:
            upper.append(m)
    paired_sf = set()
    for m in upper + lower:
        away = m.get("away")
        if away:
            paired_sf.add(m["home"]["name"])
            paired_sf.add(away["name"])
    for m in ms:
        if m.get("away"):
            continue
        hn = m["home"]["name"]
        if hn in paired_sf:
            continue
        if losses_before.get(hn, 0) >= 1:
            lower_solos.append(m)
        else:
            upper_solos.append(m)
    sec: List[str] = []
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--title">'
        "Winners bracket — playing for 1st–4th place</div>"
    )
    meta_u = (
        "Semifinal week — at least one team has no quarterfinal loss "
        "(or custom draw: mixed winner/loser games are listed here when the sheet does not follow standard seeds)."
    )
    for mm in upper:
        sec.append(_classic_match_block_html(mm, extra_meta=meta_u))
    for mm in upper_solos:
        sec.append(
            _classic_match_block_html(
                mm,
                extra_meta="Bye week — advances without a head-to-head semifinal matchup on the sheet.",
            )
        )
    if len(upper) + len(upper_solos) < 2:
        sec.append(
            _classic_pending_line(
                "Expected winners-bracket semifinal — not on the sheet yet, or still a bye week."
            )
        )
    sec.append("</div>")
    sec.append(
        '<div class="bracket-subsec">'
        '<div class="bracket-subsec-h bracket-subsec-h--place">'
        "Losers bracket — playing for 5th–8th place</div>"
    )
    meta_l = (
        "Both teams lost in the quarterfinals — this week sorts placement in the bottom half of the playoffs."
    )
    for mm in lower:
        sec.append(_classic_match_block_html(mm, extra_meta=meta_l))
    for mm in lower_solos:
        sec.append(
            _classic_match_block_html(
                mm,
                extra_meta="Bye week — advances without a head-to-head semifinal matchup on the sheet.",
            )
        )
    if len(lower) + len(lower_solos) < 2:
        sec.append(
            _classic_pending_line(
                "Expected losers-bracket semifinal — not on the sheet yet, or still a bye week."
            )
        )
    sec.append("</div>")
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'

def _eight_team_week2_placement_column(
    snap: dict,
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    snapshots: List[Optional[dict]],
) -> Optional[str]:
    snap0 = snapshots[0] if snapshots else None
    if not snap0 or not snap0.get("matchups"):
        return None
    qf_ms = list(snap0["matchups"])
    ms1 = list(snap["matchups"])
    ms2: List[dict] = []
    if len(snapshots) > 2 and snapshots[2] and snapshots[2].get("matchups"):
        ms2 = list(snapshots[2]["matchups"])
    model = _pick_best_eight_team_placement_model(
        qf_ms, ms1, ms2, rounds[0], snapshots=snapshots
    )
    if model is None:
        return _eight_team_week2_loss_bucket_column(snap, snapshots)
    if model["kind"] == "cross":
        n_filled = sum(1 for x in model["cross_ord"] if x is not None)
    else:
        n_filled = sum(1 for x in model["wb_ord"] + model["lb_ord"] if x is not None)
    if n_filled < 4:
        return _eight_team_week2_loss_bucket_column(snap, snapshots)
    if model["kind"] == "cross":
        return _eight_team_week2_cross_layout_html(
            model["cross_ord"], model["cross_sets"], model["rest"]
        )
    return _eight_team_week2_parallel_layout_html(
        model["wb_ord"], model["lb_ord"], model["rest"]
    )

def _eight_team_path_band_column(
    snap: dict,
    snapshots: List[Optional[dict]],
    *,
    losses_before_col: int,
) -> str:
    """Group matchups by playoff-loss bands (1st, 3rd–4th, 5th–8th, etc.)."""
    all_ms = list(snap["matchups"])
    ms2 = _playoff_matchups_with_opponent(all_ms)
    solos = [m for m in all_ms if not m.get("away")]
    losses = _playoff_losses_through_prior_rounds(snapshots, losses_before_col)
    title_g: List[dict] = []
    mixed_g: List[dict] = []
    place_g: List[dict] = []
    title_s: List[dict] = []
    mixed_s: List[dict] = []
    place_s: List[dict] = []
    for m in ms2:
        away = m.get("away")
        if not away:
            continue
        hn, an = m["home"]["name"], away["name"]
        _lbl, key, _blur = _path_band(losses, hn, an)
        if key == "title":
            title_g.append(m)
        elif key == "mixed":
            mixed_g.append(m)
        else:
            place_g.append(m)
    for m in solos:
        hn = m["home"]["name"]
        n = losses.get(hn, 0)
        if n == 0:
            title_s.append(m)
        elif len(mixed_g) + len(mixed_s) < 2:
            mixed_s.append(m)
        else:
            place_s.append(m)
    sections: List[Tuple[str, str, List[dict]]] = [
        ("title", "1st & 2nd place", title_g + title_s),
        ("mixed", "3rd & 4th place", mixed_g + mixed_s),
        ("place", "5th & 6th place", place_g[:1] + place_s[:1]),
        ("place", "7th & 8th place", place_g[1:2] + place_s[1:2]),
    ]
    sec: List[str] = []
    for hkey, label, items in sections:
        sec.append(
            f'<div class="bracket-subsec">'
            f'<div class="bracket-subsec-h bracket-subsec-h--{hkey}">'
            f"{html_module.escape(label)}</div>"
        )
        if items:
            for mm in items:
                sec.append(
                    _classic_match_block_html(
                        mm,
                        extra_meta=label,
                    )
                )
        else:
            sec.append(
                _classic_pending_line(
                    "Placement game not on the sheet yet, or team had a bye this week."
                )
            )
        sec.append("</div>")
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'

def _eight_team_week3_path_band_column(
    snap: dict,
    snapshots: List[Optional[dict]],
) -> str:
    return _eight_team_path_band_column(
        snap, snapshots, losses_before_col=2
    )

def _eight_team_two_week_finals_column(
    snap: dict,
    snapshots: List[Optional[dict]],
) -> str:
    """Week 2 of a two-week playoff: placement games after quarterfinals only."""
    return _eight_team_path_band_column(
        snap, snapshots, losses_before_col=1
    )

def _is_two_week_eight_team_playoffs(
    pweeks: List[int],
    snapshots: List[Optional[dict]],
    n_teams: int,
) -> bool:
    if n_teams != 8 or len(pweeks) != 2:
        return False
    return any(s and s.get("matchups") for s in snapshots[:2])

def _labeled_placement_column_html(
    snap: dict,
    w3_groups: List[Tuple[FrozenSet[str], str]],
    *,
    pending_msg: str,
) -> str:
    """Four placement games with 1st–2nd, 3rd–4th, etc. labels."""
    ms2 = _playoff_matchups_with_opponent(list(snap["matchups"]))
    ordered, rest = order_matchups_by_labeled_groups(ms2, w3_groups)
    ordered = _backfill_ordered_matchups(ordered, rest)
    used_ids = {_matchup_identity(mm) for _lb, mm in ordered if mm is not None}
    rest_ms = [m for m in ms2 if _matchup_identity(m) not in used_ids]
    sec: List[str] = []
    for label, mm in ordered:
        if label.startswith("1st"):
            hkey = "title"
        elif "3rd" in label or "4th" in label:
            hkey = "mixed"
        else:
            hkey = "place"
        sec.append(
            f'<div class="bracket-subsec">'
            f'<div class="bracket-subsec-h bracket-subsec-h--{hkey}">'
            f"{html_module.escape(label)}</div>"
        )
        if mm:
            sec.append(
                _classic_match_block_html(
                    mm,
                    extra_meta=label,
                )
            )
        else:
            sec.append(_classic_pending_line(pending_msg))
        sec.append("</div>")
    if rest_ms:
        sec.append(
            '<div class="bracket-subsec">'
            '<div class="bracket-subsec-h bracket-subsec-h--mixed">Other matchups</div>'
        )
        for m in rest_ms:
            sec.append(
                _classic_match_block_html(
                    m, extra_meta="Playoff matchup"
                )
            )
        sec.append("</div>")
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'

def _eight_team_two_week_labeled_finals_column(
    snap: dict,
    w3_groups: List[Tuple[FrozenSet[str], str]],
) -> str:
    return _labeled_placement_column_html(
        snap,
        w3_groups,
        pending_msg=(
            "Placement game not on the sheet yet, or teams still TBD from semifinals."
        ),
    )

def _eight_team_week3_placement_column(
    snap: dict,
    snapshots: List[Optional[dict]],
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
) -> Optional[str]:
    snap0 = snapshots[0] if snapshots else None
    snap1 = snapshots[1] if len(snapshots) > 1 else None
    if not snap0 or not snap0.get("matchups") or not snap1 or not snap1.get("matchups"):
        return None
    qf_ms = list(snap0["matchups"])
    ms1 = list(snap1["matchups"])
    ms2 = _playoff_matchups_with_opponent(list(snap["matchups"]))
    if not ms2:
        return _eight_team_week3_path_band_column(snap, snapshots)
    w3 = _best_w3_groups(qf_ms, ms1, ms2, rounds[0], snapshots=snapshots)
    if not w3 or _week3_match_count(ms2, w3) < 2:
        return _eight_team_week3_path_band_column(snap, snapshots)
    ordered, rest = order_matchups_by_labeled_groups(ms2, w3)
    ordered = _backfill_ordered_matchups(ordered, rest)
    used_ids = {_matchup_identity(mm) for _lb, mm in ordered if mm is not None}
    rest = [m for m in ms2 if _matchup_identity(m) not in used_ids]
    sec: List[str] = []
    for label, mm in ordered:
        if label.startswith("1st"):
            hkey = "title"
        elif "3rd" in label or "4th" in label:
            hkey = "mixed"
        else:
            hkey = "place"
        sec.append(
            f'<div class="bracket-subsec">'
            f'<div class="bracket-subsec-h bracket-subsec-h--{hkey}">{html_module.escape(label)}</div>'
        )
        if mm:
            sec.append(
                _classic_match_block_html(
                    mm,
                    extra_meta=label,
                )
            )
        else:
            sec.append(
                _classic_pending_line(
                    "Matchup not in data or teams still TBD from the prior playoff week."
                )
            )
        sec.append("</div>")
    for m in rest:
        sec.append(
            _classic_match_block_html(
                m, extra_meta="Playoff matchup (extra)"
            )
        )
    return f'<div class="bracket-tcell-inner">{"".join(sec)}</div>'

def _bracket_team_track_hint_html(team_name: str, losses_before: Dict[str, int]) -> Tuple[str, str]:
    """Row modifier class + hint markup from playoff losses before this week."""
    n = losses_before.get(team_name, 0)
    if n == 0:
        return (
            " bracket-pair-line--champ",
            '<span class="bracket-track-hint bracket-track-hint--champ" '
            'title="Still in the hunt for 1st place — no playoff losses before this week">1st</span>',
        )
    return (
        " bracket-pair-line--place",
        '<span class="bracket-track-hint bracket-track-hint--place" '
        'title="Already took a playoff loss — still bowling for final rank (often 3rd–8th)">Lower</span>',
    )

def _bracket_team_rows_html(
    hn: str,
    an: str,
    hr: str,
    ar: str,
    losses_before: Optional[Dict[str, int]],
) -> str:
    """Two team lines with optional row hints for who is still playing for 1st vs lower spots."""

    def one(name: str, res: str) -> str:
        if losses_before is None:
            track = ""
            hint = ""
        else:
            track, hint = _bracket_team_track_hint_html(name, losses_before)
        return (
            f'<div class="bracket-pair-line bracket-pair-line--row{track}">'
            f'<div class="bracket-line-with-hint">'
            f'<span class="bracket-line {_bracket_name_result_class(res)}" style="{_team_color_style(name)}">'
            f"{html_module.escape(name)}</span>"
            f"{hint}</div>"
            f"{_bracket_result_badge_html(res)}</div>"
        )

    return one(hn, hr) + one(an, ar)

def _snapshot_matchup_wrap(
    m: dict,
    *,
    path_label: Optional[str],
    path_key: Optional[str],
    path_blurb: Optional[str],
    show_path_chip: bool,
    losses_before: Optional[Dict[str, int]] = None,
) -> str:
    pair_mod = f" bracket-pair--path-{path_key}" if path_key else ""
    chip = ""
    if show_path_chip and path_label and path_key:
        chip = (
            f'<div class="bracket-path-chip bracket-path-chip--{path_key}">'
            f"{html_module.escape(path_label)}</div>"
        )
    home = m["home"]
    away = m.get("away")
    pop = f'<aside class="bracket-pop">{_matchup_hover_inner_html(m, extra_meta=path_blurb)}</aside>'
    if not away:
        nm = home["name"]
        if losses_before is None:
            face = (
                f'<div class="bracket-pair bracket-pair--bye{pair_mod}">'
                f"{chip}"
                f'<span class="bracket-line bracket-line--team" style="{_team_color_style(nm)}">'
                f"{html_module.escape(nm)}</span>"
                f'<span class="bracket-bye-note">advances</span></div>'
            )
        else:
            track, hint = _bracket_team_track_hint_html(nm, losses_before)
            face = (
                f'<div class="bracket-pair bracket-pair--bye{pair_mod}">'
                f"{chip}"
                f'<div class="bracket-pair-line bracket-pair-line--row{track}">'
                f'<div class="bracket-line-with-hint">'
                f'<span class="bracket-line bracket-line--team" style="{_team_color_style(nm)}">'
                f"{html_module.escape(nm)}</span>"
                f"{hint}</div></div>"
                f'<span class="bracket-bye-note">advances</span></div>'
            )
        return f'<div class="bracket-pair-wrap" tabindex="0">{face}{pop}</div>'
    hn, an = home["name"], away["name"]
    hr, ar = home.get("result", ""), away.get("result", "")
    face = (
        f'<div class="bracket-pair{pair_mod}">'
        f"{chip}"
        f"{_bracket_team_rows_html(hn, an, hr, ar, losses_before)}"
        f"</div>"
    )
    return f'<div class="bracket-pair-wrap" tabindex="0">{face}{pop}</div>'

def _playoff_snapshot_column_html(
    snap: dict,
    ri: int,
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    snapshots: List[Optional[dict]],
    sorted_teams: List[Tuple[str, Dict[str, Any]]],
    *,
    split_placement_groups: bool,
    eight_placement_layout: bool = False,
    classic_skin: bool = False,
    two_week_playoffs: bool = False,
    two_week_parallel: Optional[dict] = None,
) -> str:
    seed_rank = _seed_rank_map(sorted_teams)
    nr = len(rounds)
    if (
        eight_placement_layout
        and nr == 3
        and len(rounds[0]) == 4
        and snap
        and snap.get("matchups")
    ):
        if ri == 0 and classic_skin:
            if two_week_parallel:
                return _eight_team_week2_parallel_layout_html(
                    two_week_parallel["wb_ord"],
                    two_week_parallel["lb_ord"],
                    two_week_parallel.get("rest", []),
                )
            return _eight_team_week0_classic_column(snap, rounds)
        if ri == 1 and two_week_playoffs:
            if two_week_parallel and two_week_parallel.get("w3_groups"):
                return _eight_team_two_week_labeled_finals_column(
                    snap, two_week_parallel["w3_groups"]
                )
            return _eight_team_two_week_finals_column(snap, snapshots)
        if ri == 1:
            w2 = _eight_team_week2_placement_column(
                snap, rounds, snapshots
            )
            if w2 is not None:
                return w2
        if ri == 2:
            w3 = _eight_team_week3_placement_column(snap, snapshots, rounds)
            if w3 is not None:
                return w3

    ms = list(snap["matchups"])
    if ri < len(rounds):
        ms, track_aligned = _match_matchups_to_theoretical_round(ms, rounds[ri])
    else:
        track_aligned = [True] * len(ms)
    ms, track_aligned = _sort_matchups_with_alignment(ms, track_aligned, seed_rank)
    losses_before = _playoff_losses_through_prior_rounds(snapshots, ri)
    align_by = {_matchup_identity(m): a for m, a in zip(ms, track_aligned)}
    enriched: List[Tuple[dict, Optional[str], Optional[str], Optional[str]]] = []
    for m in ms:
        away = m.get("away")
        if not away:
            enriched.append((m, None, None, None))
            continue
        hn, an = m["home"]["name"], away["name"]
        label, pkey, blurb = _path_band(losses_before, hn, an)
        enriched.append((m, label, pkey, blurb))

    multi = split_placement_groups and ri > 0 and _enriched_path_keys_distinct(enriched)
    if not multi:
        parts: List[str] = []
        for j, (m, label, pkey, blurb) in enumerate(enriched):
            af = track_aligned[j]
            show_row_track = _should_show_row_track_hints(ri, nr, af)
            lb = losses_before if show_row_track else None
            chip_on = ri > 0 and not multi and show_row_track
            parts.append(
                _snapshot_matchup_wrap(
                    m,
                    path_label=label,
                    path_key=pkey,
                    path_blurb=blurb,
                    show_path_chip=chip_on,
                    losses_before=lb,
                )
            )
        return "".join(parts)

    buckets: Dict[str, List[Tuple[dict, Optional[str], Optional[str], Optional[str]]]] = {
        "title": [],
        "mixed": [],
        "place": [],
    }
    for row in enriched:
        _m, _lab, pk, _b = row
        if pk is None:
            buckets["title"].append(row)
        elif pk in buckets:
            buckets[pk].append(row)
        else:
            buckets["mixed"].append(row)

    titles = {
        "title": "1st place (no playoff losses yet)",
        "mixed": "2nd–4th place",
        "place": "5th–8th place",
    }
    section_parts: List[str] = []
    for key in ("title", "mixed", "place"):
        rows = buckets[key]
        if not rows:
            continue
        inner = "".join(
            _snapshot_matchup_wrap(
                m,
                path_label=lab,
                path_key=pk,
                path_blurb=blob,
                show_path_chip=False,
                losses_before=(
                    losses_before
                    if _should_show_row_track_hints(
                        ri, nr, align_by.get(_matchup_identity(m), False)
                    )
                    else None
                ),
            )
            for (m, lab, pk, blob) in rows
        )
        section_parts.append(
            f'<div class="bracket-subsec">'
            f'<div class="bracket-subsec-h bracket-subsec-h--{key}">{html_module.escape(titles[key])}</div>'
            f"{inner}</div>"
        )
    return f'<div class="bracket-tcell-inner">{"".join(section_parts)}</div>'

def _bracket_round_title(
    round_idx: int,
    num_rounds: int,
    *,
    two_week_playoffs: bool = False,
    two_week_parallel_semis: bool = False,
) -> str:
    if two_week_playoffs and num_rounds == 2:
        if two_week_parallel_semis:
            return ("Semifinals", "Placement finals")[round_idx]
        return ("Quarterfinals", "Placement finals")[round_idx]
    dist = num_rounds - 1 - round_idx
    if dist == 0:
        return "Final"
    if dist == 1:
        return "Semifinals"
    if dist == 2:
        return "Quarterfinals"
    return f"Round {round_idx + 1}"

def build_playoff_bracket_html(
    season: str,
    seeding_week: int,
    sorted_teams: List[Tuple[str, Dict[str, Any]]],
    rounds: List[List[Tuple[BracketSlot, BracketSlot]]],
    playoff_week_numbers: Optional[List[int]] = None,
    playoff_matchups_by_round: Optional[List[Optional[dict]]] = None,
) -> str:
    """sorted_teams: best first, (name, stats).

    If playoff_week_numbers / playoff_matchups_by_round are set, each index aligns with a bracket
    column and shows compact names with a styled hover card for scores and games; otherwise seeds.
    """
    snapshots = playoff_matchups_by_round or []
    champion_team = champion_from_playoff_snapshots(snapshots)
    headers = [
        {"label": "Seed", "right": True},
        {"label": "Team"},
        {"label": "Record"},
        {"label": "Avg", "right": True},
        {"label": "Pins", "right": True},
    ]
    rows = []
    for i, (name, stats) in enumerate(sorted_teams, 1):
        w = stats.get("wins", 0)
        l = stats.get("losses", 0)
        t = stats.get("ties", 0)
        record = f"{w}-{l}" + (f"-{t}" if t else "")
        if stats.get("record_override_mark"):
            record += _record_override_marker_html()
        avg = stats.get("avg_per_game", 0)
        pins = stats.get("pins_for", 0)
        rows.append([
            {"val": i, "cls": "right rank"},
            {
                "val": _team_name_cell_html(name, champion_team),
                "cls": "name-col",
                "style": _team_color_style(name),
                "sort": name.lower(),
            },
            {"val": record, "cls": "record", "sort": w * 10000 + l * 100 + t},
            {"val": _format_avg(avg), "cls": "right gold"},
            {"val": f"{pins:,}", "cls": "right sub-col", "sort": pins},
        ])
    seed_section = _list_section(
        f"Seeds (record through week {seeding_week})",
        headers,
        rows,
    )
    nr = len(rounds)
    pweeks = playoff_week_numbers or []
    num_cols = max(len(rounds), len(pweeks))

    use_elim_svg = _use_single_elim_connectors(rounds, snapshots)
    split_placement = not use_elim_svg
    has_playoff_data = any(s and s.get("matchups") for s in snapshots)
    n_teams = len(sorted_teams)
    eight_placement_layout = (
        split_placement
        and has_playoff_data
        and n_teams == 8
        and nr == 3
        and bool(rounds)
        and len(rounds[0]) == 4
    )
    classic_skin = eight_placement_layout
    two_week_playoffs = _is_two_week_eight_team_playoffs(pweeks, snapshots, n_teams)
    seed_rank_for_resolve = {name: i for i, (name, _) in enumerate(sorted_teams)}
    two_week_parallel = (
        _resolve_two_week_parallel_playoffs(snapshots, seed_rank_for_resolve)
        if two_week_playoffs
        else None
    )
    if two_week_playoffs:
        num_cols = 2

    header_frag: List[str] = []
    track_frag: List[str] = []
    title_rounds = 2 if two_week_playoffs else nr
    two_week_parallel_semis = bool(two_week_parallel)
    for ri in range(num_cols):
        snap = snapshots[ri] if ri < len(snapshots) else None
        pw = pweeks[ri] if ri < len(pweeks) else None
        has_actual = bool(snap and snap.get("matchups"))

        if has_actual and pw is not None:
            disp = (
                _bracket_round_title(
                    ri,
                    title_rounds,
                    two_week_playoffs=two_week_playoffs,
                    two_week_parallel_semis=two_week_parallel_semis,
                )
                if ri < title_rounds
                else f"Week {pw}"
            )
            col_title = html_module.escape(disp)
            wk_line = f'<div class="wk-chip">Week {pw}</div>'
            body = _playoff_snapshot_column_html(
                snap,
                ri,
                rounds,
                snapshots,
                sorted_teams,
                split_placement_groups=split_placement,
                eight_placement_layout=eight_placement_layout,
                classic_skin=classic_skin,
                two_week_playoffs=two_week_playoffs,
                two_week_parallel=two_week_parallel,
            )
            header_frag.append(
                f'<div class="bracket-hcell">'
                f'<div class="section-title" style="margin-bottom:4px;">{col_title}</div>{wk_line}</div>'
            )
            track_frag.append(f'<div class="bracket-tcell">{body}</div>')
        elif ri < len(rounds):
            title_disp = html_module.escape(
                _bracket_round_title(
                    ri,
                    title_rounds,
                    two_week_playoffs=two_week_playoffs,
                    two_week_parallel_semis=two_week_parallel_semis,
                )
                if title_rounds
                else f"Round {ri + 1}"
            )
            matches = rounds[ri]
            blocks = [_simple_theoretical_pair_html(left, right) for left, right in matches]
            wk_pending = ""
            if pw is not None and not has_actual:
                wk_pending = f'<div class="wk-chip">Week {pw} · no matchup data yet</div>'
            header_frag.append(
                f'<div class="bracket-hcell">'
                f'<div class="section-title" style="margin-bottom:4px;">{title_disp}</div>{wk_pending}</div>'
            )
            track_frag.append(f'<div class="bracket-tcell">{"".join(blocks)}</div>')
        else:
            if pw is not None:
                header_frag.append(
                    f'<div class="bracket-hcell">'
                    f'<div class="section-title" style="margin-bottom:4px;">'
                    f'{html_module.escape(f"Week {pw}")}</div>'
                    f'<div class="wk-chip">No matchup data yet</div></div>'
                )
                track_frag.append(
                    '<div class="bracket-tcell"><span class="bracket-idle">—</span></div>'
                )
            else:
                title_disp = html_module.escape(
                    _bracket_round_title(
                        ri,
                        title_rounds,
                        two_week_playoffs=two_week_playoffs,
                        two_week_parallel_semis=two_week_parallel_semis,
                    )
                    if title_rounds
                    else f"Round {ri + 1}"
                )
                header_frag.append(
                    f'<div class="bracket-hcell">'
                    f'<div class="section-title" style="margin-bottom:4px;">{title_disp}</div></div>'
                )
                track_frag.append(
                    '<div class="bracket-tcell"><span class="bracket-idle">—</span></div>'
                )

    n_leaf = len(rounds[0]) * 2 if rounds else 1
    h_px = float(n_leaf * BRACKET_MATCH_SLOT_PX)
    w_px = float(num_cols * BRACKET_COL_W_PX + max(0, num_cols - 1) * BRACKET_GAP_PX)
    center_rows = _bracket_center_rows(n_leaf, float(BRACKET_MATCH_SLOT_PX))
    n_draw = min(num_cols, len(center_rows))
    svg = (
        _bracket_connectors_svg(
            center_rows,
            n_draw,
            w_px,
            h_px,
            stroke="rgba(238, 240, 252, 0.78)" if classic_skin else "#7c6ec4",
            stroke_opacity=1.0 if classic_skin else 0.95,
        )
        if use_elim_svg and n_leaf >= 2 and n_draw >= 2
        else ""
    )
    wrap_cls = "bracket-wrap" + (" bracket-wrap--classic" if classic_skin else "")
    grid_cls = "bracket-grid-main" + (" bracket-grid-main--classic" if classic_skin else "")
    bracket_fit_w = int(w_px)
    bracket_fit_h = int(h_px + BRACKET_HEADER_ROW_PX + 4)
    bracket_inner = (
        f'<div class="bracket-shell" style="--bf-slots: {n_leaf};" '
        f'data-bracket-w="{bracket_fit_w}" data-bracket-h="{bracket_fit_h}">'
        f'<div class="bracket-headers-row">{"".join(header_frag)}</div>'
        f'<div class="{grid_cls}">'
        '<div class="bracket-main-tracks">'
        f"{svg}"
        f'<div class="bracket-tracks-row">{"".join(track_frag)}</div>'
        "</div>"
        "</div></div>"
    )
    bracket_section = (
        f'<div class="section"><div class="section-title">Bracket</div>'
        f'<div class="{wrap_cls}">{_bracket_zoom_viewport_html(bracket_inner)}</div></div>'
    )
    css = (
        _LIST_CSS
        + _BRACKET_EXTRA_CSS
        + """
body.page-playoffs {
  width: 100% !important;
  max-width: min(1320px, 98vw) !important;
  margin: 0 auto !important;
}
body.page-playoffs .container {
  max-width: none !important;
  width: 100% !important;
  padding: 20px 16px !important;
}
"""
    )
    subtitle = (
        f"{html_module.escape(season)} &nbsp;·&nbsp; "
        f"Seeding through week {seeding_week} &nbsp;·&nbsp; "
        f"{len(sorted_teams)} teams"
    )
    return _render_list_page(
        css=css,
        title="🏆 PLAYOFFS",
        subtitle=subtitle,
        sections=seed_section + bracket_section,
        extra_script=_BRACKET_PAN_SCRIPT,
        body_class="page-playoffs",
    )

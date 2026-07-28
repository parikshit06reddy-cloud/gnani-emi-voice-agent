/* =========================================================================
   charts.js — inline SVG bar + donut charts. No canvas libs, no CDN.
   ========================================================================= */
(function (global) {
  "use strict";

  var STAGE_COLORS = {
    ptp: "#2fbf71",
    already_paid: "#22b8b0",
    callback: "#4f8cff",
    rtp: "#e0a530",
    dispute: "#9d7bea",
    non_connect: "#8891a3",
    other: "#6b7c93"
  };

  var LANG_COLORS = {
    "en-US": "#4f8cff",
    "es-ES": "#2fbf71",
    mixed: "#9d7bea",
    unknown: "#8891a3"
  };
  var LANG_LABELS = {
    "en-US": "English (US)",
    "es-ES": "Spanish",
    mixed: "Mixed",
    unknown: "Unknown"
  };

  function el(tag, attrs, children) {
    var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.keys(attrs || {}).forEach(function (k) {
      node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      node.appendChild(c);
    });
    return node;
  }

  /* Horizontal bar chart: calls by stage code, grouped/colored by stage_group */
  function renderStageBarChart(container, byStageCode) {
    container.innerHTML = "";
    var entries = Object.keys(byStageCode || {})
      .map(function (code) {
        return { code: code, count: byStageCode[code] };
      })
      .sort(function (a, b) { return b.count - a.count; });

    if (!entries.length) {
      container.innerHTML = '<div class="state-block"><p>No stage-code data for the current filters.</p></div>';
      return;
    }

    var max = Math.max.apply(null, entries.map(function (e) { return e.count; })) || 1;
    var Format = global.Format;

    entries.forEach(function (entry) {
      var group = Format.stageGroup(entry.code);
      var color = STAGE_COLORS[group] || STAGE_COLORS.other;
      var pct = Math.max(4, Math.round((entry.count / max) * 100));

      var row = document.createElement("div");
      row.className = "bar-row";

      var label = document.createElement("div");
      label.className = "bar-label";
      label.title = Format.stageLabel(entry.code);
      label.textContent = Format.stageLabel(entry.code);

      var track = document.createElement("div");
      track.className = "bar-track";
      var fill = document.createElement("div");
      fill.className = "bar-fill";
      fill.style.width = pct + "%";
      fill.style.background = color;
      track.appendChild(fill);

      var value = document.createElement("div");
      value.className = "bar-value";
      value.textContent = entry.count;

      row.appendChild(label);
      row.appendChild(track);
      row.appendChild(value);
      container.appendChild(row);
    });
  }

  /* Donut chart: calls by language */
  function renderLanguageDonut(svgContainer, legendContainer, byLanguage) {
    svgContainer.innerHTML = "";
    legendContainer.innerHTML = "";

    var entries = Object.keys(byLanguage || {})
      .map(function (lang) { return { lang: lang, count: byLanguage[lang] }; })
      .filter(function (e) { return e.count > 0; });

    var total = entries.reduce(function (sum, e) { return sum + e.count; }, 0);

    if (!total) {
      svgContainer.innerHTML = '<div class="state-block"><p>No language data for the current filters.</p></div>';
      return;
    }

    var size = 180;
    var radius = 70;
    var stroke = 26;
    var cx = size / 2;
    var cy = size / 2;
    var circumference = 2 * Math.PI * radius;

    var svg = el("svg", {
      viewBox: "0 0 " + size + " " + size,
      width: "100%",
      height: "auto",
      role: "img",
      "aria-label": "Donut chart of calls by language"
    });

    // background ring
    svg.appendChild(
      el("circle", {
        cx: cx,
        cy: cy,
        r: radius,
        fill: "none",
        stroke: "#1c222e",
        "stroke-width": stroke
      })
    );

    var offset = 0;
    entries.forEach(function (entry) {
      var color = LANG_COLORS[entry.lang] || "#6b7c93";
      var fraction = entry.count / total;
      var dash = fraction * circumference;
      var circle = el("circle", {
        cx: cx,
        cy: cy,
        r: radius,
        fill: "none",
        stroke: color,
        "stroke-width": stroke,
        "stroke-dasharray": dash + " " + (circumference - dash),
        "stroke-dashoffset": -offset,
        transform: "rotate(-90 " + cx + " " + cy + ")"
      });
      circle.setAttribute("stroke-linecap", "butt");
      svg.appendChild(circle);
      offset += dash;
    });

    var centerText = el("text", {
      x: cx,
      y: cy - 4,
      "text-anchor": "middle",
      fill: "#e7ebf3",
      "font-size": "22",
      "font-weight": "700",
      "font-family": "inherit"
    });
    centerText.textContent = total;
    svg.appendChild(centerText);

    var centerLabel = el("text", {
      x: cx,
      y: cy + 16,
      "text-anchor": "middle",
      fill: "#6b7488",
      "font-size": "10",
      "font-family": "inherit"
    });
    centerLabel.textContent = "CALLS";
    svg.appendChild(centerLabel);

    svgContainer.appendChild(svg);

    entries
      .sort(function (a, b) { return b.count - a.count; })
      .forEach(function (entry) {
        var item = document.createElement("div");
        item.className = "legend-item";
        var swatch = document.createElement("span");
        swatch.className = "legend-swatch";
        swatch.style.background = LANG_COLORS[entry.lang] || "#6b7c93";
        var pct = Math.round((entry.count / total) * 100);
        var text = document.createElement("span");
        text.textContent = (LANG_LABELS[entry.lang] || entry.lang) + " — " + entry.count + " (" + pct + "%)";
        item.appendChild(swatch);
        item.appendChild(text);
        legendContainer.appendChild(item);
      });
  }

  global.Charts = {
    STAGE_COLORS: STAGE_COLORS,
    LANG_COLORS: LANG_COLORS,
    renderStageBarChart: renderStageBarChart,
    renderLanguageDonut: renderLanguageDonut
  };
})(window);

/* =========================================================================
   dashboard.js — index.html page controller.
   ========================================================================= */
(function () {
  "use strict";

  var Format = window.Format;
  var Api = window.Api;
  var Charts = window.Charts;

  var STAGE_CODE_OPTIONS = [
    "PTP_TODAY", "PTP_TOMORROW", "PTP_FUTURE", "PTP_PARTIAL",
    "ALREADY_PAID", "CALLBACK_SCHEDULED",
    "RTP_FINANCIAL", "RTP_MEDICAL", "RTP_NO_REASON",
    "DISPUTE_PAID", "DISPUTE_CHARGES", "NO_LOAN",
    "WRONG_NUMBER", "THIRD_PARTY", "BUSY", "RNR", "VM", "DSCN", "UNCLEAR"
  ];

  var CARD_DEFS = [
    { key: "total_calls", label: "Total calls", accent: "total", sub: function (s) { return "All calls in view"; } },
    { key: "completed_calls", label: "Completed", accent: "completed", sub: function (s) { return rate(s.completed_calls, s.total_calls) + " of total"; } },
    { key: "connected_calls", label: "Connected", accent: "connected", sub: function (s) { return Format.formatPercent(s.connect_rate, 0) + " connect rate"; } },
    { key: "ptp_calls", label: "PTP", accent: "ptp", sub: function (s) { return Format.formatPercent(s.ptp_rate, 0) + " PTP rate"; } },
    { key: "already_paid_calls", label: "Already paid", accent: "already_paid", sub: function (s) { return rate(s.already_paid_calls, s.total_calls) + " of total"; } },
    { key: "rtp_calls", label: "Refusal to pay", accent: "rtp", sub: function (s) { return rate(s.rtp_calls, s.total_calls) + " of total"; } },
    { key: "dispute_calls", label: "Disputes", accent: "dispute", sub: function (s) { return rate(s.dispute_calls, s.total_calls) + " of total"; } },
    { key: "non_connect_calls", label: "Non-connect", accent: "non_connect", sub: function (s) { return rate(s.non_connect_calls, s.total_calls) + " of total"; } }
  ];

  function rate(part, total) {
    if (!total) return "0%";
    return Format.formatPercent(part / total, 0);
  }

  var state = {
    filters: {},
    page: 1,
    pageSize: 25,
    sortBy: "call_initiated_time",
    sortDir: "desc",
    lastResult: null,
    ws: null,
    pollTimer: null
  };

  /* ---------------------------------------------------------------------
     URL <-> filter state sync
     --------------------------------------------------------------------- */
  var FIELD_IDS = {
    call_date: "f-call-date",
    date_from: "f-date-from",
    date_to: "f-date-to",
    call_status: "f-call-status",
    customer_id: "f-customer-id",
    loan_account_number: "f-loan-account",
    language: "f-language",
    ptp_date: "f-ptp-date",
    q: "f-q"
  };

  function readFiltersFromUrl() {
    var params = new URLSearchParams(window.location.search);
    var filters = {};
    Object.keys(FIELD_IDS).forEach(function (key) {
      var v = params.get(key);
      if (v) filters[key] = v;
    });
    var stageCodes = params.getAll("stage_code");
    if (stageCodes.length) filters.stage_code = stageCodes;
    state.page = parseInt(params.get("page") || "1", 10) || 1;
    state.sortBy = params.get("sort_by") || "call_initiated_time";
    state.sortDir = params.get("sort_dir") || "desc";
    return filters;
  }

  function writeFiltersToUrl() {
    var params = new URLSearchParams();
    if (Api.isDemoMode()) params.set("demo", "1");
    Object.keys(FIELD_IDS).forEach(function (key) {
      if (state.filters[key]) params.set(key, state.filters[key]);
    });
    if (state.filters.stage_code && state.filters.stage_code.length) {
      state.filters.stage_code.forEach(function (code) {
        params.append("stage_code", code);
      });
    }
    if (state.page > 1) params.set("page", state.page);
    if (state.sortBy !== "call_initiated_time") params.set("sort_by", state.sortBy);
    if (state.sortDir !== "desc") params.set("sort_dir", state.sortDir);
    var newUrl = window.location.pathname + (params.toString() ? "?" + params.toString() : "");
    window.history.replaceState(null, "", newUrl);
  }

  function applyFiltersToForm() {
    Object.keys(FIELD_IDS).forEach(function (key) {
      var el = document.getElementById(FIELD_IDS[key]);
      if (el) el.value = state.filters[key] || "";
    });
    renderStageCodeCheckboxes();
  }

  function readFormIntoState() {
    Object.keys(FIELD_IDS).forEach(function (key) {
      var el = document.getElementById(FIELD_IDS[key]);
      if (!el) return;
      var v = el.value.trim();
      if (v) state.filters[key] = v;
      else delete state.filters[key];
    });
    var checked = Array.from(document.querySelectorAll('#stage-code-panel input[type="checkbox"]:checked')).map(function (cb) {
      return cb.value;
    });
    if (checked.length) state.filters.stage_code = checked;
    else delete state.filters.stage_code;
  }

  /* ---------------------------------------------------------------------
     Stage code multi-select dropdown
     --------------------------------------------------------------------- */
  function renderStageCodeCheckboxes() {
    var panel = document.getElementById("stage-code-panel");
    if (panel.childElementCount === 0) {
      STAGE_CODE_OPTIONS.forEach(function (code) {
        var label = document.createElement("label");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = code;
        var span = document.createElement("span");
        span.textContent = Format.stageLabel(code);
        label.appendChild(cb);
        label.appendChild(span);
        panel.appendChild(label);
      });
    }
    var selected = state.filters.stage_code || [];
    panel.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
      cb.checked = selected.indexOf(cb.value) !== -1;
    });
    updateStageDropdownTrigger();
  }

  function updateStageDropdownTrigger() {
    var trigger = document.getElementById("f-stage-code-trigger");
    var selected = state.filters.stage_code || [];
    if (!selected.length) {
      trigger.textContent = "All stages";
    } else if (selected.length === 1) {
      trigger.textContent = Format.stageLabel(selected[0]);
    } else {
      trigger.textContent = selected.length + " stages selected";
    }
  }

  function initStageDropdown() {
    var trigger = document.getElementById("f-stage-code-trigger");
    var panel = document.getElementById("stage-code-panel");
    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      panel.hidden = !panel.hidden;
      trigger.setAttribute("aria-expanded", String(!panel.hidden));
    });
    panel.addEventListener("change", function () {
      updateStageDropdownTrigger();
    });
    document.addEventListener("click", function (e) {
      if (!panel.hidden && !panel.contains(e.target) && e.target !== trigger) {
        panel.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        panel.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* ---------------------------------------------------------------------
     Cards
     --------------------------------------------------------------------- */
  function renderCardsSkeleton() {
    var grid = document.getElementById("cards-grid");
    grid.innerHTML = "";
    CARD_DEFS.forEach(function (def) {
      var card = document.createElement("div");
      card.className = "card accent-" + def.accent;
      card.innerHTML =
        '<div class="card-label">' + Format.escapeHtml(def.label) + '</div>' +
        '<div class="card-value skeleton">00</div>' +
        '<div class="card-sub skeleton">00%</div>';
      grid.appendChild(card);
    });
  }

  function renderCards(stats) {
    var grid = document.getElementById("cards-grid");
    grid.innerHTML = "";
    CARD_DEFS.forEach(function (def) {
      var card = document.createElement("div");
      card.className = "card accent-" + def.accent;
      var value = stats[def.key];
      card.innerHTML =
        '<div class="card-label">' + Format.escapeHtml(def.label) + '</div>' +
        '<div class="card-value">' + (value === undefined || value === null ? "0" : value) + '</div>' +
        '<div class="card-sub">' + Format.escapeHtml(def.sub(stats)) + '</div>';
      grid.appendChild(card);
    });
  }

  /* ---------------------------------------------------------------------
     Table
     --------------------------------------------------------------------- */
  function stageChipHtml(stageCode, stageGroup) {
    var group = stageGroup || Format.stageGroup(stageCode);
    return (
      '<span class="chip chip-' + group + '" title="' + Format.escapeHtml(Format.stageLabel(stageCode)) + '">' +
      Format.escapeHtml(Format.stageLabel(stageCode)) +
      "</span>"
    );
  }

  function statusPillHtml(status) {
    return (
      '<span class="status-pill"><span class="status-dot st-' + Format.escapeHtml(status) + '" aria-hidden="true"></span>' +
      Format.escapeHtml(Format.titleCase(status)) +
      "</span>"
    );
  }

  function rowHtml(row) {
    var detailUrl = "detail.html?call_id=" + encodeURIComponent(row.call_id) + (Api.isDemoMode() ? "&demo=1" : "");
    var reason = row.disposition_reason || "—";
    return (
      '<td class="mono">' + Format.escapeHtml(row.call_id) + "</td>" +
      "<td>" + Format.escapeHtml(row.customer_id) + "</td>" +
      "<td>" + Format.escapeHtml(row.customer_name) + "</td>" +
      '<td class="mono">' + Format.escapeHtml(row.masked_phone_number) + "</td>" +
      '<td class="mono">' + Format.escapeHtml(row.loan_account_number) + "</td>" +
      "<td>" + Format.escapeHtml(Format.formatDateTime(row.call_initiated_time)) + "</td>" +
      "<td>" + statusPillHtml(row.call_status) + "</td>" +
      "<td>" + Format.escapeHtml(Format.formatDuration(row.call_duration_seconds)) + "</td>" +
      "<td>" + stageChipHtml(row.stage_code, row.stage_group) + "</td>" +
      '<td title="' + Format.escapeHtml(reason) + '">' + Format.escapeHtml(Format.truncate(reason, 42)) + "</td>" +
      "<td>" + Format.escapeHtml(Format.formatDate(row.ptp_date)) + "</td>" +
      "<td>" + Format.escapeHtml(row.language || "—") + "</td>" +
      '<td class="link-cell"><a href="' + detailUrl + '">View →</a></td>'
    );
  }

  function renderTableSkeleton() {
    var tbody = document.getElementById("calls-tbody");
    tbody.innerHTML = "";
    for (var i = 0; i < 6; i++) {
      var tr = document.createElement("tr");
      var cells = "";
      for (var c = 0; c < 13; c++) {
        cells += '<td><span class="skel-line" style="width:' + (60 + (c % 3) * 20) + 'px;"></span></td>';
      }
      tr.innerHTML = cells;
      tbody.appendChild(tr);
    }
    document.getElementById("table-state-region").innerHTML = "";
  }

  function renderEmptyState() {
    document.getElementById("calls-tbody").innerHTML = "";
    document.getElementById("table-state-region").innerHTML =
      '<div class="state-block"><div class="state-icon" aria-hidden="true">☎</div>' +
      "<h3>No calls match these filters</h3>" +
      "<p>Try widening the date range or clearing some filters.</p></div>";
  }

  function renderErrorState(message) {
    document.getElementById("calls-tbody").innerHTML = "";
    document.getElementById("table-state-region").innerHTML =
      '<div class="state-block state-error"><div class="state-icon" aria-hidden="true">⚠</div>' +
      "<h3>Couldn't load calls</h3>" +
      "<p>" + Format.escapeHtml(message || "An unexpected error occurred.") + "</p></div>";
  }

  function renderTable(items, highlightId) {
    var tbody = document.getElementById("calls-tbody");
    tbody.innerHTML = "";
    document.getElementById("table-state-region").innerHTML = "";
    items.forEach(function (row) {
      var tr = document.createElement("tr");
      tr.dataset.callId = row.call_id;
      tr.innerHTML = rowHtml(row);
      if (row.call_id === highlightId) tr.classList.add("row-flash");
      tbody.appendChild(tr);
    });
  }

  function renderPagination(meta) {
    var pag = document.getElementById("pagination");
    if (meta.total === 0) {
      pag.hidden = true;
      return;
    }
    pag.hidden = false;
    var start = (meta.page - 1) * meta.page_size + 1;
    var end = Math.min(meta.total, meta.page * meta.page_size);
    document.getElementById("page-info").textContent =
      "Showing " + start + "–" + end + " of " + meta.total + " calls";
    document.getElementById("page-current").textContent = meta.page + " / " + meta.total_pages;
    document.getElementById("page-prev").disabled = meta.page <= 1;
    document.getElementById("page-next").disabled = meta.page >= meta.total_pages;
  }

  /* ---------------------------------------------------------------------
     Data loading
     --------------------------------------------------------------------- */
  function currentQueryFilters() {
    return Object.assign({}, state.filters, {
      page: state.page,
      page_size: state.pageSize,
      sort_by: state.sortBy,
      sort_dir: state.sortDir
    });
  }

  function loadAll() {
    renderTableSkeleton();
    renderCardsSkeleton();
    var chartFilters = Object.assign({}, state.filters);

    var callsPromise = Api.getCalls(currentQueryFilters())
      .then(function (res) {
        state.lastResult = res;
        if (!res.items.length) {
          renderEmptyState();
        } else {
          renderTable(res.items);
        }
        renderPagination(res);
        document.getElementById("table-result-count").textContent = "(" + res.total + " total)";
      })
      .catch(function (err) {
        renderErrorState(err.message);
        document.getElementById("pagination").hidden = true;
      });

    var statsPromise = Api.getStats(chartFilters)
      .then(function (stats) {
        renderCards(stats);
        Charts.renderStageBarChart(document.getElementById("stage-bar-chart"), stats.by_stage_code);
        Charts.renderLanguageDonut(
          document.getElementById("lang-donut-chart"),
          document.getElementById("lang-donut-legend"),
          stats.by_language
        );
      })
      .catch(function (err) {
        Api.toastError("Failed to load stats: " + err.message);
      });

    return Promise.all([callsPromise, statsPromise]);
  }

  /* ---------------------------------------------------------------------
     Sorting
     --------------------------------------------------------------------- */
  function initSorting() {
    var th = document.getElementById("th-call-initiated-time");
    th.addEventListener("click", toggleSort);
    th.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleSort();
      }
    });
    function toggleSort() {
      if (state.sortBy !== "call_initiated_time") {
        state.sortBy = "call_initiated_time";
        state.sortDir = "desc";
      } else {
        state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
      }
      th.setAttribute("aria-sort", state.sortDir === "asc" ? "ascending" : "descending");
      th.querySelector(".sort-arrow").textContent = state.sortDir === "asc" ? "▲" : "▼";
      state.page = 1;
      writeFiltersToUrl();
      loadAll();
    }
  }

  /* ---------------------------------------------------------------------
     Pagination controls
     --------------------------------------------------------------------- */
  function initPagination() {
    document.getElementById("page-prev").addEventListener("click", function () {
      if (state.page > 1) {
        state.page--;
        writeFiltersToUrl();
        loadAll();
      }
    });
    document.getElementById("page-next").addEventListener("click", function () {
      if (!state.lastResult || state.page < state.lastResult.total_pages) {
        state.page++;
        writeFiltersToUrl();
        loadAll();
      }
    });
  }

  /* ---------------------------------------------------------------------
     Filter form
     --------------------------------------------------------------------- */
  function initFilterForm() {
    var form = document.getElementById("filter-form");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      readFormIntoState();
      state.page = 1;
      writeFiltersToUrl();
      loadAll();
    });
    document.getElementById("filter-reset-btn").addEventListener("click", function () {
      form.reset();
      state.filters = {};
      state.page = 1;
      renderStageCodeCheckboxes();
      writeFiltersToUrl();
      loadAll();
    });
  }

  /* ---------------------------------------------------------------------
     CSV export
     --------------------------------------------------------------------- */
  function initCsvExport() {
    document.getElementById("csv-export-btn").addEventListener("click", function () {
      if (!state.lastResult || !state.lastResult.items.length) {
        Api.toastError("Nothing to export for the current view.");
        return;
      }
      var cols = [
        "call_id", "customer_id", "customer_name", "masked_phone_number",
        "loan_account_number", "call_initiated_time", "call_status",
        "call_duration_display", "stage_code", "disposition_reason", "ptp_date", "language"
      ];
      var lines = [cols.join(",")];
      state.lastResult.items.forEach(function (row) {
        lines.push(
          cols
            .map(function (c) {
              var v = row[c] === null || row[c] === undefined ? "" : String(row[c]);
              v = v.replace(/"/g, '""');
              if (/[",\n]/.test(v)) v = '"' + v + '"';
              return v;
            })
            .join(",")
        );
      });
      var blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "gnani-calls-export.csv";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      Api.toastSuccess("CSV exported.");
    });
  }

  /* ---------------------------------------------------------------------
     Live updates: WebSocket with polling fallback
     --------------------------------------------------------------------- */
  function setConnState(mode, text) {
    var el = document.getElementById("conn-indicator");
    el.dataset.state = mode;
    document.getElementById("conn-indicator-text").textContent = text;
  }

  function startPolling() {
    setConnState("polling", "Polling (10s)");
    if (state.pollTimer) clearInterval(state.pollTimer);
    state.pollTimer = setInterval(function () {
      loadAll();
    }, 10000);
  }

  function upsertRowLive(row) {
    // Only splice into view if it matches current filters loosely (skip strict check; just refresh cards + prepend/update visible row if present).
    var tbody = document.getElementById("calls-tbody");
    var existing = tbody.querySelector('tr[data-call-id="' + row.call_id.replace(/"/g, "") + '"]');
    if (existing) {
      existing.innerHTML = rowHtml(row);
      existing.classList.remove("row-flash");
      // restart animation
      void existing.offsetWidth;
      existing.classList.add("row-flash");
    } else if (state.page === 1) {
      var tr = document.createElement("tr");
      tr.dataset.callId = row.call_id;
      tr.innerHTML = rowHtml(row);
      tr.classList.add("row-flash");
      tbody.insertBefore(tr, tbody.firstChild);
      // Trim to page size to avoid unbounded growth
      while (tbody.children.length > state.pageSize) {
        tbody.removeChild(tbody.lastChild);
      }
    }
    // Refresh cards/stats quietly
    Api.getStats(Object.assign({}, state.filters))
      .then(renderCards)
      .catch(function () {});
  }

  function initLiveUpdates() {
    if (Api.isDemoMode()) {
      setConnState("polling", "Demo mode (static fixture)");
      return;
    }
    try {
      var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      var wsUrl = proto + "//" + window.location.host + "/ws/calls";
      var ws = new WebSocket(wsUrl);
      state.ws = ws;
      setConnState("polling", "Connecting…");

      ws.addEventListener("open", function () {
        setConnState("live", "Live (WebSocket)");
        if (state.pollTimer) {
          clearInterval(state.pollTimer);
          state.pollTimer = null;
        }
      });
      ws.addEventListener("message", function (evt) {
        try {
          var msg = JSON.parse(evt.data);
          if ((msg.type === "call.created" || msg.type === "call.updated") && msg.row) {
            upsertRowLive(msg.row);
          }
        } catch (e) {
          /* ignore malformed messages */
        }
      });
      ws.addEventListener("close", function () {
        setConnState("polling", "Polling (10s)");
        startPolling();
      });
      ws.addEventListener("error", function () {
        setConnState("error", "Connection error — polling");
        startPolling();
      });
    } catch (e) {
      startPolling();
    }
  }

  /* ---------------------------------------------------------------------
     Init
     --------------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", function () {
    state.filters = readFiltersFromUrl();
    applyFiltersToForm();
    initStageDropdown();
    initFilterForm();
    initSorting();
    initPagination();
    initCsvExport();
    Api.initSettingsPopover();
    loadAll();
    initLiveUpdates();
  });
})();

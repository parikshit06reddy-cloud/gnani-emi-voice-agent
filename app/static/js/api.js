/* =========================================================================
   api.js — fetch wrapper, API key management, toasts, demo/fixture fallback.
   Same-origin only. No external network requests.
   ========================================================================= */
(function (global) {
  "use strict";

  var STORAGE_KEY = "gnani_api_key";
  var DEFAULT_KEY = "dev-api-key";
  var FIXTURE_URL = "fixtures/sample-calls.json";

  function isDemoMode() {
    var params = new URLSearchParams(window.location.search);
    return params.get("demo") === "1";
  }

  function getApiKey() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_KEY;
    } catch (e) {
      return DEFAULT_KEY;
    }
  }

  function setApiKey(key) {
    try {
      window.localStorage.setItem(STORAGE_KEY, key || DEFAULT_KEY);
    } catch (e) {
      /* ignore storage errors (e.g. private mode) */
    }
  }

  /* ---------------------------------------------------------------------
     Toasts
     --------------------------------------------------------------------- */
  function ensureToastRegion() {
    var region = document.getElementById("toast-region");
    if (!region) {
      region = document.createElement("div");
      region.id = "toast-region";
      region.setAttribute("role", "status");
      region.setAttribute("aria-live", "polite");
      document.body.appendChild(region);
    }
    return region;
  }

  function toast(message, type, timeoutMs) {
    var region = ensureToastRegion();
    var el = document.createElement("div");
    el.className = "toast" + (type ? " toast-" + type : "");
    el.textContent = message;
    region.appendChild(el);
    var ttl = timeoutMs || 4500;
    setTimeout(function () {
      if (el.parentNode) el.parentNode.removeChild(el);
    }, ttl);
  }

  function toastError(message) {
    toast(message, "error");
  }

  function toastSuccess(message) {
    toast(message, "success");
  }

  /* ---------------------------------------------------------------------
     Fixture loading (demo mode / offline fallback)
     --------------------------------------------------------------------- */
  var fixtureCache = null;
  function loadFixture() {
    if (fixtureCache) return Promise.resolve(fixtureCache);
    return fetch(FIXTURE_URL, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("Fixture load failed: " + res.status);
        return res.json();
      })
      .then(function (data) {
        fixtureCache = data;
        return data;
      });
  }

  function matchesFilters(row, filters) {
    if (!filters) return true;
    if (filters.call_status && row.call_status !== filters.call_status) return false;
    if (filters.customer_id && row.customer_id.toLowerCase().indexOf(filters.customer_id.toLowerCase()) === -1) return false;
    if (filters.loan_account_number && row.loan_account_number.toLowerCase().indexOf(filters.loan_account_number.toLowerCase()) === -1) return false;
    if (filters.language && row.language !== filters.language) return false;
    if (filters.ptp_date && row.ptp_date !== filters.ptp_date) return false;
    if (filters.call_date && String(row.call_initiated_time).slice(0, 10) !== filters.call_date) return false;
    if (filters.date_from && String(row.call_initiated_time).slice(0, 10) < filters.date_from) return false;
    if (filters.date_to && String(row.call_initiated_time).slice(0, 10) > filters.date_to) return false;
    if (filters.stage_code && filters.stage_code.length) {
      var codes = Array.isArray(filters.stage_code) ? filters.stage_code : [filters.stage_code];
      if (codes.indexOf(row.stage_code) === -1) return false;
    }
    if (filters.q) {
      var needle = filters.q.toLowerCase();
      var hay = (row.disposition_reason || "").toLowerCase() + " " + (row.customer_name || "").toLowerCase();
      if (hay.indexOf(needle) === -1) return false;
    }
    return true;
  }

  function summaryRowFromDetail(detail) {
    return {
      call_id: detail.call_id,
      customer_id: detail.customer.customer_id,
      customer_name: detail.customer.customer_name,
      masked_phone_number: detail.customer.masked_phone_number,
      loan_account_number: detail.emi_details.loan_account_number,
      call_initiated_time: detail.call_initiated_at,
      call_status: detail.call_status,
      call_duration_seconds: detail.call_duration_seconds,
      call_duration_display: detail.call_duration_display,
      stage_code: detail.stage_code,
      stage_group: detail.stage_group,
      disposition_reason: detail.disposition_reason,
      ptp_date: detail.ptp_date,
      language: detail.language_captured
    };
  }

  function fixtureCalls(filters) {
    return loadFixture().then(function (data) {
      var rows = data.calls.map(summaryRowFromDetail).filter(function (row) {
        return matchesFilters(row, filters);
      });
      // sort by call_initiated_time desc by default
      var sortBy = (filters && filters.sort_by) || "call_initiated_time";
      var sortDir = (filters && filters.sort_dir) || "desc";
      rows.sort(function (a, b) {
        var av = a[sortBy === "created_at" ? "call_initiated_time" : sortBy] || "";
        var bv = b[sortBy === "created_at" ? "call_initiated_time" : sortBy] || "";
        if (av < bv) return sortDir === "asc" ? -1 : 1;
        if (av > bv) return sortDir === "asc" ? 1 : -1;
        return 0;
      });
      var page = (filters && filters.page) || 1;
      var pageSize = (filters && filters.page_size) || 25;
      var total = rows.length;
      var totalPages = Math.max(1, Math.ceil(total / pageSize));
      var start = (page - 1) * pageSize;
      var items = rows.slice(start, start + pageSize);
      return { items: items, page: page, page_size: pageSize, total: total, total_pages: totalPages };
    });
  }

  function fixtureStats(filters) {
    return loadFixture().then(function (data) {
      var rows = data.calls.map(summaryRowFromDetail).filter(function (row) {
        return matchesFilters(row, filters);
      });
      if (!filters || Object.keys(filters).every(function (k) { return !filters[k]; })) {
        return data.stats;
      }
      // Recompute lightweight stats for filtered subset.
      var byStage = {};
      var byLang = {};
      var total = rows.length;
      var completed = 0, connected = 0, ptp = 0, alreadyPaid = 0, rtp = 0, dispute = 0, nonConnect = 0, callback = 0;
      rows.forEach(function (r) {
        byStage[r.stage_code] = (byStage[r.stage_code] || 0) + 1;
        byLang[r.language] = (byLang[r.language] || 0) + 1;
        if (r.call_status === "completed") completed++;
        if (["connected", "completed"].indexOf(r.call_status) !== -1) connected++;
        if (r.stage_group === "ptp") ptp++;
        if (r.stage_group === "already_paid") alreadyPaid++;
        if (r.stage_group === "rtp") rtp++;
        if (r.stage_group === "dispute") dispute++;
        if (r.stage_group === "non_connect") nonConnect++;
        if (r.stage_group === "callback") callback++;
      });
      return {
        total_calls: total,
        completed_calls: completed,
        connected_calls: connected,
        ptp_calls: ptp,
        already_paid_calls: alreadyPaid,
        rtp_calls: rtp,
        dispute_calls: dispute,
        non_connect_calls: nonConnect,
        callback_calls: callback,
        connect_rate: total ? connected / total : 0,
        ptp_rate: total ? ptp / total : 0,
        by_stage_code: byStage,
        by_language: byLang,
        by_day: data.stats.by_day
      };
    });
  }

  function fixtureDetail(callId) {
    return loadFixture().then(function (data) {
      var found = data.calls.find(function (c) { return c.call_id === callId; });
      if (!found) {
        var err = new Error("CALL_NOT_FOUND");
        err.code = "CALL_NOT_FOUND";
        throw err;
      }
      return found;
    });
  }

  /* ---------------------------------------------------------------------
     Core request function
     --------------------------------------------------------------------- */
  var forcedFixtureMode = isDemoMode();

  function request(path, options) {
    options = options || {};
    if (forcedFixtureMode) {
      return fixtureRoute(path, options);
    }
    var url = path; // same-origin relative
    var headers = Object.assign({ "X-API-Key": getApiKey() }, options.headers || {});
    return fetch(url, {
      method: options.method || "GET",
      headers: headers,
      body: options.body
    })
      .then(function (res) {
        if (!res.ok) {
          return res
            .json()
            .catch(function () {
              return { error: { message: "Request failed with status " + res.status } };
            })
            .then(function (data) {
              var message = (data && data.error && data.error.message) || "Request failed (" + res.status + ")";
              var err = new Error(message);
              err.status = res.status;
              err.code = data && data.error && data.error.code;
              throw err;
            });
        }
        return res.json();
      })
      .catch(function (err) {
        // Network unreachable: fall back to fixture data transparently.
        if (err instanceof TypeError) {
          toastError("API unreachable — showing demo data.");
          return fixtureRoute(path, options);
        }
        throw err;
      });
  }

  function fixtureRoute(path, options) {
    var url = new URL(path, window.location.origin);
    var params = Object.fromEntries(url.searchParams.entries());
    // multi-value stage_code
    var stageCodes = url.searchParams.getAll("stage_code");
    if (stageCodes.length) params.stage_code = stageCodes;
    if (params.page) params.page = parseInt(params.page, 10);
    if (params.page_size) params.page_size = parseInt(params.page_size, 10);

    if (/\/api\/v1\/calls\/[^/?]+$/.test(url.pathname)) {
      var callId = decodeURIComponent(url.pathname.split("/").pop());
      return fixtureDetail(callId);
    }
    if (/\/api\/v1\/calls\/?$/.test(url.pathname)) {
      return fixtureCalls(params);
    }
    if (/\/api\/v1\/stats\/?$/.test(url.pathname)) {
      return fixtureStats(params);
    }
    return Promise.reject(new Error("No fixture route for " + path));
  }

  function getCalls(filters) {
    var qsStr = global.Format.qs(filters || {});
    return request("/api/v1/calls" + (qsStr ? "?" + qsStr : ""));
  }

  function getStats(filters) {
    var qsStr = global.Format.qs(filters || {});
    return request("/api/v1/stats" + (qsStr ? "?" + qsStr : ""));
  }

  function getCallDetail(callId) {
    return request("/api/v1/calls/" + encodeURIComponent(callId));
  }

  /* ---------------------------------------------------------------------
     Settings popover wiring (shared header control)
     --------------------------------------------------------------------- */
  function initSettingsPopover() {
    var trigger = document.getElementById("api-key-btn");
    var popover = document.getElementById("api-key-popover");
    var input = document.getElementById("api-key-input");
    var saveBtn = document.getElementById("api-key-save");
    var cancelBtn = document.getElementById("api-key-cancel");
    if (!trigger || !popover || !input) return;

    function open() {
      input.value = getApiKey();
      popover.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      input.focus();
    }
    function close() {
      popover.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }

    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      if (popover.hidden) open();
      else close();
    });
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        setApiKey(input.value.trim());
        toastSuccess("API key saved.");
        close();
      });
    }
    if (cancelBtn) {
      cancelBtn.addEventListener("click", close);
    }
    document.addEventListener("click", function (e) {
      if (!popover.hidden && !popover.contains(e.target) && e.target !== trigger) {
        close();
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  }

  global.Api = {
    STORAGE_KEY: STORAGE_KEY,
    DEFAULT_KEY: DEFAULT_KEY,
    isDemoMode: isDemoMode,
    getApiKey: getApiKey,
    setApiKey: setApiKey,
    toast: toast,
    toastError: toastError,
    toastSuccess: toastSuccess,
    getCalls: getCalls,
    getStats: getStats,
    getCallDetail: getCallDetail,
    initSettingsPopover: initSettingsPopover,
    request: request
  };
})(window);

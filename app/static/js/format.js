/* =========================================================================
   format.js — shared formatting helpers for the Gnani EMI dashboard.
   No dependencies. Attaches everything to window.Format.
   ========================================================================= */
(function (global) {
  "use strict";

  var STAGE_GROUPS = {
    ptp: ["PTP_TODAY", "PTP_TOMORROW", "PTP_FUTURE", "PTP_PARTIAL"],
    already_paid: ["ALREADY_PAID"],
    rtp: ["RTP_FINANCIAL", "RTP_MEDICAL", "RTP_NO_REASON"],
    dispute: ["DISPUTE_PAID", "DISPUTE_CHARGES", "NO_LOAN"],
    callback: ["CALLBACK_SCHEDULED"],
    non_connect: ["RNR", "VM", "BUSY", "WRONG_NUMBER", "DSCN"],
    other: ["THIRD_PARTY", "UNCLEAR"]
  };

  var STAGE_TO_GROUP = {};
  Object.keys(STAGE_GROUPS).forEach(function (group) {
    STAGE_GROUPS[group].forEach(function (code) {
      STAGE_TO_GROUP[code] = group;
    });
  });

  var STAGE_LABELS = {
    PTP_TODAY: "PTP Today",
    PTP_TOMORROW: "PTP Tomorrow",
    PTP_FUTURE: "PTP Future",
    PTP_PARTIAL: "PTP Partial",
    ALREADY_PAID: "Already Paid",
    CALLBACK_SCHEDULED: "Callback Scheduled",
    RTP_FINANCIAL: "RTP Financial",
    RTP_MEDICAL: "RTP Medical",
    RTP_NO_REASON: "RTP No Reason",
    DISPUTE_PAID: "Dispute (Paid)",
    DISPUTE_CHARGES: "Dispute (Charges)",
    NO_LOAN: "No Loan",
    WRONG_NUMBER: "Wrong Number",
    THIRD_PARTY: "Third Party",
    BUSY: "Busy",
    RNR: "Ring No Response",
    VM: "Voicemail",
    DSCN: "Disconnected",
    UNCLEAR: "Unclear"
  };

  function stageGroup(stageCode) {
    return STAGE_TO_GROUP[stageCode] || "other";
  }

  function stageLabel(stageCode) {
    if (!stageCode) return "—";
    return STAGE_LABELS[stageCode] || stageCode;
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatDateTime(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return escapeHtml(iso);
    var pad = function (n) { return String(n).padStart(2, "0"); };
    return (
      d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes())
    );
  }

  function formatDate(iso) {
    if (!iso) return "—";
    // Accept plain YYYY-MM-DD or full ISO
    var datePart = String(iso).slice(0, 10);
    return datePart;
  }

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return "—";
    var s = Math.max(0, Math.floor(Number(seconds) || 0));
    var m = Math.floor(s / 60);
    var r = s % 60;
    return String(m).padStart(2, "0") + ":" + String(r).padStart(2, "0");
  }

  function formatPercent(fraction, digits) {
    if (fraction === null || fraction === undefined || isNaN(fraction)) return "—";
    var d = digits === undefined ? 0 : digits;
    return (Number(fraction) * 100).toFixed(d) + "%";
  }

  function formatMoney(amount, currency) {
    if (amount === null || amount === undefined) return "—";
    var cur = currency || "USD";
    var symbol = cur === "USD" ? "$" : cur + " ";
    var n = Number(amount);
    return symbol + n.toFixed(2);
  }

  function truncate(str, maxLen) {
    if (!str) return "";
    str = String(str);
    if (str.length <= maxLen) return str;
    return str.slice(0, maxLen - 1) + "…";
  }

  function titleCase(str) {
    if (!str) return "";
    return String(str)
      .split("_")
      .map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1); })
      .join(" ");
  }

  function debounce(fn, wait) {
    var t = null;
    return function () {
      var args = arguments;
      var ctx = this;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(ctx, args);
      }, wait);
    };
  }

  function syntaxHighlightJson(obj) {
    var json = JSON.stringify(obj, null, 2);
    if (json === undefined) return "undefined";
    var escaped = escapeHtml(json);
    return escaped.replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false)\b|\bnull\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
      function (match) {
        var cls = "json-number";
        if (/^"/.test(match)) {
          cls = /:$/.test(match) ? "json-key" : "json-string";
        } else if (/true|false/.test(match)) {
          cls = "json-boolean";
        } else if (/null/.test(match)) {
          cls = "json-null";
        }
        return '<span class="' + cls + '">' + match + "</span>";
      }
    );
  }

  function qs(params) {
    var parts = [];
    Object.keys(params).forEach(function (key) {
      var val = params[key];
      if (val === null || val === undefined || val === "") return;
      if (Array.isArray(val)) {
        val.forEach(function (v) {
          if (v !== null && v !== undefined && v !== "") {
            parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(v));
          }
        });
      } else {
        parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(val));
      }
    });
    return parts.join("&");
  }

  global.Format = {
    STAGE_GROUPS: STAGE_GROUPS,
    STAGE_TO_GROUP: STAGE_TO_GROUP,
    STAGE_LABELS: STAGE_LABELS,
    stageGroup: stageGroup,
    stageLabel: stageLabel,
    escapeHtml: escapeHtml,
    formatDateTime: formatDateTime,
    formatDate: formatDate,
    formatDuration: formatDuration,
    formatPercent: formatPercent,
    formatMoney: formatMoney,
    truncate: truncate,
    titleCase: titleCase,
    debounce: debounce,
    syntaxHighlightJson: syntaxHighlightJson,
    qs: qs
  };
})(window);

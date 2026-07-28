/* =========================================================================
   detail.js — detail.html page controller.
   ========================================================================= */
(function () {
  "use strict";

  var Format = window.Format;
  var Api = window.Api;

  var currentDetail = null;

  function getCallId() {
    var params = new URLSearchParams(window.location.search);
    return params.get("call_id");
  }

  function setBackLink() {
    var link = document.getElementById("back-link");
    var params = new URLSearchParams(window.location.search);
    params.delete("call_id");
    var qs = params.toString();
    link.href = "index.html" + (qs ? "?" + qs : "");
  }

  function renderLoading() {
    document.getElementById("detail-content").hidden = true;
    document.getElementById("detail-state-region").innerHTML =
      '<div class="panel"><div class="state-block">' +
      '<div class="state-icon" aria-hidden="true">⏳</div>' +
      "<h3>Loading call details…</h3></div></div>";
  }

  function renderError(message) {
    document.getElementById("detail-content").hidden = true;
    document.getElementById("detail-state-region").innerHTML =
      '<div class="panel"><div class="state-block state-error">' +
      '<div class="state-icon" aria-hidden="true">⚠</div>' +
      "<h3>Couldn't load this call</h3><p>" + Format.escapeHtml(message || "Unknown error") + "</p></div></div>";
  }

  function renderEmptyNoId() {
    document.getElementById("detail-content").hidden = true;
    document.getElementById("detail-state-region").innerHTML =
      '<div class="panel"><div class="state-block">' +
      '<div class="state-icon" aria-hidden="true">☎</div>' +
      "<h3>No call selected</h3><p>Open this page from the calls list with a <code>?call_id=</code> parameter.</p></div></div>";
  }

  function stageChip(el, stageCode, stageGroup) {
    var group = stageGroup || Format.stageGroup(stageCode);
    el.className = "chip chip-" + group;
    el.textContent = Format.stageLabel(stageCode);
  }

  function sourceBadge(el, source) {
    var labelMap = { LLM: "LLM", derived: "Derived", fallback: "Fallback" };
    el.textContent = "Source: " + (labelMap[source] || source || "unknown");
  }

  function boolBadge(el, label, value) {
    el.textContent = label + ": " + (value ? "Yes" : "No");
    el.className = "badge " + (value ? "badge-yes" : "badge-no");
  }

  function renderDisposition(detail) {
    document.getElementById("call-id-heading").textContent = detail.call_id;
    stageChip(document.getElementById("disp-stage-chip"), detail.stage_code, detail.stage_group);
    sourceBadge(document.getElementById("disp-source-badge"), detail.stage_code_source);
    boolBadge(document.getElementById("disp-verified-badge"), "Customer verified", detail.customer_verified);

    var sentimentEl = document.getElementById("disp-sentiment-badge");
    sentimentEl.textContent = "Sentiment: " + Format.titleCase(detail.sentiment || "unknown");
    sentimentEl.className = "badge";

    var confidence = detail.confidence === null || detail.confidence === undefined ? 0 : detail.confidence;
    document.getElementById("disp-confidence-fill").style.width = Math.round(confidence * 100) + "%";
    document.getElementById("disp-confidence-value").textContent = Format.formatPercent(confidence, 0);

    document.getElementById("disp-reason").textContent = detail.disposition_reason || "—";
    document.getElementById("disp-summary").textContent = detail.disposition_summary || "—";

    var ptpText = "—";
    if (detail.ptp_date) {
      ptpText = Format.formatDate(detail.ptp_date);
      if (detail.ptp_amount) ptpText += " · " + Format.formatMoney(detail.ptp_amount, detail.emi_details && detail.emi_details.currency);
    }
    document.getElementById("disp-ptp").textContent = ptpText;
    document.getElementById("disp-callback").textContent = detail.callback_datetime ? Format.formatDateTime(detail.callback_datetime) : "—";

    var evidenceEl = document.getElementById("disp-evidence");
    evidenceEl.textContent = detail.evidence_quote ? "\u201C" + detail.evidence_quote + "\u201D" : "No evidence quote captured.";
  }

  function renderCustomer(detail) {
    var c = detail.customer || {};
    document.getElementById("cust-id").textContent = c.customer_id || "—";
    document.getElementById("cust-name").textContent = c.customer_name || "—";
    document.getElementById("cust-phone").textContent = c.masked_phone_number || "—";
    document.getElementById("cust-country").textContent = c.country_code || "—";
  }

  function renderEmi(detail) {
    var e = detail.emi_details || {};
    document.getElementById("emi-loan").textContent = e.loan_account_number || "—";
    document.getElementById("emi-amount").textContent = Format.formatMoney(e.emi_amount, e.currency);
    document.getElementById("emi-due").textContent = Format.formatDate(e.emi_due_date);
    document.getElementById("emi-currency").textContent = e.currency || "—";
  }

  function renderMeta(detail) {
    document.getElementById("meta-status").innerHTML =
      '<span class="status-pill"><span class="status-dot st-' + Format.escapeHtml(detail.call_status) + '"></span>' +
      Format.escapeHtml(Format.titleCase(detail.call_status)) + "</span>";
    document.getElementById("meta-duration").textContent = detail.call_duration_display || Format.formatDuration(detail.call_duration_seconds);
    document.getElementById("meta-initiated").textContent = Format.formatDateTime(detail.call_initiated_at);
    document.getElementById("meta-started").textContent = Format.formatDateTime(detail.call_started_at);
    document.getElementById("meta-completed").textContent = Format.formatDateTime(detail.call_completed_at);
    var ref = (detail.gnani_console_response && detail.gnani_console_response.gnani_call_reference) || "—";
    document.getElementById("meta-reference").textContent = ref;
  }

  function renderEngines(detail) {
    var engines = detail.engines || {};
    var defs = [
      { key: "asr", role: "ASR", label: "Prisma ASR", cls: "asr" },
      { key: "tts", role: "TTS", label: "Timbre 2.5 TTS", cls: "tts" },
      { key: "llm", role: "LLM", label: "Evon LLM", cls: "llm" }
    ];
    var wrap = document.getElementById("engine-badges");
    wrap.innerHTML = "";
    defs.forEach(function (def) {
      var raw = engines[def.key] || def.label;
      var badge = document.createElement("div");
      badge.className = "engine-badge";
      badge.innerHTML =
        '<span class="engine-icon ' + def.cls + '" aria-hidden="true">' + def.role.slice(0, 1) + "</span>" +
        '<span><span class="engine-role">' + def.role + '</span><br/><span class="engine-name" title="' +
        Format.escapeHtml(raw) + '">' + Format.escapeHtml(def.label) + "</span></span>";
      wrap.appendChild(badge);
    });
  }

  function renderAudio(detail) {
    var region = document.getElementById("audio-region");
    region.innerHTML = "";
    if (!detail.recording_url) {
      region.innerHTML =
        '<div class="audio-fallback"><span aria-hidden="true">🔇</span> Recording unavailable for this call.</div>';
      return;
    }
    var audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "none";
    audio.setAttribute("aria-label", "Call recording playback");
    var source = document.createElement("source");
    source.src = detail.recording_url;
    audio.appendChild(source);
    audio.addEventListener("error", function () {
      region.innerHTML =
        '<div class="audio-fallback"><span aria-hidden="true">🔇</span> Recording unavailable (unable to fetch audio).</div>';
    });
    region.appendChild(audio);
  }

  function renderTranscript(detail, filterText) {
    var list = document.getElementById("transcript-list");
    var turns = detail.conversation_transcript || [];
    list.innerHTML = "";
    var matchCount = 0;
    var needle = (filterText || "").trim().toLowerCase();

    if (!turns.length) {
      list.innerHTML = '<div class="state-block"><p>No transcript captured for this call.</p></div>';
      document.getElementById("transcript-match-count").textContent = "";
      return;
    }

    turns.forEach(function (turn) {
      var isCustomer = turn.speaker === "customer";
      var row = document.createElement("div");
      row.className = "turn-row speaker-" + (isCustomer ? "customer" : "bot");

      var meta = document.createElement("div");
      meta.className = "turn-meta";
      var speakerLabel = isCustomer ? "Customer" : "Bot";
      meta.innerHTML =
        "<span>Turn " + turn.turn + " · " + speakerLabel + "</span>" +
        '<span class="lang-tag">' + Format.escapeHtml(turn.language || "—") + "</span>" +
        "<span>" + Format.escapeHtml(Format.formatDateTime(turn.timestamp)) + "</span>";

      var bubble = document.createElement("div");
      bubble.className = "turn-bubble";
      var text = turn.text || "";
      var matched = false;
      if (needle && text.toLowerCase().indexOf(needle) !== -1) {
        matched = true;
        matchCount++;
        var escaped = Format.escapeHtml(text);
        var re = new RegExp("(" + needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
        bubble.innerHTML = escaped.replace(re, function (m) { return "<mark>" + m + "</mark>"; });
      } else {
        bubble.textContent = text;
      }

      row.appendChild(meta);
      row.appendChild(bubble);

      if (needle && !matched) {
        row.style.opacity = "0.35";
      }
      list.appendChild(row);
    });

    if (needle) {
      document.getElementById("transcript-match-count").textContent = matchCount + " match" + (matchCount === 1 ? "" : "es");
    } else {
      document.getElementById("transcript-match-count").textContent = "";
    }
  }

  function renderJson(detail) {
    var map = {
      "json-call-request-pre": detail.call_request,
      "json-console-response-pre": detail.gnani_console_response,
      "json-post-call-pre": detail.post_call_payload
    };
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      el.innerHTML = Format.syntaxHighlightJson(map[id] || {});
    });
  }

  function initCopyButtons() {
    document.querySelectorAll(".copy-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var targetId = btn.getAttribute("data-copy-target");
        var pre = document.getElementById(targetId);
        var text = pre.textContent;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard
            .writeText(text)
            .then(function () {
              Api.toastSuccess("Copied to clipboard.");
            })
            .catch(function () {
              Api.toastError("Copy failed.");
            });
        } else {
          Api.toastError("Clipboard API unavailable.");
        }
      });
    });
  }

  function renderAuditLog(detail) {
    var tbody = document.getElementById("audit-log-tbody");
    tbody.innerHTML = "";
    var log = detail.audit_log || [];
    if (!log.length) {
      tbody.innerHTML = '<tr><td colspan="4">No audit entries recorded.</td></tr>';
      return;
    }
    log.forEach(function (entry) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + Format.escapeHtml(Format.formatDateTime(entry.at)) + "</td>" +
        "<td>" + Format.escapeHtml(entry.actor) + "</td>" +
        "<td>" + Format.escapeHtml(entry.action) + "</td>" +
        '<td class="wrap-cell">' + Format.escapeHtml(entry.detail) + "</td>";
      tbody.appendChild(tr);
    });
  }

  function renderAll(detail) {
    currentDetail = detail;
    document.getElementById("detail-state-region").innerHTML = "";
    document.getElementById("detail-content").hidden = false;
    document.title = detail.call_id + " — Call Details — Gnani EMI Console";
    renderDisposition(detail);
    renderCustomer(detail);
    renderEmi(detail);
    renderMeta(detail);
    renderEngines(detail);
    renderAudio(detail);
    renderTranscript(detail);
    renderJson(detail);
    renderAuditLog(detail);
    initCopyButtons();
  }

  function initTranscriptSearch() {
    var input = document.getElementById("transcript-search");
    input.addEventListener(
      "input",
      Format.debounce(function () {
        if (currentDetail) renderTranscript(currentDetail, input.value);
      }, 150)
    );
  }

  document.addEventListener("DOMContentLoaded", function () {
    setBackLink();
    Api.initSettingsPopover();
    initTranscriptSearch();

    var callId = getCallId();
    if (!callId) {
      renderEmptyNoId();
      return;
    }
    renderLoading();
    Api.getCallDetail(callId)
      .then(renderAll)
      .catch(function (err) {
        renderError(err.message);
      });
  });
})();

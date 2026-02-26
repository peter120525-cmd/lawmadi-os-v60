/**
 * Lawmadi OS — Frontend Monitoring
 * JS 에러 추적 + Core Web Vitals + 페이지 성능 자동 수집
 *
 * 사용법: <script src="/lawmadi-monitor.js" defer></script>
 */
(function () {
  "use strict";

  var API_BASE = "";  // 같은 도메인이면 빈 문자열

  // ── 유틸 ──
  function post(endpoint, data) {
    try {
      var payload = JSON.stringify(data);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(API_BASE + endpoint, payload);
      } else {
        fetch(API_BASE + endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
          keepalive: true,
        }).catch(function () {});
      }
    } catch (e) {
      // 모니터링 실패는 무시
    }
  }

  // ══════════════════════════════════════════
  // 1. JS 에러 추적
  // ══════════════════════════════════════════

  window.onerror = function (message, source, lineno, colno, error) {
    post("/api/errors", {
      message: String(message).slice(0, 500),
      source: String(source || "").slice(0, 200),
      lineno: lineno || 0,
      colno: colno || 0,
      stack: error && error.stack ? error.stack.slice(0, 2000) : "",
      url: location.href.slice(0, 500),
      userAgent: navigator.userAgent.slice(0, 300),
    });
  };

  window.addEventListener("unhandledrejection", function (event) {
    var reason = event.reason || {};
    post("/api/errors", {
      message: "[UnhandledRejection] " + String(reason.message || reason).slice(0, 500),
      source: "promise",
      lineno: 0,
      colno: 0,
      stack: reason.stack ? reason.stack.slice(0, 2000) : "",
      url: location.href.slice(0, 500),
      userAgent: navigator.userAgent.slice(0, 300),
    });
  });

  // ══════════════════════════════════════════
  // 2. 페이지 로드 성능
  // ══════════════════════════════════════════

  function reportPageLoad() {
    var timing = performance.timing || {};
    var nav = timing.navigationStart || 0;
    if (!nav) return;

    post("/api/perf", {
      ttfb: timing.responseStart ? timing.responseStart - nav : null,
      domLoad: timing.domContentLoadedEventEnd ? timing.domContentLoadedEventEnd - nav : null,
      fullLoad: timing.loadEventEnd ? timing.loadEventEnd - nav : null,
      url: location.href.slice(0, 500),
      userAgent: navigator.userAgent.slice(0, 300),
    });
  }

  // loadEventEnd가 설정된 후 보고
  if (document.readyState === "complete") {
    setTimeout(reportPageLoad, 100);
  } else {
    window.addEventListener("load", function () {
      setTimeout(reportPageLoad, 100);
    });
  }

  // ══════════════════════════════════════════
  // 3. Core Web Vitals (LCP, FID, CLS)
  // ══════════════════════════════════════════

  var vitals = { lcp: null, fid: null, cls: 0 };
  var vitalsSent = false;

  function sendVitals() {
    if (vitalsSent) return;
    if (vitals.lcp === null) return;  // LCP 측정 전 전송 안 함
    vitalsSent = true;
    post("/api/perf", {
      lcp: vitals.lcp ? Math.round(vitals.lcp) : null,
      fid: vitals.fid ? Math.round(vitals.fid) : null,
      cls: vitals.cls ? Math.round(vitals.cls * 1000) / 1000 : null,
      url: location.href.slice(0, 500),
      userAgent: navigator.userAgent.slice(0, 300),
    });
  }

  // LCP (Largest Contentful Paint)
  if (typeof PerformanceObserver !== "undefined") {
    try {
      new PerformanceObserver(function (list) {
        var entries = list.getEntries();
        if (entries.length > 0) {
          vitals.lcp = entries[entries.length - 1].startTime;
        }
      }).observe({ type: "largest-contentful-paint", buffered: true });
    } catch (e) {}

    // FID (First Input Delay)
    try {
      new PerformanceObserver(function (list) {
        var entries = list.getEntries();
        if (entries.length > 0) {
          vitals.fid = entries[0].processingStart - entries[0].startTime;
        }
      }).observe({ type: "first-input", buffered: true });
    } catch (e) {}

    // CLS (Cumulative Layout Shift)
    try {
      new PerformanceObserver(function (list) {
        var entries = list.getEntries();
        for (var i = 0; i < entries.length; i++) {
          if (!entries[i].hadRecentInput) {
            vitals.cls += entries[i].value;
          }
        }
      }).observe({ type: "layout-shift", buffered: true });
    } catch (e) {}
  }

  // 페이지 이탈 시 Web Vitals 전송
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      sendVitals();
    }
  });

  // 5초 후 fallback 전송
  setTimeout(sendVitals, 5000);
})();

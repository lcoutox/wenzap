/* Wenzap Web Widget Loader — v1.0 */
(function () {
  "use strict";

  // Prevent double initialization when script is accidentally loaded twice.
  if (window.__wenzapWidgetLoaded) return;
  window.__wenzapWidgetLoaded = true;

  // Locate the <script> tag that loaded this file.
  var script =
    document.currentScript ||
    (function () {
      var tags = document.getElementsByTagName("script");
      return tags[tags.length - 1];
    })();

  var widgetKey = script && script.getAttribute("data-widget-key");
  if (!widgetKey) {
    console.warn("[Wenzap Widget] data-widget-key attribute is required.");
    return;
  }

  // Derive app origin from the script src so this file works in any environment.
  var scriptSrc = (script && script.getAttribute("src")) || "";
  var appOrigin = scriptSrc.replace(/\/widget\.js(\?.*)?$/, "");
  if (!appOrigin) appOrigin = window.location.origin;

  var iframe = document.createElement("iframe");
  iframe.src = appOrigin + "/embed/widget/" + widgetKey;
  iframe.setAttribute("allowtransparency", "true");
  iframe.setAttribute("frameborder", "0");
  iframe.setAttribute("scrolling", "no");
  iframe.setAttribute("title", "Wenzap Chat Widget");

  // Helper: apply iframe geometry.
  // Desktop: 420×680px fixed in chosen corner.
  // Mobile (≤480px): nearly full-screen with small margin.
  function applyStyles(side) {
    var isMobile = window.innerWidth <= 480;
    var w = isMobile ? "calc(100vw - 16px)" : "420px";
    var h = isMobile ? "calc(100vh - 16px)" : "680px";
    var bottom = isMobile ? "8px" : "0";
    var horizontal = (side === "left") ? "left:8px;right:auto;" : "right:8px;left:auto;";

    iframe.style.cssText =
      "position:fixed;" +
      "bottom:" + bottom + ";" +
      horizontal +
      "width:" + w + ";" +
      "height:" + h + ";" +
      "border:none;" +
      "z-index:2147483647;" +
      "background:transparent;" +
      "overflow:hidden;" +
      "pointer-events:auto;";
  }

  // Default side: right. Updated via postMessage from the embed once config loads.
  var currentSide = "right";
  applyStyles(currentSide);

  // Capture page context from the parent page (this script runs in the parent, not the iframe).
  function getPageContext() {
    var params = new URLSearchParams(window.location.search);
    return {
      page_url: window.location.href || null,
      page_title: document.title || null,
      referrer: document.referrer || null,
      utm_source: params.get("utm_source") || null,
      utm_medium: params.get("utm_medium") || null,
      utm_campaign: params.get("utm_campaign") || null,
      utm_term: params.get("utm_term") || null,
      utm_content: params.get("utm_content") || null,
    };
  }

  // Send page context to the embed iframe after it loads.
  function sendPageContext() {
    try {
      iframe.contentWindow.postMessage(
        { type: "wenzap:page-context", pageContext: getPageContext() },
        appOrigin
      );
    } catch (e) {
      // Ignore cross-origin or sandboxed errors.
    }
  }

  iframe.addEventListener("load", function () {
    sendPageContext();
    // Retry once after a short delay in case the embed was not yet listening.
    setTimeout(sendPageContext, 400);
  });

  // Listen for position updates sent by the WidgetEmbed component.
  window.addEventListener("message", function (event) {
    // Accept only messages from the widget origin.
    if (event.origin !== appOrigin) return;
    if (!event.data || event.data.type !== "wenzap:widget-config") return;
    var pos = event.data.position;
    if (pos === "bottom-left" || pos === "bottom-right") {
      var side = pos === "bottom-left" ? "left" : "right";
      if (side !== currentSide) {
        currentSide = side;
        applyStyles(currentSide);
      }
    }
  });

  // Re-apply on resize for mobile/desktop switch.
  window.addEventListener("resize", function () {
    applyStyles(currentSide);
  });

  function inject() {
    if (document.getElementById("__wenzap_widget_iframe__")) return;
    iframe.id = "__wenzap_widget_iframe__";
    document.body.appendChild(iframe);
  }

  if (document.body) {
    inject();
  } else {
    document.addEventListener("DOMContentLoaded", inject);
  }
})();

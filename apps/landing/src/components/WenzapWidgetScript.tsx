"use client";

import Script from "next/script";

const WIDGET_KEY = "wgt_Q6WX_q7vh_Xbb71HyJmN-bwH";
const WIDGET_SRC = "https://app.wenzap.com.br/widget.js";

export function WenzapWidgetScript() {
  return (
    <Script
      src={WIDGET_SRC}
      data-widget-key={WIDGET_KEY}
      strategy="lazyOnload"
      id="wenzap-widget"
    />
  );
}

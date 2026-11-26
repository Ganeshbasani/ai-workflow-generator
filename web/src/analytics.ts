const CONSENT_KEY = "architect.posthog-consent.v1";
const projectKey = import.meta.env.VITE_POSTHOG_KEY?.trim();
const apiHost = import.meta.env.VITE_POSTHOG_HOST?.trim() || "https://us.i.posthog.com";
let posthogClient: Promise<typeof import("posthog-js").default> | null = null;

function isLocalOrigin(): boolean {
  return typeof window === "undefined" || ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

function readConsent(): boolean {
  try { return window.localStorage.getItem(CONSENT_KEY) === "granted"; }
  catch { return false; }
}

function initialize(): boolean {
  if (!projectKey || isLocalOrigin()) return false;
  if (!posthogClient) {
    posthogClient = import("posthog-js").then(({ default: client }) => {
      client.init(projectKey!, {
      api_host: apiHost,
      autocapture: false,
      capture_pageview: false,
      capture_pageleave: false,
      disable_session_recording: true,
      persistence: "memory",
      person_profiles: "identified_only",
      });
      if (readConsent()) client.opt_in_capturing();
      return client;
    });
  }
  return true;
}

if (readConsent()) initialize();

export function productAnalyticsConfigured(): boolean {
  return Boolean(projectKey) && !isLocalOrigin();
}

export function productAnalyticsEnabled(): boolean {
  return productAnalyticsConfigured() && readConsent();
}

export function setProductAnalyticsEnabled(enabled: boolean): boolean {
  if (!productAnalyticsConfigured()) return false;
  try {
    if (enabled) window.localStorage.setItem(CONSENT_KEY, "granted");
    else window.localStorage.removeItem(CONSENT_KEY);
  } catch { return false; }
  if (!initialize()) return false;
  void posthogClient?.then((client) => enabled ? client.opt_in_capturing() : client.opt_out_capturing());
  return true;
}

type ProductEvent =
  | "workflow_generation_started"
  | "workflow_generation_completed"
  | "workflow_generation_failed"
  | "workflow_edited"
  | "workflow_exported"
  | "workflow_template_used"
  | "workflow_run_started"
  | "workflow_run_completed";

export function trackProductEvent(event: ProductEvent, properties?: Record<string, string | number>): void {
  if (!productAnalyticsEnabled() || !initialize()) return;
  void posthogClient?.then((client) => {
    if (productAnalyticsEnabled()) client.capture(event, properties);
  });
}

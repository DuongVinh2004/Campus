"use client";

import React, { useEffect, useSyncExternalStore } from "react";
import { FEATURE_DEFAULTS, type FeatureKey } from "./feature-registry.generated";
import { featuresApi } from "./features-api";

/**
 * Runtime feature flags. The server (GET /v1/features) is the source of truth; until it answers, and whenever it cannot be reached,
 * the last value we saw is kept, and the registry default (generated at build time) is used when we saw none. That keeps the menu
 * from flickering and never hides everything because of one failed request.
 */
type Values = Record<string, boolean | string>;
const REFRESH_MS = 60_000;

let values: Values = { ...FEATURE_DEFAULTS };
let loaded = false;
let started = false;
// Other component tests script `fetch` call by call; an extra request from the menu would shift their mocks, so tests opt in.
let autoFetch = process.env.NODE_ENV !== "test";
export function enableFeatureFetchForTests() { autoFetch = true; }
const listeners = new Set<() => void>();

function emit() { listeners.forEach(listener => listener()); }

export async function refreshFeatures(): Promise<void> {
  try {
    const snapshot = await featuresApi.snapshot();
    values = { ...FEATURE_DEFAULTS, ...snapshot.features };
    loaded = true;
    emit();
  } catch {
    /* keep the last known values */
  }
}

function start() {
  if (typeof window === "undefined" || !autoFetch) return;
  if (!loaded) void refreshFeatures();
  if (started) return;
  started = true;
  window.setInterval(() => void refreshFeatures(), REFRESH_MS);
  window.addEventListener("focus", () => void refreshFeatures());
}

/** Test helper: back to registry defaults, nothing fetched yet. */
export function resetFeaturesForTests() {
  values = { ...FEATURE_DEFAULTS };
  loaded = false;
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function useValues(): Values {
  useEffect(() => { start(); }, []);
  return useSyncExternalStore(subscribe, () => values, () => values);
}

/** True when the feature is on for the current user; the registry default while nothing has been fetched yet. */
export function useFeature(key: FeatureKey): boolean {
  const current = useValues()[key];
  return typeof current === "string" ? current !== "off" : Boolean(current);
}

export function useFeatureValue(key: FeatureKey): boolean | string {
  return useValues()[key];
}

export function useFeaturesLoaded(): boolean {
  useValues();
  return loaded;
}

/** Whether a navigation key is shown: a nav key with no feature is always shown. */
export function useNavEnabled(navFeature: Record<string, FeatureKey>): (navKey: string) => boolean {
  const current = useValues();
  return navKey => {
    const feature = navFeature[navKey];
    if (!feature) return true;
    const value = current[feature];
    return typeof value === "string" ? value !== "off" : value !== false;
  };
}

export function FeatureGate({ feature, fallback = null, children }: { feature: FeatureKey; fallback?: React.ReactNode; children: React.ReactNode }) {
  return useFeature(feature) ? <>{children}</> : <>{fallback}</>;
}

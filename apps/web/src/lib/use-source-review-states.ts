"use client";

import { useEffect, useMemo, useState } from "react";
import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export type SourceReviewState = "OK" | "DUE_SOON" | "OVERDUE" | "EXPIRED";
const MAX_IDS = 20;

/**
 * Review state of each cited source (sources of the current release only). It is a label for the reader, nothing more:
 * a failed lookup yields no labels and never blocks the citation.
 */
export function useSourceReviewStates(sourceIds: string[], enabled = true): Record<string, SourceReviewState> {
  const key = useMemo(() => Array.from(new Set(sourceIds.filter(Boolean))).slice(0, MAX_IDS).join(","), [sourceIds]);
  const [loaded, setLoaded] = useState<{ key: string; states: Record<string, SourceReviewState> }>({ key: "", states: {} });
  useEffect(() => {
    if (!enabled || !key) return;
    let cancelled = false;
    new ApiClient({ baseUrl: CAMPUS_API_BASE_URL })
      .get<{ states: Record<string, SourceReviewState> }>(`/v1/knowledge/source-review-status?source_ids=${encodeURIComponent(key)}`)
      .then((reply) => { if (!cancelled) setLoaded({ key, states: reply.states || {} }); })
      .catch(() => { if (!cancelled) setLoaded({ key, states: {} }); });
    return () => { cancelled = true; };
  }, [enabled, key]);
  return enabled && loaded.key === key ? loaded.states : {};
}

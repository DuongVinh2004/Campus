"use client";

import { useEffect, useState } from "react";
import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

/**
 * True only once the policy-graph API has answered. The operational runtime does not serve it (the graph is built on
 * the older knowledge store), so the link to its page stays hidden there instead of leading to a 404.
 */
export function usePolicyGraphAvailable(): boolean {
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    let cancelled = false;
    new ApiClient({ baseUrl: CAMPUS_API_BASE_URL }).get("/v1/policy-graph/versions")
      .then(() => { if (!cancelled) setAvailable(true); })
      .catch(() => { if (!cancelled) setAvailable(false); });
    return () => { cancelled = true; };
  }, []);
  return available;
}

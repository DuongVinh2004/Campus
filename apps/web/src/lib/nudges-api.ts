import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export interface NudgeItem { key: string; kind: string; title: string; reason: string; due_at: string | null; urgency: "HIGH" | "MEDIUM" | "LOW" | string; link: string }

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

export const nudgesApi = {
  today: () => client().get<{ items: NudgeItem[] }>("/v1/nudges/today"),
  done: (key: string) => client().post<{ key: string; state: string }>(`/v1/nudges/${encodeURIComponent(key)}/done`),
  snooze: (key: string, hours: number) => client().post<{ key: string; state: string }>(`/v1/nudges/${encodeURIComponent(key)}/snooze`, { hours }),
  preferences: () => client().get<{ preferences: Record<string, boolean> }>("/v1/nudges/preferences"),
  setPreferences: (preferences: Record<string, boolean>) => client().put<{ preferences: Record<string, boolean> }>("/v1/nudges/preferences", { preferences }),
};

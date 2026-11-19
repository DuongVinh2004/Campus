"use client";

import React, { useEffect, useState } from "react";
import { CAMPUS_API_BASE_URL } from "../../lib/api/base-url";
import { ApiClient, ApiClientError } from "../../lib/api/client";

type Kind = "exam" | "sources";
type Preferences = Record<Kind, boolean>;

const LABELS: Record<Kind, { title: string; help: string }> = {
  exam: { title: "Nhắc lịch thi", help: "Thông báo trước giờ thi 24 giờ và 2 giờ." },
  sources: { title: "Nhắc rà soát nguồn tri thức", help: "Thông báo trước khi nguồn hết hiệu lực hoặc đến hạn rà soát, và tóm tắt hằng tuần." },
};

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

/** On/off switches for the reminders a person receives. `kinds` lists which ones to show (students: exam; knowledge managers: sources). */
export function ReminderPreferences({ kinds = ["exam"] }: { kinds?: Kind[] }) {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<Kind | null>(null);

  useEffect(() => {
    let cancelled = false;
    client()
      .get<Preferences>("/v1/notifications/preferences")
      .then((value) => !cancelled && setPrefs(value))
      .catch(() => !cancelled && setError("Không tải được cài đặt nhắc việc."));
    return () => {
      cancelled = true;
    };
  }, []);

  async function toggle(kind: Kind) {
    if (!prefs || saving) return;
    const wanted = !prefs[kind];
    setSaving(kind);
    setError(null);
    setPrefs({ ...prefs, [kind]: wanted }); // show the change at once; undone below if the server refuses it
    try {
      setPrefs(await client().put<Preferences>("/v1/notifications/preferences", { [kind]: wanted }));
    } catch (caught) {
      setPrefs(prefs);
      setError(caught instanceof ApiClientError ? caught.message : "Không lưu được cài đặt. Hãy thử lại.");
    } finally {
      setSaving(null);
    }
  }

  if (!prefs) return error ? <p role="alert" className="text-sm">{error}</p> : <p role="status" className="text-sm">Đang tải cài đặt nhắc việc…</p>;
  return (
    <section aria-labelledby="reminder-prefs-heading" data-testid="reminder-preferences" className="campus-panel space-y-3 p-4">
      <h2 id="reminder-prefs-heading" className="text-base font-semibold">Nhắc việc</h2>
      {error ? <p role="alert" className="text-sm text-[var(--color-danger,#c0392b)]">{error}</p> : null}
      <ul className="space-y-3">
        {kinds.map((kind) => (
          <li key={kind} className="flex items-start justify-between gap-3">
            <div>
              <p id={`pref-${kind}-label`} className="text-sm font-medium">{LABELS[kind].title}</p>
              <p id={`pref-${kind}-help`} className="text-xs text-[var(--text-secondary)]">{LABELS[kind].help}</p>
            </div>
            <button type="button" role="switch" aria-checked={prefs[kind]} aria-labelledby={`pref-${kind}-label`} aria-describedby={`pref-${kind}-help`}
                    disabled={saving === kind} onClick={() => void toggle(kind)}
                    className="min-h-[44px] min-w-[72px] shrink-0 rounded-full border px-3 text-sm font-medium">
              {prefs[kind] ? "Bật" : "Tắt"}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

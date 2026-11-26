"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { nudgesApi, type NudgeItem } from "../../lib/nudges-api";

const URGENCY_WORD: Record<string, string> = { HIGH: "Gấp", MEDIUM: "Sắp đến hạn", LOW: "Nhắc nhẹ" };
const KIND_LABEL: Record<string, string> = {
  EXAM: "Lịch thi", TICKET_NEED_INFO: "Hồ sơ cần bổ sung", ANNOUNCEMENT_ACK: "Thông báo cần xác nhận", ANNOUNCEMENT_URGENT_UNREAD: "Thông báo khẩn chưa đọc",
};

/** "Việc cần làm hôm nay": computed live from the person's own signals; done and snooze act on one item at a time. */
export function TodayTasks() {
  const [items, setItems] = useState<NudgeItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    nudgesApi.today().then(r => { setItems(r.items); setError(null); }).catch(e => setError(e instanceof Error ? e.message : "Không tải được việc cần làm."));
  }, []);
  useEffect(load, [load]);

  const act = async (action: () => Promise<unknown>) => {
    try { await action(); load(); } catch (e) { setError(e instanceof Error ? e.message : "Không thực hiện được."); }
  };

  if (error) return <section aria-label="Việc cần làm"><p role="alert">{error}</p></section>;
  if (!items) return <section aria-label="Việc cần làm"><p role="status">Đang tải việc cần làm…</p></section>;
  return (
    <section aria-labelledby="today-tasks-title" className="campus-card space-y-2">
      <h2 id="today-tasks-title">Việc cần làm</h2>
      {items.length === 0 ? <p>Hôm nay bạn không có việc nào cần xử lý.</p> : (
        <ul>
          {items.map(item => (
            <li key={item.key}>
              <strong>{URGENCY_WORD[item.urgency] ?? item.urgency}</strong> · {KIND_LABEL[item.kind] ?? item.kind}: {item.link ? <Link href={item.link}>{item.title}</Link> : item.title}
              <small> — {item.reason}</small>
              <button onClick={() => void act(() => nudgesApi.done(item.key))} aria-label={`Đã xong: ${item.title}`}>Xong</button>
              <button onClick={() => void act(() => nudgesApi.snooze(item.key, 24))} aria-label={`Hoãn 1 ngày: ${item.title}`}>Hoãn 1 ngày</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ApiClient } from "@/lib/api/client";
import { useUnifiedAssistant } from "@/lib/unified-assistant-runtime";

export function StudentActionCoverage() {
  const runtime = useUnifiedAssistant(), path = usePathname();
  const [items, setItems] = useState<Array<{ action: string; route: string; support: string; next_step: string }>>([]);
  useEffect(() => {
    let current = true;
    if (runtime.capabilities?.student_preparation !== true) return;
    void (async () => { try { await runtime.guard(); const value = await new ApiClient({ baseUrl: CAMPUS_API_BASE_URL }).get<{ items: typeof items }>("/v1/assistant/student-actions"); await runtime.guard(); if (current) setItems(value.items); } catch { if (current) setItems([]); } })();
    return () => { current = false; };
  }, [runtime.capabilities?.student_preparation, runtime.actor?.user_id]);
  if (runtime.capabilities?.audience !== "student") return null;
  const selected = items.filter(item => item.route === path);
  return <details className="border-b p-2 text-xs"><summary className="min-h-11 cursor-pointer">Chức năng được hỗ trợ tại trang này</summary>
    {selected.length ? selected.map(item => <p className="my-2" key={item.action}>{item.next_step} · {item.support === "unavailable" ? "Chưa hỗ trợ" : item.support === "explicit_confirmation" ? "Cần xác nhận" : "Có consumer"}</p>) : <p>Chưa xác nhận capability của trang này từ máy chủ.</p>}
    <nav className="flex flex-wrap gap-3"><Link className="min-h-11" href="/chat">Hỏi đáp</Link><Link className="min-h-11" href="/tickets">Giấy xác nhận & hồ sơ</Link><Link className="min-h-11" href="/services">Phúc khảo & hỗ trợ</Link><Link className="min-h-11" href="/privacy">Quyền riêng tư</Link></nav>
  </details>;
}

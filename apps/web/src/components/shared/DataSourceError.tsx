"use client";

import React from "react";
import { useStore } from "@/lib/store";
import { CompactNotice } from "./CompactNotice";
import { usePathname } from "next/navigation";

export function DataSourceError() {
  const { dataError, reloadData, isDataLoading } = useStore();
  const pathname = usePathname();

  if (!dataError || pathname === "/my-requests") return null;

  const title = "Chưa tải được thông tin";

  return (
    <div className="pointer-events-none fixed right-3 top-20 z-40 max-w-[min(320px,calc(100vw-24px))]">
      <CompactNotice key={`${pathname}:${dataError.message}`} title={title} alert>
        <p>{dataError.message} Thông tin đã lưu vẫn được giữ; hãy thử tải lại.</p>
        <button type="button" disabled={isDataLoading} onClick={() => void reloadData().catch(() => { /* Error remains in the store for retry. */ })} className="mt-2 min-h-11 rounded-lg px-3 font-semibold underline disabled:opacity-50">{isDataLoading ? "Đang tải…" : "Thử tải lại"}</button>
      </CompactNotice>
    </div>
  );
}

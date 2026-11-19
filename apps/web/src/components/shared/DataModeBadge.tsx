"use client";

import React from "react";
import { useStore } from "@/lib/store";
import { Database, Wifi } from "lucide-react";

export function DataModeBadge() {
  const { dataConfig, dataStatus, isDataLoading, dataError } = useStore();

  if (!dataConfig || dataStatus === "configuration_error" || dataError?.reason === "configuration") {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 rounded-full text-[10px] font-semibold border border-red-200 dark:border-red-800">
        <Wifi className="w-3 h-3" />
        <span>Lỗi cấu hình</span>
      </div>
    );
  }

  if (dataConfig.mode === "mock") {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 rounded-full text-[10px] font-semibold border border-amber-200 dark:border-amber-800">
        <Database className="w-3 h-3" />
        <span>Mock UAT</span>
      </div>
    );
  }

  if (isDataLoading || dataStatus === "loading") {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded-full text-[10px] font-semibold border border-blue-200 dark:border-blue-800">
        <Wifi className="w-3 h-3 animate-pulse" />
        <span>Đang kết nối...</span>
      </div>
    );
  }

  if (dataStatus === "unsupported" || dataError?.reason === "unsupported") {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 rounded-full text-[10px] font-semibold border border-amber-200 dark:border-amber-800">
        <Wifi className="w-3 h-3" />
        <span>API chưa được hỗ trợ</span>
      </div>
    );
  }

  if (dataStatus === "ready" && !dataError) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded-full text-[10px] font-semibold border border-green-200 dark:border-green-800">
        <Wifi className="w-3 h-3" />
        <span>Đã kết nối</span>
      </div>
    );
  }

  const isConnectionError =
    dataStatus === "connection_error" || dataError?.reason === "network" || dataError?.reason === "server";
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 rounded-full text-[10px] font-semibold border border-red-200 dark:border-red-800">
      <Wifi className="w-3 h-3" />
      <span>{isConnectionError ? "Lỗi kết nối" : "Lỗi dữ liệu"}</span>
    </div>
  );
}

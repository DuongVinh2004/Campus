"use client";

import React from "react";
import { useStore } from "@/lib/store";
import { DATA_MODE_KEY } from "@/lib/data/config";

export function DataModeSwitcher() {
  const { dataConfig } = useStore();

  if (!dataConfig || !dataConfig.enableModeSwitch) {
    return null;
  }

  const toggleMode = () => {
    const nextMode = dataConfig.mode === "mock" ? "api" : "mock";
    localStorage.setItem(DATA_MODE_KEY, nextMode);
    window.location.reload();
  };

  return (
    <button
      onClick={toggleMode}
      className="text-[10px] px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
      title="Click để chuyển đổi mode dữ liệu"
    >
      Chuyển sang {dataConfig.mode === "mock" ? "API" : "Mock"}
    </button>
  );
}

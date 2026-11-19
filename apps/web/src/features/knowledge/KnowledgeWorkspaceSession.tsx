"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { PreservedActivity } from "../learning/learning-session";
import { KnowledgePlatform } from "./KnowledgePlatform";

// Keep the actual forms (including file selections and request keys) in this
// tab. Hidden Activity suspends effects; AppShell revalidates before resuming.
export function KnowledgeWorkspaceSession({ children }: { children: React.ReactNode }) {
  const visible = usePathname() === "/knowledge/sources";
  const [opened, setOpened] = useState(visible);
  useEffect(() => { if (visible) setOpened(true); }, [visible]);
  return <>{!visible && children}
    <PreservedActivity mode={visible ? "visible" : "hidden"}>
      {(opened || visible) && <KnowledgePlatform />}
    </PreservedActivity>
  </>;
}

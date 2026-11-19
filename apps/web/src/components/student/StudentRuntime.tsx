"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import { StudentWorkspaceProvider } from "@/lib/student-workspace";
import { VinUniFormsProvider } from "@/lib/vinuni-workspace";
import { AssistantProvider, useAssistant } from "@/lib/assistant-context";
import { AssistantSurface } from "./AssistantSurface";

function StudentSurface({ children }: { children: ReactNode }) {
  const assistant = useAssistant();
  const pathname = usePathname();
  const router = useRouter();
  const legacyRequest = pathname.match(/^\/(tickets|reviews)\/([^/]+)$/);
  const destination = pathname === "/chat" ? "/student/assistant"
    : legacyRequest ? `/my-requests?${legacyRequest[1] === "tickets" ? "ticket" : "review"}=${encodeURIComponent(decodeURIComponent(legacyRequest[2]))}`
      : pathname === "/dashboard" || pathname === "/reviews" ? "/student" : null;
  useEffect(() => { if (destination) router.replace(destination); }, [destination, router]);
  const supported = assistant.isChat || assistant.contextKey.startsWith("page:/student") || assistant.contextKey.startsWith("draft:") || assistant.contextKey.startsWith("request:") || assistant.contextKey === "page:/my-requests";
  if (destination) return <p role="status" className="p-6 text-center text-sm text-slate-500">Đang mở hồ sơ và dịch vụ của bạn…</p>;
  return <div className={supported && assistant.open && !assistant.isChat ? "lg:pr-[380px]" : ""}>
    {children}
    {supported && !assistant.isChat && <AssistantSurface />}
  </div>;
}
export function StudentRuntime({ children }: { children: ReactNode }) {
  const { currentUser, dataConfig } = useStore();
  if (!currentUser || currentUser.role !== "student") return children;
  return <StudentWorkspaceProvider key={`${dataConfig?.mode}:${currentUser.id}`} userId={currentUser.id} mode={dataConfig?.mode || "mock"}>
    <VinUniFormsProvider><AssistantProvider><StudentSurface>{children}</StudentSurface></AssistantProvider></VinUniFormsProvider>
  </StudentWorkspaceProvider>;
}

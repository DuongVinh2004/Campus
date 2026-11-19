"use client";

import * as React from "react";
import { useCallback, useLayoutEffect, useRef, useState } from "react";

type SessionState = "ready" | "checking" | "changed" | "permissions_changed" | "expired" | "unavailable";
const channelName = "campus247-session-change";

// Runtime React is 19.3; the retained @types/react package predates Activity.
export const PreservedActivity = (React as typeof React & {
  Activity: React.ExoticComponent<{ mode: "visible" | "hidden"; children?: React.ReactNode }>;
}).Activity;

export function announceSessionChange() {
  if (typeof BroadcastChannel === "undefined") return;
  try {
    const channel = new BroadcastChannel(channelName);
    channel.postMessage("changed"); channel.close();
  } catch { /* Focus and periodic identity checks remain available. */ }
}

export function useLearningSession(actorId: string, roles?: readonly string[], checkOnResume = false) {
  const expectedRoles = roles === undefined ? undefined : JSON.stringify([...new Set(roles)].sort());
  const [state, setState] = useState<SessionState>("ready");
  const canAccess = useRef(true);
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const update = useCallback((next: SessionState) => {
    canAccess.current = next === "ready";
    if (mounted.current) setState(next);
  }, []);
  // A periodic check of a still-ready account stays silent: hiding the view (and its focus) every 30 s would
  // take the caret out of whatever the person is typing. Focus, blur and visibility checks still hide first.
  const check = useCallback(async (quiet?: boolean) => {
    if (!actorId) return true;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    if (!(quiet === true && canAccess.current)) update("checking");
    const timeout = window.setTimeout(() => {
      if (mounted.current && request.current === controller && !controller.signal.aborted) {
        controller.abort(); update("unavailable");
      }
    }, 10000);
    try {
      const response = await fetch("/v1/users/me", { credentials: "include", cache: "no-store", signal: controller.signal });
      if (controller.signal.aborted || !mounted.current) return false;
      if (!response.ok) { update(response.status === 401 ? "expired" : "unavailable"); return false; }
      const actor = await response.json();
      if (controller.signal.aborted || !mounted.current) return false;
      const sameActor = (actor.user_id || actor.subject_id) === actorId;
      const sameRoles = expectedRoles === undefined || (Array.isArray(actor.roles)
        && actor.roles.every((role: unknown) => typeof role === "string")
        && JSON.stringify([...new Set(actor.roles)].sort()) === expectedRoles);
      update(!sameActor ? "changed" : !sameRoles ? "permissions_changed" : "ready");
      return sameActor && sameRoles;
    } catch {
      if (!controller.signal.aborted && mounted.current) update("unavailable");
      return false;
    } finally {
      window.clearTimeout(timeout);
    }
  }, [actorId, expectedRoles, update]);
  useLayoutEffect(() => {
    mounted.current = true;
    if (!actorId) return;
    const suspend = () => { request.current?.abort(); update("checking"); };
    const refresh = () => { void check(); };
    const visibility = () => document.visibilityState === "hidden" ? suspend() : refresh();
    let channel: BroadcastChannel | undefined;
    try {
      if (typeof BroadcastChannel !== "undefined") {
        channel = new BroadcastChannel(channelName); channel.onmessage = refresh;
      }
    } catch { /* No data or authority is carried by the optional hint channel. */ }
    window.addEventListener("focus", refresh); window.addEventListener("online", refresh);
    window.addEventListener("blur", suspend); document.addEventListener("visibilitychange", visibility);
    const interval = window.setInterval(() => { void check(true); }, 30000);
    if (checkOnResume) refresh();
    return () => {
      mounted.current = false; request.current?.abort(); channel?.close(); window.clearInterval(interval);
      window.removeEventListener("focus", refresh); window.removeEventListener("online", refresh);
      window.removeEventListener("blur", suspend); document.removeEventListener("visibilitychange", visibility);
    };
  }, [actorId, check, update, checkOnResume]);
  return { state, check, canAccess };
}

export function LearningSessionNotice({ state, onCheck, title = "Kiểm tra tài khoản học liệu", destination = "/learning", destinationLabel = "Mở học liệu bằng phiên hiện tại trong tab mới" }: {
  state: SessionState; onCheck: () => void; title?: string; destination?: string; destinationLabel?: string;
}) {
  if (state === "ready") return null;
  return <main className="mx-auto max-w-xl space-y-4 p-8">
    <h1>{title}</h1>
    <p role={state === "checking" ? "status" : "alert"}>{state === "checking" ? "Đang kiểm tra lại tài khoản…"
      : state === "changed" ? "Tài khoản đăng nhập đã thay đổi. Nội dung của tài khoản trước đang được tạm ẩn."
      : state === "permissions_changed" ? "Quyền truy cập của tài khoản đã thay đổi. Nội dung đã tải đang được tạm ẩn; hãy mở tab mới để tiếp tục với quyền hiện tại."
      : state === "expired" ? "Phiên đăng nhập đã hết hạn. Nội dung riêng đang được tạm ẩn."
      : "Chưa xác minh được phiên đăng nhập. Nội dung riêng đang được tạm ẩn."}</p>
    <p>Bản nháp chưa gửi vẫn được giữ trong tab này.{state !== "permissions_changed" && " Đăng nhập lại tài khoản ban đầu để tiếp tục."}</p>
    <button type="button" disabled={state === "checking"} onClick={onCheck}>Kiểm tra lại tài khoản</button>
    <p><a href={`/login?redirect=${encodeURIComponent(destination)}`} target="_blank" rel="noopener noreferrer">Đăng nhập trong tab mới</a></p>
    <p><a href={destination} target="_blank" rel="noopener noreferrer">{destinationLabel}</a></p>
  </main>;
}

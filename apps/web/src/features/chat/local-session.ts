// Authentication is verified by the server using the HttpOnly session cookie.
export class SessionRenewalError extends Error {
  constructor(readonly status: number) {
    super(status === 401
      ? "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại để tiếp tục; lịch sử đã lưu vẫn được giữ."
      : "Chưa thể kiểm tra phiên đăng nhập. Vui lòng thử kết nối lại.");
    this.name = "SessionRenewalError";
  }
}

export function localTokenExpired(token: string, nowMs = Date.now()): boolean {
  try {
    const parts = token.split(".");
    if (parts.length !== 2) return false;
    const payload = JSON.parse(atob(parts[0].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" && Number.isFinite(payload.exp)
      && payload.exp * 1000 <= nowMs + 30000;
  } catch { return false; }
}

export function clearLegacyLocalToken() {
  try { window.localStorage.removeItem("campus247_token"); } catch { /* Storage may be disabled. */ }
}

export function sessionLoginHref(redirect?: string): string {
  const path = redirect ?? (typeof window === "undefined" ? "/chat" : window.location.pathname + window.location.search);
  return `/login?redirect=${encodeURIComponent(path.startsWith("/") && !path.startsWith("//") ? path : "/chat")}`;
}

// Keep the existing caller contract while discarding all bearer credentials.
export async function renewExpiredLocalToken(_token: string | null, _apiBase: string,
  _signal: AbortSignal): Promise<null> {
  clearLegacyLocalToken();
  return null;
}

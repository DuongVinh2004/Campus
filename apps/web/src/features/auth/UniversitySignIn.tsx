"use client";

import React, { useEffect, useState } from "react";
import { CAMPUS_API_BASE_URL } from "../../lib/api/base-url";
import { ApiClient } from "../../lib/api/client";

/** What each failure code of the sign-in means for the person who sees it. Codes come from the server and never carry provider text. */
export const SIGN_IN_ERRORS: Record<string, string> = {
  ACCOUNT_NOT_PROVISIONED: "Tài khoản của bạn chưa được cấp quyền dùng Campus 24/7. Hãy liên hệ quản trị viên.",
  ACCOUNT_DISABLED: "Tài khoản này đã bị khóa. Hãy liên hệ quản trị viên.",
  ROLE_NOT_MAPPED: "Tài khoản của bạn chưa có vai trò nào trong hệ thống. Hãy liên hệ quản trị viên.",
  STUDENT_CODE_INVALID: "Tài khoản trường không cung cấp mã sinh viên hợp lệ. Hãy liên hệ phòng đào tạo.",
  PROVIDER_DENIED: "Bạn đã hủy đăng nhập hoặc nhà trường từ chối yêu cầu.",
  PROVIDER_UNREACHABLE: "Không kết nối được hệ thống đăng nhập của trường. Hãy thử lại sau ít phút.",
  LOGIN_ATTEMPT_INVALID: "Phiên đăng nhập đã hết hạn hoặc đã được dùng. Hãy bấm đăng nhập lại.",
  TOKEN_EXPIRED: "Phiên đăng nhập của trường đã hết hạn. Hãy thử lại.",
};
const GENERIC_ERROR = "Đăng nhập bằng tài khoản trường không thành công. Hãy thử lại; nếu vẫn lỗi, liên hệ quản trị viên.";

interface ProvidersResponse {
  providers: Array<{ id: string; label: string }>;
}

export function signInErrorMessage(code: string | null): string | null {
  if (!code) return null;
  return SIGN_IN_ERRORS[code] ?? GENERIC_ERROR;
}

/** Safe return path: inside this site only (the server checks again). */
export function returnPath(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : "/";
}

/**
 * "Sign in with the school account". It appears only when the server offers it: the providers endpoint does not exist until the owner
 * configures a provider, and any failure to read it hides the button instead of showing a broken one.
 */
export function UniversitySignIn({ search }: { search?: string }) {
  const [available, setAvailable] = useState(false);
  const params = new URLSearchParams(search ?? (typeof window === "undefined" ? "" : window.location.search));
  const message = signInErrorMessage(params.get("error"));
  const next = returnPath(params.get("next"));

  useEffect(() => {
    let cancelled = false;
    new ApiClient({ baseUrl: CAMPUS_API_BASE_URL })
      .get<ProvidersResponse>("/v1/auth/providers")
      .then((response) => {
        if (!cancelled) setAvailable(response.providers.some((provider) => provider.id === "oidc"));
      })
      .catch(() => {
        if (!cancelled) setAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!available && !message) return null;
  return (
    <section aria-label="Đăng nhập bằng tài khoản trường" data-testid="university-sign-in" className="space-y-3">
      {message ? <p role="alert" data-testid="university-sign-in-error" className="text-sm text-[var(--color-danger,#c0392b)]">{message}</p> : null}
      {available ? (
        <a href={`${CAMPUS_API_BASE_URL}/v1/auth/oidc/start?next=${encodeURIComponent(next)}`}
           className="inline-flex min-h-[44px] w-full items-center justify-center rounded-lg border px-4 py-2 text-sm font-medium">
          Đăng nhập bằng tài khoản trường
        </a>
      ) : null}
    </section>
  );
}

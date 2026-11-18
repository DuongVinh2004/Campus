"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import { SettingsNavigation } from "@/components/shared/SettingsNavigation";
import React, { useEffect, useState, useCallback } from "react";
import { AppShell } from "../../components/AppShell";
import {
  PrivacyCenter,
  type PrivacyNoticeData,
  type PrivacyRequestStatus,
} from "../../features/privacy/PrivacyCenter";
import { AsyncState, type AsyncStatus } from "../../components/AsyncState";
import { ApiClient } from "../../lib/api/client";
import { AssistantSettingsCenter } from "@/features/assistance/AssistantSettingsCenter";
import Link from "next/link";
import { OperationalPrivacy } from "@/features/privacy/OperationalPrivacy";

const API_BASE_URL = CAMPUS_API_BASE_URL;

interface PrivacyNoticeResponse {
  notice_id: string;
  version: string;
  effective_at: string;
  status: string;
  purposes?: string[];
}

export default function PrivacyPage() {
  if (process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true") return <OperationalPrivacy />;
  return process.env.NEXT_PUBLIC_UNIFIED_AI === "true" ? (
    <AppShell activeNav="privacy">
      <div className="campus-settings-page space-y-6">
        <header className="campus-page-heading">
          <div>
            <h1>Cài đặt quyền riêng tư & dữ liệu cá nhân</h1>
            <p>Kiểm soát quyền truy cập, cá nhân hóa và bộ nhớ trợ lý của bạn.</p>
          </div>
        </header>
        <SettingsNavigation active="privacy" />
        <AssistantSettingsCenter inline />
        <section className="fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-5 space-y-3 text-sm text-[var(--text-secondary)]">
          <p>
            History, cá nhân hóa và chất lượng là ba mục đích riêng. Consent không cấp quyền nghiệp vụ. Yêu cầu dữ liệu cá nhân tiếp tục theo quy trình quyền riêng tư của tài khoản.
          </p>
          <p>
            <Link href="/memory" className="font-semibold text-[var(--color-primary)] hover:underline">
              Memory: xem, sửa, quên và export phạm vi riêng
            </Link>
            . Quên chỉ suppression có phiên bản, chưa xóa vật lý history, index hoặc backup. Chat tạm thời không dùng personal memory.{" "}
            <Link href="/notifications" className="font-semibold text-[var(--color-primary)] hover:underline">
              Thông báo trong ứng dụng
            </Link>
            ; kênh ngoài chưa cấu hình.
          </p>
        </section>
      </div>
    </AppShell>
  ) : (
    <ExistingPrivacyPage />
  );
}

function ExistingPrivacyPage() {
  const [notice, setNotice] = useState<PrivacyNoticeData>({
    version: "1.0.0",
    effectiveDate: "01/10/2026",
    purpose: "Xử lý dữ liệu sinh viên phục vụ hỗ trợ đào tạo và dịch vụ Campus 24/7",
    hasConsented: false,
  });
  const [requests, setRequests] = useState<PrivacyRequestStatus[]>([]);
  const [status, setStatus] = useState<AsyncStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const fetchPrivacyData = useCallback(async () => {
    setStatus("loading");
    setErrorMessage("");

    try {
      const client = new ApiClient({ baseUrl: API_BASE_URL });
      const response = await client.get<PrivacyNoticeResponse>("/v1/privacy/notice");

      if (response) {
        const d = response;
        setNotice((prev) => ({
          ...prev,
          version: d.version || "1.0.0",
          effectiveDate: d.effective_at
            ? new Date(d.effective_at).toLocaleDateString("vi-VN")
            : "01/10/2026",
          purpose:
            d.purposes?.join(", ") ||
            "Xử lý dữ liệu sinh viên phục vụ hỗ trợ đào tạo và dịch vụ Campus 24/7",
        }));
      }

      // Sample privacy requests for synthetic demo
      setRequests([
        {
          requestId: "req-001",
          requestType: "EXPORT_DATA",
          status: "completed",
          submittedAt: "20/09/2026",
        },
      ]);

      setStatus("success");
    } catch {
      // Demo fallback when API server is in offline simulation mode
      setNotice({
        version: "v2.1-2026",
        effectiveDate: "01/09/2026",
        purpose:
          "Xử lý dữ liệu sinh viên phục vụ hỗ trợ đào tạo, thủ tục một cửa số và nâng cao chất lượng dịch vụ Campus 24/7 theo Nghị định 13/2023/NĐ-CP",
        hasConsented: false,
      });
      setRequests([
        {
          requestId: "REQ-DATA-0192",
          requestType: "EXPORT_DATA",
          status: "completed",
          submittedAt: "20/09/2026",
        },
      ]);
      setStatus("success");
    }
  }, []);

  const handleConsentChange = useCallback(
    async (consented: boolean) => {
      setNotice((prev) => ({ ...prev, hasConsented: consented }));

      try {
        const client = new ApiClient({ baseUrl: API_BASE_URL });
        await client.post("/v1/privacy/consents", {
          purpose: "QUALITY_FEEDBACK",
          decision: consented ? "GRANTED" : "WITHDRAWN",
          notice_version: notice.version,
        });
      } catch {
        // Optimistic UI state maintained for demo mode
      }
    },
    [notice.version]
  );

  const handleRequestErasure = useCallback(async () => {
    try {
      const client = new ApiClient({ baseUrl: API_BASE_URL });
      await client.post("/v1/privacy/requests", { request_type: "DELETE_DATA" });
    } catch {
      // In demo mode, append a new request locally
    }
    setRequests((prev) => [
      {
        requestId: `REQ-DEL-${Date.now().toString().slice(-4)}`,
        requestType: "DELETE_DATA",
        status: "processing",
        submittedAt: new Date().toLocaleDateString("vi-VN"),
      },
      ...prev,
    ]);
  }, []);

  useEffect(() => {
    fetchPrivacyData();
  }, [fetchPrivacyData]);

  return (
    <AppShell activeNav="privacy">
      <div className="campus-settings-page">
        <AsyncState
          status={status}
          loadingMessage="Đang tải chính sách quyền riêng tư..."
          errorMessage={errorMessage}
          onRetry={fetchPrivacyData}
        >
          <PrivacyCenter
            notice={notice}
            requests={requests}
            onConsentChange={handleConsentChange}
            onRequestErasure={handleRequestErasure}
          />
        </AsyncState>
      </div>
    </AppShell>
  );
}

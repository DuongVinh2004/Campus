"use client";

import React, { useEffect, useState } from "react";
import { ApiClientError } from "../../lib/api/client";
import { answerQualityApi, type StudentGapReports as Reports } from "../../lib/answer-quality-api";

/** Questions students chose to send with "Báo thiếu thông tin": redacted, kept 90 days, no name or account (P2). */
export function StudentGapReports() {
  const [data, setData] = useState<Reports | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    answerQualityApi.studentReports().then((value) => { if (active) setData(value); }).catch((caught) => {
      if (!active) return;
      if (caught instanceof ApiClientError && caught.problem.status === 403) return;
      setError("Không tải được các báo cáo của sinh viên.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <p role="alert" data-testid="student-reports-error" className="campus-panel p-4 text-sm">{error}</p>;
  if (!data) return null;
  const samples = Array.isArray(data.samples) ? data.samples : [];
  return (
    <section aria-labelledby="student-reports-heading" className="space-y-3" data-testid="student-reports">
      <header>
        <h2 id="student-reports-heading" className="text-xl font-semibold">Báo thiếu thông tin do sinh viên gửi</h2>
        <p className="text-sm text-[var(--text-secondary)]">
          Sinh viên tự chọn gửi từng câu, đã ẩn số điện thoại, email và số căn cước, không kèm tên hay tài khoản. Giữ 90 ngày rồi tự xóa.
          Hiện có {data.total} báo cáo{data.total > samples.length ? `; ${data.total - samples.length} báo cáo không giữ chữ vì có dạng mã cá nhân` : ""}.
        </p>
      </header>
      {samples.length === 0 ? (
        <p data-testid="student-reports-empty" className="campus-panel p-4 text-sm">Chưa có báo cáo nào.</p>
      ) : (
        <ul className="space-y-2">
          {samples.map((sample) => (
            <li key={sample.id} className="campus-panel p-4 text-sm">
              <p className="break-words">{sample.question}</p>
              <p className="text-xs text-[var(--text-secondary)]">{new Date(sample.at).toLocaleString("vi-VN")} · hết hạn {new Date(sample.expires_at).toLocaleDateString("vi-VN")}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

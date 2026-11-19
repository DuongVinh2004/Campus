"use client";

import React, { useState } from "react";
import { AdminOverviewPanel } from "../../features/admin/AdminOverviewPanel";
import { OperationsPanel } from "../../features/admin/OperationsPanel";
import { OPS_ENABLED } from "../../lib/campus-ops-api";
import {
  Download,
  TrendingUp,
  Clock,
  Star,
  Sliders,
  ShieldCheck,
  CheckCircle2,
  FileSpreadsheet,
  Edit3,
  X,
  AlertCircle,
} from "lucide-react";
import {
  staffButton,
  staffPrimary,
  staffSurface,
} from "../../components/staff/StaffShell";

interface SlaConfigItem {
  id: string;
  name: string;
  department: string;
  currentHours: number;
}

interface AuditLogItem {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  targetId: string;
  details: string;
}

export default function AdminDashboardPage() {
  if (OPS_ENABLED) {
    return (
      <div className="campus-page space-y-6">
        <AdminOverviewPanel />
        <OperationsPanel />
      </div>
    );
  }
  return <LegacyAdminDashboardPage />;
}

function LegacyAdminDashboardPage() {
  const [slaConfigs, setSlaConfigs] = useState<SlaConfigItem[]>([
    { id: "xac_nhan_sv", name: "Giấy xác nhận sinh viên", department: "Phòng CTSV", currentHours: 24 },
    { id: "bang_diem", name: "Bảng điểm tạm thời", department: "Phòng Quản lý Đào tạo", currentHours: 48 },
    { id: "gioi_thieu_tt", name: "Giấy giới thiệu thực tập", department: "Khoa CNTT", currentHours: 24 },
    { id: "hoan_nvqs", name: "Giấy xác nhận tạm hoãn NVQS", department: "Phòng CTSV", currentHours: 24 },
  ]);

  const [editingSlaId, setEditingSlaId] = useState<string | null>(null);
  const [newSlaHours, setNewSlaHours] = useState<number>(24);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([
    {
      id: "log-001",
      timestamp: "2026-09-26 16:45:10",
      actor: "staff-huce-01",
      action: "CLAIM_TICKET",
      targetId: "TCK-2026-0101",
      details: "Tiếp nhận hồ sơ xin miễn giảm học phí",
    },
    {
      id: "log-002",
      timestamp: "2026-09-26 16:30:22",
      actor: "system-auto",
      action: "AI_TRIAGE_CHECK",
      targetId: "TCK-2026-0102",
      details: "Kiểm tra trùng lặp và đề xuất phân loại",
    },
    {
      id: "log-003",
      timestamp: "2026-09-26 15:10:05",
      actor: "admin-huce-01",
      action: "UPDATE_SLA",
      targetId: "CONFIG-SLA-01",
      details: "Điều chỉnh SLA cấp bảng điểm từ 72h xuống 48h",
    },
  ]);

  const handleEditSla = (item: SlaConfigItem) => {
    setEditingSlaId(item.id);
    setNewSlaHours(item.currentHours);
  };

  const handleSaveSla = (id: string) => {
    const config = slaConfigs.find((configItem) => configItem.id === id);
    const oldHours = config?.currentHours;
    setSlaConfigs((prev) =>
      prev.map((configItem) =>
        configItem.id === id ? { ...configItem, currentHours: Number(newSlaHours) } : configItem
      )
    );
    // Auto-log SLA change to audit trail
    if (config && oldHours !== Number(newSlaHours)) {
      const newLog: AuditLogItem = {
        id: `log-${Date.now()}`,
        timestamp: new Date().toLocaleString("vi-VN"),
        actor: "admin-huce-01",
        action: "UPDATE_SLA",
        targetId: `CONFIG-${id}`,
        details: `Đổi SLA "${config.name}" từ ${oldHours}h → ${newSlaHours}h`,
      };
      setAuditLogs((prev) => [newLog, ...prev]);
    }
    setEditingSlaId(null);
  };

  const handleExportAudit = () => {
    const csvContent =
      "data:text/csv;charset=utf-8,ID,Timestamp,Actor,Action,Target,Details\n" +
      auditLogs
        .map((logItem) => `${logItem.id},${logItem.timestamp},${logItem.actor},${logItem.action},${logItem.targetId},"${logItem.details}"`)
        .join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `audit_log_campus247_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setExportNotice("Đã xuất thành công tệp kiểm toán CSV!");
    setTimeout(() => setExportNotice(null), 4000);
  };

  return (
    <div className="campus-page flex flex-col gap-6">
        {/* Header */}
        <header className="campus-page-heading">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              </span>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
                Bảng điều khiển Quản trị Một cửa số (Admin Ops)
              </h1>
            </div>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Giám sát chất lượng tiếp nhận, cấu hình cam kết SLA và kiểm toán tuân thủ toàn trường
            </p>
          </div>

          <button
            type="button"
            onClick={handleExportAudit}
            className={staffButton}
            aria-label="Xuất dữ liệu kiểm toán"
          >
            <Download className="h-4 w-4 text-slate-500" aria-hidden="true" />
            <span>Xuất dữ liệu kiểm toán</span>
          </button>
        </header>

        {exportNotice && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 shadow-xs dark:border-emerald-900/60 dark:bg-emerald-950/60 dark:text-emerald-300"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{exportNotice}</span>
          </div>
        )}

        {/* Operational KPI Cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className={`${staffSurface} p-5 shadow-xs border border-[var(--border-color)] bg-[var(--surface-card)]`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                Tổng hồ sơ tiếp nhận
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--color-primary-light)] text-[var(--color-primary)]">
                <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />
              </span>
            </div>
            <div className="mt-3 text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
              1,248
            </div>
            <div className="mt-2 flex items-center gap-1 text-xs font-semibold text-[var(--color-status-success)]">
              <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
              <span>↑ +12.4% so với tuần trước</span>
            </div>
          </div>

          <div className={`${staffSurface} p-5 shadow-xs border border-[var(--border-color)] bg-[var(--surface-card)]`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                Tỷ lệ đúng hạn SLA
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--color-primary-light)] text-[var(--color-primary)]">
                <Clock className="h-4 w-4" aria-hidden="true" />
              </span>
            </div>
            <div className="mt-3 text-3xl font-extrabold tracking-tight text-[var(--color-primary)]">
              98.5%
            </div>
            <div className="mt-2 text-xs text-[var(--text-secondary)]">
              Cam kết dịch vụ vượt chỉ tiêu 95%
            </div>
          </div>

          <div className={`${staffSurface} p-5 shadow-xs border border-[var(--border-color)] bg-[var(--surface-card)]`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                Hồ sơ đang tồn đọng
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300">
                <AlertCircle className="h-4 w-4" aria-hidden="true" />
              </span>
            </div>
            <div className="mt-3 text-3xl font-extrabold tracking-tight text-amber-600 dark:text-amber-400">
              14
            </div>
            <div className="mt-2 text-xs text-[var(--text-secondary)]">
              0 ca quá hạn thời gian cam kết
            </div>
          </div>

          <div className={`${staffSurface} p-5 shadow-xs border border-[var(--border-color)] bg-[var(--surface-card)]`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                Mức độ hài lòng CSAT
              </span>
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                <Star className="h-4 w-4" aria-hidden="true" />
              </span>
            </div>
            <div className="mt-3 text-3xl font-extrabold tracking-tight text-emerald-600 dark:text-emerald-400">
              4.85 / 5
            </div>
            <div className="mt-2 text-xs text-[var(--text-secondary)]">
              Dựa trên 412 lượt đánh giá sinh viên
            </div>
          </div>
        </div>

        {/* SLA Configuration Table */}
        <section className={`${staffSurface} p-6 shadow-xs border border-[var(--border-color)] bg-[var(--surface-card)]`}>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Sliders className="h-5 w-5 text-[var(--color-primary)]" aria-hidden="true" />
                <h2 className="text-lg font-bold text-[var(--text-primary)]">
                  Cấu hình cam kết thời hạn xử lý (SLA)
                </h2>
              </div>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                Thiết lập thời gian phản hồi và xử lý tối đa theo từng loại hồ sơ Một cửa số
              </p>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-[var(--border-color)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--surface-subtle)] text-xs font-semibold text-[var(--text-secondary)] border-b border-[var(--border-color)]">
                <tr>
                  <th scope="col" className="px-4 py-3">Loại giấy tờ / Thủ tục</th>
                  <th scope="col" className="px-4 py-3">Đơn vị phụ trách</th>
                  <th scope="col" className="px-4 py-3">Thời hạn cam kết SLA</th>
                  <th scope="col" className="px-4 py-3">Hành động</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]">
                {slaConfigs.map((config) => {
                  const isEditing = editingSlaId === config.id;
                  return (
                    <tr key={config.id} className="hover:bg-[var(--surface-subtle)] transition-colors">
                      <td className="px-4 py-3.5 font-semibold text-[var(--text-primary)]">
                        {config.name}
                      </td>
                      <td className="px-4 py-3.5 text-[var(--text-secondary)]">
                        {config.department}
                      </td>
                      <td className="px-4 py-3.5">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <label htmlFor={`sla-input-${config.id}`} className="sr-only">
                              Thời hạn SLA mới (giờ)
                            </label>
                            <input
                              id={`sla-input-${config.id}`}
                              type="number"
                              min={1}
                              max={168}
                              value={newSlaHours}
                              onChange={(e) => setNewSlaHours(Number(e.target.value))}
                              className="w-20 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-2.5 py-1 text-sm font-semibold text-[var(--text-primary)] shadow-xs focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                            />
                            <span className="text-xs text-[var(--text-secondary)]">giờ</span>
                          </div>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-[var(--color-primary-light)] px-3 py-1 text-xs font-bold text-[var(--color-primary)]">
                            {config.currentHours} giờ
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3.5">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleSaveSla(config.id)}
                              className={staffPrimary}
                              aria-label="Lưu cấu hình SLA"
                            >
                              Lưu cấu hình SLA
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingSlaId(null)}
                              className={staffButton}
                            >
                              <X className="h-4 w-4" aria-hidden="true" />
                              <span>Hủy</span>
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleEditSla(config)}
                            aria-label={`Chỉnh sửa SLA ${config.name}`}
                            className={staffButton}
                          >
                            <Edit3 className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>Chỉnh sửa</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Audit Log Section */}
        <section className={`${staffSurface} p-6 shadow-xs border border-[var(--border-color)] bg-[var(--surface-card)]`}>
          <div className="mb-4">
            <h2 className="text-lg font-bold text-[var(--text-primary)]">
              Nhật ký kiểm toán Một cửa số (Audit Trail)
            </h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              Ghi nhận bất biến mọi tác vụ nghiệp vụ, phân quyền và can thiệp thủ tục của cán bộ
            </p>
          </div>

          <div className="overflow-x-auto rounded-xl border border-[var(--border-color)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--surface-subtle)] text-xs font-semibold text-[var(--text-secondary)] border-b border-[var(--border-color)]">
                <tr>
                  <th scope="col" className="px-4 py-3">Thời gian</th>
                  <th scope="col" className="px-4 py-3">Người thực hiện</th>
                  <th scope="col" className="px-4 py-3">Hành động</th>
                  <th scope="col" className="px-4 py-3">Mã đối tượng</th>
                  <th scope="col" className="px-4 py-3">Chi tiết tác vụ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]">
                {auditLogs.map((logItem) => (
                  <tr key={logItem.id} className="hover:bg-[var(--surface-subtle)] transition-colors">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-[var(--text-secondary)]">
                      {logItem.timestamp}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 font-semibold text-[var(--text-primary)]">
                      {logItem.actor}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="rounded-md bg-[var(--surface-subtle)] px-2 py-0.5 font-mono text-xs font-semibold text-[var(--text-secondary)] border border-[var(--border-color)]">
                        {logItem.action}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 font-semibold text-[var(--color-primary)]">
                      {logItem.targetId}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">
                      {logItem.details}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
  );
}

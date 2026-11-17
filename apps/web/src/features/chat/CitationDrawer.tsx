import React from "react";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { CitationSource, type CitationSourceBinding } from "./CitationSource";
import { FileTextIcon, XIcon, ShieldCheckIcon, AlertTriangleIcon, ArrowRightIcon } from "../../components/Icons";

export interface CitationItem {
  id: string;
  title: string;
  documentRef: string;
  quote: string;
  authority?: string;
  locator?: string;
  effectiveDate?: string;
  validityStatus?: "active" | "stale" | "conflicting";
  isSimulation?: boolean;
  canonicalUrl?: string;
  sourceBinding?: CitationSourceBinding;
  confidence?: number;
  isAuthorized?: boolean;
}

export interface CitationDrawerProps {
  isOpen: boolean;
  citations: CitationItem[];
  onClose: () => void;
  onReportIssue?: (citationId: string) => void;
}

export function CitationDrawer({
  isOpen,
  citations,
  onClose,
  onReportIssue,
}: CitationDrawerProps) {
  const getValidityBadge = (status?: string) => {
    switch (status) {
      case "stale":
        return {
          text: "Văn bản cần đối chiếu",
          className: "badge badge-warning",
        };
      case "conflicting":
        return {
          text: "Có nội dung mâu thuẫn",
          className: "badge badge-danger",
        };
      case "active":
      default:
        return {
          text: process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" ? "Nguồn trong câu trả lời — mở để kiểm tra lại" : "Văn bản đang hiệu lực",
          className: "badge badge-success",
        };
    }
  };

  return (
    <AccessibleDialog open={isOpen} onClose={onClose} labelledBy="citation-drawer-title" className="campus-citation-sheet">
        {/* Drawer Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: "1px solid var(--color-border, #e2e8f0)",
            paddingBottom: "16px",
            marginBottom: "16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
            <div
              style={{
                width: "36px",
                flexShrink: 0,
                height: "36px",
                borderRadius: "var(--radius-md, 8px)",
                backgroundColor: "var(--color-primary-light, #eff6ff)",
                color: "var(--color-primary, #1e3a8a)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <FileTextIcon size={20} />
            </div>
            <div style={{ minWidth: 0, overflowWrap: "anywhere" }}>
              <h2 id="citation-drawer-title" style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "var(--color-text-main, #0f172a)" }}>
                Nguồn trích dẫn & Bằng chứng
              </h2>
              <span style={{ fontSize: "11px", color: "var(--color-text-muted, #64748b)" }}>
                Kiểm chứng căn cứ văn bản và thời hiệu
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            style={{
              minHeight: "44px",
              minWidth: "44px",
              flexShrink: 0,
              border: "none",
              backgroundColor: "var(--surface-subtle, #f1f5f9)",
              fontSize: "14px",
              color: "var(--color-text-muted, #475569)",
              cursor: "pointer",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <XIcon size={16} />
          </button>
        </div>

        {/* Citations List */}
        <div style={{ flex: 1, minWidth: 0, overflowY: "auto", overflowX: "hidden", display: "flex", flexDirection: "column", gap: "16px" }}>
          {citations.length === 0 ? (
            <div style={{ textAlign: "center", padding: "36px 16px", color: "var(--color-text-muted, #64748b)", fontSize: "13px" }}>
              Không có nguồn trích dẫn nào cho câu trả lời này.
            </div>
          ) : (
            citations.map((cite) => {
              if (cite.isAuthorized === false) {
                return (
                  <article
                    key={cite.id}
                    style={{
                      border: "1px solid var(--color-border, #e2e8f0)",
                      borderRadius: "var(--radius-lg, 12px)",
                      padding: "16px",
                      backgroundColor: "var(--surface-subtle, #f8fafc)",
                      boxShadow: "var(--shadow-ambient, 0 1px 3px rgba(15,23,42,0.04))",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                      <ShieldCheckIcon size={16} />
                      <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "var(--color-text-muted, #64748b)" }}>
                        Tài liệu hạn chế truy cập
                      </h3>
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--color-text-muted, #64748b)" }}>
                      Bạn không có quyền truy cập xem chi tiết tài liệu này.
                    </div>
                  </article>
                );
              }

              const isPublicSnapshot = cite.documentRef.startsWith("public-");
              const badge = isPublicSnapshot
                ? { text: "Nguồn HUCE", className: "badge badge-success" }
                : cite.isSimulation ? { text: "Nguồn mô phỏng", className: "badge badge-warning" } : getValidityBadge(cite.validityStatus);
              return (
                <article
                  key={cite.id}
                  style={{
                    border: "1px solid var(--color-border, #e2e8f0)",
                    borderRadius: "var(--radius-lg, 12px)",
                    padding: "16px",
                    minWidth: 0,
                    flexShrink: 0,
                    overflowWrap: "anywhere",
                    backgroundColor: "var(--surface-subtle, #f8fafc)",
                    boxShadow: "var(--shadow-ambient, 0 1px 3px rgba(15,23,42,0.04))",
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "8px", marginBottom: "8px" }}>
                    <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "var(--color-primary, #1e3a8a)", lineHeight: 1.4 }}>
                      {cite.title}
                    </h3>
                    <span className={badge.className} style={{ maxWidth: "100%", whiteSpace: "normal", lineHeight: 1.5 }}>
                      {badge.text}
                    </span>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: "var(--color-text-muted, #475569)", marginBottom: "10px" }}>
                    {!isPublicSnapshot && <div>
                      {process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" ? "Phiên bản nguồn:" : "Mã văn bản:"} <strong style={{ color: "var(--color-text-main, #1e293b)" }}>{cite.documentRef}</strong>
                    </div>}
                    {cite.authority && (
                      <div>
                        Cơ quan ban hành: <span style={{ color: "var(--color-text-main, #1e293b)" }}>{cite.authority}</span>
                      </div>
                    )}
                    {cite.locator && (
                      <div>
                        Vị trí trích lục: <span style={{ color: "var(--color-text-main, #1e293b)" }}>{cite.locator}</span>
                      </div>
                    )}
                    {cite.effectiveDate && (
                      <div>
                        Ngày hiệu lực: <span style={{ color: "var(--color-text-main, #1e293b)" }}>{cite.effectiveDate}</span>
                      </div>
                    )}
                  </div>

                  <blockquote
                    style={{
                      margin: 0,
                      padding: "10px 14px",
                      borderLeft: "3px solid var(--color-primary, #1e3a8a)",
                      backgroundColor: "var(--surface-card, #ffffff)",
                      borderRadius: "0 6px 6px 0",
                      fontSize: "13px",
                      color: "var(--color-text-main, #1e293b)",
                      lineHeight: 1.5,
                      fontStyle: "italic",
                      boxShadow: "inset 0 1px 2px rgba(0,0,0,0.02)",
                    }}
                  >
                    "{cite.quote}"
                  </blockquote>

                  {/* Actions & Report Issue */}
                  <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", alignItems: "stretch", gap: "16px", paddingTop: "12px", borderTop: "1px dashed var(--color-border, #e2e8f0)" }}>
                    {cite.sourceBinding && <CitationSource binding={cite.sourceBinding} />}
                    {cite.canonicalUrl ? (
                      <a
                        href={cite.canonicalUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          fontSize: "12px",
                          fontWeight: 600,
                          color: "var(--color-primary, #1e3a8a)",
                          textDecoration: "none",
                        }}
                      >
                        <span>Mở văn bản gốc</span>
                        <ArrowRightIcon size={13} />
                      </a>
                    ) : !cite.sourceBinding ? (
                      <span style={{ fontSize: "11px", color: "var(--color-text-muted, #64748b)" }}>
                        Lưu trữ nội bộ HUCE
                      </span>
                    ) : null}

                    {onReportIssue && (
                      <button
                        type="button"
                        onClick={() => onReportIssue(cite.id)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          padding: "4px 8px",
                          borderRadius: "4px",
                          backgroundColor: "transparent",
                          color: "var(--color-text-muted, #475569)",
                          border: "1px solid var(--color-border, #e2e8f0)",
                          fontSize: "11px",
                          cursor: "pointer",
                        }}
                      >
                        <AlertTriangleIcon size={12} />
                        <span>Báo lỗi nguồn</span>
                      </button>
                    )}
                  </div>
                </article>
              );
            })
          )}
        </div>
    </AccessibleDialog>
  );
}

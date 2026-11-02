import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CapabilityBanner, type SystemOperationalStatus } from "./CapabilityBanner";

describe("CapabilityBanner Component (TASK-WEB-OPS-002)", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders degradation warning banner with affected capabilities and non-color text", () => {
    const status: SystemOperationalStatus = {
      mode: "degraded",
      message: "Hệ thống đang hoạt động ở chế độ suy giảm năng lực. Dịch vụ AI đang dùng mô hình dự phòng.",
      affectedServices: ["LLM Streaming", "Vector Search"],
    };

    render(<CapabilityBanner status={status} />);

    expect(screen.getByRole("region")).toBeDefined();
    expect(screen.getAllByText(status.message)).toHaveLength(2);
    expect(screen.getByText(/LLM Streaming/i)).toBeDefined();
    expect(screen.getByText(/Vector Search/i)).toBeDefined();
    // Non-color indicator
    expect(screen.getByText(/\[!\] SUY GIẢM/i)).toBeDefined();
  });

  it("does not render banner when system is healthy and metrics normal", () => {
    const status: SystemOperationalStatus = {
      mode: "healthy",
      message: "Tất cả các dịch vụ đang hoạt động bình thường.",
      affectedServices: [],
    };

    render(<CapabilityBanner status={status} />);
    expect(screen.queryByRole("region")).toBeNull();
  });

  it("shows KPI context with metric name, value, unit, time window, freshness, and source together", () => {
    const status: SystemOperationalStatus = {
      mode: "degraded",
      message: "Một số chỉ số vận hành đang vượt ngưỡng cảnh báo.",
      affectedServices: ["API Gateway"],
      metrics: [
        {
          name: "Độ trễ P95",
          value: 1250,
          unit: "ms",
          timeWindow: "15 phút qua",
          freshness: "Cập nhật 20 giây trước",
          source: "Prometheus Gateway",
          status: "degraded",
        },
      ],
    };

    render(<CapabilityBanner status={status} />);

    // Check all 6 required KPI context elements together
    expect(screen.getByText("Độ trễ P95")).toBeDefined();
    expect(screen.getByText("1250")).toBeDefined();
    expect(screen.getByText("ms")).toBeDefined();
    expect(screen.getByText("15 phút qua")).toBeDefined();
    expect(screen.getByText("Cập nhật 20 giây trước")).toBeDefined();
    expect(screen.getByText("Prometheus Gateway")).toBeDefined();
  });

  it("distinguishes unavailable and degraded data transparently with non-color labels", () => {
    const status: SystemOperationalStatus = {
      mode: "degraded",
      message: "Hạ tầng gặp sự cố phân mảnh mạng.",
      affectedServices: ["Redis Cache", "Search Index"],
      metrics: [
        {
          name: "Bộ nhớ Cache",
          value: "--",
          unit: "MB",
          timeWindow: "5 phút qua",
          freshness: "Chưa xác định",
          source: "Redis Sentinel",
          status: "unavailable",
        },
        {
          name: "Tỷ lệ lỗi Search",
          value: 14.2,
          unit: "%",
          timeWindow: "10 phút qua",
          freshness: "Cập nhật 1 phút trước",
          source: "Elastic Node",
          status: "degraded",
        },
      ],
    };

    render(<CapabilityBanner status={status} />);

    // Distinct non-color badges for unavailable vs degraded
    expect(screen.getByText(/\[✕\] Không khả dụng/i)).toBeDefined();
    expect(screen.getAllByText(/\[!\] Suy giảm/i).length).toBeGreaterThanOrEqual(1);
  });

  it("handles stale data state explicitly", () => {
    const status: SystemOperationalStatus = {
      mode: "degraded",
      message: "Đồng bộ chỉ số bị trễ.",
      affectedServices: [],
      metrics: [
        {
          name: "Hàng đợi tiếp nhận",
          value: 24,
          unit: "yêu cầu",
          timeWindow: "1 giờ qua",
          freshness: "Cập nhật 45 phút trước (Dữ liệu cũ)",
          source: "Ticket Collector",
          status: "stale",
        },
      ],
    };

    render(<CapabilityBanner status={status} />);

    expect(screen.getByText(/\[~\] Dữ liệu cũ/i)).toBeDefined();
    expect(screen.getByText(/Cập nhật 45 phút trước \(Dữ liệu cũ\)/i)).toBeDefined();
  });

  it("is dismissible only when approved via isDismissible prop", () => {
    const handleDismiss = vi.fn();
    const dismissibleStatus: SystemOperationalStatus = {
      mode: "degraded",
      message: "Cảnh báo bảo trì định kỳ.",
      affectedServices: [],
      isDismissible: true,
    };

    const { rerender } = render(
      <CapabilityBanner status={dismissibleStatus} onDismiss={handleDismiss} />
    );

    const dismissBtn = screen.getByRole("button", { name: /Đóng thông báo/i });
    expect(dismissBtn).toBeDefined();
    fireEvent.click(dismissBtn);
    expect(handleDismiss).toHaveBeenCalled();

    // When isDismissible is false or omitted, no dismiss button is rendered
    const nonDismissibleStatus: SystemOperationalStatus = {
      mode: "degraded",
      message: "Cảnh báo nghiêm trọng không thể bỏ qua.",
      affectedServices: ["Core DB"],
      isDismissible: false,
    };

    rerender(<CapabilityBanner status={nonDismissibleStatus} onDismiss={handleDismiss} />);
    expect(screen.queryByRole("button", { name: /Đóng thông báo/i })).toBeNull();
  });
});

import React from "react";

interface SkeletonProps {
  width?: string;
  height?: string;
  borderRadius?: string;
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({
  width = "100%",
  height = "14px",
  borderRadius,
  className = "",
  style,
}: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-slate-200 dark:bg-slate-700 rounded ${className}`}
      aria-hidden="true"
      style={{
        width,
        height,
        borderRadius,
        ...style,
      }}
    />
  );
}

export function SkeletonCard() {
  return (
    <div
      className="p-5 flex flex-col gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl"
      aria-hidden="true"
    >
      <div className="flex justify-between items-center">
        <Skeleton width="60%" height="20px" borderRadius="6px" />
        <Skeleton width="80px" height="24px" borderRadius="9999px" />
      </div>
      <Skeleton width="100%" height="14px" />
      <Skeleton width="85%" height="14px" />
      <div className="flex gap-2 mt-1">
        <Skeleton width="100px" height="32px" borderRadius="8px" />
        <Skeleton width="100px" height="32px" borderRadius="8px" />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Đang tải dữ liệu...">
      {Array.from({ length: count }, (_, i) => (
        <SkeletonCard key={`skel-${i}`} />
      ))}
    </div>
  );
}

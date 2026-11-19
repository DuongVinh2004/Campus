import React from "react";
import { AlertTriangle } from "lucide-react";

export interface ClaimEvidenceProps {
  id?: string;
  text: string;
  isUnsupported?: boolean;
  citationIndices?: number[];
  onCitationClick?: (index: number) => void;
}

export function ClaimEvidence({
  id,
  text,
  isUnsupported = false,
  citationIndices = [],
  onCitationClick,
}: ClaimEvidenceProps) {
  if (isUnsupported) {
    return (
      <span
        id={id}
        data-testid="unsupported-claim"
        title="Nội dung chưa được kiểm chứng"
        className="relative bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300 border-b border-dotted border-rose-500 px-1 py-0.5 rounded text-sm inline"
      >
        {text}
        <span className="inline-flex items-center ml-1 align-middle text-rose-600 dark:text-rose-400">
          <AlertTriangle className="w-3 h-3" />
        </span>
      </span>
    );
  }

  return (
    <span id={id} data-testid="supported-claim">
      {text}
      {citationIndices.length > 0 && (
        <sup
          data-testid="citation-badges"
          className="ml-0.5 inline-flex gap-0.5 select-none align-super"
        >
          {citationIndices.map((idx) => (
            <React.Fragment key={idx}>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  onCitationClick?.(idx);
                }}
                aria-label={`Xem nguồn trích dẫn ${idx}`}
                className="bg-blue-100 hover:bg-blue-200 dark:bg-blue-900/60 dark:hover:bg-blue-800/80 text-blue-800 dark:text-blue-300 border-0 rounded px-1 text-[10px] font-semibold cursor-pointer inline-flex items-center justify-center leading-none h-3.5 transition-colors focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {idx}
              </button>
            </React.Fragment>
          ))}
        </sup>
      )}
    </span>
  );
}

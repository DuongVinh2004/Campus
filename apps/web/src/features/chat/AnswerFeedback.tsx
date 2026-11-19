import React, { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";

export type FeedbackRating = "helpful" | "not_helpful";

export interface AnswerFeedbackProps {
  answerId: string;
  onFeedbackSubmit?: (answerId: string, rating: FeedbackRating) => Promise<void> | void;
}

export function AnswerFeedback({ answerId, onFeedbackSubmit }: AnswerFeedbackProps) {
  const [selectedRating, setSelectedRating] = useState<FeedbackRating | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleVote = async (rating: FeedbackRating) => {
    setSelectedRating(rating);
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      if (onFeedbackSubmit) {
        await onFeedbackSubmit(answerId, rating);
      }
      setSubmitted(true);
    } catch {
      setErrorMessage("Không thể gửi đánh giá. Vui lòng thử lại.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div
        aria-live="polite"
        className="text-xs text-emerald-600 dark:text-emerald-400 py-1 font-medium"
      >
        Cảm ơn bạn đã phản hồi!
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 mt-2">
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <span>Câu trả lời có hữu ích không?</span>
        <button
          type="button"
          onClick={() => handleVote("helpful")}
          disabled={isSubmitting}
          aria-label="Hữu ích"
          aria-pressed={selectedRating === "helpful"}
          className={`min-h-[36px] px-3.5 py-1.5 text-xs font-medium rounded-full inline-flex items-center gap-1.5 transition-colors cursor-pointer border ${
            selectedRating === "helpful"
              ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 shadow-none"
              : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs"
          } ${isSubmitting ? "cursor-not-allowed opacity-60" : ""}`}
        >
          <ThumbsUp className="w-3.5 h-3.5" />
          <span>Hữu ích</span>
        </button>
        <button
          type="button"
          onClick={() => handleVote("not_helpful")}
          disabled={isSubmitting}
          aria-label="Chưa hữu ích"
          aria-pressed={selectedRating === "not_helpful"}
          className={`min-h-[36px] px-3.5 py-1.5 text-xs font-medium rounded-full inline-flex items-center gap-1.5 transition-colors cursor-pointer border ${
            selectedRating === "not_helpful"
              ? "border-rose-300 dark:border-rose-700 bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 shadow-none"
              : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs"
          } ${isSubmitting ? "cursor-not-allowed opacity-60" : ""}`}
        >
          <ThumbsDown className="w-3.5 h-3.5" />
          <span>Chưa hữu ích</span>
        </button>
      </div>

      {errorMessage && (
        <div
          role="alert"
          className="flex items-center gap-2 text-xs text-rose-600 dark:text-rose-400 mt-1"
        >
          <span>{errorMessage}</span>
          {selectedRating && (
            <button
              type="button"
              onClick={() => handleVote(selectedRating)}
              className="text-xs underline bg-transparent border-0 text-rose-600 dark:text-rose-400 cursor-pointer px-1 py-0.5 font-medium hover:text-rose-700 dark:hover:text-rose-300"
            >
              Thử lại
            </button>
          )}
        </div>
      )}
    </div>
  );
}

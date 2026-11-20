"use client";

import { useT, type MessageKey } from "@/lib/i18n";
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Bell,
  Building2,
  CheckCheck,
  FolderOpen,
  RefreshCw,
} from "lucide-react";
import {
  notificationsApi,
  problemMessage,
  type AppNotification,
} from "@/lib/campus-ops-api";

function formatRelativeTime(isoString: string, t: (key: MessageKey, params?: Record<string, string | number>) => string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  if (Number.isNaN(diffMs) || diffMs < 0) {
    return t("inbox.justNow");
  }

  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);

  if (diffMin < 1) {
    return t("inbox.justNow");
  }
  if (diffMin < 60) {
    return t("inbox.minutesAgo", { n: diffMin });
  }

  const toDayString = (d: Date) =>
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);

  const todayStr = toDayString(now);
  const notifStr = toDayString(date);

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = toDayString(yesterday);

  if (diffHours < 24 && notifStr === todayStr) {
    return t("inbox.hoursAgo", { n: diffHours });
  }
  if (notifStr === yesterdayStr) {
    return t("inbox.yesterday");
  }
  if (diffHours < 24) {
    return t("inbox.hoursAgo", { n: diffHours });
  }

  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return formatter.format(date).replace(",", "");
}

function formatFullTime(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function getNotificationIcon(kind: string) {
  switch (kind) {
    case "TICKET":
      return FolderOpen;
    case "ROOM_BOOKING":
      return Building2;
    default:
      return Bell;
  }
}

export function NotificationsInbox() {
  const t = useT();
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState<boolean>(false);

  const loadNotifications = useCallback(
    async (showSkeleton = true) => {
      if (showSkeleton) {
        setLoading(true);
      }
      setError(null);
      try {
        const res = await notificationsApi.list({
          unreadOnly: filter === "unread",
        });
        setItems(res.items);
        setUnreadCount(res.unread_count);
      } catch (err) {
        setError(problemMessage(err));
      } finally {
        setLoading(false);
      }
    },
    [filter]
  );

  useEffect(() => {
    loadNotifications(true);
  }, [loadNotifications]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      loadNotifications(false);
    }, 60000);

    const handleFocus = () => {
      loadNotifications(false);
    };

    const handleNotificationsChanged = () => {
      loadNotifications(false);
    };

    window.addEventListener("focus", handleFocus);
    window.addEventListener(
      "campus:notifications-changed",
      handleNotificationsChanged
    );

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener(
        "campus:notifications-changed",
        handleNotificationsChanged
      );
    };
  }, [loadNotifications]);

  const handleMarkAllRead = async () => {
    if (unreadCount === 0 || markingAll) return;
    try {
      setMarkingAll(true);
      setError(null);
      await notificationsApi.markAllRead();
      setUnreadCount(0);
      if (filter === "unread") {
        setItems([]);
      } else {
        setItems((prev) => prev.map((item) => ({ ...item, read: true })));
      }
      window.dispatchEvent(new Event("campus:notifications-changed"));
    } catch (err) {
      setError(problemMessage(err));
    } finally {
      setMarkingAll(false);
    }
  };

  const handleItemClick = (item: AppNotification) => {
    if (!item.read) {
      setItems((prev) =>
        prev.map((n) => (n.id === item.id ? { ...n, read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
      void notificationsApi
        .markRead(item.id)
        .then(() => {
          window.dispatchEvent(new Event("campus:notifications-changed"));
        })
        .catch((err) => {
          setError(problemMessage(err));
        });
    }
  };

  return (
    <div className="campus-page min-w-0 space-y-6" data-testid="notifications-inbox">
      <header className="campus-page-heading">
        <div data-eyebrow={t("inbox.eyebrow")}>
          <h1 className="text-2xl font-semibold">{t("inbox.title")}</h1>
          <p>{t("inbox.subtitle")}</p>
        </div>
      </header>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-[var(--border-color)] pb-4">
        <div
          role="tablist"
          aria-label={t("inbox.filterLabel")}
          className="inline-flex rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] p-1"
        >
          <button
            type="button"
            role="tab"
            aria-selected={filter === "all"}
            data-testid="notifications-filter-all"
            onClick={() => setFilter("all")}
            className={`inline-flex min-h-[44px] items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] ${
              filter === "all"
                ? "bg-[var(--surface-card)] text-[var(--color-primary)] font-semibold shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {t("inbox.all")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filter === "unread"}
            data-testid="notifications-filter-unread"
            onClick={() => setFilter("unread")}
            className={`inline-flex min-h-[44px] items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] ${
              filter === "unread"
                ? "bg-[var(--surface-card)] text-[var(--color-primary)] font-semibold shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {t("inbox.unread", { count: unreadCount })}
          </button>
        </div>

        <button
          type="button"
          data-testid="notifications-read-all"
          disabled={unreadCount === 0 || markingAll}
          onClick={handleMarkAllRead}
          className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-subtle)] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
        >
          <CheckCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
          {t("inbox.markAll")}
        </button>
      </div>

      {loading && items.length === 0 && (
        <div
          role="status"
          className="campus-panel flex flex-col items-center justify-center py-12 text-center text-[var(--text-secondary)]"
        >
          <RefreshCw
            className="h-6 w-6 animate-spin text-[var(--color-primary)] mb-2"
            aria-hidden="true"
          />
          <p>{t("inbox.loading")}</p>
        </div>
      )}

      {error && items.length === 0 && (
        <div
          role="alert"
          className="campus-panel flex flex-col items-center justify-center py-10 text-center space-y-3"
        >
          <p className="text-sm font-medium text-[var(--text-primary)]">{error}</p>
          <button
            type="button"
            onClick={() => loadNotifications(true)}
            className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-[var(--color-primary)] px-5 py-2.5 text-sm font-medium text-[var(--color-on-primary)] transition-colors hover:bg-[var(--color-primary-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          >
            {t("inbox.retry")}
          </button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="campus-empty-state">
          <Bell className="h-6 w-6" aria-hidden="true" />
          <p className="text-base font-semibold text-[var(--text-primary)]">
            {filter === "unread" ? t("inbox.emptyUnread") : t("inbox.empty")}
          </p>
          <p className="max-w-md text-sm text-[var(--text-secondary)]">
            {filter === "unread" ? t("inbox.emptyUnreadHint") : t("inbox.emptyHint")}
          </p>
        </div>
      )}

      {items.length > 0 && (
        <div className="space-y-3" role="feed" aria-label={t("inbox.feed")}>
          {error && (
            <div
              role="alert"
              className="flex items-center justify-between rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] p-4 text-sm"
            >
              <span className="text-[var(--text-primary)]">{error}</span>
              <button
                type="button"
                onClick={() => loadNotifications(false)}
                className="inline-flex min-h-[44px] items-center px-3 font-medium text-[var(--color-primary)] hover:underline"
              >
                {t("inbox.retry")}
              </button>
            </div>
          )}
          {items.map((item) => {
            const Icon = getNotificationIcon(item.kind);
            const isInternal = Boolean(item.link && item.link.startsWith("/"));
            const cardClasses = `campus-notification-card w-full text-left transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] min-h-[44px] ${
              !item.read ? "border-l-4 border-l-[var(--color-primary)]" : ""
            }`;

            const cardContent = (
              <>
                <div className="campus-notification-icon" aria-hidden="true">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[15px] font-semibold text-[var(--text-primary)] break-words">
                      {item.title}
                    </p>
                    {!item.read && (
                      <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-[var(--color-primary-light)] px-2.5 py-0.5 text-xs font-semibold text-[var(--color-primary)]">
                        <span
                          className="h-1.5 w-1.5 rounded-full bg-[var(--color-primary)]"
                          aria-hidden="true"
                        />
                        {t("inbox.new")}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-[var(--text-secondary)] break-words">
                    {item.body}
                  </p>
                  <div className="mt-2">
                    <time
                      dateTime={item.created_at}
                      title={formatFullTime(item.created_at)}
                      className="text-xs text-[var(--text-secondary)]"
                    >
                      {formatRelativeTime(item.created_at, t)}
                    </time>
                  </div>
                </div>
              </>
            );

            if (isInternal) {
              return (
                <Link
                  key={item.id}
                  href={item.link}
                  onClick={() => handleItemClick(item)}
                  data-testid={`notification-item-${item.id}`}
                  className={cardClasses}
                >
                  {cardContent}
                </Link>
              );
            }

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleItemClick(item)}
                data-testid={`notification-item-${item.id}`}
                className={cardClasses}
              >
                {cardContent}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

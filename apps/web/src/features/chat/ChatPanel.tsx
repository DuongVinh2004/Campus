import React, { useState, useRef, useEffect, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Bot,
  Copy,
  Check,
  ArrowUp,
  Square,
  RefreshCw,
  ArrowRight,
  GraduationCap,
  FileText,
  Calendar,
  Building2,
  ShieldCheck,
  AlertTriangle,
  PanelLeft,
  SquarePen,
  ChevronDown,
  PanelsTopLeft,
  MessageSquare,
} from "lucide-react";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { AnswerFeedback, type FeedbackRating } from "./AnswerFeedback";
import { FAILED_GUIDANCE, type AgentProgress } from "./sse";

export interface ChatCitation {
  id: string;
  index: number;
  title: string;
  page?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
  status?: "streaming" | "success" | "failed" | "abstained" | "unknown" | "stopped";
  responseClass?: string;
  citations?: ChatCitation[];
  agentProgress?: AgentProgress;
  blocks?: AssistantBlock[];
}

export type AssistantBlock =
  | { type: "steps"; items: string[] }
  | { type: "table"; columns: string[]; rows: string[][] }
  | { type: "status"; state: "pending" | "completed" | "interrupted" | "error"; text: string }
  | { type: "proposal"; title: string; changes: Array<{ field: string; before: string; after: string }>; action_authority: "none" }
  | { type: "navigation"; label: string; path: "/services" | "/my-requests" | "/privacy" | "/student/certificate" | "/student/complaint" | "/staff"; audience: "student" | "staff" };

export function AssistantContent({ content, blocks = [], audience, components }: {
  content: string; blocks?: AssistantBlock[]; audience?: "student" | "staff"; components?: Components;
}) {
  const text = (value: unknown): value is string => typeof value === "string" && value.length <= 4000;
  const safe = (Array.isArray(blocks) ? blocks : []).slice(0, 12).filter(block => block && (
    block.type === "steps" ? Array.isArray(block.items) && block.items.length <= 20 && block.items.every(text)
      : block.type === "table" ? Array.isArray(block.columns) && block.columns.length <= 12 && block.columns.every(text) && Array.isArray(block.rows) && block.rows.length <= 100 && block.rows.every(row => Array.isArray(row) && row.length === block.columns.length && row.every(text))
        : block.type === "status" ? ["pending", "completed", "interrupted", "error"].includes(block.state) && text(block.text)
          : block.type === "proposal" ? block.action_authority === "none" && text(block.title) && Array.isArray(block.changes) && block.changes.length <= 30 && block.changes.every(change => text(change.field) && text(change.before) && text(change.after))
            : block.type === "navigation" && block.audience === audience && text(block.label) && (audience === "student" ? ["/services", "/my-requests", "/privacy", "/student/certificate", "/student/complaint"] : ["/staff", "/privacy"]).includes(block.path)));
  return <div className="min-w-0 break-words text-sm leading-7">
    <ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={{ ...STATIC_MARKDOWN_COMPONENTS, ...components,
      img: ({ alt }) => <span>{alt || "Hình ảnh không được tải tự động"}</span>,
    }}>{content}</ReactMarkdown>
    {safe.map((block, index) => <div key={index} className="my-3">{block.type === "steps" ? <ol className="list-decimal pl-5">{block.items.map((item, i) => <li key={i}>{item}</li>)}</ol>
      : block.type === "table" ? <div className="overflow-x-auto"><table className="min-w-full"><thead><tr>{block.columns.map((cell, i) => <th key={i} className="p-2 text-left">{cell}</th>)}</tr></thead><tbody>{block.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j} className="border-t p-2">{cell}</td>)}</tr>)}</tbody></table></div>
        : block.type === "status" ? <p role="status">{({ pending: "Đang chờ", completed: "Hoàn tất", interrupted: "Gián đoạn", error: "Lỗi" })[block.state]} · {block.text}</p>
          : block.type === "proposal" ? <div className="rounded-xl border p-3"><p className="font-semibold">{block.title} · Chưa áp dụng</p>{block.changes.map((change, i) => <p key={i}>{change.field}: {change.before} → {change.after}</p>)}</div>
            : <a href={block.path} className="inline-flex min-h-11 items-center rounded-lg border px-3">{block.label}</a>}</div>)}
  </div>;
}

export interface ChatPanelProps {
  messages?: ChatMessage[];
  isStreaming?: boolean;
  onSendMessage?: (content: string) => void;
  onStopStreaming?: () => void;
  onRetry?: (messageId: string) => void;
  onHandover?: () => void;
  onCitationClick?: (citationId: string) => void;
  onFeedbackSubmit?: (answerId: string, rating: FeedbackRating) => Promise<void> | void;
  onClearMessages?: () => void;
  citationCount?: number;
  onOpenCitations?: () => void;
  historyContent?: ReactNode;
  headerActions?: ReactNode;
  hideHeader?: boolean;
  chatContext?: ReactNode;
  onComposerTools?: () => void;
  onComposerSettings?: () => void;
  onOpenHistory?: () => void;
  composerValue?: string;
  onComposerChange?: (value: string) => void;
  disabled?: boolean;
  audience?: "student" | "staff";
  initialSidebarOpen?: boolean;
}

interface PromptCardItem {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
  prompt: string;
  iconBg: string;
  iconColor: string;
  iconRing: string;
}

const PROMPT_CARDS: PromptCardItem[] = [
  {
    icon: GraduationCap,
    title: "Điều kiện xét học bổng",
    desc: "Kết quả học tập, điểm rèn luyện và điều kiện xét",
    prompt: "Điều kiện xét học bổng",
    iconBg: "bg-[#FF8C00]/15 dark:bg-[#FF8C00]/25",
    iconColor: "text-[#FF8C00]",
    iconRing: "ring-[#FF8C00]/30",
  },
  {
    icon: FileText,
    title: "Thủ tục xin cấp bảng điểm",
    desc: "Đăng ký qua Một cửa và nhận bảng điểm",
    prompt: "Thủ tục xin cấp bảng điểm",
    iconBg: "bg-[#155E63]/15 dark:bg-[#155E63]/25",
    iconColor: "text-[#155E63]",
    iconRing: "ring-[#155E63]/30",
  },
  {
    icon: Calendar,
    title: "Quy chế hoãn thi học kỳ",
    desc: "Vắng thi có lý do chính đáng và cách gửi đơn",
    prompt: "Quy chế hoãn thi học kỳ",
    iconBg: "bg-[#008080]/15 dark:bg-[#008080]/25",
    iconColor: "text-[#008080]",
    iconRing: "ring-[#008080]/30",
  },
  {
    icon: Building2,
    title: "Quy chế chuyển ngành",
    desc: "Đối tượng được chuyển ngành và thẩm quyền xét duyệt",
    prompt: "Quy chế chuyển ngành",
    iconBg: "bg-[#155E63]/15 dark:bg-[#155E63]/25",
    iconColor: "text-[#155E63]",
    iconRing: "ring-[#155E63]/30",
  },
];

const QUICK_TOPICS = [
  "Tư vấn quy chế & học vụ HUCE",
  "Điều kiện xét học bổng kỳ này",
  "Thủ tục xin cấp bảng điểm Một cửa",
  "Quy chế hoãn thi học kỳ",
  "Tra cứu phòng tự học thư viện",
];
const OPERATIONAL_PROMPTS = [
  { title: "Học phí theo khóa và chương trình", prompt: "Tôi cần tra học phí CNTT theo khóa và chương trình" },
  { title: "QĐ 2114: bảo vệ tài khoản", prompt: "Theo Quyết định 2114, người dùng cần bảo vệ tài khoản thế nào?" },
];

function displayText(text: string): string {
  return text.replace(/\[CIT-(\d{3})\]/g, (_, number: string) => `[${Number(number)}]`);
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

function CodeBlock({ children, language }: { children: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const success = await copyToClipboard(children);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-950 text-slate-200 font-mono text-xs shadow-md">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px]">
        <span className="font-semibold uppercase tracking-wider">{language || "mã nguồn"}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition-colors cursor-pointer"
          aria-label={copied ? "Đã sao chép mã" : "Sao chép mã"}
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? "Đã sao chép" : "Sao chép mã"}</span>
        </button>
      </div>
      <div className="p-4 overflow-x-auto">
        <pre className="m-0 leading-relaxed font-mono">
          <code>{children}</code>
        </pre>
      </div>
    </div>
  );
}

function ActionSuggestions({ content }: { content: string }) {
  const contentLower = content.toLowerCase();
  const isProcedural =
    contentLower.includes("một cửa") ||
    contentLower.includes("motcua.huce.edu.vn");
  const isSchedule =
    contentLower.includes("lịch thi") ||
    contentLower.includes("thời khóa biểu") ||
    contentLower.includes("ca thi") ||
    contentLower.includes("tiết");
  const isRoom =
    contentLower.includes("thư viện") ||
    contentLower.includes("phòng học") ||
    contentLower.includes("tự học");

  if (!isProcedural && !isSchedule && !isRoom) return null;

  return (
    <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800 flex flex-col gap-2">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
        <span>Gợi ý hành động:</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {isProcedural && (
          <a
            href="https://motcua.huce.edu.vn"
            target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-slate-850 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 text-slate-700 hover:text-emerald-700 dark:text-slate-200 dark:hover:text-emerald-300 border border-slate-200 dark:border-slate-700/80 text-xs font-medium transition-all group shadow-2xs"
          >
            <span>📝</span>
            <span>Nộp hồ sơ Một cửa trực tuyến</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
          </a>
        )}
        {isSchedule && (
          <a
            href="https://sinhvien.huce.edu.vn"
            target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-slate-850 hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 hover:text-blue-700 dark:text-slate-200 dark:hover:text-blue-300 border border-slate-200 dark:border-slate-700/80 text-xs font-medium transition-all group shadow-2xs"
          >
            <span>📅</span>
            <span>Xem thời khóa biểu & lịch thi</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
          </a>
        )}
        {isRoom && (
          <a
            href="https://thuvien.huce.edu.vn/introduction.aspx?contentid=1191&mnuid=164"
            target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-slate-850 hover:bg-purple-50 dark:hover:bg-purple-950/40 text-slate-700 hover:text-purple-700 dark:text-slate-200 dark:hover:text-purple-300 border border-slate-200 dark:border-slate-700/80 text-xs font-medium transition-all group shadow-2xs"
          >
            <span>🏢</span>
            <span>Thông tin thư viện & phòng tự học</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
          </a>
        )}
      </div>
    </div>
  );
}

const STATIC_MARKDOWN_COMPONENTS: Components = {
  h1: ({ children }: { children?: ReactNode }) => (
    <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-4 mb-2">
      {children}
    </h1>
  ),
  h2: ({ children }: { children?: ReactNode }) => (
    <h2 className="text-lg sm:text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-3 mb-2">
      {children}
    </h2>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h3 className="text-base sm:text-lg font-semibold text-slate-900 dark:text-slate-100 mt-2.5 mb-1.5">
      {children}
    </h3>
  ),
  p: ({ children }: { children?: ReactNode }) => (
    <p className="mb-3 leading-[1.75] text-slate-800 dark:text-slate-200 last:mb-0">
      {children}
    </p>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="list-disc pl-5 mb-3 space-y-1 text-slate-800 dark:text-slate-200">
      {children}
    </ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="list-decimal pl-5 mb-3 space-y-1 text-slate-800 dark:text-slate-200">
      {children}
    </ol>
  ),
  li: ({ children }: { children?: ReactNode }) => (
    <li className="leading-[1.75]">
      {children}
    </li>
  ),
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote className="border-l-3 border-blue-500 dark:border-blue-400 bg-slate-50 dark:bg-slate-900/60 pl-4 py-2 my-3 rounded-r-lg italic text-slate-700 dark:text-slate-300">
      {children}
    </blockquote>
  ),
  table: ({ children }: { children?: ReactNode }) => (
    <div className="overflow-x-auto my-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs">
      <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800 text-xs sm:text-sm">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }: { children?: ReactNode }) => (
    <thead className="bg-slate-100 dark:bg-slate-850 text-slate-900 dark:text-slate-100 border-b border-slate-200 dark:border-slate-800">
      {children}
    </thead>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th className="px-3.5 py-2.5 font-semibold text-left text-slate-900 dark:text-slate-100">
      {children}
    </th>
  ),
  tbody: ({ children }: { children?: ReactNode }) => (
    <tbody className="divide-y divide-slate-200/80 dark:divide-slate-800 bg-white/60 dark:bg-slate-900/60">
      {children}
    </tbody>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="px-3.5 py-2 text-slate-800 dark:text-slate-200">
      {children}
    </td>
  ),
  code: ({ className, children, ...props }: React.ComponentPropsWithoutRef<"code">) => {
    const match = /language-(\w+)/.exec(className || "");
    const isBlock = match || String(children).includes("\n");
    if (!isBlock) {
      return (
        <code
          className="bg-slate-100 dark:bg-slate-800 text-blue-600 dark:text-blue-400 border border-slate-200/80 dark:border-slate-700/60 px-1.5 py-0.5 rounded font-mono text-xs font-semibold"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <CodeBlock language={match ? match[1] : undefined}>
        {String(children).replace(/\n$/, "")}
      </CodeBlock>
    );
  },
  a: ({ href, children }: React.ComponentPropsWithoutRef<"a">) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 dark:text-blue-400 underline underline-offset-2 hover:opacity-80 transition-opacity font-medium"
    >
      {children}
    </a>
  ),
};

export function ChatPanel({
  messages = [],
  isStreaming = false,
  onSendMessage,
  onStopStreaming,
  onRetry,
  onHandover,
  onCitationClick,
  onFeedbackSubmit,
  onClearMessages,
  citationCount,
  onOpenCitations,
  historyContent, headerActions, hideHeader = false, chatContext, onComposerTools, onComposerSettings, onOpenHistory, composerValue, onComposerChange, disabled = false, audience, initialSidebarOpen = true,
}: ChatPanelProps) {
  const operational = process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true";
  const [input, setInput] = useState("");
  const [isMobile, setIsMobile] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(initialSidebarOpen);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  const handleScroll = () => {
    if (!scrollAreaRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollAreaRef.current;
    const distanceToBottom = scrollHeight - (scrollTop + clientHeight);
    isNearBottomRef.current = distanceToBottom < 80;
  };

  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      setIsMobile(window.innerWidth < 768);
      if (window.innerWidth < 768) setIsSidebarOpen(false);
      return;
    }
    const media = window.matchMedia("(max-width: 767px)");
    const update = () => { setIsMobile(media.matches); if (media.matches) setIsSidebarOpen(false); };
    update(); media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (messages.length === 0) {
      if (scrollAreaRef.current) scrollAreaRef.current.scrollTop = 0;
      return;
    }
    if (scrollAreaRef.current && isNearBottomRef.current) {
      if (typeof scrollAreaRef.current.scrollTo === "function") {
        scrollAreaRef.current.scrollTo({
          top: scrollAreaRef.current.scrollHeight,
          behavior: "smooth",
        });
      } else {
        scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
      }
    }
  }, [messages, isStreaming]);

  const handleSubmit = (e?: FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = (composerValue ?? input).trim();
    if (!trimmed || isStreaming || disabled) return;
    isNearBottomRef.current = true;
    onSendMessage?.(trimmed);
    if (!onComposerChange) setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    onComposerChange?.(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  };

  const handlePromptClick = (promptText: string) => {
    if (isStreaming || disabled) return;
    onSendMessage?.(promptText);
  };

  const handleCopyMessage = async (content: string, id: string) => {
    const success = await copyToClipboard(displayText(content));
    if (success) {
      setCopiedMessageId(id);
      setTimeout(() => setCopiedMessageId(null), 2000);
    }
  };

  const historySidebar = (
        <aside
          role="complementary"
          aria-label="Thanh bên cuộc trò chuyện"
          className="campus-chat-history fixed md:static inset-y-0 left-0 w-[260px] h-full shrink-0 bg-[var(--surface-card)] dark:bg-[var(--surface-card)] border-r border-slate-200 dark:border-slate-800 flex flex-col justify-between p-3 select-none transition-all z-40 md:z-20 shadow-xl md:shadow-none"
        >
          <div className="flex-1 min-h-0 flex flex-col gap-2">
            {/* Sidebar Top: Logo + Toggle */}
            <div className="flex items-center justify-between mb-1 px-1 shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-blue-600 to-blue-700 text-white flex items-center justify-center font-bold text-xs shadow-xs">
                  C
                </div>
                <span id="chat-history-title" className="font-semibold text-sm tracking-tight text-slate-900 dark:text-slate-100">
                  Trợ lý học vụ
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsSidebarOpen(false)}
                title="Đóng thanh bên"
                aria-label="Đóng thanh bên"
                className="p-1.5 rounded-lg hover:bg-slate-200/70 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors cursor-pointer"
              >
                <PanelLeft className="w-4 h-4" />
              </button>
            </div>

            {/* New Chat Button */}
            <button
              type="button"
              onClick={onClearMessages}
              className="flex items-center gap-2.5 w-full px-3 py-2.5 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-sm font-medium transition-colors cursor-pointer text-slate-800 dark:text-slate-200 shadow-2xs shrink-0"
            >
              <SquarePen className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <span>Đoạn chat mới</span>
            </button>

            {/* Scrollable Conversation History */}
            <div className="flex-1 overflow-y-auto space-y-1 pt-2">
              {historyContent}
              <span className="text-[11px] font-semibold text-slate-400 dark:text-slate-500 px-3 uppercase tracking-wider block mb-1">
                Chủ đề thường hỏi
              </span>
              <div className="space-y-0.5">
                {(operational ? OPERATIONAL_PROMPTS.map(item => item.prompt) : QUICK_TOPICS).map((title, idx) => (
                  <button
                    key={title}
                    type="button"
                    onClick={() => handlePromptClick(title)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs text-left transition-colors cursor-pointer truncate ${
                      idx === 0
                        ? "bg-slate-200/70 dark:bg-slate-800 font-semibold text-slate-900 dark:text-slate-100"
                        : "hover:bg-slate-200/50 dark:hover:bg-slate-800/50 text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-60" />
                    <span className="truncate">{title}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar Footer: Student Profile */}
          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 shrink-0">
            <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-xl hover:bg-slate-200/60 dark:hover:bg-slate-800/60 transition-colors">
              <div className="w-7 h-7 rounded-full bg-blue-600 text-white font-semibold flex items-center justify-center text-xs shrink-0 shadow-xs">
                AI
              </div>
              <div className="flex flex-col min-w-0">
                <span className="font-semibold text-slate-800 dark:text-slate-200 text-xs truncate">Hỏi đáp học vụ HUCE</span>
                <span className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  {operational ? "Phạm vi phục vụ giới hạn" : "Trực tuyến"}
                </span>
              </div>
            </div>
          </div>
        </aside>
  );

  return (
    <div data-empty={messages.length === 0} className="campus-chat-panel flex h-full w-full bg-slate-50/60 dark:bg-slate-950 overflow-hidden text-slate-900 dark:text-slate-100">
      {isSidebarOpen && (isMobile ? <AccessibleDialog open onClose={() => setIsSidebarOpen(false)} labelledBy="chat-history-title" className="campus-history-dialog">{historySidebar}</AccessibleDialog> : historySidebar)}

      {/* Main Conversation Container (100% full height) */}
      <div className="campus-chat-main flex-1 flex flex-col h-full min-w-0 bg-slate-50/60 dark:bg-slate-950 relative overflow-hidden">
        {chatContext && <div className="campus-context-anchor">{chatContext}</div>}
        {/* Modern Top Navigation Bar */}
        {!hideHeader && <div className="campus-chat-header h-13 px-4 flex items-center justify-between border-b border-slate-200/80 dark:border-slate-800/80 shrink-0 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md z-10">
          <div className="flex items-center gap-2">
            {!isSidebarOpen && (
              <>
                <button
                  type="button"
                  onClick={onOpenHistory || (() => setIsSidebarOpen(true))}
                  title={onOpenHistory ? "Lịch sử" : "Mở thanh bên"}
                  aria-label={onOpenHistory ? "Lịch sử" : "Mở thanh bên"}
                  className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
                >
                  <PanelLeft className="w-4 h-4" />
                </button>
                {onClearMessages && (
                  <button
                    type="button"
                    onClick={onClearMessages}
                    title="Đoạn chat mới"
                    aria-label="Đoạn chat mới"
                    className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
                  >
                    <SquarePen className="w-4 h-4" />
                  </button>
                )}
              </>
            )}

            {/* Model Pill */}
            <div className={`items-center gap-1.5 px-3 py-1.5 rounded-xl whitespace-nowrap shrink-0 ${headerActions ? "hidden sm:flex" : "flex"}`}>
              <span className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
                Trợ lý học vụ
              </span>
              <span className="text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/60 px-1.5 py-0.5 rounded-md">
                HUCE
              </span>
            </div>
          </div>

          {/* AI Disclosure & Actions */}
          <div className="flex items-center gap-2">
            {!headerActions && <div className="hidden md:inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-xs font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span>Trợ lý AI Campus 24/7</span>
              <span className="sr-only">Cổng thông tin & Trợ lý học vụ số — Trường Đại học Xây dựng Hà Nội</span>
            </div>}
            {headerActions}

            {Boolean(citationCount && citationCount > 0 && onOpenCitations) && (
              <button
                type="button"
                onClick={onOpenCitations}
                aria-label={`Xem ${citationCount} nguồn trích dẫn`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-blue-50 dark:hover:bg-slate-700 text-xs font-semibold text-blue-700 dark:text-blue-300 border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer shadow-2xs"
              >
                <FileText className="w-3.5 h-3.5" />
                <span className={headerActions ? "hidden sm:inline" : undefined}>Nguồn trích dẫn</span>
                <span className="bg-blue-600 text-white rounded-full px-1.5 py-0.5 text-[10px] font-bold">
                  {citationCount}
                </span>
              </button>
            )}

            {onHandover && (
              <button
                type="button"
                onClick={onHandover}
                aria-label="Gặp cán bộ"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer shadow-2xs"
              >
                <span>Gặp cán bộ</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        }
        {/* Messages Scroll Area */}
        <div
          ref={scrollAreaRef}
          onScroll={handleScroll}
          role="log"
          aria-label="Lịch sử đối thoại"
          className="campus-chat-log flex-1 overflow-y-auto w-full px-4 flex flex-col"
        >
          <div className="max-w-3xl mx-auto w-full flex-1 flex flex-col justify-center py-6">
            {/* Empty Welcome State */}
            {messages.length === 0 && (
              <div className="campus-chat-welcome my-auto flex flex-col items-center text-center py-6 max-w-2xl mx-auto w-full">
                <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-slate-800 dark:text-slate-100 mb-2">
                  Bạn cần hỗ trợ gì?
                </h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md leading-relaxed mb-6">
                  Hỏi về học vụ HUCE. Trợ lý sử dụng nguồn hiện có và trích dẫn khi tìm được căn cứ.
                </p>

                {/* 2x2 Clean Prompt Cards */}
                <div className="campus-prompt-suggestions">
                  {(operational ? OPERATIONAL_PROMPTS : PROMPT_CARDS).map((promptCard) => {
                    return (
                      <button
                        key={promptCard.prompt}
                        type="button"
                        aria-label={promptCard.title}
                        disabled={disabled}
                        onClick={() => handlePromptClick(promptCard.prompt)}
                        className="campus-prompt-chip"
                      >
                        {promptCard.title}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Transcript Messages */}
            {messages.length > 0 && (
              <div className="space-y-6">
                {messages.map((message) => {
                  const isUser = message.role === "user";
                  const isSystem = message.role === "system";
                  const isFailed = message.status === "failed" || message.status === "unknown";
                  const isAbstained = message.status === "abstained";
                  const isProvisional = message.status === "streaming";
                  const isStopped = message.status === "stopped";

                  if (isSystem) {
                    return (
                      <div
                        key={message.id}
                        role="status"
                        className="self-center max-w-[90%] px-4 py-2.5 rounded-xl bg-rose-50 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 text-xs font-medium flex items-center gap-2 border border-rose-200 dark:border-rose-900"
                      >
                        <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600 dark:text-rose-400" />
                        <span>{message.content}</span>
                      </div>
                    );
                  }

                  if (isUser) {
                    return (
                      <article
                        key={message.id}
                        role="article"
                        aria-label={`Tin nhắn của bạn: ${message.content.slice(0, 30)}...`}
                        className="flex flex-col items-end w-full"
                      >
                        <div className="flex items-center gap-2 mb-1.5 text-xs font-semibold text-slate-400 dark:text-slate-500">
                          <span>Bạn</span>
                          {message.timestamp && <span className="text-[11px] font-normal">• {message.timestamp}</span>}
                        </div>
                        <div className="campus-chat-user-bubble max-w-[85%] sm:max-w-[70%] px-5 py-3 rounded-2xl rounded-tr-xs bg-[#155E63] text-white text-[15px] leading-relaxed break-words shadow-sm">
                          <p className="m-0 whitespace-pre-wrap">{message.content}</p>
                        </div>
                      </article>
                    );
                  }

                  return (
                    <article
                      key={message.id}
                      role="article"
                      aria-label={`Tin nhắn của trợ lý: ${message.content.slice(0, 30)}...`}
                      className="campus-assistant-message flex flex-col items-start w-full"
                    >
                      {/* Assistant Header */}
                      {isProvisional && message.agentProgress && (
                        <div role="status" aria-live="polite" className="mb-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
                          <p>{({ planning: "Đang xác định thông tin cần tra cứu", researching: "Đang tìm và đọc nguồn", verifying: "Đang kiểm chứng nguồn và điều kiện", reviewing: "Đang kiểm tra phần thông tin còn thiếu", synthesizing: "Đang tổng hợp phần có căn cứ", waiting_user: "Cần bạn bổ sung thông tin", failed: "Chưa hoàn tất xử lý", completed: "Đã hoàn tất xử lý", cancelled: "Đã dừng xử lý", partial: "Mới xác minh được một phần", interrupted: "Xử lý bị gián đoạn; công việc đã lưu được giữ", uncertain: "Chưa xác định kết quả; cần đọc receipt trước khi tiếp tục" })[message.agentProgress.phase]}</p>
                          {message.agentProgress.tasks.length > 0 && <p className="mt-1 opacity-80">{message.agentProgress.tasks.filter(task => ["succeeded", "partial"].includes(task.status)).length}/{message.agentProgress.tasks.length} phần đã tra cứu · {message.agentProgress.sourceCount} nguồn đã đọc</p>}
                        </div>
                      )}
                      <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-slate-600 dark:text-slate-400">
                        <div className="w-7 h-7 rounded-md bg-[#155E63] text-white flex items-center justify-center shrink-0 shadow-xs">
                          <Bot className="w-4 h-4" />
                        </div>
                        <span className="text-slate-900 dark:text-slate-200 font-semibold">Trợ lý AI</span>
                        {message.timestamp && <span className="text-[11px] font-normal text-slate-400">• {message.timestamp}</span>}
                        {isProvisional && (
                          <span role="status" className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 px-2 py-0.5 rounded-full border border-blue-200 dark:border-blue-800">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
                            • Nội dung tạm — đang kiểm tra
                          </span>
                        )}
                        {isAbstained && (
                          <span role="status" className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/50 px-2 py-0.5 rounded-full border border-amber-200 dark:border-amber-800">
                            {message.responseClass === "clarification_request" ? "• Hỏi làm rõ" : "• Chưa đủ căn cứ"}
                          </span>
                        )}
                        {message.responseClass === "partial_answer" && <span role="status" className="text-xs text-amber-700 dark:text-amber-300">• Có căn cứ cho một phần</span>}
                        {message.status === "unknown" && (
                          <span role="status" className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/50 px-2 py-0.5 rounded-full border border-rose-200 dark:border-rose-800">
                            • UNKNOWN
                          </span>
                        )}
                        {isStopped && (
                          <span role="status" className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full border border-slate-200 dark:border-slate-700">
                            • Đã dừng — chưa xác nhận
                          </span>
                        )}
                      </div>

                      {/* Assistant Body */}
                      <div className="w-full pl-9 pr-2">
                        {isFailed || message.status === "unknown" ? (
                          <div className="p-4 rounded-2xl bg-rose-50/80 text-rose-900 dark:bg-rose-950/50 dark:text-rose-200 border border-rose-200 dark:border-rose-900/80 text-sm shadow-xs">
                            <p className="m-0 leading-relaxed">{message.status === "unknown" ? FAILED_GUIDANCE : message.content}</p>
                          </div>
                        ) : (
                          <div className="prose-content text-[15px] sm:text-[16px] leading-[1.75] text-slate-800 dark:text-slate-200">
                            <AssistantContent content={displayText(message.content)} blocks={message.blocks} audience={audience} />

                            {isProvisional && (
                              <span className="inline-block w-2 h-4 ml-0.5 bg-blue-600 dark:bg-blue-400 animate-pulse align-middle" />
                            )}
                          </div>
                        )}

                        {/* Citations Preview Pills */}
                        {!isProvisional && !isFailed && !isStopped && message.citations && message.citations.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-1.5 items-center">
                            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 mr-1 flex items-center gap-1">
                              <FileText className="w-3 h-3 text-blue-600 dark:text-blue-400" /> Nguồn:
                            </span>
                            {message.citations.map((citation) => (
                              <button
                                key={citation.id}
                                type="button"
                                onClick={() => onCitationClick?.(citation.id)}
                                aria-label={`Xem nguồn trích dẫn [${citation.index}]: ${citation.title}`}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 hover:bg-blue-50 dark:bg-slate-850 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700/80 text-xs font-medium transition-colors cursor-pointer shadow-2xs"
                              >
                                <span className="font-bold text-blue-600 dark:text-blue-400">[{citation.index}]</span>
                                <span className="truncate max-w-[220px]">{citation.title}</span>
                              </button>
                            ))}
                          </div>
                        )}

                        {/* Agentic Actions */}
                        {!operational && !isFailed && !isAbstained && !isProvisional && !isStopped && (
                          <span className="sr-only">Điều hướng chỉ xuất hiện khi có schema hợp lệ.</span>
                        )}

                        {/* Recovery & Action Toolbar */}
                        {isFailed && onRetry && (
                          <div className="mt-3 flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => onRetry(message.id)}
                              aria-label="Thử lại"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-rose-100 hover:bg-rose-200 dark:bg-rose-950/80 dark:hover:bg-rose-900 text-rose-800 dark:text-rose-200 text-xs font-semibold transition-colors cursor-pointer"
                            >
                              <RefreshCw className="w-3.5 h-3.5" />
                              <span>Thử lại</span>
                            </button>
                            <span className="text-xs text-slate-500 dark:text-slate-400">
                              Chưa thể hoàn tất câu trả lời
                            </span>
                          </div>
                        )}

                        {isAbstained && onHandover && (
                          <div className="mt-3 flex items-center gap-2">
                            <button
                              type="button"
                              onClick={onHandover}
                              aria-label="Chuyển cán bộ"
                              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer shadow-2xs"
                            >
                              <span>Chuyển cán bộ</span>
                              <ArrowRight className="w-3.5 h-3.5" />
                            </button>
                            <span className="text-xs text-slate-500 dark:text-slate-400">
                              Chuyển tiếp câu hỏi tới một cửa số
                            </span>
                          </div>
                        )}

                        {/* Next steps when the assistant could not ground an answer */}
                        {isAbstained && message.responseClass !== "clarification_request" && !isProvisional && (
                          <div role="note" className="campus-abstain-help mt-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 p-3 text-sm text-slate-600 dark:text-slate-300">
                            <p className="m-0 font-medium text-slate-800 dark:text-slate-100">Bạn có thể thử</p>
                            <ul className="m-0 mt-1 list-disc pl-5 leading-relaxed">
                              <li>Hỏi cụ thể hơn: nêu khóa hoặc năm học, ngành, tên văn bản hay mã học phần.</li>
                              <li>Tách câu hỏi nhiều ý thành từng câu riêng.</li>
                              <li>Với việc cần kết quả chính thức, liên hệ Phòng Đào tạo HUCE.</li>
                            </ul>
                            {operational && (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {OPERATIONAL_PROMPTS.map(item => (
                                  <button key={item.prompt} type="button" disabled={isStreaming || disabled} onClick={() => handlePromptClick(item.prompt)}
                                    className="rounded-full border border-slate-200 dark:border-slate-700 px-3 py-1 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 cursor-pointer">
                                    {item.title}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Bottom Actions Toolbar */}
                        {!isFailed && !isAbstained && !isProvisional && !isStopped && (
                          <div className="mt-3 flex items-center gap-2 text-slate-400 dark:text-slate-500">
                            <button
                              type="button"
                              onClick={() => handleCopyMessage(message.content, message.id)}
                              className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors cursor-pointer"
                              aria-label={copiedMessageId === message.id ? "Đã sao chép câu trả lời" : "Sao chép câu trả lời"}
                              title={copiedMessageId === message.id ? "Đã sao chép" : "Sao chép"}
                            >
                              {copiedMessageId === message.id ? (
                                <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                              ) : (
                                <Copy className="w-4 h-4" />
                              )}
                            </button>
                            {onFeedbackSubmit && <AnswerFeedback
                              answerId={message.id}
                              onFeedbackSubmit={onFeedbackSubmit}
                            />}
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}

            {/* Active Streaming Indicator */}
            {isStreaming && (
              <div
                role="status"
                aria-live="polite"
                className="flex items-center gap-3 pl-9 py-1 text-xs text-slate-500 dark:text-slate-400 mt-2"
              >
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600 dark:bg-blue-400" />
                </span>
                <span>Trợ lý đang trả lời...</span>
              </div>
            )}
          </div>
        </div>

        {/* Floating Bottom Composer */}
        <div className="campus-composer shrink-0 w-full px-4 pb-3 pt-1 bg-transparent z-10">
          <div className="max-w-3xl mx-auto w-full">
            <form
              onSubmit={handleSubmit}
              className="campus-composer-bar"
            >
              {onComposerTools && <button type="button" className="campus-composer-add" aria-label="Tiện ích học vụ" title="Tiện ích học vụ" onClick={onComposerTools}><PanelsTopLeft size={19} aria-hidden="true" /></button>}
              <label htmlFor="chat-input" className="sr-only">
                Đặt câu hỏi
              </label>
              <textarea
                ref={textareaRef}
                id="chat-input"
                value={composerValue ?? input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                aria-label="Đặt câu hỏi"
                placeholder="Hỏi Campus 24/7"
                rows={1}
                className="w-full max-h-44 min-h-[44px] bg-transparent text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 text-[15px] leading-relaxed resize-none focus:outline-none border-0 p-0"
              />

              {onComposerSettings && <button type="button" className="campus-composer-settings" aria-label="Tùy chọn trả lời" title="Tùy chọn trả lời" onClick={onComposerSettings}><span>Tùy chọn</span><ChevronDown size={14} aria-hidden="true" /></button>}
                  {isStreaming ? (
                    <button
                      type="button"
                      onClick={onStopStreaming}
                      aria-label="Dừng trả lời"
                      title="Dừng trả lời"
                      className="campus-composer-send"
                    >
                      <Square className="w-3.5 h-3.5 fill-current" />
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={disabled || !(composerValue ?? input).trim()}
                      aria-label="Gửi"
                      title="Gửi"
                      className="campus-composer-send"
                    >
                      <ArrowUp className="w-5 h-5" aria-hidden="true" />
                    </button>
                  )}
            </form>

            <p className="mt-1.5 mb-1 text-center text-[11px] text-slate-400 dark:text-slate-500">
              Campus 24/7 AI có thể mắc lỗi. Hãy kiểm tra các thông tin quan trọng.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

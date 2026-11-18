export function formatDate(input: string | Date | undefined, timeZone?: string): string {
  if (!input) return "Không xác định";

  const safeFormat = (date: Date): string => {
    try {
      return new Intl.DateTimeFormat("vi-VN", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit",
        timeZone
      }).format(date);
    } catch (e) {
      if (e instanceof RangeError) {
        // Fallback for invalid timezone
        return new Intl.DateTimeFormat("vi-VN", {
          day: "2-digit", month: "2-digit", year: "numeric",
          hour: "2-digit", minute: "2-digit"
        }).format(date) + " (TZ Lỗi)";
      }
      return "Ngày không hợp lệ";
    }
  };

  if (input instanceof Date) {
    if (isNaN(input.getTime())) return "Ngày không hợp lệ";
    return safeFormat(input);
  }

  const str = input.trim();

  // Existing valid labels
  if (str === "Vừa xong" || /^\d{2}:\d{2} Hôm nay$/.test(str)) {
    return str;
  }

  // Date-only YYYY-MM-DD
  const dateOnlyMatch = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dateOnlyMatch) {
    const year = parseInt(dateOnlyMatch[1], 10);
    const month = parseInt(dateOnlyMatch[2], 10);
    const day = parseInt(dateOnlyMatch[3], 10);
    const d = new Date(year, month - 1, day);
    if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) {
      return "Ngày không hợp lệ";
    }
    return `${dateOnlyMatch[3]}/${dateOnlyMatch[2]}/${dateOnlyMatch[1]}`;
  }

  // Datetime with offset/Z
  const offsetRegex = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2}|[+-]\d{4})$/;
  const offsetMatch = str.match(offsetRegex);
  if (offsetMatch) {
    const year = parseInt(offsetMatch[1], 10);
    const month = parseInt(offsetMatch[2], 10);
    const day = parseInt(offsetMatch[3], 10);
    const hour = parseInt(offsetMatch[4], 10);
    const minute = parseInt(offsetMatch[5], 10);
    const second = offsetMatch[6] ? parseInt(offsetMatch[6], 10) : 0;

    if (hour > 23 || minute > 59 || second > 59) return "Ngày không hợp lệ";
    const d = new Date(year, month - 1, day);
    if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) {
      return "Ngày không hợp lệ";
    }

    const date = new Date(str);
    if (isNaN(date.getTime())) return "Ngày không hợp lệ";
    return safeFormat(date);
  }

  // Datetime without offset -> treat as local
  const localRegex = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?$/;
  const localMatch = str.match(localRegex);
  if (localMatch) {
    const year = parseInt(localMatch[1], 10);
    const month = parseInt(localMatch[2], 10);
    const day = parseInt(localMatch[3], 10);
    const hour = parseInt(localMatch[4], 10);
    const minute = parseInt(localMatch[5], 10);
    const second = localMatch[6] ? parseInt(localMatch[6], 10) : 0;

    if (hour > 23 || minute > 59 || second > 59) return "Ngày không hợp lệ";
    const d = new Date(year, month - 1, day);
    if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) {
      return "Ngày không hợp lệ";
    }
    return `${localMatch[4]}:${localMatch[5]} ${localMatch[3]}/${localMatch[2]}/${localMatch[1]}`;
  }

  // Do not automatically parse unknown strings
  return "Ngày không hợp lệ";
}

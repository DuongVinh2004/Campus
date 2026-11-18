/** Vietnamese labels for ticket form fields. A key with no label is shown as it is, never hidden. */
export const FIELD_LABELS: Record<string, string> = {
  purpose: "Mục đích sử dụng",
  recipient: "Đơn vị nhận",
  course: "Học phần",
  reason: "Nội dung / lý do",
};

export function fieldLabel(key: string): string {
  return FIELD_LABELS[key] ?? key;
}

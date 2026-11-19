import type { StoredAttachment } from "./types";

const DATABASE = "campus247_attachments_v1";
const STORE = "files";
interface AttachmentRecord {
  id: string;
  ownerId: string;
  scope: string;
  blob: Blob;
}

export function validateAttachment(file: Pick<File, "name" | "size" | "type">): string {
  if (file.size <= 0 || file.size > 10 * 1024 * 1024 || !/\.(pdf|png|jpe?g)$/i.test(file.name)
    || !["application/pdf", "image/png", "image/jpeg"].includes(file.type)) {
    return "Chọn tệp PDF/PNG/JPG không rỗng, tối đa 10MB.";
  }
  return "";
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("Trình duyệt chưa cho phép lưu tệp. Hãy kiểm tra quyền lưu trữ rồi thử lại."));
      return;
    }
    const request = indexedDB.open(DATABASE, 1);
    let blocked = false;
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE, { keyPath: "id" });
    };
    request.onsuccess = () => {
      if (blocked) { request.result.close(); return; }
      request.result.onversionchange = () => request.result.close();
      resolve(request.result);
    };
    request.onerror = () => reject(new Error("Chưa mở được nơi lưu tệp trên thiết bị. Hãy thử lại."));
    request.onblocked = () => {
      blocked = true;
      reject(new Error("Hãy đóng các tab Campus 24/7 khác rồi thử lưu tệp lại."));
    };
  });
}

/** Save binary content before accepting a submission. Existing files are never replaced or removed. */
export async function saveLocalAttachments(ownerId: string, scope: string, groups: Record<string, File[]>): Promise<StoredAttachment[]> {
  if (!ownerId || !scope) throw new Error("Chưa xác định được tài khoản và hồ sơ để lưu tệp.");
  const entries = Object.entries(groups).flatMap(([field, files]) => {
    if (files.length > 5) throw new Error("Chọn tối đa 5 tệp cho mỗi mục đính kèm.");
    return files.map(file => ({ field, file }));
  });
  for (const { file } of entries) {
    const error = validateAttachment(file);
    if (error) throw new Error(error);
  }
  if (!entries.length) return [];
  const database = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = database.transaction(STORE, "readwrite");
      const store = transaction.objectStore(STORE);
      const attachments = entries.map(({ field, file }) => {
        const id = crypto.randomUUID();
        store.add({ id, ownerId, scope, blob: file } satisfies AttachmentRecord);
        return { id, name: file.name, size: file.size, contentType: file.type, field };
      });
      transaction.oncomplete = () => resolve(attachments);
      transaction.onabort = () => reject(new Error("Chưa lưu được tệp. Kiểm tra dung lượng thiết bị và thử lại; tệp đang chọn vẫn được giữ."));
      transaction.onerror = () => { /* onabort reports the transaction failure. */ };
    });
  } finally { database.close(); }
}

export async function readLocalAttachment(ownerId: string, id: string): Promise<Blob> {
  if (!ownerId || !id) throw new Error("Chưa xác định được tệp cần mở.");
  const database = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = database.transaction(STORE, "readonly");
      const request = transaction.objectStore(STORE).get(id);
      request.onsuccess = () => {
        const record = request.result as AttachmentRecord | undefined;
        if (!record || record.ownerId !== ownerId || !(record.blob instanceof Blob)) {
          reject(new Error("Không tìm thấy tệp của tài khoản này trên thiết bị. Hãy đính kèm lại tệp gốc."));
        } else resolve(record.blob);
      };
      request.onerror = () => reject(new Error("Chưa đọc được tệp. Hãy thử lại."));
    });
  } finally { database.close(); }
}

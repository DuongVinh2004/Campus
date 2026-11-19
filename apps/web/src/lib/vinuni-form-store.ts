import { defaults, languages, visibleFields, type FormValues, type VinUniTask } from "./vinuni-forms";

export interface FormSubmission { ticketId: string; ticketCode: string }
export interface FormDraft {
  id: string; values: FormValues; stage: number; checked: string | null;
  revision: number; updatedAt: string; submission?: FormSubmission;
}
export interface FormChange {
  task: VinUniTask; draftId: string; revision: number; label: string;
  before: FormValues; after: FormValues;
}
interface Snapshot {
  certificate: FormDraft; complaint: FormDraft;
  archive: Array<{ task: VinUniTask; draft: FormDraft }>;
  pending: string[]; issue: string | null;
}
const fresh = (values: FormValues): FormDraft => ({ id: crypto.randomUUID(), values: { ...values }, stage: 0, checked: null, revision: 0, updatedAt: new Date().toISOString() });
function restore(value: unknown): FormDraft {
  if (!value || typeof value !== "object") throw new Error("Invalid draft");
  const d = value as Partial<FormDraft>;
  if (!d.values || Array.isArray(d.values) || typeof d.values !== "object" || !Object.values(d.values).every(v => typeof v === "string") ||
    ![0, 1, 2].includes(d.stage!) || !(d.checked === null || typeof d.checked === "string") ||
    (d.submission && (typeof d.submission.ticketId !== "string" || typeof d.submission.ticketCode !== "string"))) throw new Error("Invalid draft");
  return { ...fresh(d.values), ...d, id: typeof d.id === "string" ? d.id : crypto.randomUUID(),
    values: { ...d.values }, stage: d.stage!, checked: d.checked!, revision: Number.isSafeInteger(d.revision) && d.revision! >= 0 ? d.revision! : 0,
    updatedAt: typeof d.updatedAt === "string" ? d.updatedAt : new Date().toISOString() };
}

/** v2 has its own key; legacy data is read without modifying the original. */
export function createVinUniFormStore(key: string, legacyKey: string, seeds: Record<VinUniTask, FormValues>) {
  let snapshot: Snapshot = { certificate: fresh(seeds.certificate), complaint: fresh(seeds.complaint), archive: [], pending: [], issue: null };
  let preserveSaved = false;
  const files = new Map<string, Record<string, File[]>>();
  try {
    const current = localStorage.getItem(key);
    const saved = current ?? localStorage.getItem(legacyKey);
    if (saved) {
      const value = JSON.parse(saved);
      if (![1, 2].includes(value.version)) throw new Error("Unsupported draft");
      const archive = value.archive ?? [];
      if (!Array.isArray(archive)) throw new Error("Invalid archive");
      snapshot = { ...snapshot, certificate: restore(value.certificate), complaint: restore(value.complaint),
        archive: archive.map((entry: { task: VinUniTask; draft: unknown }) => {
          if (!["certificate", "complaint"].includes(entry.task)) throw new Error("Invalid task");
          return { task: entry.task, draft: restore(entry.draft) };
        }) };
    }
  } catch { preserveSaved = true; snapshot.issue = "Không đọc được bản nháp đã lưu. Dữ liệu cũ được giữ nguyên; thay đổi mới chỉ giữ trong phiên này."; }
  const listeners = new Set<() => void>();
  function publish(next: Snapshot) {
    snapshot = next;
    if (!preserveSaved) {
      try { localStorage.setItem(key, JSON.stringify({ version: 2, certificate: next.certificate, complaint: next.complaint, archive: next.archive })); snapshot = { ...next, issue: null }; }
      catch { snapshot = { ...next, issue: "Chưa lưu được bản nháp trên thiết bị. Hãy giữ trang này mở." }; }
    }
    listeners.forEach(fn => fn());
  }
  function editable(task: VinUniTask) { return !snapshot[task].submission && !snapshot.pending.includes(snapshot[task].id); }
  function normalized(task: VinUniTask, values: FormValues) {
    return task === "certificate" && values.documentType ? { ...values, language: languages(values.documentType)[0][0] } : values;
  }
  function update(task: VinUniTask, values: FormValues) {
    if (!editable(task)) return false;
    publish({ ...snapshot, [task]: { ...snapshot[task], values: { ...snapshot[task].values, ...normalized(task, values) }, checked: null,
      revision: snapshot[task].revision + 1, updatedAt: new Date().toISOString() } });
    return true;
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; },
    getFiles(task: VinUniTask) { return files.get(snapshot[task].id) ?? {}; },
    update,
    stage(task: VinUniTask, stage: number) { if (editable(task) && [0, 1, 2].includes(stage)) publish({ ...snapshot, [task]: { ...snapshot[task], stage } }); },
    check(task: VinUniTask) { if (editable(task)) publish({ ...snapshot, [task]: { ...snapshot[task], checked: JSON.stringify(snapshot[task].values) } }); },
    attach(task: VinUniTask, field: string, selected: File[]) {
      if (!editable(task)) return;
      files.set(snapshot[task].id, { ...files.get(snapshot[task].id), [field]: selected });
      update(task, { [field]: selected.map(f => f.name).join("\n") });
    },
    beginSubmission(task: VinUniTask) {
      if (!editable(task)) return null;
      const id = snapshot[task].id;
      publish({ ...snapshot, pending: [...snapshot.pending, id] }); return id;
    },
    endSubmission(id: string) { publish({ ...snapshot, pending: snapshot.pending.filter(value => value !== id) }); },
    recordSubmission(task: VinUniTask, id: string, submission: FormSubmission) {
      if (snapshot[task].id === id) publish({ ...snapshot, [task]: { ...snapshot[task], submission } });
    },
    startNew(task: VinUniTask, email: string) {
      if (snapshot.pending.includes(snapshot[task].id)) return false;
      publish({ ...snapshot, archive: [...snapshot.archive, { task, draft: snapshot[task] }], [task]: fresh(defaults(task, email)) }); return true;
    },
    selectDraft(task: VinUniTask, id: string) {
      if (snapshot[task].id === id) return true;
      if (snapshot.pending.includes(snapshot[task].id)) return false;
      const entry = snapshot.archive.find(entry => entry.task === task && entry.draft.id === id);
      if (!entry) return false;
      publish({ ...snapshot, archive: [...snapshot.archive.filter(entry => entry.draft.id !== id), { task, draft: snapshot[task] }], [task]: entry.draft }); return true;
    },
    propose(task: VinUniTask, field: string, value: string): FormChange | null {
      if (!editable(task) || value.length > 4000) return null;
      const draft = snapshot[task];
      const definition = [0, 1].flatMap(stage => visibleFields(task, stage, draft.values)).find(f => f.name === field);
      if (!definition || definition.type === "checkbox" || definition.type === "file" || (definition.options && !definition.options.some(([id]) => id === value))) return null;
      const after = normalized(task, { [field]: value });
      return { task, draftId: draft.id, revision: draft.revision, label: definition.label,
        before: Object.fromEntries(Object.keys(after).map(name => [name, draft.values[name] ?? ""])), after };
    },
    apply(change: FormChange) {
      const draft = snapshot[change.task];
      if (!editable(change.task) || draft.id !== change.draftId || draft.revision !== change.revision ||
        !Object.entries(change.before).every(([field, value]) => (draft.values[field] ?? "") === value)) return null;
      const values = { ...draft.values, ...normalized(change.task, change.after) };
      const definitions = [0, 1].flatMap(stage => visibleFields(change.task, stage, values));
      if (Object.keys(change.before).length !== Object.keys(change.after).length ||
        !Object.entries(change.after).every(([field, value]) => {
          const definition = definitions.find(item => item.name === field);
          return Object.hasOwn(change.before, field) && typeof value === "string" && value.length <= 4000 && definition &&
            definition.type !== "checkbox" && definition.type !== "file" && (!definition.options || definition.options.some(([id]) => id === value));
        })) return null;
      update(change.task, change.after);
      return { ...change, revision: snapshot[change.task].revision };
    },
    undo(change: FormChange) {
      const draft = snapshot[change.task];
      if (!editable(change.task) || draft.id !== change.draftId || draft.revision !== change.revision ||
        !Object.entries(change.after).every(([field, value]) => draft.values[field] === value)) return false;
      return update(change.task, change.before);
    },
  };
}

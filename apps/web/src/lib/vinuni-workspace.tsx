"use client";

import { createContext, useContext, useState, useSyncExternalStore, type ReactNode } from "react";
import { defaults } from "./vinuni-forms";
import { useStore } from "./store";
import { useStudentWorkspace } from "./student-workspace";
import { createVinUniFormStore } from "./vinuni-form-store";

type Workspace = ReturnType<typeof createVinUniFormStore>;
type Snapshot = ReturnType<Workspace["getSnapshot"]>;
const Context = createContext<{ store: Workspace; state: Snapshot } | null>(null);
export function VinUniFormsProvider({ children }: { children: ReactNode }) {
  const { currentUser, dataConfig } = useStore();
  const { certificate, complaint } = useStudentWorkspace();
  const [store] = useState(() => createVinUniFormStore(`campus247_vinuni_forms_v2:${dataConfig?.mode}:${encodeURIComponent(currentUser!.id)}`, `campus247_vinuni_forms_v1:${dataConfig?.mode}:${encodeURIComponent(currentUser!.id)}`, {
    certificate: { ...defaults("certificate", /@(?:[\w-]+\.)*(?:huce|vinuni)\.edu\.vn$/i.test(currentUser!.email) ? currentUser!.email : currentUser!.email || ""),
      ...(!certificate.submission ? { purpose: certificate.data.purpose, destinationOrg: certificate.data.destinationOrg, receiveMethod: certificate.data.receiveMethod } : {}) },
    complaint: { ...defaults("complaint", /@(?:[\w-]+\.)*(?:huce|vinuni)\.edu\.vn$/i.test(currentUser!.email) ? currentUser!.email : currentUser!.email || ""),
      ...(!complaint.submission ? { course: complaint.data.course, description: complaint.data.description } : {}) },
  }));
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  return <Context.Provider value={{ store, state }}>{children}</Context.Provider>;
}
export function useVinUniForms() { const context = useContext(Context); if (!context) throw new Error("VinUniFormsProvider required"); return context; }

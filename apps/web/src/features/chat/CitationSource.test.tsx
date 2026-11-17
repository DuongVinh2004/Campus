import React from "react";
import { webcrypto } from "node:crypto";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CitationSource, type CitationSourceBinding } from "./CitationSource";

const id = "019a0000-0024-7000-8000-000000000011";
const text = "Nguồn mô phỏng <script>không thực thi</script> 480.000 VNĐ/tín chỉ.";
const binding: CitationSourceBinding = { conversationId:id, messageId:id, citation:{citation_id:id,
  source_id:id, document_version_id:id, chunk_id:id, source_title:"Nguồn mô phỏng", canonical_uri:"synthetic://campus247/tuition",
  version_label:"simulation-v1", source_status:"SYNTHETIC", locator:{section_path:"Học phí"}, quote:text.slice(0,20)} };
async function result() {
  const hash = await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return {conversation_id:id,message_id:id,citation:binding.citation,issuer:"HUCE Demo",effective_from:"2026-01-01T00:00:00Z",
    effective_until:null,content_text:text,content_sha256:Buffer.from(hash).toString("hex"),representation:"CITED_CHUNK"};
}
async function v2Result() {
  const quote = "tổ chức các lớp học phương thức trực tuyến khi đáp ứng các điều kiện bảo đảm chất lượng";
  const content = `Điều 8. Tổ chức giảng dạy và học tập\n2. Dạy và học trực tuyến: ${quote}.\nCác quy định khác của điều này.`;
  const hash = await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(content));
  const content_sha256 = Buffer.from(hash).toString("hex");
  const citation = {
    citation_id:"01a1973a-6cca-7089-82ae-21eabfd24c67", source_id:"253eb450-c57a-79a7-84a4-b0d85e12de1c",
    document_version_id:"01a17057-0cbd-7504-a63c-b4c0ca345694", chunk_id:"01a17057-0d62-76af-8733-fb90d72a2762",
    source_title:"Quy chế đào tạo HUCE — Quyết định 1486 ngày 06/11/2023",
    canonical_uri:"https://drive.google.com/file/d/fixture/preview?",
    version_label:"verified-effective-01a17057-0cbd-7504-a63c-b4c0ca345694", source_status:"CURRENT" as const,
    locator:{section_path:"Quy chế 1486 — Điều 8, khoản 2 — PDF 10",page_start:10,page_end:10}, quote,
    release_id:"01a172fe-1822-7679-a515-335e063dd1fa", release_generation:27,
    evidence_sha256:content_sha256, unit_id:"unit-v2-quy-che-1486-dieu-8-khoan-2",
  };
  return {conversation_id:id,message_id:id,citation,issuer:"Trường Đại học Xây dựng Hà Nội",
    effective_from:"2023-11-06T00:00:00Z",effective_until:null,content_text:content,content_sha256,representation:"CITED_CHUNK"};
}
beforeEach(() => { vi.stubGlobal("crypto", webcrypto); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it.each([true,false])("opens a v2 quote in the middle of a chunk with binding unit_id=%s", async(withUnitId)=>{
  const payload = await v2Result();
  const {unit_id,...withoutUnitId} = payload.citation;
  const bound = {conversationId:id,messageId:id,citation:withUnitId ? payload.citation : withoutUnitId};
  expect(unit_id).toBeTruthy();
  expect(payload.content_text.indexOf(payload.citation.quote)).toBeGreaterThan(0);
  vi.spyOn(globalThis,"fetch").mockResolvedValue({ok:true,status:200,json:async()=>payload} as Response);
  render(<CitationSource binding={bound}/>); fireEvent.click(screen.getByRole("button"));
  await waitFor(()=>expect(screen.getByTestId("original-source-text").textContent).toBe(payload.content_text));
  expect(screen.queryByRole("alert")).toBeNull();
});
it.each(["missing quote","empty quote","content hash","evidence hash","unit_id"])("rejects v2 %s", async(fault)=>{
  const payload = await v2Result();
  if (fault === "missing quote") payload.citation.quote = "Đoạn trích không có trong nguồn.";
  if (fault === "empty quote") payload.citation.quote = "";
  if (fault === "content hash") payload.content_text += " Nội dung đã thay đổi.";
  if (fault === "evidence hash") payload.citation.evidence_sha256 = "0".repeat(64);
  const bound = {conversationId:id,messageId:id,citation:{...payload.citation}};
  if (fault === "unit_id") payload.citation.unit_id = "unit-v2-other";
  vi.spyOn(globalThis,"fetch").mockResolvedValue({ok:true,status:200,json:async()=>payload} as Response);
  render(<CitationSource binding={bound}/>); fireEvent.click(screen.getByRole("button"));
  await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("Chưa thể xác minh"));
  expect(screen.queryByTestId("original-source-text")).toBeNull();
});
it("opens the bound persisted source with authentication and displays plain text", async () => {
  const payload = await result();
  const fetcher = vi.spyOn(globalThis,"fetch").mockResolvedValue({ok:true,status:200,json:async()=>payload} as Response);
  render(<CitationSource binding={binding}/>);
  fireEvent.click(screen.getByRole("button"));
  await waitFor(()=>expect(screen.getByTestId("original-source-text").textContent).toBe(text));
  expect(screen.getByText(/Nguồn mô phỏng —/)).toBeDefined();
  expect(document.querySelector("script")).toBeNull();
  expect(fetcher).toHaveBeenCalledWith(expect.stringContaining(`/messages/${id}/citations/${id}/source`),expect.objectContaining({credentials:"include",cache:"no-store"}));
});
it.each([403,404])("conceals denied source status %s", async(status)=>{
  vi.spyOn(globalThis,"fetch").mockResolvedValue({ok:false,status} as Response);
  render(<CitationSource binding={binding}/>); fireEvent.click(screen.getByRole("button"));
  await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("không còn khả dụng"));
  expect(screen.queryByTestId("original-source-text")).toBeNull();
});
it("uses only cookies for a v2 source and offers login on 401 without reading a token", async () => {
  const payload = await v2Result();
  window.localStorage.setItem("campus247_token", "legacy-fixture");
  const read = vi.spyOn(window.localStorage, "getItem");
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 401 } as Response);
  render(<CitationSource binding={{ conversationId: id, messageId: id, citation: payload.citation }} />);
  fireEvent.click(screen.getByRole("button"));
  await screen.findByText(/Phiên đăng nhập đã hết hạn/);
  expect(screen.getByRole("link", { name: "Đăng nhập lại" }).getAttribute("href")).toBe(`/login?redirect=${encodeURIComponent(`/chat?conversation_id=${id}`)}`);
  expect(read.mock.calls.some(([key]) => key === "campus247_token")).toBe(false);
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(new Headers(fetcher.mock.calls[0][1]?.headers).has("Authorization")).toBe(false);
  window.localStorage.removeItem("campus247_token");
});
it.each(["message_id","content_sha256"])("rejects mismatched %s", async(field)=>{
  const payload = {...await result(),[field]:"0".repeat(64)};
  vi.spyOn(globalThis,"fetch").mockResolvedValue({ok:true,status:200,json:async()=>payload} as Response);
  render(<CitationSource binding={binding}/>); fireEvent.click(screen.getByRole("button"));
  await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("Chưa thể xác minh"));
  expect(screen.queryByTestId("original-source-text")).toBeNull();
});
it("aborts a pending request when the drawer unmounts",async()=>{
  const fetcher = vi.spyOn(globalThis,"fetch").mockImplementation(()=>new Promise(()=>{}));
  const view = render(<CitationSource binding={binding}/>); fireEvent.click(screen.getByRole("button"));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  const signal = fetcher.mock.calls[0][1]?.signal;
  view.unmount(); expect(signal?.aborted).toBe(true);
});
it("labels a reviewed snapshot without claiming a legal effective date", async () => {
  const snapshot = { ...binding, citation: { ...binding.citation, version_label: "public-snapshot-v1" } };
  const payload = { ...await result(), citation: snapshot.citation,
    applicability_note: "Bản nguồn đối chiếu ngày 2026-10-24; không phải ngày hiệu lực pháp lý." };
  vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => payload } as Response);
  render(<CitationSource binding={snapshot} />); fireEvent.click(screen.getByRole("button"));
  await waitFor(() => expect(screen.getByTestId("original-source-text").textContent).toBe(text));
  expect(screen.getByText(/không phải ngày hiệu lực pháp lý/)).toBeDefined();
  expect(screen.queryByText(/^Hiệu lực từ:/)).toBeNull();
});

import { describe, expect, it, vi } from "vitest";

vi.mock("pdfjs-dist/web/pdf_viewer.css", () => ({}));
import { normalizeReaderState, validatePdfSource } from "./LearningPdfReader";

describe("Reader position restoration", () => {
  it("bounds stale page, offsets and zoom after document metadata changes", () => {
    expect(normalizeReaderState({page_no:800,offset_x:-1,offset_y:2,zoom_mode:"custom",zoom_value:9,rotation:45},48))
      .toEqual({page_no:48,offset_x:0,offset_y:1,scroll_mode:"vertical",zoom_mode:"custom",zoom_value:3,rotation:0});
  });
  it("restores a valid horizontal reading position and rotation", () => {
    const saved={page_no:7,offset_x:0.2,offset_y:0.4,scroll_mode:"horizontal" as const,zoom_mode:"page-fit" as const,zoom_value:1.5,rotation:90};
    expect(normalizeReaderState(saved,48)).toEqual(saved);
  });
  it("rejects nonfinite server or browser state instead of breaking the viewer", () => {
    expect(normalizeReaderState({page_no:NaN,zoom_value:Infinity,offset_y:NaN},3)).toMatchObject({page_no:1,zoom_value:1,offset_y:0});
  });
});

describe("Authenticated PDF source boundary",()=>{
  it("allows only content served by the Campus origin",()=>{
    expect(validatePdfSource('/v1/learning/versions/v1/content','https://campus.test')).toBe('https://campus.test/v1/learning/versions/v1/content');
    for(const source of ['https://outside.test/file.pdf','javascript:alert(1)','data:application/pdf,abc','https://user:password@campus.test/file'])expect(()=>validatePdfSource(source,'https://campus.test')).toThrow();
  });
});

import { describe, expect, it } from "vitest";
import { splitGuidance } from "./ChatPanel";

describe("splitGuidance", () => {
  it("separates the server's next-steps block from the answer body", () => {
    const text = "Học phí K67 là 580.500 đồng/tín chỉ. [1]\n\nMức này phụ thuộc vào ngành.\n\nGợi ý hỏi tiếp:\n- K67\n- Công nghệ thông tin";
    expect(splitGuidance(text)).toEqual({
      body: "Học phí K67 là 580.500 đồng/tín chỉ. [1]\n\nMức này phụ thuộc vào ngành.",
      suggestions: ["K67", "Công nghệ thông tin"],
    });
  });

  it("leaves ordinary messages, and a marker without bullets, untouched", () => {
    expect(splitGuidance("Chỉ có câu trả lời.")).toEqual({ body: "Chỉ có câu trả lời.", suggestions: [] });
    const lone = "Nội dung\n\nGợi ý hỏi tiếp:\nkhông có gạch đầu dòng";
    expect(splitGuidance(lone)).toEqual({ body: lone, suggestions: [] });
  });

  it("only treats the final block as guidance and caps the number of buttons", () => {
    const many = Array.from({ length: 8 }, (_, i) => `- Mục ${i + 1}`).join("\n");
    const result = splitGuidance(`Trả lời\n\nGợi ý hỏi tiếp:\n${many}`);
    expect(result.suggestions).toHaveLength(5);
    expect(result.body).toBe("Trả lời");
  });
});

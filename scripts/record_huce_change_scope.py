"""Record reviewable inverse-patch preimages for pre-existing untracked source files.

These are normalized-text reconstructions of this task's scoped patches, NOT
claimed byte-for-byte snapshots captured before the task. No source is rewritten.
"""
import difflib
import hashlib
import json
from pathlib import Path

from huce_source_registry import ROOT, checked, save


def replace_once(text, after, before):
    if text.count(after) != 1:
        raise ValueError("scope changed; cannot reconstruct exact inverse patch")
    return text.replace(after, before, 1)


def main():
    out = checked(ROOT / ".tooling/huce-expansion-20261020-01/change-scope")
    out.mkdir(exist_ok=False)
    rules = {}
    name = "services/api/src/campus247/infrastructure/retrieval/public_knowledge.py"
    text = checked(ROOT / name).read_text(encoding="utf-8")
    text = replace_once(text, "faq_directory: Path | None = None, include_reviewed_expansion: bool = True):", "faq_directory: Path | None = None):")
    start = text.index('        for name in (active, regulations, "supplemental-20261020.json"')
    end = text.index('            path = directory / name', start)
    text = text[:start] + '        for name in (active, regulations, "supplemental-20261020.json", *legacy):\n' + text[end:]
    for first, last in [('            reviewed_release = name ==', '            items = regulation_sections'),
                        ('                if reviewed_release:\n                    snapshot', '                url = item["url"]'),
                        ('                if reviewed_release:\n                    source_id', '                section = item["section"]'),
                        ('                if reviewed_release:\n                    row["provenance"]', '                if name in legacy:')]:
        a = text.index(first); b = text.index(last, a); text = text[:a] + text[b:]
    rules[name] = text
    name = "services/api/src/campus247/infrastructure/retrieval/public_hybrid.py"
    text = checked(ROOT / name).read_text(encoding="utf-8")
    text = replace_once(text, "from campus247.application.retrieval.programme_scope import matches_programme_scope\n", "")
    a = text.index('\n\ndef _program_credit_span('); b = text.index('\n\n@dataclass', a); text = text[:a] + text[b:]
    a = text.index('        credit_total = '); b = text.index('        # The cross-encoder', a)
    text = text[:a] + '        focused = max(excerpts, key=lambda text: len(relevant & set(terms(text))))\n' + text[b:]
    a = text.index('        if "tin chi tot nghiep" in topics:'); b = text.index('        if scoped:', a); text = text[:a] + text[b:]
    a = text.index('        # A direct program total'); b = text.index('        for index in dict.fromkeys(priority):', a)
    text = text[:a] + '        priority = graph_children[:candidate_limit//2] + sorted(fused,\n            key=lambda index: (-fused[index], self.children[index]["id"]))\n' + text[b:]
    rules[name] = text
    name = "scripts/public_rag_retrieval.py"
    text = checked(ROOT / name).read_text(encoding="utf-8")
    text = replace_once(text, 'policy: PublicRetrievalPolicy | None = None,\n                               include_reviewed_expansion: bool = True) -> PublicHybridKnowledgeStore:',
                        'policy: PublicRetrievalPolicy | None = None) -> PublicHybridKnowledgeStore:')
    text = replace_once(text, '        include_reviewed_expansion=include_reviewed_expansion,\n', '')
    rules[name] = text
    name = "services/api/src/campus247/application/conversation/followup.py"
    text = checked(ROOT / name).read_text(encoding="utf-8")
    text = replace_once(text, '    if " tien hoc " in text or re.search(r"\\bk\\d{2}\\s+(?:can\\s+)?dong\\s+bao\\s+nhieu\\b", text):\n        topics.add("hoc phi")\n', '')
    rules[name] = text
    name = "apps/web/e2e-live/tuition-credit.pw.ts"
    text = checked(ROOT / name).read_text(encoding="utf-8")
    text = replace_once(text, 'import { writeFile } from "node:fs/promises";\n', '')
    text = replace_once(text, '    // Chromium may retain the proxied SSE connection after the final event.\n    // Require the UI to consume that event, then read the persisted result.\n    await expect(page.getByLabel("Đặt câu hỏi", { exact: true })).toHaveValue("", { timeout: 150_000 });',
        '    // Let the actual stream finish rather than flooding the shared read API\n    // while both the workspace and agent progress are already polling it.\n    await stream.finished();')
    text = replace_once(text, '    await writeFile(test.info().outputPath(`answer-${index + 1}.json`), JSON.stringify({ question: item.q, final }, null, 2), { flag: "wx" });\n', '')
    rules[name] = text
    summary = []
    for name, before in rules.items():
        current = checked(ROOT / name).read_text(encoding="utf-8")
        preimage = checked(out / name)
        preimage.parent.mkdir(parents=True, exist_ok=True)
        with preimage.open("x", encoding="utf-8") as stream: stream.write(before)
        diff = "".join(difflib.unified_diff(before.splitlines(keepends=True), current.splitlines(keepends=True), fromfile="before/"+name, tofile="after/"+name))
        with checked(out / (Path(name).name + ".patch")).open("x", encoding="utf-8") as stream: stream.write(diff)
        summary.append({"path": name, "before_normalized_text_sha256": hashlib.sha256(before.encode()).hexdigest(),
                        "after_normalized_text_sha256": hashlib.sha256(current.encode()).hexdigest(), "diff_lines": len(diff.splitlines())})
    save(out / "manifest.json", {"method": "inverse_scoped_patch_reconstruction_not_initial_byte_snapshot", "files": summary})
    print(json.dumps(summary), flush=True)


if __name__ == "__main__": main()

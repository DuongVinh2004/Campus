"""Helper script to update public_knowledge.py cleanly."""
from pathlib import Path

p = Path("services/api/src/campus247/infrastructure/retrieval/public_knowledge.py")
text = p.read_text(encoding="utf-8")

old_part = """            reviewed_release = name in ("reviewed-expansion-20261020.json", "reviewed-expansion-20261020-batch2.json",
                                       "reviewed-expansion-20261020-batch3-titleonly.json", "reviewed-services-20261020-01.json",
                                       "reviewed-course-review-20261021.json", "reviewed-withdrawal-20261021.json")
            if name == "reviewed-withdrawal-20261021.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed withdrawal correction required")
            if name == "reviewed-course-review-20261021.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed course correction required")
            if name == "reviewed-services-20261020-01.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed service release required")"""

new_part = """            reviewed_release = name in ("reviewed-expansion-20261020.json", "reviewed-expansion-20261020-batch2.json",
                                       "reviewed-expansion-20261020-batch3-titleonly.json",
                                       "reviewed-curricula-batch3-verified-20261021.json",
                                       "reviewed-services-20261020-01.json", "reviewed-services-20261021-02.json",
                                       "reviewed-course-review-20261021.json", "reviewed-withdrawal-20261021.json")
            if name == "reviewed-withdrawal-20261021.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed withdrawal correction required")
            if name == "reviewed-course-review-20261021.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed course correction required")
            if name in ("reviewed-services-20261020-01.json", "reviewed-services-20261021-02.json") and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed service release required")
            if reviewed_release and name == "reviewed-curricula-batch3-verified-20261021.json" and manifest.get("verification") != "visually_reviewed_source_excerpts":
                raise ValueError("reviewed batch3 verified release required")"""

assert old_part in text, "old_part not found"
text = text.replace(old_part, new_part)

old_prov = """if name in {"reviewed-services-20261020-01.json", "reviewed-course-review-20261021.json", "reviewed-withdrawal-20261021.json"}:"""
new_prov = """if name in {"reviewed-services-20261020-01.json", "reviewed-services-20261021-02.json", "reviewed-course-review-20261021.json", "reviewed-withdrawal-20261021.json", "reviewed-curricula-batch3-verified-20261021.json"}:"""
assert old_prov in text, "old_prov not found"
text = text.replace(old_prov, new_prov)

old_ret = """                if (name in legacy
                        or name == "reviewed-expansion-20261020-batch2.json" and item["text_sha256"] in retired_excerpts
                        or name == active and hashlib.sha256(item["text"].encode()).hexdigest() in retired_handbook_excerpts):"""

new_ret = """                if (name in legacy
                        or name == "reviewed-expansion-20261020-batch2.json" and item["text_sha256"] in retired_excerpts
                        or name == "reviewed-expansion-20261020-batch3-titleonly.json" and item["text_sha256"] in retired_batch3_titleonly_excerpts
                        or name == active and hashlib.sha256(item["text"].encode()).hexdigest() in retired_handbook_excerpts):"""
assert old_ret in text, "old_ret not found"
text = text.replace(old_ret, new_ret)

p.write_text(text, encoding="utf-8")
print("public_knowledge.py updated successfully!")

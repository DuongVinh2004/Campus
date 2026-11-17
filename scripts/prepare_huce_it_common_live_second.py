"""Keep only IT/common questions and all79 queries for the new focused versions."""
from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, checked, read, save
from prepare_huce_stem_full_second import STEM
from review_huce_csqt_geometry_second import CS, CSQT
from review_huce_network_geometry_second import NETWORK
from review_huce_data_science_second import DATA_SCIENCE


def main():
    priorities = {r["source_id"]: r for r in read(OUT / "source-execution-priorities-01.json")["sources"]}
    baseline = read(ROOT / "infra/local/knowledge-platform-20261023/independent-questions-20261025T082557158670.json")
    old_cases = {r["name"]: r for r in read(OUT / "combined-live-cases-294-01.json")}
    cases, deferred = {}, []
    for case in baseline["cases"]:
        name = case["name"]
        sources = [s["body"]["citation"]["source_id"] for s in case.get("sources", [])]
        nonfocus = name.startswith(("km_", "mtc_", "envb_", "hk_", "econ_", "catalogue_",
            "evidence_arch_", "evidence_civil_", "evidence_materials_", "evidence_economics_"))
        nonfocus |= any(priorities[s]["group"] == "DE_SAU" for s in sources)
        if nonfocus:
            deferred.append({"name": name, "source_ids": sources, "reason": "Other programme documents deferred by direct human instruction"})
        else:
            cases[name] = old_cases[name]
    assert len(cases) == 153 and len(deferred) == 141
    original_expected = read(OUT / "combined-live-expectations-294-01.json")
    expected = {r["name"]: r for r in original_expected["cases"] if r["name"] in cases}
    for row in expected.values():
        row["source_id"] = STEM if row["name"].startswith("stem_") else DATA_SCIENCE if row["name"].startswith("ds_") else NETWORK
    smoke = [n for n in original_expected["prior_smoke_names"] if n in cases]
    release = read(CORPUS / "candidate-release-32.json")
    members = {r["source_id"]: r["version_id"] for r in release["members"]}
    for prefix, filename, source in (("csqt_", "csqt-71-candidate-probes-06.json", CSQT),
            ("cs_", "cs-71-candidate-probes-06.json", CS), ("", "stem-notice-details-candidate-probes-06.json", STEM)):
        probe = read(OUT / filename)
        assert probe["all_passed"] and probe["release_id"] == release["release_id"]
        for row in probe["cases"]:
            assert row["expected_version"] == members[source]
            name = prefix + row["name"]
            case = {"name": name, "question": row["question"], "followup": False}
            if name in cases:
                assert cases[name] == case
            else:
                cases[name] = case
            target = source
            requirement = {k: row[k] for k in ("expected_present", "expected_terms")}
            if row["name"] == "other_programme":
                target = CS if source == CSQT else CSQT
                requirement = {"expected_present": True, "expected_terms": ["608829", "390111", "390121", "250101", "250103", "538801", "510211", "940201", "091701", "thể chất 1"]}
            if name in expected:
                assert expected[name]["expected_present"] == requirement["expected_present"] and expected[name]["source_id"] == target
                expected[name]["expected_terms"] = list(dict.fromkeys(expected[name]["expected_terms"] + requirement["expected_terms"]))
            else:
                expected[name] = {"name": name, "source_id": target, **requirement}
    assert len(cases) == 224 and set(expected) | set(smoke) == set(cases)
    save(checked(OUT / "it-common-live-cases-224-01.json"), list(cases.values()))
    save(checked(OUT / "it-common-live-expectations-224-01.json"), {"cases": list(expected.values()),
        "prior_smoke_names": smoke, "deferred_previous_cases": deferred, "generation": 27, "release_number": "32",
        "scope_manifest": "source-execution-priorities-01.json",
        "method": "153 prior IT/common questions plus71 new distinct questions; eight shared STEM questions preserve the union of prior expectations.141 other-programme questions deferred, not marked passed."})
    focus = ["cs_edge_e8", "csqt_other_programme", "stem_notice_heading", "stem_notice_recitals",
        "stem_notice_contact", "stem_notice_recipients", "stem_notice_signatory"]
    save(checked(OUT / "it-common-focus-live-cases-7-01.json"), [cases[n] for n in focus])
    print({"focus_cases": 7, "full_batch": 224, "prior_cases_deferred": 141, "other_programme_additions": 0})


if __name__ == "__main__":
    main()

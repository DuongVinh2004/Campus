"""Prepare one fixed API batch from all four candidate probes plus regressions."""
from continue_huce_completion_20261025 import OUT, checked, read, save
from prepare_huce_environment_geometry_second import ENVIRONMENT
from prepare_huce_stem_full_second import STEM
from review_huce_building_services_second import BUILDING_SERVICES
from review_huce_construction_economics_english_second import SOURCE as KTE
from review_huce_csqt_geometry_second import CS, CSQT
from review_huce_network_geometry_second import NETWORK
from review_huce_data_science_second import DATA_SCIENCE


def main():
    cases, expected = [], []
    for prefix, filename, source in [
            ("kte_", "construction-economics-english-safe-71-candidate-probes-05.json", KTE),
            ("csqt_", "csqt-71-candidate-probes-05.json", CSQT),
            ("cs_", "cs-71-candidate-probes-05.json", CS),
            ("", "stem-notice-details-candidate-probes-05.json", STEM)]:
        probe = read(OUT / filename)
        assert probe["all_passed"]
        for row in probe["cases"]:
            name = prefix + row["name"]
            cases.append({"name": name, "question": row["question"], "followup": False})
            requirement = {k: row[k] for k in ("expected_present", "expected_terms")}
            target = source
            if row["name"] == "other_programme":
                # A negative own-version preview is a positive API question for
                # the other explicitly requested programme, now also admitted.
                target = CS if source == CSQT else CSQT
                requirement = {"expected_present": True, "expected_terms": ["608829", "390111", "390121", "250101", "250103", "538801", "510211", "940201", "091701", "thể chất 1"]}
            expected.append({"name": name, "source_id": target, **requirement})
    assert len(cases) == 113
    smoke = ["tuition_k64", "password_new", "reg_full_hours", "reg_full_missing_appendix",
        "personal_unconnected", "source_injection", "geo_semester_1"]
    old = read(OUT / "combined-live-cases-294-01.json")
    cases.extend(next(c for c in old if c["name"] == name) for name in smoke)
    focus = ["hk_semester_1", "hk_elective", "envb_prior_wrong_target", "envb_unresolved_left_target"]
    old_expectations = {r["name"]: r for r in read(OUT / "combined-live-expectations-294-01.json")["cases"]}
    for name in focus:
        cases.append(next(c for c in old if c["name"] == name))
        expected.append({**old_expectations[name], "source_id": BUILDING_SERVICES if name.startswith("hk_") else ENVIRONMENT})
    assert len(cases) == len({c["name"] for c in cases}) == 124
    save(checked(OUT / "public-details-live-cases-124-01.json"), cases)
    save(checked(OUT / "public-details-live-expectations-124-01.json"), {"cases": expected,
        "prior_smoke_names": smoke, "generation": 27, "release_number": "31",
        "method": "All113 new-version candidate queries, including explicit cross-programme positive API questions, plus11 regression questions; no substitution after running"})
    # The serving code now adds sealed locator context for every verified edge.
    # Exercise the whole294-question baseline again with the105 new questions.
    all_cases = {c["name"]: c for c in old}
    base = read(OUT / "combined-live-expectations-294-01.json")
    all_expected = {r["name"]: r for r in base["cases"]}
    for row in all_expected.values():
        row["source_id"] = (STEM if row["name"].startswith("stem_") else BUILDING_SERVICES if row["name"].startswith("hk_")
            else ENVIRONMENT if row["name"].startswith("envb_") else DATA_SCIENCE if row["name"].startswith("ds_") else NETWORK)
    for case in cases:
        if case["name"] in all_cases:
            assert case == all_cases[case["name"]]
        else:
            all_cases[case["name"]] = case
    for row in expected:
        if row["name"] in all_expected:
            previous = all_expected[row["name"]]
            assert previous["expected_present"] == row["expected_present"] and previous["source_id"] == row["source_id"]
            previous["expected_terms"] = list(dict.fromkeys(previous["expected_terms"] + row["expected_terms"]))
        else:
            all_expected[row["name"]] = row
    assert len(all_cases) == 399
    save(checked(OUT / "public-details-live-cases-399-01.json"), list(all_cases.values()))
    save(checked(OUT / "public-details-live-expectations-399-01.json"), {"cases": list(all_expected.values()),
        "prior_smoke_names": base["prior_smoke_names"], "generation": 27, "release_number": "31",
        "method": "All294 prior questions plus105 new distinct questions; eight shared STEM queries retain the union of their original expectations"})
    focus_names = ["cs_edge_e8", "kte_duplicate_relation", "csqt_other_programme", "stem_notice_heading",
        "stem_notice_recitals", "stem_notice_contact", "stem_notice_recipients", "stem_notice_signatory"]
    save(checked(OUT / "public-details-focus-live-cases-08-01.json"), [all_cases[n] for n in focus_names])
    print({"focus_cases": 8, "new_version_queries": 113, "full_batch": 399})


if __name__ == "__main__":
    main()

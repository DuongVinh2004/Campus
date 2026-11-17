"""Tests that exercise the Windows development machine, skipped (with the reason) on Linux.

The Linux acceptance run (rollout step 1.11) covers everything the server executes. These files do not run on a server:
- they read evidence manifests that were written on Windows (paths with backslashes or absolute C:\\ paths);
- or they test Windows-only tooling (the PowerShell/pg_ctl launcher, the parser interpreter lookup, the restore script).
On Windows nothing is skipped.
"""
import os

import pytest

WINDOWS_EVIDENCE_FILES = {
    "test_remaining_rag_repairs.py", "test_huce_native_table_variants.py", "test_huce_raster_curriculum.py",
    "test_huce_it_related_programmes.py", "test_huce_instruction_quantities.py", "test_huce_irregular_course_line.py",
    "test_huce_service_release.py", "test_stem_publication_binding.py", "test_regulation_publication_binding.py",
    "test_merged_table_layout.py", "test_curriculum_axis_binding.py",
}
WINDOWS_TOOLING_FILES = {"test_campus_parser_runtime.py", "test_restore_script.py"}
WINDOWS_LAUNCHER_TESTS = ("test_start_passes_explicit_engine_and_index_to_api",)


def pytest_collection_modifyitems(config, items):
    if os.name == "nt":
        return
    evidence = pytest.mark.skip(reason="reads evidence manifests written on Windows (backslash or C:\\ paths); not run on a server")
    tooling = pytest.mark.skip(reason="tests Windows-only development tooling; on Linux systemd starts the services")
    for item in items:
        name = item.path.name
        if name in WINDOWS_EVIDENCE_FILES:
            item.add_marker(evidence)
        elif name in WINDOWS_TOOLING_FILES or any(item.name.startswith(prefix) for prefix in WINDOWS_LAUNCHER_TESTS):
            item.add_marker(tooling)

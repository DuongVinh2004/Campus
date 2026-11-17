"""Explicit fixture lifecycle. No app settings, .env, default DSN or cleanup."""
from __future__ import annotations

import argparse
import ast
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STATE = HERE / ".fixture-state.json"
DB = "campus247_rag_fixture"
CONTAINER = "campus247-rag-fixture"
VOLUME = "campus247_rag_fixture_pgdata"
NETWORK = "campus247-rag-fixture_default"
MARKER = "rag-synthetic-v1"
DSN_ENV = "RAG_FIXTURE_DATABASE_URL"
PORT = 15433

# Reviewed upgrade bodies are additive; downgrade bodies are never invoked.
# New/changed migrations require another scoped review, not silent execution.
REVIEWED = {
    "0001_identity.py": "71c7c7b61e0b0a943023531c8d5a323ac563cd899dba9100a4124f31332d63e1",
    "0002_knowledge.py": "76dc19ac93df1c26d921e369210f2aee0efa146c8d24a7002ab78ff99d798890",
    "0003_conversation.py": "1fa2b900c01be97c3944bda8df2b3aa6e1362f1df5de2a4359aa74ed34988816",
    "0004_action.py": "f9c3391ce7596252ad05e335bf06d46e549b92f58dd84a76ff85b89872e260c7",
    "0005_ticket.py": "4d48452d027261508c80daeafd87bcefbfd692afd685105e9a19034c1f5c54ac",
    "0006_document_request.py": "a0f8e03cf4255ab1142acb0050c6e45f237c8987b904bf5b5e4a197b12d7933c",
    "0007_booking.py": "6d2af369f62a7944cc3e99136f59ce0a3fbd3101c2d61f730e60c238c48d8fca",
    "0008_audit_outbox.py": "ede73266d620c5481590e54b01ca664201a321aab59303f1ff514e2b4194f011",
    "0009_schedule_and_vectors.py": "38d0f1fc98bc01f87e6a175bac5e3929361fc33d655eafd39d8106bf24791354",
    "booking_overlap_guard.py": "55c8c66edb21e8b85de1155a209326fe840733b20cfd00f43d7b8a5b1d2dc22b",
}
# Preserve the 0010 baseline used by EMBED-004's historical preservation test.
# This exact additive source was reviewed and applied on the owned synthetic
# fixture by TASK-RAGUP-EMBED-004. Unknown sources and hash drift still stop.
REVIEWED_ADDITIONS = {
    "0011_embedding_index_manifest.py": "bad24bab87a36fc54bfd6e807f1bc199a1f05f1ed606075dbce55e4850da1d7e",
    # FILTER-001 source reviewed: additive nullable fields, strict tuple CHECK,
    # legacy-only NULL trigger, five indexes; no lifecycle/data/vector rewrite.
    "0012_retrieval_scope.py": "b13ece1987ae63fcbf0481fe54144902dc89bbda7881a8cbc6afd81077595e1d",
    # Exact additive 0013 only; all prior hashes and unknown-source rejection stay.
    "0013_profile_embedding_storage.py":
        "50e59a3a229fcaecb72d812f31c9c6bdc06542e02c2c277c838953c7d920f3c1",
    # Exact additive chat metadata migration only; all other guards unchanged.
    "0014_chat_final_metadata.py": "bb3083ac0b4588410fb8d38937c2abecd9781b48d9a9e2af55519cf370445bc7",
    # 0015-0022 reviewed on 2026-11-03 by the repository owner after a source scan: additive tables,
    # columns, indexes and immutability triggers; 0019/0020 forward-only; only widened constraints,
    # no DROP TABLE/DELETE/TRUNCATE. Hash drift and unknown sources still stop.
    "0015_knowledge_platform.py": "820cdf93a287a109bfdd56e711f0edc11b3cc752876c784a7100cca93000492e",
    "0016_platform_immutability.py": "638a94727603bff9dcf96e9b095658fa37847ddd1025359f2fb6508b282b9393",
    "0017_chunk_inputs.py": "c35ea08d617a32fbb58a0fe247add8b3d11a4afd73a01e47a292171a86e99182",
    "0018_source_dispositions.py": "5e64999f3aca19199b0c16adc3079b696a6143224eb061eaf1b2ddae306ec612",
    "0019_document_intake_lineage.py": "5b20ae685de0c11390803d90a4127d76883ea5f5429d401c4c235b60341b460c",
    "0020_intake_fetch_receipts.py": "abe0036c1f84ee55a8ad4ae53e66cfcb7bc6084323eda43b2eba8b3e8b9dd3bf",
    "0021_edition_decision_history.py": "4eee659c7aba13e2a47eda03c902d9653365f8551822330432e67ad28160bc7a",
    "0022_rendition_corrections.py": "12b3259827063440011a338a51186df606fb2c9a869de20b5e2e9d8474ca1924",
    # 0023-0031 (learning module) reviewed 2026-11-16 and approved by the owner in chat: linear chain 0022 -> 0031, each only creates
    # new learning.* tables/columns/indexes/constraints and retention or immutability triggers; no DROP/DELETE/TRUNCATE/UPDATE of
    # existing data; every downgrade() raises (forward-only). Hash drift and unknown sources still stop.
    "0023_learning_materials.py": "5bd761f01908984ad1ff071469d0e09ae1075bf9038eb42efe1a9084736025cf",
    "0024_learning_pdf_views.py": "ae0f1f439b0c525571514d98501fbaf0d31a7b204c1b951b5460699dd79cd4af",
    "0025_learning_pptx_renditions.py": "fd71d6e4fd6ae9e4a31b00fc36e42e387e3f332b134fb19fc35b64045b1a1aed",
    "0026_learning_feedback_foundation.py": "4a97b8ccd448dab6f002a012debfbc18a24c8bd2eb1b31842cecf3499b9370ce",
    "0027_learning_page_explanations.py": "c85d6f3722a36120d88ec1659d6d01123e5e8383505d582a7d9f8213953d807a",
    "0028_learning_version_changes.py": "5a398d4d6f68eb00fb3fd963bafc70c78f7928793d59fdd5216f7b5f1070384e",
    "0029_learning_exit_tickets.py": "4e67df64496eee106d6320bbfaaacdb2b93c7166e5b7c63ac1b2452686f0d3dc",
    "0030_learning_idea_cards.py": "b252172f8bfc91ee0e431d1177c1df203ec8bcf39f38338d767a04726e261bd9",
    "0031_learning_accessible_text.py": "53991e655f08df3e2ffca7256ef74c4e5ff71b4292cf916ee14d1a2e1a3352e1",
}
SOURCE_ID = "019a0000-0000-7000-8000-000000000001"
DOCUMENT_ID = "019a0000-0000-7000-8000-000000000002"
CHUNK_IDS = tuple(f"019a0000-0000-7000-8000-{n:012d}" for n in (3, 4, 5))
TEXTS = ("Synthetic fixture: exact axis", "Synthetic fixture: diagonal", "Synthetic fixture: orthogonal axis")
DOC_HASH = hashlib.sha256("\n".join(TEXTS).encode()).hexdigest()


class FixtureError(ValueError):
    """Only constant safe messages may be reported by the CLI."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def check_runtime(version=None) -> None:
    version = sys.version_info[:2] if version is None else version
    require((3, 12) <= tuple(version) < (3, 14), "Python 3.12 or 3.13 required; no mutation performed")


def check_paths() -> None:
    # Reject Windows junctions/reparse points as well as ordinary symlinks.
    for path in (HERE, STATE, HERE / "compose.yaml", HERE / "init.sql"):
        require(path.absolute().is_relative_to(ROOT), "fixture path outside workspace")
        require(path.resolve().is_relative_to(ROOT), "resolved fixture path outside workspace")
        for ancestor in (path, *path.parents):
            if ancestor.exists():
                require(not ancestor.is_symlink() and not ancestor.is_junction(), "fixture path uses link or junction")
                require(not (getattr(ancestor.stat(), "st_file_attributes", 0) & 0x400), "fixture path uses reparse point")
            if ancestor == ROOT:
                break


def run_cli(args, *, env=None, timeout=45) -> str:
    # Never forward subprocess stderr: Docker/SQL errors can include credentials.
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, "external command failed; output suppressed")
    return result.stdout


def docker(*args) -> str:
    return run_cli(["docker", *args])


def preflight() -> None:
    check_runtime()
    check_paths()
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/verify_dependencies.py")],
                            cwd=ROOT, capture_output=True, text=True)
    require(result.returncode == 0, "dependency verifier failed; no mutation performed")
    docker("version", "--format", "{{.Server.Version}}")
    docker("compose", "version")
    print("runtime, dependencies and Docker preflight passed")


def receipt() -> dict:
    check_paths()
    require(STATE.is_file(), "fixture ownership receipt missing")
    value = json.loads(STATE.read_text(encoding="utf-8"))
    require(value.get("fixture") == MARKER and value.get("workspace") == str(ROOT), "fixture receipt identity mismatch")
    require(re.fullmatch(r"[0-9a-f]{32}", value.get("owner", "")) is not None, "fixture owner invalid")
    require(re.fullmatch(r"[A-Za-z0-9_-]{32,}", value.get("password", "")) is not None, "fixture credential invalid")
    return value


def validate_dsn(value: str | None, state: dict) -> str:
    require(isinstance(value, str) and bool(value), "RAG_FIXTURE_DATABASE_URL required; fallback forbidden")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "postgresql+asyncpg" and parsed.hostname == "127.0.0.1"
                 and parsed.port == PORT and parsed.path == "/" + DB
                 and parsed.username == "rag_fixture" and parsed.password == state["password"]
                 and not parsed.query and not parsed.fragment)
    except (ValueError, KeyError):
        valid = False
    require(valid, "fixture endpoint or database identity rejected")
    return value


def owned() -> dict:
    state = receipt()
    container = json.loads(docker("inspect", "--type", "container", CONTAINER))[0]
    volume = json.loads(docker("volume", "inspect", VOLUME))[0]
    network = json.loads(docker("network", "inspect", NETWORK))[0]
    for labels in (container["Config"].get("Labels") or {}, volume.get("Labels") or {}, network.get("Labels") or {}):
        require(labels.get("campus247.fixture") == MARKER
                and labels.get("campus247.fixture.owner") == state["owner"], "Docker ownership mismatch")
    bindings = container["HostConfig"]["PortBindings"].get("5432/tcp")
    require(bindings == [{"HostIp": "127.0.0.1", "HostPort": str(PORT)}], "fixture port binding mismatch")
    mounts = container["Mounts"]
    require(any(m.get("Name") == VOLUME and m["Destination"] == "/var/lib/postgresql/data" for m in mounts),
            "fixture volume mismatch")
    require(container["Config"]["Image"] == "pgvector/pgvector:pg16", "fixture image mismatch")
    return state


def wait_healthy() -> None:
    for _ in range(30):
        state = json.loads(docker("inspect", "--type", "container", CONTAINER))[0]["State"]
        if state.get("Health", {}).get("Status") == "healthy":
            return
        require(state.get("Running", False), "fixture container is not running")
        time.sleep(2)
    raise FixtureError("fixture healthcheck timed out; resources preserved")


def start() -> None:
    preflight()
    require(not STATE.exists(), "ownership receipt exists; inspect or resume, never recreate")
    for kind, target, args in (
        ("container", CONTAINER, ("container", "ls", "-a", "--format", "{{.Names}}")),
        ("volume", VOLUME, ("volume", "ls", "--format", "{{.Name}}")),
        ("network", NETWORK, ("network", "ls", "--format", "{{.Name}}")),
    ):
        require(target not in docker(*args).splitlines(), "fixture target collision; no reuse permitted")
    with socket.socket() as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", PORT))
    state = {"fixture": MARKER, "workspace": str(ROOT), "owner": secrets.token_hex(16),
             "password": secrets.token_urlsafe(32)}
    env = os.environ.copy()
    env["RAG_FIXTURE_POSTGRES_PASSWORD"] = state["password"]
    env["RAG_FIXTURE_OWNER"] = state["owner"]
    args = ["docker", "compose", "--env-file", os.devnull, "-f", str(HERE / "compose.yaml")]
    run_cli([*args, "config", "--quiet"], env=env)
    check_paths()
    # Exclusive creation preserves any existing receipt. Failed startup retains it.
    with STATE.open("x", encoding="utf-8") as file:
        json.dump(state, file)
    # Create stopped resources first. Ownership is verified before PostgreSQL
    # can initialize any volume, including a target raced by another process.
    run_cli([*args, "create", "--no-recreate", "postgres"], env=env, timeout=120)
    owned()
    docker("start", CONTAINER)
    wait_healthy()
    print("fixture started; ownership receipt stored; credential output suppressed")


def reviewed_sources():
    directory = ROOT / "services/api/migrations/versions"
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob("*.py")}
    require(actual == REVIEWED | REVIEWED_ADDITIONS,
            "migration source changed or unreviewed; stop before DB mutation")
    return directory


def chain():
    directory = reviewed_sources()
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config()
    config.set_main_option("script_location", str(directory.parent))
    script = ScriptDirectory.from_config(config)
    require(len(script.get_heads()) == 1, "single reviewed Alembic head required")
    tables = set()
    for path in directory.glob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        for function in module.body:
            if isinstance(function, ast.FunctionDef) and function.name == "upgrade":
                for node in ast.walk(function):
                    if isinstance(node, ast.Call) and ast.unparse(node.func) == "op.create_table":
                        tables.add(ast.literal_eval(node.args[0]))
    return config, script, script.get_current_head(), tables


def sql(conn, statement, params=None):
    from sqlalchemy import text
    return conn.execute(text(statement), params or {})


def guard_database(conn, tables: set[str], *, fresh=False) -> None:
    require(sql(conn, "SELECT current_database(), current_user, current_schema()").one()
            == (DB, "rag_fixture", "public"), "connected database/user/schema rejected")
    schemas = set(sql(conn, "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%'").scalars())
    require(schemas == {"public", "information_schema", "rag_fixture_control"}, "unknown database schema")
    relations = set(sql(conn, "SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema' "
                        "AND c.relkind IN ('r','p','v','m','f','S')").all())
    allowed = {("rag_fixture_control", "identity")}
    if not fresh:
        allowed |= {("public", name) for name in tables | {"alembic_version"}}
    require(relations <= allowed and ("rag_fixture_control", "identity") in relations, "unknown relation or bootstrap state")
    require(sql(conn, "SELECT singleton, fixture_id, synthetic_only FROM rag_fixture_control.identity").all()
            == [(True, MARKER, True)], "fixture marker rejected")
    require(sql(conn, "SELECT extversion FROM pg_extension WHERE extname='vector'").scalar() is not None,
            "pgvector extension missing")
    if not fresh:
        require(relations == allowed, "migration schema incomplete")
        # DEC-023 exact M1 extension: compare every old row and only the ten
        # checksum-bound additive rows. Unknown/removed/changed rows still stop.
        m1_path = HERE / "m1_guard_20261011_30.py"
        require(hashlib.sha256(m1_path.read_bytes()).hexdigest() == "0278fe2792da0ef9f46e52af21d687c2579601749f46763655515100223aa5ca", "M1 extension source drift")
        from m1_guard_20261011_30 import guard_database_rows, TABLES as m1_tables
        # Direct human post32 scope: retain the old guard/journal and compose
        # one hash-bound additive conversation journal, max6 exact messages.
        extension = HERE / "m1_chat_journal_20261011_33.py"
        if extension.exists():
            require(hashlib.sha256(extension.read_bytes()).hexdigest() == "e818a7b12d7f185fd4ba58461de19090481d10d5d287743bfe2f6d74220d120a", "additional M1 journal source drift")
            from m1_chat_journal_20261011_33 import guard_database_rows
        continuation = HERE / "m1_chat_journal_20261011_34.py"
        if continuation.exists():
            require(hashlib.sha256(continuation.read_bytes()).hexdigest() == "a3239f1c67fc081a7ebe2aa4aebb335b140e57e21865e43a647906f3070e4f5b", "continued M1 journal source drift")
            from m1_chat_journal_20261011_34 import guard_database_rows
        # Direct human approval37/4827/8: retain both failed USER messages and
        # authorize only six exact additive messages in the same conversation.
        measured_continuation = HERE / "m1_chat_journal_20261011_36.py"
        if measured_continuation.exists():
            require(hashlib.sha256(measured_continuation.read_bytes()).hexdigest() == "d39a2f43dd1ed2cf1d0e59b83e8fdaa0c731ed0e81800afa067af9724dfd6d99", "measured M1 journal source drift")
            from m1_chat_journal_20261011_36 import guard_database_rows
        # Direct human41/4963/9 continuation: all three failed USERs retained,
        # then at most six exact messages; no historical journal is replaced.
        verified_continuation = HERE / "m1_chat_journal_20261011_38.py"
        if verified_continuation.exists():
            require(hashlib.sha256(verified_continuation.read_bytes()).hexdigest() == "4fd2361e7dc4c098cd86f845e2bdc76cbe68782a2231e0790f6aca964543e98e", "verified M1 journal source drift")
            from m1_chat_journal_20261011_38 import guard_database_rows
        # Direct human50/6390/10: preserve all four failed USERs, then
        # at most six exact additive messages under the same immutable guard.
        pinned_continuation = HERE / "m1_chat_journal_20261011_43.py"
        if pinned_continuation.exists():
            require(hashlib.sha256(pinned_continuation.read_bytes()).hexdigest() == "8ca84fb592440dee4637fe733d0700689400e8bed839dd8eaabf2977a314b497", "pinned M1 journal source drift")
            from m1_chat_journal_20261011_43 import guard_database_rows
        # Direct human autonomous cap authority; exact additive continuation,
        # retaining all prior journals and five failed USER messages.
        measured_continuation = HERE / "m1_chat_journal_20261011_48.py"
        if measured_continuation.exists():
            require(hashlib.sha256(measured_continuation.read_bytes()).hexdigest() == "465dd368bdb7f9e130580fafb99516087b40b7fa76e06a5f04ee5caedd33e42a", "measured M1 journal source drift")
            from m1_chat_journal_20261011_48 import guard_database_rows
        cached_continuation = HERE / "m1_chat_journal_20261011_50.py"
        if cached_continuation.exists():
            require(hashlib.sha256(cached_continuation.read_bytes()).hexdigest() == "0c64785fc975589355d6a1e55223d1f7615ff1c62e65899a67dae662f2eeb4be", "cached M1 journal source drift")
            from m1_chat_journal_20261011_50 import guard_database_rows
        spin_continuation = HERE / "m1_chat_journal_20261011_52.py"
        if spin_continuation.exists():
            require(hashlib.sha256(spin_continuation.read_bytes()).hexdigest() == "56bfdb1656a926360b14f576f68eaeadcb5e4966544a412cd43ad3bc093ec3fb", "spin M1 journal source drift")
            from m1_chat_journal_20261011_52 import guard_database_rows
        deadline_continuation = HERE / "m1_chat_journal_20261012_53.py"
        if deadline_continuation.exists():
            require(hashlib.sha256(deadline_continuation.read_bytes()).hexdigest() == "a31254aa8a7b0e432813f6288540164141e0ce742594e21da9162f7f6d560ed2", "deadline M1 journal source drift")
            from m1_chat_journal_20261012_53 import guard_database_rows
        raised_deadline_continuation = HERE / "m1_chat_journal_20261012_56.py"
        if raised_deadline_continuation.exists():
            require(hashlib.sha256(raised_deadline_continuation.read_bytes()).hexdigest() == "6c6b82f4e027dbe6e425027a95f2b70192d4e4904edbbed84d1f77bdec493bc0", "raised deadline M1 journal source drift")
            from m1_chat_journal_20261012_56 import guard_database_rows
        guard_database_rows(conn, tables)
        for name in tables - {"knowledge_source", "document_version", "knowledge_chunk"}:
            # Names are literal identifiers from the hash-reviewed migration source.
            require(re.fullmatch(r"[a-z_]+", name) is not None, "unreviewed table identifier")
            if name in m1_tables:
                continue  # Already checked as exact whole-table state above.
            if name in {"user_identity", "conversation", "message"}:
                extension_path = HERE / "chat_extension_20261006_23.py"
                require(hashlib.sha256(extension_path.read_bytes()).hexdigest() == "cab9a46850a2bbe9b125fd14b201f567de5cd1eeb855653b8ed93d653733e282", "chat extension source drift")
                from chat_extension_20261006_23 import guard_chat_rows
                guard_chat_rows(conn)
            else:
                require(not sql(conn, f'SELECT EXISTS(SELECT 1 FROM public."{name}")').scalar(), "non-fixture data found")


def dimension(conn) -> int:
    value = sql(conn, "SELECT format_type(a.atttypid,a.atttypmod) FROM pg_attribute a "
                "WHERE a.attrelid='public.knowledge_chunk'::regclass AND a.attname='embedding' AND NOT a.attisdropped").scalar()
    match = re.fullmatch(r"vector\(([1-9][0-9]*)\)", value or "")
    require(match is not None, "fixed schema vector dimension required")
    return int(match[1])


def vector(first, second, dim):
    require(dim >= 2, "fixture requires at least two dimensions")
    return "[" + ",".join(str(x) for x in [first, second, *([0] * (dim - 2))]) + "]"


def seed_rows(dim):
    return (
        ("knowledge_source", {"id": SOURCE_ID, "source_type": "SYNTHETIC_DOCUMENT",
          "canonical_uri": "synthetic://rag-fixture/source-v1", "title": "Synthetic pgvector mechanism fixture",
          "owner_unit": "RAG Fixture", "authority_level": 1, "approval_status": "APPROVED", "is_synthetic": True,
          "version": 1}),
        ("document_version", {"id": DOCUMENT_ID, "knowledge_source_id": SOURCE_ID, "version_label": "fixture-v1",
          "content_checksum": DOC_HASH, "effective_from": None, "effective_until": None, "status": "PUBLISHED",
          "storage_object_key": "synthetic/rag-fixture/document-v1",
          "published_at": datetime(2026, 10, 2, tzinfo=timezone.utc), "published_by": None,
          "version": 1}),
        *(("knowledge_chunk", {"id": cid, "document_version_id": DOCUMENT_ID, "ordinal": index + 1,
          "section_path": f"Synthetic fixture / {index + 1}", "page_start": index + 1, "page_end": index + 1,
          "content_text": content, "content_checksum": hashlib.sha256(content.encode()).hexdigest(), "version": 1,
          "embedding": vector(*coords, dim), "content_tsv": None})
          for index, (cid, content, coords) in enumerate(zip(CHUNK_IDS, TEXTS, ((1, 0), (0.6, 0.8), (0, 1))))),
    )


def inspect_seed(conn, dim, *, complete=False):
    from m1_guard_20261011_30 import allowed_knowledge_ids
    expected = seed_rows(dim)
    for table in ("knowledge_source", "document_version", "knowledge_chunk"):
        valid_ids = {row["id"] for name, row in expected if name == table}
        seed_ids = set(valid_ids)
        valid_ids |= allowed_knowledge_ids(table)
        actual_ids = set(str(x) for x in sql(conn, f"SELECT id FROM public.{table}").scalars())
        require(actual_ids <= valid_ids, "data outside fixture seed found")
        if complete:
            require(seed_ids <= actual_ids <= valid_ids, "fixture seed incomplete")
    present = set()
    for table, row in expected:
        columns = ",".join(f"{key}::text AS {key}" if key == "embedding" else key for key in row)
        existing = sql(conn, f"SELECT {columns} FROM public.{table} WHERE id=:id", {"id": row["id"]}).mappings().first()
        if existing is not None:
            for key, value in row.items():
                actual = existing[key]
                if key == "embedding":
                    require(json.loads(actual) == json.loads(value), "existing fixture vector differs; overwrite forbidden")
                else:
                    require(actual == value or (key in {"id", "knowledge_source_id", "document_version_id"}
                                               and str(actual) == value), "existing fixture provenance differs; overwrite forbidden")
            present.add(row["id"])
    return present


def prepare(conn, config, script, head, tables):
    from alembic.runtime.environment import EnvironmentContext
    version_exists = sql(conn, "SELECT to_regclass('public.alembic_version')").scalar() is not None
    guard_database(conn, tables, fresh=not version_exists)
    if version_exists:
        require(sql(conn, "SELECT version_num FROM public.alembic_version").all() == [(head,)],
                "existing fixture revision differs; no implicit migration of existing data")
        inspect_seed(conn, dimension(conn))
        print("fixture already at source head; no migration executed")
        return
    # Same guarded connection and transaction; never import the app's env.py/settings.
    # Alembic's upgrade traversal runs revision upgrade() only and maintains its version table.
    with EnvironmentContext(config, script, fn=lambda rev, ctx: script._upgrade_revs(head, rev)) as context:
        context.configure(connection=conn, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
    guard_database(conn, tables)
    require(sql(conn, "SELECT version_num FROM public.alembic_version").all() == [(head,)], "Alembic head mismatch")
    print("Alembic upgrade applied to freshly owned fixture at source head " + head)


def seed(conn, tables, head):
    guard_database(conn, tables)
    require(sql(conn, "SELECT version_num FROM public.alembic_version").all() == [(head,)], "Alembic head mismatch")
    dim = dimension(conn)
    present = inspect_seed(conn, dim)
    for table, row in seed_rows(dim):
        if row["id"] in present:
            continue
        columns = ",".join(row)
        values = ",".join("CAST(:embedding AS vector)" if key == "embedding" else ":" + key for key in row)
        sql(conn, f"INSERT INTO public.{table} ({columns}) VALUES ({values})", row)
    inspect_seed(conn, dim, complete=True)
    print("synthetic seed verified; existing records preserved; dimension " + str(dim))


def verify(conn, tables, head):
    from sqlalchemy.exc import DBAPIError
    guard_database(conn, tables)
    require(sql(conn, "SELECT version_num FROM public.alembic_version").all() == [(head,)], "Alembic head mismatch")
    dim = dimension(conn)
    inspect_seed(conn, dim, complete=True)
    ranked = tuple(str(x) for x in sql(conn, "SELECT id FROM public.knowledge_chunk "
                   "WHERE embedding IS NOT NULL ORDER BY embedding <=> CAST(:query AS vector), id", {"query": vector(1, 0, dim)}).scalars())
    require(ranked == CHUNK_IDS, "pgvector nearest-neighbor ordering differs")
    rejected = False
    try:
        with conn.begin_nested():
            sql(conn, f"SELECT CAST(:bad AS vector({dim}))", {"bad": vector(1, 0, dim + 1)})
    except DBAPIError as error:
        rejected = getattr(error.orig, "sqlstate", None) == "22000"
    require(rejected, "database dimension rejection not verified")
    extension = sql(conn, "SELECT extversion FROM pg_extension WHERE extname='vector'").scalar()
    server = sql(conn, "SHOW server_version").scalar()
    # Include every stored column (including timestamps) and all public index
    # definitions so persistence evidence detects changes beyond seed counts.
    rows = {name: sql(conn, f"SELECT to_jsonb(t)::text FROM public.{name} t ORDER BY id").scalars().all()
            for name in ("knowledge_source", "document_version", "knowledge_chunk")}
    indexes = [list(row) for row in sql(conn, "SELECT tablename,indexname,indexdef FROM pg_indexes "
                                      "WHERE schemaname='public' ORDER BY tablename,indexname").all()]
    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    evidence = {"database": DB, "schema": "public", "head": head, "dimension": dim,
                "pgvector_version": extension, "postgres_version": server,
                "seed_counts": [1, 1, 3], "nearest_neighbor": "passed", "dimension_rejection": "passed",
                "stored_rows_sha256": digest(rows), "public_indexes_sha256": digest(indexes),
                "chunk_indexes": [row[2] for row in indexes if row[0] == "knowledge_chunk"]}
    print(json.dumps(evidence))
    return evidence


async def database_action(action):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    state = owned()
    dsn = validate_dsn(os.environ.get(DSN_ENV), state)
    config, script, head, tables = chain()
    engine = create_async_engine(dsn, poolclass=NullPool, echo=False, hide_parameters=True)
    try:
        async with engine.begin() as conn:
            # Serializes fixture preparation/seed commands without deleting anything.
            await conn.exec_driver_sql("SELECT pg_advisory_xact_lock(24715433)")
            if action == "prepare":
                return await conn.run_sync(lambda c: prepare(c, config, script, head, tables))
            if action == "seed":
                return await conn.run_sync(lambda c: seed(c, tables, head))
            return await conn.run_sync(lambda c: verify(c, tables, head))
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "start", "prepare", "seed", "verify", "stop", "resume", "persistence"))
    action = parser.parse_args().action
    try:
        if action == "start":
            start()
        elif action in {"stop", "resume"}:
            check_runtime()
            owned()
            docker("stop" if action == "stop" else "start", CONTAINER)
            if action == "resume":
                wait_healthy()
            print("exact owned fixture " + action + " passed; volume preserved")
        else:
            preflight()
            if action != "preflight":
                before = asyncio.run(database_action(action))
                if action == "persistence":
                    owned()
                    docker("stop", CONTAINER)
                    owned()
                    docker("start", CONTAINER)
                    wait_healthy()
                    after = asyncio.run(database_action("verify"))
                    require(before == after, "stop/start persistence differs")
                    print("stop/start persistence passed; volume preserved")
        return 0
    except FixtureError as error:
        print("BLOCKED: " + str(error), file=sys.stderr)
    except Exception as error:
        print("BLOCKED: " + type(error).__name__ + "; details suppressed; resources preserved", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

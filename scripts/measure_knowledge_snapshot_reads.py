"""Read-only comparison of release prefilter work, with all payload hashes checked."""
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace

from knowledge_platform import ROOT, TENANT, checked_path, components, retain
from campus247.application.knowledge.source_snapshot import read_snapshot, read_release_snapshots


class CountConnection:
    def __init__(self, conn):
        self.conn, self.selects = conn, 0
    async def fetch(self, *args):
        self.selects += 1
        return await self.conn.fetch(*args)
    async def fetchrow(self, *args):
        self.selects += 1
        return await self.conn.fetchrow(*args)


class CountStorage:
    def __init__(self, storage):
        self.storage, self.reads, self.bytes = storage, 0, 0
    def read(self, artifact):
        raw = self.storage.read(artifact)
        self.reads += 1; self.bytes += len(raw)
        return raw


async def main():
    pool, _, platform, _ = await components()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation="repeatable_read"):
                pointer = await platform.repo.pointer(conn)
                measurements, results = {}, {}
                for mode in ("old", "batch"):
                    counted = CountConnection(conn)
                    storage = CountStorage(platform.storage)
                    bound = SimpleNamespace(repo=platform.repo, storage=storage)
                    started, cpu_started = time.perf_counter(), time.process_time()
                    if mode == "old":
                        members = await counted.fetch("SELECT version_id FROM knowledge_release_member WHERE release_id=$1", pointer["release_id"])
                        versions = [await platform.repo.version(counted, row["version_id"]) for row in members]
                        scopes = {version["version_id"]: await read_snapshot(bound, counted, version) for version in versions}
                    else:
                        versions = await platform.repo.release_versions(counted, pointer["release_id"])
                        scopes = await read_release_snapshots(bound, counted, versions)
                    measurements[mode] = {"wall_seconds": time.perf_counter()-started, "cpu_seconds": time.process_time()-cpu_started,
                        "metadata_selects": counted.selects, "artifact_reads": storage.reads, "artifact_bytes": storage.bytes,
                        "versions": len(versions), "model_calls": 0}
                    results[mode] = ({v["version_id"]: v for v in versions}, scopes)
                equal = results["old"] == results["batch"]
                if not equal:
                    raise RuntimeError("Batch metadata/scope differs; no runtime activation attempted")
        at = datetime.now(UTC)
        output = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("snapshot-reads-" + at.strftime("%Y%m%dT%H%M%S%f") + ".json"), ROOT)
        files = ["services/api/src/campus247/infrastructure/knowledge/repository.py",
                 "services/api/src/campus247/infrastructure/knowledge/runtime.py",
                 "services/api/src/campus247/application/knowledge/source_snapshot.py"]
        result = {"at": at.isoformat(), "binding": pointer, "tenant": TENANT, "measurements": measurements,
            "metadata_and_scopes_equal": equal, "all_artifact_hashes_rechecked": True,
            "phase": "release metadata and applicability prefilter only; not end-to-end latency or load",
            "cache": "request-scoped batch only; no cross-request trust of filesystem contents",
            "files": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
            "runtime_process_restarted": False, "release_changed": False}
        retain(output, result)
        print(json.dumps({"receipt": str(output), **result}, default=str))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

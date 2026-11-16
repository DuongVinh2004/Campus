"""Bind a full local Campus rehearsal to an explicitly provisioned synthetic bundle."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from campus247.bootstrap.learning import checked_learning_path


@dataclass(frozen=True)
class LearningCampusRehearsal:
    directory: Path
    cluster: Path
    credentials_file: Path
    database: str
    port: int
    revision: str

    @classmethod
    def load(cls, path, workspace: Path) -> LearningCampusRehearsal:
        manifest = checked_learning_path(Path(path), workspace)
        directory = manifest.parent
        if (manifest.name != "rehearsal.json" or directory.parent != workspace / ".tooling"
                or not re.fullmatch(r"learning-campus-rehearsal-[0-9]{8}-[0-9]{2}", directory.name)):
            raise ValueError("Explicit synthetic Campus rehearsal directory required")
        value = json.loads(manifest.read_text(encoding="utf-8"))
        if (value.get("schema") != "learning-campus-rehearsal-v1" or value.get("synthetic_only") is not True
                or value.get("revision") not in ("0025", "0026", "0027", "0028", "0029", "0030", "0031") or value.get("host") != "127.0.0.1"
                or type(value.get("port")) is not int or not 56000 <= value["port"] <= 56999
                or value.get("database") != "campus247_" + directory.name.replace("-", "_")):
            raise ValueError("Campus rehearsal database identity mismatch")
        cluster = checked_learning_path(workspace / value["cluster"], workspace)
        if (cluster.name != "cluster" or cluster.parent.parent != workspace / ".tooling"
                or not re.fullmatch(r"learning-pg-live-[0-9]{8}-[0-9]{2}", cluster.parent.name)
                or not cluster.is_dir()):
            raise ValueError("Only a task-owned local learning cluster is accepted")
        credentials = checked_learning_path(cluster.parent / "credentials.json", workspace)
        for name in ("learning/config.json", "artifacts", "owner/identity.json", "student/identity.json",
                     "actor-state.sqlite3", "action-idempotency.sqlite3", "conversations.sqlite3"):
            checked_learning_path(directory / name, workspace)
        return cls(directory, cluster, credentials, value["database"], value["port"], value["revision"])

    def connection(self):
        credentials = json.loads(self.credentials_file.read_text(encoding="utf-8"))
        if (credentials.get("synthetic_only") is not True or credentials.get("user") != "learning_rehearsal"
                or credentials.get("host") != "127.0.0.1" or credentials.get("port") != self.port):
            raise ValueError("Scoped rehearsal credentials mismatch")
        return {key: credentials[key] for key in ("host", "port", "user", "password")} | {"database": self.database}

    async def verify_connection(self, conn):
        row = await conn.fetchrow("""SELECT current_database() AS db, current_user AS usr,
            host(inet_server_addr()) AS host, inet_server_port() AS port, current_setting('data_directory') AS directory""")
        if ((row["db"], row["usr"], row["host"], row["port"]) != (self.database, "learning_rehearsal", "127.0.0.1", self.port)
                or Path(row["directory"]).resolve(strict=True) != self.cluster
                or await conn.fetchval("SELECT version_num FROM alembic_version") != self.revision):
            raise ValueError("Rehearsal runtime connection differs from the verified profile")

"""Resume only the missing 3115 UI alongside an already running Campus backend."""
import json
import subprocess
from urllib.request import build_opener, ProxyHandler

from campus import ROOT, WEB, NODE, NEXT, HIDDEN, current_build, environment, port_owned, wait_ready
from campus_backend import checked


def main():
    if port_owned(3115) or not port_owned(8006):
        raise RuntimeError("Require missing frontend and existing backend; no automatic stop")
    with build_opener(ProxyHandler({})).open("http://127.0.0.1:8006/health/live", timeout=5) as response:
        assert response.status == 200
    destination = current_build()
    output = checked(ROOT / ".tooling/huce-continuation-20261020-01")
    command = [NODE, str(NEXT), "start", "-H", "127.0.0.1", "-p", "3115"]
    with checked(output / "frontend.log").open("xb") as log:
        process = subprocess.Popen(command, cwd=WEB, env=environment(destination),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=HIDDEN)
    wait_ready(process, "http://127.0.0.1:3115/health/live")
    receipt = {"pid": process.pid, "command": command, "build": destination,
               "backend_preserved": True, "url": "http://127.0.0.1:3115/chat"}
    with checked(output / "frontend-launch.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()

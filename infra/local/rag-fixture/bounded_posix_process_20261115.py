"""Linux counterpart of bounded_physical_process (the Windows job object): one owned child, killed with its parent.

Windows bounds the model worker with a job object: 5 GiB memory, four logical processors, kill on close.
On Linux the same bounds are applied by the service manager that starts this process (systemd MemoryMax and
CPUQuota, or the container limits of the simulation), because a per-process address-space limit would break the
memory-mapped model files. What this class itself guarantees: the worker is a direct child with piped output and
receives SIGKILL when its owner dies (PR_SET_PDEATHSIG), so no orphaned model server keeps the ports.
"""
import ctypes
import os
import signal
import subprocess

PR_SET_PDEATHSIG = 1


def _die_with_parent():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)


class BoundedProcess:
    def __init__(self, args, *, cwd, env):
        self.process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", preexec_fn=_die_with_parent)
        self.controls = {"memory_gib": 5, "cpu_count": os.cpu_count(), "enforced_by": "service manager (systemd MemoryMax / container limits)",
            "parent_death_signal": "SIGKILL", "child_tree_bound": False}

    def close(self):
        if self.process.poll() is None:
            self.process.kill()

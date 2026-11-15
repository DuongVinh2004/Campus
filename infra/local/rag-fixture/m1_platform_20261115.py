"""The reviewed CPU engine class for this operating system.

Windows keeps the measured policy (four pinned logical processors, bounded spinning). Elsewhere the thread
affinities would name processors that may not exist (a 4 vCPU server), so the reviewed scheduling option
without affinity is used. Same model, same math; only thread placement differs."""
import os

if os.name == "nt":
    from m1_spin_policy_20261011_51 import CPU
else:
    from m1_cpu_20261011_34 import CPU

__all__ = ["CPU"]

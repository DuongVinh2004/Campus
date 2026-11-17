"""The paid-ledger writer lease works on Windows and Linux: exactly one process holds it (stdlib only, runs under WSL too)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.public_rag_ledger import PaidLedgerWriterLease  # noqa: E402

PROBE = ("import sys; sys.path.insert(0, sys.argv[1]); from scripts.public_rag_ledger import PaidLedgerWriterLease; "
         "from pathlib import Path\n"
         "try:\n    lease = PaidLedgerWriterLease(Path(sys.argv[2])); print('ACQUIRED')\n"
         "except (OSError, ValueError, RuntimeError) as error:\n    print('REFUSED', type(error).__name__)\n")


class LedgerLeaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix=".lease-test-", dir=ROOT))
        self.path = self.directory / "paid-ledger-writer.lock"

    def tearDown(self):
        for item in self.directory.glob("*"):
            item.unlink()
        self.directory.rmdir()

    def other_process(self):
        return subprocess.run([sys.executable, "-B", "-c", PROBE, str(ROOT), str(self.path)], capture_output=True, text=True,
                              timeout=60).stdout.split()[0]

    def test_second_process_is_refused_while_the_first_holds_the_lease(self):
        lease = PaidLedgerWriterLease(self.path)
        try:
            self.assertEqual(self.other_process(), "REFUSED")
        finally:
            lease.close()

    def test_lease_can_be_taken_again_after_release(self):
        PaidLedgerWriterLease(self.path).close()
        self.assertEqual(self.other_process(), "ACQUIRED")

    def test_lease_is_freed_when_the_holder_exits(self):
        holder = subprocess.Popen([sys.executable, "-B", "-c", PROBE.replace("print('ACQUIRED')", "print('ACQUIRED', flush=True); sys.stdin.readline()"),
                                   str(ROOT), str(self.path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.assertEqual(holder.stdout.readline().split()[0], "ACQUIRED")
        self.assertEqual(self.other_process(), "REFUSED")
        holder.stdin.write("\n"); holder.stdin.flush(); holder.wait(timeout=30)
        self.assertEqual(self.other_process(), "ACQUIRED")

    def test_lease_outside_the_workspace_and_foreign_file_are_refused(self):
        with self.assertRaises(ValueError):
            PaidLedgerWriterLease(Path(tempfile.gettempdir()) / "lease.lock")
        self.path.write_bytes(b"not the marker")
        with self.assertRaises(ValueError):
            PaidLedgerWriterLease(self.path)


if __name__ == "__main__":
    unittest.main()

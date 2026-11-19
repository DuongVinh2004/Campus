"""Real PDF children resolve the parent's reviewed vendor dependency path."""
import hashlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from campus247.domain.learning import LearningError
from campus247.infrastructure.learning.blob import LearningBlobStore

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "infra/local/learning-materials-20261104-01/blobs/01a1a77e-b294-793e-8809-6fe4e504f936.pdf"


class PdfSubprocessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = ROOT / "infra/local/chrome-audit-20261109-01" / ("pdf-test-" + uuid4().hex)
        self.assertTrue(self.directory.resolve().is_relative_to(ROOT))
        self.directory.mkdir(exist_ok=False)
        self.key = "019a0000-0000-7000-8000-000000000001.pdf"
        self.raw = FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), "a26214e1c1dd1a81bdd4e96fec4af380d84ad53edf4c47a1b6fe56f2435c7c40")
        with (self.directory / self.key).open("xb") as stream:
            stream.write(self.raw)
        self.store = LearningBlobStore(self.directory, workspace=ROOT)

    async def test_real_children_read_valid_pdf_without_inherited_pythonpath(self):
        # pypdf remains available in this parent's sys.path; the child must
        # receive its vendor root explicitly rather than depend on shell state.
        with patch.dict(os.environ, {"AUDIT_SECRET": "synthetic-value"}):
            prior = os.environ.pop("PYTHONPATH", None)
            try:
                self.assertNotIn("AUDIT_SECRET", self.store._pdf_environment())
                self.assertEqual(await self.store.inspect(self.key), {"page_count": 3, "has_text_layer": True})
                self.assertIn("SQL JOIN", await self.store.extract_page(self.key, 2))
                self.assertEqual(await self.store._web_view(self.key), {"optimized": False, "reason": "SMALL_PAGE_TREE"})
            finally:
                if prior is not None:
                    os.environ["PYTHONPATH"] = prior
        self.assertEqual((self.directory / self.key).read_bytes(), self.raw)
        self.assertEqual(FIXTURE.read_bytes(), self.raw)

    async def test_missing_pdf_dependency_is_service_unavailable(self):
        with patch("campus247.infrastructure.learning.blob.importlib.util.find_spec", return_value=None), self.assertRaises(LearningError) as failure:
            await self.store.inspect(self.key)
        self.assertEqual((failure.exception.status, failure.exception.code), (503, "PDF_PROCESSOR_UNAVAILABLE"))

    async def test_invalid_pdf_remains_rejected_and_retained(self):
        invalid = "019a0000-0000-7000-8000-000000000002.pdf"
        with (self.directory / invalid).open("xb") as stream:
            stream.write(b"%PDF-1.7\ninvalid synthetic document\n")
        with self.assertRaises(LearningError) as failure:
            await self.store.inspect(invalid)
        self.assertEqual((failure.exception.status, failure.exception.code), (422, "INVALID_PDF"))
        self.assertTrue((self.directory / invalid).is_file())

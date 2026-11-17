"""Exclusive immutable blob writes and bounded scanning/inspection."""
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from campus247.domain.learning import LearningError, require
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.learning.metrics import record
from campus247.ports.learning_rendition import PDF_MEDIA_TYPE, PPTX_MEDIA_TYPE


from campus247.application.learning.scanner import UnavailableScanner  # noqa: E402,F401 -- the default scanner lives in the application layer


class FixtureHashScanner:
    """Only explicitly enumerated synthetic bytes, never a real malware scanner."""
    name = "synthetic_fixture_hash_allowlist"

    def __init__(self, hashes):
        self.hashes = frozenset(hashes)

    async def scan(self, path):
        def checksum():
            with path.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").hexdigest()
        digest = await asyncio.to_thread(checksum)
        require(digest in self.hashes, 503, "SCANNER_UNAVAILABLE", "Chỉ fixture tổng hợp đã chỉ định được kiểm tra trong chế độ này.")


class ClamAVScanner:
    name = "clamav"

    def __init__(self, executable: Path, *, database_dir: Path, temporary_dir: Path, cvd_certs_dir: Path | None = None):
        self.executable = executable.resolve(strict=True)
        self.database_dir = database_dir.resolve(strict=True)
        self.temporary_dir = temporary_dir.resolve(strict=True)
        self.cvd_certs_dir = cvd_certs_dir.resolve(strict=True) if cvd_certs_dir else None
        require(self.executable.is_file() and self.database_dir.is_dir() and self.temporary_dir.is_dir(), 503, "SCANNER_UNAVAILABLE", "Đường dẫn bộ quét chưa được cấu hình.")
        require((self.database_dir / "daily.cvd").is_file() or (self.database_dir / "daily.cld").is_file(), 503, "SCANNER_UNAVAILABLE", "Chưa có dữ liệu nhận diện mã độc.")

    async def scan(self, path):
        arguments = [str(self.executable), "--no-summary", "--database=" + str(self.database_dir), "--tempdir=" + str(self.temporary_dir), "--leave-temps", "--alert-exceeds-max=yes", "--alert-encrypted=yes", "--max-filesize=50M", "--max-scansize=150M", "--max-recursion=10", "--max-files=1000"]
        if self.cvd_certs_dir:
            arguments.append("--cvdcertsdir=" + str(self.cvd_certs_dir))
        arguments.extend(["--", str(path)])
        process = await asyncio.create_subprocess_exec(*arguments, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            code = await asyncio.wait_for(process.wait(), 90)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise LearningError(503, "SCANNER_UNAVAILABLE", "Bộ quét tệp quá thời gian.") from None
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        require(code == 0, 422 if code == 1 else 503, "FILE_REJECTED" if code == 1 else "SCANNER_UNAVAILABLE", "Tệp chưa vượt qua kiểm tra an toàn.")


class LearningBlobStore:
    def _pdf_environment(self):
        # The local launcher adds reviewed vendor packages to the parent's
        # sys.path. A fresh Python child does not inherit that runtime path.
        spec = importlib.util.find_spec("pypdf")
        require(spec is not None and spec.origin is not None, 503, "PDF_PROCESSOR_UNAVAILABLE", "Bộ xử lý PDF chưa sẵn sàng.")
        package = Path(spec.origin).resolve()
        require(package.is_file() and package.parent.name == "pypdf", 503, "PDF_PROCESSOR_UNAVAILABLE", "Bộ xử lý PDF chưa sẵn sàng.")
        environment = {name: value for name, value in os.environ.items()
            if name.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "LANG", "LC_ALL"}}
        environment.update(PYTHONPATH=str(package.parent.parent),
            PYTHONDONTWRITEBYTECODE="1", TEMP=str(self.root), TMP=str(self.root))
        return environment

    def __init__(self, root: Path, *, workspace: Path, max_bytes=50 * 1024**2, max_total_bytes=10 * 1024**3):
        self.workspace = workspace.resolve(strict=True)
        self.root = root.resolve(strict=True)
        require(self.root.is_relative_to(self.workspace) and self.root != self.workspace, 503, "INVALID_STORAGE", "Thư mục tệp học liệu không hợp lệ.")
        self.max_bytes = max_bytes
        require(type(max_total_bytes) is int and max_total_bytes >= max_bytes, 503, "INVALID_STORAGE_QUOTA", "Hạn mức kho học liệu không hợp lệ.")
        self.max_total_bytes = max_total_bytes
        self._capacity_lock = asyncio.Lock()
        self._reserved_bytes = 0
        self._verified = {}

    def bytes_used(self):
        total = 0
        for entry in self.root.iterdir():
            require(not entry.is_symlink() and not getattr(entry, 'is_junction', lambda: False)(), 503, "INVALID_STORAGE", "Kho tệp có liên kết chưa được xác minh.")
            if entry.is_file():
                total += entry.stat().st_size
        return total

    def path(self, key):
        require(bool(re.fullmatch(r"[0-9a-f-]{36}\.(pdf|pptx)", str(key))), 404)
        candidate = self.root / key
        require(candidate.resolve().parent == self.root and not candidate.is_symlink(), 503, "INVALID_STORAGE", "Đường dẫn tệp không hợp lệ.")
        require(self.root.resolve(strict=True) == self.root, 503, "INVALID_STORAGE", "Thư mục tệp đã thay đổi.")
        return candidate

    @asynccontextmanager
    async def capacity(self, expected_size):
        async with self._capacity_lock:
            remaining = self.max_total_bytes - await asyncio.to_thread(self.bytes_used) - self._reserved_bytes
            require(expected_size <= remaining, 413, "STORAGE_QUOTA_EXCEEDED", "Kho học liệu đã đạt hạn mức; không có tệp nào được dọn tự động.")
            self._reserved_bytes += expected_size
            record("learning.storage_capacity", available_bytes=remaining - expected_size)
        try:
            yield
        finally:
            async with self._capacity_lock:
                self._reserved_bytes -= expected_size

    async def receive(self, chunks, *, expected_size, content_type=PDF_MEDIA_TYPE):
        async with self.capacity(expected_size):
            return await self._receive(chunks, expected_size=expected_size, content_type=content_type)

    async def _receive(self, chunks, *, expected_size, content_type=PDF_MEDIA_TYPE):
        require(content_type in {PDF_MEDIA_TYPE, PPTX_MEDIA_TYPE}, 415, 'UNSUPPORTED_MEDIA_TYPE', 'Định dạng học liệu chưa được hỗ trợ.')
        key = generate_uuid7() + ('.pptx' if content_type == PPTX_MEDIA_TYPE else '.pdf')
        path = self.path(key)
        count, digest, prefix = 0, hashlib.sha256(), b""
        with path.open("xb") as output:
            async for chunk in chunks:
                if not chunk:
                    continue
                count += len(chunk)
                require(count <= self.max_bytes and count <= expected_size, 413, "PAYLOAD_TOO_LARGE", "Tệp vượt kích thước được cho phép.")
                prefix = (prefix + chunk)[:8]
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        require(count > 0 and count == expected_size, 422, "SIZE_MISMATCH", "Số byte nhận khác dung lượng đã khai báo.")
        require(prefix.startswith(b'PK\x03\x04') if content_type == PPTX_MEDIA_TYPE else prefix.startswith(b'%PDF-'),
            415, 'UNSUPPORTED_MEDIA_TYPE', 'Nội dung tệp không khớp định dạng đã khai báo.')
        return {"storage_key": key, "byte_size": count, "sha256": digest.hexdigest()}

    async def import_pdf(self, source: Path, *, expected_sha256, expected_size):
        source = Path(source).absolute()
        require(source.resolve(strict=True).is_relative_to(self.workspace), 503, 'RENDITION_PATH_INVALID', 'Bản xem nằm ngoài kho được cấu hình.')
        cursor = source
        while cursor != self.workspace:
            require(not cursor.is_symlink() and not getattr(cursor, 'is_junction', lambda: False)(), 503, 'RENDITION_PATH_INVALID', 'Đường dẫn bản xem chưa được xác minh.')
            cursor = cursor.parent
        require(source.is_file() and source.stat().st_size == expected_size and 0 < expected_size <= self.max_bytes,
            422, 'RENDITION_SIZE_INVALID', 'Bản xem vượt giới hạn hoặc chưa đầy đủ.')
        async def chunks():
            with source.open('rb') as stream:
                while block := stream.read(65536):
                    yield block
        result = await self.receive(chunks(), expected_size=expected_size)
        require(result['sha256'] == expected_sha256, 503, 'RENDITION_HASH_MISMATCH', 'Bản xem thay đổi trong khi tiếp nhận.')
        return result

    async def web_view(self, key):
        try:
            async with self.capacity(self.max_bytes):
                return await self._web_view(key)
        except LearningError as error:
            if error.code == 'STORAGE_QUOTA_EXCEEDED':
                return {'optimized': False, 'reason': 'STORAGE_QUOTA'}
            raise

    async def _web_view(self, key):
        source = self.path(key)
        if await asyncio.to_thread(self.bytes_used) + self.max_bytes > self.max_total_bytes:
            return {"optimized": False, "reason": "STORAGE_QUOTA"}
        view_key = generate_uuid7() + '.pdf'
        destination = self.path(view_key)
        helper = Path(__file__).with_name('pdf_layout.py')
        environment = self._pdf_environment()
        process = await asyncio.create_subprocess_exec(sys.executable, '-B', str(helper),
            str(source), str(destination), str(self.workspace), env=environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), 45)
        except TimeoutError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise LearningError(503, 'PDF_VIEW_TIMEOUT', 'Quá thời gian chuẩn bị bản PDF xem.') from None
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        require(process.returncode == 0 and len(stdout) <= 4096, 422, 'PDF_VIEW_INVALID', 'Chưa xác minh được bản PDF tối ưu để đọc.')
        result = json.loads(stdout)
        if result.get('optimized'):
            require(destination.is_file() and destination.stat().st_size <= self.max_bytes, 413, 'PDF_VIEW_TOO_LARGE', 'Bản PDF xem vượt hạn mức.')
            result['storage_key'] = view_key
        return result

    async def inspect(self, key):
        path = self.path(key)
        script = """import json,sys
from pypdf import PdfReader
r=PdfReader(sys.argv[1],strict=True)
if r.is_encrypted: raise ValueError('encrypted')
n=len(r.pages)
if not 0<n<=500: raise ValueError('page_count')
has_text=any(bool((r.pages[i].extract_text() or '').strip()) for i in range(min(n,10)))
print(json.dumps({'page_count':n,'has_text_layer':has_text}))
"""
        process = await asyncio.create_subprocess_exec(sys.executable, "-B", "-c", script, str(path), env=self._pdf_environment(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), 45)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise LearningError(422, "PDF_TIMEOUT", "Không xử lý được PDF trong thời gian cho phép.") from None
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        require(process.returncode == 0 and len(stdout) < 2048, 422, "INVALID_PDF", "PDF hỏng, có mật khẩu hoặc vượt giới hạn 500 trang.")
        return json.loads(stdout)

    async def verify(self, key, sha256, size):
        path = self.path(key)
        stat = path.stat()
        signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        require(stat.st_size == size, 503, "BLOB_CORRUPTED", "Tệp học liệu không đầy đủ.")
        if self._verified.get((key, sha256)) == signature:
            return
        def checksum():
            with path.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").hexdigest()
        actual = await asyncio.to_thread(checksum)
        require(actual == sha256, 503, "BLOB_CORRUPTED", "Tệp học liệu không khớp bản đã công bố.")
        require(path.stat().st_mtime_ns == stat.st_mtime_ns, 503, "BLOB_CHANGED", "Tệp học liệu thay đổi trong khi kiểm tra.")
        self._verified[(key, sha256)] = signature

    async def extract_page(self, key, page_no):
        script = """import json,sys
from pypdf import PdfReader
r=PdfReader(sys.argv[1],strict=True)
p=int(sys.argv[2])-1
if r.is_encrypted or not 0<=p<len(r.pages): raise ValueError('page')
print(json.dumps((r.pages[p].extract_text() or '')[:10000]))
"""
        process = await asyncio.create_subprocess_exec(sys.executable, "-B", "-c", script, str(self.path(key)), str(page_no), env=self._pdf_environment(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), 15)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise LearningError(503, "SOURCE_UNAVAILABLE", "Chưa đọc được chữ của trang.") from None
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        require(process.returncode == 0 and len(stdout) <= 80000, 503, "SOURCE_UNAVAILABLE", "Chưa đọc được nguồn trang.")
        return json.loads(stdout)

    async def chunks(self, key, start, length):
        with self.path(key).open("rb") as stream:
            stream.seek(start)
            remaining = length
            while remaining:
                data = stream.read(min(65536, remaining))
                require(bool(data), 503, "BLOB_UNAVAILABLE", "Nội dung học liệu không đầy đủ.")
                remaining -= len(data)
                yield data

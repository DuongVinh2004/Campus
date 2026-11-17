"""Windows adapter for a task-owned, network-isolated WSL/bubblewrap converter."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path, PureWindowsPath

from campus247_worker.learning.pptx import (
    PptxConversionError,
    ProcessResult,
    SandboxJob,
)


def linux_path(path: Path, workspace: Path):
    path = Path(path).absolute()
    workspace = workspace.resolve(strict=True)
    if '..' in path.parts or path.resolve(strict=True) == workspace or not path.resolve(strict=True).is_relative_to(workspace):
        raise PptxConversionError('PPTX_SANDBOX_PATH_INVALID')
    for parent in (path, *path.parents):
        if parent.is_symlink() or getattr(parent, 'is_junction', lambda: False)():
            raise PptxConversionError('PPTX_SANDBOX_PATH_INVALID')
        if parent == workspace:
            break
    parsed = PureWindowsPath(path)
    if not re.fullmatch(r'[A-Za-z]:', parsed.drive):
        raise PptxConversionError('PPTX_SANDBOX_PATH_INVALID')
    return '/mnt/' + parsed.drive[0].lower() + '/' + '/'.join(parsed.parts[1:])


class WslBubblewrapExecutor:
    network_disabled = True
    resource_limits_enforced = True

    def __init__(self, *, workspace: Path, runtime_root: Path, converter_sha256: str,
                 bwrap_sha256: str, distribution='Ubuntu', wsl_executable=Path('C:/Windows/System32/wsl.exe')):
        self.workspace = workspace.resolve(strict=True)
        self.runtime_root = runtime_root.resolve(strict=True)
        self.supervisor = Path(__file__).with_name('wsl_supervisor.py').resolve(strict=True)
        self.wsl_executable = wsl_executable.resolve(strict=True)
        self.converter_sha256, self.bwrap_sha256 = converter_sha256, bwrap_sha256
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', distribution) or any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in (converter_sha256, bwrap_sha256)):
            raise PptxConversionError('PPTX_SANDBOX_CONFIGURATION_INVALID')
        self.distribution = distribution
        linux_path(self.runtime_root, self.workspace)
        linux_path(self.supervisor, self.workspace)
        binary = self.runtime_root / 'usr/lib/libreoffice/program/soffice.bin'
        with binary.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != converter_sha256:
                raise PptxConversionError('PPTX_CONVERTER_HASH_MISMATCH')
        self._active = {}

    async def run(self, job: SandboxJob):
        scope = job.cwd.resolve(strict=True)
        linux_scope = linux_path(scope, self.workspace)
        if (job.network_allowed or not job.source_path.resolve(strict=True).is_relative_to(scope)
            or not job.output_directory.resolve(strict=True).is_relative_to(scope)
            or Path(job.command[0]).resolve(strict=True) != self.runtime_root / 'usr/lib/libreoffice/program/soffice.bin'):
            raise PptxConversionError('PPTX_SANDBOX_JOB_SCOPE_MISMATCH')
        profile = scope / 'office-profile'
        request = {'runtime_root': linux_path(self.runtime_root, self.workspace),
            'source_path': linux_path(job.source_path, self.workspace),
            'output_directory': linux_path(job.output_directory, self.workspace),
            'profile_directory': linux_path(profile, self.workspace), 'limits': asdict(job.limits),
            'converter_sha256': self.converter_sha256, 'bwrap_sha256': self.bwrap_sha256}
        request_path = scope / 'sandbox-request.json'
        with request_path.open('x', encoding='utf-8') as stream:
            json.dump(request, stream)
        process = await asyncio.create_subprocess_exec(str(self.wsl_executable), '-d', self.distribution,
            '--exec', '/usr/bin/python3', '-B', linux_path(self.supervisor, self.workspace),
            '--request', linux_scope + '/sandbox-request.json',
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        communication = asyncio.create_task(process.communicate())
        self._active[str(scope)] = (process, communication)
        try:
            stdout, _ = await asyncio.wait_for(asyncio.shield(communication), job.limits.timeout_seconds + 30)
            if process.returncode != 0 or len(stdout) > 8192:
                raise PptxConversionError('PPTX_SANDBOX_UNAVAILABLE')
            try:
                result = json.loads(stdout)
            except (ValueError, TypeError):
                raise PptxConversionError('PPTX_SANDBOX_UNAVAILABLE') from None
            reason = result.get('reason')
            if reason:
                if not re.fullmatch(r'PPTX_[A-Z_]{1,60}', str(reason)):
                    reason = 'PPTX_SANDBOX_UNAVAILABLE'
                raise PptxConversionError(reason)
            if not all(result.get(key) is True for key in ('network_disabled', 'resource_limits_enforced', 'owned_tree_terminated')):
                raise PptxConversionError('PPTX_SANDBOX_UNVERIFIED')
            return ProcessResult(result.get('returncode', 1))
        except (asyncio.CancelledError, TimeoutError):
            await asyncio.shield(self.cancel(job))
            raise
        finally:
            if process.returncode is not None:
                self._active.pop(str(scope), None)

    async def cancel(self, job):
        scope = job.cwd.resolve(strict=True)
        linux_path(scope, self.workspace)
        active = self._active.get(str(scope))
        if active is None:
            return
        marker = scope / 'cancel-request.json'
        if not marker.exists():
            with marker.open('x', encoding='utf-8') as stream:
                json.dump({'cancel_owned_job': scope.name}, stream)
        process, communication = active
        try:
            stdout, _ = await asyncio.wait_for(asyncio.shield(communication), 15)
        except TimeoutError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise PptxConversionError('PPTX_SANDBOX_CANCEL_UNVERIFIED') from None
        try:
            if json.loads(stdout).get('owned_tree_terminated') is not True:
                raise ValueError('Owned tree was not verified')
        except (ValueError, TypeError, AttributeError):
            raise PptxConversionError('PPTX_SANDBOX_CANCEL_UNVERIFIED') from None

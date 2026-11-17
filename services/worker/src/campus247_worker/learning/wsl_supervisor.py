"""Linux-side owned converter supervision; invoked by the Windows WSL adapter.

Only runtime/system files are mounted read-only. The original input is mounted
read-only and only this job's output/profile directories are writable. No host
home, workspace, WSL interop socket or network namespace is exposed to converter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import stat
import subprocess
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve(strict=True).parents[5]


def checked(value, *, directory=False):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or not path.is_relative_to(WORKSPACE):
        raise ValueError('PPTX_SANDBOX_PATH_INVALID')
    resolved = path.resolve(strict=True)
    if resolved == WORKSPACE or not resolved.is_relative_to(WORKSPACE):
        raise ValueError('PPTX_SANDBOX_PATH_INVALID')
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError('PPTX_SANDBOX_PATH_INVALID')
        if parent == WORKSPACE:
            break
    if directory != resolved.is_dir():
        raise ValueError('PPTX_SANDBOX_PATH_INVALID')
    return resolved


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def merged_mounts(host, extra, destination, runtime):
    """Construct a read-only union without overlayfs or host filesystem writes."""
    result = ['--dir', destination]
    names = {p.name for p in host.iterdir()} | {p.name for p in extra.iterdir()}
    for name in sorted(names):
        original, addition = host / name, extra / name
        target = destination + '/' + name
        if name.startswith('libuno_') and addition.is_file() and (runtime / 'usr/lib/libreoffice/program' / name).is_file():
            result += ['--symlink', '../libreoffice/program/' + name, target]
        elif original.is_dir() and addition.is_dir() and not original.is_symlink():
            result += merged_mounts(original, addition, target, runtime)
        else:
            selected = addition if addition.exists() else original
            if selected.exists():
                result += ['--ro-bind', str(selected), target]
    if len(result) > 25000:
        raise ValueError('PPTX_SANDBOX_MOUNT_LIMIT')
    return result


def sandbox_command(runtime, profile, output, source):
    mounts = merged_mounts(Path('/usr/lib'), runtime / 'usr/lib', '/usr/lib', runtime)
    for name in ('bin', 'sbin', 'libexec', 'lib64'):
        if Path('/usr', name).exists():
            mounts += ['--ro-bind', '/usr/' + name, '/usr/' + name]
    for name in ('fonts', 'fontconfig', 'mime', 'locale', 'zoneinfo', 'glib-2.0'):
        if Path('/usr/share', name).exists():
            mounts += ['--ro-bind', '/usr/share/' + name, '/usr/share/' + name]
    mounts += ['--ro-bind', str(runtime / 'usr/share/libreoffice'), '/usr/share/libreoffice']
    return ['/usr/bin/bwrap', '--unshare-all', '--new-session', '--die-with-parent', '--cap-drop', 'ALL',
        *mounts, '--symlink', 'usr/bin', '/bin', '--symlink', 'usr/sbin', '/sbin',
        '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
        '--ro-bind', '/etc/passwd', '/etc/passwd', '--ro-bind', '/etc/group', '/etc/group',
        '--ro-bind', '/etc/fonts', '/etc/fonts', '--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache',
        '--ro-bind', str(runtime / 'etc/libreoffice'), '/etc/libreoffice',
        '--ro-bind', str(source), '/input/source.pptx', '--bind', str(profile), '/profile', '--bind', str(output), '/output',
        '--size', str(64 * 1024**2), '--tmpfs', '/tmp', '--clearenv', '--setenv', 'HOME', '/profile',
        '--setenv', 'XDG_CONFIG_HOME', '/profile', '--setenv', 'XDG_CACHE_HOME', '/profile/cache',
        '--setenv', 'LD_LIBRARY_PATH', '/usr/lib/libreoffice/program:/usr/lib/x86_64-linux-gnu:/usr/lib',
        '--setenv', 'SAL_USE_VCLPLUGIN', 'svp', '--setenv', 'LC_ALL', 'C.UTF-8', '--chdir', '/output',
        # The packaged launcher owns normal first-profile initialization/restarts.
        '/usr/lib/libreoffice/program/soffice', '-env:UserInstallation=file:///profile', '--headless', '--nologo',
        '--nodefault', '--convert-to', 'pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}',
        '--outdir', '/output', '/input/source.pptx']


def process_tree(root_pid):
    found, pending = {}, [(root_pid, os.getpid())]
    while pending and len(found) <= 256:
        pid, parent_pid = pending.pop()
        if pid in found:
            continue
        try:
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[1]) != parent_pid:
                continue
            found[pid] = {'started': fields[19], 'cpu': sum(int(fields[i]) for i in (11, 12, 13, 14)), 'rss': int(fields[21]) * os.sysconf('SC_PAGE_SIZE')}
            for task in Path(f'/proc/{pid}/task').iterdir():
                try:
                    pending += [(int(value), pid) for value in (task / 'children').read_text().split()]
                except (FileNotFoundError, ProcessLookupError):
                    continue
        except (FileNotFoundError, ProcessLookupError):
            continue
    return found


def stop_owned(process, observed):
    if process.poll() is None:
        observed.update(process_tree(process.pid))
        process.kill()
    for pid, record in observed.items():
        try:
            fd = os.pidfd_open(pid)
            try:
                fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
                if fields[19] == record['started'] and fields[0] != 'Z':
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
            finally:
                os.close(fd)
        except (FileNotFoundError, ProcessLookupError):
            pass
    process.wait(timeout=5)
    deadline = time.monotonic() + 5
    while any(owned_process_live(pid, record['started']) for pid, record in observed.items()):
        if time.monotonic() >= deadline:
            raise ValueError('PPTX_SANDBOX_CANCEL_UNVERIFIED')
        time.sleep(0.02)


def owned_process_live(pid, started):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return fields[19] == started and fields[0] != 'Z'
    except (FileNotFoundError, ProcessLookupError):
        return False


def writable_usage(directories):
    size, files = 0, 0
    for directory in directories:
        for entry in directory.rglob('*'):
            try:
                info = entry.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode):
                raise ValueError('PPTX_SANDBOX_OUTPUT_LINK')
            if stat.S_ISREG(info.st_mode):
                size += info.st_size
                files += 1
    return size, files


def native_launcher(limits):
    """Apply kernel limits and drop privileges for this child only."""
    return ['/usr/bin/prlimit', '--core=0', '--as=' + str(limits['memory_mib'] * 1024**2),
        '--cpu=' + str(limits['cpu_seconds']), '--fsize=' + str(limits['max_output_bytes']), '--nofile=256', '--nproc=64',
        '--', '/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', '--no-new-privs', '--']


def execute(request_path):
    request_path = checked(request_path)
    scope = request_path.parent
    request = json.loads(request_path.read_text())
    runtime = checked(request['runtime_root'], directory=True)
    source = checked(request['source_path'])
    output = checked(request['output_directory'], directory=True)
    profile = checked(request['profile_directory'], directory=True)
    if not all(path.is_relative_to(scope) for path in (source, output, profile)):
        raise ValueError('PPTX_SANDBOX_JOB_SCOPE_MISMATCH')
    limits = request['limits']
    if any(type(value) is not int or value <= 0 for value in limits.values()):
        raise ValueError('PPTX_SANDBOX_LIMIT_INVALID')
    if limits['timeout_seconds'] > 120 or limits['memory_mib'] > 1024 or limits['cpu_seconds'] > 90 or limits['max_output_bytes'] > 50 * 1024**2:
        raise ValueError('PPTX_SANDBOX_LIMIT_INVALID')
    if checksum(runtime / 'usr/lib/libreoffice/program/soffice.bin') != request['converter_sha256'] or checksum(Path('/usr/bin/bwrap')) != request['bwrap_sha256']:
        raise ValueError('PPTX_SANDBOX_BINARY_CHANGED')
    command = sandbox_command(runtime, profile, output, source)
    process = subprocess.Popen(native_launcher(limits) + command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, start_new_session=True)
    started, observed = time.monotonic(), {}
    peak_rss, peak_cpu, reason = 0, 0.0, None
    try:
        while process.poll() is None:
            current = process_tree(process.pid)
            observed.update(current)
            rss = sum(row['rss'] for row in current.values())
            cpu = sum(row['cpu'] for row in current.values()) / os.sysconf('SC_CLK_TCK')
            peak_rss, peak_cpu = max(peak_rss, rss), max(peak_cpu, cpu)
            bytes_written, files_written = writable_usage((output, profile))
            if (scope / 'cancel-request.json').exists():
                reason = 'PPTX_SANDBOX_CANCELLED'
            elif time.monotonic() - started > limits['timeout_seconds']:
                reason = 'PPTX_CONVERSION_TIMEOUT'
            elif rss > limits['memory_mib'] * 1024**2 or cpu > limits['cpu_seconds'] or len(current) > 64:
                reason = 'PPTX_SANDBOX_RESOURCE_LIMIT'
            elif bytes_written > limits['max_output_bytes'] + 64 * 1024**2 or files_written > 2000:
                reason = 'PPTX_SANDBOX_OUTPUT_LIMIT'
            if reason:
                break
            time.sleep(0.05)
    finally:
        stop_owned(process, observed)
    result = {'returncode': process.returncode, 'reason': reason, 'peak_aggregate_rss_bytes': peak_rss,
        'observed_cpu_seconds': peak_cpu, 'network_disabled': True, 'resource_limits_enforced': True,
        'wall_seconds': time.monotonic() - started, 'owned_process_count': len(observed), 'owned_tree_terminated': True}
    with (scope / 'sandbox-result.json').open('x') as out:
        json.dump(result, out, indent=2)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.request)))
    except (ValueError, OSError, subprocess.SubprocessError):
        print(json.dumps({'returncode': 1, 'reason': 'PPTX_SANDBOX_UNAVAILABLE'}))
        raise SystemExit(1) from None

"""Optional local converters, isolated profiles and explicit conversion provenance."""
import os
import platform
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile


PLATFORM = sys.platform
TARGETS = {'.doc': 'docx', '.xls': 'xlsx', '.wps': 'docx', '.et': 'xlsx', '.dps': 'pptx'}


def run_tool(argv, timeout=60):
    """Capture output; kill and reap the process (and POSIX group) on timeout."""
    options = {'start_new_session': True} if os.name != 'nt' else {}
    with subprocess.Popen([str(a) for a in argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name != 'nt':
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                # taskkill is local OS process cleanup, never a shell or network call.
                killer = shutil.which('taskkill')
                try:
                    if killer:
                        subprocess.run([killer, '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=10)
                except (OSError, subprocess.SubprocessError):
                    pass
                finally:
                    if proc.poll() is None:
                        proc.kill()
            proc.communicate(timeout=10)
            raise TimeoutError(f'Converter timed out after {timeout:g}s; process terminated')
        if proc.returncode:
            raise RuntimeError(f'Tool exited {proc.returncode}: ' + stderr.decode('utf-8', errors='replace')[:2000])
        return stdout.decode('utf-8', errors='replace'), stderr.decode('utf-8', errors='replace')


def soffice_path():
    configured = os.environ.get('EVIDENCE_REVIEWER_SOFFICE')
    if configured:
        resolved = shutil.which(configured) or (str(Path(configured).expanduser().resolve()) if Path(configured).expanduser().is_file() else None)
        return resolved
    # Prefer the console binary on Windows, to wait for conversion completion.
    return (shutil.which('soffice.com') if PLATFORM == 'win32' else None) or shutil.which('soffice')


def convert(path, cache, target, provenance, timeout=60):
    from .readers import digest
    path, cache = Path(path), Path(cache)
    output = cache / ('converted.' + target)
    tools = []
    if path.suffix.lower() == '.doc' and PLATFORM == 'darwin':
        tools.append(('textutil', shutil.which('textutil')))
    tools.append(('LibreOffice', soffice_path()))
    for name, executable in tools:
        record = dict(method=name + ' ' + path.suffix.lower() + '-to-' + target,
                      converter=name, executable=executable, version=None, parameters=[],
                      parent_sha256=digest(path), state='tool_unavailable', errors=[])
        provenance.append(record)
        if not executable:
            record['errors'] = ['Converter executable unavailable; no fallback was silently assumed']
            continue
        try:
            with tempfile.TemporaryDirectory(prefix='evidence-convert-') as temporary:
                tmp = Path(temporary).resolve()
                profile = tmp / 'profile'
                # Even version probes get the isolated LibreOffice profile.
                probe = ([executable, '-help'] if name == 'textutil' else
                         [executable, '-env:UserInstallation=' + profile.as_uri(), '--version'])
                record.update(version_parameters=probe[1:], timeout_seconds=timeout, executable_sha256=digest(Path(executable)))
                version, _ = run_tool(probe, timeout=min(timeout, 10))
                record['version'] = ('macOS ' + platform.mac_ver()[0] + ' system textutil; separate utility version not exposed'
                                     if name == 'textutil' else version.splitlines()[0] if version.strip() else 'version_not_reported')
                local = tmp / ('input' + path.suffix.lower())
                shutil.copyfile(path, local)
                if name == 'textutil':
                    produced = tmp / ('converted.' + target)
                    argv = [executable, '-convert', target, '-output', str(produced), str(local)]
                else:
                    produced = tmp / ('input.' + target)
                    argv = [executable, '-env:UserInstallation=' + profile.as_uri(), '--headless',
                            '--convert-to', target, '--outdir', str(tmp), str(local)]
                record['parameters'] = argv[1:]
                stdout, stderr = run_tool(argv, timeout=timeout)
                record.update(stdout=stdout[:2000], stderr=stderr[:2000])
                if not produced.is_file() or not produced.stat().st_size:
                    raise ValueError('Converter returned without a nonempty output file')
                shutil.copyfile(produced, output)
            record.update(state='converted', artifact=str(output), sha256=digest(output))
            return output
        except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as exc:
            record.update(state='failed', errors=[f'{type(exc).__name__}: {exc}'])
            output.unlink(missing_ok=True)
    raise ValueError('No successful conversion; see processing attempts for failed/tool_unavailable details')

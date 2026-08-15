import logging
import os
import platform
import sys
import tempfile

import requests

logger = logging.getLogger(__name__)

VERSION = "0.0.0"
UPDATE_URL = "https://smalnets.ddns.net/api/v1/latest-release"


def _is_compiled() -> bool:
    return getattr(sys, 'frozen', False)


def get_current_version() -> str:
    for candidate in _version_file_candidates():
        try:
            with open(candidate) as f:
                version = f.read().strip()
                if version:
                    return version
        except Exception:
            pass
    try:
        import subprocess
        tag = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if tag:
            return tag.lstrip('v')
    except Exception:
        pass
    return VERSION


def _version_file_candidates() -> list:
    if _is_compiled():
        exe_dir = os.path.dirname(sys.executable)
        return [os.path.join(exe_dir, 'version.txt')]
    cwd = os.getcwd()
    mod_dir = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(cwd, 'version.txt'),
        os.path.join(cwd, 'config_program', 'version.txt'),
        os.path.join(mod_dir, '..', 'version.txt'),
    ]


def _detect_platform_key() -> str | None:
    system = platform.system().lower()
    if system == 'windows':
        return 'windows'
    if system == 'darwin':
        return 'macos'
    if system == 'linux':
        try:
            import distro
            distro_id = distro.id().lower()
        except ImportError:
            distro_id = ''
        if any(d in distro_id for d in ['ubuntu', 'debian']):
            return 'linux_deb'
        if any(d in distro_id for d in ['fedora', 'rhel', 'centos']):
            return 'linux_rpm'
        return 'linux_deb'
    return None


def check_for_updates() -> dict | None:
    """Check for updates. Returns release info dict or None if no update."""
    try:
        resp = requests.get(UPDATE_URL, timeout=10)
        if resp.status_code != 200:
            logger.warning(f'Update check failed: HTTP {resp.status_code}')
            return None
        data = resp.json()
        latest = data.get('version', '')
        if not latest:
            return None
        if _compare_versions(latest, VERSION) <= 0:
            logger.info(f'Already up-to-date (v{VERSION})')
            return None
        platform_key = _detect_platform_key()
        download_info = data.get('downloads', {}).get(platform_key) if platform_key else None
        if not download_info:
            logger.warning(f'No download found for platform: {platform_key}')
            return None
        return {
            'version': latest,
            'download_url': download_info['url'],
            'file_name': download_info['name'],
            'release_url': data.get('release_url', ''),
        }
    except requests.RequestException as e:
        logger.warning(f'Update check network error: {e}')
        return None


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two semver strings. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
    parts1 = [int(p) for p in v1.split('.')]
    parts2 = [int(p) for p in v2.split('.')]
    for a, b in zip(parts1, parts2, strict=False):
        if a > b:
            return 1
        if a < b:
            return -1
    return 0


def download_update(download_url: str) -> str | None:
    """Download the update file to a temp location. Returns the local file path."""
    if not _is_compiled():
        logger.info('Not compiled, skipping download')
        return None
    try:
        logger.info(f'Downloading update from {download_url}')
        resp = requests.get(download_url, stream=True, timeout=120)
        if resp.status_code != 200:
            logger.error(f'Download failed: HTTP {resp.status_code}')
            return None
        suffix = os.path.splitext(download_url.split('/')[-1])[1] or '.exe'
        fd, tmp = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(tmp, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info(f'Downloaded update to {tmp.name}')
        return tmp.name
    except Exception as e:
        logger.error(f'Download error: {e}', exc_info=True)
        return None


def apply_update(download_path: str) -> bool:
    """Replace current executable with downloaded update."""
    if not _is_compiled():
        logger.info('Not compiled, cannot self-update')
        return False

    system = platform.system().lower()
    current_exe = sys.executable

    if system == 'windows':
        return _apply_windows(download_path, current_exe)
    logger.info('Self-update not supported on this platform. Manual install required.')
    return False


def _apply_windows(download_path: str, current_exe: str) -> bool:
    """Create a PowerShell script that replaces the exe and restarts."""
    script = f'''Start-Sleep -Seconds 1
Stop-Process -Name "{os.path.splitext(os.path.basename(current_exe))[0]}" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Move-Item -Force "{download_path}" "{current_exe}"
Start-Process "{current_exe}"
'''
    ps_path = os.path.join(tempfile.gettempdir(), 'smalnets_update.ps1')
    with open(ps_path, 'w') as f:
        f.write(script)
    os.startfile(ps_path) if hasattr(os, 'startfile') else None
    return True

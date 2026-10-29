"""Central application configuration.

The backend base URL (and bare domain) for Smalnets is defined here once and
imported everywhere it is needed, so it only has to be changed in a single
place.

Two environments are supported:

* **prod** (default) — ``https://smalnets.com``
* **dev** — ``https://smaldev.smalnets.com``

Compiled builds have the environment baked in by generating
``build_config.py`` (see ``build_linux.sh``, ``build_windows.bat`` and
``.github/workflows/build.yml``).

When running from source, the environment is picked at launch, highest
priority first:

1. the ``SMALNETS_ENV`` environment variable (``dev`` or ``prod``)
2. a ``.env`` file in the repository root containing ``SMALNETS_ENV=dev``
3. the generated ``build_config.py``, if present
4. ``prod``

``SMALNETS_BASE_URL`` overrides the URL for either environment (e.g. a local
backend). Compiled binaries ignore all of the above.
"""

import os
import sys
from pathlib import Path

ENVIRONMENT_URLS = {
    'prod': 'https://smalnets.com',
    'dev': 'https://smaldev.smalnets.com',
}

_ENV_ALIASES = {
    'prod': 'prod', 'production': 'prod', 'live': 'prod',
    'dev': 'dev', 'development': 'dev', 'test': 'dev',
}


def _read_dotenv() -> dict[str, str]:
    """Parse KEY=VALUE lines from the repository-root ``.env`` file."""
    path = Path(__file__).resolve().parent.parent / '.env'
    values: dict[str, str] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        values[key.strip()] = value.strip().strip('"\'')
    return values


def _resolve() -> tuple[str, str]:
    try:
        import build_config  # generated at build time
        built = (str(build_config.VARIANT), str(build_config.BASE_URL))
    except ImportError:
        built = ('prod', ENVIRONMENT_URLS['prod'])

    if getattr(sys, 'frozen', False):
        return built

    dotenv = _read_dotenv()
    raw_env = os.environ.get('SMALNETS_ENV') or dotenv.get('SMALNETS_ENV')
    base_url = os.environ.get('SMALNETS_BASE_URL') or dotenv.get('SMALNETS_BASE_URL')

    if raw_env:
        variant = _ENV_ALIASES.get(raw_env.strip().lower())
        if variant is None:
            raise SystemExit(
                f"Invalid SMALNETS_ENV '{raw_env}': use 'dev' or 'prod'."
            )
    else:
        variant = built[0]

    if base_url:
        return variant, base_url.rstrip('/')
    if raw_env:
        return variant, ENVIRONMENT_URLS[variant]
    return built


#: Active environment: 'dev' or 'prod'.
VARIANT, BASE_URL = _resolve()

#: Bare domain name (no scheme), derived from BASE_URL.
DOMAIN = BASE_URL.split('://', 1)[-1]

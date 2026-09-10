"""Central application configuration.

The backend base URL (and bare domain) for Smalnets is defined here once and
imported everywhere it is needed, so it only has to be changed in a single
place.

Two build variants are supported:

* **production** (default) — ``https://smalnets.com``
* **development** — ``https://smalnets.ddns.net``

The variant is selected at compile time by generating ``build_config.py``
(see ``build_linux.sh``, ``build_windows.bat`` and
``.github/workflows/build.yml``). When no ``build_config.py`` is present the
app falls back to the production URL, so a plain ``python3 config_program/main.py``
keeps working out of the box.
"""

try:
    from build_config import BASE_URL  # generated at build time
except ImportError:
    BASE_URL = 'https://smalnets.com'

#: Bare domain name (no scheme), derived from BASE_URL.
DOMAIN = BASE_URL.split('://', 1)[-1]

"""Central application configuration.

The backend base URL (and bare domain) for Smalnets is defined here once and
imported everywhere it is needed, so it only has to be changed in a single
place.
"""

#: Public base URL of the Smalnets backend this tool talks to.
BASE_URL = 'https://smalnets.com'

#: Bare domain name (no scheme), derived from BASE_URL.
DOMAIN = BASE_URL.split('://', 1)[-1]

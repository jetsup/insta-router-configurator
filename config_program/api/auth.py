import json
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TOKEN_FILE = Path.home() / '.smalnets_token'


class Auth:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.token: str | None = None
        self.user: dict | None = None
        self._load_token()

    def _token_path(self) -> Path:
        return TOKEN_FILE

    def _load_token(self):
        if self._token_path().exists():
            try:
                data = json.loads(self._token_path().read_text())
                self.token = data.get('token')
                self.base_url = data.get('base_url', self.base_url)
                logger.info(f'Loaded saved token for base_url={self.base_url}')
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f'Failed to load token file: {e}')
                pass

    def _save_token(self):
        self._token_path().write_text(json.dumps({
            'token': self.token,
            'base_url': self.base_url,
        }))
        logger.info(f'Saved token to {self._token_path()}')

    def _clear_token(self):
        if self._token_path().exists():
            self._token_path().unlink()
            logger.info('Cleared saved token')

    def verify_token(self) -> bool:
        if not self.token:
            logger.info('No saved token to verify')
            return False
        logger.info(f'Verifying saved token against {self.base_url}/api/v1/user')
        try:
            resp = requests.get(f'{self.base_url}/api/v1/user', headers={
                'Authorization': f'Bearer {self.token}',
                'Accept': 'application/json',
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.user = data.get('user')
                roles = self.user.get('roles', [])
                logger.info(f'Token valid, user={self.user.get("email")}, roles={roles}')
                allowed = {'ROLE_ROOT', 'ROLE_ADMIN', 'ROLE_ISP'}
                if not allowed.intersection(roles):
                    logger.warning('Saved token user has no allowed role, clearing')
                    self._clear_token()
                    self.token = None
                    self.user = None
                    return False
                return True
            logger.warning(f'Token verification failed: HTTP {resp.status_code}')
            self._clear_token()
            self.token = None
            self.user = None
            return False
        except requests.ConnectionError as e:
            logger.error(f'Cannot reach server to verify token: {e}')
            return False
        except Exception as e:
            logger.error(f'Token verification error: {e}', exc_info=True)
            return False

    def login(self, email: str, password: str) -> tuple[bool, str | None, str]:
        """Returns (success, two_factor_email, message)."""
        url = f'{self.base_url}/api/v1/auth/login'
        logger.info(f'Attempting login to {url}')
        try:
            resp = requests.post(url, json={
                'email': email,
                'password': password,
            }, headers={
                'Accept': 'application/json',
            }, timeout=10)
            logger.info(f'Login response: HTTP {resp.status_code}')
            if resp.status_code == 200:
                data = resp.json()
                if data.get('two_factor'):
                    logger.info(f'2FA required for {email}')
                    return True, email, 'Verification code sent to your email.'
                self.token = data.get('token')
                self.user = data.get('user')
                logger.info(f'Login successful, user={self.user.get("email")}, roles={self.user.get("roles")}')
                self._save_token()
                return True, None, 'Login successful'
            msg = resp.json().get('message', 'Login failed')
            logger.warning(f'Login failed ({resp.status_code}): {msg}')
            return False, None, msg
        except requests.ConnectionError as e:
            logger.error(f'ConnectionError to {url}: {e}', exc_info=True)
            return False, None, f'Cannot connect to server ({self.base_url})'
        except requests.Timeout as e:
            logger.error(f'Timeout connecting to {url}: {e}', exc_info=True)
            return False, None, f'Connection timed out ({self.base_url})'
        except Exception as e:
            logger.error(f'Unexpected error logging in: {e}', exc_info=True)
            return False, None, str(e)

    def verify_two_factor(self, email: str, code: str) -> tuple[bool, str]:
        """Verify 2FA code and complete login."""
        url = f'{self.base_url}/api/v1/auth/two-factor-challenge'
        logger.info(f'Verifying 2FA code for {email}')
        try:
            resp = requests.post(url, json={
                'email': email,
                'code': code,
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get('token')
                self.user = data.get('user')
                logger.info(f'2FA verified, user={self.user.get("email")}, roles={self.user.get("roles")}')
                self._save_token()
                return True, 'Verification successful.'
            msg = resp.json().get('message', '') or resp.json().get('errors', {}).get('code', ['Verification failed'])[0]
            logger.warning(f'2FA failed: {msg}')
            return False, msg
        except requests.RequestException as e:
            logger.error(f'2FA request failed: {e}')
            return False, str(e)

    def logout(self):
        if self.token:
            try:
                url = f'{self.base_url}/api/v1/auth/logout'
                logger.info(f'Logging out from {url}')
                requests.post(url, headers={
                    'Authorization': f'Bearer {self.token}',
                    'Accept': 'application/json',
                }, timeout=5)
            except requests.RequestException as e:
                logger.warning(f'Logout request failed: {e}')
                pass
        self.token = None
        self.user = None
        self._clear_token()

    @property
    def is_authenticated(self) -> bool:
        return self.token is not None

    @property
    def is_admin(self) -> bool:
        if not self.user:
            return False
        roles = self.user.get('roles', [])
        return 'ROLE_ADMIN' in roles

    @property
    def is_isp(self) -> bool:
        if not self.user:
            return False
        roles = self.user.get('roles', [])
        return 'ROLE_ISP' in roles

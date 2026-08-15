import logging

import requests

from .auth import Auth

logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(self, auth: Auth):
        self.auth = auth
        self._session = requests.Session()

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.auth.token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f'{self.auth.base_url}{path}'
        logger.info(f'API {method} {url}')
        return self._session.request(method, url, headers=self._headers(), timeout=(30, 300), **kwargs)

    def _handle_response(self, resp: requests.Response, label: str):
        logger.info(f'{label}: HTTP {resp.status_code}')
        if not resp.ok:
            logger.error(f'{label} failed: {resp.status_code} {resp.text[:500]}')
            resp.raise_for_status()

    def get_isps(self) -> list[dict]:
        logger.info('Fetching ISP list')
        resp = self._request('GET', '/api/v1/isps')
        self._handle_response(resp, 'get_isps')
        data = resp.json().get('data', [])
        logger.info(f'Got {len(data)} ISPs')
        return data

    def get_isp_routers(self, isp_slug: str) -> list[dict]:
        logger.info(f'Fetching routers for ISP {isp_slug}')
        resp = self._request('GET', f'/api/v1/isps/{isp_slug}/routers')
        self._handle_response(resp, 'get_isp_routers')
        data = resp.json().get('data', [])
        logger.info(f'Got {len(data)} routers')
        return data

    def get_my_routers(self) -> list[dict]:
        logger.info('Fetching my routers')
        resp = self._request('GET', '/api/v1/my/routers')
        self._handle_response(resp, 'get_my_routers')
        data = resp.json().get('data', [])
        logger.info(f'Got {len(data)} routers')
        return data

    def get_mikrotik_models(self) -> list[dict]:
        logger.info('Fetching MikroTik models')
        resp = self._request('GET', '/api/v1/mikrotik-models')
        self._handle_response(resp, 'get_mikrotik_models')
        data = resp.json().get('data', [])
        logger.info(f'Got {len(data)} models')
        return data

    def get_next_vpn_ip(self) -> str:
        logger.info('Fetching next available VPN IP')
        resp = self._request('GET', '/api/v1/vpn/next-ip')
        self._handle_response(resp, 'get_next_vpn_ip')
        ip = resp.json().get('ip')
        logger.info(f'Next VPN IP: {ip}')
        return ip

    def create_router(self, data: dict) -> dict:
        logger.info(f'Creating router: name={data.get("name")}, isp_id={data.get("isp_id")}')
        resp = self._request('POST', '/api/v1/routers', json=data)
        self._handle_response(resp, 'create_router')
        result = resp.json().get('data', {})
        logger.info(f'Router created: id={result.get("id")}')
        return result

    def update_router(self, router_name: str, data: dict) -> dict:
        logger.info(f'Updating router name={router_name}')
        resp = self._request('PUT', f'/api/v1/routers/{router_name}', json=data)
        self._handle_response(resp, 'update_router')
        result = resp.json().get('data', {})
        logger.info(f'Router updated: id={result.get("id")}')
        return result

    def get_wireguard_public_key(self) -> str:
        logger.info('Fetching server WireGuard public key')
        resp = self._request('GET', '/api/v1/vpn/server-public-key')
        self._handle_response(resp, 'get_wireguard_public_key')
        key = resp.json().get('public_key')
        logger.info(f'Server WireGuard public key: {key[:20]}...' if key else 'Server WireGuard key empty')
        return key

    def add_wireguard_peer(self, public_key: str, allowed_ip: str, endpoint: str = '', persistent_keepalive: int = 0, serial_number: str = '') -> dict:
        logger.info(f'Adding WireGuard peer: pubkey={public_key[:20]}... ip={allowed_ip}')
        payload = {
            'public_key': public_key,
            'allowed_ip': allowed_ip,
        }
        if endpoint:
            payload['endpoint'] = endpoint
            payload['persistent_keepalive'] = persistent_keepalive or 25
        if serial_number:
            payload['serial_number'] = serial_number
        resp = self._request('POST', '/api/v1/wireguard/add-peer', json=payload)
        self._handle_response(resp, 'add_wireguard_peer')
        result = resp.json()
        logger.info(f'WireGuard peer added: {result}')
        return result

    def get_settings(self) -> dict:
        logger.info('Fetching VPN and GenieACS settings')
        resp = self._request('GET', '/api/v1/settings')
        self._handle_response(resp, 'get_settings')
        settings = resp.json()
        logger.info(f'Settings: vpn={"set" if settings.get("vpn") else "not set"}, genieacs={"set" if settings.get("genieacs") else "not set"}')
        return settings

    def store_hotspots(self, data: dict) -> list:
        logger.info(f'Storing hotspots for router {data.get("router_id")}')
        resp = self._request('POST', '/api/v1/routers/hotspots', json=data)
        self._handle_response(resp, 'store_hotspots')
        result = resp.json().get('data', [])
        logger.info(f'Stored {len(result)} hotspots')
        return result

    def get_router_full_settings(self, router_name: str) -> dict:
        logger.info(f'Fetching full settings for router {router_name}')
        resp = self._request('GET', f'/api/v1/routers/{router_name}/full-settings')
        self._handle_response(resp, 'get_router_full_settings')
        data = resp.json().get('data', {})
        logger.info(f'Got full settings for router {router_name}')
        return data

    def get_api_credentials(self, router_name: str) -> dict:
        logger.info(f'Fetching API credentials for router {router_name}')
        resp = self._request('GET', f'/api/v1/routers/{router_name}/api-credentials')
        self._handle_response(resp, 'get_api_credentials')
        creds = resp.json()
        logger.info(f'Got API credentials for router {router_name}')
        return creds

    def verify_reconfigure_router(self, router_name: str, host: str = '', port: int = 0) -> dict:
        logger.info(f'Verify & reconfigure router {router_name} host={host}')
        payload = {}
        if host:
            payload['host'] = host
        if port:
            payload['port'] = port
        resp = self._request('POST', f'/api/v1/routers/{router_name}/verify-reconfigure', json=payload)
        self._handle_response(resp, 'verify_reconfigure_router')
        result = resp.json()
        logger.info(f'Verify & reconfigure result: {result.get("message", "")}')
        return result

    def server_checks(self, router_name: str, system_info: dict | None = None, firmware_version: str = '') -> dict:
        logger.info(f'Running server checks for router {router_name}')
        payload: dict = {}
        if system_info:
            payload['system_info'] = system_info
        if firmware_version:
            payload['firmware_version'] = firmware_version
        resp = self._request('POST', f'/api/v1/routers/{router_name}/server-checks', json=payload)
        self._handle_response(resp, 'server_checks')
        result = resp.json()
        logger.info(f'Server checks result: {result.get("message", "")}')
        return result

    def get_hotspot_files(self, domain: str, captive_portal_url: str) -> dict[str, str]:
        logger.info(f'Fetching hotspot files from server for domain={domain} captive_portal_url={captive_portal_url}')
        resp = self._request('GET', '/api/v1/hotspot/files', params={'domain': domain, 'captive_portal_url': captive_portal_url})
        self._handle_response(resp, 'get_hotspot_files')
        files = resp.json().get('files', {})
        logger.info(f'Fetched {len(files)} hotspot files from server')
        return files

    def verify_connection(self) -> bool:
        try:
            resp = self._request('GET', '/api/v1/user')
            ok = resp.status_code == 200
            logger.info(f'Connection verify: HTTP {resp.status_code} => {"OK" if ok else "FAIL"}')
            return ok
        except requests.RequestException as e:
            logger.error(f'Connection verify failed: {e}')
            return False

#!/usr/bin/env python3
"""
Headless router provisioning script.
Runs the same steps as the GUI wizard without the GUI.
"""
import ipaddress
import logging
import sys
from urllib.parse import urlparse

sys.path.insert(0, '/my-files/Creations/Projects/insta-billing/config_program')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger('provision')

from api.auth import Auth  # noqa: E402
from api.client import ApiClient  # noqa: E402
from routeros.configurator import RouterOSConfigurator  # noqa: E402
from routeros.connector import RouterOSConnector  # noqa: E402


def main():
    # 1. Server API setup
    auth = Auth(base_url='http://localhost:9000')
    if not auth.token:
        logger.error('No saved token. Run the GUI to login first.')
        sys.exit(1)
    if not auth.verify_token():
        logger.error('Token invalid. Run the GUI to re-login.')
        sys.exit(1)
    api = ApiClient(auth)

    # 2. Router connection
    host = '192.168.88.1'
    user = 'admin'
    password = ''
    port = 8728

    conn = RouterOSConnector(host, user, password, port)
    ok, msg = conn.connect()
    if not ok:
        logger.error(f'Router connection failed: {msg}')
        sys.exit(1)
    logger.info(f'Connected: {msg}')

    configurator = RouterOSConfigurator(conn)

    # 3. Get ISP data for Fastnet (id=3)
    isps = api.get_isps()
    isp = next((isp for isp in isps if isp.get('id') == 3), None)
    if not isp:
        logger.error('ISP Fastnet (id=3) not found')
        sys.exit(1)
    isp_data = isp
    isp_id = isp_data['id']
    isp_name = isp_data.get('name', 'Fastnet')
    logger.info(f'ISP: {isp_name} (id={isp_id})')
    logger.info(f'  stripped_name={isp_data.get("stripped_name","")}, radius_secret={"set" if isp_data.get("radius_secret") else "not set"}')

    # 4. Fetch server settings
    settings = api.get_settings()
    vpn = settings.get('vpn') or {}
    genieacs = settings.get('genieacs') or {}
    hotspot_dns_name = settings.get('hotspot_dns_name', '')
    app_url = settings.get('app_url', '')
    portal_domain = settings.get('portal_domain', 'failed.smalnets.com')

    logger.info(f'Settings: vpn={"set" if vpn else "not set"}, genieacs={"set" if genieacs else "not set"}')
    logger.info(f'  hotspot_dns_name={hotspot_dns_name}')
    logger.info(f'  portal_domain={portal_domain}')
    logger.info(f'  app_url={app_url}')

    # 5. Check if router already exists in DB
    existing_routers = api.get_isp_routers(isp_id)
    existing_serial = ''
    try:
        conn_serial = configurator.get_router_info()[1].get('serial_number', '')
        existing_serial = conn_serial
    except Exception:
        pass
    existing_router = next((r for r in existing_routers if r.get('serial_number') == existing_serial), None)

    # 6. Compute router name and allocate/use VPN IP
    router_name = existing_router.get('name', '') if existing_router else ''
    if not router_name:
        import secrets as _secrets
        import string as _string
        existing_names = {r.get('name') for r in existing_routers}
        _alpha = _string.ascii_letters + _string.digits
        while True:
            router_name = ''.join(_secrets.choice(_alpha) for _ in range(8))
            if router_name not in existing_names:
                break
    logger.info(f'Router name: {router_name}')

    if existing_router and existing_router.get('vpn_ip'):
        vpn_ip = existing_router['vpn_ip']
        logger.info(f'Reusing existing VPN IP: {vpn_ip}')
    else:
        vpn_ip = api.get_next_vpn_ip()
        logger.info(f'VPN IP allocated: {vpn_ip}')

    # 6. Run configuration steps
    vpn_endpoint = vpn.get('server_address', '')
    if vpn.get('listen_port'):
        vpn_endpoint = f'{vpn_endpoint}:{vpn["listen_port"]}'

    server_pubkey = None
    if vpn_endpoint:
        try:
            server_pubkey = api.get_wireguard_public_key()
            logger.info(f'Server WG pubkey: {server_pubkey[:20]}...')
        except Exception as e:
            logger.warning(f'Could not fetch server WG key: {e}')

    vpn_subnet = vpn.get('allowed_ips', '10.200.0.0/20')

    steps = [
        ("Reading router info", lambda: configurator.get_router_info()),
        ("Detecting hotspot interfaces", lambda: configurator.get_hotspot_interfaces()),
        ("Setting router identity", lambda: configurator.set_identity(router_name)),
        ("Configuring firewall rules", lambda: configurator.configure_firewall(allowed_subnets=[vpn_subnet])),
        ("Configuring WireGuard", lambda: configurator.configure_vpn_wireguard(
            vpn_ip, '',
            endpoint='' if vpn_endpoint else None,
            listen_port=vpn.get('listen_port'),
        )),
    ]

    if server_pubkey and vpn_endpoint:
        steps.append((
            "Adding WG server peer",
            lambda: configurator.add_vpn_peer(
                server_pubkey, vpn_endpoint,
                persistent_keepalive=vpn.get('persistent_keepalive', 25),
            )
        ))

    radius_secret = isp_data.get('radius_secret', '')
    radius_server_ip = ''
    if radius_secret:
        network = ipaddress.ip_network(vpn_subnet, strict=False)
        radius_server_ip = str(network.network_address + 1)
        steps.append((
            "Configuring RADIUS",
            lambda: configurator.configure_radius(radius_server_ip, radius_secret),
        ))

    acs_url = genieacs.get('acs_url', '')
    router_info = {}
    for label, func in steps:
        logger.info(f'Step: {label}')
        ok, result = func()
        if not ok:
            logger.error(f'  FAILED: {result}')
            sys.exit(1)
        if isinstance(result, dict):
            router_info.update(result)
        logger.info('  OK')

    serial_number = router_info.get('serial_number', '')
    model = router_info.get('model', '')
    firmware_version = router_info.get('firmware_version', '')

    if acs_url and serial_number:
        logger.info('Step: Configuring GenieACS')
        ok, msg = configurator.configure_genieacs(
            serial_number,
            acs_url=acs_url,
            username=genieacs.get('username', ''),
            password=genieacs.get('password', ''),
            inform_interval=genieacs.get('periodic_inform_interval', 300),
        )
        if not ok:
            logger.warning(f'  GenieACS: {msg}')
        else:
            logger.info('  OK')

    # 7. Save router to server
    ifaces = router_info.get('hotspot_interfaces', [])
    ports_count = sum(1 for i in ifaces if i.get('type') == 'ether') + 2

    api_data = {
        'isp_id': isp_id,
        'serial_number': serial_number,
        'model': model,
        'firmware_version': firmware_version,
        'ports_count': ports_count,
        'vpn_ip': vpn_ip,
        'routeros_host': host,
        'routeros_port': port,
        'routeros_user': user,
        'routeros_password': password,
        'default_password': password,
    }

    existing_routers = api.get_isp_routers(isp_id)
    existing = next((r for r in existing_routers if r.get('serial_number') == serial_number), None)
    if existing:
        router_id = existing['id']
        logger.info(f'Router exists (id={router_id}), updating...')
        api.update_router(router_id, api_data)
        # Update VPN IP since it might have changed
        api_data['vpn_ip'] = existing.get('vpn_ip', vpn_ip)
    else:
        result = api.create_router(api_data)
        router_id = result.get('id')
        logger.info(f'Router created: id={router_id}')

    stripped_name = isp_data.get('stripped_name', '')

    # Parse captive portal server address from app_url
    parsed = urlparse(app_url)
    cp_host = parsed.hostname or ''
    parsed_port = parsed.port
    # Use portal_domain with port for the hotspot redirect URL
    if parsed_port and parsed_port not in (80, 443):
        portal_host = f'{portal_domain}:{parsed_port}'
        cp_host_port = f'{cp_host}:{parsed_port}'
    else:
        portal_host = portal_domain
        cp_host_port = cp_host

    # 8. Provision hotspot
    logger.info(f'Provisioning hotspot bridge with {len(ifaces)} ports, captive portal domain: {portal_host} ({cp_host_port})...')
    ok, hs = configurator.provision_hotspot_ports(
        ifaces,
        dns_name=hotspot_dns_name,
        radius_server_ip=radius_server_ip,
        router_id=router_id,
        stripped_name=stripped_name,
        captive_portal_server=cp_host_port,
        portal_domain=portal_domain,
        router_name=router_name,
    )
    if not ok:
        logger.error(f'Hotspot provisioning failed: {hs.get("error", "unknown")}')
        sys.exit(1)
    logger.info(f'Hotspot provisioned: {hs}')

    # 9. Save hotspot to server
    captive_portal_url = hs.get('captive_portal_url', '')
    hs_data = {
        'router_id': router_id,
        'hotspots': [{
            'interface': hs['interface'],
            'name': hs['name'],
            'captive_portal_url': captive_portal_url,
            'ip_range': hs.get('ip_range', ''),
        }],
    }
    try:
        api.store_hotspots(hs_data)
        logger.info('Hotspot saved to server')
    except Exception as e:
        logger.warning(f'Failed to save hotspot: {e}')

    # 10. Upload hotspot files
    logger.info(f'Fetching hotspot files for domain={portal_host} captive_portal_url={captive_portal_url}')
    try:
        api_files = api.get_hotspot_files(portal_host, captive_portal_url)
        ok, msg = configurator.upload_hotspot_files(api_files)
        logger.info(f'File upload: {"OK" if ok else "FAIL"} — {msg}')
    except Exception as e:
        logger.warning(f'File upload failed: {e}')

    # 11. Add WG peer on server
    ok, pubkey = configurator.get_wireguard_public_key()
    if ok and pubkey:
        logger.info(f'Adding WG peer on server for {pubkey[:20]}... -> {vpn_ip}')
        api.add_wireguard_peer(pubkey, vpn_ip)
    else:
        logger.warning('Could not read router WG public key')

    conn.disconnect()
    logger.info('=== Provisioning complete ===')


if __name__ == '__main__':
    main()

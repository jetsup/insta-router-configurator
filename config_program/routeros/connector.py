import socket


class RouterOSConnector:
    def __init__(self, host: str, username: str, password: str, port: int = 8728):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.ros = None
        self._pool = None

    def test_connection(self) -> tuple[bool, str]:
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5)
            sock.close()
            return True, 'Connection successful'
        except TimeoutError:
            return False, 'Connection timed out'
        except socket.gaierror:
            return False, 'Invalid hostname'
        except ConnectionRefusedError:
            return False, 'Connection refused — check API port and firewall'
        except Exception as e:
            return False, str(e)

    def connect(self) -> tuple[bool, str]:
        try:
            import routeros_api

            self._pool = routeros_api.RouterOsApiPool(
                self.host,
                username=self.username,
                password=self.password,
                port=self.port,
                plaintext_login=True,
            )
            self.ros = self._pool.get_api()
            identity = list(self.cmd('/system/identity/print'))[0].get('name', 'Unknown')
            return True, f'Connected to {identity}'
        except ImportError:
            return False, 'routeros-api not installed — run: pip install routeros-api'
        except Exception as e:
            self.ros = None
            self._pool = None
            return False, str(e)

    def disconnect(self):
        if self._pool:
            self._pool.disconnect()
        self.ros = None
        self._pool = None

    def is_connected(self) -> bool:
        return self.ros is not None

    def cmd(self, path: str, **kwargs) -> list[dict]:
        if not self.ros:
            raise RuntimeError('Not connected to RouterOS')

        parts = path.strip('/').split('/')
        command = parts.pop()
        base_path = '/' + '/'.join(parts)

        resource = self.ros.get_binary_resource(base_path)

        bytes_kwargs = {}
        for k, v in kwargs.items():
            # RouterOS API expects hyphens (dns-name, html-directory), not underscores
            ros_key = k.replace('_', '-')
            if isinstance(v, bool):
                bytes_kwargs[ros_key] = b'yes' if v else b'no'
            elif v is None:
                bytes_kwargs[ros_key] = b''
            elif isinstance(v, bytes):
                bytes_kwargs[ros_key] = v
            else:
                bytes_kwargs[ros_key] = str(v).encode()

        result = resource.call(command, arguments=bytes_kwargs)

        return [
            {k: v.decode(errors='replace') if isinstance(v, bytes) else v for k, v in item.items()}
            for item in result
        ]

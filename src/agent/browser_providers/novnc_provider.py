from __future__ import annotations

import os
import time
import socket
import docker
from typing import Optional, Mapping, Any
from datetime import datetime
from loguru import logger

from agent.browser_providers.base import BrowserProvider, BrowserSession, BrowserProviderError

class NoVNCProvider(BrowserProvider):
    code = "NOVNC"
    
    def __init__(self):
        # Settings should be loaded here
        self.image = os.environ.get("NOVNC_DOCKER_IMAGE", "social/novnc-browser:latest")
        self.network = os.environ.get("NOVNC_DOCKER_NETWORK", "bridge")
        self.base_profile_dir = os.environ.get("NOVNC_PROFILE_BASE_DIR", "/tmp/novnc_profiles")
        
        try:
            self.client = docker.from_env()
        except Exception:
            self.client = None
            logger.warning("Docker client not initialized. NoVNC provider will fail if used.")

    def start_session(
        self,
        profile_row: Any,
        *, 
        trace_id: str,
        extra: Optional[Mapping[str, str]] = None,
    ) -> BrowserSession:
        if not self.client:
            raise BrowserProviderError("Docker not available", code="NOVNC_DOCKER_ERROR", provider=self.code)
            
        account_name = profile_row.dummy_account.name
        safe_name = "".join(c for c in account_name if c.isalnum() or c in ('-','_'))
        container_name = f"novnc-{safe_name}-{trace_id[-6:]}"
        
        # Ports mapping
        # We need to find free ports on host or let Docker assign random
        # Let Docker assign random
        ports = {
            '6080/tcp': None, # noVNC
            '9515/tcp': None  # WebDriver
        }
        
        # Volumes
        # Ensure profile dir exists
        host_profile_dir = os.path.join(self.base_profile_dir, safe_name)
        os.makedirs(host_profile_dir, exist_ok=True)
        
        volumes = {
            host_profile_dir: {'bind': '/home/browser_user/.browser_profile', 'mode': 'rw'}
        }
        
        # Env vars for anti-detect or proxy
        environment = {
            "SCREEN_RESOLUTION": "1920x1080x24",
            # "BROWSER_PROXY_URL": ... (get from db if available)
        }
        
        try:
            logger.info(f"[{trace_id}] Starting noVNC container {container_name}")
            container = self.client.containers.run(
                self.image,
                detach=True,
                name=container_name,
                ports=ports,
                volumes=volumes,
                environment=environment,
                # network=self.network, # Use default or specific
                shm_size='2g' # Important for Chrome
            )
            
            # Wait for ports and readiness
            container.reload() # Get mapped ports
            
            # Simple polling wait
            retries = 20
            webdriver_port = None
            novnc_port = None
            
            while retries > 0:
                container.reload()
                if container.status != 'running':
                    raise BrowserProviderError(f"Container died: {container.logs().decode('utf-8')}", code="NOVNC_CRASH", provider=self.code)
                
                # Check mapping
                # Ports format: {'6080/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32768'}], ...}
                p_wd = container.ports.get('9515/tcp')
                p_vnc = container.ports.get('6080/tcp')
                
                if p_wd and p_vnc:
                    webdriver_port = p_wd[0]['HostPort']
                    novnc_port = p_vnc[0]['HostPort']
                    
                    # Try connecting to webdriver port socket to ensure it's listening
                    if self._is_port_open('localhost', int(webdriver_port)):
                        break
                
                time.sleep(1)
                retries -= 1
            
            if not webdriver_port:
                # Cleanup
                container.stop()
                container.remove()
                raise BrowserProviderError("Timed out waiting for WebDriver", code="NOVNC_TIMEOUT", provider=self.code)
                
            webdriver_url = f"http://localhost:{webdriver_port}/wd/hub" # Assuming standard selenium server URL structure? 
            # Or if it's raw chromedriver: http://localhost:{webdriver_port}
            # Note: chromedriver usually listens on /, but selenium.webdriver.Remote expects /wd/hub usually or can adjust.
            # Using raw chromedriver directly with Remote might require command_executor adjustment.
            # Let's use standard URL, assume user handles path if needed.
            # Actually, standard chromedriver standalone exposes root.
            webdriver_url = f"http://localhost:{webdriver_port}" 
            
            novnc_url = f"http://localhost:{novnc_port}/vnc.html"
            
            return BrowserSession(
                provider_code=self.code,
                provider_profile_id=profile_row.id,
                provider_session_ref=container.id,
                webdriver_url=webdriver_url,
                novnc_url=novnc_url
            )
            
        except docker.errors.APIError as e:
            raise BrowserProviderError(f"Docker API error: {e}", code="NOVNC_DOCKER_ERROR", provider=self.code)
        except Exception as e:
            raise BrowserProviderError(f"Failed to start noVNC: {e}", code="NOVNC_UNKNOWN", provider=self.code)

    def stop_session(
        self,
        session: BrowserSession,
        *,
        trace_id: str,
    ) -> None:
        if not self.client:
            return
            
        container_id = session.provider_session_ref
        try:
            logger.info(f"[{trace_id}] Stopping container {container_id[:12]}")
            container = self.client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove()
        except docker.errors.NotFound:
            logger.warning(f"[{trace_id}] Container {container_id} not found during stop")
        except Exception as e:
            logger.error(f"[{trace_id}] Error stopping container: {e}")

    def _is_port_open(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host, port)) == 0

from __future__ import annotations

import os
import time
import socket
import docker
import json
from typing import Optional, Mapping, Any
from loguru import logger

from agent.browser_providers.base import BrowserProvider, BrowserSession, BrowserProviderError
from agent.config import load_settings

class NovncAwsProvider(BrowserProvider):
    code = "NOVNC_AWS"

    def __init__(self):
        self.settings = load_settings()
        # Initialize Docker Client
        # We respect DOCKER_HOST env var automatically
        try:
            self.client = docker.from_env()
        except Exception as e:
            self.client = None
            logger.warning(f"Docker client initialization failed: {e}")

    def start_session(
        self,
        profile_row: Any,
        *,
        trace_id: str,
        extra: Optional[Mapping[str, str]] = None,
    ) -> BrowserSession:
        if not self.client:
             raise BrowserProviderError("Docker client unavailable", code="NOVNC_AWS_DOCKER_ERROR", provider=self.code)

        # 1. Config Resolution
        provider_config = profile_row.provider.config or {}
        profile_config = profile_row.config or {}
        
        image = provider_config.get("docker_image", "social/novnc-browser:latest")
        internal_port = int(provider_config.get("default_webdriver_port", 4444)) # Or 9515 depending on image
        # Note: Previous noVNC script used 9515. Consolidating to single port if possible, 
        # or respect config.
        
        # 2. Start Container
        account_name = profile_row.dummy_account.name
        safe_name = "".join(c for c in account_name if c.isalnum() or c in ('-','_'))
        container_name = f"novnc-aws-{safe_name}-{trace_id[-6:]}-{int(time.time())}"
        
        # We typically map:
        # 6080 -> random (for vnc viewing if debug needed)
        # Webdriver Port -> random
        ports = {
            f"{internal_port}/tcp": None,
            "6080/tcp": None
        }
        
        # Env vars for container
        environment = {
            "SCREEN_RESOLUTION": "1920x1080x24",
            "SE_NODE_MAX_SESSIONS": "1", # If using selenium grid image
        }
        
        # Proxy?
        if profile_config.get("proxy_enabled"):
             # Add proxy
             pass

        try:
            logger.info(f"[{trace_id}] Starting {self.code} container {container_name} ({image})")
            container = self.client.containers.run(
                image,
                detach=True,
                name=container_name,
                ports=ports,
                environment=environment,
                shm_size='2g'
            )
            
            # 3. Wait for Readiness
            container.reload()
            host_wd_port = None
            host_vnc_port = None
            
            retries = 30
            while retries > 0:
                container.reload()
                if container.status not in ['running', 'created']:
                    logs = container.logs().decode('utf-8')[-200:]
                    raise BrowserProviderError(f"Container exited: {logs}", code="NOVNC_AWS_CRASH", provider=self.code)
                
                # Check ports
                p_wd = container.ports.get(f"{internal_port}/tcp")
                p_vnc = container.ports.get("6080/tcp")
                
                if p_wd:
                    host_wd_port = p_wd[0]['HostPort']
                    
                    # Resolve Host IP
                    target_host = self._resolve_docker_host()
                    
                    # Check Socket
                    if self._is_port_open(target_host, int(host_wd_port)):
                        if p_vnc:
                            host_vnc_port = p_vnc[0]['HostPort']
                        break
                        
                time.sleep(1)
                retries -= 1
                
            if not host_wd_port:
                container.stop()
                container.remove()
                raise BrowserProviderError("Timed out waiting for WebDriver port", code="NOVNC_AWS_TIMEOUT", provider=self.code)

            target_host = self._resolve_docker_host()
            
            # Construct URLs
            # Using standard Selenium /wd/hub path?
            # Or root? Depends on image entrypoint. 
            # Previous noVNC script (start.sh) used chromedriver direct on 9515 -> root?
            # Selenium Standalone uses /wd/hub.
            # Let's assume /wd/hub for robustness or check image type.
            # If our 'social/novnc-browser' uses direct chromedriver, it is root.
            # If we switch to 'selenium/standalone-chrome', it is /wd/hub.
            
            # For now, let's assume /wd/hub as it is standard for RemoteWebDriver.
            # BUT if we use our custom image, we need to ensure it matches.
            # Our custom start.sh started chromedriver on WEBDRIVER_PORT. This serves / usually.
            # Selenium Remote client often appends /wd/hub if not present? Or expects it?
            
            # Safe bet: If using `social/novnc-browser` (our custom one), ensure start.sh is compatible.
            # Or just use `http://host:port` and let client handle?
            # Standard `webdriver.Remote` defaults to `/wd/hub`.
            # To support that, our custom image needs to serve there, OR we pass custom command_executor to Remote.
            
            # Let's use `http://host:port` and let the client append /wd/hub if it's default, 
            # Or explicitly:
            webdriver_url = f"http://{target_host}:{host_wd_port}"
            
            novnc_url = None
            if host_vnc_port:
                novnc_url = f"http://{target_host}:{host_vnc_port}/vnc.html"

            return BrowserSession(
                provider_code=self.code,
                provider_profile_id=profile_row.id,
                provider_session_ref=container.id,
                webdriver_url=webdriver_url,
                novnc_url=novnc_url
            )

        except docker.errors.APIError as e:
             raise BrowserProviderError(f"Docker API Error: {e}", code="NOVNC_AWS_DOCKER_ERROR", provider=self.code)
        except Exception as e:
             raise BrowserProviderError(f"Unknown Error: {e}", code="NOVNC_AWS_UNKNOWN", provider=self.code)

    def stop_session(
        self,
        session: BrowserSession,
        *,
        trace_id: str,
    ) -> None:
        if not self.client: return
        cid = session.provider_session_ref
        try:
             logger.info(f"[{trace_id}] Stopping {self.code} container {cid[:8]}")
             c = self.client.containers.get(cid)
             c.stop(timeout=5)
             c.remove()
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.error(f"Error stopping container {cid}: {e}")

    def _resolve_docker_host(self) -> str:
        d_host = os.environ.get("DOCKER_HOST")
        if d_host and "tcp://" in d_host:
             return d_host.split("://")[1].split(":")[0]
        return "localhost"

    def _is_port_open(self, host, port):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

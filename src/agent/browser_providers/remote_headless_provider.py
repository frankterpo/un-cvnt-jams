from __future__ import annotations

import os
import time
import socket
import docker
from typing import Optional, Mapping, Any, Dict
from datetime import datetime
from loguru import logger

from agent.browser_providers.base import BrowserProvider, BrowserSession, BrowserProviderError
from agent.config import load_settings

class RemoteHeadlessProvider(BrowserProvider):
    code = "REMOTE_HEADLESS"

    def __init__(self):
        # We rely on docker.from_env() to pick up DOCKER_HOST if set
        # But we also want to allow explicit config from settings if needed
        self.settings = load_settings()
        
        try:
            self.client = docker.from_env()
        except Exception:
            self.client = None
            logger.warning("Docker client failed to initialize. REMOTE_HEADLESS provider will fail if used.")

    def start_session(
        self,
        profile_row: Any,
        *,
        trace_id: str,
        extra: Optional[Mapping[str, str]] = None,
    ) -> BrowserSession:
        if not self.client:
             raise BrowserProviderError("Docker client unavailable", code="REMOTE_HEADLESS_DOCKER_ERROR", provider=self.code)

        # 1. Resolve Config
        # Provider defaults
        provider_config = profile_row.provider.config or {}
        # Profile config
        profile_config = profile_row.config or {}
        
        image = profile_config.get("image", provider_config.get("docker_image", "selenium/standalone-chrome:latest"))
        internal_port = int(provider_config.get("default_webdriver_port", 4444))
        
        # 2. Start Container
        account_name = profile_row.dummy_account.name
        safe_name = "".join(c for c in account_name if c.isalnum() or c in ('-','_'))
        # Ensure unique container name
        container_name = f"headless-{safe_name}-{trace_id[-6:]}-{int(time.time())}"
        
        ports = {f"{internal_port}/tcp": None} # Let Docker assign random host port
        
        environment = {
            "SE_NODE_MAX_SESSIONS": "1",
            "SE_NODE_OVERRIDE_MAX_SESSIONS": "true",
            "START_XVFB": "false" # It's headless anyway, but safe to set
        }
        
        # Proxy handling?
        if profile_config.get("proxy_enabled"):
             # Add proxy envs
             pass

        try:
            logger.info(f"[{trace_id}] Starting Remote Headless container {container_name} ({image})")
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
            host_port = None
            
            # Get Mapped Port
            # Loop because sometimes it takes a split second for Docker to update port mappings API
            retries = 30
            while retries > 0:
                container.reload()
                if container.status != 'running' and container.status != 'created':
                     # If it exited immediately
                     raise BrowserProviderError(f"Container exited: {container.logs().decode('utf-8')[:200]}", code="REMOTE_HEADLESS_CRASH", provider=self.code)
                
                mapped = container.ports.get(f"{internal_port}/tcp")
                if mapped:
                    host_port = mapped[0]['HostPort']
                    # Verify connectivity
                    # We need the Docker Host IP.
                    # If we are remote, localhost might NOT be correct.
                    # docker.from_env().base_url might give clue, but 'localhost' is standard assumption for port mapping unless DOCKER_HOST is IP.
                    
                    # Resolve Host
                    # logic: if DOCKER_HOST is set, parse IP. Else localhost.
                    docker_host_url = os.environ.get("DOCKER_HOST")
                    target_host = "localhost"
                    if docker_host_url and "tcp://" in docker_host_url:
                        # Extract IP
                        # tcp://1.2.3.4:2375 -> 1.2.3.4
                        target_host = docker_host_url.split("://")[1].split(":")[0]
                    
                    # Check URL
                    base_url = f"http://{target_host}:{host_port}"
                    status_url = f"{base_url}/wd/hub/status"
                    
                    # Currently we just check TCP socket first
                    if self._is_port_open(target_host, int(host_port)):
                        # Ideally verify HTTP status 200/OK from /status
                        break
                
                time.sleep(1)
                retries -= 1
            
            if not host_port:
                 container.stop()
                 container.remove()
                 raise BrowserProviderError("Timed out waiting for mapped port", code="REMOTE_HEADLESS_TIMEOUT", provider=self.code)

            # Re-resolve target host for final URL
            docker_host_url = os.environ.get("DOCKER_HOST")
            target_host = "localhost"
            if docker_host_url and "tcp://" in docker_host_url:
                target_host = docker_host_url.split("://")[1].split(":")[0]

            # Construct URL
            # Selenium Images typically use /wd/hub
            webdriver_url = f"http://{target_host}:{host_port}/wd/hub"
            
            return BrowserSession(
                provider_code=self.code,
                provider_profile_id=profile_row.id,
                provider_session_ref=container.id,
                webdriver_url=webdriver_url,
                cdp_url=None, # Configure if using Playwright image
                novnc_url=None
            )

        except docker.errors.APIError as e:
             raise BrowserProviderError(f"Docker API Error: {e}", code="REMOTE_HEADLESS_DOCKER_ERROR", provider=self.code)
        except Exception as e:
             raise BrowserProviderError(f"Unknown Remote Headless Error: {e}", code="REMOTE_HEADLESS_UNKNOWN", provider=self.code)

    def stop_session(
        self,
        session: BrowserSession,
        *,
        trace_id: str,
    ) -> None:
        if not self.client: return
        
        cid = session.provider_session_ref
        try:
            logger.info(f"[{trace_id}] Stopping Remote Headless container {cid[:8]}")
            c = self.client.containers.get(cid)
            c.stop(timeout=5)
            c.remove()
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.error(f"Failed to stop container {cid}: {e}")

    def _is_port_open(self, host, port):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (socket.timeout, ConnectionRefusedError):
            return False
        except OSError:
            return False

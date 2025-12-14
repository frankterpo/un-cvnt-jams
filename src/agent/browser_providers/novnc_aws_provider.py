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
        # profile_row does not have config column currently
        profile_config = {}
        
        image = provider_config.get("docker_image", "social/novnc-browser:latest")
        internal_port = int(provider_config.get("default_webdriver_port", 9515)) # Default to 9515 matching Image
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
            "SCREEN_RESOLUTION": "1920x1080",
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
            webdriver_url = f"http://{target_host}:{host_wd_port}/wd/hub"
            
            # Wait for ChromeDriver to be ready
            # Docker reports "Running" and ports mapped, but process inside needs time to bind
            import urllib.request
            import urllib.error
            
            logger.info(f"[{trace_id}] Waiting for WebDriver readiness at {webdriver_url}...")
            ready = False
            last_error = None
            start_wait = time.time()
            
            for i in range(60): # Retry for 60 seconds
                try:
                    # Check status endpoint with increased timeout (3s) to handle initial latency
                    with urllib.request.urlopen(f"{webdriver_url}/status", timeout=3) as response:
                        if response.status == 200:
                            elapsed = time.time() - start_wait
                            logger.info(f"[{trace_id}] WebDriver ready in {elapsed:.1f}s")
                            ready = True
                            break
                        else:
                            last_error = f"HTTP {response.status}"
                except (OSError, urllib.error.URLError) as e:
                    # Capture exact error for debugging (ConnectionRefused vs Timeout vs no route)
                    last_error = f"{type(e).__name__}: {e}"
                    # Log only periodically to avoid spam, or on final attempt
                    if i % 10 == 0 or i == 59:
                         logger.debug(f"[{trace_id}] Waiting for WebDriver... ({last_error})")
                    time.sleep(1)
            
            if not ready:
                container.stop()
                container.remove()
                raise BrowserProviderError(f"Timed out waiting for ChromeDriver readiness. Last error: {last_error}", code="NOVNC_AWS_TIMEOUT", provider=self.code)

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

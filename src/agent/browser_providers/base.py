from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional, Mapping, Any

class BrowserProviderError(Exception):
    def __init__(self, msg: str, code: Optional[str] = None, provider: Optional[str] = None):
        super().__init__(msg)
        self.code = code
        self.provider = provider


@dataclass
class BrowserSession:
    provider_code: str              # "GOLOGIN" or "NOVNC"
    provider_profile_id: int        # browser_provider_profiles.id
    provider_session_ref: str       # provider-specific session id or container id
    webdriver_url: str              # URL to use for Selenium / undetected-chromedriver
    cdp_url: Optional[str] = None   # optional CDP endpoint, for Playwright or debugging
    novnc_url: Optional[str] = None # optional noVNC viewer URL for humans


class BrowserProvider(Protocol):
    code: str  # e.g. "GOLOGIN" / "NOVNC"

    def start_session(
        self,
        profile_row: Any,   # ORM row from browser_provider_profiles
        *, 
        trace_id: str,
        extra: Optional[Mapping[str, str]] = None,
    ) -> BrowserSession:
        """Provision/start a browser session and return connection details."""
        ...

    def stop_session(
        self,
        session: BrowserSession,
        *,
        trace_id: str,
    ) -> None:
        """Tear down or release the underlying session/container if applicable."""
        ...

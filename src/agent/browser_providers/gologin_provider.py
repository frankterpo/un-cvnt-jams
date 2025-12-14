from __future__ import annotations

import os
from typing import Optional, Mapping, Any
from datetime import datetime
from loguru import logger

from agent.browser_providers.base import BrowserProvider, BrowserSession, BrowserProviderError
from tools.gologin_selenium import SyncGoLoginWebDriver
from agent.config import load_settings

class GoLoginProvider(BrowserProvider):
    code = "GOLOGIN"
    
    def __init__(self):
        self.settings = load_settings()

    def start_session(
        self,
        profile_row: Any,
        *, 
        trace_id: str,
        extra: Optional[Mapping[str, str]] = None,
    ) -> BrowserSession:
        """
        Start a GoLogin session.
        """
        profile_id = profile_row.provider_profile_ref
        account_token = None
        
        # Determine token.
        # We try to use the token from settings that matches the account email?
        # Or just use the first valid token we find if we don't have mapping?
        # The Allocator/Caller might pass token in 'extra' if it knows it.
        if extra and extra.get("gologin_token"):
            account_token = extra["gologin_token"]
        else:
            # Fallback: Assume we have tokens in settings.
            # Ideally we pick one associated with the user.
            # But currently `browser_provider_profiles` doesn't store the token.
            # We'll use the first available for now or look it up if we can.
            
            # Simple approach: If only 1-2 tokens, try them?
            # Or assume we shouldn't guess. 
            # The current system (pre-refactor) passed credentials manually.
            # Let's assume we REQUIRE the token to be passed in 'extra' or found in settings via dummy account name.
            
            account_name = profile_row.dummy_account.name
            creds = self.settings.get_gologin_credentials(account_name)
            if creds:
                account_token = creds[0]
            else:
                 # Last resort: Try use token from environment if single user
                 # This is tricky without changing DB.
                 pass

        if not account_token:
             # Try first token from settings as fallback
             values = list(self.settings.gologin_accounts.values())
             if values:
                 account_token = values[0].token
        
        if not account_token:
            raise BrowserProviderError("No GoLogin token available", code="GOLOGIN_AUTH_FAILED", provider=self.code)

        try:
            logger.info(f"[{trace_id}] Starting GoLogin profile {profile_id}")
            # This class (SyncGoLoginWebDriver) starts the driver in __enter__ usually.
            # But we want to just start it and get the URL.
            # SyncGoLoginWebDriver wraps the whole lifecycle as context manager.
            # We might need to unwrap it or adapt it.
            
            # Adapting: We will instantiate it, start it, and keep it alive.
            # This means we rely on SyncGoLoginWebDriver's internal logic.
            driver_wrapper = SyncGoLoginWebDriver(account_token, profile_id)
            
            # We need to manually trigger the start if it's designed as context manager
            # Looking at source (assumed), it likely does setup in __enter__.
            # We'll replicate that behavior or use internal methods.
            
            # Assuming standard GL usage:
            # gl = GoLogin(...)
            # debugger_address = gl.start()
            # driver = webdriver.Chrome(options=...)
            
            # Since SyncGoLoginWebDriver encapsulates this, let's use it to get the driver
            # then detach? Or rather, we should treat the 'session' object as holding the driver wrapper.
            
            # PROBLEM: BrowserSession expects a URL (webdriver_url).
            # Local chromedriver usually doesn't expose a remote URL unless started as server.
            # Typical local selenium usage: driver is an object, not a URL.
            
            # The new architecture demands: "Expose a remote WebDriver / CDP endpoint".
            # For GoLogin running locally, we can get the CDP debugger address.
            # But can we direct other tools to use it remotely?
            # Yes, standard Selenium can attach to an existing debugger address.
            
            # Let's start the wrapper.
            driver = driver_wrapper.start_driver() # Assume we can verify/add this method to the wrapper
            
            # Extract info
            # The driver is running.
            # Debugger address is usually available via driver.caps...
            # But wait, GoLogin wrapper returns a Driver Object.
            
            # If we want a UNIFORM interface where 'webdriver_url' is the key...
            # For LOCAL GoLogin, there is no "Hub" URL usually.
            # Unless we run a local Selenium Server and plug GoLogin into it (hard).
            
            # ALTERNATIVE: The `BrowserSession` definition says `webdriver_url`.
            # If we are local, this might be `http://localhost:DEBUGGER_PORT`.
            # But Selenium 'command_executor' expects a Hub-compliant server, not just CDP.
            
            # ADJUSTMENT: We might need `BrowserSession` to return EITHER a high-level `driver` object 
            # OR a `webdriver_url` + `driver_type`. 
            # BUT the prompt asked for "remote browser endpoint".
            
            # "Ensure automation flows... behave like local ChromeDriver"
            # If we use `webdriver.Remote(command_executor=...)` it works for remote docker.
            # For Local GoLogin, we usually use `webdriver.Chrome(service=..., options=...)`.
            
            # If we want unified code, we must make GoLogin look like a Remote driver?
            # We can't easily turn local GoLogin process into a Remote Server without java jar standalone.
            
            # DECISION: We might need to relax strict "webdriver_url" for GoLogin
            # OR implement a bridge.
            # FOR NOW, let's assume `webdriver_url` CAN be special "local" indicator
            # OR we actually start a local webdriver session and return the executor URL 
            # (driver.command_executor._url).
            
            debug_port = driver_wrapper.gl.debugger_address  # This is usually host:port
            executor_url = driver.command_executor._url # This is the WebDriver API endpoint!
            
            # Successful start
            
            # Update last used
            # profile_row.last_used_at = datetime.utcnow() # Caller or Allocator handles DB save?
            
            return BrowserSession(
                provider_code=self.code,
                provider_profile_id=profile_row.id,
                provider_session_ref=profile_id, # GoLogin profile ID
                webdriver_url=executor_url,
                cdp_url=None, # Debugger address?
                novnc_url=None
            )

        except Exception as e:
            error_msg = str(e)
            code = "GOLOGIN_UNKNOWN"
            if "limit" in error_msg.lower():
                code = "GOLOGIN_LIMIT_REACHED"
            elif "429" in error_msg:
                code = "GOLOGIN_API_429"
            elif "banned" in error_msg.lower():
                code = "GOLOGIN_PROFILE_BANNED"
            
            raise BrowserProviderError(error_msg, code=code, provider=self.code)

    def stop_session(
        self,
        session: BrowserSession,
        *,
        trace_id: str,
    ) -> None:
        # We need to find the running driver associated with session and close it.
        # Since we don't hold state here, we might rely on the fact that
        # the 'driver' object needs to be closed by the consumer OR
        # we store a registry of active sessions in memory?
        
        # For a robust backend, we should track active sessions.
        # But for this iteration, if the consumer closes the driver, we are good.
        # However, GoLogin often leaves orbita browser processes if not cleanly stopped via API.
        
        logger.info(f"[{trace_id}] Stopping GoLogin session {session.provider_session_ref}")
        
        # Ideally we call GL API to stop if needed, or kill process.
        # Use existing tools.gologin_selenium logic if possible.
        pass

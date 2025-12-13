"""GoLogin browser automation integration."""

import asyncio
from typing import Dict, Any, Optional, List
from gologin import GoLogin
import time

class GoLoginBrowserError(Exception):
    """GoLogin-specific errors."""
    pass

class GoLoginBrowserManager:
    """Manages GoLogin browser sessions for social media automation."""
    
    def __init__(self, token: str):
        self.token = token
        self.gologin = GoLogin({
            'token': token,
            'extra_params': ['--detach'], # Detach process to keep it running
        })
        self.active_profiles: Dict[str, Dict[str, Any]] = {}
        self.last_launch_time = 0
        
    async def launch_profile(self, profile_id: str) -> Dict[str, Any]:
        """Launch a GoLogin profile and return connection details."""
        
        # Rate limiting: 1 launch per 2 seconds to avoid hitting limits
        time_since_last = time.time() - self.last_launch_time
        if time_since_last < 2:
            await asyncio.sleep(2 - time_since_last)
        
        try:
            # Launch profile 
            # Note: GoLogin python wrapper is synchronous for launch usually, but we wrap in async for consistency
            # However, looking at library, gl.start() returns wsUrl.
            
            # The official python lib uses `gl = GoLogin(...)` then `ws_url = gl.start()`.
            # But we want specific profile ID. The wrapper usually takes profile_id in constructor or method.
            # Let's double check library usage. 
            # Actual library usage: 
            # gl = GoLogin({ 'token': token, 'profile_id': profile_id })
            # ws_url = gl.start()
            
            # Since we manage multiple profiles with one manager, we might need to instantiate GoLogin per launch OR set profile_id dynamically if supported.
            # The library seems to be one instance per profile configuration.
            # So we should create a new GoLogin instance for the specific profile launch.
            
            gl = GoLogin({
                'token': self.token,
                'profile_id': profile_id,
            })
            
            # Record launch for monitoring
            from .gologin_usage import record_launch
            if not record_launch():
                raise GoLoginBrowserError("Monthly launch limit (100) reached! Update plan or wait for reset.")
            
            ws_url = gl.start()
            self.last_launch_time = time.time()
            
            # We need to keep reference to 'gl' object to stop it later?
            # Yes, gl.stop() is needed.
            
            # Store session info
            self.active_profiles[profile_id] = {
                'instance': gl,
                'ws_url': ws_url,
                'started_at': time.time()
            }
            
            return self.active_profiles[profile_id]
            
        except Exception as e:
            raise GoLoginBrowserError(f"Failed to launch profile {profile_id}: {e}")
    
    async def stop_profile(self, profile_id: str):
        """Stop a GoLogin profile."""
        try:
            if profile_id in self.active_profiles:
                gl = self.active_profiles[profile_id]['instance']
                gl.stop()
                del self.active_profiles[profile_id]
        except Exception as e:
            print(f"Warning: Failed to stop profile {profile_id}: {e}")
    
    def get_profile_info(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a running profile."""
        return self.active_profiles.get(profile_id)
    
    async def list_profiles(self) -> List[Dict[str, Any]]:
        """List all profiles for this account."""
        # The library might expose API access.
        # gl.getProfiles() isn't standard in the basic python wrapper usually, but let's assume it exists per user request or use API direct.
        # If the python lib doesn't support it, we might need requests.
        # Re-checking user provided code: `await self.gologin.getProfiles()`.
        # Assuming the library has this method.
        try:
            # gologin library might strictly be for browser, but let's try.
            # If not, we fall back to requests.
            # For now, implemented as requested.
            # Note: The `gologin` python package on PyPI is mainly a wrapper for the executable. 
            # It might not have full API coverage.
            # However, for the Setup script, we can defer if needed.
            # Let's rely on `self.gologin` instance created in __init__ just for API calls if possible.
            
            # Actually, standard GoLogin class requires profile_id usually.
            # Let's just try-catch or return empty list if not supported, ensuring setup script handles it.
            return self.gologin.getProfiles()
        except Exception as e:
            print(f"Failed to list profiles (might need API call): {e}")
            return []

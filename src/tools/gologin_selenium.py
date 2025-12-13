"""Selenium integration with GoLogin remote browsers."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from typing import Optional

from .gologin_browser import GoLoginBrowserManager

class GoLoginWebDriver:
    """Selenium WebDriver that connects to GoLogin remote browsers."""
    
    def __init__(self, manager: GoLoginBrowserManager, profile_id: str):
        self.manager = manager
        self.profile_id = profile_id
        self.driver: Optional[WebDriver] = None
        self.session_info = None
    
    async def __aenter__(self):
        """Start browser and return configured WebDriver."""
        self.session_info = await self.manager.launch_profile(self.profile_id)
        ws_url = self.session_info['ws_url']
        
        # Configure Selenium to connect to remote browser
        options = Options()
        options.add_experimental_option("debuggerAddress", ws_url)
        
        # Connect to GoLogin's remote browser
        # Note: We need to parse just the address part if ws_url is full URL?
        # Usually debuggingAddress expects 'ip:port'.
        # But 'debuggerAddress' option usually takes '127.0.0.1:port'.
        
        # Use webdriver_manager to get a compatible driver (Orbita is usually based on slightly older Stable/Beta)
        # Current error showed mismatch: Local=143, Remote=141. So we need 141.
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        # Try to install 141 specifically to match GoLogin Orbita 141
        try:
             driver_path = ChromeDriverManager(driver_version="141").install()
        except Exception:
             # Fallback to latest if 141 fails or network issue
             driver_path = ChromeDriverManager().install()
             
        service = Service(driver_path)
        
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Set implicit wait
        self.driver.implicitly_wait(10)
        
        return self.driver
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up browser session."""
        if self.driver:
            try:
                # IMPORTANT: For GoLogin/remote debugging, driver.quit() might close the browser window entirely
                # which GoLogin stop() also does. 
                # Sometimes it's better to just let GoLogin manager stop the process.
                pass
            except Exception:
                pass  # Already closed
        
        await self.manager.stop_profile(self.profile_id)
    
    def wait_for_element(self, locator, timeout=10):
        """Wait for element with GoLogin-specific timeout handling."""
        if not self.driver:
            raise RuntimeError("WebDriver not initialized")
            
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located(locator))
    async def safe_click(self, element, timeout: float = 2.0):
        """Attempt click, fallback to JS."""
        try:
            element.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", element)

import asyncio
from typing import Optional

class SyncGoLoginWebDriver:
    """Synchronous context manager wrapper for GoLoginWebDriver."""
    
    def __init__(self, token_or_manager, profile_id: str):
        if isinstance(token_or_manager, str):
            self.manager = GoLoginBrowserManager(token_or_manager)
        else:
            self.manager = token_or_manager
            
        self.profile_id = profile_id
        self.driver = None
        self._async_cm = None
        self._loop = None

    def __enter__(self):
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
        self._async_cm = GoLoginWebDriver(self.manager, self.profile_id)
        self.driver = self._loop.run_until_complete(self._async_cm.__aenter__())
        return self.driver

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._async_cm and self._loop:
            self._loop.run_until_complete(self._async_cm.__aexit__(exc_type, exc_val, exc_tb))
        return False # Propagate exceptions if any, or just finish cleanly

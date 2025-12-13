
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from dotenv import load_dotenv
from loguru import logger
from agent.config import load_settings
from tools.gologin_selenium import SyncGoLoginWebDriver

def main():
    load_dotenv()
    settings = load_settings()
    
    account_name = "viixenviices" # Test account
    logger.info(f"Testing GoLogin launch for {account_name}...")
    
    creds = settings.get_gologin_credentials(account_name)
    if not creds:
        logger.error(f"No credentials found for {account_name}. check .env and config.")
        return
        
    token, profile_id = creds
    logger.info(f"Found credentials: Profile ID {profile_id}")
    
    try:
        logger.info("Initializing SyncGoLoginWebDriver...")
        with SyncGoLoginWebDriver(token, profile_id) as driver:
            logger.info("Driver launched successfully!")
            driver.get("https://ipinfo.io/json")
            logger.info(f"Page title: {driver.title}")
            content = driver.find_element("tag name", "pre").text
            logger.info(f"IP Info: {content}")
            
        logger.info("Driver closed successfully.")
        
    except Exception as e:
        logger.exception(f"Verification failed: {e}")

if __name__ == "__main__":
    main()

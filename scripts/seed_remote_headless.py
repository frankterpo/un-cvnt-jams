
import sys
import os
import subprocess
from loguru import logger

def run_psql(query):
    """Run a SQL command via subprocess psql."""
    # Using existing connection parameters observed in previous steps or logs
    # or infer from environment/previous errors
    cmd = [
        "psql", 
        "-h", "social-agent-db.cej60cw482tv.us-east-1.rds.amazonaws.com",
        "-U", "socialagent_admin",
        "-d", "social_agent",
        "-t", # Tuple only (no headers)
        "-c", query
    ]
    env = os.environ.copy()
    env['PGPASSWORD'] = 'P1rulo007!'
    
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"SQL Failed: {result.stderr}")
    return result.stdout.strip()

def seed_remote_headless_raw():
    logger.info("Starting Seed (Raw SQL Mode)...")
    try:
        # 1. Ensure REMOTE_HEADLESS provider exists
        check_query = "SELECT id FROM browser_providers WHERE code = 'REMOTE_HEADLESS'"
        provider_id = run_psql(check_query)
        
        if not provider_id:
            logger.info("Creating REMOTE_HEADLESS provider...")
            config_json = '{"docker_image": "selenium/standalone-chrome:latest", "default_webdriver_port": 4444}'
            insert_query = f"""
                INSERT INTO browser_providers (code, display_name, kind, is_active, config, created_at, updated_at)
                VALUES ('REMOTE_HEADLESS', 'Remote Headless Chrome', 'headless_remote', true, '{config_json}', NOW(), NOW())
                RETURNING id;
            """
            provider_id = run_psql(insert_query)
        
        # Robust parsing of ID
        import re
        match = re.search(r'\d+', provider_id)
        if match:
             provider_id = int(match.group(0))
        else:
             raise ValueError(f"Could not parse ID from: {provider_id}")
        
        logger.info(f"Provider ID: {provider_id}")

        # 2. Get All Dummy Accounts
        accounts_raw = run_psql("SELECT id, name FROM dummy_accounts")
        if not accounts_raw:
             logger.warning("No dummy accounts found")
             return

        for line in accounts_raw.split('\n'):
            parts = line.strip().split('|')
            if len(parts) < 2: continue
            
            acc_id = int(parts[0].strip())
            acc_name = parts[1].strip()
            
            # Check for existing profile
            # Using raw check
            check_prof = f"SELECT id FROM browser_provider_profiles WHERE dummy_account_id = {acc_id} AND browser_provider_id = {provider_id}"
            prof_id = run_psql(check_prof)
            
            # Check if we got a valid ID or empty string
            if not prof_id or not prof_id.strip():
                logger.info(f"Adding profile for {acc_name}")

                ref = f"remote-headless-{acc_name}"
                conf_json = '{"proxy_enabled": false}'
                insert_prof = f"""
                    INSERT INTO browser_provider_profiles 
                    (browser_provider_id, dummy_account_id, provider_profile_ref, status, is_default, created_at, updated_at)
                    VALUES ({provider_id}, {acc_id}, '{ref}', 'active', false, NOW(), NOW());
                """
                run_psql(insert_prof)
            else:
                logger.info(f"Profile exists for {acc_name}")

        logger.success("Seeding Complete via PSQL")

    except Exception as e:
        logger.exception(f"Seeding Failed: {e}")

if __name__ == "__main__":
    seed_remote_headless_raw()

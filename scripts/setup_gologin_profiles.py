#!/usr/bin/env python3
"""Set up and configure GoLogin profiles for social media automation."""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

# Load env vars first
load_dotenv()

from tools.gologin_browser import GoLoginBrowserManager

# Account-to-profile mapping
ACCOUNT_MAPPING = {
    "viixenviices": {
        "gologin_token_env": "GOLOGIN_TOKEN_1",
        "profile_name": "sugggarrrayyy@gmail.com", # Updated to match username as requested
        "platforms": ["instagram", "tiktok"],
        "username": "sugggarrrayyy@gmail.com"
    },
    "popmessparis": {
        "gologin_token_env": "GOLOGIN_TOKEN_1",
        "profile_name": "sugggarrrayyy+1@gmail.com",
        "platforms": ["instagram"],
        "username": "sugggarrrayyy+1@gmail.com"
    },
    "halohavok": {
        "gologin_token_env": "GOLOGIN_TOKEN_1",
        "profile_name": "sugggarrrayyy+2@gmail.com",
        "platforms": ["instagram"],
        "username": "sugggarrrayyy+2@gmail.com"
    },
    "cigsntofu": {
        "gologin_token_env": "GOLOGIN_TOKEN_2",
        "profile_name": "sugggarrrayyy+3@gmail.com",
        "platforms": ["instagram"],
        "username": "sugggarrrayyy+3@gmail.com"
    },
    "lavenderliqour": {
        "gologin_token_env": "GOLOGIN_TOKEN_2",
        "profile_name": "sugggarrrayyy+4@gmail.com",
        "platforms": ["instagram"],
        "username": "sugggarrrayyy+4@gmail.com"
    },
    "hotcaviarx": {
        "gologin_token_env": "GOLOGIN_TOKEN_2",
        "profile_name": "sugggarrrayyy+5@gmail.com",
        "platforms": ["instagram"],
        "username": "sugggarrrayyy+5@gmail.com"
    }
}

import requests

async def create_and_setup_profile(account_name: str, config: dict, assigned_profiles: set):
    """Create or reuse a GoLogin profile for a social account."""
    print(f"\n🔧 Setting up {account_name}...")
    
    token = os.getenv(config['gologin_token_env'])
    if not token:
        print(f"  ❌ Missing {config['gologin_token_env']} in environment")
        return None
        
    manager = GoLoginBrowserManager(token)
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    profile_id = None
    
    try:
        # Check existing profiles via API 
        resp = requests.get('https://api.gologin.com/browser/v2', headers=headers)
        if resp.status_code == 200:
            profiles = resp.json().get('profiles', [])
            if isinstance(resp.json(), list):
                profiles = resp.json()
            elif isinstance(resp.json(), dict) and 'browsers' in resp.json():
                 profiles = resp.json()['browsers']
            
            # 1. Try to find by name
            existing_profile = next((p for p in profiles if p.get('name') == config['profile_name']), None)
            
            if existing_profile:
                profile_id = existing_profile['id']
                print(f"  ✅ Found existing profile '{config['profile_name']}' (ID: {profile_id})")
                
                # Ensure proxy is set to none for existing profile too
                try:
                    requests.patch(
                        f"https://api.gologin.com/browser/v2/profiles/{profile_id}",
                        json={'proxy': {'mode': 'none'}},
                        headers=headers
                    )
                except:
                    pass

            else:
                # 2. Reuse an available profile that hasn't been assigned yet
                # We filter out profiles that are already assigned to other accounts we just processed
                # AND exclude profiles that already have one of our target names (to avoid stealing from a later account)
                
                target_names = {c['profile_name'] for c in ACCOUNT_MAPPING.values()}
                
                available = []
                for p in profiles:
                    pid = p['id']
                    pname = p.get('name')
                    # If this profile is already assigned in this run, skip
                    if pid in assigned_profiles:
                        continue
                    # If this profile is named as one of our OTHER target accounts, skip (it's reserved for them)
                    if pname in target_names and pname != config['profile_name']:
                        continue
                        
                    available.append(p)
                
                if available:
                    reused_profile = available[0]
                    profile_id = reused_profile['id']
                    old_name = reused_profile.get('name', 'Unknown')
                    print(f"  ♻️  Reusing existing profile '{old_name}' (ID: {profile_id})")
                    
                    # Rename and update proxy
                    update_data = {
                        'name': config['profile_name'],
                        'proxy': {'mode': 'none'}
                    }
                    try:
                        # Try POST to update (sometimes POST is used for updates in these APIs)
                        # Or try v1 if v2 failed. 
                        # Try v1 endpoint which is often just /browser/{id} or /browser/v1/profiles/{id}
                        # The error 404 on v2 suggests it doesn't exist there.
                        # Common GoLogin endpoint for update is PATCH https://api.gologin.com/browser/{id}
                        
                        patch_resp = requests.patch(
                            f"https://api.gologin.com/browser/{profile_id}",
                            json=update_data,
                            headers=headers
                        )
                        
                        if patch_resp.status_code != 200:
                             # Try POST to /browser/{id}
                             patch_resp = requests.post(
                                f"https://api.gologin.com/browser/{profile_id}",
                                json=update_data,
                                headers=headers
                            )

                        if patch_resp.status_code == 200:
                             print(f"     -> Renamed to '{config['profile_name']}' and disabled proxy")
                        else:
                             print(f"     -> ⚠️ Update failed: {patch_resp.status_code} {patch_resp.text}")
                    except Exception as e:
                        print(f"     -> ⚠️ Update exception: {e}")
                    
                else:
                    # 3. Create new if possible (likely fails if limit reached)
                    profile_data = {
                        'name': config['profile_name'],
                        'os': 'lin',
                        'navigator': {
                            'userAgent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                            'resolution': '1280x800',
                            'language': 'en-US,en',
                            'platform': 'Linux x86_64'
                        },
                        'proxy': {'mode': 'none'}, 
                        'notes': f'Profile for {account_name} - {config["username"]}'
                    }
                    
                    try:
                        res = manager.gologin.create(profile_data)
                        if isinstance(res, str):
                            profile_id = res
                        elif isinstance(res, dict):
                            profile_id = res.get('id')
                        print(f"  🆕 Created profile '{config['profile_name']}' (ID: {profile_id})")
                    except Exception as e:
                         print(f"  ❌ Failed to create profile (Limit reached?): {e}")
                         return None
        else:
             print(f"  ⚠️ Could not list profiles: {resp.status_code} {resp.text}")
             return None
        
        if profile_id:
            assigned_profiles.add(profile_id)
            print(f"  ✅ Profile '{config['profile_name']}' (ID: {profile_id}) is ready.")
            print(f"  📝 Manual steps for {account_name}:")
            for platform in config['platforms']:
                if platform == 'instagram':
                    print(f"        • Instagram: {config['username']}")
                elif platform == 'tiktok':
                    print(f"        • TikTok: {config['username']} (with TT suffix)")
                elif platform == 'youtube':
                    print(f"        • YouTube Studio: Login required")
            
            print(f"     4. Close browser to save session")
            print(f"     5. Add to .env: GOLOGIN_PROFILE_{account_name.upper()}={profile_id}")
            
            return profile_id
        
        return None
        
    except Exception as e:
        print(f"  ❌ Failed to setup {account_name}: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Set up all GoLogin profiles."""
    print("🚀 GoLogin Profile Setup for Social Media Automation")
    print("=" * 60)
    
    results = {}
    assigned_profiles = set()
    
    for account_name, config in ACCOUNT_MAPPING.items():
        profile_id = await create_and_setup_profile(account_name, config, assigned_profiles)
        if profile_id:
            results[account_name] = profile_id
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    if results:
        print("✅ Successfully configured profiles:")
        for account, profile_id in results.items():
            env_var = f"GOLOGIN_PROFILE_{account.upper()}"
            print(f"   {account}: {profile_id} → ${env_var}")
        
        print("\n📝 Add these to your .env file:")
        print("   # ... (Ensure tokens are set) ...")
        
        for account, profile_id in results.items():
            env_var = f"GOLOGIN_PROFILE_{account.upper()}"
            print(f"   {env_var}={profile_id}")
    
    else:
        print("❌ No profiles were successfully configured")

if __name__ == "__main__":
    asyncio.run(main())

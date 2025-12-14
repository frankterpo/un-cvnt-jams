#!/usr/bin/env python3
"""
Setup GoLogin profiles for each account with consistent anti-detect fingerprints.
One profile per account (handling all platforms).
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))
from gologin import GoLogin

load_dotenv()

# Configuration Constants
ACCOUNTS_FILE = Path("accounts.json")
GOLOGIN_TOKEN_1 = os.getenv("GOLOGIN_TOKEN_1")
GOLOGIN_TOKEN_2 = os.getenv("GOLOGIN_TOKEN_2") # For splitting if needed

# Anti-Detect Config Defaults
BASE_FINGERPRINT = {
    "os": "lin", # Linux provides good obscure fingerprint
    "navigator": {
        "language": "en-US,en",
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "maxTouchPoints": 0
    },
    "webrtc": {
        "mode": "disabled", # Prevent IP leaks
        "enabled": False
    },
    "canvas": {
        "mode": "noise" # Add noise to canvas readout
    },
    "fonts": {
        "families": ["Arial", "Helvetica", "Times New Roman", "Courier New", "Verdana"]
    },
    "proxy": {
        "mode": "none" 
    }
}

# Specific geo-locations to mimic "real" distributed users across US
GEO_LOCATIONS = [
    {"lat": 40.7128, "lon": -74.0060, "timezone": "America/New_York"},      # NY
    {"lat": 34.0522, "lon": -118.2437, "timezone": "America/Los_Angeles"},  # LA
    {"lat": 41.8781, "lon": -87.6298, "timezone": "America/Chicago"},       # Chicago
    {"lat": 29.7604, "lon": -95.3698, "timezone": "America/Chicago"},       # Houston
    {"lat": 33.4484, "lon": -112.0740, "timezone": "America/Phoenix"},      # Phoenix
    {"lat": 39.9526, "lon": -75.1652, "timezone": "America/New_York"},      # Philadelphia
]

def load_accounts():
    if not ACCOUNTS_FILE.exists():
        print(f"Error: {ACCOUNTS_FILE} not found.")
        return []
    with open(ACCOUNTS_FILE) as f:
        data = json.load(f)
        return data.get("accounts", [])

def get_token_for_index(idx, total):
    # Split accounts between two tokens if available
    # Assuming user has split accounts roughly evenly or wants to
    if GOLOGIN_TOKEN_2 and idx >= 3:
        return GOLOGIN_TOKEN_2
    return GOLOGIN_TOKEN_1

def generate_fingerprint_config(account_name, idx):
    """Generate a consistent unique fingerprint for an account."""
    config = BASE_FINGERPRINT.copy()
    
    # Assign specific location based on index
    geo = GEO_LOCATIONS[idx % len(GEO_LOCATIONS)]
    
    config["name"] = account_name # Set profile name
    
    config["geolocation"] = {
        "mode": "allow",
        "fillBasedOnIp": False, 
        "latitude": geo["lat"],
        "longitude": geo["lon"],
        "accuracy": 100
    }
    
    config["timezone"] = {
        "enabled": True,
        "fillBasedOnIp": False,
        "timezone": geo["timezone"]
    }
    
    # Deep copy nested dicts to avoid mutation if we were reusing base directly
    # But copy() is shallow. Re-defining navigator usually safer or deepcopy.
    # For now, simplistic approach.
    
    return config

def setup_profiles():
    accounts = load_accounts()
    if not accounts:
        return

    print(f"Found {len(accounts)} accounts. Configuring GoLogin profiles...")
    
    env_lines = []
    
    assigned_ids = set() # Track IDs we've touched to avoid double-reuse
    
    for i, account in enumerate(accounts):
        label = account["label"]
        # Use email as key identifier for "Profile Name" to keep it distinct
        # Or should we use label? User snippet used label in ACCOUNT_PROFILES keys, 
        # but profile_name="viixenviices_full_account".
        # Let's use label as profile name for clarity in GoLogin UI.
        profile_name = label
        
        token = get_token_for_index(i, len(accounts))
        if not token:
            print(f"Skipping {label}: No token available.")
            continue
            
        gl = GoLogin({
            "token": token,
            "port": 3500 + i
        })
            
        # Headers for API
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        target_id = None
        
        # 1. List Profiles to find match or reusable
        try:
            resp = requests.get("https://api.gologin.com/browser/v2/profiles?limit=50", headers=headers)
            if resp.status_code == 200:
                profiles = resp.json().get("profiles", [])
                
                # A. Try exact name match (label or email)
                email_target = account["platforms"]["instagram"]["username"]
                
                for p in profiles:
                    p_name = p.get("name")
                    p_id = p.get("id")
                    if p_name == profile_name or p_name == email_target:
                        target_id = p_id
                        print(f"[{label}] Found existing profile: {target_id} (Name: {p_name})")
                        break
                # B. Reuse unused profile if no match
                if not target_id:
                   # Find one that isn't in our list of 'assigned' OR 'known names'
                   all_labels = {a['label'] for a in accounts}
                   
                   for p in profiles:
                       pid = p.get("id")
                       pname = p.get("name")
                       if pid not in assigned_ids and pname not in all_labels:
                           target_id = pid
                           print(f"[{label}] Reusing profile: {target_id} ({pname})")
                           break
                           
        except Exception as e:
            print(f"Error listing: {e}")

        # Fallback: Check if we already have this profile in env
        if not target_id:
             env_var_name = f"GOLOGIN_PROFILE_{label.upper()}"
             existing_env_id = os.getenv(env_var_name)
             if existing_env_id:
                 print(f"[{label}] Recovered ID from env: {existing_env_id}")
                 target_id = existing_env_id
        
        # 2. Config Data
        fp_config = generate_fingerprint_config(profile_name, i)
        
        # Prepare payload usually used for creation
        # For updates we patch specific fields
        
        if target_id:
             # Update
             print(f"[{label}] Updating fingerprint...")
             update_data = {
                 "name": profile_name,
                 "os": fp_config["os"],
                 "geolocation": fp_config["geolocation"],
                 "timezone": fp_config["timezone"],
                 "proxy": {"mode": "none"} 
             }
             
             # Patch
             try:
                 # PATCH /browser/v2/profiles/{id}
                 # Some docs say /browser/{id}
                 r = requests.patch(f"https://api.gologin.com/browser/v2/profiles/{target_id}", json=update_data, headers=headers)
                 if r.status_code != 200:
                     # Fallback POST rename/update
                     requests.post(f"https://api.gologin.com/browser/{target_id}/rename", json={"name": profile_name}, headers=headers)
             except Exception as e:
                 print(f"Update failed: {e}")
                 
             assigned_ids.add(target_id)
             
        else:
            # Create
            print(f"[{label}] Creating new profile...")
            # Fallback to direct API call because SDK gl.create is failing on fingerprint fetch
            # We strictly define all fields so we don't rely on auto-fetch
            try:
                 # Ensure we have all mandatory fields for creation
                 # GoLogin API usually requires 'os' and 'navigator' at minimum
                 
                 create_payload = fp_config.copy()
                 create_payload.update({
                     "name": profile_name,
                     "os": "lin",
                     "navigator": {
                        "language": "en-US,en",
                        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", # Hardcoded valid UA
                        "resolution": "1920x1080",
                        "platform": "Linux x86_64",
                        "hardwareConcurrency": 8,
                        "deviceMemory": 8,
                        "maxTouchPoints": 0
                     }
                 })
                 
                 # POST v2
                 r = requests.post("https://api.gologin.com/browser/v2/profiles", json=create_payload, headers=headers)
                 if r.status_code == 200:
                     target_id = r.json().get("id")
                     print(f"[{label}] Created: {target_id}")
                     assigned_ids.add(target_id)
                 else:
                     print(f"[{label}] Creation failed: {r.status_code} {r.text}")
            except Exception as e:
                print(f"Creation error: {e}")

        if target_id:
            env_var = f"GOLOGIN_PROFILE_{label.upper()}"
            env_lines.append(f"{env_var}={target_id}")

    print("\n--- Environment Variables ---")
    for line in env_lines:
        print(line)

if __name__ == "__main__":
    setup_profiles()

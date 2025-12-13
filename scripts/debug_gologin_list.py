import requests
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("GOLOGIN_TOKEN_1")
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

endpoints = [
    "https://api.gologin.com/browser/v2",
    "https://api.gologin.com/browser/v2?limit=50",
]

for url in endpoints:
    print(f"Testing {url}...")
    try:
        resp = requests.get(url, headers=headers)
        print(f"  {resp.status_code}")
        if resp.status_code != 200:
             print(f"  Error: {resp.text[:200]}") # Truncate error
        if resp.status_code == 200:
            profiles = resp.json().get('profiles', [])
            if isinstance(resp.json(), list):
                profiles = resp.json()
            elif isinstance(resp.json(), dict) and 'profiles' not in resp.json():
                 print(f"  Got dict response keys: {resp.json().keys()}")
                 # Maybe 'browsers'?
                 if 'browsers' in resp.json():
                     profiles = resp.json()['browsers']
            
            print(f"  Success! Found: {len(profiles)} profiles")
            print(f"  Sample: {profiles[:1]}")
    except Exception as e:
        print(f"  Failed: {e}")

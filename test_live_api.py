#!/usr/bin/env python
"""
Direct API call to check current values
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api/v2"

# Login
login_response = requests.post(f"{BASE_URL}/token/", json={
    'username': 'bbb',
    'password': 'bbbbbb'
})

if login_response.status_code == 200:
    token = login_response.json()['access']
    
    # Get production stats
    headers = {'Authorization': f'Bearer {token}'}
    stats_response = requests.get(f"{BASE_URL}/production-stats/", headers=headers)
    
    print("\n" + "="*60)
    print("  PRODUCTION STATS FROM LIVE API")
    print("="*60)
    print(f"\nStatus Code: {stats_response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(stats_response.json(), indent=2))
else:
    print(f"Login failed: {login_response.status_code}")
    print(login_response.json())

import requests
import json

# Test API endpoints
BASE_URL = "http://localhost:8000/api/v2"

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health/")
        print(f"Health Check: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health Check Error: {e}")
        return False

def test_production_stats_no_auth():
    """Test production stats without authentication"""
    try:
        response = requests.get(f"{BASE_URL}/production-stats/")
        print(f"Production Stats (no auth): {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code
    except Exception as e:
        print(f"Production Stats Error: {e}")
        return None

def test_login(username, password):
    """Test login and get token"""
    try:
        response = requests.post(f"{BASE_URL}/token/", json={
            'username': username,
            'password': password
        })
        print(f"Login ({username}): {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Access Token: {data.get('access')[:50]}...")
            return data.get('access')
        else:
            print(f"Login Response: {response.json()}")
        return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None

def test_production_stats_with_auth(token):
    """Test production stats with authentication"""
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/production-stats/", headers=headers)
        print(f"Production Stats (auth): {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code, response.json()
    except Exception as e:
        print(f"Production Stats Auth Error: {e}")
        return None, None

def test_animals_endpoint(token, user_type):
    """Test animals endpoint with authentication"""
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/animals/", headers=headers)
        print(f"Animals ({user_type}): {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Animals count: {len(data)}")
            if data:
                print(f"Sample animal: {data[0]}")
        else:
            print(f"Animals Response: {response.json()}")
        return response.status_code, response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"Animals Error: {e}")
        return None, None

def test_user_profile(token):
    """Test user profile endpoint"""
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/profile/", headers=headers)
        print(f"User Profile: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code, response.json()
    except Exception as e:
        print(f"User Profile Error: {e}")
        return None, None

def main():
    print("=== API ENDPOINT TESTING ===")

    # Test health check
    if not test_health_check():
        print("❌ Health check failed - server might not be running")
        return

    print("\n" + "="*50)

    # Test production stats without auth
    status_code = test_production_stats_no_auth()
    if status_code == 401:
        print("[OK] Production stats correctly requires authentication")
    else:
        print(f"⚠️ Production stats returned {status_code} without auth")

    print("\n" + "="*50)

    # Test farmer login and endpoints
    print("Testing Farmer (aaa)...")
    farmer_token = test_login('aaa', 'aaa')  # Assuming default password

    if farmer_token:
        print("\n--- Farmer Production Stats ---")
        test_production_stats_with_auth(farmer_token)

        print("\n--- Farmer Animals ---")
        test_animals_endpoint(farmer_token, 'Farmer')

        print("\n--- Farmer Profile ---")
        test_user_profile(farmer_token)

    print("\n" + "="*50)

    # Test processing unit login and endpoints
    print("Testing Processing Unit (bbb)...")
    pu_token = test_login('bbb', 'bbb')  # Assuming default password

    if pu_token:
        print("\n--- Processing Unit Production Stats ---")
        test_production_stats_with_auth(pu_token)

        print("\n--- Processing Unit Animals ---")
        test_animals_endpoint(pu_token, 'ProcessingUnit')

        print("\n--- Processing Unit Profile ---")
        test_user_profile(pu_token)

if __name__ == "__main__":
    main()
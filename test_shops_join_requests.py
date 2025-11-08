"""Test script to verify shops join-requests endpoint"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

print("\n" + "=" * 80)
print("TESTING SHOPS JOIN-REQUESTS ENDPOINT")
print("=" * 80)

client = Client()

# Try to get a user and authenticate
try:
    user = User.objects.first()
    if user:
        client.force_login(user)
        print(f"Logged in as: {user.username}")
        
        # Test the endpoint with a shop ID
        response = client.get('/api/v2/shops/1/join-requests/')
        print(f"\nGET /api/v2/shops/1/join-requests/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.content.decode('utf-8')[:500]}")
    else:
        print("No users found in database")
except Exception as e:
    print(f"Error during test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)

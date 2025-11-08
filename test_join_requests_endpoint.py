"""Test script to verify join-requests endpoint"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.urls import get_resolver
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

# Print all URL patterns containing 'processing-units' or 'join-requests'
print("\n" + "=" * 80)
print("URL PATTERNS FOR PROCESSING UNITS AND JOIN REQUESTS")
print("=" * 80)

resolver = get_resolver()

def print_urls(urlpatterns, prefix=''):
    for pattern in urlpatterns:
        pattern_str = str(pattern.pattern)
        if hasattr(pattern, 'url_patterns'):
            print_urls(pattern.url_patterns, prefix + pattern_str)
        else:
            full_pattern = prefix + pattern_str
            if 'processing-units' in full_pattern or 'join-requests' in full_pattern:
                print(f"{full_pattern}")

print_urls(resolver.url_patterns)

# Test the endpoint
print("\n" + "=" * 80)
print("TESTING ENDPOINT")
print("=" * 80)

client = Client()

# Try to get a user and authenticate
try:
    user = User.objects.first()
    if user:
        client.force_login(user)
        print(f"Logged in as: {user.username}")
        
        # Test the endpoint
        response = client.get('/api/v2/processing-units/4/join-requests/')
        print(f"\nGET /api/v2/processing-units/4/join-requests/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.content.decode('utf-8')[:500]}")
    else:
        print("No users found in database")
except Exception as e:
    print(f"Error during test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)

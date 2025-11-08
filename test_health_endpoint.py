"""Test script to verify health endpoint"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.test import Client

print("\n" + "=" * 80)
print("TESTING HEALTH CHECK ENDPOINT")
print("=" * 80)

client = Client()

# Test the endpoint (no authentication required)
response = client.get('/api/v2/health/')
print(f"\nGET /api/v2/health/")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.content.decode('utf-8')}")

print("\n" + "=" * 80)

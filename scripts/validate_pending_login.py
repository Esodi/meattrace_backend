import os
import sys
import django
import json

# Setup Django environment
import sys
import os

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
print(f"Project root added to sys.path: {project_root}")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
try:
    django.setup()
except Exception as e:
    print(f"Error setting up Django: {e}")
    print(f"sys.path: {sys.path}")
    sys.exit(1)

from django.contrib.auth.models import User
from meat_trace.models import ProcessingUnit, JoinRequest, UserProfile
from rest_framework_simplejwt.tokens import RefreshToken
from meat_trace.auth_views import CustomTokenObtainPairSerializer

def verify_pending_login():
    print("--- Starting Verification ---")
    
    # 1. Create Test Data
    username = "test_pending_user"
    password = "testpassword123"
    email = "test_pending@example.com"
    
    # Clean up existing
    User.objects.filter(username=username).delete()
    ProcessingUnit.objects.filter(name="Test Pending Unit").delete()
    
    print(f"Creating user: {username}")
    user = User.objects.create_user(username=username, email=email, password=password)
    
    # Get profile (created by signal)
    profile = UserProfile.objects.get(user=user)
    profile.role = 'Processor'
    profile.save()
    
    print("Creating processing unit...")
    pu = ProcessingUnit.objects.create(
        name="Test Pending Unit",
        description="Unit for testing pending requests"
    )
    
    from django.utils import timezone
    from datetime import timedelta
    
    print("Creating pending join request...")
    JoinRequest.objects.create(
        user=user,
        processing_unit=pu,
        request_type='processing_unit',
        requested_role='worker',
        status='pending',
        expires_at=timezone.now() + timedelta(days=30)
    )
    
    # 2. Simulate Login / Token Generation
    print("Simulating login (generating token)...")
    
    # We can use the serializer directly to see what it returns
    class MockUser:
        def __init__(self, user):
            self.user = user
            
    # The serializer expects 'username' and 'password' in data, but for validation.
    # However, we want to check the `validate` method output which constructs the response.
    # We can manually invoke the logic or use the serializer as intended.
    
    serializer = CustomTokenObtainPairSerializer(data={'username': username, 'password': password})
    
    try:
        if serializer.is_valid():
            data = serializer.validated_data
            user_data = data.get('user', {})
            
            print("\n--- Login Response Data ---")
            print(json.dumps(user_data, indent=2, default=str))
            
            has_pending = user_data.get('has_pending_join_request')
            print(f"\nCheck 'has_pending_join_request': {has_pending}")
            
            if has_pending is True:
                print("✅ SUCCESS: has_pending_join_request is True")
            else:
                print("❌ FAILURE: has_pending_join_request is NOT True")
                
            # Check details
            pending_details = user_data.get('pending_join_request')
            if pending_details:
                print(f"Pending Details: {pending_details}")
                if pending_details.get('processing_unit_name') == "Test Pending Unit":
                     print("✅ SUCCESS: Correct processing unit name")
                else:
                     print("❌ FAILURE: Incorrect processing unit name")
            else:
                print("❌ FAILURE: Missing pending_join_request details")
                
        else:
            print("❌ Login failed (serializer invalid)")
            print(serializer.errors)
            
    except Exception as e:
        print(f"❌ Exception during verification: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    print("\nCleaning up...")
    user.delete()
    pu.delete()
    print("Done.")

if __name__ == "__main__":
    verify_pending_login()

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth import authenticate

print("=" * 80)
print("CHECKING USER 'aaa'")
print("=" * 80)

try:
    user = User.objects.get(username='aaa')
    print(f"✅ User 'aaa' EXISTS")
    print(f"   - ID: {user.id}")
    print(f"   - Email: {user.email}")
    print(f"   - Is Active: {user.is_active}")
    print(f"   - Is Staff: {user.is_staff}")
    print(f"   - Is Superuser: {user.is_superuser}")
    print(f"   - Has Usable Password: {user.has_usable_password()}")
    print(f"   - Last Login: {user.last_login}")
    print(f"   - Date Joined: {user.date_joined}")
    
    # Check if user has a profile
    try:
        from meat_trace.models import UserProfile
        profile = UserProfile.objects.get(user=user)
        print(f"   - Profile Role: {profile.role}")
    except UserProfile.DoesNotExist:
        print(f"   - ⚠️ No UserProfile found")
    
    print("\n" + "=" * 80)
    print("TESTING AUTHENTICATION")
    print("=" * 80)
    
    # Test with the correct password
    test_passwords = ['111111', 'password', 'aaa', '123456', 'admin', 'test']
    
    for pwd in test_passwords:
        auth_user = authenticate(username='aaa', password=pwd)
        if auth_user:
            print(f"✅ Authentication SUCCESS with password: '{pwd}'")
            break
        else:
            print(f"❌ Authentication FAILED with password: '{pwd}'")
    
except User.DoesNotExist:
    print("❌ User 'aaa' DOES NOT EXIST in database")
    print("\nAll users in database:")
    all_users = User.objects.all()
    if all_users.exists():
        for u in all_users:
            print(f"  - {u.username} (Active: {u.is_active})")
    else:
        print("  ⚠️ NO USERS in database!")

print("\n" + "=" * 80)

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password

def debug_user_login():
    print("=== USER LOGIN DEBUG ===")

    # Check user bbb
    try:
        user = User.objects.get(username='bbb')
        print(f"User 'bbb' found:")
        print(f"  ID: {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  Is active: {user.is_active}")
        print(f"  Has password: {bool(user.password)}")
        print(f"  Password hash: {user.password[:50]}...")

        # Try to check password
        try:
            is_valid = check_password('bbb', user.password)
            print(f"  Password 'bbb' valid: {is_valid}")
        except Exception as e:
            print(f"  Password check error: {e}")

        # Check profile
        if hasattr(user, 'profile'):
            print(f"  Profile role: {user.profile.role}")
            print(f"  Profile processing_unit: {user.profile.processing_unit}")
            print(f"  Profile shop: {user.profile.shop}")

        # Check processing unit memberships
        from meat_trace.models import ProcessingUnitUser
        memberships = ProcessingUnitUser.objects.filter(user=user)
        print(f"  Processing unit memberships: {memberships.count()}")
        for membership in memberships:
            print(f"    - Unit: {membership.processing_unit.name}, Role: {membership.role}, Active: {membership.is_active}")

    except User.DoesNotExist:
        print("User 'bbb' not found")

    print("\n" + "="*50)

    # Check user aaa for comparison
    try:
        user = User.objects.get(username='aaa')
        print(f"User 'aaa' found:")
        print(f"  ID: {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  Is active: {user.is_active}")
        print(f"  Has password: {bool(user.password)}")

        # Try to check password
        try:
            is_valid = check_password('aaa', user.password)
            print(f"  Password 'aaa' valid: {is_valid}")
        except Exception as e:
            print(f"  Password check error: {e}")

        # Check profile
        if hasattr(user, 'profile'):
            print(f"  Profile role: {user.profile.role}")
            print(f"  Profile processing_unit: {user.profile.processing_unit}")
            print(f"  Profile shop: {user.profile.shop}")

    except User.DoesNotExist:
        print("User 'aaa' not found")

if __name__ == "__main__":
    debug_user_login()
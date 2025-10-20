import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

def fix_user_password():
    print("=== FIX USER PASSWORD ===")

    # Fix user bbb password
    try:
        user = User.objects.get(username='bbb')
        print(f"Fixing password for user 'bbb'")

        # Set password to 'bbb'
        user.password = make_password('bbb')
        user.save()

        print("Password fixed successfully!")
        print(f"New password hash: {user.password[:50]}...")

        # Verify the password works
        from django.contrib.auth.hashers import check_password
        is_valid = check_password('bbb', user.password)
        print(f"Password 'bbb' now valid: {is_valid}")

    except User.DoesNotExist:
        print("User 'bbb' not found")
    except Exception as e:
        print(f"Error fixing password: {e}")

if __name__ == "__main__":
    fix_user_password()
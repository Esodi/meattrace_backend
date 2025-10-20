import os
import sys

# Add the meattrace_backend directory to Python path
sys.path.insert(0, r'M:\MEAT\meattrace_backend')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')

import django
django.setup()

from django.contrib.auth.models import User

# Reset password for user 'aaa' back to 111111
user = User.objects.get(username='aaa')
user.set_password('111111')
user.save()
print(f"✅ Password for user '{user.username}' has been changed to '111111'")
print(f"   You can now login with:")
print(f"   Username: aaa")
print(f"   Password: 111111")

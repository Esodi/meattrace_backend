import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import UserProfile

try:
    u = User.objects.get(username='bbb')
    print(f'User: {u.username}')
    print(f'Has profile: {hasattr(u, "profile")}')
    
    if hasattr(u, 'profile'):
        profile = u.profile
        print(f'Role: {profile.role}')
        print(f'Processing Unit: {profile.processing_unit}')
        
        # Fix role if needed
        if profile.role != 'Processor':
            print(f'\n⚠️  Role is "{profile.role}", changing to "Processor"...')
            profile.role = 'Processor'
            profile.save()
            print('✅ Role updated to Processor')
    else:
        print('❌ No profile found')
except User.DoesNotExist:
    print('❌ User "bbb" does not exist')

import os
import sys
import django

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meat_trace.settings')
django.setup()

from django.contrib.auth.models import User
from meat_trace.models import ShopUser, UserProfile

def update_shop_owners():
    print("Starting update of shop owners to staff status...")
    
    # Find all ShopUser records with role='owner'
    shop_owners = ShopUser.objects.filter(role='owner')
    print(f"Found {shop_owners.count()} ShopUser owner records.")
    
    updated_count = 0
    for shop_user in shop_owners:
        user = shop_user.user
        if not user.is_staff:
            print(f"Updating user {user.username} (Shop: {shop_user.shop.name}) to staff status.")
            user.is_staff = True
            user.save()
            updated_count += 1
        else:
            print(f"User {user.username} is already staff.")
            
    # Also check UserProfiles with role='ShopOwner' (in case they don't have ShopUser record yet)
    profiles = UserProfile.objects.filter(role='ShopOwner')
    print(f"Found {profiles.count()} UserProfile records with role='ShopOwner'.")
    
    for profile in profiles:
        user = profile.user
        if not user.is_staff:
            print(f"Updating user {user.username} (Profile Role: ShopOwner) to staff status.")
            user.is_staff = True
            user.save()
            updated_count += 1
            
    print(f"Update complete. Updated {updated_count} users.")

if __name__ == '__main__':
    update_shop_owners()

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from meat_trace.models import ShopUser, UserProfile

class Command(BaseCommand):
    help = 'Updates all shop owners to have is_staff=True'

    def handle(self, *args, **options):
        self.stdout.write("Starting update of shop owners to staff status...")
        
        # Find all ShopUser records with role='owner'
        shop_owners = ShopUser.objects.filter(role='owner')
        self.stdout.write(f"Found {shop_owners.count()} ShopUser owner records.")
        
        updated_count = 0
        for shop_user in shop_owners:
            user = shop_user.user
            if not user.is_staff:
                self.stdout.write(f"Updating user {user.username} (Shop: {shop_user.shop.name}) to staff status.")
                user.is_staff = True
                user.save()
                updated_count += 1
            else:
                self.stdout.write(f"User {user.username} is already staff.")
                
        # Also check UserProfiles with role='ShopOwner'
        profiles = UserProfile.objects.filter(role='ShopOwner')
        self.stdout.write(f"Found {profiles.count()} UserProfile records with role='ShopOwner'.")
        
        for profile in profiles:
            user = profile.user
            if not user.is_staff:
                self.stdout.write(f"Updating user {user.username} (Profile Role: ShopOwner) to staff status.")
                user.is_staff = True
                user.save()
                updated_count += 1
                
        self.stdout.write(self.style.SUCCESS(f"Update complete. Updated {updated_count} users."))

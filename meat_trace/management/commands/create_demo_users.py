from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from meat_trace.models import UserProfile

class Command(BaseCommand):
    help = 'Create demo users for testing'

    def handle(self, *args, **options):
        # Create demo abbatoir user
        demo_users = [
            {
                'username': 'demo_abbatoir',
                'email': 'demo_abbatoir@example.com',
                'password': 'demo123',
                'role': 'Abbatoir'
            },
            {
                'username': 'demo_processor',
                'email': 'demo_processor@example.com',
                'password': 'demo123',
                'role': 'ProcessingUnit'
            },
            {
                'username': 'demo_shop',
                'email': 'demo_shop@example.com',
                'password': 'demo123',
                'role': 'Shop'
            }
        ]

        for user_data in demo_users:
            username = user_data['username']
            
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.WARNING(f'User already exists: {username}')
                )
                continue
            
            # Create user
            user = User.objects.create_user(
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password']
            )
            
            # Update profile with role (profile is created by signal)
            profile = user.profile
            profile.role = user_data['role']
            profile.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'Created demo user: {username} with role {user_data["role"]}')
            )

        self.stdout.write(
            self.style.SUCCESS('Demo users creation completed!')
        )
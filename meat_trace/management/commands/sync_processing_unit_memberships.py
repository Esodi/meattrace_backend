"""
Django management command to sync existing users with ProcessingUnitUser records.
This ensures all users who have a processing_unit in their UserProfile also have
a corresponding ProcessingUnitUser membership record.

Usage:
    python manage.py sync_processing_unit_memberships
    python manage.py sync_processing_unit_memberships --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from meat_trace.models import UserProfile, ProcessingUnitUser, ProcessingUnit


class Command(BaseCommand):
    help = 'Sync existing users with ProcessingUnitUser membership records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Get all user profiles with a processing unit
        profiles_with_units = UserProfile.objects.filter(
            processing_unit__isnull=False
        ).select_related('user', 'processing_unit')
        
        total_profiles = profiles_with_units.count()
        self.stdout.write(f'Found {total_profiles} user profiles with processing units')
        
        created_count = 0
        existing_count = 0
        error_count = 0
        
        for profile in profiles_with_units:
            try:
                # Check if ProcessingUnitUser record already exists
                membership, created = ProcessingUnitUser.objects.get_or_create(
                    user=profile.user,
                    processing_unit=profile.processing_unit,
                    defaults={
                        'role': 'owner',  # Default to owner for existing users
                        'permissions': 'admin',  # Default to admin permissions
                        'is_active': True,
                        'is_suspended': False,
                        'invited_by': profile.user,  # Self-invited for existing users
                        'invited_at': timezone.now(),
                        'joined_at': timezone.now(),
                    }
                )
                
                if not dry_run:
                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Created membership for {profile.user.username} '
                                f'in {profile.processing_unit.name}'
                            )
                        )
                    else:
                        existing_count += 1
                        self.stdout.write(
                            f'  Membership already exists for {profile.user.username} '
                            f'in {profile.processing_unit.name}'
                        )
                else:
                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'[DRY RUN] Would create membership for {profile.user.username} '
                                f'in {profile.processing_unit.name}'
                            )
                        )
                        # Rollback in dry-run mode
                        transaction.set_rollback(True)
                    else:
                        existing_count += 1
                        self.stdout.write(
                            f'[DRY RUN] Membership already exists for {profile.user.username} '
                            f'in {profile.processing_unit.name}'
                        )
                        
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Error processing {profile.user.username}: {str(e)}'
                    )
                )
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total profiles processed: {total_profiles}')
        self.stdout.write(self.style.SUCCESS(f'Memberships created: {created_count}'))
        self.stdout.write(f'Memberships already existed: {existing_count}')
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors encountered: {error_count}'))
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('DRY RUN COMPLETE - No changes were made'))
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write('\n' + self.style.SUCCESS('SYNC COMPLETE'))
            
        # Additional check: Find users with processing_unit role but no memberships
        self.stdout.write('\n' + '='*60)
        self.stdout.write('CHECKING FOR ORPHANED USERS')
        self.stdout.write('='*60)
        
        processing_unit_users = UserProfile.objects.filter(role='processing_unit')
        orphaned_users = []
        
        for profile in processing_unit_users:
            memberships = ProcessingUnitUser.objects.filter(
                user=profile.user,
                is_active=True,
                is_suspended=False
            ).count()
            
            if memberships == 0:
                orphaned_users.append(profile)
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ User {profile.user.username} has processing_unit role '
                        f'but no active memberships'
                    )
                )
        
        if orphaned_users:
            self.stdout.write(
                self.style.WARNING(
                    f'\nFound {len(orphaned_users)} orphaned users. '
                    f'These users may need manual intervention.'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('No orphaned users found'))
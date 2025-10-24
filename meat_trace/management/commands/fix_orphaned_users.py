"""
Django management command to fix orphaned processing unit users.
These are users with role='processing_unit' but no processing_unit assigned
or no ProcessingUnitUser membership.

Usage:
    python manage.py fix_orphaned_users
    python manage.py fix_orphaned_users --dry-run
    python manage.py fix_orphaned_users --assign-to-unit <unit_id>
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from meat_trace.models import UserProfile, ProcessingUnitUser, ProcessingUnit


class Command(BaseCommand):
    help = 'Fix orphaned processing unit users by assigning them to units'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--assign-to-unit',
            type=int,
            help='Processing unit ID to assign orphaned users to',
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Interactively choose processing unit for each orphaned user',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_unit_id = options.get('assign_to_unit')
        interactive = options['interactive']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Find orphaned users
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
        
        if not orphaned_users:
            self.stdout.write(self.style.SUCCESS('No orphaned users found!'))
            return
        
        self.stdout.write(f'Found {len(orphaned_users)} orphaned users:')
        for profile in orphaned_users:
            self.stdout.write(f'  - {profile.user.username} (ID: {profile.user.id})')
        
        # Get available processing units
        available_units = ProcessingUnit.objects.all()
        if not available_units.exists():
            self.stdout.write(self.style.ERROR('No processing units found in database!'))
            self.stdout.write('Please create at least one processing unit first.')
            return
        
        self.stdout.write(f'\nAvailable processing units:')
        for unit in available_units:
            self.stdout.write(f'  [{unit.id}] {unit.name} - {unit.location or "No location"}')
        
        # Determine target unit
        target_unit = None
        if target_unit_id:
            try:
                target_unit = ProcessingUnit.objects.get(id=target_unit_id)
                self.stdout.write(f'\nUsing specified unit: {target_unit.name}')
            except ProcessingUnit.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Processing unit with ID {target_unit_id} not found!'))
                return
        
        # Process each orphaned user
        fixed_count = 0
        skipped_count = 0
        
        for profile in orphaned_users:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Processing user: {profile.user.username}')
            
            # Determine which unit to assign
            if interactive and not target_unit:
                self.stdout.write('Available units:')
                for unit in available_units:
                    self.stdout.write(f'  [{unit.id}] {unit.name}')
                
                unit_id = input(f'Enter unit ID for {profile.user.username} (or "skip"): ').strip()
                if unit_id.lower() == 'skip':
                    self.stdout.write(self.style.WARNING(f'Skipped {profile.user.username}'))
                    skipped_count += 1
                    continue
                
                try:
                    assign_unit = ProcessingUnit.objects.get(id=int(unit_id))
                except (ValueError, ProcessingUnit.DoesNotExist):
                    self.stdout.write(self.style.ERROR(f'Invalid unit ID. Skipping {profile.user.username}'))
                    skipped_count += 1
                    continue
            elif target_unit:
                assign_unit = target_unit
            else:
                # Auto-assign to first unit if not interactive
                assign_unit = available_units.first()
                self.stdout.write(f'Auto-assigning to: {assign_unit.name}')
            
            # Create membership
            if not dry_run:
                try:
                    membership, created = ProcessingUnitUser.objects.get_or_create(
                        user=profile.user,
                        processing_unit=assign_unit,
                        defaults={
                            'role': 'worker',  # Default to worker for orphaned users
                            'permissions': 'write',  # Default to write permissions
                            'is_active': True,
                            'is_suspended': False,
                            'invited_by': profile.user,
                            'invited_at': timezone.now(),
                            'joined_at': timezone.now(),
                        }
                    )
                    
                    # Update profile if needed
                    if not profile.processing_unit:
                        profile.processing_unit = assign_unit
                        profile.save()
                    
                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Created membership for {profile.user.username} '
                                f'in {assign_unit.name} (role: worker, permissions: write)'
                            )
                        )
                        fixed_count += 1
                    else:
                        self.stdout.write(
                            f'  Membership already exists for {profile.user.username}'
                        )
                        fixed_count += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error: {str(e)}')
                    )
                    skipped_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'[DRY RUN] Would create membership for {profile.user.username} '
                        f'in {assign_unit.name} (role: worker, permissions: write)'
                    )
                )
                fixed_count += 1
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total orphaned users found: {len(orphaned_users)}')
        self.stdout.write(self.style.SUCCESS(f'Users fixed: {fixed_count}'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'Users skipped: {skipped_count}'))
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('DRY RUN COMPLETE - No changes were made'))
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write('\n' + self.style.SUCCESS('FIX COMPLETE'))
            self.stdout.write('\nRecommendation: Review the assigned roles and permissions')
            self.stdout.write('and adjust them as needed for each user.')
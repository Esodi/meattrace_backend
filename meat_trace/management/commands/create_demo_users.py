from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from meat_trace.models import (
    ProcessingUnit,
    ProcessingUnitUser,
    Shop,
    ShopUser,
    UserProfile,
)


DEFAULT_PASSWORD = 'ReviewDemo123!'


class Command(BaseCommand):
    help = 'Create reviewer-ready demo users for each primary role'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default=DEFAULT_PASSWORD,
            help='Password to set for every reviewer account',
        )
        parser.add_argument(
            '--skip-password-reset',
            action='store_true',
            help='Do not reset passwords for accounts that already exist',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password']
        reset_existing_passwords = not options['skip_password_reset']

        if not password:
            raise CommandError('Password cannot be empty')

        processing_unit = self._upsert_processing_unit()
        shop = self._upsert_shop()
        accounts = self._account_definitions(processing_unit, shop)

        created_count = 0
        updated_count = 0

        self.stdout.write('Creating Play Store reviewer demo users...')

        for account in accounts:
            user, created = User.objects.get_or_create(
                username=account['username'],
                defaults={'email': account['email']},
            )

            user.email = account['email']
            user.first_name = account['first_name']
            user.last_name = account['last_name']
            user.is_active = True
            user.is_staff = account.get('is_staff', False)
            user.is_superuser = account.get('is_superuser', False)

            if created or reset_existing_passwords:
                user.set_password(password)

            user.save()

            self._upsert_profile(user, account)
            self._upsert_membership(user, account, processing_unit, shop)

            if created:
                created_count += 1
                status = 'created'
            else:
                updated_count += 1
                status = 'updated'

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {status}: {account['username']} ({account['role']})"
                )
            )

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Demo reviewer users ready: {created_count} created, {updated_count} updated'
            )
        )
        self._print_credentials(accounts, password)

    def _upsert_processing_unit(self):
        unit, _ = ProcessingUnit.objects.update_or_create(
            name='Play Store Review Processing Unit',
            defaults={
                'description': 'Demo processing unit for app review',
                'location': 'Dar es Salaam, Tanzania',
                'latitude': Decimal('-6.816475'),
                'longitude': Decimal('39.289436'),
                'contact_email': 'playstore_processor@example.com',
                'contact_phone': '+255711000001',
                'license_number': 'PSR-PU-001',
                'is_active': True,
            },
        )
        return unit

    def _upsert_shop(self):
        shop, _ = Shop.objects.update_or_create(
            name='Play Store Review Shop',
            defaults={
                'description': 'Demo shop for app review',
                'location': 'Dar es Salaam, Tanzania',
                'latitude': Decimal('-6.792354'),
                'longitude': Decimal('39.208328'),
                'contact_email': 'playstore_shop@example.com',
                'contact_phone': '+255722000001',
                'business_license': 'PSR-SH-001',
                'tax_id': 'PSR-TIN-001',
                'is_active': True,
            },
        )
        return shop

    def _account_definitions(self, processing_unit, shop):
        return [
            {
                'role': 'Admin',
                'username': 'playstore_admin',
                'email': 'playstore_admin@example.com',
                'first_name': 'Play Store',
                'last_name': 'Admin',
                'phone': '+255700000001',
                'address': 'Dar es Salaam, Tanzania',
                'latitude': Decimal('-6.792354'),
                'longitude': Decimal('39.208328'),
                'is_staff': True,
            },
            {
                'role': 'Abbatoir',
                'username': 'playstore_abbatoir',
                'email': 'playstore_abbatoir@example.com',
                'first_name': 'Play Store',
                'last_name': 'Abbatoir',
                'phone': '+255700000002',
                'address': 'Mbezi Beach, Dar es Salaam, Tanzania',
                'latitude': Decimal('-6.684069'),
                'longitude': Decimal('39.218365'),
                'preferred_species': ['cow', 'goat', 'sheep'],
            },
            {
                'role': 'Processor',
                'username': 'playstore_processor',
                'email': 'playstore_processor@example.com',
                'first_name': 'Play Store',
                'last_name': 'Processor',
                'phone': '+255700000003',
                'address': processing_unit.location,
                'latitude': processing_unit.latitude,
                'longitude': processing_unit.longitude,
                'processing_unit': processing_unit,
            },
            {
                'role': 'ShopOwner',
                'username': 'playstore_shop',
                'email': 'playstore_shop@example.com',
                'first_name': 'Play Store',
                'last_name': 'Shop',
                'phone': '+255700000004',
                'address': shop.location,
                'latitude': shop.latitude,
                'longitude': shop.longitude,
                'shop': shop,
            },
        ]

    def _upsert_profile(self, user, account):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = account['role']
        profile.processing_unit = account.get('processing_unit')
        profile.shop = account.get('shop')
        profile.is_profile_complete = True
        profile.profile_completion_step = 4
        profile.phone = account['phone']
        profile.address = account['address'] or ''
        profile.bio = 'Demo account for Play Store app review.'
        profile.latitude = account.get('latitude')
        profile.longitude = account.get('longitude')
        profile.preferred_species = account.get('preferred_species', [])
        profile.is_email_verified = True
        profile.is_phone_verified = True
        profile.notification_preferences = {
            'email': True,
            'push': True,
            'sms': False,
        }
        profile.save()

    def _upsert_membership(self, user, account, processing_unit, shop):
        now = timezone.now()

        if account['role'] == 'Processor':
            ProcessingUnitUser.objects.update_or_create(
                user=user,
                processing_unit=processing_unit,
                defaults={
                    'role': 'owner',
                    'permissions': 'admin',
                    'granular_permissions': {},
                    'invited_by': user,
                    'invited_at': now,
                    'joined_at': now,
                    'is_active': True,
                    'is_suspended': False,
                    'suspension_reason': '',
                    'suspension_date': None,
                    'last_active': now,
                },
            )

        if account['role'] == 'ShopOwner':
            ShopUser.objects.update_or_create(
                user=user,
                shop=shop,
                defaults={
                    'role': 'owner',
                    'permissions': 'admin',
                    'invited_by': user,
                    'invited_at': now,
                    'joined_at': now,
                    'is_active': True,
                },
            )

    def _print_credentials(self, accounts, password):
        rows = [
            (account['role'], account['username'], account['email'], password)
            for account in accounts
        ]
        headers = ('Role', 'Username', 'Email', 'Password')
        widths = [
            max(len(str(row[index])) for row in rows + [headers])
            for index in range(len(headers))
        ]

        def format_row(row):
            return '  '.join(
                str(value).ljust(widths[index])
                for index, value in enumerate(row)
            )

        self.stdout.write('')
        self.stdout.write('Play Store review credentials:')
        self.stdout.write(format_row(headers))
        self.stdout.write(format_row(tuple('-' * width for width in widths)))
        for row in rows:
            self.stdout.write(format_row(row))

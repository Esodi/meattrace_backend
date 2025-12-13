"""
Management command to geocode existing entities that have location text but no coordinates.

Usage:
    python manage.py geocode_existing_locations
    python manage.py geocode_existing_locations --dry-run
    python manage.py geocode_existing_locations --limit 10
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
import time


class Command(BaseCommand):
    help = 'Geocode existing ProcessingUnits, Shops, and UserProfiles that have location text but no coordinates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be geocoded without actually doing it',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of entities to geocode',
        )

    def handle(self, *args, **options):
        from meat_trace.models import ProcessingUnit, Shop, UserProfile
        from meat_trace.utils.geocoding_service import GeocodingService

        dry_run = options['dry_run']
        limit = options['limit']
        
        total_geocoded = 0
        total_failed = 0

        # Geocode Processing Units
        self.stdout.write(self.style.NOTICE('\n=== Processing Units ==='))
        pu_queryset = ProcessingUnit.objects.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True),
            location__isnull=False
        ).exclude(location='')
        
        if limit:
            pu_queryset = pu_queryset[:limit]
        
        for pu in pu_queryset:
            self.stdout.write(f'  Processing: {pu.name} - "{pu.location}"')
            
            if dry_run:
                coords = GeocodingService.geocode(pu.location)
                if coords:
                    self.stdout.write(self.style.SUCCESS(f'    Would set: {coords}'))
                else:
                    self.stdout.write(self.style.WARNING(f'    No coordinates found'))
            else:
                coords = GeocodingService.geocode(pu.location)
                if coords:
                    pu.latitude = coords['latitude']
                    pu.longitude = coords['longitude']
                    # Use update to avoid triggering save() geocoding logic again
                    ProcessingUnit.objects.filter(pk=pu.pk).update(
                        latitude=coords['latitude'],
                        longitude=coords['longitude']
                    )
                    self.stdout.write(self.style.SUCCESS(f'    Set: {coords}'))
                    total_geocoded += 1
                else:
                    self.stdout.write(self.style.WARNING(f'    Failed to geocode'))
                    total_failed += 1
            
            # Rate limiting: Nominatim requires 1 request per second
            time.sleep(1.1)

        # Geocode Shops
        self.stdout.write(self.style.NOTICE('\n=== Shops ==='))
        shop_queryset = Shop.objects.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True),
            location__isnull=False
        ).exclude(location='')
        
        if limit:
            shop_queryset = shop_queryset[:limit]
        
        for shop in shop_queryset:
            self.stdout.write(f'  Processing: {shop.name} - "{shop.location}"')
            
            if dry_run:
                coords = GeocodingService.geocode(shop.location)
                if coords:
                    self.stdout.write(self.style.SUCCESS(f'    Would set: {coords}'))
                else:
                    self.stdout.write(self.style.WARNING(f'    No coordinates found'))
            else:
                coords = GeocodingService.geocode(shop.location)
                if coords:
                    Shop.objects.filter(pk=shop.pk).update(
                        latitude=coords['latitude'],
                        longitude=coords['longitude']
                    )
                    self.stdout.write(self.style.SUCCESS(f'    Set: {coords}'))
                    total_geocoded += 1
                else:
                    self.stdout.write(self.style.WARNING(f'    Failed to geocode'))
                    total_failed += 1
            
            time.sleep(1.1)

        # Geocode Farmers (UserProfiles)
        self.stdout.write(self.style.NOTICE('\n=== Farmers ==='))
        farmer_queryset = UserProfile.objects.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True),
            role='Farmer',
            address__isnull=False
        ).exclude(address='').select_related('user')
        
        if limit:
            farmer_queryset = farmer_queryset[:limit]
        
        for farmer in farmer_queryset:
            self.stdout.write(f'  Processing: {farmer.user.username} - "{farmer.address}"')
            
            if dry_run:
                coords = GeocodingService.geocode(farmer.address)
                if coords:
                    self.stdout.write(self.style.SUCCESS(f'    Would set: {coords}'))
                else:
                    self.stdout.write(self.style.WARNING(f'    No coordinates found'))
            else:
                coords = GeocodingService.geocode(farmer.address)
                if coords:
                    UserProfile.objects.filter(pk=farmer.pk).update(
                        latitude=coords['latitude'],
                        longitude=coords['longitude']
                    )
                    self.stdout.write(self.style.SUCCESS(f'    Set: {coords}'))
                    total_geocoded += 1
                else:
                    self.stdout.write(self.style.WARNING(f'    Failed to geocode'))
                    total_failed += 1
            
            time.sleep(1.1)

        # Summary
        self.stdout.write(self.style.NOTICE('\n=== Summary ==='))
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully geocoded: {total_geocoded}'))
            self.stdout.write(self.style.WARNING(f'Failed to geocode: {total_failed}'))

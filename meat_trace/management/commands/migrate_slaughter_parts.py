from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from meat_trace.models import SlaughterPart
import uuid
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate existing SlaughterPart records: generate unique part_id values and update old part types to new anatomical names'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        # Get all SlaughterPart records that need migration
        parts_without_id = SlaughterPart.objects.filter(part_id='')
        parts_with_other = SlaughterPart.objects.filter(part_type='other')

        total_parts = SlaughterPart.objects.count()
        parts_needing_id = parts_without_id.count()
        parts_needing_type_update = parts_with_other.count()

        self.stdout.write(
            self.style.SUCCESS(
                f'Found {total_parts} total SlaughterPart records\n'
                f'Records needing part_id generation: {parts_needing_id}\n'
                f'Records with "other" part_type to update: {parts_needing_type_update}'
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )

        # Process part_id generation
        if parts_needing_id > 0:
            self.stdout.write(f'\nProcessing part_id generation...')
            self._generate_part_ids(parts_without_id, batch_size, dry_run)

        # Process part type updates
        if parts_needing_type_update > 0:
            self.stdout.write(f'\nProcessing part type updates...')
            self._update_part_types(parts_with_other, batch_size, dry_run)

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS('\nMigration completed successfully!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nDry run completed - no changes made')
            )

    def _generate_part_ids(self, queryset, batch_size, dry_run):
        """Generate unique part_id values for records that don't have them"""
        total_processed = 0
        total_updated = 0

        # Process in batches to avoid memory issues
        for i in range(0, queryset.count(), batch_size):
            batch = queryset[i:i + batch_size]
            batch_ids = []

            for part in batch:
                new_part_id = self._generate_unique_part_id()
                total_processed += 1

                if dry_run:
                    self.stdout.write(
                        f'  Would update part {part.id} ({part.part_type}): "" -> "{new_part_id}"'
                    )
                else:
                    part.part_id = new_part_id
                    batch_ids.append(part)

                # Show progress
                if total_processed % 100 == 0:
                    self.stdout.write(f'  Processed {total_processed} records...')

            # Bulk update if not dry run
            if not dry_run and batch_ids:
                SlaughterPart.objects.bulk_update(batch_ids, ['part_id'])
                total_updated += len(batch_ids)

        if not dry_run:
            self.stdout.write(f'  Generated part_id for {total_updated} records')
        else:
            self.stdout.write(f'  Would generate part_id for {total_processed} records')

    def _update_part_types(self, queryset, batch_size, dry_run):
        """Update 'other' part types to appropriate anatomical names based on description"""
        total_processed = 0
        total_updated = 0

        # Process in batches
        for i in range(0, queryset.count(), batch_size):
            batch = queryset[i:i + batch_size]
            batch_updates = []

            for part in batch:
                new_part_type = self._map_other_to_anatomical(part)
                total_processed += 1

                if new_part_type != 'other':
                    if dry_run:
                        self.stdout.write(
                            f'  Would update part {part.id}: "other" -> "{new_part_type}" (description: "{part.description or "None"}")'
                        )
                    else:
                        part.part_type = new_part_type
                        batch_updates.append(part)
                        total_updated += 1
                else:
                    if dry_run:
                        self.stdout.write(
                            f'  Would keep part {part.id} as "other" (no mapping found, description: "{part.description or "None"}")'
                        )

                # Show progress
                if total_processed % 100 == 0:
                    self.stdout.write(f'  Processed {total_processed} records...')

            # Bulk update if not dry run
            if not dry_run and batch_updates:
                SlaughterPart.objects.bulk_update(batch_updates, ['part_type'])

        if not dry_run:
            self.stdout.write(f'  Updated part_type for {total_updated} records')
        else:
            self.stdout.write(f'  Would update part_type for {total_updated} records')

    def _generate_unique_part_id(self):
        """Generate a unique part ID using UUID"""
        return f"PART_{uuid.uuid4().hex[:12].upper()}"

    def _map_other_to_anatomical(self, part):
        """
        Map 'other' part type to appropriate anatomical name based on description.
        Returns the new part_type or 'other' if no mapping found.
        """
        description = (part.description or '').lower().strip()

        # Mapping rules based on common descriptions
        mapping_rules = {
            'torso': [
                'torso', 'body', 'carcass body', 'main body', 'central body',
                'trunk', 'body cavity', 'chest cavity', 'abdominal cavity',
                'ribs', 'rib cage', 'spine', 'vertebral column', 'backbone'
            ],
            'head': [
                'head', 'skull', 'brain', 'tongue', 'ears', 'eyes'
            ],
            'feet': [
                'feet', 'hooves', 'hoof', 'foot', 'paws'
            ],
            'internal_organs': [
                'organs', 'liver', 'kidney', 'kidneys', 'heart', 'lungs',
                'intestines', 'stomach', 'spleen', 'pancreas', 'glands'
            ],
            'front_legs': [
                'front legs', 'forelegs', 'shoulder', 'front quarters',
                'fore quarters', 'brisket', 'neck', 'throat'
            ],
            'hind_legs': [
                'hind legs', 'back legs', 'rear legs', 'hind quarters',
                'rear quarters', 'rump', 'flank', 'loin'
            ]
        }

        for anatomical_type, keywords in mapping_rules.items():
            if any(keyword in description for keyword in keywords):
                return anatomical_type

        # Default fallback - if description suggests it's meat/tissue but no specific match
        if any(word in description for word in ['meat', 'flesh', 'tissue', 'muscle', 'cut']):
            return 'torso'  # Default to torso for generic meat descriptions

        # If no mapping found, keep as 'other'
        return 'other'
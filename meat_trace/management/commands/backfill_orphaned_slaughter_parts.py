from django.core.management.base import BaseCommand
from django.db import transaction

from meat_trace.models import Animal


class Command(BaseCommand):
    help = (
        "Backfill SlaughterPart rows that were left behind (still "
        "transferred_to=None / received_by=None) when their parent Animal "
        "was transferred/received before transfer_animals/receive_animals "
        "started cascading those fields onto slaughter_parts. Without this, "
        "a 'whole carcass' animal's auto-created SlaughterPart (which holds "
        "the actual remaining_weight once the animal's own remaining_weight "
        "is zeroed at slaughter time) stays invisible to the processing "
        "unit even though the animal itself shows as received."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        transferred_animals = Animal.objects.filter(
            transferred_to__isnull=False
        ).prefetch_related('slaughter_parts')

        received_animals = Animal.objects.filter(
            received_by__isnull=False
        ).prefetch_related('slaughter_parts')

        transfer_fixed = 0
        receive_fixed = 0

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        with transaction.atomic():
            for animal in transferred_animals:
                orphaned = [p for p in animal.slaughter_parts.all() if p.transferred_to_id is None]
                if not orphaned:
                    continue
                for part in orphaned:
                    if dry_run:
                        self.stdout.write(
                            f'  Would set part {part.id} ({part.part_type}) of animal '
                            f'{animal.animal_id}: transferred_to -> {animal.transferred_to_id}'
                        )
                    else:
                        part.transferred_to_id = animal.transferred_to_id
                        part.transferred_at = animal.transferred_at
                        part.save(update_fields=['transferred_to', 'transferred_at'])
                    transfer_fixed += 1

            for animal in received_animals:
                orphaned = [
                    p for p in animal.slaughter_parts.all()
                    if p.transferred_to_id is not None and p.received_by_id is None
                ]
                if not orphaned:
                    continue
                for part in orphaned:
                    if dry_run:
                        self.stdout.write(
                            f'  Would set part {part.id} ({part.part_type}) of animal '
                            f'{animal.animal_id}: received_by -> {animal.received_by_id}'
                        )
                    else:
                        part.received_by_id = animal.received_by_id
                        part.received_at = animal.received_at
                        part.save(update_fields=['received_by', 'received_at'])
                    receive_fixed += 1

            if dry_run:
                # Roll back - dry run must not persist anything even though
                # nothing was actually written above.
                transaction.set_rollback(True)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nDry run complete - would backfill transferred_to on '
                    f'{transfer_fixed} part(s) and received_by on {receive_fixed} part(s).'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nBackfilled transferred_to on {transfer_fixed} part(s) '
                    f'and received_by on {receive_fixed} part(s).'
                )
            )

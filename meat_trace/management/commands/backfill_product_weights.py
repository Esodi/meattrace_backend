from django.core.management.base import BaseCommand
from django.db.models import F, Q

from meat_trace.models import Product


class Command(BaseCommand):
    help = (
        'Recover product weight for legacy rows where weight is 0 but the real '
        'figure survives in quantity/weight_received.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Product.save() keeps quantity in sync with weight, but rows created
        # before that logic existed kept the weight column at its 0 default while
        # the real figure went into quantity (and weight_received). Those show up
        # on the public traceability page as "0 kg", so recover them.
        #
        # Deliberately narrow: only rows where the two independent columns agree,
        # so this recovers a value that is already recorded twice rather than
        # inferring one. A product that genuinely weighs 0 has no quantity either
        # and is left alone.
        candidates = Product.objects.filter(
            Q(weight__isnull=True) | Q(weight=0),
            quantity__gt=0,
            quantity=F('weight_received'),
        )

        total = candidates.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nothing to do — no legacy zero-weight products.'))
            return

        self.stdout.write(f'{"[dry-run] " if dry_run else ""}Recovering weight for {total} product(s)...')
        for p in candidates[:10]:
            self.stdout.write(f'  {p.id}: weight {p.weight} -> {p.quantity} {p.weight_unit}')
        if total > 10:
            self.stdout.write(f'  ... and {total - 10} more')

        skipped = Product.objects.filter(
            Q(weight__isnull=True) | Q(weight=0)
        ).exclude(pk__in=candidates.values('pk')).count()

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[dry-run] {total} would be updated, {skipped} left alone.'))
            return

        # F() expression: one UPDATE, and quantity already equals the new weight
        # so the save() sync has nothing to correct.
        updated = candidates.update(weight=F('quantity'))
        self.stdout.write(self.style.SUCCESS(
            f'Done: {updated} product(s) updated, {skipped} left alone '
            f'(no corroborating quantity/weight_received).'
        ))

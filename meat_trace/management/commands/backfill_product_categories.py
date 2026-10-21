import re
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from meat_trace.models import Product, ProductCategory


def derive_name(product_name):
    """Derive a category name from a product name.

    Products are named "<category> from <source part>" ("TROTTERS from Feet",
    "sausage from Whole Carcass"), so everything before " from " is the
    category. Names without that suffix are used as-is.
    """
    base = re.split(r'\s+from\s+', (product_name or '').strip(), flags=re.I)[0]
    return re.sub(r'\s+', ' ', base).strip()


def match_key(name):
    """Key for deciding whether two names mean the same category.

    Case-insensitive, and tolerant of a trailing plural, so 'Neck' matches the
    existing 'Necks' and 'Sausages' matches 'sausage' instead of creating a
    near-duplicate alongside it. Deliberately does NOT do fuzzy/typo matching:
    collapsing 'Lion chops' into 'Loin chops' is a guess, and guessing wrong
    silently merges two real categories. Those are reported for review instead.
    """
    n = name.strip().lower()
    n = re.sub(r'[^a-z0-9 ]+', '', n)
    # Strip a single trailing 's' only. Stripping 'es' too would turn
    # 'sausages' into 'sausag' while 'sausage' stays put, so the plural and
    # singular would land on different keys and fail to merge.
    n = re.sub(r's$', '', n)
    return re.sub(r'\s+', ' ', n).strip()


class Command(BaseCommand):
    help = (
        'Assign a category to every uncategorised product, deriving category '
        'names from the product names and creating the categories that do not '
        'exist yet.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without writing anything')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        existing = {}
        for cat in ProductCategory.objects.all():
            existing.setdefault(match_key(cat.name), cat)

        products = list(Product.objects.filter(category__isnull=True))
        if not products:
            self.stdout.write(self.style.SUCCESS('Nothing to do — every product has a category.'))
            return

        # Group products by what their name resolves to.
        by_key = defaultdict(list)
        casings = defaultdict(Counter)
        for p in products:
            name = derive_name(p.name)
            if not name:
                continue
            key = match_key(name)
            if not key:
                continue
            by_key[key].append(p)
            casings[key][name] += 1

        reuse = {k: v for k, v in by_key.items() if k in existing}
        create = {k: v for k, v in by_key.items() if k not in existing}

        self.stdout.write(
            f'{"[dry-run] " if dry_run else ""}{len(products)} uncategorised product(s): '
            f'{sum(len(v) for v in reuse.values())} match an existing category, '
            f'{sum(len(v) for v in create.values())} need {len(create)} new categories.'
        )

        if reuse:
            self.stdout.write('\n  Matched to existing categories:')
            for k, ps in sorted(reuse.items(), key=lambda x: -len(x[1])):
                self.stdout.write(f'    {len(ps):>3}  {casings[k].most_common(1)[0][0]!r} -> {existing[k].name!r}')

        if create:
            self.stdout.write('\n  New categories to create:')
            for k, ps in sorted(create.items(), key=lambda x: -len(x[1])):
                self.stdout.write(f'    {len(ps):>3}  {casings[k].most_common(1)[0][0]!r}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[dry-run] Nothing written.'))
            self._report_suspects(create, existing, casings)
            return

        created_count = assigned = 0
        with transaction.atomic():
            for key, ps in create.items():
                # Most common spelling in the data becomes the canonical name.
                canonical = casings[key].most_common(1)[0][0]
                cat = ProductCategory.objects.create(
                    name=canonical,
                    description='Created from existing product names during category backfill.',
                    processing_unit=None,  # global, matching the pre-existing categories
                )
                existing[key] = cat
                created_count += 1

            for key, ps in by_key.items():
                cat = existing.get(key)
                if not cat:
                    continue
                assigned += Product.objects.filter(
                    pk__in=[p.pk for p in ps]
                ).update(category=cat)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {created_count} categories created, {assigned} products assigned.'
        ))
        self._report_suspects(create, existing, casings)

    def _report_suspects(self, create, existing, casings):
        """Flag newly created names that look like misspellings of another category.

        These are left as separate categories on purpose — merging them is a
        judgement call about the business's taxonomy, not something to do
        silently during a backfill.
        """
        import difflib

        pool = {c.name for c in ProductCategory.objects.all()}
        suspects = []
        for key in create:
            name = casings[key].most_common(1)[0][0]
            others = [n for n in pool if n != name]
            close = difflib.get_close_matches(name, others, n=1, cutoff=0.8)
            if close:
                suspects.append((name, close[0]))

        if suspects:
            self.stdout.write(self.style.WARNING(
                '\nPossible duplicates/misspellings — review and merge in the app if you agree:'
            ))
            for a, b in sorted(suspects):
                self.stdout.write(f'    {a!r}  ~  {b!r}')

"""Backfill Product.category for products saved before the app sent it.

The create-product / opening-stock screens used to drop the selected
category on submit, so `category_id` stayed NULL and the public trace page
(/trace/<batch_number>/) rendered "—" for Category. Product names from
those screens embed the category that was picked ("Fillet from goat",
"FRESH MEAT from Head"), so the category can be recovered from the name.

Matching is per processing unit where possible, then falls back to a
globally unique category name. Products whose name matches nothing — or
matches ambiguously — are left alone and reported.

Usage:
    python scripts/backfill_product_categories.py            # dry run
    python scripts/backfill_product_categories.py --apply    # write
"""
import os
import sys

import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Product, ProductCategory  # noqa: E402


def _norm(value):
    return ' '.join(value.lower().split())


def resolve(product, by_unit, by_name):
    """Return the category whose name prefixes the product name, or None."""
    name = _norm(product.name)
    candidates = by_unit.get(product.processing_unit_id, {})

    # Longest name first so "Pork Chops" wins over a hypothetical "Pork".
    for cat_name, category in sorted(candidates.items(), key=lambda kv: -len(kv[0])):
        if name == cat_name or name.startswith(cat_name + ' from '):
            return category

    for cat_name, categories in sorted(by_name.items(), key=lambda kv: -len(kv[0])):
        if name == cat_name or name.startswith(cat_name + ' from '):
            if len(categories) == 1:
                return categories[0]
            return None  # ambiguous across processing units
    return None


def main(apply_changes):
    by_unit = {}
    by_name = {}
    for category in ProductCategory.objects.all():
        key = _norm(category.name)
        by_unit.setdefault(category.processing_unit_id, {})[key] = category
        by_name.setdefault(key, []).append(category)

    pending = Product.objects.filter(category__isnull=True).order_by('id')
    matched, unmatched = [], []

    for product in pending:
        category = resolve(product, by_unit, by_name)
        (matched if category else unmatched).append((product, category))

    print(f"Products without a category: {pending.count()}")
    print(f"  resolvable from name: {len(matched)}")
    print(f"  left as-is:           {len(unmatched)}")

    for product, category in matched:
        print(f"  #{product.id} {product.batch_number!r} {product.name!r} -> {category.name}")

    if unmatched:
        print("\nNo match (will keep showing '—' until set by hand):")
        for product, _ in unmatched:
            print(f"  #{product.id} {product.batch_number!r} {product.name!r}")

    if not apply_changes:
        print("\nDry run — re-run with --apply to write these changes.")
        return

    for product, category in matched:
        product.category = category
    Product.objects.bulk_update([p for p, _ in matched], ['category'], batch_size=200)
    print(f"\nUpdated {len(matched)} products.")


if __name__ == '__main__':
    main('--apply' in sys.argv)

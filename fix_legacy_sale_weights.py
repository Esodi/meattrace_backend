"""
One-time script to fix product weights for legacy sales.
Recalculates Product.weight by subtracting all historical SaleItem weights.
"""
import os
import django
import sys
from decimal import Decimal

sys.path.append('/home/egao/Documents/MEAT/meattrace_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from django.db.models import Sum
from meat_trace.models import Product, SaleItem, Inventory

def fix_legacy_weights():
    # Get all products that have been sold
    products_with_sales = (
        SaleItem.objects
        .values('product_id')
        .annotate(total_sold=Sum('weight'))
        .filter(total_sold__gt=0)
    )

    print(f"Found {len(products_with_sales)} products with sales history.\n")

    fixed_count = 0
    for entry in products_with_sales:
        product_id = entry['product_id']
        total_sold = entry['total_sold'] or Decimal('0')

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            print(f"  ⚠️  Product {product_id} not found, skipping.")
            continue

        # Get the original weight from receipts (what was received into the shop)
        from meat_trace.models import Receipt
        total_received = (
            Receipt.objects
            .filter(product=product)
            .aggregate(total=Sum('received_weight'))
        )['total'] or Decimal('0')

        # If no receipts, use the current product weight + total sold as the original
        if total_received > 0:
            original_weight = total_received
        else:
            # Assume current weight hasn't been adjusted yet, so original = current weight
            original_weight = product.weight

        new_weight = max(Decimal('0'), original_weight - total_sold)

        if product.weight != new_weight:
            old_weight = product.weight
            product.weight = new_weight
            if product.remaining_weight is not None:
                product.remaining_weight = new_weight
            product.save(update_fields=['weight', 'remaining_weight'])
            print(f"  ✅ Product '{product.name}' (ID: {product.id}): {old_weight} → {new_weight} kg (sold: {total_sold} kg)")
            fixed_count += 1

            # Also fix associated inventory records
            inventories = Inventory.objects.filter(product=product)
            for inv in inventories:
                inv.weight = new_weight
                inv.quantity = new_weight
                inv.save()
                print(f"     └─ Inventory (Shop: {inv.shop.name}): updated to {new_weight} kg")
        else:
            print(f"  ── Product '{product.name}' (ID: {product.id}): already correct at {product.weight} kg")

    print(f"\nDone. Fixed {fixed_count} product(s).")

if __name__ == "__main__":
    fix_legacy_weights()

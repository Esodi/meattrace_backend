"""
Test script to verify that product quantity is reduced when a sale is created
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Product, Sale, SaleItem, Shop, User
from decimal import Decimal

print("=" * 80)
print("TEST: Product Quantity Reduction on Sale")
print("=" * 80)

# Get a product with quantity
product = Product.objects.filter(quantity__gt=0).first()
if not product:
    print("❌ No products with quantity found!")
    exit()

print(f"\n📦 Product: {product.name} (ID: {product.id})")
print(f"   Batch: {product.batch_number}")
print(f"   Current Quantity: {product.quantity}")

# Store original quantity
original_quantity = product.quantity
quantity_to_sell = Decimal('2.00')

print(f"\n💰 Creating sale for {quantity_to_sell} units...")

# Get shop and user
shop = Shop.objects.first()
user = User.objects.first()

if not shop or not user:
    print("❌ No shop or user found!")
    exit()

# Create sale using the same method as the API
sale = Sale.objects.create(
    shop=shop,
    sold_by=user,
    customer_name="Test Customer",
    customer_phone="1234567890",
    total_amount=Decimal('100.00'),
    payment_method='cash'
)

print(f"✅ Sale created (ID: {sale.id})")

# Create sale item (this should trigger quantity reduction)
sale_item = SaleItem.objects.create(
    sale=sale,
    product=product,
    quantity=quantity_to_sell,
    unit_price=Decimal('50.00'),
    subtotal=Decimal('100.00')
)

print(f"✅ Sale item created (ID: {sale_item.id})")

# Refresh product from database
product.refresh_from_db()

print(f"\n📊 Results:")
print(f"   Original Quantity: {original_quantity}")
print(f"   Quantity Sold: {quantity_to_sell}")
print(f"   New Quantity: {product.quantity}")
print(f"   Expected Quantity: {original_quantity - quantity_to_sell}")

if product.quantity == original_quantity - quantity_to_sell:
    print(f"\n✅ SUCCESS! Product quantity was correctly reduced!")
else:
    print(f"\n❌ FAILED! Product quantity was NOT reduced correctly!")
    print(f"   Difference: {product.quantity - (original_quantity - quantity_to_sell)}")

# Clean up test data
print(f"\n🧹 Cleaning up test data...")
sale.delete()  # This will also delete the sale_item due to CASCADE
print(f"✅ Test data cleaned up")

print("\n" + "=" * 80)

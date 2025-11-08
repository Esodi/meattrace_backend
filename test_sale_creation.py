import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Sale, Product, UserProfile, Shop
from decimal import Decimal

# Get a shop user and a product
try:
    shop = Shop.objects.first()
    if not shop:
        print("No shop found!")
        exit()
    
    print(f"Shop: {shop.name}")
    
    # Get a product from this shop
    product = Product.objects.filter(received_by_shop=shop).first()
    if not product:
        # Try any product
        product = Product.objects.first()
        if not product:
            print("No product found at all!")
            exit()
        print(f"Using any available product since shop has no products")
    
    print(f"Product: {product.name}, ID: {product.id}")
    
    # Try to create a sale
    sale_data = {
        'shop': shop,
        'product': product,
        'quantity_sold': Decimal('1.0'),
        'sale_price': Decimal('100.0'),
        'customer_name': 'Test Customer',
        'customer_phone': '1234567890'
    }
    
    print(f"\nAttempting to create sale with data: {sale_data}")
    
    sale = Sale.objects.create(**sale_data)
    print(f"\nSale created successfully! ID: {sale.id}")
    print(f"Sale details: {sale}")
    
except Exception as e:
    print(f"\nError creating sale: {e}")
    import traceback
    traceback.print_exc()

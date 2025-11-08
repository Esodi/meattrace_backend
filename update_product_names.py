#!/usr/bin/env python
"""
Script to update product names from generic "meat" to specific category names
based on the animal species (e.g., "meat" -> "fresh meat from cow").
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import Product

def update_product_names():
    """Update product names to include species information"""

    # Get all products
    products = Product.objects.all()
    print(f"Total products found: {products.count()}")
    print()

    # Track changes
    updated_products = []
    skipped_products = []

    for product in products:
        original_name = product.name
        name_lower = original_name.lower()

        # Skip if already contains species information
        if any(species in name_lower for species in ['sheep', 'chicken', 'cow', 'pig', 'goat']):
            skipped_products.append((product.id, original_name, "Already contains species"))
            continue

        # Skip if not a meat product
        if product.product_type != 'meat':
            skipped_products.append((product.id, original_name, f"Not a meat product (type: {product.product_type})"))
            continue

        # Get animal species
        if not product.animal:
            skipped_products.append((product.id, original_name, "No associated animal"))
            continue

        species = product.animal.species

        # Create new name based on existing pattern
        # Extract descriptors like "fresh", "ground", etc.
        descriptors = []
        if 'fresh' in name_lower:
            descriptors.append('fresh')
        if 'ground' in name_lower:
            descriptors.append('ground')
        if 'organic' in name_lower:
            descriptors.append('organic')

        # Build new name
        descriptor_str = ' '.join(descriptors).title() if descriptors else 'Fresh'
        new_name = f"{descriptor_str} Meat from {species}"

        # Update the product
        product.name = new_name
        product.save()

        updated_products.append((product.id, original_name, new_name))
        print(f"Updated ID {product.id}: '{original_name}' -> '{new_name}'")

    print()
    print(f"Summary:")
    print(f"  Updated: {len(updated_products)} products")
    print(f"  Skipped: {len(skipped_products)} products")

    if updated_products:
        print("\nUpdated products:")
        for pid, old, new in updated_products:
            print(f"  ID {pid}: '{old}' -> '{new}'")

    if skipped_products:
        print("\nSkipped products:")
        for pid, name, reason in skipped_products:
            print(f"  ID {pid}: '{name}' - {reason}")

if __name__ == '__main__':
    update_product_names()
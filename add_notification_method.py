#!/usr/bin/env python3
"""
Script to add notify_product_rejected method to notification_service.py
"""

import sys

def add_method():
    file_path = 'm:/MEAT/meattrace_backend/meat_trace/utils/notification_service.py'
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the line with notify_part_rejected
    insert_index = None
    for i, line in enumerate(lines):
        if 'def notify_part_rejected' in line:
            # Find the end of this method (next @staticmethod or end of class)
            for j in range(i + 1, len(lines)):
                if lines[j].strip().startswith('@staticmethod'):
                    insert_index = j
                    break
            break
    
    if insert_index is None:
        print("Could not find insertion point")
        sys.exit(1)
    
    # The new method to insert
    new_method = '''    @staticmethod
    def notify_product_rejected(processor_user, product, shop, quantity_rejected, rejection_reason):
        """Send notification to processor when shop rejects a product"""
        return NotificationService.create_notification(
            processor_user,
            'product_rejected',
            f'Product {product.name} rejected by shop',
            f'Shop {shop.name} rejected {quantity_rejected} units of {product.name} (Batch: {product.batch_number}). Reason: {rejection_reason}',
            priority='high',
            action_type='view',
            data={
                'product_id': product.id,
                'product_name': product.name,
                'batch_number': product.batch_number,
                'shop_id': shop.id,
                'shop_name': shop.name,
                'quantity_rejected': float(quantity_rejected),
                'rejection_reason': rejection_reason
            }
        )

'''
    
    # Insert the new method
    lines.insert(insert_index, new_method)
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"Successfully added notify_product_rejected method at line {insert_index}")

if __name__ == '__main__':
    add_method()

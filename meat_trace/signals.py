# Signals for meat_trace app
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Order, Inventory
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Order)
def track_order_status_change(sender, instance, **kwargs):
    """Track if order status is changing to 'confirmed'"""
    if instance.pk:
        try:
            old_order = Order.objects.get(pk=instance.pk)
            instance._old_status = old_order.status
        except Order.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

# Order inventory updates are handled in the OrderSerializer.create method for new orders
# This signal handles inventory updates when existing orders are updated to confirmed status

@receiver(post_save, sender=Order)
def update_inventory_on_order_status_change(sender, instance, created, **kwargs):
    """Update inventory when existing order status changes to 'confirmed'"""
    if created:
        return  # New orders are handled in serializer

    old_status = getattr(instance, '_old_status', None)

    # Only update inventory if status changed to 'confirmed' from something else
    if old_status != 'confirmed' and instance.status == 'confirmed':
        logger.info(f"Order {instance.id} status changed to confirmed, updating inventory")

        for order_item in instance.items.all():
            try:
                # Get or create inventory for this shop and product
                inventory, created = Inventory.objects.get_or_create(
                    shop=instance.shop,
                    product=order_item.product,
                    defaults={'quantity': 0}
                )

                # Subtract ordered quantity from inventory
                old_quantity = inventory.quantity
                inventory.quantity = max(0, inventory.quantity - order_item.quantity)
                inventory.last_updated = timezone.now()
                inventory.save()

                logger.info(f"Updated inventory for product {order_item.product.name}: {old_quantity} -> {inventory.quantity}")

            except Exception as e:
                logger.error(f"Failed to update inventory for order item {order_item.id}: {str(e)}")
                # Continue with other items even if one fails
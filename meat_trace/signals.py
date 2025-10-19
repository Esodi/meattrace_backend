# Signals for meat_trace app
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Order, Inventory, ProcessingUnitUser, ShopUser, UserAuditLog
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


@receiver(pre_save, sender=ProcessingUnitUser)
def track_processing_unit_user_changes(sender, instance, **kwargs):
    """Track changes to ProcessingUnitUser for audit logging"""
    if instance.pk:
        try:
            old_instance = ProcessingUnitUser.objects.get(pk=instance.pk)
            instance._old_values = {
                'role': old_instance.role,
                'permissions': old_instance.permissions,
                'granular_permissions': old_instance.granular_permissions,
                'is_active': old_instance.is_active,
                'is_suspended': old_instance.is_suspended,
                'suspension_reason': old_instance.suspension_reason,
            }
        except ProcessingUnitUser.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}


@receiver(post_save, sender=ProcessingUnitUser)
def audit_processing_unit_user_changes(sender, instance, created, **kwargs):
    """Create audit log entries for ProcessingUnitUser changes"""
    try:
        old_values = getattr(instance, '_old_values', {})

        if created:
            # User was invited to processing unit
            UserAuditLog.objects.create(
                performed_by=instance.invited_by,
                affected_user=instance.user,
                processing_unit=instance.processing_unit,
                action='user_invited',
                description=f"User {instance.user.username} was invited to processing unit {instance.processing_unit.name} with role {instance.role}",
                new_values={
                    'role': instance.role,
                    'permissions': instance.permissions,
                    'granular_permissions': instance.granular_permissions,
                }
            )
        else:
            # Check for changes
            changes = []
            new_values = {}

            if old_values.get('role') != instance.role:
                changes.append(f"role: {old_values.get('role')} -> {instance.role}")
                new_values['role'] = instance.role

            if old_values.get('permissions') != instance.permissions:
                changes.append(f"permissions: {old_values.get('permissions')} -> {instance.permissions}")
                new_values['permissions'] = instance.permissions

            if old_values.get('granular_permissions') != instance.granular_permissions:
                changes.append("granular permissions changed")
                new_values['granular_permissions'] = instance.granular_permissions

            if old_values.get('is_suspended') != instance.is_suspended:
                action = 'user_suspended' if instance.is_suspended else 'user_unsuspended'
                reason = f" ({instance.suspension_reason})" if instance.suspension_reason else ""
                UserAuditLog.objects.create(
                    performed_by=None,  # System action or need to track who performed it
                    affected_user=instance.user,
                    processing_unit=instance.processing_unit,
                    action=action,
                    description=f"User {instance.user.username} was {'suspended' if instance.is_suspended else 'unsuspended'} in processing unit {instance.processing_unit.name}{reason}",
                    old_values={'is_suspended': old_values.get('is_suspended')},
                    new_values={'is_suspended': instance.is_suspended, 'suspension_reason': instance.suspension_reason}
                )

            if changes:
                UserAuditLog.objects.create(
                    performed_by=None,  # Need to track who performed the change
                    affected_user=instance.user,
                    processing_unit=instance.processing_unit,
                    action='permissions_changed' if 'permissions' in str(changes) else 'role_changed',
                    description=f"User {instance.user.username} changes in processing unit {instance.processing_unit.name}: {', '.join(changes)}",
                    old_values=old_values,
                    new_values=new_values
                )

    except Exception as e:
        logger.error(f"Failed to create audit log for ProcessingUnitUser change: {str(e)}")


@receiver(pre_save, sender=ShopUser)
def track_shop_user_changes(sender, instance, **kwargs):
    """Track changes to ShopUser for audit logging"""
    if instance.pk:
        try:
            old_instance = ShopUser.objects.get(pk=instance.pk)
            instance._old_values = {
                'role': old_instance.role,
                'permissions': old_instance.permissions,
                'is_active': old_instance.is_active,
            }
        except ShopUser.DoesNotExist:
            instance._old_values = {}
    else:
        instance._old_values = {}


@receiver(post_save, sender=ShopUser)
def audit_shop_user_changes(sender, instance, created, **kwargs):
    """Create audit log entries for ShopUser changes"""
    try:
        old_values = getattr(instance, '_old_values', {})

        if created:
            # User was invited to shop
            UserAuditLog.objects.create(
                performed_by=instance.invited_by,
                affected_user=instance.user,
                shop=instance.shop,
                action='user_invited',
                description=f"User {instance.user.username} was invited to shop {instance.shop.name} with role {instance.role}",
                new_values={
                    'role': instance.role,
                    'permissions': instance.permissions,
                }
            )
        else:
            # Check for changes
            changes = []
            new_values = {}

            if old_values.get('role') != instance.role:
                changes.append(f"role: {old_values.get('role')} -> {instance.role}")
                new_values['role'] = instance.role

            if old_values.get('permissions') != instance.permissions:
                changes.append(f"permissions: {old_values.get('permissions')} -> {instance.permissions}")
                new_values['permissions'] = instance.permissions

            if changes:
                UserAuditLog.objects.create(
                    performed_by=None,  # Need to track who performed the change
                    affected_user=instance.user,
                    shop=instance.shop,
                    action='permissions_changed' if 'permissions' in str(changes) else 'role_changed',
                    description=f"User {instance.user.username} changes in shop {instance.shop.name}: {', '.join(changes)}",
                    old_values=old_values,
                    new_values=new_values
                )

    except Exception as e:
        logger.error(f"Failed to create audit log for ShopUser change: {str(e)}")
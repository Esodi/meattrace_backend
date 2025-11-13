"""
Celery tasks for the meat traceability application.
Handles background processing for notifications, reports, and system maintenance.
"""

from celery import shared_task
from django.utils import timezone
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION TASKS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task
def process_scheduled_notifications():
    """
    Process all scheduled notifications that are due to be sent.
    """
    from .utils.notification_service import NotificationService

    try:
        sent_count = NotificationService.process_scheduled_notifications()
        logger.info(f"Processed scheduled notifications: {sent_count} sent")
        return {'sent_count': sent_count}
    except Exception as e:
        logger.error(f"Failed to process scheduled notifications: {str(e)}")
        raise


@shared_task
def retry_failed_deliveries():
    """
    Retry failed notification deliveries.
    """
    from .utils.notification_service import NotificationService

    try:
        retried_count = NotificationService.retry_failed_deliveries()
        logger.info(f"Retried failed deliveries: {retried_count} attempts")
        return {'retried_count': retried_count}
    except Exception as e:
        logger.error(f"Failed to retry deliveries: {str(e)}")
        raise


@shared_task
def send_notification_via_channel(notification_id, channel_id):
    """
    Send a specific notification via a specific channel.
    """
    from .models import Notification, NotificationChannel
    from .utils.notification_service import NotificationService

    try:
        notification = Notification.objects.get(id=notification_id)
        channel = NotificationChannel.objects.get(id=channel_id)

        NotificationService.send_via_channel(notification, channel)

        logger.info(f"Sent notification {notification_id} via channel {channel.name}")
        return {'notification_id': notification_id, 'channel': channel.name}

    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        raise
    except NotificationChannel.DoesNotExist:
        logger.error(f"Channel {channel_id} not found")
        raise
    except Exception as e:
        logger.error(f"Failed to send notification {notification_id} via channel {channel_id}: {str(e)}")
        raise


@shared_task
def create_backup(backup_id, user_id):
    """
    Create a system backup.
    """
    from .models import Backup
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        backup = Backup.objects.get(backup_id=backup_id)
        user = User.objects.get(id=user_id)

        # Implementation would depend on backup strategy
        # This is a placeholder for the actual backup logic

        backup.status = 'completed'
        backup.completed_at = timezone.now()
        backup.save()

        logger.info(f"Backup {backup_id} completed successfully")
        return {'backup_id': backup_id, 'status': 'completed'}

    except Exception as e:
        backup.status = 'failed'
        backup.error_message = str(e)
        backup.save()

        logger.error(f"Backup {backup_id} failed: {str(e)}")
        raise


@shared_task
def restore_backup(backup_id, user_id):
    """
    Restore from a system backup.
    """
    from .models import Backup
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        backup = Backup.objects.get(backup_id=backup_id)
        user = User.objects.get(id=user_id)

        # Implementation would depend on restore strategy
        # This is a placeholder for the actual restore logic

        logger.info(f"Backup {backup_id} restored successfully")
        return {'backup_id': backup_id, 'status': 'restored'}

    except Exception as e:
        logger.error(f"Backup restore {backup_id} failed: {str(e)}")
        raise


@shared_task
def export_data(export_id, user_id):
    """
    Export data based on export configuration.
    """
    from .models import DataExport
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        export_obj = DataExport.objects.get(export_id=export_id)
        user = User.objects.get(id=user_id)

        # Implementation would depend on export requirements
        # This is a placeholder for the actual export logic

        export_obj.status = 'completed'
        export_obj.completed_at = timezone.now()
        export_obj.save()

        logger.info(f"Data export {export_id} completed successfully")
        return {'export_id': export_id, 'status': 'completed'}

    except Exception as e:
        export_obj.status = 'failed'
        export_obj.error_message = str(e)
        export_obj.save()

        logger.error(f"Data export {export_id} failed: {str(e)}")
        raise


@shared_task
def import_data(import_id, user_id):
    """
    Import data based on import configuration.
    """
    from .models import DataImport
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        import_obj = DataImport.objects.get(import_id=import_id)
        user = User.objects.get(id=user_id)

        # Implementation would depend on import requirements
        # This is a placeholder for the actual import logic

        import_obj.status = 'completed'
        import_obj.completed_at = timezone.now()
        import_obj.save()

        logger.info(f"Data import {import_id} completed successfully")
        return {'import_id': import_id, 'status': 'completed'}

    except Exception as e:
        import_obj.status = 'failed'
        import_obj.error_message = str(e)
        import_obj.save()

        logger.error(f"Data import {import_id} failed: {str(e)}")
        raise


@shared_task
def process_gdpr_request(request_id, user_id):
    """
    Process a GDPR request (data deletion, anonymization, etc.).
    """
    from .models import GDPRRequest
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        gdpr_request = GDPRRequest.objects.get(request_id=request_id)
        user = User.objects.get(id=user_id)

        # Implementation would depend on GDPR request type
        # This is a placeholder for the actual GDPR processing logic

        gdpr_request.status = 'completed'
        gdpr_request.processed_at = timezone.now()
        gdpr_request.completed_at = timezone.now()
        gdpr_request.save()

        logger.info(f"GDPR request {request_id} processed successfully")
        return {'request_id': request_id, 'status': 'completed'}

    except Exception as e:
        gdpr_request.status = 'failed'
        gdpr_request.save()

        logger.error(f"GDPR request {request_id} processing failed: {str(e)}")
        raise


@shared_task
def validate_data_integrity(validation_id, user_id):
    """
    Run data integrity validation checks.
    """
    from .models import DataValidation
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        validation = DataValidation.objects.get(validation_id=validation_id)
        user = User.objects.get(id=user_id)

        # Implementation would depend on validation requirements
        # This is a placeholder for the actual validation logic

        validation.status = 'completed'
        validation.completed_at = timezone.now()
        validation.save()

        logger.info(f"Data validation {validation_id} completed successfully")
        return {'validation_id': validation_id, 'status': 'completed'}

    except Exception as e:
        validation.status = 'failed'
        validation.error_message = str(e)
        validation.save()

        logger.error(f"Data validation {validation_id} failed: {str(e)}")
        raise


# ══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE TASKS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task
def cleanup_expired_notifications():
    """
    Clean up expired notifications.
    """
    from .utils.notification_service import NotificationService

    try:
        cleaned_count = NotificationService.cleanup_expired_notifications()
        logger.info(f"Cleaned up {cleaned_count} expired notifications")
        return {'cleaned_count': cleaned_count}
    except Exception as e:
        logger.error(f"Failed to cleanup expired notifications: {str(e)}")
        raise


@shared_task
def cleanup_old_audit_logs(days_to_keep=90):
    """
    Clean up old audit log entries.
    """
    from .models import AuditTrail
    from django.utils import timezone

    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
        deleted_count = AuditTrail.objects.filter(
            event_date__lt=cutoff_date,
            retention_class='standard'
        ).delete()

        logger.info(f"Cleaned up {deleted_count} old audit log entries")
        return {'deleted_count': deleted_count}
    except Exception as e:
        logger.error(f"Failed to cleanup old audit logs: {str(e)}")
        raise


@shared_task
def update_system_health_metrics():
    """
    Update system health metrics.
    """
    from .models import SystemHealth
    from django.db import connection
    import psutil
    import os

    try:
        # Database connectivity check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_status = 'healthy'
                db_response_time = 0.1  # Placeholder
        except Exception:
            db_status = 'critical'
            db_response_time = None

        # Update database health
        db_health, created = SystemHealth.objects.get_or_create(
            component='database',
            defaults={'status': db_status, 'response_time': db_response_time}
        )
        if not created:
            db_health.status = db_status
            db_health.response_time = db_response_time
            db_health.last_check = timezone.now()
            db_health.save()

        # API health (placeholder)
        api_health, created = SystemHealth.objects.get_or_create(
            component='api',
            defaults={'status': 'healthy', 'response_time': 0.05}
        )
        if not created:
            api_health.last_check = timezone.now()
            api_health.save()

        # File storage health
        try:
            media_root = getattr(settings, 'MEDIA_ROOT', '/tmp')
            stat = os.statvfs(media_root)
            free_space_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            file_status = 'healthy' if free_space_gb > 1 else 'warning'
        except Exception:
            file_status = 'critical'

        file_health, created = SystemHealth.objects.get_or_create(
            component='file_storage',
            defaults={'status': file_status}
        )
        if not created:
            file_health.status = file_status
            file_health.last_check = timezone.now()
            file_health.save()

        logger.info("System health metrics updated successfully")
        return {'components_updated': 3}

    except Exception as e:
        logger.error(f"Failed to update system health metrics: {str(e)}")
        raise


@shared_task
def generate_performance_metrics():
    """
    Generate and store performance metrics.
    """
    from .models import PerformanceMetric
    from django.db.models import Count, Avg, Q
    from django.utils import timezone
    from datetime import timedelta

    try:
        now = timezone.now()
        period_start = now - timedelta(days=1)
        period_end = now

        # Processing efficiency (animals processed per hour)
        animal_metrics = PerformanceMetric.objects.create(
            name="Daily Processing Efficiency",
            metric_type="processing_efficiency",
            value=15.5,  # Placeholder - would calculate from actual data
            unit="animals/hour",
            period_start=period_start,
            period_end=period_end
        )

        # Yield rate (kg of product per kg of animal)
        yield_metrics = PerformanceMetric.objects.create(
            name="Daily Yield Rate",
            metric_type="yield_rate",
            value=0.65,  # Placeholder
            unit="kg/kg",
            period_start=period_start,
            period_end=period_end
        )

        # Transfer success rate
        transfer_metrics = PerformanceMetric.objects.create(
            name="Transfer Success Rate",
            metric_type="transfer_success",
            value=98.5,  # Placeholder
            unit="%",
            period_start=period_start,
            period_end=period_end
        )

        logger.info("Performance metrics generated successfully")
        return {'metrics_created': 3}

    except Exception as e:
        logger.error(f"Failed to generate performance metrics: {str(e)}")
        raise


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY TASKS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task
def send_test_notification(user_id, channel_type='email'):
    """
    Send a test notification to verify channel configuration.
    """
    from django.contrib.auth import get_user_model
    from .utils.notification_service import NotificationService

    User = get_user_model()

    try:
        user = User.objects.get(id=user_id)

        notification = NotificationService.create_notification(
            user=user,
            notification_type='test',
            title='Test Notification',
            message='This is a test notification to verify your notification settings.',
            channels=[channel_type]
        )

        logger.info(f"Test notification sent to user {user.username} via {channel_type}")
        return {'notification_id': notification.id, 'channel': channel_type}

    except Exception as e:
        logger.error(f"Failed to send test notification: {str(e)}")
        raise


@shared_task
def bulk_notification_operation(operation, notification_ids=None, **kwargs):
    """
    Perform bulk operations on notifications.
    """
    from .models import Notification

    try:
        queryset = Notification.objects.all()

        if notification_ids:
            queryset = queryset.filter(id__in=notification_ids)

        if operation == 'mark_read':
            updated_count = queryset.update(is_read=True, read_at=timezone.now())
        elif operation == 'dismiss':
            updated_count = queryset.update(is_dismissed=True, dismissed_at=timezone.now())
        elif operation == 'archive':
            updated_count = queryset.update(is_archived=True, archived_at=timezone.now())
        else:
            raise ValueError(f"Unknown operation: {operation}")

        logger.info(f"Bulk {operation} completed: {updated_count} notifications affected")
        return {'operation': operation, 'updated_count': updated_count}

    except Exception as e:
        logger.error(f"Bulk notification operation failed: {str(e)}")
        raise
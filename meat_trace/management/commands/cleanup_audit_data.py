from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from meat_trace.models import AuditTrail, ComplianceStatus
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old audit data based on retention policies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--retention-days',
            type=int,
            default=365,
            help='Number of days to retain audit data (default: 365)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without confirmation',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        retention_days = options['retention_days']
        force = options['force']

        cutoff_date = timezone.now() - timedelta(days=retention_days)

        self.stdout.write(
            self.style.WARNING(
                f"{'DRY RUN: ' if dry_run else ''}Cleaning up audit data older than {retention_days} days ({cutoff_date.date()})"
            )
        )

        # Count records to be deleted
        audit_trail_count = AuditTrail.objects.filter(
            timestamp__lt=cutoff_date,
            retention_class='standard'  # Don't delete critical audit data
        ).count()

        # Compliance status cleanup (keep compliance history but archive old records)
        compliance_count = ComplianceStatus.objects.filter(
            created_at__lt=cutoff_date,
            compliance_level__in=['compliant', 'warning']  # Only archive good compliance records
        ).count()

        total_count = audit_trail_count + compliance_count

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No old audit data found to clean up.')
            )
            return

        self.stdout.write(f"Found {total_count} records to clean up:")
        self.stdout.write(f"  - AuditTrail records: {audit_trail_count}")
        self.stdout.write(f"  - ComplianceStatus records: {compliance_count}")

        # Confirm deletion unless forced or dry run
        if not dry_run and not force:
            confirm = input(f"\nDelete {total_count} records? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                self.stdout.write('Operation cancelled.')
                return

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Dry run complete. Would delete {total_count} records.")
            )
            return

        # Perform cleanup
        try:
            with transaction.atomic():
                # Delete old audit trail records
                deleted_audit, _ = AuditTrail.objects.filter(
                    timestamp__lt=cutoff_date,
                    retention_class='standard'
                ).delete()

                # Archive old compliance records (mark as inactive)
                archived_compliance = ComplianceStatus.objects.filter(
                    created_at__lt=cutoff_date,
                    compliance_level__in=['compliant', 'warning']
                ).update(is_active=False)

                total_deleted = deleted_audit + archived_compliance

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully cleaned up {total_deleted} records:"
                    )
                )
                self.stdout.write(f"  - Deleted {deleted_audit} audit trail records")
                self.stdout.write(f"  - Archived {archived_compliance} compliance records")

                # Log the cleanup operation
                AuditTrail.objects.create(
                    event_date=timezone.now().date(),
                    action_type='system',
                    entity_type='system',
                    action_description=f'Cleanup operation: deleted {deleted_audit} audit records, archived {archived_compliance} compliance records',
                    retention_class='permanent',  # Keep cleanup logs permanently
                    metadata={
                        'cleanup_operation': True,
                        'retention_days': retention_days,
                        'records_deleted': deleted_audit,
                        'records_archived': archived_compliance,
                        'cutoff_date': cutoff_date.isoformat()
                    }
                )

        except Exception as e:
            raise CommandError(f"Error during cleanup: {e}")

        self.stdout.write(
            self.style.SUCCESS('Cleanup completed successfully.')
        )
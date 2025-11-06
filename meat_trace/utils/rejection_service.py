"""
RejectionService handles processing rejections and sending notifications.
Provides centralized logic for rejection workflows including notifications and audit logging.
"""

from django.utils import timezone
from django.db import transaction
from ..models import Animal, SlaughterPart, Notification, UserAuditLog, Activity


class RejectionService:
    """Service class for handling rejection processing and notifications"""

    @staticmethod
    def process_animal_rejection(animal, rejection_data, rejected_by, processing_unit):
        """
        Process rejection of an animal with full workflow including notifications.

        Args:
            animal: Animal instance being rejected
            rejection_data: dict with 'category', 'specific_reason', 'notes'
            rejected_by: User who performed the rejection
            processing_unit: ProcessingUnit that rejected the animal
        """
        with transaction.atomic():
            # Update animal rejection fields
            animal.rejection_status = 'rejected'
            animal.rejection_reason_category = rejection_data['category']
            animal.rejection_reason_specific = rejection_data['specific_reason']
            animal.rejection_notes = rejection_data.get('notes', '')
            animal.rejected_by = rejected_by
            animal.rejected_at = timezone.now()
            animal.save()

            # Create rejection reason record
            from ..models import RejectionReason
            RejectionReason.objects.create(
                animal=animal,
                category=rejection_data['category'],
                specific_reason=rejection_data['specific_reason'],
                notes=rejection_data.get('notes', ''),
                rejected_by=rejected_by,
                processing_unit=processing_unit,
            )

            # Send notification to farmer
            RejectionService._send_rejection_notification(
                'animal',
                animal.farmer,
                animal,
                rejection_data['category'],
                rejection_data['specific_reason']
            )

            # Create activity log
            Activity.objects.create(
                user=rejected_by,
                activity_type='transfer',
                title=f'Animal {animal.animal_id} rejected',
                description=f'Rejected animal {animal.animal_id}: {rejection_data["category"]} - {rejection_data["specific_reason"]}',
                entity_id=str(animal.id),
                entity_type='animal',
                metadata={
                    'animal_id': animal.animal_id,
                    'rejection_category': rejection_data['category'],
                    'rejection_reason': rejection_data['specific_reason']
                }
            )

            # Create audit log
            UserAuditLog.objects.create(
                performed_by=rejected_by,
                affected_user=animal.farmer,
                processing_unit=processing_unit,
                action='animal_rejected',
                description=f'Animal {animal.animal_id} rejected by processing unit {processing_unit.name}',
                old_values={'received_by': None},
                new_values={
                    'rejection_status': 'rejected',
                    'rejection_reason_category': rejection_data['category'],
                    'rejection_reason_specific': rejection_data['specific_reason'],
                    'rejected_at': animal.rejected_at.isoformat()
                },
                metadata={
                    'rejection_category': rejection_data['category'],
                    'rejection_reason': rejection_data['specific_reason'],
                    'rejection_notes': rejection_data.get('notes', '')
                }
            )

    @staticmethod
    def process_part_rejection(part, rejection_data, rejected_by, processing_unit):
        """
        Process rejection of a slaughter part with full workflow including notifications.

        Args:
            part: SlaughterPart instance being rejected
            rejection_data: dict with 'category', 'specific_reason', 'notes'
            rejected_by: User who performed the rejection
            processing_unit: ProcessingUnit that rejected the part
        """
        with transaction.atomic():
            # Update part rejection fields
            part.rejection_status = 'rejected'
            part.rejection_reason_category = rejection_data['category']
            part.rejection_reason_specific = rejection_data['specific_reason']
            part.rejection_notes = rejection_data.get('notes', '')
            part.rejected_by = rejected_by
            part.rejected_at = timezone.now()
            part.save()

            # Create rejection reason record
            from ..models import RejectionReason
            RejectionReason.objects.create(
                slaughter_part=part,
                category=rejection_data['category'],
                specific_reason=rejection_data['specific_reason'],
                notes=rejection_data.get('notes', ''),
                rejected_by=rejected_by,
                processing_unit=processing_unit,
            )

            # Send notification to farmer
            RejectionService._send_rejection_notification(
                'part',
                part.animal.farmer,
                part,
                rejection_data['category'],
                rejection_data['specific_reason']
            )

            # Create activity log
            Activity.objects.create(
                user=rejected_by,
                activity_type='transfer',
                title=f'Part {part.part_type} of animal {part.animal.animal_id} rejected',
                description=f'Rejected part {part.part_type}: {rejection_data["category"]} - {rejection_data["specific_reason"]}',
                entity_id=str(part.id),
                entity_type='slaughter_part',
                metadata={
                    'animal_id': part.animal.animal_id,
                    'part_id': part.id,
                    'part_type': part.part_type,
                    'rejection_category': rejection_data['category'],
                    'rejection_reason': rejection_data['specific_reason']
                }
            )

            # Create audit log
            UserAuditLog.objects.create(
                performed_by=rejected_by,
                affected_user=part.animal.farmer,
                processing_unit=processing_unit,
                action='part_rejected',
                description=f'Part {part.part_type} of animal {part.animal.animal_id} rejected by processing unit {processing_unit.name}',
                old_values={'received_by': None},
                new_values={
                    'rejection_status': 'rejected',
                    'rejection_reason_category': rejection_data['category'],
                    'rejection_reason_specific': rejection_data['specific_reason'],
                    'rejected_at': part.rejected_at.isoformat()
                },
                metadata={
                    'rejection_category': rejection_data['category'],
                    'rejection_reason': rejection_data['specific_reason'],
                    'rejection_notes': rejection_data.get('notes', '')
                }
            )

    @staticmethod
    def process_appeal_resolution(item_type, item_id, resolution, resolved_by, resolution_notes=''):
        """
        Process appeal resolution (approve/deny) with notifications.

        Args:
            item_type: 'animal' or 'part'
            item_id: ID of the item being appealed
            resolution: 'approved' or 'denied'
            resolved_by: User resolving the appeal
            resolution_notes: Optional notes about the resolution
        """
        with transaction.atomic():
            if item_type == 'animal':
                animal = Animal.objects.get(id=item_id)
                if animal.appeal_status != 'pending':
                    raise ValueError('Appeal is not in pending status')

                animal.appeal_status = resolution
                animal.appeal_resolved_at = timezone.now()
                animal.save()

                # Send notification
                RejectionService._send_appeal_resolution_notification(
                    'animal', animal.farmer, animal, resolution, resolution_notes
                )

                # Create activity
                Activity.objects.create(
                    user=resolved_by,
                    activity_type='other',
                    title=f'Appeal {resolution} for animal {animal.animal_id}',
                    description=f'Appeal for rejected animal {animal.animal_id} was {resolution}',
                    entity_id=str(animal.id),
                    entity_type='animal',
                    metadata={
                        'animal_id': animal.animal_id,
                        'appeal_resolution': resolution,
                        'resolution_notes': resolution_notes
                    }
                )

            elif item_type == 'part':
                part = SlaughterPart.objects.get(id=item_id)
                if part.appeal_status != 'pending':
                    raise ValueError('Appeal is not in pending status')

                part.appeal_status = resolution
                part.appeal_resolved_at = timezone.now()
                part.save()

                # Send notification
                RejectionService._send_appeal_resolution_notification(
                    'part', part.animal.farmer, part, resolution, resolution_notes
                )

                # Create activity
                Activity.objects.create(
                    user=resolved_by,
                    activity_type='other',
                    title=f'Appeal {resolution} for part {part.part_type} of animal {part.animal.animal_id}',
                    description=f'Appeal for rejected part {part.part_type} was {resolution}',
                    entity_id=str(part.id),
                    entity_type='slaughter_part',
                    metadata={
                        'animal_id': part.animal.animal_id,
                        'part_id': part.id,
                        'part_type': part.part_type,
                        'appeal_resolution': resolution,
                        'resolution_notes': resolution_notes
                    }
                )

    @staticmethod
    def _send_rejection_notification(item_type, farmer, item, category, specific_reason):
        """Send rejection notification to farmer"""
        if item_type == 'animal':
            title = f'Animal {item.animal_id} Rejected'
            message = f'Your animal {item.animal_id} was rejected during processing. Reason: {category} - {specific_reason}'
            notification_type = 'animal_rejected'
        else:
            title = f'Animal Part Rejected'
            message = f'A part ({item.part_type}) of your animal {item.animal.animal_id} was rejected during processing. Reason: {category} - {specific_reason}'
            notification_type = 'part_rejected'

        Notification.objects.create(
            user=farmer,
            notification_type=notification_type,
            title=title,
            message=message,
            data={
                'item_type': item_type,
                'item_id': item.id,
                'category': category,
                'specific_reason': specific_reason,
                'animal_id': item.animal_id if item_type == 'part' else item.animal_id
            }
        )

    @staticmethod
    def _send_appeal_resolution_notification(item_type, farmer, item, resolution, resolution_notes):
        """Send appeal resolution notification to farmer"""
        if item_type == 'animal':
            title = f'Appeal {resolution.title()} for Animal {item.animal_id}'
            message = f'Your appeal for animal {item.animal_id} has been {resolution}.'
            notification_type = 'appeal_approved' if resolution == 'approved' else 'appeal_denied'
        else:
            title = f'Appeal {resolution.title()} for Animal Part'
            message = f'Your appeal for part {item.part_type} of animal {item.animal.animal_id} has been {resolution}.'
            notification_type = 'appeal_approved' if resolution == 'approved' else 'appeal_denied'

        if resolution_notes:
            message += f' Notes: {resolution_notes}'

        Notification.objects.create(
            user=farmer,
            notification_type=notification_type,
            title=title,
            message=message,
            data={
                'item_type': item_type,
                'item_id': item.id,
                'resolution': resolution,
                'resolution_notes': resolution_notes,
                'animal_id': item.animal_id if item_type == 'part' else item.animal_id
            }
        )
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import viewsets, status as status_module
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from django.db import models
from django.db import transaction

from .models import Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage, ProductTimelineEvent, Inventory, Order, OrderItem, CarcassMeasurement, SlaughterPart, ProcessingUnit, ProcessingUnitUser, Shop, ShopUser, UserAuditLog, JoinRequest, Notification, Activity, SystemAlert, PerformanceMetric, ComplianceAudit, Certification, SystemHealth, SecurityLog, TransferRequest, BackupSchedule, Sale, SaleItem, RejectionReason
from .farmer_dashboard_serializer import FarmerDashboardSerializer
from .serializers import AnimalSerializer, ProductSerializer, OrderSerializer, ShopSerializer, SlaughterPartSerializer, ActivitySerializer, ProcessingUnitSerializer, JoinRequestSerializer, ProductCategorySerializer, CarcassMeasurementSerializer, SaleSerializer, SaleItemSerializer, NotificationSerializer, UserProfileSerializer
from .utils.rejection_service import RejectionService


class AnimalViewSet(viewsets.ModelViewSet):
    """ViewSet for managing animals with comprehensive CRUD operations and filtering"""
    serializer_class = AnimalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return animals for the current user with optional filtering.
        Supports filtering by species, slaughtered status, search, and ordering.
        
        Filtering logic:
        - Farmers: see their own animals
        - Processors: see animals transferred to ANY processing unit they belong to
        - Admins: see all animals
        """
        user = self.request.user
        queryset = Animal.objects.all().select_related('farmer', 'transferred_to', 'received_by')

        # Farmers see their own animals
        if hasattr(user, 'profile') and user.profile.role == 'farmer':
            queryset = queryset.filter(farmer=user)

        # ProcessingUnit users see animals transferred to ANY processing unit they belong to
        elif hasattr(user, 'profile') and user.profile.role == 'processing_unit':
            # Get all processing units the user is a member of
            from .models import ProcessingUnitUser
            user_processing_units = ProcessingUnitUser.objects.filter(
                user=user,
                is_active=True,
                is_suspended=False
            ).values_list('processing_unit_id', flat=True)
            
            if user_processing_units:
                # Show animals transferred to any of the user's processing units (whole or parts)
                # Exclude rejected animals
                queryset = queryset.filter(
                    Q(transferred_to_id__in=user_processing_units) |
                    Q(slaughter_parts__transferred_to_id__in=user_processing_units)
                ).exclude(
                    rejection_status='rejected'
                ).distinct()
            else:
                queryset = queryset.none()

        # Apply filters from query parameters
        species = self.request.query_params.get('species')
        if species:
            queryset = queryset.filter(species=species)

        slaughtered = self.request.query_params.get('slaughtered')
        if slaughtered is not None:
            slaughtered_bool = slaughtered.lower() == 'true'
            queryset = queryset.filter(slaughtered=slaughtered_bool)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(animal_id__icontains=search) |
                Q(animal_name__icontains=search) |
                Q(breed__icontains=search) |
                Q(notes__icontains=search)
            )

        ordering = self.request.query_params.get('ordering', '-created_at')
        if ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        """Set the farmer to the current user when creating an animal"""
        serializer.save(farmer=self.request.user)

    @action(detail=True, methods=['patch'], url_path='slaughter')
    def slaughter_animal(self, request, pk=None):
        """Slaughter an animal and create slaughter parts if carcass measurement exists"""
        animal = self.get_object()

        # Check if animal is already slaughtered
        if animal.slaughtered:
            return Response(
                {'error': 'Animal is already slaughtered'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        # Check if animal has been transferred (can't slaughter transferred animals)
        if animal.transferred_to is not None:
            return Response(
                {'error': 'Cannot slaughter transferred animal'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                # Mark animal as slaughtered
                animal.slaughtered = True
                animal.slaughtered_at = timezone.now()
                animal.save()

                # Check if carcass measurement exists and create slaughter parts
                if hasattr(animal, 'carcass_measurement'):
                    carcass_measurement = animal.carcass_measurement
                    # Slaughter parts creation logic would go here
                    # This is handled by the carcass measurement save method

                # Create activity log
                Activity.objects.create(
                    user=request.user,
                    activity_type='slaughter',
                    title=f'Animal {animal.animal_id} slaughtered',
                    description=f'Slaughtered {animal.species} with ID {animal.animal_id}',
                    entity_id=str(animal.id),
                    entity_type='animal',
                    metadata={
                        'animal_id': animal.animal_id,
                        'species': animal.species,
                        'weight': str(animal.live_weight) if animal.live_weight else None
                    }
                )

                serializer = self.get_serializer(animal)
                return Response(serializer.data)

        except Exception as e:
            return Response(
                {'error': f'Failed to slaughter animal: {str(e)}'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='transfer')
    def transfer_animals(self, request):
        """Transfer animals to a processing unit"""
        animal_ids = request.data.get('animal_ids', [])
        processing_unit_id = request.data.get('processing_unit_id')
        part_transfers = request.data.get('part_transfers', [])

        if not processing_unit_id:
            return Response(
                {'error': 'processing_unit_id is required'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        if not animal_ids and not part_transfers:
            return Response(
                {'error': 'Either animal_ids or part_transfers must be provided'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response(
                {'error': 'Processing unit not found'},
                status=status_module.HTTP_404_NOT_FOUND
            )

        transferred_animals = []
        transferred_parts = []

        try:
            with transaction.atomic():
                # Transfer whole animals
                if animal_ids:
                    animals = Animal.objects.filter(
                        id__in=animal_ids,
                        farmer=request.user,
                        transferred_to__isnull=True  # Not already transferred
                    )

                    for animal in animals:
                        animal.transferred_to = processing_unit
                        animal.transferred_at = timezone.now()
                        animal.save()
                        transferred_animals.append(animal)

                # Transfer parts
                if part_transfers:
                    animals_with_transferred_parts = set()  # Track animals whose parts are being transferred
                    
                    for part_transfer in part_transfers:
                        part_ids = part_transfer.get('part_ids', [])
                        parts = SlaughterPart.objects.filter(
                            id__in=part_ids,
                            animal__farmer=request.user,
                            transferred_to__isnull=True  # Not already transferred
                        )

                        for part in parts:
                            part.transferred_to = processing_unit
                            part.transferred_at = timezone.now()
                            part.save()
                            transferred_parts.append(part)
                            animals_with_transferred_parts.add(part.animal)
                    
                    # Check if all parts of any animal are now transferred
                    # If so, mark the parent animal as transferred
                    for animal in animals_with_transferred_parts:
                        all_parts = animal.slaughter_parts.all()
                        if all_parts.exists():
                            transferred_parts_count = sum(1 for p in all_parts if p.transferred_to is not None)
                            
                            # If all parts are transferred, mark the animal as transferred
                            if transferred_parts_count == len(all_parts):
                                animal.transferred_to = processing_unit
                                animal.transferred_at = timezone.now()
                                animal.save()
                                transferred_animals.append(animal)
                                
                                # Log for debugging
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(f"[TRANSFER] All {len(all_parts)} parts of animal {animal.animal_id} transferred - marking animal as transferred")

                # Create activity log
                if transferred_animals or transferred_parts:
                    # Count how many animals were transferred as complete split carcasses
                    split_carcass_count = sum(1 for a in transferred_animals if a.is_split_carcass)
                    whole_animal_count = len(transferred_animals) - split_carcass_count
                    
                    # Build descriptive title
                    title_parts = []
                    if whole_animal_count > 0:
                        title_parts.append(f'{whole_animal_count} whole animal{"s" if whole_animal_count != 1 else ""}')
                    if split_carcass_count > 0:
                        title_parts.append(f'{split_carcass_count} split carcass{"es" if split_carcass_count != 1 else ""}')
                    if len(transferred_parts) > 0 and split_carcass_count == 0:
                        # Only mention individual parts if they're not part of complete carcasses
                        title_parts.append(f'{len(transferred_parts)} individual part{"s" if len(transferred_parts) != 1 else ""}')
                    
                    title = f'Transferred {" and ".join(title_parts) if title_parts else "items"}'
                    
                    Activity.objects.create(
                        user=request.user,
                        activity_type='transfer',
                        title=title,
                        description=f'Transferred to {processing_unit.name}',
                        entity_type='transfer',
                        metadata={
                            'processing_unit': processing_unit.name,
                            'animal_count': len(transferred_animals),
                            'whole_animal_count': whole_animal_count,
                            'split_carcass_count': split_carcass_count,
                            'part_count': len(transferred_parts)
                        }
                    )

                # Build success message
                split_carcass_count = sum(1 for a in transferred_animals if a.is_split_carcass)
                whole_animal_count = len(transferred_animals) - split_carcass_count
                
                message_parts = []
                if whole_animal_count > 0:
                    message_parts.append(f'{whole_animal_count} whole animal{"s" if whole_animal_count != 1 else ""}')
                if split_carcass_count > 0:
                    message_parts.append(f'{split_carcass_count} complete split carcass{"es" if split_carcass_count != 1 else ""}')
                if len(transferred_parts) > 0:
                    message_parts.append(f'{len(transferred_parts)} part{"s" if len(transferred_parts) != 1 else ""}')
                
                success_message = f'Successfully transferred {" and ".join(message_parts) if message_parts else "items"} to {processing_unit.name}'
                
                return Response({
                    'message': success_message,
                    'transferred_animals': [a.id for a in transferred_animals],
                    'transferred_parts': [p.id for p in transferred_parts],
                    'whole_animal_count': whole_animal_count,
                    'split_carcass_count': split_carcass_count
                })

        except Exception as e:
            return Response(
                {'error': f'Failed to transfer: {str(e)}'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='transferred_animals')
    def transferred_animals(self, request):
        """Get animals transferred by the current user"""
        queryset = Animal.objects.filter(
            farmer=request.user,
            transferred_to__isnull=False
        ).order_by('-transferred_at')

        # Apply pagination if needed
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my_transferred_animals')
    def my_transferred_animals(self, request):
        """Alias for transferred_animals - used by Flutter app"""
        return self.transferred_animals(request)

    @action(detail=False, methods=['post'], url_path='receive_animals')
    def receive_animals(self, request):
        """Receive animals/parts at processing unit"""
        animal_ids = request.data.get('animal_ids', [])
        part_receives = request.data.get('part_receives', [])
        animal_rejections = request.data.get('animal_rejections', [])
        part_rejections = request.data.get('part_rejections', [])

        # Allow rejections even without receive IDs
        if not animal_ids and not part_receives and not animal_rejections and not part_rejections:
            return Response(
                {'error': 'Either animal_ids, part_receives, animal_rejections, or part_rejections must be provided'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        received_animals = []
        received_parts = []
        rejected_animals = []
        rejected_parts = []

        try:
            with transaction.atomic():
                # Receive whole animals
                if animal_ids:
                    animals = Animal.objects.filter(
                        id__in=animal_ids,
                        transferred_to__isnull=False,
                        received_by__isnull=True  # Not already received
                    )

                    for animal in animals:
                        animal.received_by = request.user
                        animal.received_at = timezone.now()
                        animal.save()
                        received_animals.append(animal)

                # Receive parts
                if part_receives:
                    for part_receive in part_receives:
                        part_ids = part_receive.get('part_ids', [])
                        parts = SlaughterPart.objects.filter(
                            id__in=part_ids,
                            transferred_to__isnull=False,
                            received_by__isnull=True  # Not already received
                        )

                        for part in parts:
                            part.received_by = request.user
                            part.received_at = timezone.now()
                            part.save()
                            received_parts.append(part)

                # Get processing unit for rejection service
                processing_unit = None
                try:
                    # Get the first active processing unit for this user
                    from .models import ProcessingUnitUser
                    pu_user = ProcessingUnitUser.objects.filter(
                        user=request.user,
                        is_active=True,
                        is_suspended=False
                    ).first()
                    if pu_user:
                        processing_unit = pu_user.processing_unit
                except Exception:
                    pass  # No processing unit found, continue with None

                # Process rejections using RejectionService
                if animal_rejections:
                    for rejection in animal_rejections:
                        animal_id = rejection.get('animal_id')
                        
                        # Build rejection data
                        if 'reason' in rejection:
                            # Old format - convert to new format
                            rejection_data = {
                                'category': 'other',
                                'specific_reason': rejection.get('reason', 'Not specified'),
                                'notes': ''
                            }
                        else:
                            # New structured format
                            rejection_data = {
                                'category': rejection.get('category', 'other'),
                                'specific_reason': rejection.get('specific_reason', 'Not specified'),
                                'notes': rejection.get('notes', '')
                            }

                        try:
                            animal = Animal.objects.get(id=animal_id)
                            # Use RejectionService to handle rejection with notifications
                            RejectionService.process_animal_rejection(
                                animal, rejection_data, request.user, processing_unit
                            )
                            rejected_animals.append(animal)
                        except Animal.DoesNotExist:
                            continue

                if part_rejections:
                    for rejection in part_rejections:
                        part_id = rejection.get('part_id')
                        
                        # Build rejection data
                        if 'reason' in rejection:
                            # Old format - convert to new format
                            rejection_data = {
                                'category': 'other',
                                'specific_reason': rejection.get('reason', 'Not specified'),
                                'notes': ''
                            }
                        else:
                            # New structured format
                            rejection_data = {
                                'category': rejection.get('category', 'other'),
                                'specific_reason': rejection.get('specific_reason', 'Not specified'),
                                'notes': rejection.get('notes', '')
                            }

                        try:
                            part = SlaughterPart.objects.get(id=part_id)
                            # Use RejectionService to handle rejection with notifications
                            RejectionService.process_part_rejection(
                                part, rejection_data, request.user, processing_unit
                            )
                            rejected_parts.append(part)
                        except SlaughterPart.DoesNotExist:
                            continue

                # Create activity log
                if received_animals or received_parts or rejected_animals or rejected_parts:
                    Activity.objects.create(
                        user=request.user,
                        activity_type='receive',
                        title=f'Received {len(received_animals)} animals and {len(received_parts)} parts',
                        description=f'Processed {len(rejected_animals)} animal rejections and {len(rejected_parts)} part rejections',
                        entity_type='receive',
                        metadata={
                            'received_animals': len(received_animals),
                            'received_parts': len(received_parts),
                            'rejected_animals': len(rejected_animals),
                            'rejected_parts': len(rejected_parts)
                        }
                    )

                return Response({
                    'message': f'Successfully processed receive operation',
                    'received_animals': [a.id for a in received_animals],
                    'received_parts': [p.id for p in received_parts],
                    'rejected_animals': [a.id for a in rejected_animals],
                    'rejected_parts': [p.id for p in rejected_parts]
                })

        except Exception as e:
            return Response(
                {'error': f'Failed to process receive: {str(e)}'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='by-status')
    def by_status(self, request):
        """Get animals filtered by lifecycle status"""
        status_filter = request.query_params.get('status')
        if not status_filter:
            return Response(
                {'error': 'status parameter is required'},
                status=status_module.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset()

        if status_filter.upper() == 'HEALTHY':
            queryset = queryset.filter(
                transferred_to__isnull=True,
                slaughtered=False
            )
        elif status_filter.upper() == 'SLAUGHTERED':
            queryset = queryset.filter(
                slaughtered=True,
                transferred_to__isnull=True
            )
        elif status_filter.upper() == 'TRANSFERRED':
            queryset = queryset.filter(transferred_to__isnull=False)
        elif status_filter.upper() == 'SEMI-TRANSFERRED':
            # Animals with some parts transferred but not all
            queryset = queryset.filter(
                slaughter_parts__transferred_to__isnull=False
            ).exclude(
                transferred_to__isnull=False
            ).distinct()

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'status': status_filter,
            'count': queryset.count(),
            'animals': serializer.data
        })


class SlaughterPartViewSet(viewsets.ModelViewSet):
    """ViewSet for managing slaughter parts with filtering and CRUD operations"""
    serializer_class = SlaughterPartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return slaughter parts for the current user with optional filtering.
        
        Filtering logic:
        - Farmers: see parts from their animals
        - Processors: see parts transferred to or received by them
        - Admins: see all parts
        """
        user = self.request.user
        queryset = SlaughterPart.objects.all().select_related('animal', 'transferred_to', 'received_by')

        # Farmers see parts from their own animals
        if hasattr(user, 'profile') and user.profile.role == 'farmer':
            queryset = queryset.filter(animal__farmer=user)

        # ProcessingUnit users see parts transferred to or received by them
        elif hasattr(user, 'profile') and user.profile.role == 'processing_unit':
            # Get all processing units the user is a member of
            from .models import ProcessingUnitUser
            user_processing_units = ProcessingUnitUser.objects.filter(
                user=user,
                is_active=True,
                is_suspended=False
            ).values_list('processing_unit_id', flat=True)
            
            if user_processing_units:
                # Show parts transferred to any of the user's processing units OR received by the user
                # Exclude rejected parts
                queryset = queryset.filter(
                    Q(transferred_to_id__in=user_processing_units) |
                    Q(received_by=user)
                ).exclude(
                    rejection_status='rejected'
                )
            else:
                # Fallback to parts received by the user directly
                # Exclude rejected parts
                queryset = queryset.filter(received_by=user).exclude(
                    rejection_status='rejected'
                )

        # Apply filters from query parameters
        animal_id = self.request.query_params.get('animal')
        if animal_id:
            queryset = queryset.filter(animal_id=animal_id)

        part_type = self.request.query_params.get('part_type')
        if part_type:
            queryset = queryset.filter(part_type=part_type)

        used_in_product = self.request.query_params.get('used_in_product')
        if used_in_product is not None:
            used_bool = used_in_product.lower() == 'true'
            queryset = queryset.filter(used_in_product=used_bool)

        received_by = self.request.query_params.get('received_by')
        if received_by:
            queryset = queryset.filter(received_by_id=received_by)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(part_id__icontains=search) |
                Q(description__icontains=search) |
                Q(animal__animal_id__icontains=search)
            )

        ordering = self.request.query_params.get('ordering', '-created_at')
        if ordering:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        """Create a slaughter part"""
        serializer.save()


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notifications with filtering and batch actions"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return notifications for the current user with optional filtering.
        Query parameters:
        - is_read: Filter by read status (true/false)
        - is_dismissed: Filter by dismissed status (true/false)
        - is_archived: Filter by archived status (true/false)
        - priority: Filter by priority level
        - notification_type: Filter by notification type
        - group_key: Filter by group key
        """
        queryset = Notification.objects.filter(user=self.request.user)

        # Apply filters
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')

        is_dismissed = self.request.query_params.get('is_dismissed')
        if is_dismissed is not None:
            queryset = queryset.filter(is_dismissed=is_dismissed.lower() == 'true')

        is_archived = self.request.query_params.get('is_archived')
        if is_archived is not None:
            queryset = queryset.filter(is_archived=is_archived.lower() == 'true')

        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        notification_type = self.request.query_params.get('notification_type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        group_key = self.request.query_params.get('group_key')
        if group_key:
            queryset = queryset.filter(group_key=group_key)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['patch'], url_path='mark-read')
    def mark_read_single(self, request, pk=None):
        """Mark a single notification as read"""
        try:
            notification = self.get_object()
            if notification.user != request.user:
                return Response(
                    {'error': 'You do not have permission to modify this notification'},
                    status=status_module.HTTP_403_FORBIDDEN
                )
            
            if not notification.is_read:
                notification.is_read = True
                notification.read_at = timezone.now()
                notification.save()
            
            serializer = self.get_serializer(notification)
            return Response(serializer.data)
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status_module.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        """Mark notifications as read"""
        notification_ids = request.data.get('notification_ids', [])
        if not notification_ids:
            return Response({'error': 'notification_ids are required'}, status=status_module.HTTP_400_BAD_REQUEST)

        updated_count = Notification.objects.filter(
            user=request.user,
            id__in=notification_ids,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())

        return Response({
            'message': f'Marked {updated_count} notifications as read',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['post'], url_path='mark-unread')
    def mark_unread(self, request):
        """Mark notifications as unread"""
        notification_ids = request.data.get('notification_ids', [])
        if not notification_ids:
            return Response({'error': 'notification_ids are required'}, status=status_module.HTTP_400_BAD_REQUEST)

        updated_count = Notification.objects.filter(
            user=request.user,
            id__in=notification_ids,
            is_read=True
        ).update(is_read=False, read_at=None)

        return Response({
            'message': f'Marked {updated_count} notifications as unread',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['post'], url_path='dismiss')
    def dismiss(self, request):
        """Dismiss notifications"""
        notification_ids = request.data.get('notification_ids', [])
        if not notification_ids:
            return Response({'error': 'notification_ids are required'}, status=status_module.HTTP_400_BAD_REQUEST)

        updated_count = Notification.objects.filter(
            user=request.user,
            id__in=notification_ids,
            is_dismissed=False
        ).update(is_dismissed=True, dismissed_at=timezone.now())

        return Response({
            'message': f'Dismissed {updated_count} notifications',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['post'], url_path='archive')
    def archive(self, request):
        """Archive notifications"""
        notification_ids = request.data.get('notification_ids', [])
        if not notification_ids:
            return Response({'error': 'notification_ids are required'}, status=status_module.HTTP_400_BAD_REQUEST)

        updated_count = Notification.objects.filter(
            user=request.user,
            id__in=notification_ids,
            is_archived=False
        ).update(is_archived=True, archived_at=timezone.now())

        return Response({
            'message': f'Archived {updated_count} notifications',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['post'], url_path='unarchive')
    def unarchive(self, request):
        """Unarchive notifications"""
        notification_ids = request.data.get('notification_ids', [])
        if not notification_ids:
            return Response({'error': 'notification_ids are required'}, status=status_module.HTTP_400_BAD_REQUEST)

        updated_count = Notification.objects.filter(
            user=request.user,
            id__in=notification_ids,
            is_archived=True
        ).update(is_archived=False, archived_at=None)

        return Response({
            'message': f'Unarchived {updated_count} notifications',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['post'], url_path='batch-update')
    def batch_update(self, request):
        """Batch update multiple notifications with different operations"""
        operations = request.data.get('operations', [])
        if not operations:
            return Response({'error': 'operations are required'}, status=status_module.HTTP_400_BAD_REQUEST)

        total_updated = 0
        results = []

        for operation in operations:
            op_type = operation.get('type')
            notification_ids = operation.get('notification_ids', [])

            if not op_type or not notification_ids:
                continue

            if op_type == 'mark_read':
                count = Notification.objects.filter(
                    user=request.user,
                    id__in=notification_ids,
                    is_read=False
                ).update(is_read=True, read_at=timezone.now())
            elif op_type == 'mark_unread':
                count = Notification.objects.filter(
                    user=request.user,
                    id__in=notification_ids,
                    is_read=True
                ).update(is_read=False, read_at=None)
            elif op_type == 'dismiss':
                count = Notification.objects.filter(
                    user=request.user,
                    id__in=notification_ids,
                    is_dismissed=False
                ).update(is_dismissed=True, dismissed_at=timezone.now())
            elif op_type == 'archive':
                count = Notification.objects.filter(
                    user=request.user,
                    id__in=notification_ids,
                    is_archived=False
                ).update(is_archived=True, archived_at=timezone.now())
            elif op_type == 'unarchive':
                count = Notification.objects.filter(
                    user=request.user,
                    id__in=notification_ids,
                    is_archived=True
                ).update(is_archived=False, archived_at=None)
            else:
                continue

            total_updated += count
            results.append({
                'operation': op_type,
                'updated_count': count
            })

        return Response({
            'message': f'Batch operations completed. Total updated: {total_updated}',
            'total_updated': total_updated,
            'results': results
        })

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """Get unread notification count for the current user"""
        count = Notification.objects.filter(
            user=request.user,
            is_read=False,
            is_dismissed=False,
            is_archived=False
        ).count()
        return Response({'count': count})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """Mark all notifications as read for the current user"""
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return Response({
            'message': f'Marked {updated_count} notifications as read',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Get notification statistics for the current user"""
        user = request.user
        base_queryset = Notification.objects.filter(user=user)

        stats = {
            'total': base_queryset.count(),
            'unread': base_queryset.filter(is_read=False).count(),
            'read': base_queryset.filter(is_read=True).count(),
            'dismissed': base_queryset.filter(is_dismissed=True).count(),
            'archived': base_queryset.filter(is_archived=True).count(),
            'by_priority': {
                'urgent': base_queryset.filter(priority='urgent', is_dismissed=False, is_archived=False).count(),
                'high': base_queryset.filter(priority='high', is_dismissed=False, is_archived=False).count(),
                'medium': base_queryset.filter(priority='medium', is_dismissed=False, is_archived=False).count(),
                'low': base_queryset.filter(priority='low', is_dismissed=False, is_archived=False).count(),
            },
            'by_type': {}
        }

        # Count by notification type
        for choice in Notification.NOTIFICATION_TYPE_CHOICES:
            type_key = choice[0]
            count = base_queryset.filter(
                notification_type=type_key,
                is_dismissed=False,
                is_archived=False
            ).count()
            if count > 0:
                stats['by_type'][type_key] = count

        return Response(stats)

    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """Bulk delete notifications (only archived ones can be deleted)"""
        notification_ids = request.data.get('notification_ids', [])
        if not notification_ids:
            return Response({'error': 'notification_ids are required'}, status=status_module.HTTP_400_BAD_REQUEST)

        # Only allow deletion of archived notifications
        deleted_count, _ = Notification.objects.filter(
            user=request.user,
            id__in=notification_ids,
            is_archived=True
        ).delete()

        return Response({
            'message': f'Deleted {deleted_count} archived notifications',
            'deleted_count': deleted_count
        })


# ----------------------
# Minimal admin template views
# These were referenced from `urls.py` but missing, causing an import-time
# AttributeError. Provide small, safe implementations that return the
# existing templates with light-weight context so the module imports cleanly.
# ----------------------


@login_required
def admin_dashboard(request):
    """Render the admin dashboard template with lightweight defaults.

    Keep queries wrapped in try/except to avoid import-time failures if
    models are temporarily unavailable during migrations or tests.
    """
    try:
        users_total = UserProfile.objects.count()
    except Exception:
        users_total = 0

    try:
        products_active = Product.objects.filter().count()
    except Exception:
        products_active = 0

    try:
        transfers_pending = TransferRequest.objects.filter(status='pending').count()
    except Exception:
        transfers_pending = 0

    dashboard_data = {
        'users': {'total': users_total},
        'products': {'active': products_active},
        'transfers': {'pending': transfers_pending},
        'system': {'health_score': 95},
        'activities': [],
    }

    return render(request, 'admin/dashboard.html', {'dashboard_data': dashboard_data})


@login_required
def admin_users(request):
    # Provide a simple users context; templates can request more via AJAX
    try:
        users = UserProfile.objects.select_related('user').all()[:200]
    except Exception:
        users = []
    return render(request, 'admin/users.html', {'users': users})


@login_required
def admin_supply_chain(request):
    return render(request, 'admin/supply_chain.html', {})


@login_required
def admin_performance(request):
    return render(request, 'admin/performance.html', {})


@login_required
def admin_compliance(request):
    return render(request, 'admin/compliance.html', {})


@login_required
def admin_system_health(request):
    return render(request, 'admin/system_health.html', {})


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_dashboard_data(request):
    # Lightweight JSON used by the admin frontend. Keep values safe.
    try:
        users_total = UserProfile.objects.count()
    except Exception:
        users_total = 0

    try:
        products_active = Product.objects.filter().count()
    except Exception:
        products_active = 0

    data = {
        'users': {'total': users_total},
        'products': {'active': products_active},
        'transfers': {'pending': 0},
        'system': {'health_score': 95},
        'activities': [],
    }
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_supply_chain_data(request):
    return Response({'supply_chain': {}})


@api_view(['GET'])
@permission_classes([AllowAny])
def admin_performance_data(request):
    return Response({'performance': {}})


# ----------------------
# Minimal public and API view stubs referenced by urls.py
# These are lightweight and safe: they return simple JSON or render the
# expected template without heavy database operations. Replace with full
# implementations as needed.
# ----------------------


@api_view(['GET'])
@permission_classes([AllowAny])
def public_processing_units_list(request):
    try:
        units = ProcessingUnit.objects.filter(is_public=True).values('id', 'name')[:200]
        data = list(units)
    except Exception:
        data = []
    return Response({'processing_units': data})


@api_view(['GET'])
@permission_classes([AllowAny])
def public_shops_list(request):
    try:
        shops = Shop.objects.filter(is_public=True).values('id', 'name')[:200]
        data = list(shops)
    except Exception:
        data = []
    return Response({'shops': data})


class JoinRequestCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, entity_id, request_type):
        # Minimal creation flow; full validation should be added later.
        serializer = JoinRequestSerializer(data={
            'entity_id': entity_id,
            'request_type': request_type,
            'requester': getattr(request.user, 'id', None)
        })
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status_module.HTTP_201_CREATED)
        return Response(serializer.errors, status=status_module.HTTP_400_BAD_REQUEST)


class JoinRequestReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id):
        try:
            jr = JoinRequest.objects.get(id=request_id)
            data = JoinRequestSerializer(jr).data
        except Exception:
            return Response({'error': 'not found'}, status=status_module.HTTP_404_NOT_FOUND)
        return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile_view(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        # Return complete user and profile data for Flutter app compatibility
        data = {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'is_active': request.user.is_active,
            'date_joined': request.user.date_joined.isoformat() if request.user.date_joined else None,
            'last_login': request.user.last_login.isoformat() if request.user.last_login else None,
            'role': profile.role,
            'processing_unit': {
                'id': profile.processing_unit.id,
                'name': profile.processing_unit.name,
            } if profile.processing_unit else None,
            'shop': {
                'id': profile.shop.id,
                'name': profile.shop.name,
            } if profile.shop else None,
            'processing_unit_memberships': []  # Add memberships if needed
        }
    except UserProfile.DoesNotExist:
        # Fallback for users without profile
        data = {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'is_active': request.user.is_active,
            'date_joined': request.user.date_joined.isoformat() if request.user.date_joined else None,
            'last_login': request.user.last_login.isoformat() if request.user.last_login else None,
            'role': 'Farmer',  # Default role
            'processing_unit': None,
            'shop': None,
            'processing_unit_memberships': []
        }
    except Exception as e:
        # Handle any other errors gracefully
        data = {'username': getattr(request.user, 'username', None), 'error': str(e)}
    return Response({'profile': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    return Response({'message': 'dashboard placeholder'})


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint for monitoring backend availability"""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'meattrace-backend'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def activities_view(request):
    try:
        acts = Activity.objects.order_by('-created_at')[:50]
        data = ActivitySerializer(acts, many=True).data
    except Exception:
        data = []
    return Response({'activities': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_dashboard(request):
    # Return a small serialized payload compatible with farmer dashboard
    try:
        serializer = FarmerDashboardSerializer({'user': request.user})
        data = serializer.data
    except Exception:
        data = {}
    return Response(data)


@login_required
def product_info_view(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
    except Exception:
        product = None
    return render(request, 'product_info/view.html', {'product': product})


@login_required
def product_info_list_view(request):
    try:
        products = Product.objects.all()[:200]
    except Exception:
        products = []
    return render(request, 'product_info/list.html', {'products': products})


@login_required
def add_product_category(request):
    # Minimal form handler placeholder
    if request.method == 'POST':
        # In real code, validate and create category
        return JsonResponse({'status': 'created'})
    return render(request, 'product_info/add_category.html', {})


@login_required
def sale_info_view(request, sale_id):
    try:
        sale = Sale.objects.get(id=sale_id)
    except Exception:
        sale = None
    return render(request, 'sale_info/view.html', {'sale': sale})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rejection_reasons_view(request):
    try:
        reasons = RejectionReason.objects.all().values('id', 'reason')
        data = list(reasons)
    except Exception:
        data = []
    return Response({'rejection_reasons': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def production_stats_view(request):
    """
    Return production statistics for the current user's processing unit.
    
    Stats include:
    - RECEIVED: Total number of received animals/parts since account creation
    - PENDING: Total number of animals/parts not yet received/accepted or rejected
    - PRODUCTS: Total number of products created since account creation
    - IN STOCK: Total number of products not yet fully transferred to shops
    """
    try:
        user = request.user
        profile = user.profile

        # Only processing unit users get production stats
        # Support both 'processing_unit' and 'Processor' role values
        if profile.role not in ['processing_unit', 'Processor']:
            return Response({'production': {}})

        # Get user's processing units
        from .models import ProcessingUnitUser
        user_processing_units = ProcessingUnitUser.objects.filter(
            user=user,
            is_active=True,
            is_suspended=False
        ).values_list('processing_unit_id', flat=True)

        if not user_processing_units:
            return Response({'production': {}})

        from datetime import datetime, timedelta

        # RECEIVED: Count whole animals + slaughter parts received by this user
        received_whole_animals = Animal.objects.filter(
            received_by=user
        ).count()
        
        received_slaughter_parts = SlaughterPart.objects.filter(
            received_by=user
        ).count()
        
        total_animals_received = received_whole_animals + received_slaughter_parts

        # PENDING: Count animals/parts transferred to processing unit but not yet received or rejected
        pending_whole_animals = Animal.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=True,
            rejection_status__isnull=True  # Not rejected
        ).count()
        
        pending_slaughter_parts = SlaughterPart.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=True,
            rejection_status__isnull=True  # Not rejected
        ).count()
        
        pending_animals_to_process = pending_whole_animals + pending_slaughter_parts

        # PRODUCTS: Total products created by this processing unit since creation
        total_products_created = Product.objects.filter(
            processing_unit_id__in=user_processing_units
        ).count()

        # IN STOCK: Products not yet fully transferred (transferred_to is null or not transferred to shop)
        products_in_stock = Product.objects.filter(
            processing_unit_id__in=user_processing_units,
            transferred_to__isnull=True  # Not transferred to shop
        ).count()

        # TRANSFERRED: Total products transferred to shops
        total_products_transferred = Product.objects.filter(
            processing_unit_id__in=user_processing_units,
            transferred_to__isnull=False  # Transferred to shop
        ).count()

        # Calculate today's stats
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        animals_received_today = Animal.objects.filter(
            received_by=user,
            received_at__gte=today_start
        ).count() + SlaughterPart.objects.filter(
            received_by=user,
            received_at__gte=today_start
        ).count()
        
        products_created_today = Product.objects.filter(
            processing_unit_id__in=user_processing_units,
            created_at__gte=today_start
        ).count()
        
        products_transferred_today = Product.objects.filter(
            processing_unit_id__in=user_processing_units,
            transferred_to__isnull=False,
            created_at__gte=today_start  # Approximation - we'd need a transfer_date field
        ).count()

        # Calculate this week's stats
        week_start = today_start - timedelta(days=today_start.weekday())
        
        animals_received_this_week = Animal.objects.filter(
            received_by=user,
            received_at__gte=week_start
        ).count() + SlaughterPart.objects.filter(
            received_by=user,
            received_at__gte=week_start
        ).count()
        
        products_created_this_week = Product.objects.filter(
            processing_unit_id__in=user_processing_units,
            created_at__gte=week_start
        ).count()

        # Calculate throughput (animals processed per day over last 30 days)
        thirty_days_ago = today_start - timedelta(days=30)
        animals_last_30_days = Animal.objects.filter(
            received_by=user,
            received_at__gte=thirty_days_ago
        ).count() + SlaughterPart.objects.filter(
            received_by=user,
            received_at__gte=thirty_days_ago
        ).count()
        
        processing_throughput_per_day = round(animals_last_30_days / 30.0, 2) if animals_last_30_days > 0 else 0.0

        # Calculate transfer success rate (assuming all transfers are successful for now)
        if total_products_created > 0:
            transfer_success_rate = round((total_products_transferred / total_products_created) * 100, 2)
        else:
            transfer_success_rate = 0.0

        # Determine operational status
        if pending_animals_to_process > 10:
            operational_status = 'high_load'
        elif pending_animals_to_process > 5:
            operational_status = 'active'
        elif total_animals_received > 0:
            operational_status = 'operational'
        else:
            operational_status = 'idle'

        # Return stats matching the exact requirements
        stats = {
            # Main stats for Production Overview cards
            'received': total_animals_received,           # Total received animals/parts since creation
            'pending': pending_animals_to_process,        # Total animals/parts not yet received or rejected
            'products': total_products_created,           # Total products created since creation
            'in_stock': products_in_stock,                # Products not yet fully transferred to shop
            
            # Additional detailed stats (for future use)
            'details': {
                'products_created_today': products_created_today,
                'products_created_this_week': products_created_this_week,
                'animals_received_today': animals_received_today,
                'animals_received_this_week': animals_received_this_week,
                'processing_throughput_per_day': processing_throughput_per_day,
                'equipment_uptime_percentage': 95.0,  # Placeholder
                'operational_status': operational_status,
                'total_products_transferred': total_products_transferred,
                'products_transferred_today': products_transferred_today,
                'transfer_success_rate': transfer_success_rate,
                'last_updated': timezone.now().isoformat(),
            }
        }

        return Response(stats)

    except Exception as e:
        # Return empty stats on error
        import traceback
        print(f"Error in production_stats_view: {e}")
        traceback.print_exc()
        return Response({
            'received': 0,
            'pending': 0,
            'products': 0,
            'in_stock': 0,
            'details': {}
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processing_pipeline_view(request):
    """Return dynamic processing pipeline data for the current user's processing unit"""
    try:
        user = request.user
        profile = user.profile

        # Only processing unit users can see pipeline data
        if profile.role != 'processing_unit':
            return Response({'pipeline': {}})

        # Get user's processing units
        from .models import ProcessingUnitUser
        user_processing_units = ProcessingUnitUser.objects.filter(
            user=user,
            is_active=True,
            is_suspended=False
        ).values_list('processing_unit_id', flat=True)

        if not user_processing_units:
            return Response({'pipeline': {}})

        # Calculate pipeline stages
        pipeline_data = {
            'stages': [],
            'total_pending': 0
        }

        # Stage 1: Receive - Animals transferred to processing unit but not received
        receive_count = Animal.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=True
        ).count()

        # Stage 2: Inspect - Animals received but not slaughtered (no carcass measurement)
        inspect_count = Animal.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=False,
            slaughtered=False
        ).count()

        # Stage 3: Process - Animals slaughtered but no products created yet
        process_count = Animal.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=False,
            slaughtered=True
        ).exclude(
            # Exclude animals that have products created from their slaughter parts
            slaughter_parts__used_in_product__isnull=False
        ).distinct().count()

        # Stage 4: Stock - Products created and in inventory
        stock_count = Product.objects.filter(
            processing_unit_id__in=user_processing_units,
            transferred_to__isnull=True  # Not transferred out
        ).count()

        # Build stages data
        stages = [
            {
                'name': 'Receive',
                'is_active': receive_count > 0,
                'is_completed': receive_count == 0,
                'count': receive_count
            },
            {
                'name': 'Inspect',
                'is_active': inspect_count > 0,
                'is_completed': inspect_count == 0 and receive_count == 0,
                'count': inspect_count
            },
            {
                'name': 'Process',
                'is_active': process_count > 0,
                'is_completed': process_count == 0 and inspect_count == 0,
                'count': process_count
            },
            {
                'name': 'Stock',
                'is_active': stock_count > 0,
                'is_completed': True,  # Stock is always "completed" if there are products
                'count': stock_count
            }
        ]

        pipeline_data['stages'] = stages
        pipeline_data['total_pending'] = receive_count + inspect_count + process_count

        return Response({'pipeline': pipeline_data})

    except Exception as e:
        # Return empty pipeline on error to avoid breaking the UI
        return Response({'pipeline': {}})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def appeal_rejection_view(request):
    # Minimal accept-and-acknowledge implementation
    data = request.data
    return Response({'received': True, 'data': data})


class ProcessingUnitViewSet(viewsets.ViewSet):
    """Minimal ViewSet exposing a `users` action used by URLs.

    This keeps URL resolution working. Replace with full ViewSet when
    implementing real behavior.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List all processing units"""
        try:
            queryset = ProcessingUnit.objects.all()
            serializer = ProcessingUnitSerializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[PROCESSING_UNIT_VIEWSET] Error listing processing units: {e}")
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'], url_path='join-requests')
    def join_requests(self, request, pk=None):
        """List join requests for a specific processing unit"""
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[PROCESSING_UNIT_VIEWSET] Fetching join requests for processing unit {pk}")
            
            # Check if processing unit exists
            try:
                processing_unit = ProcessingUnit.objects.get(pk=pk)
            except ProcessingUnit.DoesNotExist:
                return Response(
                    {'error': 'Processing unit not found'}, 
                    status=status_module.HTTP_404_NOT_FOUND
                )
            
            # Filter join requests for this processing unit
            join_requests = JoinRequest.objects.filter(
                processing_unit=processing_unit
            ).order_by('-created_at')
            
            serializer = JoinRequestSerializer(join_requests, many=True)
            logger.info(f"[PROCESSING_UNIT_VIEWSET] Found {len(join_requests)} join requests")
            
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[PROCESSING_UNIT_VIEWSET] Error fetching join requests: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e)}, 
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        try:
            users = ProcessingUnitUser.objects.filter(processing_unit_id=pk).values('id', 'user__username')
            return Response({'users': list(users)})
        except Exception:
            return Response({'users': []})


class CarcassMeasurementViewSet(viewsets.ModelViewSet):
    """ViewSet for managing carcass measurements"""
    serializer_class = CarcassMeasurementSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        """Override create to add detailed logging and handle update-or-create"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("=" * 80)
        logger.info("[CARCASS_MEASUREMENT_VIEWSET] CREATE method called")
        logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] User: {request.user.username} (ID: {request.user.id})")
        logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Request data: {request.data}")
        logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Request data type: {type(request.data)}")
        logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Request content type: {request.content_type}")
        
        try:
            # Log user profile info
            profile = request.user.profile
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] User role: {profile.role}")
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Processing unit: {profile.processing_unit}")
        except Exception as e:
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Error getting user profile: {e}")
        
        try:
            # Check if a measurement already exists for this animal
            animal_id = request.data.get('animal')
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Checking for existing measurement for animal: {animal_id}")
            
            existing_measurement = None
            if animal_id:
                try:
                    existing_measurement = CarcassMeasurement.objects.get(animal_id=animal_id)
                    logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Found existing measurement ID: {existing_measurement.id}")
                except CarcassMeasurement.DoesNotExist:
                    logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] No existing measurement found, will create new")
            
            if existing_measurement:
                # Update existing measurement
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Updating existing measurement")
                serializer = self.get_serializer(existing_measurement, data=request.data)
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
                response_data = serializer.data
                status_code = status_module.HTTP_200_OK
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Successfully updated measurement")
            else:
                # Create new measurement
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Creating new measurement")
                response = super().create(request, *args, **kwargs)
                response_data = response.data
                status_code = response.status_code
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Successfully created measurement")
            
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Response status: {status_code}")
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Response data: {response_data}")
            logger.info("=" * 80)
            
            return Response(response_data, status=status_code)
            
        except Exception as e:
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Error creating measurement: {e}")
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Error type: {type(e)}")
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Error args: {e.args}")
            import traceback
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Traceback:\n{traceback.format_exc()}")
            logger.info("=" * 80)
            raise
    
    def get_queryset(self):
        """Filter carcass measurements based on user permissions"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Admin can see all measurements
            if profile.role == 'Admin':
                return CarcassMeasurement.objects.all()
            
            # Processor can see measurements for animals in their processing unit
            elif profile.role == 'Processor':
                if profile.processing_unit:
                    # Get animals that belong to the processor's unit
                    from .models import Product
                    animal_ids = Product.objects.filter(
                        processing_unit=profile.processing_unit
                    ).values_list('animal_id', flat=True).distinct()
                    return CarcassMeasurement.objects.filter(animal_id__in=animal_ids)
                return CarcassMeasurement.objects.none()
            
            # Farmer can see measurements for their own animals
            elif profile.role == 'Farmer':
                return CarcassMeasurement.objects.filter(animal__farmer=user)
            
            # Shop owners can see measurements for animals they've purchased
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    # Get products bought by this shop
                    from .models import Product
                    animal_ids = Product.objects.filter(
                        shop=profile.shop
                    ).values_list('animal_id', flat=True).distinct()
                    return CarcassMeasurement.objects.filter(animal_id__in=animal_ids)
                return CarcassMeasurement.objects.none()
            
        except UserProfile.DoesNotExist:
            pass
        
        return CarcassMeasurement.objects.none()
    
    def perform_create(self, serializer):
        """Create a carcass measurement and trigger slaughter part creation"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("[CARCASS_MEASUREMENT_VIEWSET] perform_create called")
        logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Validated data: {serializer.validated_data}")
        
        try:
            measurement = serializer.save()
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Measurement saved successfully. ID: {measurement.id}")
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Animal: {measurement.animal.animal_id}")
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Carcass type: {measurement.carcass_type}")
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Measurements: {measurement.measurements}")
            
            # Mark the animal as slaughtered
            animal = measurement.animal
            if not animal.slaughtered:
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Marking animal {animal.animal_id} as slaughtered")
                animal.slaughtered = True
                animal.slaughter_date = timezone.now()
                animal.save()
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Animal marked as slaughtered successfully")
            else:
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Animal {animal.animal_id} was already marked as slaughtered")
            
            # Import the utility function to create slaughter parts
            from .utils.carcass_parts import create_slaughter_parts_from_measurement
            
            logger.info("[CARCASS_MEASUREMENT_VIEWSET] Creating slaughter parts...")
            # Create slaughter parts from the measurement
            create_slaughter_parts_from_measurement(measurement.animal, measurement)
            logger.info("[CARCASS_MEASUREMENT_VIEWSET] Slaughter parts created successfully")
            
        except Exception as e:
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Error in perform_create: {e}")
            import traceback
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Traceback:\n{traceback.format_exc()}")
            raise

    def perform_update(self, serializer):
        """Update a carcass measurement and recreate slaughter parts"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("[CARCASS_MEASUREMENT_VIEWSET] perform_update called")
        logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Validated data: {serializer.validated_data}")
        
        try:
            measurement = serializer.save()
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Measurement updated successfully. ID: {measurement.id}")
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Animal: {measurement.animal.animal_id}")
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Carcass type: {measurement.carcass_type}")
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Measurements: {measurement.measurements}")
            
            # Mark the animal as slaughtered (in case it wasn't already)
            animal = measurement.animal
            if not animal.slaughtered:
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Marking animal {animal.animal_id} as slaughtered")
                animal.slaughtered = True
                animal.slaughter_date = timezone.now()
                animal.save()
                logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Animal marked as slaughtered successfully")
            
            # Delete existing slaughter parts for this animal
            logger.info("[CARCASS_MEASUREMENT_VIEWSET] Deleting existing slaughter parts...")
            deleted_count = SlaughterPart.objects.filter(animal=measurement.animal).delete()[0]
            logger.info(f"[CARCASS_MEASUREMENT_VIEWSET] Deleted {deleted_count} existing slaughter parts")
            
            # Import the utility function to create slaughter parts
            from .utils.carcass_parts import create_slaughter_parts_from_measurement
            
            logger.info("[CARCASS_MEASUREMENT_VIEWSET] Creating new slaughter parts...")
            # Create slaughter parts from the measurement
            create_slaughter_parts_from_measurement(measurement.animal, measurement)
            logger.info("[CARCASS_MEASUREMENT_VIEWSET] Slaughter parts created successfully")
            
        except Exception as e:
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Error in perform_update: {e}")
            import traceback
            logger.error(f"[CARCASS_MEASUREMENT_VIEWSET] Traceback:\n{traceback.format_exc()}")
            raise


class ActivityViewSet(viewsets.ModelViewSet):
    """ViewSet for managing activity logs"""
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter activities based on user permissions"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Admin can see all activities
            if profile.role == 'Admin':
                return Activity.objects.all().order_by('-timestamp')
            
            # Others can only see activities related to them
            return Activity.objects.filter(user=user).order_by('-timestamp')
            
        except UserProfile.DoesNotExist:
            return Activity.objects.filter(user=user).order_by('-timestamp')


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user profiles"""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter profiles based on user permissions"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Admin can see all profiles
            if profile.role == 'Admin':
                return UserProfile.objects.all()
            
            # Processor can see profiles in their processing unit
            elif profile.role == 'Processor':
                if profile.processing_unit:
                    unit_user_ids = ProcessingUnitUser.objects.filter(
                        processing_unit=profile.processing_unit
                    ).values_list('user_id', flat=True)
                    return UserProfile.objects.filter(user_id__in=unit_user_ids)
                return UserProfile.objects.filter(user=user)
            
            # Shop owners can see profiles in their shop
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    shop_user_ids = ShopUser.objects.filter(
                        shop=profile.shop
                    ).values_list('user_id', flat=True)
                    return UserProfile.objects.filter(user_id__in=shop_user_ids)
                return UserProfile.objects.filter(user=user)
            
            # Others can only see their own profile
            return UserProfile.objects.filter(user=user)
            
        except UserProfile.DoesNotExist:
            return UserProfile.objects.filter(user=user)


class JoinRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing join requests"""
    serializer_class = JoinRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter join requests based on user permissions"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Admin can see all requests
            if profile.role == 'Admin':
                return JoinRequest.objects.all().order_by('-created_at')
            
            # Processor can see requests for their processing unit
            elif profile.role == 'Processor':
                if profile.processing_unit:
                    return JoinRequest.objects.filter(
                        processing_unit=profile.processing_unit
                    ).order_by('-created_at')
                return JoinRequest.objects.filter(user=user).order_by('-created_at')
            
            # Shop owners can see requests for their shop
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    return JoinRequest.objects.filter(
                        shop=profile.shop
                    ).order_by('-created_at')
                return JoinRequest.objects.filter(user=user).order_by('-created_at')
            
            # Others can only see their own requests
            return JoinRequest.objects.filter(user=user).order_by('-created_at')
            
        except UserProfile.DoesNotExist:
            return JoinRequest.objects.filter(user=user).order_by('-created_at')


class ShopViewSet(viewsets.ModelViewSet):
    """ViewSet for managing shops"""
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter shops based on user permissions"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Admin can see all shops
            if profile.role == 'Admin':
                return Shop.objects.all()
            
            # Shop owners can see their own shop
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    return Shop.objects.filter(id=profile.shop.id)
                return Shop.objects.none()
            
            # Others can see all shops (for browsing)
            return Shop.objects.all()
            
        except UserProfile.DoesNotExist:
            return Shop.objects.all()

    @action(detail=True, methods=['get'], url_path='join-requests', permission_classes=[AllowAny])
    def join_requests(self, request, pk=None):
        """List join requests for a specific shop"""
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[SHOP_VIEWSET] Fetching join requests for shop {pk}")
            
            # Check if shop exists
            try:
                shop = Shop.objects.get(pk=pk)
            except Shop.DoesNotExist:
                return Response(
                    {'error': 'Shop not found'}, 
                    status=status_module.HTTP_404_NOT_FOUND
                )
            
            # Only allow shop owners/managers to view join requests
            user = request.user
            if user.is_authenticated:
                try:
                    # Check if user is owner or member of this shop
                    from .models import ShopUser
                    is_shop_member = ShopUser.objects.filter(
                        user=user,
                        shop=shop,
                        is_active=True
                    ).exists()
                    
                    # Or check if user's profile is linked to this shop
                    is_shop_owner = hasattr(user, 'profile') and user.profile.shop_id == shop.id
                    
                    if not (is_shop_member or is_shop_owner or user.is_staff):
                        return Response(
                            {'error': 'You do not have permission to view join requests for this shop'},
                            status=status_module.HTTP_403_FORBIDDEN
                        )
                except Exception as perm_error:
                    logger.error(f"[SHOP_VIEWSET] Permission check error: {perm_error}")
            
            # Filter join requests for this shop
            join_requests = JoinRequest.objects.filter(
                shop=shop
            ).order_by('-created_at')
            
            serializer = JoinRequestSerializer(join_requests, many=True)
            logger.info(f"[SHOP_VIEWSET] Found {len(join_requests)} join requests")
            
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[SHOP_VIEWSET] Error fetching join requests: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e)}, 
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='members', permission_classes=[AllowAny])
    def members(self, request, pk=None):
        """List members of a specific shop"""
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[SHOP_VIEWSET] Fetching members for shop {pk}")
            
            # Check if shop exists
            try:
                shop = Shop.objects.get(pk=pk)
            except Shop.DoesNotExist:
                return Response(
                    {'error': 'Shop not found'}, 
                    status=status_module.HTTP_404_NOT_FOUND
                )
            
            # Only allow shop owners/managers to view members
            user = request.user
            if user.is_authenticated:
                try:
                    # Check if user is owner or member of this shop
                    from .models import ShopUser
                    is_shop_member = ShopUser.objects.filter(
                        user=user,
                        shop=shop,
                        is_active=True
                    ).exists()
                    
                    # Or check if user's profile is linked to this shop
                    is_shop_owner = hasattr(user, 'profile') and user.profile.shop_id == shop.id
                    
                    if not (is_shop_member or is_shop_owner or user.is_staff):
                        return Response(
                            {'error': 'You do not have permission to view members of this shop'},
                            status=status_module.HTTP_403_FORBIDDEN
                        )
                except Exception as perm_error:
                    logger.error(f"[SHOP_VIEWSET] Permission check error: {perm_error}")
            
            # Get shop members
            from .models import ShopUser
            shop_members = ShopUser.objects.filter(shop=shop).select_related('user')
            
            # Serialize member data
            members_data = []
            for shop_user in shop_members:
                members_data.append({
                    'id': shop_user.id,
                    'user': {
                        'id': shop_user.user.id,
                        'username': shop_user.user.username,
                        'email': shop_user.user.email,
                        'first_name': shop_user.user.first_name,
                        'last_name': shop_user.user.last_name,
                    },
                    'role': shop_user.role,
                    'permissions': shop_user.permissions,
                    'is_active': shop_user.is_active,
                    'joined_at': shop_user.joined_at,
                    'invited_by': {
                        'id': shop_user.invited_by.id,
                        'username': shop_user.invited_by.username,
                    } if shop_user.invited_by else None,
                })
            
            logger.info(f"[SHOP_VIEWSET] Found {len(members_data)} members")
            
            return Response(members_data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[SHOP_VIEWSET] Error fetching members: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e)}, 
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing orders"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter orders based on user permissions"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Admin can see all orders
            if profile.role == 'Admin':
                return Order.objects.all().order_by('-created_at')
            
            # Shop owners can see orders for their shop
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    return Order.objects.filter(shop=profile.shop).order_by('-created_at')
                return Order.objects.none()
            
            # Processor can see orders related to their processing unit
            elif profile.role == 'Processor':
                if profile.processing_unit:
                    return Order.objects.filter(
                        items__product__processing_unit=profile.processing_unit
                    ).distinct().order_by('-created_at')
                return Order.objects.none()
            
            return Order.objects.none()
            
        except UserProfile.DoesNotExist:
            return Order.objects.none()


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for managing products"""
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        """Override to handle weight tracking when creating products"""
        from decimal import Decimal
        
        # Get the product weight and related animal/part from request data
        product_weight = Decimal(str(self.request.data.get('weight', 0)))
        animal_id = self.request.data.get('animal')
        slaughter_part_id = self.request.data.get('slaughter_part')
        
        # Save the product first
        product = serializer.save()
        
        # Update weight tracking
        if slaughter_part_id:
            # Product made from slaughter part - deduct from part's remaining weight
            try:
                slaughter_part = SlaughterPart.objects.get(id=slaughter_part_id)
                if slaughter_part.remaining_weight is None:
                    slaughter_part.remaining_weight = slaughter_part.weight
                
                slaughter_part.remaining_weight = max(Decimal('0'), slaughter_part.remaining_weight - product_weight)
                
                # Mark as used if weight is depleted
                if slaughter_part.remaining_weight <= 0:
                    slaughter_part.used_in_product = True
                
                slaughter_part.save()
                print(f"✅ Updated slaughter part {slaughter_part.id}: remaining_weight = {slaughter_part.remaining_weight}")
            except SlaughterPart.DoesNotExist:
                print(f"⚠️ Slaughter part {slaughter_part_id} not found")
        elif animal_id:
            # Product made from whole animal - deduct from animal's remaining weight
            try:
                animal = Animal.objects.get(id=animal_id)
                if animal.remaining_weight is None:
                    animal.remaining_weight = animal.live_weight or Decimal('0')
                
                animal.remaining_weight = max(Decimal('0'), animal.remaining_weight - product_weight)
                
                # Mark as processed if weight is depleted
                if animal.remaining_weight <= 0:
                    animal.processed = True
                
                animal.save()
                print(f"✅ Updated animal {animal.id}: remaining_weight = {animal.remaining_weight}")
            except Animal.DoesNotExist:
                print(f"⚠️ Animal {animal_id} not found")
    
    def get_queryset(self):
        """Filter products based on user permissions"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Admin can see all products
            if profile.role == 'Admin':
                return Product.objects.all().order_by('-created_at')
            
            # Processor can see products from their processing unit
            elif profile.role == 'Processor':
                if profile.processing_unit:
                    return Product.objects.filter(
                        processing_unit=profile.processing_unit
                    ).order_by('-created_at')
                return Product.objects.none()
            
            # Shop owners can see products they've purchased
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    return Product.objects.filter(shop=profile.shop).order_by('-created_at')
                return Product.objects.none()
            
            # Farmer can see products from their animals
            elif profile.role == 'Farmer':
                return Product.objects.filter(animal__farmer=user).order_by('-created_at')
            
            return Product.objects.all().order_by('-created_at')
            
        except UserProfile.DoesNotExist:
            return Product.objects.all().order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='receive_products')
    def receive_products(self, request):
        """
        Selectively receive products at shop with partial quantity support and rejection handling.
        
        Expected payload:
        {
            "receives": [
                {
                    "product_id": 1,
                    "quantity_received": 50.0
                }
            ],
            "rejections": [
                {
                    "product_id": 2,
                    "quantity_rejected": 20.0,
                    "rejection_reason": "Damaged packaging"
                }
            ]
        }
        """
        receives = request.data.get('receives', [])
        rejections = request.data.get('rejections', [])
        
        if not receives and not rejections:
            return Response(
                {'error': 'Either receives or rejections must be provided'},
                status=status_module.HTTP_400_BAD_REQUEST
            )
        
        # Get user's shop
        try:
            profile = request.user.profile
            user_shop = profile.shop
            
            if not user_shop:
                return Response(
                    {'error': 'User is not associated with any shop'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'User profile not found'},
                status=status_module.HTTP_404_NOT_FOUND
            )
        
        received_products = []
        rejected_products = []
        errors = []
        
        try:
            with transaction.atomic():
                # Process receives
                for receive in receives:
                    product_id = receive.get('product_id')
                    quantity_received = Decimal(str(receive.get('quantity_received', 0)))
                    
                    if quantity_received <= 0:
                        errors.append(f"Product {product_id}: quantity_received must be greater than 0")
                        continue
                    
                    try:
                        product = Product.objects.get(
                            id=product_id,
                            transferred_to=user_shop,
                            rejection_status__isnull=True  # Not rejected
                        )
                        
                        # Validate quantity
                        total_accounted = product.quantity_received + product.quantity_rejected
                        remaining = product.quantity - total_accounted
                        
                        if quantity_received > remaining:
                            errors.append(
                                f"Product {product_id}: Cannot receive {quantity_received}. "
                                f"Only {remaining} remaining (Total: {product.quantity}, "
                                f"Already received: {product.quantity_received}, "
                                f"Already rejected: {product.quantity_rejected})"
                            )
                            continue
                        
                        # Update product
                        product.quantity_received += quantity_received
                        
                        # If fully received, mark as received
                        if product.quantity_received + product.quantity_rejected >= product.quantity:
                            product.received_by_shop = user_shop
                            product.received_at = timezone.now()
                        
                        product.save()
                        
                        # Update inventory
                        inventory, created = Inventory.objects.get_or_create(
                            shop=user_shop,
                            product=product,
                            defaults={'quantity': Decimal('0')}
                        )
                        inventory.quantity += quantity_received
                        inventory.last_updated = timezone.now()
                        inventory.save()
                        
                        received_products.append({
                            'product_id': product.id,
                            'product_name': product.name,
                            'quantity_received': float(quantity_received),
                            'total_received': float(product.quantity_received),
                            'total_quantity': float(product.quantity)
                        })
                        
                    except Product.DoesNotExist:
                        errors.append(f"Product {product_id} not found or not available for receipt")
                        continue
                
                # Process rejections
                for rejection in rejections:
                    product_id = rejection.get('product_id')
                    quantity_rejected = Decimal(str(rejection.get('quantity_rejected', 0)))
                    rejection_reason = rejection.get('rejection_reason', 'Not specified')
                    
                    if quantity_rejected <= 0:
                        errors.append(f"Product {product_id}: quantity_rejected must be greater than 0")
                        continue
                    
                    try:
                        product = Product.objects.get(
                            id=product_id,
                            transferred_to=user_shop
                        )
                        
                        # Validate quantity
                        total_accounted = product.quantity_received + product.quantity_rejected
                        remaining = product.quantity - total_accounted
                        
                        if quantity_rejected > remaining:
                            errors.append(
                                f"Product {product_id}: Cannot reject {quantity_rejected}. "
                                f"Only {remaining} remaining (Total: {product.quantity}, "
                                f"Already received: {product.quantity_received}, "
                                f"Already rejected: {product.quantity_rejected})"
                            )
                            continue
                        
                        # Update product
                        product.quantity_rejected += quantity_rejected
                        product.rejection_reason = rejection_reason
                        product.rejected_by = request.user
                        product.rejected_at = timezone.now()
                        
                        # If entire product is rejected, mark status as rejected
                        if product.quantity_rejected >= product.quantity:
                            product.rejection_status = 'rejected'
                        
                        product.save()
                        
                        rejected_products.append({
                            'product_id': product.id,
                            'product_name': product.name,
                            'quantity_rejected': float(quantity_rejected),
                            'total_rejected': float(product.quantity_rejected),
                            'rejection_reason': rejection_reason,
                            'rejection_status': product.rejection_status
                        })
                        
                    except Product.DoesNotExist:
                        errors.append(f"Product {product_id} not found")
                        continue
                
                # Create activity log
                if received_products or rejected_products:
                    Activity.objects.create(
                        user=request.user,
                        activity_type='receive',
                        title=f'Received/Rejected products at {user_shop.name}',
                        description=f'Received {len(received_products)} products, Rejected {len(rejected_products)} products',
                        entity_type='product_receipt',
                        metadata={
                            'shop': user_shop.name,
                            'received_count': len(received_products),
                            'rejected_count': len(rejected_products)
                        }
                    )
                
                response_data = {
                    'message': 'Product receipt processed successfully',
                    'received_products': received_products,
                    'rejected_products': rejected_products
                }
                
                if errors:
                    response_data['errors'] = errors
                
                return Response(response_data)
        
        except Exception as e:
            return Response(
                {'error': f'Failed to process receipt: {str(e)}'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='transfer')
    def transfer_products(self, request):
        """
        Transfer products to a shop with optional quantity adjustment.
        
        Expected payload:
        {
            "shop_id": 1,
            "transfers": [
                {
                    "product_id": 1,
                    "quantity": 50.0  # Optional - defaults to full product quantity
                }
            ]
        }
        """
        user = request.user
        
        # Verify user is a processor
        try:
            profile = user.profile
            if profile.role != 'Processor':
                return Response(
                    {'error': 'Only processors can transfer products'},
                    status=status_module.HTTP_403_FORBIDDEN
                )
            
            processing_unit = profile.processing_unit
            if not processing_unit:
                return Response(
                    {'error': 'User not associated with a processing unit'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'User profile not found'},
                status=status_module.HTTP_404_NOT_FOUND
            )
        
        shop_id = request.data.get('shop_id')
        transfers = request.data.get('transfers', [])
        
        # Support legacy format with product_ids array
        product_ids = request.data.get('product_ids')
        if product_ids and not transfers:
            transfers = [{'product_id': pid} for pid in product_ids]
        
        if not shop_id:
            return Response(
                {'error': 'shop_id is required'},
                status=status_module.HTTP_400_BAD_REQUEST
            )
        
        if not transfers:
            return Response(
                {'error': 'transfers or product_ids are required'},
                status=status_module.HTTP_400_BAD_REQUEST
            )
        
        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Shop not found'},
                status=status_module.HTTP_404_NOT_FOUND
            )
        
        transferred_count = 0
        errors = []
        
        try:
            with transaction.atomic():
                for transfer in transfers:
                    product_id = transfer.get('product_id')
                    quantity_to_transfer = transfer.get('quantity')
                    
                    try:
                        product = Product.objects.get(
                            id=product_id,
                            processing_unit=processing_unit
                        )
                    except Product.DoesNotExist:
                        errors.append(f'Product {product_id} not found or not owned by your processing unit')
                        continue
                    
                    if product.transferred_to is not None:
                        errors.append(f'Product {product.name} has already been transferred')
                        continue
                    
                    # If quantity specified, validate it
                    if quantity_to_transfer is not None:
                        quantity_to_transfer = Decimal(str(quantity_to_transfer))
                        
                        if quantity_to_transfer <= 0:
                            errors.append(f'Product {product.name}: quantity must be greater than 0')
                            continue
                        
                        if quantity_to_transfer > product.quantity:
                            errors.append(
                                f'Product {product.name}: cannot transfer {quantity_to_transfer}. '
                                f'Only {product.quantity} available'
                            )
                            continue
                        
                        # If transferring partial quantity, create a new product for the transfer
                        if quantity_to_transfer < product.quantity:
                            # Reduce original product quantity
                            original_quantity = product.quantity
                            product.quantity -= quantity_to_transfer
                            product.save()
                            
                            # Create new product for transfer
                            transferred_product = Product.objects.create(
                                name=product.name,
                                batch_number=f"{product.batch_number}-T",
                                product_type=product.product_type,
                                quantity=quantity_to_transfer,
                                weight=product.weight * (quantity_to_transfer / original_quantity) if product.weight else None,
                                weight_unit=product.weight_unit,
                                price=product.price,
                                description=product.description,
                                processing_unit=processing_unit,
                                animal=product.animal,
                                slaughter_part=product.slaughter_part,
                                category=product.category,
                                transferred_to=shop,
                                transferred_at=timezone.now()
                            )
                            
                            # Create activity for split and transfer
                            Activity.objects.create(
                                user=user,
                                activity_type='transfer',
                                title=f'Product {product.name} split and transferred',
                                description=f'Split {product.name}: kept {product.quantity}, transferred {quantity_to_transfer} to {shop.name}',
                                entity_id=str(transferred_product.id),
                                entity_type='product',
                                metadata={
                                    'original_product_id': product.id,
                                    'transferred_product_id': transferred_product.id,
                                    'original_batch': product.batch_number,
                                    'transferred_batch': transferred_product.batch_number,
                                    'quantity_kept': float(product.quantity),
                                    'quantity_transferred': float(quantity_to_transfer),
                                    'shop_name': shop.name
                                }
                            )
                        else:
                            # Transfer full product
                            product.transferred_to = shop
                            product.transferred_at = timezone.now()
                            product.save()
                            
                            # Create activity for full transfer
                            Activity.objects.create(
                                user=user,
                                activity_type='transfer',
                                title=f'Product {product.name} transferred',
                                description=f'Transferred {product.name} (Batch: {product.batch_number}) to {shop.name}',
                                entity_id=str(product.id),
                                entity_type='product',
                                metadata={
                                    'product_id': product.id,
                                    'batch_number': product.batch_number,
                                    'shop_name': shop.name,
                                    'quantity': float(product.quantity)
                                }
                            )
                    else:
                        # No quantity specified - transfer full product (legacy behavior)
                        product.transferred_to = shop
                        product.transferred_at = timezone.now()
                        product.save()
                        
                        # Create activity
                        Activity.objects.create(
                            user=user,
                            activity_type='transfer',
                            title=f'Product {product.name} transferred',
                            description=f'Transferred {product.name} (Batch: {product.batch_number}) to {shop.name}',
                            entity_id=str(product.id),
                            entity_type='product',
                            metadata={
                                'product_id': product.id,
                                'batch_number': product.batch_number,
                                'shop_name': shop.name
                            }
                        )
                    
                    transferred_count += 1
                
                # Check if there were any errors
                if errors and transferred_count == 0:
                    return Response(
                        {'errors': errors},
                        status=status_module.HTTP_400_BAD_REQUEST
                    )
                
                response_data = {
                    'message': f'Successfully transferred {transferred_count} product(s) to {shop.name}',
                    'transferred_count': transferred_count
                }
                
                if errors:
                    response_data['partial_errors'] = errors
                
                return Response(response_data)
        
        except Exception as e:
            return Response(
                {'error': f'Failed to transfer products: {str(e)}'},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product categories"""
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """All authenticated users can see all product categories"""
        return ProductCategory.objects.all().order_by('name')


class SaleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing sales"""
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter sales based on user permissions"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Admin can see all sales
            if profile.role == 'Admin':
                return Sale.objects.all().order_by('-created_at')
            
            # Shop owners can see sales from their shop
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    return Sale.objects.filter(shop=profile.shop).order_by('-created_at')
                return Sale.objects.none()
            
            # Processor can see sales of products from their processing unit
            elif profile.role == 'Processor':
                if profile.processing_unit:
                    return Sale.objects.filter(
                        items__product__processing_unit=profile.processing_unit
                    ).distinct().order_by('-created_at')
                return Sale.objects.none()
            
            return Sale.objects.none()
            
        except UserProfile.DoesNotExist:
            return Sale.objects.none()
    
    def perform_create(self, serializer):
        """Automatically set shop and sold_by when creating a sale"""
        user = self.request.user
        
        try:
            profile = user.profile
            
            # Set the shop from user's profile
            if profile.shop:
                serializer.save(shop=profile.shop, sold_by=user)
            else:
                raise ValidationError("User is not associated with any shop")
                
        except UserProfile.DoesNotExist:
            raise ValidationError("User profile not found")

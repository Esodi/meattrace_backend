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
from .role_utils import (
    normalize_role, get_user_role, is_farmer, is_processor, is_shop_owner, is_admin,
    ROLE_FARMER, ROLE_PROCESSOR, ROLE_SHOPOWNER, ROLE_ADMIN
)


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
        - Shop Owners: see NO animals (shops work with products, not animals)
        - Admins: see all animals
        """
        user = self.request.user
        queryset = Animal.objects.all().select_related('farmer', 'transferred_to', 'received_by')

        # Get normalized user role
        user_role = get_user_role(user)
        
        print(f"[ANIMAL_QUERYSET] User: {user.username}, Role: {user_role}")

        # Farmers see their own animals
        if user_role == ROLE_FARMER:
            queryset = queryset.filter(farmer=user)
            print(f"[ANIMAL_QUERYSET] Farmer filter applied: {queryset.count()} animals")

        # Processors see animals transferred to ANY processing unit they belong to
        elif user_role == ROLE_PROCESSOR:
            from .models import ProcessingUnitUser
            user_processing_units = ProcessingUnitUser.objects.filter(
                user=user,
                is_active=True,
                is_suspended=False
            ).values_list('processing_unit_id', flat=True)

            if user_processing_units:
                queryset = queryset.filter(
                    Q(transferred_to_id__in=user_processing_units) |
                    Q(slaughter_parts__transferred_to_id__in=user_processing_units)
                ).exclude(
                    rejection_status='rejected'
                ).distinct()
                print(f"[ANIMAL_QUERYSET] Processor filter applied: {queryset.count()} animals")
            else:
                queryset = queryset.none()
                print(f"[ANIMAL_QUERYSET] Processor has no units: 0 animals")
        
        # Shop owners should NOT see animals (they work with products only)
        elif user_role == ROLE_SHOPOWNER:
            queryset = queryset.none()
            print(f"[ANIMAL_QUERYSET] Shop owner filter applied: 0 animals (shops don't access animals)")
        
        # If no specific role matched, return empty queryset for security
        elif user_role not in [ROLE_ADMIN]:
            queryset = queryset.none()
            print(f"[ANIMAL_QUERYSET] Unknown role '{user_role}': 0 animals (default deny)")
        
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

    def destroy(self, request, *args, **kwargs):
        """Prevent deletion of slaughtered animals"""
        animal = self.get_object()
        
        if animal.slaughtered:
            return Response(
                {'error': 'Cannot delete slaughtered animals. Slaughtered animals must be retained for traceability.'},
                status=status_module.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)

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
        - Shop Owners: see NO slaughter parts (shops work with final products)
        - Admins: see all parts
        """
        user = self.request.user
        queryset = SlaughterPart.objects.all().select_related('animal', 'transferred_to', 'received_by')

        # Get normalized user role
        user_role = get_user_role(user)

        # Farmers see parts from their own animals
        if user_role == ROLE_FARMER:
            queryset = queryset.filter(animal__farmer=user)

        # Processors see parts transferred to or received by them
        elif user_role == ROLE_PROCESSOR:
            from .models import ProcessingUnitUser
            user_processing_units = ProcessingUnitUser.objects.filter(
                user=user,
                is_active=True,
                is_suspended=False
            ).values_list('processing_unit_id', flat=True)

            if user_processing_units:
                queryset = queryset.filter(
                    Q(transferred_to_id__in=user_processing_units) |
                    Q(received_by=user)
                ).exclude(
                    rejection_status='rejected'
                )
            else:
                queryset = queryset.filter(received_by=user).exclude(
                    rejection_status='rejected'
                )
        
        # Shop owners should NOT see slaughter parts
        elif user_role == ROLE_SHOPOWNER:
            queryset = queryset.none()
        
        # If no specific role matched, return empty queryset for security
        elif user_role not in [ROLE_ADMIN]:
            queryset = queryset.none()
        
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

    def destroy(self, request, *args, **kwargs):
        """Prevent deletion of slaughter parts for traceability"""
        return Response(
            {'error': 'Cannot delete slaughter parts. Slaughter parts must be retained for traceability.'},
            status=status_module.HTTP_400_BAD_REQUEST
        )


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


def product_info_view(request, product_id):
    try:
        product = Product.objects.select_related(
            'animal', 'animal__farmer', 'processing_unit', 
            'category', 'slaughter_part', 'transferred_to',
            'received_by_shop'
        ).prefetch_related(
            'inventory', 'receipts', 'orderitem_set', 
            'ingredients__slaughter_part',
            'animal__slaughter_parts'
        ).get(id=product_id)
        
        # Build comprehensive timeline
        timeline = []
        
        # 1. Animal Registration (Farmer Stage)
        if product.animal:
            animal = product.animal
            
            # Get farmer contact info
            farmer_details = {
                'Animal ID': animal.animal_id,
                'Animal Name': animal.animal_name or 'Not named',
                'Species': animal.get_species_display(),
                'Gender': animal.get_gender_display() if hasattr(animal, 'gender') else 'Unknown',
                'Age': f'{animal.age} months' if animal.age else 'Not recorded',
                'Live Weight': f'{animal.live_weight} kg' if animal.live_weight else 'Not recorded',
                'Health Status': animal.health_status or 'Not recorded',
                'Breed': animal.breed or 'Not specified',
                'Farmer Name': animal.farmer.get_full_name() if animal.farmer.first_name else animal.farmer.username,
                'Farmer Email': animal.farmer.email or 'Not provided',
                'Notes': animal.notes or 'None'
            }
            
            # Add farmer phone if available
            if hasattr(animal.farmer, 'profile') and hasattr(animal.farmer.profile, 'phone'):
                farmer_details['Farmer Phone'] = animal.farmer.profile.phone or 'Not provided'
            elif hasattr(animal.farmer, 'phone_number'):
                farmer_details['Farmer Phone'] = animal.farmer.phone_number or 'Not provided'
            
            timeline.append({
                'stage': 'Animal Registration',
                'category': 'farmer',
                'timestamp': animal.created_at,
                'location': f'Farm - {animal.farmer.username}',
                'actor': animal.farmer.get_full_name() if animal.farmer.first_name else animal.farmer.username,
                'action': f'Animal {animal.animal_id} registered at farm',
                'icon': 'fa-clipboard-list',
                'details': farmer_details
            })
            
            # 2. Animal Transfer to Processing Unit
            if animal.transferred_at and animal.transferred_to:
                transfer_details = {
                    'From': f'Farm - {animal.farmer.get_full_name() if animal.farmer.first_name else animal.farmer.username}',
                    'To': animal.transferred_to.name,
                    'Transfer Date': animal.transferred_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'Transfer Mode': 'Live Animal Transport',
                    'Animal ID': animal.animal_id,
                    'Animal Species': animal.get_species_display(),
                    'Live Weight': f'{animal.live_weight} kg' if animal.live_weight else 'Not recorded',
                    'Health Status': animal.health_status or 'Not recorded',
                    'Processing Unit': animal.transferred_to.name,
                    'Processing Unit Location': animal.transferred_to.location if hasattr(animal.transferred_to, 'location') else 'Not specified'
                }
                
                timeline.append({
                    'stage': 'Animal Transfer to Processing',
                    'category': 'logistics',
                    'timestamp': animal.transferred_at,
                    'location': animal.transferred_to.name,
                    'actor': animal.farmer.get_full_name() if animal.farmer.first_name else animal.farmer.username,
                    'action': f'Live animal transported to {animal.transferred_to.name}',
                    'icon': 'fa-truck',
                    'details': transfer_details
                })
            
            # 3. Animal Reception at Processing Unit
            if animal.received_at and animal.received_by:
                reception_details = {
                    'Received By': animal.received_by.get_full_name() if animal.received_by.first_name else animal.received_by.username,
                    'Reception Date': animal.received_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'Processing Unit': animal.transferred_to.name if animal.transferred_to else 'Unknown',
                    'Animal ID': animal.animal_id,
                    'Species': animal.get_species_display(),
                    'Reception Status': 'Accepted for processing',
                    'Health Inspection': animal.health_status or 'Passed',
                }
                
                if hasattr(animal.received_by, 'email'):
                    reception_details['Inspector Email'] = animal.received_by.email or 'Not provided'
                
                timeline.append({
                    'stage': 'Animal Reception & Inspection',
                    'category': 'processing',
                    'timestamp': animal.received_at,
                    'location': animal.transferred_to.name if animal.transferred_to else 'Processing Unit',
                    'actor': animal.received_by.get_full_name() if animal.received_by.first_name else animal.received_by.username,
                    'action': f'Animal received, inspected and approved for processing',
                    'icon': 'fa-check-circle',
                    'details': reception_details
                })
            
            # 4. Slaughter Event
            if animal.slaughtered and animal.slaughtered_at:
                slaughter_details = {
                    'Animal ID': animal.animal_id,
                    'Species': animal.get_species_display(),
                    'Slaughter Date': animal.slaughtered_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'Processing Unit': animal.transferred_to.name if animal.transferred_to else 'Unknown',
                    'Abbatoir': animal.abbatoir_name or 'Not specified',
                    'Pre-Slaughter Weight': f'{animal.live_weight} kg' if animal.live_weight else 'Not recorded',
                }
                
                # Add carcass measurement if available
                if hasattr(animal, 'carcass_measurement'):
                    cm = animal.carcass_measurement
                    if cm:
                        slaughter_details['Carcass Weight'] = f'{cm.carcass_weight} kg' if hasattr(cm, 'carcass_weight') and cm.carcass_weight else 'Not recorded'
                        slaughter_details['Dressing Percentage'] = f'{(cm.carcass_weight / animal.live_weight * 100):.1f}%' if animal.live_weight and hasattr(cm, 'carcass_weight') and cm.carcass_weight else 'Not calculated'
                
                timeline.append({
                    'stage': 'Slaughter',
                    'category': 'processing',
                    'timestamp': animal.slaughtered_at,
                    'location': animal.transferred_to.name if animal.transferred_to else 'Processing Unit',
                    'actor': 'Processing Unit Slaughter Team',
                    'action': f'Animal {animal.animal_id} ({animal.get_species_display()}) slaughtered',
                    'icon': 'fa-cut',
                    'details': slaughter_details
                })
                
                # 5. Carcass Breakdown - Detailed Part Tracking
                if animal.slaughter_parts.exists():
                    parts = animal.slaughter_parts.all()
                    total_parts_weight = sum([p.weight for p in parts if p.weight])
                    
                    # Create detailed parts breakdown
                    parts_breakdown = {
                        'Total Parts Created': parts.count(),
                        'Total Parts Weight': f'{total_parts_weight} kg',
                        'Breakdown Date': animal.slaughtered_at.strftime('%Y-%m-%d %H:%M:%S'),
                    }
                    
                    # List all individual parts with their destinations
                    for idx, part in enumerate(parts, 1):
                        part_key = f'Part {idx}'
                        part_value = f'{part.get_part_type_display()} - {part.weight} kg'
                        
                        # Add destination if part was transferred
                        if hasattr(part, 'transferred_to') and part.transferred_to:
                            part_value += f' → {part.transferred_to.name}'
                        elif hasattr(part, 'processing_unit') and part.processing_unit:
                            part_value += f' (at {part.processing_unit.name})'
                        
                        parts_breakdown[part_key] = part_value
                    
                    timeline.append({
                        'stage': 'Carcass Breakdown & Part Distribution',
                        'category': 'processing',
                        'timestamp': animal.slaughtered_at,
                        'location': animal.transferred_to.name if animal.transferred_to else 'Processing Unit',
                        'actor': 'Butchery Team',
                        'action': f'Carcass divided into {parts.count()} parts for processing',
                        'icon': 'fa-th-large',
                        'details': parts_breakdown
                    })
                    
                    # 5b. Individual Part Transfers (if split carcass scenario)
                    for part in parts:
                        if hasattr(part, 'transferred_at') and part.transferred_at and hasattr(part, 'transferred_to') and part.transferred_to:
                            part_transfer_details = {
                                'Part Type': part.get_part_type_display(),
                                'Part Weight': f'{part.weight} kg',
                                'From': animal.transferred_to.name if animal.transferred_to else 'Origin Processing Unit',
                                'To': part.transferred_to.name,
                                'Transfer Date': part.transferred_at.strftime('%Y-%m-%d %H:%M:%S'),
                                'Part ID': f'Part-{part.id}',
                                'Original Animal': animal.animal_id,
                            }
                            
                            timeline.append({
                                'stage': 'Carcass Part Transfer',
                                'category': 'logistics',
                                'timestamp': part.transferred_at,
                                'location': part.transferred_to.name,
                                'actor': 'Logistics Team',
                                'action': f'{part.get_part_type_display()} part transferred to different processing unit',
                                'icon': 'fa-exchange-alt',
                                'details': part_transfer_details
                            })
        
        # 6. Product Creation - Enhanced Details
        creation_details = {
            'Product Name': product.name,
            'Batch Number': product.batch_number,
            'Product Type': product.get_product_type_display(),
            'Quantity': f'{product.quantity} {product.weight_unit}',
            'Weight': f'{product.weight} {product.weight_unit}' if product.weight else 'Not recorded',
            'Category': product.category.name if product.category else 'Not categorized',
            'Processing Unit': product.processing_unit.name if product.processing_unit else 'Unknown',
            'Creation Date': product.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        # Add source information
        if product.animal:
            creation_details['Source Animal'] = product.animal.animal_id
            creation_details['Animal Species'] = product.animal.get_species_display()
        
        # Add slaughter part info if this product came from a specific part
        if product.slaughter_part:
            creation_details['From Carcass Part'] = product.slaughter_part.get_part_type_display()
            creation_details['Part Weight'] = f'{product.slaughter_part.weight} kg'
        
        # Add ingredients if this is a composite product
        if product.ingredients.exists():
            ingredients_list = []
            for ing in product.ingredients.all():
                if ing.slaughter_part:
                    ingredients_list.append(f'{ing.slaughter_part.get_part_type_display()} ({ing.quantity} {ing.weight_unit})')
            if ingredients_list:
                creation_details['Ingredients'] = ', '.join(ingredients_list)
        
        timeline.append({
            'stage': 'Product Creation',
            'category': 'processing',
            'timestamp': product.created_at,
            'location': product.processing_unit.name if product.processing_unit else 'Processing Unit',
            'actor': 'Production Team',
            'action': f'Product "{product.name}" manufactured',
            'icon': 'fa-box',
            'details': creation_details
        })
        
        # 7. Product Transfer to Shop - Enhanced
        if product.transferred_at and product.transferred_to:
            transfer_details = {
                'From': product.processing_unit.name if product.processing_unit else 'Processing Unit',
                'To': product.transferred_to.name,
                'Transfer Date': product.transferred_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Product': product.name,
                'Batch Number': product.batch_number,
                'Quantity Transferred': f'{product.quantity} {product.weight_unit}',
                'Product Type': product.get_product_type_display(),
            }
            
            # Add shop location if available
            if hasattr(product.transferred_to, 'location'):
                transfer_details['Shop Location'] = product.transferred_to.location
            if hasattr(product.transferred_to, 'owner'):
                transfer_details['Shop Owner'] = product.transferred_to.owner.get_full_name() if product.transferred_to.owner.first_name else product.transferred_to.owner.username
            
            timeline.append({
                'stage': 'Product Transfer to Retail',
                'category': 'logistics',
                'timestamp': product.transferred_at,
                'location': product.transferred_to.name,
                'actor': product.processing_unit.name if product.processing_unit else 'Processing Unit',
                'action': f'Product dispatched to {product.transferred_to.name}',
                'icon': 'fa-truck-loading',
                'details': transfer_details
            })
        
        # 8. Product Reception at Shop - Enhanced
        if product.received_at and product.received_by_shop:
            reception_details = {
                'Shop Name': product.received_by_shop.name,
                'Reception Date': product.received_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Quantity Ordered': f'{product.quantity} {product.weight_unit}',
                'Quantity Received': f'{product.quantity_received} {product.weight_unit}' if hasattr(product, 'quantity_received') and product.quantity_received else 'Same as ordered',
                'Batch Number': product.batch_number,
                'Reception Status': 'Accepted and Added to Inventory',
            }
            
            # Add shop details
            if hasattr(product.received_by_shop, 'location'):
                reception_details['Shop Location'] = product.received_by_shop.location
            if hasattr(product.received_by_shop, 'owner'):
                owner = product.received_by_shop.owner
                reception_details['Received By'] = owner.get_full_name() if owner.first_name else owner.username
                if hasattr(owner, 'email') and owner.email:
                    reception_details['Contact Email'] = owner.email
            
            timeline.append({
                'stage': 'Product Reception at Shop',
                'category': 'shop',
                'timestamp': product.received_at,
                'location': product.received_by_shop.name,
                'actor': product.received_by_shop.name,
                'action': f'Product received and stocked',
                'icon': 'fa-store',
                'details': reception_details
            })
        
        # 9. Quality Issues / Rejection - Enhanced
        if hasattr(product, 'rejected_at') and product.rejected_at and hasattr(product, 'rejection_status') and product.rejection_status:
            rejection_details = {
                'Rejected By': product.rejected_by.get_full_name() if product.rejected_by and product.rejected_by.first_name else (product.rejected_by.username if product.rejected_by else 'Unknown'),
                'Rejection Date': product.rejected_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Rejection Status': product.get_rejection_status_display() if hasattr(product, 'get_rejection_status_display') else product.rejection_status,
                'Quantity Rejected': f'{product.quantity_rejected} {product.weight_unit}' if hasattr(product, 'quantity_rejected') and product.quantity_rejected else 'Full quantity',
                'Reason': product.rejection_reason or 'Not specified',
                'Location': product.received_by_shop.name if product.received_by_shop else 'Unknown',
            }
            
            if product.rejected_by and hasattr(product.rejected_by, 'email') and product.rejected_by.email:
                rejection_details['Rejector Email'] = product.rejected_by.email
            
            timeline.append({
                'stage': 'Product Rejection / Quality Issue',
                'category': 'quality',
                'timestamp': product.rejected_at,
                'location': product.received_by_shop.name if product.received_by_shop else 'Shop',
                'actor': product.rejected_by.get_full_name() if product.rejected_by and product.rejected_by.first_name else (product.rejected_by.username if product.rejected_by else 'Shop Staff'),
                'action': f'Product rejected: {product.rejection_reason or "Quality concerns"}',
                'icon': 'fa-times-circle',
                'details': rejection_details
            })
        
        # 10. Sales Events - COMPREHENSIVE Customer Details with Inventory Tracking
        sales = []
        
        # Calculate running inventory after each sale
        total_quantity_sold = 0
        remaining_after_sale = 0
        initial_inventory = float(product.quantity) if product.quantity else 0
        
        order_items = product.orderitem_set.select_related('order', 'order__customer', 'order__shop').order_by('order__created_at')
        
        for idx, item in enumerate(order_items, 1):
            if item.order:
                customer = item.order.customer
                shop = item.order.shop
                order = item.order
                
                # Calculate inventory after this sale
                quantity_sold_in_this_order = float(item.quantity) if hasattr(item, 'quantity') and item.quantity else 0
                total_quantity_sold += quantity_sold_in_this_order
                remaining_after_sale = initial_inventory - total_quantity_sold
                
                # Build comprehensive sale details
                sale_details = {
                    'Sale Number': f'#{idx} of {order_items.count()}',
                    'Order ID': f'#{order.id}',
                    'Sale Date & Time': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'Day of Week': order.created_at.strftime('%A'),
                    'Time of Day': order.created_at.strftime('%I:%M %p'),
                }
                
                # Customer Information
                sale_details['---Customer Information---'] = '---'
                sale_details['Customer Name'] = customer.get_full_name() if customer and customer.first_name else (customer.username if customer else 'Walk-in Customer')
                
                if customer:
                    sale_details['Customer Username'] = customer.username
                    
                    if hasattr(customer, 'email') and customer.email:
                        sale_details['Customer Email'] = customer.email
                    
                    # Try multiple ways to get phone number
                    phone_found = False
                    if hasattr(customer, 'profile'):
                        if hasattr(customer.profile, 'phone') and customer.profile.phone:
                            sale_details['Customer Phone'] = customer.profile.phone
                            phone_found = True
                        elif hasattr(customer.profile, 'phone_number') and customer.profile.phone_number:
                            sale_details['Customer Phone'] = customer.profile.phone_number
                            phone_found = True
                    
                    if not phone_found and hasattr(customer, 'phone_number') and customer.phone_number:
                        sale_details['Customer Phone'] = customer.phone_number
                        phone_found = True
                    
                    if not phone_found and hasattr(customer, 'phone') and customer.phone:
                        sale_details['Customer Phone'] = customer.phone
                        phone_found = True
                    
                    if not phone_found:
                        sale_details['Customer Phone'] = 'Not provided'
                    
                    # Add customer address if available
                    if hasattr(customer, 'profile'):
                        if hasattr(customer.profile, 'address') and customer.profile.address:
                            sale_details['Customer Address'] = customer.profile.address
                        elif hasattr(customer.profile, 'location') and customer.profile.location:
                            sale_details['Customer Location'] = customer.profile.location
                else:
                    sale_details['Customer Type'] = 'Walk-in (No account)'
                
                # Sale Details
                sale_details['---Sale Details---'] = '---'
                sale_details['Quantity Sold This Order'] = f'{item.quantity} {product.weight_unit}'
                sale_details['Unit Price'] = f'${item.unit_price}' if hasattr(item, 'unit_price') and item.unit_price else 'N/A'
                sale_details['Subtotal for This Item'] = f'${item.subtotal}' if hasattr(item, 'subtotal') and item.subtotal else f'${float(item.quantity) * float(item.unit_price) if hasattr(item, "unit_price") and item.unit_price else 0:.2f}'
                sale_details['Order Status'] = order.get_status_display() if hasattr(order, 'get_status_display') else order.status
                
                # Inventory Tracking
                sale_details['---Inventory Status---'] = '---'
                sale_details['Initial Product Quantity'] = f'{initial_inventory} {product.weight_unit}'
                sale_details['Total Sold Up To Now'] = f'{total_quantity_sold} {product.weight_unit}'
                sale_details['Remaining After This Sale'] = f'{remaining_after_sale} {product.weight_unit}'
                sale_details['Percentage Sold'] = f'{(total_quantity_sold / initial_inventory * 100):.1f}%' if initial_inventory > 0 else 'N/A'
                
                # Shop Information
                sale_details['---Shop Information---'] = '---'
                sale_details['Shop Name'] = shop.name if shop else 'Unknown Shop'
                if shop and hasattr(shop, 'location'):
                    sale_details['Shop Location'] = shop.location
                if shop and hasattr(shop, 'owner'):
                    sale_details['Shop Owner'] = shop.owner.get_full_name() if shop.owner.first_name else shop.owner.username
                
                # Delivery information if available
                if hasattr(order, 'delivery_address') and order.delivery_address:
                    sale_details['---Delivery Information---'] = '---'
                    sale_details['Delivery Address'] = order.delivery_address
                    if hasattr(order, 'delivery_date') and order.delivery_date:
                        sale_details['Delivery Date'] = order.delivery_date.strftime('%Y-%m-%d %H:%M:%S')
                    if hasattr(order, 'delivery_status') and order.delivery_status:
                        sale_details['Delivery Status'] = order.delivery_status
                
                # Payment information
                if hasattr(order, 'payment_method') or hasattr(order, 'payment_status') or hasattr(order, 'total_amount'):
                    sale_details['---Payment Information---'] = '---'
                    if hasattr(order, 'payment_method') and order.payment_method:
                        sale_details['Payment Method'] = order.payment_method
                    if hasattr(order, 'payment_status') and order.payment_status:
                        sale_details['Payment Status'] = order.payment_status
                    if hasattr(order, 'total_amount') and order.total_amount:
                        sale_details['Full Order Total'] = f'${order.total_amount}'
                
                # Additional order items if this order has multiple products
                order_total_items = order.orderitem_set.count() if hasattr(order, 'orderitem_set') else 1
                if order_total_items > 1:
                    sale_details['---Order Context---'] = '---'
                    sale_details['Total Items in Order'] = order_total_items
                    sale_details['This Product is Item'] = f'{idx} in multi-item order'
                
                sales.append({
                    'stage': f'Sale #{idx} to Customer',
                    'category': 'sale',
                    'timestamp': order.created_at,
                    'location': shop.name if shop else 'Retail Shop',
                    'actor': shop.name if shop else 'Retail Shop',
                    'action': f'Sold {item.quantity} {product.weight_unit} to {customer.get_full_name() if customer and customer.first_name else (customer.username if customer else "walk-in customer")}',
                    'icon': 'fa-shopping-cart',
                    'details': sale_details
                })
        
        timeline.extend(sales)
        
        # 11. Current Inventory Status (if product still has remaining stock)
        if remaining_after_sale > 0 or total_quantity_sold == 0:
            current_inventory_items = product.inventory.select_related('shop').all()
            
            if current_inventory_items.exists():
                for inv_item in current_inventory_items:
                    inventory_details = {
                        'Shop Name': inv_item.shop.name if inv_item.shop else 'Unknown',
                        'Current Stock': f'{inv_item.quantity} {product.weight_unit}' if hasattr(inv_item, 'quantity') else 'Unknown',
                        'Stock Status': 'In Stock' if (hasattr(inv_item, 'quantity') and inv_item.quantity > 0) else 'Out of Stock',
                        'Last Updated': inv_item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(inv_item, 'updated_at') and inv_item.updated_at else 'Not tracked',
                    }
                    
                    if hasattr(inv_item.shop, 'location'):
                        inventory_details['Shop Location'] = inv_item.shop.location
                    
                    if total_quantity_sold > 0:
                        inventory_details['Original Quantity'] = f'{initial_inventory} {product.weight_unit}'
                        inventory_details['Total Sold'] = f'{total_quantity_sold} {product.weight_unit}'
                        inventory_details['Sales Count'] = order_items.count()
                    
                    timeline.append({
                        'stage': 'Current Inventory Status',
                        'category': 'shop',
                        'timestamp': inv_item.updated_at if hasattr(inv_item, 'updated_at') and inv_item.updated_at else product.created_at,
                        'location': inv_item.shop.name if inv_item.shop else 'Shop',
                        'actor': 'Inventory System',
                        'action': f'Current stock level: {inv_item.quantity if hasattr(inv_item, "quantity") else "Unknown"} {product.weight_unit}',
                        'icon': 'fa-warehouse',
                        'details': inventory_details
                    })
        
        # Sort timeline chronologically
        timeline.sort(key=lambda x: x['timestamp'])
        
        # Get related data
        inventory_items = product.inventory.select_related('shop').all()
        receipts = product.receipts.select_related('shop').order_by('-received_at')
        order_items = product.orderitem_set.select_related('order', 'order__customer', 'order__shop').order_by('-order__created_at')
        
        # Carcass measurements
        carcass_measurement = None
        if product.animal and hasattr(product.animal, 'carcass_measurement'):
            cm = product.animal.carcass_measurement
            if hasattr(cm, 'get_all_measurements'):
                carcass_measurement = cm.get_all_measurements()
        
        # Create product_info object that matches template expectations
        product_info = {
            'product': product,
            'product_name': product.name,
            'batch_number': product.batch_number,
            'product_type': product.product_type,
            'quantity': product.quantity,
            'weight_unit': product.weight_unit,
            'price': product.price if hasattr(product, 'price') and product.price else '0.00',
            'timeline_events': timeline,
            'inventory_count': inventory_items.count(),
            'orders_count': order_items.count(),
        }
        
        context = {
            'product_infos': [product_info],  # Wrap in list to match template expectation
            'product': product,
            'animal': product.animal,
            'timeline': timeline,
            'inventory_items': inventory_items,
            'receipts': receipts,
            'order_items': order_items,
            'carcass_measurement': carcass_measurement,
            'inventory_count': inventory_items.count(),
            'receipts_count': receipts.count(),
            'orders_count': order_items.count(),
            'qr_code_url': product.qr_code,
            'total_inventory': inventory_items.count(),
            'total_orders': order_items.count(),
        }
        
    except Product.DoesNotExist:
        context = {
            'error': 'Product not found',
            'product': None,
            'product_infos': [],
            'timeline': []
        }
    except Exception as e:
        context = {
            'error': f'Error loading product: {str(e)}',
            'product': None,
            'product_infos': [],
            'timeline': []
        }
    
    return render(request, 'meat_trace/product_info.html', context)


@login_required
def product_info_list_view(request):
    try:
        from meat_trace.models import ProductInfo, Product
        
        # Get or create ProductInfo for all products
        product_infos = ProductInfo.objects.select_related('product').all()[:50]
        
        # If no ProductInfo exists, create them
        if not product_infos.exists():
            products = Product.objects.all()[:50]
            for product in products:
                try:
                    # Check if ProductInfo exists
                    if not hasattr(product, 'info'):
                        # Create ProductInfo with required fields from product
                        product_info = ProductInfo(
                            product=product,
                            product_name=product.name or 'Unnamed Product',
                            product_type=product.product_type,
                            batch_number=product.batch_number or 'BATCH001',
                            quantity=product.quantity or 0
                        )
                        product_info.save()
                        # Now update with full details
                        product_info.update_from_product()
                    else:
                        # Update existing ProductInfo if timeline is empty
                        product_info = product.info
                        if not product_info.timeline_events:
                            product_info.update_from_product()
                except Exception as e:
                    print(f"Error creating ProductInfo for product {product.id}: {e}")
                    pass
            product_infos = ProductInfo.objects.select_related('product').all()[:50]
        
        # Calculate summary statistics
        total_inventory = sum(info.inventory_count for info in product_infos)
        total_orders = sum(info.orders_count for info in product_infos)
        
        # Get unique processing units
        processing_units = set()
        for info in product_infos:
            if info.processing_unit_name:
                processing_units.add(info.processing_unit_name)
        
        context = {
            'product_infos': product_infos,
            'total_inventory': total_inventory,
            'total_orders': total_orders,
            'total_processing_units': len(processing_units),
        }
        
    except Exception as e:
        context = {
            'product_infos': [],
            'error': f'Error loading products: {str(e)}',
            'total_inventory': 0,
            'total_orders': 0,
            'total_processing_units': 0,
        }
    
    return render(request, 'meat_trace/product_info_list.html', context)


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
        user_role = get_user_role(user)
        if user_role != ROLE_PROCESSOR:
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
    # Default empty pipeline structure
    empty_pipeline = {
        'pipeline': {
            'stages': [],
            'total_pending': 0
        }
    }
    
    try:
        user = request.user
        profile = user.profile

        # Only processing unit users can see pipeline data
        user_role = get_user_role(user)
        import logging
        logger = logging.getLogger(__name__)

        if user_role != ROLE_PROCESSOR:
            logger.info(f"[PROCESSING_PIPELINE] User {user.username} has role '{getattr(profile, 'role', None)}' which is not a processing unit role - returning empty pipeline")
            return Response(empty_pipeline)

        # Get user's processing units
        from .models import ProcessingUnitUser
        user_processing_units = ProcessingUnitUser.objects.filter(
            user=user,
            is_active=True,
            is_suspended=False
        ).values_list('processing_unit_id', flat=True)

        if not user_processing_units:
            return Response(empty_pipeline)

        # Calculate pipeline stages
        pipeline_data = {
            'stages': [],
            'total_pending': 0
        }

        # Stage 1: Receive - Animals transferred to processing unit but not received yet
        # Excludes rejected animals
        receive_count = Animal.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=True,
            rejection_status__isnull=True  # Exclude rejected animals
        ).count()

        # Stage 2: Inspect - Animals received but no carcass measurement taken yet
        # This is the inspection phase where processor evaluates the carcass
        from .models import CarcassMeasurement
        
        # Get animals that are received but don't have carcass measurements
        received_animal_ids = Animal.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=False,
            rejection_status__isnull=True  # Exclude rejected animals
        ).values_list('id', flat=True)
        
        # Get animals that have carcass measurements
        animals_with_measurements = CarcassMeasurement.objects.filter(
            animal_id__in=received_animal_ids
        ).values_list('animal_id', flat=True)
        
        # Inspect = received but no carcass measurement
        inspect_count = len(received_animal_ids) - len(animals_with_measurements)

        # Stage 3: Process - Animals with carcass measurement but no products created yet
        # These animals have been inspected and are being processed into products
        animals_with_products = Product.objects.filter(
            processing_unit_id__in=user_processing_units,
            animal_id__isnull=False
        ).values_list('animal_id', flat=True).distinct()
        
        # Process = has carcass measurement but no products yet
        process_count = len([aid for aid in animals_with_measurements if aid not in animals_with_products])

        # Stage 4: Stock - Products created and in inventory (not transferred to shops)
        stock_count = Product.objects.filter(
            processing_unit_id__in=user_processing_units,
            transferred_to__isnull=True  # Not transferred out to shops
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
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[PROCESSING_PIPELINE] Error fetching pipeline data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Return empty but valid pipeline structure on error
        return Response({
            'pipeline': {
                'stages': [],
                'total_pending': 0
            }
        })


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
            # Return paginated-style response for Flutter app compatibility
            return Response({
                'results': serializer.data,
                'count': len(serializer.data)
            })
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
            user_role = get_user_role(user)
            
            # Admin can see all measurements
            if user_role == ROLE_ADMIN:
                return CarcassMeasurement.objects.all()
            
            # Processor can see measurements for animals in their processing unit
            elif user_role == ROLE_PROCESSOR:
                if profile.processing_unit:
                    # Get animals that belong to the processor's unit
                    from .models import Product
                    animal_ids = Product.objects.filter(
                        processing_unit=profile.processing_unit
                    ).values_list('animal_id', flat=True).distinct()
                    return CarcassMeasurement.objects.filter(animal_id__in=animal_ids)
                return CarcassMeasurement.objects.none()
            
            # Farmer can see measurements for their own animals
            elif user_role == ROLE_FARMER:
                return CarcassMeasurement.objects.filter(animal__farmer=user)
            
            # Shop owners can see measurements for animals they've purchased
            elif user_role == ROLE_SHOPOWNER:
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
                animal.slaughtered_at = timezone.now()
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
                animal.slaughtered_at = timezone.now()
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
            user_role = get_user_role(user)
            
            # Admin can see all activities
            if user_role == ROLE_ADMIN:
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
            user_role = get_user_role(user)
            
            # Admin can see all profiles
            if user_role == ROLE_ADMIN:
                return UserProfile.objects.all()
            
            # Processor can see profiles in their processing unit
            elif user_role == ROLE_PROCESSOR:
                if profile.processing_unit:
                    unit_user_ids = ProcessingUnitUser.objects.filter(
                        processing_unit=profile.processing_unit
                    ).values_list('user_id', flat=True)
                    return UserProfile.objects.filter(user_id__in=unit_user_ids)
                return UserProfile.objects.filter(user=user)
            
            # Shop owners can see profiles in their shop
            elif user_role == ROLE_SHOPOWNER:
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
            user_role = get_user_role(user)
            
            # Admin can see all requests
            if user_role == ROLE_ADMIN:
                return JoinRequest.objects.all().order_by('-created_at')
            
            # Processor can see requests for their processing unit
            elif user_role == ROLE_PROCESSOR:
                if profile.processing_unit:
                    return JoinRequest.objects.filter(
                        processing_unit=profile.processing_unit
                    ).order_by('-created_at')
                return JoinRequest.objects.filter(user=user).order_by('-created_at')
            
            # Shop owners can see requests for their shop
            elif user_role == ROLE_SHOPOWNER:
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
            user_role = get_user_role(user)
            
            # Admin can see all shops
            if user_role == ROLE_ADMIN:
                return Shop.objects.all()
            
            # Shop owners can see their own shop(s)
            elif user_role == ROLE_SHOPOWNER:
                # Get all shops where user is an active member
                user_shop_ids = ShopUser.objects.filter(
                    user=user,
                    is_active=True
                ).values_list('shop_id', flat=True)
                
                if user_shop_ids:
                    return Shop.objects.filter(id__in=user_shop_ids)
                elif profile.shop:
                    # Fallback to profile.shop
                    return Shop.objects.filter(id=profile.shop.id)
                return Shop.objects.none()
            
            # Processors and Farmers can see all shops (for browsing/selecting transfer destinations)
            elif user_role in [ROLE_PROCESSOR, ROLE_FARMER]:
                return Shop.objects.all()
            
            # Default deny for unknown roles
            return Shop.objects.none()
            
        except UserProfile.DoesNotExist:
            # Security: deny access if no profile exists
            return Shop.objects.none()

    @action(detail=False, methods=['post'], url_path='register', permission_classes=[IsAuthenticated])
    def register(self, request):
        """
        Register/create a new shop for the current authenticated user.
        The user will be assigned as the owner with admin permissions.
        """
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[SHOP_VIEWSET] Creating new shop for user {request.user.username}")
            
            user = request.user
            data = request.data
            
            # Validate required fields
            name = data.get('name')
            if not name:
                return Response(
                    {'error': 'Shop name is required'},
                    status=status_module.HTTP_400_BAD_REQUEST
                )
            
            # Check if user already owns a shop
            try:
                profile = user.profile
                user_role = get_user_role(user)
                if profile.shop and user_role == ROLE_SHOPOWNER:
                    return Response(
                        {'error': 'You already own a shop. You cannot create another one.'},
                        status=status_module.HTTP_400_BAD_REQUEST
                    )
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                profile = UserProfile.objects.create(user=user, role=ROLE_SHOPOWNER)
            
            # Create the shop
            shop = Shop.objects.create(
                name=name,
                description=data.get('description', ''),
                location=data.get('location', ''),
                contact_email=data.get('contact_email', user.email),
                contact_phone=data.get('contact_phone', ''),
                business_license=data.get('business_license', ''),
                tax_id=data.get('tax_id', ''),
                is_active=True
            )
            logger.info(f"[SHOP_VIEWSET] Created Shop ID {shop.id}")
            
            # Create ShopUser membership for owner
            shop_user = ShopUser.objects.create(
                user=user,
                shop=shop,
                role='owner',
                permissions='admin',
                is_active=True,
                invited_by=user,
                invited_at=timezone.now(),
                joined_at=timezone.now()
            )
            logger.info(f"[SHOP_VIEWSET] Created ShopUser owner membership ID {shop_user.id}")
            
            # Update user profile
            profile.shop = shop
            profile.role = ROLE_SHOPOWNER
            profile.save()
            logger.info(f"[SHOP_VIEWSET] Updated user profile with Shop ID {shop.id}")
            
            # Return shop data
            serializer = self.get_serializer(shop)
            return Response(serializer.data, status=status_module.HTTP_201_CREATED)
            
        except Exception as e:
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"[SHOP_VIEWSET] Error creating shop: {e}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status_module.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
            from .models import ShopUser, UserProfile
            shop_members = ShopUser.objects.filter(shop=shop).select_related('user', 'invited_by')
            
            logger.info(f"[SHOP_VIEWSET] ShopUser count: {shop_members.count()}")
            
            # Serialize member data
            members_data = []
            user_ids_added = set()  # Track which users we've already added
            
            # First, add shop owners from UserProfile (they might not have ShopUser records)
            shop_owners = UserProfile.objects.filter(
                shop=shop,
                role='shop'
            ).select_related('user')
            
            logger.info(f"[SHOP_VIEWSET] UserProfile owners count: {shop_owners.count()}")
            
            for profile in shop_owners:
                logger.info(f"[SHOP_VIEWSET] Processing profile: user={profile.user}, role={profile.role}")
                if profile.user and profile.user.id not in user_ids_added:
                    # Check if they have a ShopUser record
                    shop_user = shop_members.filter(user=profile.user).first()
                    
                    if shop_user:
                        # They have a ShopUser record, we'll add them later
                        logger.info(f"[SHOP_VIEWSET] User {profile.user.username} has ShopUser record, skipping profile-based add")
                        continue
                    
                    # Add shop owner without ShopUser record
                    logger.info(f"[SHOP_VIEWSET] Adding profile-based owner: {profile.user.username}")
                    member_dict = {
                        'id': -1,  # Use -1 to indicate profile-based owner (not a ShopUser record)
                        'user_id': profile.user.id or 0,
                        'username': profile.user.username or '',
                        'email': profile.user.email or '',
                        'shop_id': shop.id,
                        'shop_name': shop.name,
                        'role': 'owner',
                        'permissions': 'admin',
                        'is_active': True,
                        'is_suspended': False,
                        'joined_at': profile.created_at.isoformat() if profile.created_at else None,
                        'invited_at': profile.created_at.isoformat() if profile.created_at else timezone.now().isoformat(),
                        'invited_by_id': None,
                        'invited_by_username': None,
                    }
                    members_data.append(member_dict)
                    user_ids_added.add(profile.user.id)
            
            # Then add all ShopUser members (including owners who have ShopUser records)
            for shop_user in shop_members:
                logger.info(f"[SHOP_VIEWSET] Processing ShopUser: user={shop_user.user}, role={shop_user.role}")
                if shop_user.user and shop_user.user.id not in user_ids_added:
                    logger.info(f"[SHOP_VIEWSET] Adding ShopUser member: {shop_user.user.username}")
                    member_dict = {
                        'id': shop_user.id or 0,
                        'user_id': shop_user.user.id or 0,
                        'username': shop_user.user.username or '',
                        'email': shop_user.user.email or '',
                        'shop_id': shop.id,
                        'shop_name': shop.name,
                        'role': shop_user.role or 'salesperson',
                        'permissions': shop_user.permissions or 'write',
                        'is_active': shop_user.is_active if shop_user.is_active is not None else True,
                        'is_suspended': False,  # Add this field - you may want to add this to your ShopUser model
                        'joined_at': shop_user.joined_at.isoformat() if shop_user.joined_at else None,
                        'invited_at': shop_user.invited_at.isoformat() if shop_user.invited_at else timezone.now().isoformat(),
                        'invited_by_id': shop_user.invited_by.id if shop_user.invited_by else None,
                        'invited_by_username': shop_user.invited_by.username if shop_user.invited_by else None,
                    }
                    members_data.append(member_dict)
                    user_ids_added.add(shop_user.user.id)
                else:
                    if shop_user.user:
                        logger.info(f"[SHOP_VIEWSET] Skipping duplicate user: {shop_user.user.username}")
                    else:
                        logger.warning(f"[SHOP_VIEWSET] ShopUser {shop_user.id} has no associated user!")
            
            # Sort by role (owners first) then by username
            role_priority = {'owner': 0, 'manager': 1, 'salesperson': 2, 'cashier': 3, 'inventory_clerk': 4}
            members_data.sort(key=lambda x: (role_priority.get(x['role'], 999), x.get('username', '')))
            
            logger.info(f"[SHOP_VIEWSET] Found {len(members_data)} members (including {len(shop_owners)} owner(s))")
            logger.info(f"[SHOP_VIEWSET] Members data: {members_data}")
            
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
            user_role = get_user_role(user)
            
            # Admin can see all orders
            if user_role == ROLE_ADMIN:
                return Order.objects.all().order_by('-created_at')
            
            # Shop owners can see orders for their shop
            elif user_role == ROLE_SHOPOWNER:
                if profile.shop:
                    return Order.objects.filter(shop=profile.shop).order_by('-created_at')
                return Order.objects.none()
            
            # Processor can see orders related to their processing unit
            elif user_role == ROLE_PROCESSOR:
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
            user_role = get_user_role(user)
            
            # Admin can see all products
            if user_role == ROLE_ADMIN:
                return Product.objects.all().order_by('-created_at')
            
            # Processor can see products from their processing unit
            elif user_role == ROLE_PROCESSOR:
                if profile.processing_unit:
                    return Product.objects.filter(
                        processing_unit=profile.processing_unit
                    ).order_by('-created_at')
                return Product.objects.none()
            
            # Shop owners can see products transferred to OR received by their shop(s)
            elif user_role == ROLE_SHOPOWNER:
                # Get all shops where user is an active member via ShopUser
                user_shop_ids = ShopUser.objects.filter(
                    user=user,
                    is_active=True
                ).values_list('shop_id', flat=True)
                
                if user_shop_ids:
                    # Return products transferred to or received by any of the user's shops
                    queryset = Product.objects.filter(
                        Q(transferred_to__id__in=user_shop_ids) | Q(received_by_shop__id__in=user_shop_ids)
                    ).order_by('-created_at')
                    
                    # If pending_receipt parameter is provided, filter further
                    pending_receipt = self.request.query_params.get('pending_receipt')
                    if pending_receipt and pending_receipt.lower() == 'true':
                        # Only show products transferred to shop but not fully received yet
                        queryset = queryset.filter(
                            transferred_to__id__in=user_shop_ids,
                            rejection_status__isnull=True  # Not fully rejected
                        ).exclude(
                            Q(quantity_received__gte=models.F('quantity')) |  # Not fully received
                            Q(quantity_rejected__gte=models.F('quantity'))   # Not fully rejected
                        )
                    
                    return queryset
                
                # Fallback to profile.shop if no ShopUser memberships exist
                if profile.shop:
                    # Show products transferred to this shop OR already received by this shop
                    # Filter by pending_receipt query param if provided
                    queryset = Product.objects.filter(
                        Q(transferred_to=profile.shop) | Q(received_by_shop=profile.shop)
                    ).order_by('-created_at')
                    
                    # If pending_receipt parameter is provided, filter further
                    pending_receipt = self.request.query_params.get('pending_receipt')
                    if pending_receipt and pending_receipt.lower() == 'true':
                        # Only show products transferred to shop but not fully received yet
                        queryset = queryset.filter(
                            transferred_to=profile.shop,
                            rejection_status__isnull=True  # Not fully rejected
                        ).exclude(
                            Q(quantity_received__gte=models.F('quantity')) |  # Not fully received
                            Q(quantity_rejected__gte=models.F('quantity'))   # Not fully rejected
                        )
                    
                    return queryset
                
                return Product.objects.none()
            
            # Farmer can see products from their animals
            elif user_role == ROLE_FARMER:
                return Product.objects.filter(animal__farmer=user).order_by('-created_at')
            
            # Default deny for unknown roles
            return Product.objects.none()
            
        except UserProfile.DoesNotExist:
            # Security: deny access if no profile exists
            return Product.objects.none()

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
            
            # SECURITY FIX: Verify user is actually an active member of the assigned shop
            # This prevents users from receiving products for shops they don't belong to
            if not ShopUser.objects.filter(
                user=request.user,
                shop=user_shop,
                is_active=True
            ).exists():
                return Response(
                    {'error': 'User is not an active member of the assigned shop. Access denied.'},
                    status=status_module.HTTP_403_FORBIDDEN
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
            user_role = get_user_role(user)
            if user_role != ROLE_PROCESSOR:
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
    
    def create(self, request, *args, **kwargs):
        """Override create to add detailed logging"""
        print(f"\n{'='*80}")
        print(f"[SALE_CREATE] User: {request.user.username}")
        print(f"[SALE_CREATE] Request data: {request.data}")
        print(f"[SALE_CREATE] Request method: {request.method}")
        print(f"{'='*80}\n")
        
        try:
            response = super().create(request, *args, **kwargs)
            print(f"[SALE_CREATE] ✅ Success - Status: {response.status_code}")
            print(f"[SALE_CREATE] Response data: {response.data}")
            return response
        except Exception as e:
            print(f"[SALE_CREATE] ❌ Exception occurred: {type(e).__name__}")
            print(f"[SALE_CREATE] Error message: {str(e)}")
            import traceback
            print(f"[SALE_CREATE] Traceback:\n{traceback.format_exc()}")
            raise
    
    def get_queryset(self):
        """Filter sales based on user permissions"""
        user = self.request.user
        
        # First check ShopUser memberships (new system)
        shop_membership = user.shop_memberships.filter(is_active=True).first()
        if shop_membership:
            # ShopUser can see sales from their shop
            return Sale.objects.filter(shop=shop_membership.shop).order_by('-created_at')
        
        # Fall back to UserProfile (old system)
        try:
            profile = user.profile
            user_role = get_user_role(user)
            
            # Admin can see all sales
            if user_role == ROLE_ADMIN:
                return Sale.objects.all().order_by('-created_at')
            
            # Shop owners can see sales from their shop
            elif user_role == ROLE_SHOPOWNER:
                if profile.shop:
                    return Sale.objects.filter(shop=profile.shop).order_by('-created_at')
                return Sale.objects.none()
            
            # Processor can see sales of products from their processing unit
            elif user_role == ROLE_PROCESSOR:
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
        shop = None
        
        print(f"[SALE_PERFORM_CREATE] User: {user.username}")
        
        # Try to get shop from ShopUser first (new system)
        shop_membership = user.shop_memberships.filter(is_active=True).first()
        print(f"[SALE_PERFORM_CREATE] ShopUser membership: {shop_membership}")
        
        if shop_membership:
            shop = shop_membership.shop
            print(f"[SALE_PERFORM_CREATE] Shop from ShopUser: {shop.name} (ID: {shop.id})")
        else:
            # Fall back to UserProfile (old system)
            try:
                profile = user.profile
                print(f"[SALE_PERFORM_CREATE] UserProfile found: {profile.role}")
                if profile.shop:
                    shop = profile.shop
                    print(f"[SALE_PERFORM_CREATE] Shop from UserProfile: {shop.name} (ID: {shop.id})")
            except UserProfile.DoesNotExist:
                print(f"[SALE_PERFORM_CREATE] No UserProfile found")
                pass
        
        if shop:
            print(f"[SALE_PERFORM_CREATE] ✅ Saving sale with shop: {shop.name}, sold_by: {user.username}")
            print(f"[SALE_PERFORM_CREATE] Validated data before save: {serializer.validated_data}")
            serializer.save(shop=shop, sold_by=user)
            print(f"[SALE_PERFORM_CREATE] ✅ Sale saved successfully")
        else:
            print(f"[SALE_PERFORM_CREATE] ❌ No shop found for user")
            raise ValidationError("User is not associated with any shop")

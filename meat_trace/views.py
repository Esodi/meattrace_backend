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

from .models import Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage, ProductTimelineEvent, Inventory, Order, OrderItem, CarcassMeasurement, SlaughterPart, ProcessingUnit, ProcessingUnitUser, Shop, ShopUser, UserAuditLog, JoinRequest, Notification, Activity, SystemAlert, PerformanceMetric, ComplianceAudit, Certification, SystemHealth, SecurityLog, TransferRequest, BackupSchedule, Sale, SaleItem, RejectionReason, ShopSettings, Invoice, InvoiceItem, InvoicePayment
from .abbatoir_dashboard_serializer import AbbatoirDashboardSerializer
from .serializers import AnimalSerializer, ProductSerializer, OrderSerializer, ShopSerializer, SlaughterPartSerializer, ActivitySerializer, ProcessingUnitSerializer, JoinRequestSerializer, ProductCategorySerializer, CarcassMeasurementSerializer, SaleSerializer, SaleItemSerializer, NotificationSerializer, UserProfileSerializer, ShopSettingsSerializer, InvoiceSerializer, InvoiceCreateSerializer, InvoiceItemSerializer, InvoicePaymentSerializer, ReceiptSerializer
from .utils.rejection_service import RejectionService
from .role_utils import normalize_role, ROLE_ABBATOIR, ROLE_PROCESSOR, ROLE_SHOPOWNER, ROLE_ADMIN
from .utils.pdf_utils import download_pdf_response


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
        queryset = Animal.objects.all().select_related('abbatoir', 'transferred_to', 'received_by')

        # Farmers see their own animals
        if hasattr(user, 'profile') and normalize_role(user.profile.role) == ROLE_ABBATOIR:
            queryset = queryset.filter(abbatoir=user)

        # ProcessingUnit users see animals transferred to ANY processing unit they belong to
        elif hasattr(user, 'profile') and normalize_role(user.profile.role) == ROLE_PROCESSOR:
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
        """Set the abbatoir to the current user when creating an animal"""
        serializer.save(abbatoir=self.request.user)

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
                        abbatoir=request.user,
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
                            animal__abbatoir=request.user,
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
            abbatoir=request.user,
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

        # Abbatoirs see parts from their own animals
        if hasattr(user, 'profile') and normalize_role(user.profile.role) == ROLE_ABBATOIR:
            queryset = queryset.filter(animal__abbatoir=user)

        # ProcessingUnit users see parts transferred to or received by them
        elif hasattr(user, 'profile') and normalize_role(user.profile.role) == ROLE_PROCESSOR:
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
def public_processing_units_for_registration(request):
    """Public endpoint to list processing units for user registration flow."""
    try:
        units = ProcessingUnit.objects.all().values('id', 'name')[:200]
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
            jr = JoinRequest.objects.select_related('shop', 'processing_unit', 'user').get(id=request_id)
            user = request.user

            if not (user.is_superuser or user.is_staff):
                can_view = jr.user_id == user.id

                if not can_view and jr.shop_id:
                    can_view = ShopUser.objects.filter(
                        user=user,
                        shop_id=jr.shop_id,
                        is_active=True
                    ).exists()

                if not can_view and jr.processing_unit_id:
                    can_view = ProcessingUnitUser.objects.filter(
                        user=user,
                        processing_unit_id=jr.processing_unit_id,
                        is_active=True,
                        is_suspended=False
                    ).exists()

                if not can_view:
                    return Response({'error': 'forbidden'}, status=status_module.HTTP_403_FORBIDDEN)

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
    """General dashboard endpoint returning basic system info and welcome message."""
    user = request.user
    role = getattr(user.profile, 'role', 'User')
    
    return Response({
        'message': f'Welcome to MeatTrace, {user.first_name or user.username}!',
        'role': role,
        'system': 'MeatTrace Traceability Platform',
        'timestamp': timezone.now().isoformat()
    })


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
        user = request.user
        acts = Activity.objects.select_related('user').order_by('-created_at')

        if user.is_superuser or user.is_staff:
            data = ActivitySerializer(acts[:50], many=True).data
            return Response({'activities': data})

        try:
            role = normalize_role(user.profile.role)
        except UserProfile.DoesNotExist:
            role = None

        if role == ROLE_ADMIN:
            scoped = acts
        elif role == ROLE_SHOPOWNER:
            shop_ids = _get_user_shop_ids(user)
            if shop_ids:
                scoped = acts.filter(
                    Q(user=user) |
                    Q(user__shop_memberships__shop_id__in=shop_ids, user__shop_memberships__is_active=True) |
                    Q(user__profile__shop_id__in=shop_ids)
                ).distinct()
            else:
                scoped = acts.filter(user=user)
        elif role == ROLE_PROCESSOR:
            unit_ids = _get_user_processing_unit_ids(user)
            if unit_ids:
                scoped = acts.filter(
                    Q(user=user) |
                    Q(
                        user__processing_unit_memberships__processing_unit_id__in=unit_ids,
                        user__processing_unit_memberships__is_active=True,
                        user__processing_unit_memberships__is_suspended=False
                    ) |
                    Q(user__profile__processing_unit_id__in=unit_ids)
                ).distinct()
            else:
                scoped = acts.filter(user=user)
        else:
            scoped = acts.filter(user=user)

        acts = scoped[:50]
        data = ActivitySerializer(acts, many=True).data
    except Exception:
        data = []
    return Response({'activities': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def abbatoir_dashboard(request):
    # Return a small serialized payload compatible with abbatoir dashboard
    try:
        serializer = AbbatoirDashboardSerializer({'user': request.user})
        data = serializer.data
    except Exception:
        data = {}
    return Response(data)


def _get_user_shop_ids(user):
    """Resolve all active shop IDs associated with a user across old/new membership models."""
    shop_ids = set()

    # New model: ShopUser memberships
    try:
        shop_ids.update(
            user.shop_memberships.filter(is_active=True).values_list('shop_id', flat=True)
        )
    except Exception:
        pass

    # Legacy model: UserProfile.shop
    try:
        if user.profile.shop_id:
            shop_ids.add(user.profile.shop_id)
    except UserProfile.DoesNotExist:
        pass

    return shop_ids


def _get_user_processing_unit_ids(user):
    """Resolve all active processing unit IDs associated with a user."""
    unit_ids = set()

    try:
        unit_ids.update(
            user.processing_unit_memberships.filter(
                is_active=True,
                is_suspended=False
            ).values_list('processing_unit_id', flat=True)
        )
    except Exception:
        pass

    try:
        if user.profile.processing_unit_id:
            unit_ids.add(user.profile.processing_unit_id)
    except UserProfile.DoesNotExist:
        pass

    return unit_ids


def _can_access_sale_for_user(user, sale):
    """Check whether the current user is allowed to access a sale detail page."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    shop_ids = _get_user_shop_ids(user)
    if shop_ids and sale.shop_id in shop_ids:
        return True

    try:
        profile = user.profile
        role = normalize_role(profile.role)

        if role == ROLE_ADMIN:
            return True

        if role == ROLE_PROCESSOR and profile.processing_unit_id:
            return sale.items.filter(
                product__processing_unit_id=profile.processing_unit_id
            ).exists()
    except UserProfile.DoesNotExist:
        pass

    return False


def _can_access_product_for_user(user, product):
    """Check whether the current user is allowed to access a product traceability page."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    shop_ids = _get_user_shop_ids(user)
    if shop_ids:
        if product.received_by_shop_id and product.received_by_shop_id in shop_ids:
            return True
        if product.transferred_to_id and product.transferred_to_id in shop_ids:
            return True

    try:
        profile = user.profile
        role = normalize_role(profile.role)

        if role == ROLE_ADMIN:
            return True

        if role == ROLE_PROCESSOR and profile.processing_unit_id:
            return product.processing_unit_id == profile.processing_unit_id

        if role == ROLE_ABBATOIR and product.animal and product.animal.abbatoir_id == user.id:
            return True
    except UserProfile.DoesNotExist:
        pass

    return False


@login_required
def product_info_view(request, product_id):
    try:
        product = Product.objects.select_related(
            'animal', 'animal__abbatoir', 'processing_unit', 
            'category', 'slaughter_part', 'transferred_to',
            'received_by_shop'
        ).prefetch_related(
            'inventory', 'receipts', 'orderitem_set', 
            'ingredients__slaughter_part',
            'animal__slaughter_parts'
        ).get(id=product_id)

        if not _can_access_product_for_user(request.user, product):
            return render(request, 'meat_trace/product_info.html', {'error': 'Not found'}, status=404)
        
        # Build comprehensive timeline
        timeline = []
        
        # 1. Animal Registration (Farmer Stage)
        if product.animal:
            animal = product.animal
            
            # Get abbatoir contact info
            farmer_details = {
                'Animal ID': animal.animal_id,
                'Animal Name': animal.animal_name or 'Not named',
                'Species': animal.get_species_display(),
                'Gender': animal.get_gender_display() if hasattr(animal, 'gender') else 'Unknown',
                'Age': f'{animal.age} months' if animal.age else 'Not recorded',
                'Live Weight': f'{animal.live_weight} kg' if animal.live_weight else 'Not recorded',
                'Health Status': animal.health_status or 'Not recorded',
                'Breed': animal.breed or 'Not specified',
                'Abbatoir Name': animal.abbatoir.get_full_name() if animal.abbatoir.first_name else animal.abbatoir.username,
                'Abbatoir Email': animal.abbatoir.email or 'Not provided',
                'Notes': animal.notes or 'None'
            }
            
            # Add abbatoir phone if available
            if hasattr(animal.abbatoir, 'profile') and hasattr(animal.abbatoir.profile, 'phone'):
                farmer_details['Abbatoir Phone'] = animal.abbatoir.profile.phone or 'Not provided'
            elif hasattr(animal.abbatoir, 'phone_number'):
                farmer_details['Abbatoir Phone'] = animal.abbatoir.phone_number or 'Not provided'
            
            timeline.append({
                'stage': 'Animal Registration',
                'category': 'abbatoir',
                'timestamp': animal.created_at,
                'location': f'Abbatoir - {animal.abbatoir.username}',
                'actor': animal.abbatoir.get_full_name() if animal.abbatoir.first_name else animal.abbatoir.username,
                'action': f'Animal {animal.animal_id} registered at farm',
                'icon': 'fa-clipboard-list',
                'details': farmer_details
            })
            
            # 2. Animal Transfer to Processing Unit
            if animal.transferred_at and animal.transferred_to:
                transfer_details = {
                    'From': f'Abbatoir - {animal.abbatoir.get_full_name() if animal.abbatoir.first_name else animal.abbatoir.username}',
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
                    'actor': animal.abbatoir.get_full_name() if animal.abbatoir.first_name else animal.abbatoir.username,
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
                            part_value += f' ΓåÆ {part.transferred_to.name}'
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
                    ingredients_list.append(f'{ing.slaughter_part.get_part_type_display()} ({ing.quantity_used} {ing.quantity_unit})')
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
                'Weight Transferred': f'{product.weight} {product.weight_unit}',
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
                'Weight Ordered': f'{product.weight} {product.weight_unit}',
                'Weight Received': f'{product.weight_received} {product.weight_unit}' if hasattr(product, 'weight_received') and product.weight_received else 'Same as ordered',
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
                'Weight Rejected': f'{product.weight_rejected} {product.weight_unit}' if hasattr(product, 'weight_rejected') and product.weight_rejected else f'Full weight ({product.weight} {product.weight_unit})',
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
        total_weight_sold = 0
        remaining_after_sale = 0
        initial_inventory = float(product.weight) if product.weight else 0
        
        order_items = product.orderitem_set.select_related('order', 'order__customer', 'order__shop').order_by('order__created_at')
        
        for idx, item in enumerate(order_items, 1):
            if item.order:
                customer = item.order.customer
                shop = item.order.shop
                order = item.order
                
                # Calculate inventory after this sale
                weight_sold_in_this_order = float(item.weight) if hasattr(item, 'weight') and item.weight else (
                    float(item.quantity) if hasattr(item, 'quantity') and item.quantity else 0
                )
                total_weight_sold += weight_sold_in_this_order
                remaining_after_sale = initial_inventory - total_weight_sold
                
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
                sale_details['Weight Sold This Order'] = f'{item.weight if hasattr(item, "weight") else item.quantity} {product.weight_unit}'
                sale_details['Unit Price'] = f'${item.unit_price}' if hasattr(item, 'unit_price') and item.unit_price else 'N/A'
                sale_details['Subtotal for This Item'] = f'${item.subtotal}' if hasattr(item, 'subtotal') and item.subtotal else f'${float(item.weight if hasattr(item, "weight") and item.weight else item.quantity) * float(item.unit_price) if hasattr(item, "unit_price") and item.unit_price else 0:.2f}'
                sale_details['Order Status'] = order.get_status_display() if hasattr(order, 'get_status_display') else order.status
                
                # Inventory Tracking
                sale_details['---Inventory Status---'] = '---'
                sale_details['Initial Product Weight'] = f'{initial_inventory} {product.weight_unit}'
                sale_details['Total Sold Up To Now'] = f'{total_weight_sold} {product.weight_unit}'
                sale_details['Remaining After This Sale'] = f'{remaining_after_sale} {product.weight_unit}'
                sale_details['Percentage Sold'] = f'{(total_weight_sold / initial_inventory * 100):.1f}%' if initial_inventory > 0 else 'N/A'
                
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
                    'action': f'Sold {item.weight if hasattr(item, "weight") and item.weight else item.quantity} {product.weight_unit} to {customer.get_full_name() if customer and customer.first_name else (customer.username if customer else "walk-in customer")}',
                    'icon': 'fa-shopping-cart',
                    'details': sale_details
                })
        
        timeline.extend(sales)
        
        # 11. Current Inventory Status (if product still has remaining stock)
        if remaining_after_sale > 0 or total_weight_sold == 0:
            current_inventory_items = product.inventory.select_related('shop').all()
            
            if current_inventory_items.exists():
                for inv_item in current_inventory_items:
                    inventory_details = {
                        'Shop Name': inv_item.shop.name if inv_item.shop else 'Unknown',
                        'Current Stock': f'{inv_item.weight} {product.weight_unit}' if hasattr(inv_item, 'weight') else 'Unknown',
                        'Stock Status': 'In Stock' if (hasattr(inv_item, 'weight') and inv_item.weight > 0) else 'Out of Stock',
                        'Last Updated': inv_item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(inv_item, 'updated_at') and inv_item.updated_at else 'Not tracked',
                    }
                    
                    if hasattr(inv_item.shop, 'location'):
                        inventory_details['Shop Location'] = inv_item.shop.location
                    
                    if total_weight_sold > 0:
                        inventory_details['Original Weight'] = f'{initial_inventory} {product.weight_unit}'
                        inventory_details['Total Sold'] = f'{total_weight_sold} {product.weight_unit}'
                        inventory_details['Sales Count'] = order_items.count()
                    
                    timeline.append({
                        'stage': 'Current Inventory Status',
                        'category': 'shop',
                        'timestamp': inv_item.updated_at if hasattr(inv_item, 'updated_at') and inv_item.updated_at else product.created_at,
                        'location': inv_item.shop.name if inv_item.shop else 'Shop',
                        'actor': 'Inventory System',
                        'action': f'Current stock level: {inv_item.weight if hasattr(inv_item, "weight") else "Unknown"} {product.weight_unit}',
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
            'quantity': product.weight,
            'weight': product.weight,
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

        user = request.user
        product_queryset = Product.objects.none()

        if user.is_superuser or user.is_staff:
            product_queryset = Product.objects.all()
        else:
            try:
                role = normalize_role(user.profile.role)
            except UserProfile.DoesNotExist:
                role = None

            if role == ROLE_ADMIN:
                product_queryset = Product.objects.all()
            elif role == ROLE_SHOPOWNER:
                shop_ids = _get_user_shop_ids(user)
                if shop_ids:
                    product_queryset = Product.objects.filter(
                        Q(transferred_to_id__in=shop_ids) | Q(received_by_shop_id__in=shop_ids)
                    )
            elif role == ROLE_PROCESSOR:
                unit_ids = _get_user_processing_unit_ids(user)
                if unit_ids:
                    product_queryset = Product.objects.filter(processing_unit_id__in=unit_ids)
            elif role == ROLE_ABBATOIR:
                product_queryset = Product.objects.filter(animal__abbatoir=user)

        # Get or create ProductInfo only for products visible to this user
        product_infos = ProductInfo.objects.select_related('product').filter(product__in=product_queryset).distinct()[:50]
        
        # If no ProductInfo exists, create them
        if not product_infos.exists():
            products = product_queryset[:50]
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
                            quantity=product.weight or 0
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
    sale = get_object_or_404(Sale, id=sale_id)

    if not _can_access_sale_for_user(request.user, sale):
        return render(request, 'sale_info/view.html', {'sale': None}, status=404)

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

        # RECEIVED: Count whole animals + slaughter parts received by this unit
        # (Animals/parts where transferred_to matches user's unit and received_by is NOT NULL)
        received_whole_animals = Animal.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=False
        ).count()
        
        received_slaughter_parts = SlaughterPart.objects.filter(
            transferred_to_id__in=user_processing_units,
            received_by__isnull=False
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
def traceability_report_view(request):
    """Return traceability report for processing unit.
    
    Aggregates data from:
    1. Animals received (whole carcasses)
    2. SlaughterParts received (partial carcasses)
    
    Calculates yield based on products created from these inputs.
    """
    user = request.user
    
    # Get filters
    species_filter = request.query_params.get('species')
    search_query = request.query_params.get('search')
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    
    # 1. Fetch Animals received by this user
    animals_query = Q(received_by=user)
    if species_filter:
        animals_query &= Q(species__iexact=species_filter)
    if search_query:
        animals_query &= (Q(animal_id__icontains=search_query) | Q(animal_name__icontains=search_query))
    if date_from:
        animals_query &= Q(received_at__gte=date_from)
    if date_to:
        animals_query &= Q(received_at__lte=date_to)
        
    received_animals = Animal.objects.filter(animals_query).select_related('abbatoir')
    
    # 2. Fetch SlaughterParts received by this user
    parts_query = Q(received_by=user)
    # SlaughterPart doesn't have species directly, we access via animal
    if species_filter:
        parts_query &= Q(animal__species__iexact=species_filter)
    if search_query:
        parts_query &= (Q(part_id__icontains=search_query) | Q(animal__animal_id__icontains=search_query))
    if date_from:
        parts_query &= Q(received_at__gte=date_from)
    if date_to:
        parts_query &= Q(received_at__lte=date_to)
        
    received_parts = SlaughterPart.objects.filter(parts_query).select_related('animal', 'animal__abbatoir')

    items = []
    
    # Process Animals
    for animal in received_animals:
        # Calculate derived products
        products = Product.objects.filter(animal=animal)
        processed_weight = sum(p.weight for p in products if p.weight)
        
        initial_weight = animal.live_weight if animal.live_weight else 0.0
        # Use simple default if weights are missing to avoid division by zero
        if initial_weight <= 0:
            initial_weight = 1.0 
            
        remaining_weight = animal.remaining_weight if animal.remaining_weight is not None else 0.0
        
        utilization_rate = 0.0
        if initial_weight > 0:
            utilization_rate = (processed_weight / initial_weight) * 100
            
        # Utilization history (products created)
        history = []
        for p in products:
            history.append({
                'name': p.name,
                'batch_number': p.batch_number,
                'weight': float(p.weight) if p.weight else 0.0,
                'weight_unit': p.weight_unit or 'kg',
                'formatted_date': p.created_at.strftime("%b %d, %Y") if p.created_at else "",
                'transferred_to': p.transferred_to.name if p.transferred_to else None
            })
            
        items.append({
            'item_id': animal.animal_id,
            'name': f"{animal.species} (Whole)",
            'species': animal.species or 'Unknown',
            'origin': animal.abbatoir.username if animal.abbatoir else "Unknown Source",
            'initial_weight': float(initial_weight),
            'remaining_weight': float(remaining_weight),
            'processed_weight': float(processed_weight),
            'utilization_rate': float(utilization_rate),
            'received_at': animal.received_at.isoformat() if animal.received_at else timezone.now().isoformat(),
            'formatted_received_date': animal.received_at.strftime("%b %d, %Y") if animal.received_at else "Unknown",
            'utilization_history': history
        })

    # Process Parts
    for part in received_parts:
        # Calculate derived products
        products = Product.objects.filter(slaughter_part=part)
        processed_weight = sum(p.weight for p in products if p.weight)
        
        initial_weight = part.weight if part.weight else 1.0
        remaining_weight = part.remaining_weight if part.remaining_weight is not None else 0.0
        
        utilization_rate = 0.0
        if initial_weight > 0:
            utilization_rate = (processed_weight / initial_weight) * 100
            
         # Utilization history
        history = []
        for p in products:
            history.append({
                'name': p.name,
                'batch_number': p.batch_number,
                'weight': float(p.weight) if p.weight else 0.0,
                'weight_unit': p.weight_unit or 'kg',
                'formatted_date': p.created_at.strftime("%b %d, %Y") if p.created_at else "",
                'transferred_to': p.transferred_to.name if p.transferred_to else None
            })

        items.append({
            'item_id': f"{part.animal.animal_id}-{part.part_type}",
            'name': f"{part.part_type} (Part)",
            'species': part.animal.species if part.animal else 'Unknown',
            'origin': part.animal.abbatoir.username if part.animal and part.animal.abbatoir else "Unknown Source",
            'initial_weight': float(initial_weight),
            'remaining_weight': float(remaining_weight),
            'processed_weight': float(processed_weight),
            'utilization_rate': float(utilization_rate),
            'received_at': part.received_at.isoformat() if part.received_at else timezone.now().isoformat(),
            'formatted_received_date': part.received_at.strftime("%b %d, %Y") if part.received_at else "Unknown",
            'utilization_history': history
        })

    return Response({
        'traceability': {
            'items': items,
            'total': len(items),
            'message': 'Report generated successfully'
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def public_sale_receipt_api(request, receipt_uuid):
    """Public endpoint to view sale receipt by UUID."""
    from .models import Sale
    try:
        sale = Sale.objects.get(receipt_uuid=receipt_uuid)
        return Response({
            'sale_id': sale.id,
            'receipt_uuid': str(sale.receipt_uuid),
            'total': str(sale.total_amount) if hasattr(sale, 'total_amount') else '0',
            'created_at': sale.created_at.isoformat() if sale.created_at else None,
            'items': []
        })
    except Sale.DoesNotExist:
        return Response({'error': 'Receipt not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


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
        # Accept canonical role 'processing_unit' and tolerate legacy/capitalized variants
        import logging
        logger = logging.getLogger(__name__)

        allowed_roles = ('processing_unit', 'Processor', 'processor')
        if profile.role not in allowed_roles:
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
            user = request.user

            if user.is_superuser or user.is_staff:
                queryset = ProcessingUnit.objects.all()
            else:
                role = None
                try:
                    role = normalize_role(user.profile.role)
                except UserProfile.DoesNotExist:
                    pass

                if role == ROLE_ADMIN:
                    queryset = ProcessingUnit.objects.all()
                else:
                    unit_ids = _get_user_processing_unit_ids(user)
                    queryset = ProcessingUnit.objects.filter(id__in=unit_ids) if unit_ids else ProcessingUnit.objects.none()

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
            
            user = request.user
            if not (user.is_superuser or user.is_staff):
                role = None
                try:
                    role = normalize_role(user.profile.role)
                except UserProfile.DoesNotExist:
                    pass

                if role != ROLE_ADMIN:
                    # Only processing unit owners/managers can view unit join requests
                    can_view = ProcessingUnitUser.objects.filter(
                        user=user,
                        processing_unit=processing_unit,
                        is_active=True,
                        is_suspended=False,
                        role__in=['owner', 'manager']
                    ).exists()

                    if not can_view:
                        return Response(
                            {'error': 'Only processing unit owners or managers can view join requests'},
                            status=status_module.HTTP_403_FORBIDDEN
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
            user = request.user
            if not (user.is_superuser or user.is_staff):
                role = None
                try:
                    role = normalize_role(user.profile.role)
                except UserProfile.DoesNotExist:
                    pass

                if role != ROLE_ADMIN:
                    unit_ids = _get_user_processing_unit_ids(user)
                    if int(pk) not in unit_ids:
                        return Response(
                            {'error': 'You do not have permission to view users for this processing unit'},
                            status=status_module.HTTP_403_FORBIDDEN
                        )

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
            role = normalize_role(profile.role)
            
            # Admin can see all measurements
            if role == ROLE_ADMIN:
                return CarcassMeasurement.objects.all()
            
            # Processor can see measurements for animals in their processing unit
            elif role == ROLE_PROCESSOR:
                if profile.processing_unit:
                    # Get animals that belong to the processor's unit
                    from .models import Product
                    animal_ids = Product.objects.filter(
                        processing_unit=profile.processing_unit
                    ).values_list('animal_id', flat=True).distinct()
                    return CarcassMeasurement.objects.filter(animal_id__in=animal_ids)
                return CarcassMeasurement.objects.none()
            
            # Abbatoir can see measurements for their own animals
            elif role == ROLE_ABBATOIR:
                return CarcassMeasurement.objects.filter(animal__abbatoir=user)
            
            # Shop owners can see measurements for animals they've purchased
            elif role == ROLE_SHOPOWNER:
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

    def perform_update(self, serializer):
        """Handle request status changes, especially approvals"""
        instance = serializer.instance
        old_status = instance.status
        new_instance = serializer.save()
        new_status = new_instance.status
        
        # Check if the status changed to approved
        if old_status != 'approved' and new_status == 'approved':
            self._handle_approval(new_instance)

    def _handle_approval(self, join_request):
        """Handle the side effects of approving a join request"""
        from .models import ProcessingUnitUser, ShopUser, UserProfile
        from django.utils import timezone
        import logging
        logger = logging.getLogger(__name__)
        
        user = join_request.user
        
        # 1. Update/Create UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if join_request.request_type == 'processing_unit':
            # Create ProcessingUnitUser membership
            requested_role = join_request.requested_role.lower()
            # Valid roles: ['owner', 'manager', 'supervisor', 'worker', 'quality_control']
            if requested_role not in ['owner', 'manager', 'supervisor', 'worker', 'quality_control']:
                requested_role = 'worker'
                
            ProcessingUnitUser.objects.get_or_create(
                user=user,
                processing_unit=join_request.processing_unit,
                defaults={
                    'role': requested_role,
                    'permissions': 'write',
                    'joined_at': timezone.now()
                }
            )
            # Update profile
            profile.processing_unit = join_request.processing_unit
            profile.role = 'Processor'
            profile.save()
            logger.info(f"Γ£à Approved JoinRequest: User {user.username} joined ProcessingUnit {join_request.processing_unit.name}")
            
        elif join_request.request_type == 'shop':
            # Create ShopUser membership
            requested_role = join_request.requested_role.lower()
            # Valid roles: ['owner', 'manager', 'salesperson', 'cashier', 'inventory_clerk']
            if requested_role not in ['owner', 'manager', 'salesperson', 'cashier', 'inventory_clerk']:
                requested_role = 'salesperson'
                
            ShopUser.objects.get_or_create(
                user=user,
                shop=join_request.shop,
                defaults={
                    'role': requested_role,
                    'permissions': 'write',
                    'joined_at': timezone.now()
                }
            )
            # Update profile
            profile.shop = join_request.shop
            profile.role = 'ShopOwner'
            profile.save()
            logger.info(f"Γ£à Approved JoinRequest: User {user.username} joined Shop {join_request.shop.name}")


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
                if profile.shop and profile.role == 'ShopOwner':
                    return Response(
                        {'error': 'You already own a shop. You cannot create another one.'},
                        status=status_module.HTTP_400_BAD_REQUEST
                    )
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                profile = UserProfile.objects.create(user=user, role='ShopOwner')
            
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
            profile.role = 'ShopOwner'
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

    @action(detail=True, methods=['get'], url_path='join-requests', permission_classes=[IsAuthenticated])
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

    @action(detail=True, methods=['get'], url_path='members', permission_classes=[IsAuthenticated])
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
        """Filter orders based on user permissions with optimizations"""
        user = self.request.user
        
        base_qs = Order.objects.all().select_related(
            'shop', 'customer_profile'
        ).prefetch_related('items', 'items__product').order_by('-created_at')
        
        try:
            profile = user.profile
            
            # Admin can see all orders
            if profile.role == 'Admin':
                return base_qs
            
            # Shop owners can see orders for their shop
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    return base_qs.filter(shop=profile.shop)
                return Order.objects.none()
            
            # Processor can see orders related to their processing unit
            elif profile.role == 'Processor':
                if profile.processing_unit:
                    return base_qs.filter(
                        items__product__processing_unit=profile.processing_unit
                    ).distinct()
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
                print(f"Γ£à Updated slaughter part {slaughter_part.id}: remaining_weight = {slaughter_part.remaining_weight}")
            except SlaughterPart.DoesNotExist:
                print(f"ΓÜá∩╕Å Slaughter part {slaughter_part_id} not found")
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
                print(f"Γ£à Updated animal {animal.id}: remaining_weight = {animal.remaining_weight}")
            except Animal.DoesNotExist:
                print(f"ΓÜá∩╕Å Animal {animal_id} not found")
    
    def get_queryset(self):
        """Filter products based on user permissions"""
        user = self.request.user
        
        # Base queryset with essential optimizations
        base_qs = Product.objects.all().select_related(
            'processing_unit', 'animal', 'slaughter_part', 'category', 'transferred_to', 'received_by_shop'
        ).order_by('-created_at')
        
        try:
            profile = user.profile
            role = normalize_role(profile.role)
            print(f"[DEBUG] User: {user.username}, Role: {profile.role} -> Normalized: {role}")
            
            # Admin can see all products
            if role == ROLE_ADMIN:
                return base_qs
            
            # Processor can see products from their processing unit
            elif role == ROLE_PROCESSOR:
                # Get all processing units the user is a member of
                from .models import ProcessingUnitUser
                user_processing_units = ProcessingUnitUser.objects.filter(
                    user=user,
                    is_active=True,
                    is_suspended=False
                ).values_list('processing_unit_id', flat=True)
                
                print(f"[DEBUG] Processor Units: {list(user_processing_units)}")
                print(f"[DEBUG] Profile Unit: {profile.processing_unit}")

                if user_processing_units:
                    qs = base_qs.filter(processing_unit_id__in=user_processing_units)
                    print(f"[DEBUG] QuerySet Count (via membership): {qs.count()}")
                    return qs
                elif profile.processing_unit:
                    qs = base_qs.filter(processing_unit=profile.processing_unit)
                    print(f"[DEBUG] QuerySet Count (via profile): {qs.count()}")
                    return qs
                print("[DEBUG] No units found.")
                return Product.objects.none()
            
            # Shop owners can see products transferred to OR received by their shop(s)
            elif role == ROLE_SHOPOWNER:
                # Get all shops where user is an active member via ShopUser
                user_shop_ids = ShopUser.objects.filter(
                    user=user,
                    is_active=True
                ).values_list('shop_id', flat=True)
                
                if user_shop_ids:
                    # Return products transferred to or received by any of the user's shops
                    queryset = base_qs.filter(
                        Q(transferred_to__id__in=user_shop_ids) | Q(received_by_shop__id__in=user_shop_ids)
                    )
                    
                    # If pending_receipt parameter is provided, filter further
                    pending_receipt = self.request.query_params.get('pending_receipt')
                    if pending_receipt and pending_receipt.lower() == 'true':
                        # Only show products transferred to shop but not fully received yet
                        queryset = queryset.filter(
                            transferred_to__id__in=user_shop_ids,
                            rejection_status__isnull=True  # Not fully rejected
                        ).exclude(
                            Q(weight_received__gte=models.F('weight')) |  # Not fully received
                            Q(weight_rejected__gte=models.F('weight'))   # Not fully rejected
                        )
                    
                    return queryset
                
                # Fallback to profile.shop if no ShopUser memberships exist
                if profile.shop:
                    # Show products transferred to this shop OR already received by this shop
                    queryset = base_qs.filter(
                        Q(transferred_to=profile.shop) | Q(received_by_shop=profile.shop)
                    )
                    
                    # If pending_receipt parameter is provided, filter further
                    pending_receipt = self.request.query_params.get('pending_receipt')
                    if pending_receipt and pending_receipt.lower() == 'true':
                        # Only show products transferred to shop but not fully received yet
                        queryset = queryset.filter(
                            transferred_to=profile.shop,
                            rejection_status__isnull=True  # Not fully rejected
                        ).exclude(
                            Q(weight_received__gte=models.F('weight')) |  # Not fully received
                            Q(weight_rejected__gte=models.F('weight'))   # Not fully rejected
                        )
                    
                    return queryset
                
                return Product.objects.none()
            
            # Abbatoir can see products from their animals
            elif role == ROLE_ABBATOIR:
                return base_qs.filter(animal__abbatoir=user)
            
            return Product.objects.none()
            
        except UserProfile.DoesNotExist:
            return Product.objects.none()

    @action(detail=False, methods=['post'], url_path='receive_products')
    def receive_products(self, request):
        """
        Selectively receive products at shop with weight-first support and rejection handling.
        
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
                    weight_received = Decimal(str(receive.get('weight_received', receive.get('quantity_received', 0))))
                    
                    if weight_received <= 0:
                        errors.append(f"Product {product_id}: weight_received must be greater than 0")
                        continue
                    
                    try:
                        product = Product.objects.get(
                            id=product_id,
                            transferred_to=user_shop,
                            rejection_status__isnull=True  # Not rejected
                        )
                        
                        # Validate weight
                        total_accounted = product.weight_received + product.weight_rejected
                        remaining = product.weight - total_accounted
                        
                        if weight_received > remaining:
                            errors.append(
                                f"Product {product_id}: Cannot receive {weight_received} {product.weight_unit}. "
                                f"Only {remaining} {product.weight_unit} remaining (Total: {product.weight}, "
                                f"Already received: {product.weight_received}, "
                                f"Already rejected: {product.weight_rejected})"
                            )
                            continue
                        
                        # Update product
                        product.weight_received += weight_received
                        product.quantity_received = product.weight_received
                        
                        # If fully received, mark as received
                        if product.weight_received + product.weight_rejected >= product.weight:
                            product.received_by_shop = user_shop
                            product.received_at = timezone.now()
                        
                        product.save()
                        
                        # Update inventory
                        inventory, created = Inventory.objects.get_or_create(
                            shop=user_shop,
                            product=product,
                            defaults={'quantity': Decimal('0'), 'weight': Decimal('0'), 'weight_unit': product.weight_unit}
                        )
                        inventory.weight += weight_received
                        inventory.weight_unit = product.weight_unit
                        inventory.last_updated = timezone.now()
                        inventory.save()
                        
                        received_products.append({
                            'product_id': product.id,
                            'product_name': product.name,
                            'weight_received': float(weight_received),
                            'total_received_weight': float(product.weight_received),
                            'total_weight': float(product.weight),
                            'weight_unit': product.weight_unit,
                        })
                        
                    except Product.DoesNotExist:
                        errors.append(f"Product {product_id} not found or not available for receipt")
                        continue
                
                # Process rejections
                for rejection in rejections:
                    product_id = rejection.get('product_id')
                    weight_rejected = Decimal(str(rejection.get('weight_rejected', rejection.get('quantity_rejected', 0))))
                    rejection_reason = rejection.get('rejection_reason', 'Not specified')
                    
                    if weight_rejected <= 0:
                        errors.append(f"Product {product_id}: weight_rejected must be greater than 0")
                        continue
                    
                    try:
                        product = Product.objects.get(
                            id=product_id,
                            transferred_to=user_shop
                        )
                        
                        # Validate weight
                        total_accounted = product.weight_received + product.weight_rejected
                        remaining = product.weight - total_accounted
                        
                        if weight_rejected > remaining:
                            errors.append(
                                f"Product {product_id}: Cannot reject {weight_rejected} {product.weight_unit}. "
                                f"Only {remaining} {product.weight_unit} remaining (Total: {product.weight}, "
                                f"Already received: {product.weight_received}, "
                                f"Already rejected: {product.weight_rejected})"
                            )
                            continue
                        
                        # Update product
                        product.weight_rejected += weight_rejected
                        product.quantity_rejected = product.weight_rejected
                        product.rejection_reason = rejection_reason
                        product.rejected_by = request.user
                        product.rejected_at = timezone.now()
                        
                        # If entire product is rejected, mark status as rejected
                        if product.weight_rejected >= product.weight:
                            product.rejection_status = 'rejected'
                        
                        product.save()
                        
                        rejected_products.append({
                            'product_id': product.id,
                            'product_name': product.name,
                            'weight_rejected': float(weight_rejected),
                            'total_rejected_weight': float(product.weight_rejected),
                            'weight_unit': product.weight_unit,
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
        Transfer products to a shop with optional weight adjustment.
        
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
        
        # Verify user is a processor and get their processing units
        try:
            profile = user.profile
            if normalize_role(profile.role) != ROLE_PROCESSOR:
                return Response(
                    {'error': 'Only processors can transfer products'},
                    status=status_module.HTTP_403_FORBIDDEN
                )
            
            # Get all processing units the user belongs to
            from .models import ProcessingUnitUser
            user_processing_units = list(ProcessingUnitUser.objects.filter(
                user=user,
                is_active=True,
                is_suspended=False
            ).values_list('processing_unit_id', flat=True))
            
            if profile.processing_unit_id and profile.processing_unit_id not in user_processing_units:
                user_processing_units.append(profile.processing_unit_id)
                
            if not user_processing_units:
                return Response(
                    {'error': 'User not associated with any processing unit'},
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
                    weight_to_transfer = transfer.get('weight', transfer.get('quantity'))
                    
                    try:
                        product = Product.objects.get(
                            id=product_id,
                            processing_unit_id__in=user_processing_units
                        )
                    except Product.DoesNotExist:
                        errors.append(f'Product {product_id} not found or not owned by your processing unit')
                        continue
                    
                    if product.transferred_to is not None:
                        errors.append(f'Product {product.name} has already been transferred')
                        continue
                    
                    # If weight specified, validate it
                    if weight_to_transfer is not None:
                        weight_to_transfer = Decimal(str(weight_to_transfer))
                        
                        if weight_to_transfer <= 0:
                            errors.append(f'Product {product.name}: weight must be greater than 0')
                            continue
                        
                        if weight_to_transfer > product.weight:
                            errors.append(
                                f'Product {product.name}: cannot transfer {weight_to_transfer} {product.weight_unit}. '
                                f'Only {product.weight} {product.weight_unit} available'
                            )
                            continue
                        
                        # If transferring partial weight, create a new product for the transfer
                        if weight_to_transfer < product.weight:
                            # Reduce original product weight
                            original_weight = product.weight
                            product.weight -= weight_to_transfer
                            product.save()
                            
                            # Create new product for transfer
                            transferred_product = Product.objects.create(
                                name=product.name,
                                batch_number=f"{product.batch_number}-T",
                                product_type=product.product_type,
                                quantity=weight_to_transfer,
                                weight=weight_to_transfer,
                                weight_unit=product.weight_unit,
                                price=product.price,
                                description=product.description,
                                processing_unit=product.processing_unit,
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
                                description=f'Split {product.name}: kept {product.weight} {product.weight_unit}, transferred {weight_to_transfer} {product.weight_unit} to {shop.name}',
                                entity_id=str(transferred_product.id),
                                entity_type='product',
                                metadata={
                                    'original_product_id': product.id,
                                    'transferred_product_id': transferred_product.id,
                                    'original_batch': product.batch_number,
                                    'transferred_batch': transferred_product.batch_number,
                                    'weight_kept': float(product.weight),
                                    'weight_transferred': float(weight_to_transfer),
                                    'weight_unit': product.weight_unit,
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
                                    'weight': float(product.weight),
                                    'weight_unit': product.weight_unit
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
            print(f"[SALE_CREATE] Γ£à Success - Status: {response.status_code}")
            print(f"[SALE_CREATE] Response data: {response.data}")
            return response
        except Exception as e:
            print(f"[SALE_CREATE] Γ¥î Exception occurred: {type(e).__name__}")
            print(f"[SALE_CREATE] Error message: {str(e)}")
            import traceback
            print(f"[SALE_CREATE] Traceback:\n{traceback.format_exc()}")
            raise
    
    def get_queryset(self):
        """Filter sales based on user permissions"""
        user = self.request.user
        
        # Base queryset with essential optimizations
        base_qs = Sale.objects.all().select_related(
            'shop', 'sold_by', 'invoice'
        ).prefetch_related('items', 'items__product').order_by('-created_at')
        
        # First check ShopUser memberships (new system)
        shop_membership = user.shop_memberships.filter(is_active=True).first()
        if shop_membership:
            # ShopUser can see sales from their shop
            return base_qs.filter(shop=shop_membership.shop)
        
        # Fall back to UserProfile (old system)
        try:
            profile = user.profile
            
            # Admin can see all sales
            if profile.role == 'Admin':
                return base_qs
            
            # Shop owners can see sales from their shop
            elif profile.role == 'ShopOwner':
                if profile.shop:
                    return base_qs.filter(shop=profile.shop)
                return Sale.objects.none()
            
            # Processor can see sales of products from their processing unit
            elif profile.role == 'Processor':
                if profile.processing_unit:
                    return base_qs.filter(
                        items__product__processing_unit=profile.processing_unit
                    ).distinct()
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
            print(f"[SALE_PERFORM_CREATE] Γ£à Saving sale with shop: {shop.name}, sold_by: {user.username}")
            print(f"[SALE_PERFORM_CREATE] Validated data before save: {serializer.validated_data}")
            serializer.save(shop=shop, sold_by=user)
            print(f"[SALE_PERFORM_CREATE] Γ£à Sale saved successfully")
        else:
            print(f"[SALE_PERFORM_CREATE] Γ¥î No shop found for user")
            raise ValidationError("User is not associated with any shop")


# Shop Settings ViewSet
class ShopSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing shop settings"""
    queryset = ShopSettings.objects.all()
    serializer_class = ShopSettingsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        try:
            profile = user.profile
            if profile.shop:
                return ShopSettings.objects.filter(shop=profile.shop)
        except UserProfile.DoesNotExist:
            pass
        return ShopSettings.objects.none()
    
    @action(detail=False, methods=['get'])
    def my_settings(self, request):
        """Get settings for the current user's shop"""
        user = request.user
        try:
            profile = user.profile
            if profile.shop:
                settings, created = ShopSettings.objects.get_or_create(shop=profile.shop)
                serializer = self.get_serializer(settings)
                return Response(serializer.data)
        except UserProfile.DoesNotExist:
            pass
        return Response({"error": "No shop associated with user"}, status=status_module.HTTP_404_NOT_FOUND)


# Invoice ViewSets
class InvoiceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing invoices (pre-sale quotes)"""
    queryset = Invoice.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return InvoiceCreateSerializer
        return InvoiceSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # Base queryset with optimizations
        base_qs = Invoice.objects.all().select_related(
            'shop', 'created_by'
        ).prefetch_related('items', 'payments', 'sales').order_by('-created_at')
        
        try:
            profile = user.profile
            if profile.shop:
                return base_qs.filter(shop=profile.shop)
        except UserProfile.DoesNotExist:
            pass
        return Invoice.objects.none()
    
    def perform_create(self, serializer):
        user = self.request.user
        shop = None
        try:
            profile = user.profile
            if profile.shop:
                shop = profile.shop
        except UserProfile.DoesNotExist:
            pass
        
        if shop:
            serializer.save(shop=shop, created_by=user, status='pending')
        else:
            raise ValidationError("User is not associated with any shop")
    
    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        """Record a payment against an invoice"""
        invoice = self.get_object()
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method', 'cash')
        transaction_reference = request.data.get('transaction_reference', '')
        notes = request.data.get('notes', '')
        
        if not amount:
            return Response({"error": "Amount is required"}, status=status_module.HTTP_400_BAD_REQUEST)
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                return Response({"error": "Amount must be greater than 0"}, status=status_module.HTTP_400_BAD_REQUEST)
            
            # Check if payment exceeds balance
            if amount > invoice.balance_due:
                return Response(
                    {"error": f"Payment amount ({amount}) exceeds balance due ({invoice.balance_due})"}, 
                    status=status_module.HTTP_400_BAD_REQUEST
                )
            
            # Create payment
            payment = InvoicePayment.objects.create(
                invoice=invoice,
                amount=amount,
                payment_method=payment_method,
                transaction_reference=transaction_reference,
                notes=notes,
                recorded_by=request.user
            )
            
            serializer = InvoicePaymentSerializer(payment)
            return Response(serializer.data, status=status_module.HTTP_201_CREATED)
        
        except (ValueError, Decimal.InvalidOperation):
            return Response({"error": "Invalid amount"}, status=status_module.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def convert_to_sale(self, request, pk=None):
        """Convert invoice to sale (complete transaction)"""
        invoice = self.get_object()
        
        if invoice.status == 'cancelled':
            return Response({"error": "Cannot convert cancelled invoice"}, status=status_module.HTTP_400_BAD_REQUEST)
        
        payment_method = request.data.get('payment_method', 'cash')
        
        with transaction.atomic():
            # Create sale from invoice
            sale = Sale.objects.create(
                shop=invoice.shop,
                customer_name=invoice.customer_name,
                customer_phone=invoice.customer_phone,
                total_amount=invoice.total_amount,
                payment_method=payment_method,
                sold_by=request.user,
                invoice=invoice
            )
            
            # Create sale items from invoice items
            for invoice_item in invoice.items.all():
                item_weight = invoice_item.weight if invoice_item.weight else invoice_item.quantity
                SaleItem.objects.create(
                    sale=sale,
                    product=invoice_item.product,
                    quantity=item_weight,
                    weight=item_weight,
                    weight_unit=invoice_item.weight_unit or 'kg',
                    unit_price=invoice_item.unit_price
                )
            
            # Update invoice status
            invoice.status = 'completed'
            invoice.save()
            
            serializer = SaleSerializer(sale)
            return Response(serializer.data, status=status_module.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an invoice"""
        invoice = self.get_object()
        
        if invoice.status == 'completed':
            return Response({"error": "Cannot cancel completed invoice"}, status=status_module.HTTP_400_BAD_REQUEST)
        
        invoice.status = 'cancelled'
        invoice.save()
        
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get invoice statistics for the shop"""
        user = request.user
        try:
            profile = user.profile
            if profile.shop:
                from django.db.models import Sum, Count
                invoices = Invoice.objects.filter(shop=profile.shop)
                
                stats = {
                    'total_invoices': invoices.count(),
                    'draft': invoices.filter(status='draft').count(),
                    'pending': invoices.filter(status='pending').count(),
                    'sent': invoices.filter(status='sent').count(),
                    'partially_paid': invoices.filter(status='partially_paid').count(),
                    'paid': invoices.filter(status='paid').count(),
                    'completed': invoices.filter(status='completed').count(),
                    'cancelled': invoices.filter(status='cancelled').count(),
                    'overdue': invoices.filter(status='overdue').count(),
                    'total_value': invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0'),
                    'total_paid': invoices.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0'),
                }
                return Response(stats)
        except UserProfile.DoesNotExist:
            pass
        return Response({"error": "No shop associated with user"}, status=status_module.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Generate and download PDF version of the invoice"""
        invoice = self.get_object()
        shop = invoice.shop
        
        # Get shop settings for branding
        try:
            settings = shop.settings
        except:
            # Fallback if ShopSettings doesn't exist or is not one-to-one as expected
            settings = None
            
        items = invoice.items.all()
        # Calculate empty rows to fill the table (total 10 rows minimum for aesthetic)
        empty_rows = range(max(0, 10 - items.count()))
        
        context = {
            'invoice': invoice,
            'shop': shop,
            'settings': settings,
            'items': items,
            'empty_rows': empty_rows,
        }
        
        filename = f"Invoice_{invoice.invoice_number}.pdf"
        response = download_pdf_response('meat_trace/invoice_pdf.html', context, filename)
        
        if response:
            return response
        return Response({"error": "Failed to generate PDF"}, status=status_module.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoiceItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing invoice items"""
    queryset = InvoiceItem.objects.all()
    serializer_class = InvoiceItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        try:
            profile = user.profile
            if profile.shop:
                return InvoiceItem.objects.filter(invoice__shop=profile.shop).select_related('invoice', 'product')
        except UserProfile.DoesNotExist:
            pass
        return InvoiceItem.objects.none()


class InvoicePaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing invoice payments"""
    queryset = InvoicePayment.objects.all()
    serializer_class = InvoicePaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        try:
            profile = user.profile
            if profile.shop:
                return InvoicePayment.objects.filter(invoice__shop=profile.shop).select_related('invoice', 'recorded_by')
        except UserProfile.DoesNotExist:
            pass
        return InvoicePayment.objects.none()


# Enhanced Receipt ViewSet
class ReceiptViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product receipts"""
    queryset = Receipt.objects.all()
    serializer_class = ReceiptSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        try:
            profile = user.profile
            if profile.shop:
                return Receipt.objects.filter(shop=profile.shop).select_related('shop', 'product', 'recorded_by')
        except UserProfile.DoesNotExist:
            pass
        return Receipt.objects.none()
    
    def perform_create(self, serializer):
        user = self.request.user
        shop = None
        try:
            profile = user.profile
            if profile.shop:
                shop = profile.shop
        except UserProfile.DoesNotExist:
            pass
        
        if shop:
            serializer.save(shop=shop, recorded_by=user)
        else:
            raise ValidationError("User is not associated with any shop")
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent receipts for the shop"""
        limit = int(request.query_params.get('limit', 10))
        receipts = self.get_queryset().order_by('-created_at')[:limit]
        serializer = self.get_serializer(receipts, many=True)
        return Response(serializer.data)




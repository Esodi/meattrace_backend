from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.db import models

from .models import Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage, ProductTimelineEvent, Inventory, Order, OrderItem, CarcassMeasurement, SlaughterPart, ProcessingUnit, ProcessingUnitUser, Shop, ShopUser, UserAuditLog, JoinRequest, Notification, Activity, SystemAlert, PerformanceMetric, ComplianceAudit, Certification, SystemHealth, SecurityLog, TransferRequest, BackupSchedule
from .farmer_dashboard_serializer import FarmerDashboardSerializer
from .serializers import AnimalSerializer, ProductSerializer, OrderSerializer, ShopSerializer, SlaughterPartSerializer, ActivitySerializer, ProcessingUnitSerializer, JoinRequestSerializer, ProductCategorySerializer, CarcassMeasurementSerializer

@api_view(['GET'])
def user_profile_view(request):
    """
    API endpoint to get current user's profile information.
    Used by Flutter app after login.
    """
    user = request.user
    
    if not user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        profile = UserProfile.objects.get(user=user)
        profile_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': profile.role,
            'phone': profile.phone,
            'address': profile.address,
            'processing_unit': {
                'id': profile.processing_unit.id,
                'name': profile.processing_unit.name,
            } if profile.processing_unit else None,
            'shop': {
                'id': profile.shop.id,
                'name': profile.shop.name,
            } if profile.shop else None,
        }
        return Response({'profile': profile_data}, status=status.HTTP_200_OK)
    except UserProfile.DoesNotExist:
        # Return basic user info if no profile exists
        return Response({'profile': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': 'unknown',
        }}, status=status.HTTP_200_OK)


# Admin Dashboard Views

@login_required
def admin_dashboard(request):
    """
    Admin dashboard main page.
    """
    # Mock data for dashboard - in real implementation, this would come from database
    user_roles = UserProfile.objects.values('role').annotate(count=models.Count('id'))
    dashboard_data = {
        'users': {'total': UserProfile.objects.count(), 'active': UserProfile.objects.filter(user__is_active=True).count()},
        'products': {'active': Product.objects.count()},
        'transfers': {'pending': 23},
        'system': {'health_score': 95},
        'charts': {
            'production': {
                'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                'data': [120, 135, 98, 142, 156, 89, 134]
            },
            'users': {
                'labels': [role['role'] for role in user_roles],
                'data': [role['count'] for role in user_roles]
            },
            'performance': {
                'labels': ['CPU', 'Memory', 'Disk I/O', 'Network'],
                'data': [45, 67, 23, 78]
            }
        },
        'activities': [
            {'description': 'New user registered', 'timestamp': '2024-01-15T10:30:00Z', 'user': 'System'},
            {'description': 'Product transfer completed', 'timestamp': '2024-01-15T09:45:00Z', 'user': 'Processor A'},
            {'description': 'Inventory alert resolved', 'timestamp': '2024-01-15T08:20:00Z', 'user': 'Admin'},
        ]
    }
    
    return render(request, 'admin/dashboard.html', {'dashboard_data': dashboard_data})

@login_required
def admin_users(request):
    """
    User management page.
    """
    # Mock data for users page
    users_data = {
        'stats': {'total': 1250, 'active': 1180, 'pending': 45, 'suspended': 25},
        'users': [
            {
                'id': 1,
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'role': 'farmer',
                'status': 'active',
                'date_joined': '2024-01-01T00:00:00Z',
                'last_login': '2024-01-15T10:00:00Z'
            },
            # Add more mock users as needed
        ]
    }
    
    return render(request, 'admin/users.html', {'users_data': users_data})

@login_required
def admin_supply_chain(request):
    """
    Supply chain monitoring page.
    """
    # Mock data for supply chain page
    supply_chain_data = {
        'transfers': {
            'pending': 23,
            'completed_today': 45,
            'list': [
                {
                    'id': 1,
                    'product_name': 'Beef Ribeye',
                    'product_type': 'Meat Cut',
                    'from_unit': 'Processing Unit A',
                    'to_unit': 'Shop B',
                    'status': 'pending',
                    'requested_at': '2024-01-15T08:00:00Z'
                }
            ],
            'recent': [
                {
                    'product_name': 'Chicken Breast',
                    'from_unit': 'Processing Unit C',
                    'to_unit': 'Shop D',
                    'completed_at': '2024-01-15T09:30:00Z',
                    'status': 'completed'
                }
            ]
        },
        'inventory': {
            'alerts': 8,
            'alerts_list': [
                {
                    'id': 1,
                    'product_name': 'Ground Beef',
                    'message': 'Stock below minimum level',
                    'severity': 'warning',
                    'timestamp': '2024-01-15T07:00:00Z'
                }
            ]
        },
        'performance': {'avg_processing_time': '2.4h'},
        'processing_units': [
            {
                'name': 'Processing Unit A',
                'location': 'Nairobi',
                'status': 'active',
                'capacity_used': 75,
                'capacity_total': 100,
                'capacity_percentage': 75
            }
        ],
        'charts': {
            'flow': {
                'labels': ['Farmers', 'Processing Units', 'Shops', 'In Transit'],
                'data': [25, 35, 20, 20]
            }
        }
    }
    
    return render(request, 'admin/supply_chain.html', {'supply_chain_data': supply_chain_data})

@login_required
def admin_performance(request):
    """
    Performance metrics page.
    """
    # Mock data for performance page
    performance_data = {
        'kpis': {
            'avg_processing_time': '2.4h',
            'yield_rate': '87%',
            'on_time_delivery': '92%',
            'quality_score': '94%'
        },
        'charts': {
            'processing': {
                'labels': ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
                'processing_time': [2.5, 2.3, 2.4, 2.2],
                'volume': [120, 135, 128, 142]
            },
            'yield': {
                'labels': ['Target', 'Actual', 'Previous Month'],
                'data': [88, 87, 85]
            },
            'pipeline': {
                'labels': ['Receiving', 'Processing', 'Packaging', 'Storage', 'Shipping'],
                'data': [95, 87, 92, 89, 94]
            },
            'comparative': {
                'labels': ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
                'current': [85, 87, 89, 87],
                'previous': [82, 84, 86, 85]
            }
        },
        'alerts': [
            {
                'id': 1,
                'title': 'Processing Time Alert',
                'message': 'Average processing time exceeded threshold',
                'severity': 'warning',
                'timestamp': '2024-01-15T08:00:00Z',
                'action_required': True
            }
        ],
        'pipeline_efficiency': {
            'stages': [
                {'name': 'Receiving', 'efficiency': 95},
                {'name': 'Processing', 'efficiency': 87},
                {'name': 'Packaging', 'efficiency': 92},
                {'name': 'Storage', 'efficiency': 89},
                {'name': 'Shipping', 'efficiency': 94}
            ]
        },
        'quality_metrics': [
            {'name': 'Temperature Control', 'value': '98%', 'status': 'excellent'},
            {'name': 'Hygiene Standards', 'value': '96%', 'status': 'excellent'},
            {'name': 'Packaging Integrity', 'value': '94%', 'status': 'good'},
            {'name': 'Label Accuracy', 'value': '97%', 'status': 'excellent'}
        ],
        'reports': [
            {
                'id': 1,
                'type': 'Weekly Performance',
                'period': 'Jan 8-14, 2024',
                'generated_at': '2024-01-15T07:00:00Z',
                'status': 'completed'
            }
        ],
        'yield_analysis': {
            'target': '88%',
            'actual': '87%',
            'variance': '-1%'
        }
    }
    
    return render(request, 'admin/performance.html', {'performance_data': performance_data})

@login_required
def admin_compliance(request):
    """
    Compliance dashboard page.
    """
    # Mock data for compliance page
    compliance_data = {
        'certifications': {
            'active': 12,
            'expiring_soon': 3,
            'expired': 1
        },
        'audits': {
            'scheduled': 5,
            'completed': 23,
            'overdue': 2
        },
        'quality_tests': {
            'passed': 185,
            'failed': 12,
            'pending': 8
        },
        'incidents': [
            {
                'id': 1,
                'title': 'Temperature Deviation',
                'severity': 'medium',
                'status': 'investigating',
                'reported_at': '2024-01-15T06:00:00Z'
            }
        ]
    }
    
    return render(request, 'admin/compliance.html', {'compliance_data': compliance_data})

@login_required
def admin_system_health(request):
    """
    System health page.
    """
    # Mock data for system health page
    system_health_data = {
        'overall_score': 95,
        'components': [
            {'name': 'Database', 'status': 'healthy', 'uptime': '99.9%', 'response_time': '45ms'},
            {'name': 'API Server', 'status': 'healthy', 'uptime': '99.7%', 'response_time': '120ms'},
            {'name': 'File Storage', 'status': 'warning', 'uptime': '98.5%', 'response_time': '200ms'},
            {'name': 'Email Service', 'status': 'healthy', 'uptime': '99.8%', 'response_time': '150ms'}
        ],
        'alerts': [
            {
                'id': 1,
                'title': 'High Memory Usage',
                'message': 'Server memory usage above 80%',
                'severity': 'warning',
                'timestamp': '2024-01-15T09:00:00Z'
            }
        ],
        'backups': {
            'last_backup': '2024-01-15T02:00:00Z',
            'status': 'successful',
            'size': '2.4GB'
        },
        'security': {
            'failed_logins': 3,
            'active_sessions': 45,
            'security_events': 0
        }
    }
    
    return render(request, 'admin/system_health.html', {'system_health_data': system_health_data})

# API endpoints for real-time data updates

@api_view(['GET'])
@login_required
def admin_dashboard_data(request):
    """
    API endpoint for dashboard real-time data.
    """
    # Return mock real-time data
    data = {
        'users': {'total': 1250, 'active': 1180},
        'products': {'active': 8750},
        'transfers': {'pending': 23},
        'system': {'health_score': 95},
        'charts': {
            'production': {
                'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                'data': [120, 135, 98, 142, 156, 89, 134]
            },
            'users': {
                'labels': ['Farmers', 'Processors', 'Shop Owners', 'Admins'],
                'data': [450, 320, 180, 50]
            },
            'performance': {
                'labels': ['CPU', 'Memory', 'Disk I/O', 'Network'],
                'data': [45, 67, 23, 78]
            }
        },
        'activities': [
            {'description': 'New user registered', 'timestamp': '2024-01-15T10:30:00Z', 'user': 'System', 'details': 'User John Doe joined as Farmer'},
            {'description': 'Product transfer completed', 'timestamp': '2024-01-15T09:45:00Z', 'user': 'Processor A', 'details': 'Beef transfer to Shop B completed'},
            {'description': 'Inventory alert resolved', 'timestamp': '2024-01-15T08:20:00Z', 'user': 'Admin', 'details': 'Low stock alert for Ground Beef resolved'}
        ]
    }
    return Response(data)

@api_view(['GET'])
@login_required
def admin_supply_chain_data(request):
    """
    API endpoint for supply chain real-time data.
    """
    # Return mock supply chain data
    data = {
        'transfers': {
            'pending': 23,
            'completed_today': 45
        },
        'inventory': {
            'alerts': 8
        },
        'performance': {'avg_processing_time': '2.4h'},
        'processing_units': [
            {
                'name': 'Processing Unit A',
                'location': 'Nairobi',
                'status': 'active',
                'capacity_used': 75,
                'capacity_total': 100,
                'capacity_percentage': 75
            }
        ]
    }
    return Response(data)

@api_view(['GET'])
@login_required
def admin_performance_data(request):
    """
    API endpoint for performance real-time data.
    """
    # Return mock performance data
    data = {
        'kpis': {
            'avg_processing_time': '2.4h',
            'yield_rate': '87%',
            'on_time_delivery': '92%',
            'quality_score': '94%'
        },
        'alerts': [
            {
                'id': 1,
                'title': 'Processing Time Alert',
                'message': 'Average processing time exceeded threshold',
                'severity': 'warning',
                'timestamp': '2024-01-15T08:00:00Z',
                'action_required': True
            }
        ]
    }
    return Response(data)


# ═════════════════════════════════════════════════════════════════════════════=
# API ViewSets
# ═════════════════════════════════════════════════════════════════════════════=


class AnimalViewSet(viewsets.ModelViewSet):
    """ViewSet for animals, exposes transfer/receive/slaughter actions used by frontend"""
    queryset = Animal.objects.all()
    serializer_class = AnimalSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def perform_create(self, serializer):
        """Automatically set farmer to the authenticated user."""
        serializer.save(farmer=self.request.user)

    def get_queryset(self):
        user = self.request.user
        queryset = Animal.objects.all().select_related('farmer', 'transferred_to', 'received_by')

        # Farmers see their own animals
        if hasattr(user, 'profile') and user.profile.role == 'farmer':
            queryset = queryset.filter(farmer=user)

        # ProcessingUnit users should see animals transferred to their unit
        if hasattr(user, 'profile') and user.profile.role == 'processing_unit':
            pu = user.profile.processing_unit
            if pu:
                queryset = queryset.filter(
                    Q(transferred_to=pu) | Q(slaughter_parts__transferred_to=pu)
                ).distinct()
            else:
                queryset = queryset.none()

        return queryset.order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='transfer')
    def transfer(self, request):
        """Transfer whole animals or parts to a processing unit.

        Request data:
        - animal_ids: list of animal primary keys (whole carcass transfers)
        - processing_unit_id: id of ProcessingUnit
        - part_transfers: list of {animal_id, part_ids}
        """
        data = request.data
        animal_ids = data.get('animal_ids', []) or []
        processing_unit_id = data.get('processing_unit_id')
        part_transfers = data.get('part_transfers', []) or []

        if not animal_ids and not part_transfers:
            return Response({'error': 'animal_ids or part_transfers are required'}, status=status.HTTP_400_BAD_REQUEST)
        if not processing_unit_id:
            return Response({'error': 'processing_unit_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine transfer mode
        if 'transfer_mode' in data and data['transfer_mode'] in ['whole', 'parts']:
            transfer_mode = data['transfer_mode']
        else:
            transfer_mode = 'parts' if part_transfers and not animal_ids else 'whole'

        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        transferred_animals_count = 0
        transferred_parts_count = 0

        # Handle whole animal transfers
        for aid in animal_ids:
            try:
                animal = Animal.objects.get(id=aid, farmer=request.user)
            except Animal.DoesNotExist:
                return Response({'error': f'Animal {aid} not found or not owned by you'}, status=status.HTTP_404_NOT_FOUND)

            if animal.processed:
                return Response({'error': f'Animal {animal.animal_id} has already been processed'}, status=status.HTTP_400_BAD_REQUEST)
            if animal.transferred_to is not None:
                return Response({'error': f'Animal {animal.animal_id} has already been transferred'}, status=status.HTTP_400_BAD_REQUEST)

            animal.transferred_to = processing_unit
            animal.transferred_at = timezone.now()
            animal.save()
            transferred_animals_count += 1

            # Create activity for transfer
            Activity.objects.create(
                user=request.user,
                activity_type='transfer',
                title=f'Animal {animal.animal_name or animal.animal_id} transferred',
                description=f'Transferred {animal.species} to {processing_unit.name}',
                entity_id=str(animal.id),
                entity_type='animal',
                metadata={'animal_id': animal.animal_id, 'processing_unit': processing_unit.name, 'transfer_mode': transfer_mode}
            )

            UserAuditLog.objects.create(
                performed_by=request.user,
                affected_user=animal.farmer,
                processing_unit=processing_unit,
                action='animal_transferred',
                description=f'Animal {animal.animal_id} transferred to processing unit {processing_unit.name}',
                old_values={'transferred_to': None},
                new_values={'transferred_to': processing_unit.id, 'transferred_at': animal.transferred_at.isoformat()},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

        # Handle part transfers
        for pt in part_transfers:
            animal_id = pt.get('animal_id')
            part_ids = pt.get('part_ids', [])
            if not animal_id or not part_ids:
                return Response({'error': 'Each part_transfer must have animal_id and part_ids'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                animal = Animal.objects.get(id=animal_id, farmer=request.user)
            except Animal.DoesNotExist:
                return Response({'error': f'Animal {animal_id} not found or not owned by you'}, status=status.HTTP_404_NOT_FOUND)

            if not animal.slaughtered:
                return Response({'error': f'Animal {animal.animal_id} must be slaughtered before transferring parts'}, status=status.HTTP_400_BAD_REQUEST)

            for pid in part_ids:
                try:
                    part = SlaughterPart.objects.get(id=pid, animal=animal)
                except SlaughterPart.DoesNotExist:
                    return Response({'error': f'Part {pid} not found for animal {animal_id}'}, status=status.HTTP_404_NOT_FOUND)

                if part.transferred_to is not None:
                    return Response({'error': f'Part {part.part_type} of animal {animal.animal_id} has already been transferred'}, status=status.HTTP_400_BAD_REQUEST)

                part.transferred_to = processing_unit
                part.transferred_at = timezone.now()
                part.is_selected_for_transfer = True
                part.save()
                transferred_parts_count += 1

                # Log audit for part transfer
                UserAuditLog.objects.create(
                    performed_by=request.user,
                    affected_user=animal.farmer,
                    processing_unit=processing_unit,
                    action='part_transferred',
                    description=f'Part {part.part_type} of animal {animal.animal_id} transferred',
                    old_values={'transferred_to': None},
                    new_values={'transferred_to': processing_unit.id},
                    metadata={'transfer_mode': transfer_mode},
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )

            # If all parts are transferred, mark animal transferred
            all_parts = animal.slaughter_parts.all()
            if all_parts.exists() and all(p.transferred_to is not None for p in all_parts):
                animal.transferred_to = processing_unit
                animal.transferred_at = timezone.now()
                animal.save()

        message_parts = []
        if transferred_animals_count > 0:
            message_parts.append(f'{transferred_animals_count} animal(s)')
        if transferred_parts_count > 0:
            message_parts.append(f'{transferred_parts_count} part(s)')

        return Response({
            'message': f"Successfully transferred {' and '.join(message_parts)} to {processing_unit.name}",
            'transferred_animals_count': transferred_animals_count,
            'transferred_parts_count': transferred_parts_count,
            'transfer_mode': transfer_mode
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='receive_animals')
    def receive_animals(self, request):
        """Endpoint for processing units to receive transferred animals/parts"""
        user = request.user
        if not hasattr(user, 'profile') or user.profile.role != 'processing_unit':
            return Response({'error': 'Only processing unit users can receive animals'}, status=status.HTTP_403_FORBIDDEN)

        processing_unit = user.profile.processing_unit
        if not processing_unit:
            return Response({'error': 'User not associated with a processing unit'}, status=status.HTTP_400_BAD_REQUEST)

        animal_ids = request.data.get('animal_ids', []) or []
        part_receives = request.data.get('part_receives', []) or []

        if not animal_ids and not part_receives:
            return Response({'error': 'animal_ids or part_receives are required'}, status=status.HTTP_400_BAD_REQUEST)

        received_animals_count = 0
        received_parts_count = 0

        animals = []
        for aid in animal_ids:
            try:
                animal = Animal.objects.get(id=aid, transferred_to=processing_unit)
            except Animal.DoesNotExist:
                return Response({'error': f'Animal {aid} not found or not transferred to your processing unit'}, status=status.HTTP_404_NOT_FOUND)

            if animal.received_by is not None:
                return Response({'error': f'Animal {animal.animal_id} has already been received'}, status=status.HTTP_400_BAD_REQUEST)

            animal.received_by = user
            animal.received_at = timezone.now()
            animal.save()
            received_animals_count += 1

        # receive parts
        for pr in part_receives:
            animal_id = pr.get('animal_id')
            part_ids = pr.get('part_ids', [])
            if not animal_id or not part_ids:
                return Response({'error': 'Each part receive must include animal_id and part_ids'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                animal = Animal.objects.get(id=animal_id)
            except Animal.DoesNotExist:
                return Response({'error': f'Animal {animal_id} not found'}, status=status.HTTP_404_NOT_FOUND)

            for pid in part_ids:
                try:
                    part = SlaughterPart.objects.get(id=pid, animal=animal, transferred_to=processing_unit)
                except SlaughterPart.DoesNotExist:
                    return Response({'error': f'Part {pid} not found or not transferred to your processing unit'}, status=status.HTTP_404_NOT_FOUND)

                if part.received_by is not None:
                    return Response({'error': f'Part {part.part_type} already received'}, status=status.HTTP_400_BAD_REQUEST)

                part.received_by = user
                part.received_at = timezone.now()
                part.save()
                received_parts_count += 1
                # If all parts are received, mark the animal as received
                all_parts = SlaughterPart.objects.filter(animal=animal, transferred_to=processing_unit)
                if all_parts.exists() and all(pt.received_by is not None for pt in all_parts):
                    animal.received_by = user
                    animal.received_at = timezone.now()
                    animal.save()

        return Response({
            'message': f'Received {received_animals_count} animals and {received_parts_count} parts',
            'received_animals_count': received_animals_count,
            'received_parts_count': received_parts_count
        }, status=status.HTTP_200_OK)


class ActivityViewSet(viewsets.ModelViewSet):
    """ViewSet for activities, provides activity feed for farmers"""
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Farmers see their own activities
        if hasattr(user, 'profile') and user.profile.role == 'farmer':
            return Activity.objects.filter(user=user).order_by('-timestamp')
        return Activity.objects.none()

    @action(detail=False, methods=['get'], url_path='recent')
    def recent_activities(self, request):
        """Get recent activities for the current user"""
        limit = int(request.query_params.get('limit', 10))
        activities = self.get_queryset()[:limit]
        serializer = self.get_serializer(activities, many=True)
        return Response({'activities': serializer.data, 'count': len(serializer.data)})


@login_required
def farmer_dashboard(request):
    """Dashboard endpoint for farmers with aggregated statistics"""
    user = request.user

    # Ensure user is a farmer
    if not hasattr(user, 'profile') or user.profile.role != 'farmer':
        return Response({'error': 'Only farmers can access this endpoint'}, status=status.HTTP_403_FORBIDDEN)

    # Get animal statistics
    total_animals = Animal.objects.filter(farmer=user).count()
    active_animals = Animal.objects.filter(farmer=user, slaughtered=False).count()
    slaughtered_animals = Animal.objects.filter(farmer=user, slaughtered=True).count()
    transferred_animals = Animal.objects.filter(farmer=user, transferred_to__isnull=False).count()

    # Get species breakdown
    species_stats = {}
    for species_choice in Animal.SPECIES_CHOICES:
        species_key = species_choice[0]
        count = Animal.objects.filter(farmer=user, species=species_key).count()
        if count > 0:
            species_stats[species_choice[1]] = count

    # Get recent activities (last 5)
    recent_activities = Activity.objects.filter(user=user).order_by('-timestamp')[:5]

    # Get pending transfers
    pending_transfers = Animal.objects.filter(
        farmer=user,
        transferred_to__isnull=False,
        received_by__isnull=True
    ).count()

    dashboard_data = {
        'user': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email
        },
        'statistics': {
            'total_animals': total_animals,
            'active_animals': active_animals,
            'slaughtered_animals': slaughtered_animals,
            'transferred_animals': transferred_animals,
            'pending_transfers': pending_transfers
        },
        'species_breakdown': species_stats,
        'recent_activities': recent_activities,
        'summary': {
            'animals_registered_this_month': Animal.objects.filter(
                farmer=user,
                created_at__month=timezone.now().month,
                created_at__year=timezone.now().year
            ).count(),
            'animals_slaughtered_this_month': Animal.objects.filter(
                farmer=user,
                slaughtered_at__month=timezone.now().month,
                slaughtered_at__year=timezone.now().year
            ).count()
        }
    }

    serializer = FarmerDashboardSerializer(dashboard_data)
    return Response(serializer.data)


@api_view(['GET'])
def dashboard_view(request):
    """
    Generic dashboard endpoint that routes to role-specific dashboards.
    Called by frontend as /api/v2/dashboard/
    """
    user = request.user
    
    if not user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Route to appropriate dashboard based on user role
    if hasattr(user, 'profile'):
        role = user.profile.role
        if role == 'farmer':
            return farmer_dashboard(request)
        # Add other role-specific dashboards here as needed
    
    # Default response for users without specific dashboard
    return Response({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        },
        'statistics': {},
        'recent_activities': []
    })


@api_view(['GET'])
def activities_view(request):
    """
    Activities endpoint for frontend.
    Called by frontend as /api/v2/activities/
    Returns recent activities for the current user.
    """
    user = request.user
    
    if not user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Get recent activities for the user
    limit = int(request.query_params.get('limit', 10))
    activities = Activity.objects.filter(user=user).order_by('-timestamp')[:limit]
    
    activities_data = []
    for activity in activities:
        activities_data.append({
            'id': activity.id,
            'type': activity.activity_type,
            'title': activity.title,
            'description': activity.description,
            'timestamp': activity.timestamp.isoformat(),
            'entity_id': activity.entity_id,
            'entity_type': activity.entity_type,
            'metadata': activity.metadata
        })
    
    return Response({
        'activities': activities_data,
        'count': len(activities_data)
    })


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for user profile management"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        # Import here to avoid circular imports
        from .serializers import UserProfileSerializer
        return UserProfileSerializer

    @action(detail=False, methods=['get'], url_path='me')
    def get_my_profile(self, request):
        """Get current user's profile"""
        profile = get_object_or_404(UserProfile, user=request.user)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(profile)
        return Response(serializer.data)

    @action(detail=False, methods=['put', 'patch'], url_path='me')
    def update_my_profile(self, request):
        """Update current user's profile"""
        profile = get_object_or_404(UserProfile, user=request.user)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(profile, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            # Create activity for profile update
            Activity.objects.create(
                user=request.user,
                activity_type='other',
                title='Profile updated',
                description='User profile information was updated',
                metadata={'updated_fields': list(request.data.keys())}
            )

            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['get'], url_path='transferred_animals')
    def transferred_animals(self, request):
        """Return animals transferred to the processing unit of the current user"""
        user = request.user
        if not hasattr(user, 'profile') or user.profile.role != 'processing_unit':
            return Response({'error': 'Only processing unit users can access this endpoint'}, status=status.HTTP_403_FORBIDDEN)

        processing_unit = user.profile.processing_unit
        if not processing_unit:
            return Response({'error': 'User not associated with a processing unit'}, status=status.HTTP_400_BAD_REQUEST)

        animals = Animal.objects.filter(transferred_to=processing_unit).select_related('farmer', 'transferred_to')
        serializer = self.get_serializer(animals, many=True)
        return Response({'animals': serializer.data, 'count': len(serializer.data), 'processing_unit': {'id': processing_unit.id, 'name': processing_unit.name}}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='my_transferred_animals')
    def my_transferred_animals(self, request):
        """Return animals transferred by the current farmer"""
        user = request.user
        if not hasattr(user, 'profile') or user.profile.role != 'farmer':
            return Response({'error': 'Only farmers can access this endpoint'}, status=status.HTTP_403_FORBIDDEN)

        animals = Animal.objects.filter(farmer=user, transferred_to__isnull=False).select_related('farmer', 'transferred_to')
        serializer = self.get_serializer(animals, many=True)
        return Response({'animals': serializer.data, 'count': len(serializer.data)}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put', 'patch'], url_path='slaughter')
    def slaughter(self, request, pk=None):
        """Mark an animal as slaughtered"""
        animal = get_object_or_404(Animal, pk=pk)
        if animal.slaughtered:
            return Response({'error': 'Animal already slaughtered'}, status=status.HTTP_400_BAD_REQUEST)

        animal.slaughtered = True
        animal.slaughtered_at = timezone.now()
        animal.save()

        # Create activity for slaughter
        Activity.objects.create(
            user=request.user,
            activity_type='slaughter',
            title=f'Animal {animal.animal_name or animal.animal_id} slaughtered',
            description=f'Slaughtered {animal.species} with ID {animal.animal_id}',
            entity_id=str(animal.id),
            entity_type='animal',
            metadata={'animal_id': animal.animal_id, 'species': animal.species}
        )

        return Response(self.get_serializer(animal).data, status=status.HTTP_200_OK)


class CarcassMeasurementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CarcassMeasurement.
    This endpoint automatically marks the associated animal as slaughtered.
    """
    queryset = CarcassMeasurement.objects.all()
    serializer_class = CarcassMeasurementSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """
        Custom create logic to mark animal as slaughtered and create slaughter parts.
        """
        animal = serializer.validated_data['animal']

        # 1. Check permissions
        if animal.farmer != self.request.user:
            raise PermissionDenied("You do not own this animal.")

        # 2. Check if animal is already slaughtered
        if animal.slaughtered:
            raise ValidationError(f"Animal {animal.animal_id} is already slaughtered.")

        # 3. Save the measurement
        measurement = serializer.save()

        # 4. Mark animal as slaughtered
        animal.slaughtered = True
        animal.slaughtered_at = timezone.now()
        animal.save(update_fields=['slaughtered', 'slaughtered_at'])

        # 5. Create SlaughterPart records from the measurement
        try:
            from .utils.carcass_parts import create_slaughter_parts_from_measurement
            create_slaughter_parts_from_measurement(animal, measurement)
        except Exception as e:
            # If part creation fails, we should still proceed but maybe log it
            print(f"WARNING: Could not create slaughter parts for animal {animal.id}: {e}")

        # 6. Create an activity log
        Activity.objects.create(
            user=self.request.user,
            activity_type='slaughter',
            title=f'Animal {animal.animal_name or animal.animal_id} slaughtered',
            description=f'Slaughtered {animal.species} with ID {animal.animal_id} and recorded carcass measurements.',
            entity_id=str(animal.id),
            entity_type='animal',
            metadata={
                'animal_id': animal.animal_id,
                'carcass_measurement_id': measurement.id,
                'carcass_type': measurement.carcass_type,
            }
        )


class ProcessingUnitViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Processing Units."""
    queryset = ProcessingUnit.objects.all()
    serializer_class = ProcessingUnitSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        processing_unit = serializer.save()
        # Assign creator as owner
        ProcessingUnitUser.objects.create(
            user=self.request.user,
            processing_unit=processing_unit,
            role='owner',
            is_active=True,
            invited_by=self.request.user,
            joined_at=timezone.now()
        )
        # Update user profile
        profile = self.request.user.profile
        profile.processing_unit = processing_unit
        profile.save()

    def get_queryset(self):
        """
        Optionally restricts the returned purchases to a given user,
        by filtering against a `username` query parameter in the URL.
        """
        user = self.request.user
        print(f"[PROCESSING_UNIT_VIEWSET] get_queryset called for user {user.username} (ID: {user.id})")

        # Check if user has profile
        if hasattr(user, 'profile'):
            print(f"[PROCESSING_UNIT_VIEWSET] User has profile with role: {user.profile.role}")
        else:
            print(f"[PROCESSING_UNIT_VIEWSET] User has no profile")

        if user.is_staff:
            print(f"[PROCESSING_UNIT_VIEWSET] User is staff, returning all processing units")
            return ProcessingUnit.objects.all()

        # Farmers should see all processing units
        if hasattr(user, 'profile') and user.profile.role == 'farmer':
            print(f"[PROCESSING_UNIT_VIEWSET] User is farmer, returning all processing units")
            return ProcessingUnit.objects.all()

        # If the user is a processing unit user, they should see their unit
        if hasattr(user, 'profile') and user.profile.role == 'processing_unit':
            if user.profile.processing_unit:
                print(f"[PROCESSING_UNIT_VIEWSET] User is processing_unit, returning their unit (ID: {user.profile.processing_unit.pk})")
                return ProcessingUnit.objects.filter(pk=user.profile.processing_unit.pk)
            else:
                print(f"[PROCESSING_UNIT_VIEWSET] User is processing_unit but has no associated unit")
                return ProcessingUnit.objects.none()

        # Allow farmers to view all processing units
        if hasattr(user, 'profile') and user.profile.role == 'farmer':
            print(f"[PROCESSING_UNIT_VIEWSET] User is farmer, returning all processing units")
            return ProcessingUnit.objects.all()

        print(f"[PROCESSING_UNIT_VIEWSET] User role not recognized or no profile, returning none")
        return ProcessingUnit.objects.none()

    @action(detail=True, methods=['post'], url_path='suspend-user')
    def suspend_user(self, request, pk=None):
        """Suspend a user from a processing unit."""
        processing_unit = self.get_object()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        pu_user = get_object_or_404(ProcessingUnitUser, user_id=user_id, processing_unit=processing_unit)
        pu_user.is_active = False
        pu_user.save()

        return Response({'status': 'user suspended'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='activate-user')
    def activate_user(self, request, pk=None):
        """Activate a user in a processing unit."""
        processing_unit = self.get_object()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        pu_user = get_object_or_404(ProcessingUnitUser, user_id=user_id, processing_unit=processing_unit)
        pu_user.is_active = True
        pu_user.save()

        return Response({'status': 'user activated'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='users')
    def users(self, request, pk=None):
        """Return list of users associated with this processing unit.

        This returns a minimal user summary used by the frontend settings screen.
        """
        processing_unit = self.get_object()
        pu_users = ProcessingUnitUser.objects.filter(processing_unit=processing_unit).select_related('user')
        users_list = []
        for pu in pu_users:
            profile = None
            try:
                profile = pu.user.profile
            except Exception:
                profile = None

            users_list.append({
                'id': pu.user.id,
                'username': pu.user.username,
                'email': pu.user.email,
                'first_name': pu.user.first_name,
                'last_name': pu.user.last_name,
                'role': profile.role if profile else None,
                'pu_role': pu.role,
                'is_active': pu.is_active,
                'joined_at': pu.joined_at.isoformat() if getattr(pu, 'joined_at', None) else None,
            })

        return Response({'processing_unit': {'id': processing_unit.id, 'name': processing_unit.name}, 'users': users_list, 'count': len(users_list)}, status=status.HTTP_200_OK)


# Custom endpoints for join request creation and review
class JoinRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, entity_id, request_type):
        # Validate request type
        if request_type not in ['processing_unit', 'shop']:
            return Response({'error': 'Invalid request type'}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        requested_role = data.get('requested_role')
        message = data.get('message', '')
        qualifications = data.get('qualifications', '')

        if not requested_role:
            return Response({'error': 'requested_role is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine entity and create join request
        if request_type == 'processing_unit':
            entity = get_object_or_404(ProcessingUnit, pk=entity_id)
            join_request = JoinRequest.objects.create(
                user=request.user,
                request_type='processing_unit',
                processing_unit=entity,
                requested_role=requested_role,
                message=message,
                qualifications=qualifications,
                status='pending',
                expires_at=timezone.now()
            )
            # Notify owners
            owners = ProcessingUnitUser.objects.filter(processing_unit=entity, role='owner', is_active=True)
            for pu in owners:
                Notification.objects.create(
                    user=pu.user,
                    notification_type='join_request',
                    title='New join request',
                    message=f'{request.user.username} requested to join processing unit {entity.name}',
                    data={'join_request_id': join_request.id}
                )
        else:
            entity = get_object_or_404(Shop, pk=entity_id)
            join_request = JoinRequest.objects.create(
                user=request.user,
                request_type='shop',
                shop=entity,
                requested_role=requested_role,
                message=message,
                qualifications=qualifications,
                status='pending',
                expires_at=timezone.now()
            )
            # Notify owners
            owners = ShopUser.objects.filter(shop=entity, role='owner', is_active=True)
            for su in owners:
                Notification.objects.create(
                    user=su.user,
                    notification_type='join_request',
                    title='New join request',
                    message=f'{request.user.username} requested to join shop {entity.name}',
                    data={'join_request_id': join_request.id}
                )

        return Response(status=status.HTTP_201_CREATED)

class JoinRequestReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, request_id):
        data = request.data
        new_status = data.get('status')
        response_message = data.get('response_message', '')

        join_request = get_object_or_404(JoinRequest, pk=request_id)
        if join_request.status != 'pending':
            return Response({'error': 'Join request has already been reviewed'}, status=status.HTTP_400_BAD_REQUEST)

        # Authorization
        if join_request.request_type == 'processing_unit':
            if not ProcessingUnitUser.objects.filter(user=request.user, processing_unit=join_request.processing_unit).exists():
                return Response({'error': 'Not authorized to review this join request'}, status=status.HTTP_403_FORBIDDEN)
        else:
            if not ShopUser.objects.filter(user=request.user, shop=join_request.shop).exists():
                return Response({'error': 'Not authorized to review this join request'}, status=status.HTTP_403_FORBIDDEN)

        if new_status not in ['approved', 'rejected']:
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        join_request.status = new_status
        join_request.response_message = response_message
        join_request.reviewed_by = request.user
        join_request.reviewed_at = timezone.now()
        join_request.save()

        # Handle approval
        if new_status == 'approved':
            if join_request.request_type == 'processing_unit':
                ProcessingUnitUser.objects.get_or_create(
                    user=join_request.user,
                    processing_unit=join_request.processing_unit,
                    defaults={'role': join_request.requested_role}
                )
                profile = join_request.user.profile
                profile.processing_unit = join_request.processing_unit
                profile.save()
            else:
                ShopUser.objects.get_or_create(
                    user=join_request.user,
                    shop=join_request.shop,
                    defaults={'role': join_request.requested_role}
                )
                profile = join_request.user.profile
                profile.shop = join_request.shop
                profile.save()

            notif_type = 'join_approved'
            title = 'Join request approved'
        else:
            notif_type = 'join_rejected'
            title = 'Join request rejected'

        Notification.objects.create(
            user=join_request.user,
            notification_type=notif_type,
            title=title,
            message=response_message,
            data={'join_request_id': join_request.id}
        )

        return Response(status=status.HTTP_200_OK)

class JoinRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for users to request to join a Processing Unit.
    """
    queryset = JoinRequest.objects.all()
    serializer_class = JoinRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Users can see their own join requests.
        # Processing unit admins can see requests for their unit.
        if hasattr(user, 'profile') and user.profile.role == 'processing_unit' and user.profile.processing_unit:
            return JoinRequest.objects.filter(processing_unit=user.profile.processing_unit)
        return JoinRequest.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """
        Approve a join request and add the user to the processing unit.
        Authorization: requester must be a member of the target processing unit.
        """
        join_request = self.get_object()

        if join_request.request_type != 'processing_unit' or not join_request.processing_unit:
            return Response({'error': 'Only processing unit join requests can be approved'}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure approver is a member of the target processing unit
        if not ProcessingUnitUser.objects.filter(user=request.user, processing_unit=join_request.processing_unit).exists():
            return Response({'error': 'Not authorized to approve this join request'}, status=status.HTTP_403_FORBIDDEN)

        # Update request status
        join_request.status = 'approved'
        join_request.reviewed_by = request.user
        join_request.reviewed_at = timezone.now()
        join_request.save()

        # Create membership if it doesn't exist
        ProcessingUnitUser.objects.get_or_create(
            user=join_request.user,
            processing_unit=join_request.processing_unit,
            defaults={'role': join_request.requested_role or 'worker'}
        )

        return Response({'message': 'Join request approved.'}, status=status.HTTP_200_OK)


class ShopViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Shops."""
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return shops based on user role and permissions.
        """
        user = self.request.user
        if user.is_staff:
            return Shop.objects.all()
        
        # If the user is a shop user, they should see their shop
        if hasattr(user, 'profile') and user.profile.role == 'shop':
            if user.profile.shop:
                return Shop.objects.filter(pk=user.profile.shop.pk)
        
        # If the user is a shop user, they should see their shop
        if hasattr(user, 'profile') and user.profile.role == 'shop':
            if user.profile.shop:
                return Shop.objects.filter(pk=user.profile.shop.pk)
        
        return Shop.objects.none()


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Orders."""
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return orders based on user role and permissions.
        """
        user = self.request.user
        queryset = Order.objects.all().select_related('customer', 'shop')
        
        # Customers see their own orders
        if hasattr(user, 'profile') and user.profile.role == 'shop':
            shop = user.profile.shop
            if shop:
                queryset = queryset.filter(shop=shop)
        else:
            queryset = queryset.filter(customer=user)
        
        return queryset.order_by('-created_at')


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Products with public access for listing."""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return products with optional filtering by processing_unit.
        """
        queryset = Product.objects.all().select_related('processing_unit', 'animal')
        
        # Filter by processing_unit if provided
        processing_unit_id = self.request.query_params.get('processing_unit')
        if processing_unit_id:
            queryset = queryset.filter(processing_unit_id=processing_unit_id)
        
        return queryset.order_by('-created_at')

class ProductCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Product Categories."""
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return all product categories.
        """
        return ProductCategory.objects.all().order_by('name')


# ═════════════════════════════════════════════════════════════════════════════=
# PROCESSING UNIT DASHBOARD VIEWS
# ═════════════════════════════════════════════════════════════════════════════=

@login_required
def add_product_category(request):
    """
    View for processing unit users to add a new product category.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not name:
            return render(request, 'meat_trace/processor_dashboard/add_product_category.html', {
                'error': 'Category name is required',
                'name': name,
                'description': description
            })
        
        # Check if category already exists
        if ProductCategory.objects.filter(name__iexact=name).exists():
            return render(request, 'meat_trace/processor_dashboard/add_product_category.html', {
                'error': f'Category "{name}" already exists',
                'name': name,
                'description': description
            })
        
        # Create the category
        category = ProductCategory.objects.create(
            name=name,
            description=description
        )
        
        # Create activity log
        Activity.objects.create(
            user=request.user,
            activity_type='other',
            title='Product category created',
            description=f'Created new product category: {name}',
            metadata={'category_id': category.id, 'category_name': name}
        )
        
        return render(request, 'meat_trace/processor_dashboard/add_product_category.html', {
            'success': f'Category "{name}" created successfully!',
            'category': category
        })
    
    # GET request - show the form
def product_info_view(request, product_id):
    """
    HTML view for displaying detailed product information.
    Accessible at /api/v2/product-info/view/{product_id}/
    """
    print(f"[DEBUG] product_info_view called with product_id: {product_id}")

    try:
        # Get the product with related data
        product = Product.objects.select_related(
            'animal', 'processing_unit', 'category'
        ).get(id=product_id)
        print(f"[DEBUG] Found product: {product.name} (ID: {product.id})")

        # Get animal information if available
        animal = product.animal if product.animal else None
        print(f"[DEBUG] Product has animal: {animal.animal_id if animal else 'None'}")

        # Get QR code URL if available
        qr_code_url = product.qr_code if product.qr_code else None
        print(f"[DEBUG] Product QR code: {qr_code_url}")

        # Build timeline events
        timeline = []
        print("[DEBUG] Building timeline...")

        # Product creation event
        timeline.append({
            'stage': 'Product Created',
            'timestamp': product.created_at,
            'location': product.processing_unit.name if product.processing_unit else 'Unknown',
            'action': f'Product {product.name} created',
            'details': {
                'Product Type': product.product_type,
                'Batch Number': product.batch_number,
                'Weight': f"{product.weight} {product.weight_unit}" if product.weight else 'Not recorded',
                'Quantity': f"{product.quantity} {product.weight_unit}" if product.quantity else 'Not recorded'
            }
        })

        # Add animal-related events if animal exists
        if animal:
            # Animal registration
            timeline.append({
                'stage': 'Source Animal',
                'timestamp': animal.created_at,
                'location': animal.farmer.username,
                'action': f'Animal {animal.animal_id} registered',
                'details': {
                    'Species': animal.species,
                    'Farmer': animal.farmer.username,
                    'Weight': f"{animal.weight_kg} kg" if animal.weight_kg else 'Not recorded'
                }
            })

            # Slaughter event if applicable
            if animal.slaughtered and animal.slaughtered_at:
                timeline.append({
                    'stage': 'Slaughter',
                    'timestamp': animal.slaughtered_at,
                    'location': 'Processing Unit',
                    'action': f'Animal {animal.animal_id} slaughtered',
                    'details': {
                        'Species': animal.species,
                        'Slaughter Date': animal.slaughtered_at.strftime('%Y-%m-%d %H:%M')
                    }
                })

            # Transfer event if applicable
            if animal.transferred_at:
                timeline.append({
                    'stage': 'Transfer',
                    'timestamp': animal.transferred_at,
                    'location': animal.transferred_to.name if animal.transferred_to else 'Unknown',
                    'action': f'Animal transferred to {animal.transferred_to.name if animal.transferred_to else "processing unit"}',
                    'details': {
                        'From': animal.farmer.username,
                        'To': animal.transferred_to.name if animal.transferred_to else 'Processing Unit',
                        'Transfer Mode': 'Whole carcass' if not hasattr(animal, 'slaughter_parts') or not animal.slaughter_parts.exists() else 'Parts'
                    }
                })

        # Sort timeline by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        print(f"[DEBUG] Timeline built with {len(timeline)} events")

        # Get inventory items for this product
        inventory_items = Inventory.objects.filter(product=product).select_related('shop')
        print(f"[DEBUG] Found {inventory_items.count()} inventory items")

        # Get receipts for this product
        receipts = Receipt.objects.filter(product=product).select_related('shop')
        print(f"[DEBUG] Found {receipts.count()} receipts")

        # Get order items for this product
        order_items = OrderItem.objects.filter(product=product).select_related('order', 'order__customer', 'order__shop')
        print(f"[DEBUG] Found {order_items.count()} order items")

        # Get carcass measurement if available
        carcass_measurement = None
        if animal and hasattr(animal, 'carcass_measurement'):
            carcass_measurement = animal.carcass_measurement
            print(f"[DEBUG] Found carcass measurement: {carcass_measurement}")

        context = {
            'product': product,
            'animal': animal,
            'qr_code_url': qr_code_url,
            'timeline': timeline,
            'inventory_items': inventory_items,
            'receipts': receipts,
            'order_items': order_items,
            'carcass_measurement': carcass_measurement,
        }

        print(f"[DEBUG] Rendering product_info.html template for product {product_id}")
        return render(request, 'meat_trace/product_info.html', context)

    except Product.DoesNotExist:
        print(f"[DEBUG] Product with ID {product_id} not found")
        return render(request, 'meat_trace/product_info.html', {
            'error': f'Product with ID {product_id} not found',
            'product_id': product_id
        })
    except Exception as e:
        print(f"[DEBUG] Error in product_info_view: {str(e)}")
        import traceback
        traceback.print_exc()
        return render(request, 'meat_trace/product_info.html', {
            'error': f'An error occurred: {str(e)}',
            'product_id': product_id
        })
    return render(request, 'meat_trace/processor_dashboard/add_product_category.html')

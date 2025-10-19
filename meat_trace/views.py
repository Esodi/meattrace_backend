from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import models
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage, ProductTimelineEvent, Inventory, Order, OrderItem, CarcassMeasurement, SlaughterPart, ProcessingUnit, ProcessingUnitUser, ProductIngredient, Shop, ShopUser, UserAuditLog, JoinRequest, Notification, Activity
from .serializers import AnimalSerializer, ProductSerializer, ReceiptSerializer, ProductCategorySerializer, ProcessingStageSerializer, ProductTimelineEventSerializer, InventorySerializer, OrderSerializer, OrderItemSerializer, CarcassMeasurementSerializer, SlaughterPartSerializer, ProcessingUnitSerializer, ProcessingUnitUserSerializer, ProductIngredientSerializer, ShopSerializer, ShopUserSerializer, UserAuditLogSerializer, JoinRequestSerializer, NotificationSerializer, ActivitySerializer
from .permissions import IsFarmer, IsProcessingUnit, IsShop, IsOwnerOrReadOnly, IsProcessingUnitOwner, IsShopOwner
import logging
import uuid

logger = logging.getLogger(__name__)

# User Management Views for Processing Units NN

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_user_to_processing_unit(request, processing_unit_id):
    """
    Invite a new user to join a processing unit.
    Only owners and managers can invite users.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member of this processing unit
        try:
            membership = ProcessingUnitUser.objects.get(
                user=request.user,
                processing_unit=processing_unit,
                is_active=True
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        # Check permissions - only owners and managers can invite
        if membership.role not in ['owner', 'manager']:
            return Response({'error': 'Only owners and managers can invite users'}, status=status.HTTP_403_FORBIDDEN)

        # Get invitation data
        email = request.data.get('email')
        role = request.data.get('role', 'worker')
        custom_message = request.data.get('message', '')

        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate role
        valid_roles = ['owner', 'manager', 'supervisor', 'worker', 'quality_control']
        if role not in valid_roles:
            return Response({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already exists
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            # Check if already a member
            if ProcessingUnitUser.objects.filter(
                user=existing_user,
                processing_unit=processing_unit
            ).exists():
                return Response({'error': 'User is already a member of this processing unit'}, status=status.HTTP_400_BAD_REQUEST)

        # Create invitation record
        invitation_token = str(uuid.uuid4())

        # If user doesn't exist, we'll create a placeholder invitation
        # In a real implementation, you'd send an email with the invitation link
        invitation_data = {
            'processing_unit': processing_unit,
            'invited_by': request.user,
            'email': email,
            'role': role,
            'invitation_token': invitation_token,
            'custom_message': custom_message,
            'status': 'pending'
        }

        # For now, create a ProcessingUnitUser with joined_at=None to indicate pending invitation
        membership = ProcessingUnitUser.objects.create(
            user=existing_user if existing_user else None,  # Will be None for new users
            processing_unit=processing_unit,
            role=role,
            invited_by=request.user,
            invited_at=timezone.now(),
            joined_at=None,  # Indicates pending invitation
            is_active=False  # Not active until they accept
        )

        # Create audit log
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=existing_user if existing_user else None,
            processing_unit=processing_unit,
            action='user_invited',
            description=f'Invited user {email} to join as {role}',
            old_values={},
            new_values={'email': email, 'role': role, 'message': custom_message},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            metadata={'invitation_token': invitation_token}
        )

        # In a real implementation, send invitation email here
        # send_invitation_email(email, invitation_token, processing_unit.name, custom_message)

        response_data = {
            'message': f'Invitation sent to {email}',
            'invitation_id': membership.id,
            'role': role,
            'email': email
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error inviting user to processing unit: {str(e)}")
        return Response({'error': 'Failed to send invitation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def accept_processing_unit_invitation(request, membership_id):
    """
    Accept a processing unit invitation.
    This endpoint can be used by both existing and new users.
    """
    try:
        # Get the membership
        try:
            membership = ProcessingUnitUser.objects.get(id=membership_id)
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Invitation not found'}, status=status.HTTP_404_NOT_FOUND)

        if membership.joined_at is not None:
            return Response({'error': 'Invitation has already been accepted'}, status=status.HTTP_400_BAD_REQUEST)

        # Get user data
        username = request.data.get('username')
        password = request.data.get('password')
        email = membership.email or request.data.get('email')

        if not username or not password:
            return Response({'error': 'Username and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        if membership.user:
            # Existing user - just activate membership
            user = membership.user
        else:
            # New user - create account
            if User.objects.filter(username=username).exists():
                return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(email=email).exists():
                return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)

            # Create new user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            # Create user profile
            UserProfile.objects.create(
                user=user,
                role='ProcessingUnit',
                processing_unit=membership.processing_unit
            )

        # Activate membership
        membership.user = user
        membership.joined_at = timezone.now()
        membership.is_active = True
        membership.save()

        # Update user profile - ensure the user is linked to their processing unit
        profile = user.profile
        profile.role = 'ProcessingUnit'
        profile.processing_unit = membership.processing_unit  # This is crucial for linking the user to their unit
        profile.save()

        # Create audit log
        UserAuditLog.objects.create(
            performed_by=membership.invited_by,
            affected_user=user,
            processing_unit=membership.processing_unit,
            action='user_joined',
            description=f'User {user.username} joined processing unit {membership.processing_unit.name} as {membership.role}',
            old_values={'status': 'invited'},
            new_values={'status': 'active', 'joined_at': membership.joined_at.isoformat()},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        # Generate tokens for new users
        if not membership.user:  # New user
            refresh = RefreshToken.for_user(user)
            response_data = {
                'message': f'Successfully joined {membership.processing_unit.name}',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': 'ProcessingUnit'
                },
                'processing_unit': {
                    'id': membership.processing_unit.id,
                    'name': membership.processing_unit.name,
                    'role': membership.role
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }
            }
        else:
            response_data = {
                'message': f'Successfully joined {membership.processing_unit.name}',
                'processing_unit': {
                    'id': membership.processing_unit.id,
                    'name': membership.processing_unit.name,
                    'role': membership.role
                }
            }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error accepting processing unit invitation: {str(e)}")
        return Response({'error': 'Failed to accept invitation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def decline_processing_unit_invitation(request, membership_id):
    """
    Decline a processing unit invitation.
    """
    try:
        # Get the membership
        try:
            membership = ProcessingUnitUser.objects.get(id=membership_id)
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Invitation not found'}, status=status.HTTP_404_NOT_FOUND)

        if membership.joined_at is not None:
            return Response({'error': 'Invitation has already been processed'}, status=status.HTTP_400_BAD_REQUEST)

        # Create audit log before deleting
        UserAuditLog.objects.create(
            performed_by=membership.invited_by,
            affected_user=membership.user,
            processing_unit=membership.processing_unit,
            action='user_invitation_declined',
            description=f'User declined invitation to join {membership.processing_unit.name}',
            old_values={'status': 'invited'},
            new_values={'status': 'declined'},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        # Delete the membership
        membership.delete()

        return Response({'message': 'Invitation declined successfully'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error declining processing unit invitation: {str(e)}")
        return Response({'error': 'Failed to decline invitation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processing_unit_members(request, processing_unit_id):
    """
    Get all members of a processing unit.
    Only members of the processing unit can view this.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member
        if not ProcessingUnitUser.objects.filter(
            user=request.user,
            processing_unit=processing_unit,
            is_active=True
        ).exists():
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        # Get all members
        members = ProcessingUnitUser.objects.filter(
            processing_unit=processing_unit
        ).select_related('user', 'invited_by').order_by('-joined_at')

        serializer = ProcessingUnitUserSerializer(members, many=True)
        return Response({
            'processing_unit': {
                'id': processing_unit.id,
                'name': processing_unit.name
            },
            'members': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting processing unit members: {str(e)}")
        return Response({'error': 'Failed to get members'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_processing_unit_member(request, processing_unit_id, member_id):
    """
    Update a member's role and permissions.
    Only owners and managers can update members.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member with permission to manage users
        try:
            current_membership = ProcessingUnitUser.objects.get(
                user=request.user,
                processing_unit=processing_unit,
                is_active=True
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        if current_membership.role not in ['owner', 'manager']:
            return Response({'error': 'Only owners and managers can update member roles'}, status=status.HTTP_403_FORBIDDEN)

        # Get the target member
        try:
            member = ProcessingUnitUser.objects.get(
                id=member_id,
                processing_unit=processing_unit
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)

        # Store old values for audit
        old_values = {
            'role': member.role,
            'permissions': member.permissions,
            'granular_permissions': member.granular_permissions,
            'is_suspended': member.is_suspended
        }

        # Update fields
        role = request.data.get('role')
        permissions = request.data.get('permissions')
        granular_permissions = request.data.get('granular_permissions')
        is_suspended = request.data.get('is_suspended')
        suspension_reason = request.data.get('suspension_reason')

        if role is not None:
            valid_roles = ['owner', 'manager', 'supervisor', 'worker', 'quality_control']
            if role not in valid_roles:
                return Response({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}, status=status.HTTP_400_BAD_REQUEST)
            member.role = role

        if permissions is not None:
            valid_permissions = ['read', 'write', 'admin']
            if permissions not in valid_permissions:
                return Response({'error': f'Invalid permissions. Must be one of: {", ".join(valid_permissions)}'}, status=status.HTTP_400_BAD_REQUEST)
            member.permissions = permissions

        if granular_permissions is not None:
            member.granular_permissions = granular_permissions

        if is_suspended is not None:
            member.is_suspended = is_suspended
            if is_suspended:
                member.suspension_date = timezone.now()
                member.suspension_reason = suspension_reason or 'No reason provided'
            else:
                member.suspension_date = None
                member.suspension_reason = ''

        member.save()

        # Create audit log
        action = 'user_suspended' if member.is_suspended else 'user_unsuspended' if is_suspended is False else 'role_changed'
        description = f'Updated member {member.user.username}: role={member.role}, permissions={member.permissions}'

        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=member.user,
            processing_unit=processing_unit,
            action=action,
            description=description,
            old_values=old_values,
            new_values={
                'role': member.role,
                'permissions': member.permissions,
                'granular_permissions': member.granular_permissions,
                'is_suspended': member.is_suspended,
                'suspension_reason': member.suspension_reason
            },
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        serializer = ProcessingUnitUserSerializer(member)
        return Response({
            'message': 'Member updated successfully',
            'member': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error updating processing unit member: {str(e)}")
        return Response({'error': 'Failed to update member'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_processing_unit_member(request, processing_unit_id, member_id):
    """
    Remove a member from a processing unit.
    Only owners and managers can remove members.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member with permission to manage users
        try:
            current_membership = ProcessingUnitUser.objects.get(
                user=request.user,
                processing_unit=processing_unit,
                is_active=True
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        if current_membership.role not in ['owner', 'manager']:
            return Response({'error': 'Only owners and managers can remove members'}, status=status.HTTP_403_FORBIDDEN)

        # Get the target member
        try:
            member = ProcessingUnitUser.objects.get(
                id=member_id,
                processing_unit=processing_unit
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)

        # Cannot remove yourself
        if member.user == request.user:
            return Response({'error': 'You cannot remove yourself from the processing unit'}, status=status.HTTP_400_BAD_REQUEST)

        # Store member info for audit log
        member_info = {
            'user_id': member.user.id,
            'username': member.user.username,
            'role': member.role
        }

        # Create audit log before deleting
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=member.user,
            processing_unit=processing_unit,
            action='user_removed',
            description=f'Removed user {member.user.username} from processing unit {processing_unit.name}',
            old_values=member_info,
            new_values={'status': 'removed'},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        # Delete the membership
        member.delete()

        return Response({
            'message': f'Successfully removed {member_info["username"]} from {processing_unit.name}'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error removing processing unit member: {str(e)}")
        return Response({'error': 'Failed to remove member'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suspend_processing_unit_member(request, processing_unit_id, member_id):
    """
    Suspend a member from a processing unit.
    Only owners and managers can suspend members.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member with permission to manage users
        try:
            current_membership = ProcessingUnitUser.objects.get(
                user=request.user,
                processing_unit=processing_unit,
                is_active=True
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        if current_membership.role not in ['owner', 'manager']:
            return Response({'error': 'Only owners and managers can suspend members'}, status=status.HTTP_403_FORBIDDEN)

        # Get the target member
        try:
            member = ProcessingUnitUser.objects.get(
                id=member_id,
                processing_unit=processing_unit
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)

        if member.is_suspended:
            return Response({'error': 'Member is already suspended'}, status=status.HTTP_400_BAD_REQUEST)

        # Suspend the member
        member.is_suspended = True
        member.suspension_date = timezone.now()
        member.suspension_reason = request.data.get('reason', 'No reason provided')
        member.save()

        # Create audit log
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=member.user,
            processing_unit=processing_unit,
            action='user_suspended',
            description=f'Suspended user {member.user.username} from processing unit {processing_unit.name}',
            old_values={'is_suspended': False},
            new_values={
                'is_suspended': True,
                'suspension_reason': member.suspension_reason,
                'suspension_date': member.suspension_date.isoformat()
            },
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        serializer = ProcessingUnitUserSerializer(member)
        return Response({
            'message': f'Successfully suspended {member.user.username}',
            'member': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error suspending processing unit member: {str(e)}")
        return Response({'error': 'Failed to suspend member'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unsuspend_processing_unit_member(request, processing_unit_id, member_id):
    """
    Unsuspend a member from a processing unit.
    Only owners and managers can unsuspend members.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member with permission to manage users
        try:
            current_membership = ProcessingUnitUser.objects.get(
                user=request.user,
                processing_unit=processing_unit,
                is_active=True
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        if current_membership.role not in ['owner', 'manager']:
            return Response({'error': 'Only owners and managers can unsuspend members'}, status=status.HTTP_403_FORBIDDEN)

        # Get the target member
        try:
            member = ProcessingUnitUser.objects.get(
                id=member_id,
                processing_unit=processing_unit
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)

        if not member.is_suspended:
            return Response({'error': 'Member is not suspended'}, status=status.HTTP_400_BAD_REQUEST)

        # Unsuspend the member
        member.is_suspended = False
        member.suspension_date = None
        member.suspension_reason = ''
        member.save()

        # Create audit log
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_by=member.user,
            processing_unit=processing_unit,
            action='user_unsuspended',
            description=f'Unsuspended user {member.user.username} from processing unit {processing_unit.name}',
            old_values={'is_suspended': True, 'suspension_reason': member.suspension_reason},
            new_values={'is_suspended': False},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        serializer = ProcessingUnitUserSerializer(member)
        return Response({
            'message': f'Successfully unsuspended {member.user.username}',
            'member': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error unsuspending processing unit member: {str(e)}")
        return Response({'error': 'Failed to unsuspend member'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processing_unit_audit_logs(request, processing_unit_id):
    """
    Get audit logs for a processing unit.
    Only members of the processing unit can view logs.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member
        if not ProcessingUnitUser.objects.filter(
            user=request.user,
            processing_unit=processing_unit,
            is_active=True
        ).exists():
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        # Get query parameters
        action_filter = request.GET.get('action')
        user_filter = request.GET.get('user')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        limit = int(request.GET.get('limit', 50))

        # Build queryset
        queryset = UserAuditLog.objects.filter(processing_unit=processing_unit)

        if action_filter:
            queryset = queryset.filter(action=action_filter)

        if user_filter:
            queryset = queryset.filter(
                models.Q(performed_by__username__icontains=user_filter) |
                models.Q(affected_user__username__icontains=user_filter)
            )

        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)

        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)

        # Order by timestamp descending and limit
        queryset = queryset.select_related('performed_by', 'affected_user').order_by('-timestamp')[:limit]

        serializer = UserAuditLogSerializer(queryset, many=True)
        return Response({
            'processing_unit': {
                'id': processing_unit.id,
                'name': processing_unit.name
            },
            'audit_logs': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting processing unit audit logs: {str(e)}")
        return Response({'error': 'Failed to get audit logs'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processing_unit_member_permissions(request, processing_unit_id, member_id):
    """
    Get permissions for a specific member.
    Only members of the processing unit can view permissions.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member
        if not ProcessingUnitUser.objects.filter(
            user=request.user,
            processing_unit=processing_unit,
            is_active=True
        ).exists():
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        # Get the target member
        try:
            member = ProcessingUnitUser.objects.get(
                id=member_id,
                processing_unit=processing_unit
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)

        # Return permissions data
        permissions_data = {
            'member': {
                'id': member.id,
                'user': {
                    'id': member.user.id,
                    'username': member.user.username,
                    'email': member.user.email
                },
                'role': member.role,
                'permissions': member.permissions,
                'granular_permissions': member.granular_permissions,
                'is_suspended': member.is_suspended
            },
            'available_roles': ['owner', 'manager', 'supervisor', 'worker', 'quality_control'],
            'available_permissions': ['read', 'write', 'admin'],
            'role_permissions_matrix': {
                'owner': ['user_management', 'animal_operations', 'product_operations', 'inventory_management', 'reporting', 'settings'],
                'manager': ['user_management', 'animal_operations', 'product_operations', 'inventory_management', 'reporting'],
                'supervisor': ['animal_operations', 'product_operations', 'inventory_management', 'reporting'],
                'worker': ['animal_operations', 'product_operations'],
                'quality_control': ['product_operations', 'reporting']
            }
        }

        return Response(permissions_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting member permissions: {str(e)}")
        return Response({'error': 'Failed to get member permissions'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_processing_unit_member_permissions(request, processing_unit_id, member_id):
    """
    Update granular permissions for a member.
    Only owners and managers can update permissions.
    """
    try:
        # Get the processing unit
        try:
            processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
        except ProcessingUnit.DoesNotExist:
            return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is a member with permission to manage users
        try:
            current_membership = ProcessingUnitUser.objects.get(
                user=request.user,
                processing_unit=processing_unit,
                is_active=True
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'You are not a member of this processing unit'}, status=status.HTTP_403_FORBIDDEN)

        if current_membership.role not in ['owner', 'manager']:
            return Response({'error': 'Only owners and managers can update permissions'}, status=status.HTTP_403_FORBIDDEN)

        # Get the target member
        try:
            member = ProcessingUnitUser.objects.get(
                id=member_id,
                processing_unit=processing_unit
            )
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)

        # Store old values for audit
        old_permissions = member.granular_permissions.copy()

        # Update granular permissions
        granular_permissions = request.data.get('granular_permissions', {})
        member.granular_permissions = granular_permissions
        member.save()

        # Create audit log
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=member.user,
            processing_unit=processing_unit,
            action='granular_permissions_changed',
            description=f'Updated granular permissions for user {member.user.username}',
            old_values={'granular_permissions': old_permissions},
            new_values={'granular_permissions': granular_permissions},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        serializer = ProcessingUnitUserSerializer(member)
        return Response({
            'message': 'Permissions updated successfully',
            'member': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error updating member permissions: {str(e)}")
        return Response({'error': 'Failed to update permissions'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_processing_unit(request, membership_id):
    """
    Allow a user to leave a processing unit.
    """
    try:
        # Get the membership
        try:
            membership = ProcessingUnitUser.objects.get(id=membership_id)
        except ProcessingUnitUser.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user owns this membership
        if membership.user != request.user:
            return Response({'error': 'You can only leave your own memberships'}, status=status.HTTP_403_FORBIDDEN)

        # Check if user is the only owner
        if membership.role == 'owner':
            owner_count = ProcessingUnitUser.objects.filter(
                processing_unit=membership.processing_unit,
                role='owner',
                is_active=True
            ).count()

            if owner_count <= 1:
                return Response({
                    'error': 'You cannot leave as you are the only owner. Transfer ownership first or add another owner.'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Create audit log before deleting
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=request.user,
            processing_unit=membership.processing_unit,
            action='user_left',
            description=f'User {request.user.username} left processing unit {membership.processing_unit.name}',
            old_values={'role': membership.role, 'status': 'active'},
            new_values={'status': 'left'},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        # Store info for response
        unit_name = membership.processing_unit.name

        # Delete the membership
        membership.delete()

        return Response({
            'message': f'Successfully left {unit_name}'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error leaving processing unit: {str(e)}")
        return Response({'error': 'Failed to leave processing unit'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_client_ip(request):
    """
    Get the client IP address from the request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new user account.
    """
    logger.info(f"Registration attempt - Data: {request.data}")

    try:
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        role = request.data.get('role', 'Customer')  # Default role

        logger.info(f"Registration data - username: {username}, email: {email}, role: {role}")

        if not username or not email or not password:
            logger.warning("Registration failed: Missing required fields")
            return Response({'error': 'Username, email, and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate role
        valid_roles = ['Farmer', 'ProcessingUnit', 'Shop', 'Customer']
        if role not in valid_roles:
            logger.warning(f"Registration failed: Invalid role '{role}'")
            return Response({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            logger.warning(f"Registration failed: Username '{username}' already exists")
            return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            logger.warning(f"Registration failed: Email '{email}' already exists")
            return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Creating user: {username}")
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        logger.info(f"User created successfully: {user.id}")

        # Update user profile (created by signal) instead of creating new one
        try:
            profile = UserProfile.objects.get(user=user)
            profile.role = role
            profile.save()
            logger.info(f"UserProfile updated successfully for user {user.id} with role {role}")
        except UserProfile.DoesNotExist:
            logger.error(f"UserProfile not found for user {user.id}, creating manually")
            profile = UserProfile.objects.create(
                user=user,
                role=role
            )

        # Auto-create and associate ProcessingUnit or Shop based on role
        if role == 'ProcessingUnit':
            # Create a processing unit for this user
            processing_unit_name = request.data.get('processing_unit_name', f"{username}'s Processing Unit")
            processing_unit = ProcessingUnit.objects.create(
                name=processing_unit_name,
                description=f"Processing unit owned by {username}",
                contact_email=email,
                location=request.data.get('location', ''),
                contact_phone=request.data.get('phone', '')
            )
            logger.info(f"Created ProcessingUnit: {processing_unit.name} (ID: {processing_unit.id})")
            
            # Create membership as owner
            ProcessingUnitUser.objects.create(
                user=user,
                processing_unit=processing_unit,
                role='owner',
                permissions='admin',
                invited_by=user,
                invited_at=timezone.now(),
                joined_at=timezone.now(),
                is_active=True
            )
            logger.info(f"Created ProcessingUnitUser membership for {username} as owner")
            
            # Link profile to processing unit
            profile.processing_unit = processing_unit
            profile.save()
            logger.info(f"Linked profile to processing_unit: {processing_unit.name}")
            
        elif role == 'Shop':
            # Create a shop for this user
            shop_name = request.data.get('shop_name', f"{username}'s Shop")
            shop = Shop.objects.create(
                name=shop_name,
                description=f"Shop owned by {username}",
                contact_email=email,
                location=request.data.get('location', ''),
                contact_phone=request.data.get('phone', ''),
                is_active=True
            )
            logger.info(f"Created Shop: {shop.name} (ID: {shop.id})")
            
            # Create membership as owner
            ShopUser.objects.create(
                user=user,
                shop=shop,
                role='owner',
                permissions='admin',
                invited_by=user,
                invited_at=timezone.now(),
                joined_at=timezone.now(),
                is_active=True
            )
            logger.info(f"Created ShopUser membership for {username} as owner")
            
            # Link profile to shop
            profile.shop = shop
            profile.save()
            logger.info(f"Linked profile to shop: {shop.name}")

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        logger.info(f"Tokens generated for user {user.id}")

        response_data = {
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': role
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
        }

        logger.info(f"Registration successful for user {user.id}")
        return Response(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error registering user: {str(e)}", exc_info=True)
        return Response({'error': 'Failed to register user'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_file(request):
    """
    Upload a file (placeholder implementation).
    """
    try:
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # For now, just return success
        # In a real implementation, you'd save the file and process it
        response_data = {
            'message': 'File uploaded successfully',
            'filename': file_obj.name,
            'size': file_obj.size
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return Response({'error': 'Failed to upload file'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint.
    """
    return Response({'status': 'healthy', 'timestamp': timezone.now().isoformat()}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def server_info(request):
    """
    Server information endpoint.
    """
    import platform
    import django

    response_data = {
        'server': 'MeatTrace Backend',
        'version': '1.0.0',
        'django_version': django.get_version(),
        'python_version': platform.python_version(),
        'platform': platform.platform(),
        'timestamp': timezone.now().isoformat()
    }

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def meat_trace_list(request):
    """
    Get a list of meat trace records (placeholder).
    """
    # Placeholder implementation
    return Response({'message': 'Meat trace list endpoint'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categories_list(request):
    """
    Get a list of product categories.
    """
    try:
        categories = ProductCategory.objects.all()
        serializer = ProductCategorySerializer(categories, many=True)
        return Response({'categories': serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting categories: {str(e)}")
        return Response({'error': 'Failed to get categories'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Get current user profile information.
    """
    try:
        user = request.user
        profile = UserProfile.objects.get(user=user)

        response_data = {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined.isoformat()
            },
            'profile': {
                'role': profile.role,
                'processing_unit': profile.processing_unit.name if profile.processing_unit else None,
                'shop': profile.shop.name if profile.shop else None
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        return Response({'error': 'Failed to get user profile'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processing_units_list(request):
    """
    Get a list of processing units.
    """
    try:
        processing_units = ProcessingUnit.objects.all()
        serializer = ProcessingUnitSerializer(processing_units, many=True)
        return Response({'processing_units': serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting processing units: {str(e)}")
        return Response({'error': 'Failed to get processing units'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def shops_list(request):
    """
    Get a list of shops.
    """
    try:
        shops = Shop.objects.filter(is_active=True)
        serializer = ShopSerializer(shops, many=True)
        return Response({'shops': serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting shops: {str(e)}")
        return Response({'error': 'Failed to get shops'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def production_stats(request):
    """
    Get production statistics filtered by user role.
    """
    user = request.user
    
    try:
        # Get user's role
        user_role = user.profile.role if hasattr(user, 'profile') else None
        
        logger.info(f"📊 PRODUCTION_STATS - User: {user.username}, Role: {user_role}")
        
        # Filter data based on user role
        if user_role == 'Farmer':
            # Farmers see only their own animals
            total_animals = Animal.objects.filter(farmer=user).count()
            # Farmers don't have products/orders, so set to 0
            total_products = 0
            total_orders = 0
            
        elif user_role == 'ProcessingUnit':
            # Processing units see animals transferred to them
            processing_unit = user.profile.processing_unit
            if not processing_unit:
                # Try to get from active membership
                active_membership = ProcessingUnitUser.objects.filter(
                    user=user, is_active=True
                ).select_related('processing_unit').first()
                processing_unit = active_membership.processing_unit if active_membership else None
            
            if processing_unit:
                total_animals = Animal.objects.filter(transferred_to=processing_unit).count()
                total_products = Product.objects.filter(processing_unit=processing_unit).count() if hasattr(Product, 'processing_unit') else Product.objects.count()
                total_orders = 0  # Processing units don't have orders
            else:
                total_animals = 0
                total_products = 0
                total_orders = 0
                
        elif user_role == 'Shop':
            # Shops see products in their inventory
            shop = user.profile.shop
            if not shop:
                # Try to get from active membership
                active_membership = ShopUser.objects.filter(
                    user=user, is_active=True
                ).select_related('shop').first()
                shop = active_membership.shop if active_membership else None
            
            if shop:
                total_animals = 0  # Shops don't track individual animals
                total_products = Product.objects.filter(
                    Q(receipt__shop=shop) | Q(inventory__shop=shop)
                ).distinct().count()
                total_orders = Order.objects.filter(shop=shop).count()
            else:
                total_animals = 0
                total_products = 0
                total_orders = 0
        else:
            # Default: no filtering
            total_animals = Animal.objects.count()
            total_products = Product.objects.count()
            total_orders = Order.objects.count()
        
        response_data = {
            'total_animals': total_animals,
            'total_products': total_products,
            'total_orders': total_orders,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"📊 PRODUCTION_STATS - Response: {response_data}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ PRODUCTION_STATS - Error: {str(e)}", exc_info=True)
        # Return zero values on error
        return Response({
            'total_animals': 0,
            'total_products': 0,
            'total_orders': 0,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def yield_trends(request):
    """
    Get yield trends data (placeholder).
    """
    # Placeholder implementation
    return Response({'message': 'Yield trends endpoint'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def comparative_yield_trends(request):
    """
    Get comparative yield trends data (placeholder).
    """
    # Placeholder implementation
    return Response({'message': 'Comparative yield trends endpoint'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processing_pipeline(request):
    """
    Get processing pipeline information (placeholder).
    """
    # Placeholder implementation
    return Response({'message': 'Processing pipeline endpoint'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_info(request, product_id):
    """
    Get product information by ID.
    """
    try:
        product = Product.objects.get(id=product_id)
        serializer = ProductSerializer(product)

        # Check if request is for HTML view
        if 'view' in request.path:
            # Return HTML template (placeholder)
            from django.shortcuts import render
            return render(request, 'meat_trace/product_info.html', {'product': product})

        # Return JSON API response
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting product info: {str(e)}")
        return Response({'error': 'Failed to get product information'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def order_info(request, order_id):
    """
    Get order information by ID.
    """
    try:
        order = Order.objects.get(id=order_id)
        serializer = OrderSerializer(order)

        # Check if request is for HTML view
        if 'view' in request.path:
            # Return HTML template (placeholder)
            from django.shortcuts import render
            return render(request, 'meat_trace/order_info.html', {'order': order})

        # Return JSON API response
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting order info: {str(e)}")
        return Response({'error': 'Failed to get order information'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AnimalViewSet(viewsets.ModelViewSet):
    queryset = Animal.objects.all()
    serializer_class = AnimalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['species', 'farmer', 'slaughtered', 'processed']
    search_fields = ['animal_id', 'animal_name', 'breed', 'abbatoir_name']  # Removed 'farm_name' as it was removed from model
    ordering_fields = ['created_at', 'live_weight', 'age', 'slaughtered_at']
    pagination_class = None  # Disable pagination for animals

    @action(detail=False, methods=['post'], url_path='transfer')
    def transfer_animals(self, request):
        """
        Transfer animals or individual parts to a processing unit.
        Supports both whole carcass and split carcass (part-level) transfers.
        
        Request data:
        - animal_ids: list of animal IDs for whole carcass transfers
        - processing_unit_id: ID of the processing unit
        - part_transfers: optional list of {animal_id, part_ids} for split carcass part transfers
        """
        try:
            logger.info(f"BACKEND_TRANSFER_START - User: {request.user.username}, Data: {request.data}")

            animal_ids = request.data.get('animal_ids', [])
            processing_unit_id = request.data.get('processing_unit_id')
            part_transfers = request.data.get('part_transfers', [])  # [{animal_id: X, part_ids: [1,2,3]}]

            logger.info(f"BACKEND_TRANSFER_VALIDATION - animal_ids: {animal_ids}, part_transfers: {part_transfers}, processing_unit_id: {processing_unit_id}")

            if not animal_ids and not part_transfers:
                logger.warning("BACKEND_TRANSFER_ERROR - No animal_ids or part_transfers provided")
                return Response({'error': 'animal_ids or part_transfers are required'}, status=status.HTTP_400_BAD_REQUEST)

            if not processing_unit_id:
                logger.warning("BACKEND_TRANSFER_ERROR - No processing_unit_id provided")
                return Response({'error': 'processing_unit_id is required'}, status=status.HTTP_400_BAD_REQUEST)

            # Get the processing unit
            try:
                processing_unit = ProcessingUnit.objects.get(id=processing_unit_id)
                logger.info(f"BACKEND_TRANSFER_PROCESSING_UNIT_FOUND - {processing_unit.name}")
            except ProcessingUnit.DoesNotExist:
                logger.warning(f"BACKEND_TRANSFER_ERROR - Processing unit not found: {processing_unit_id}")
                return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)

            transferred_animals_count = 0
            transferred_parts_count = 0

            # Handle whole animal transfers (traditional flow)
            if animal_ids:
                animals = []
                logger.info(f"BACKEND_TRANSFER_ANIMAL_VALIDATION_START - Checking {len(animal_ids)} animals")
                for animal_id in animal_ids:
                    try:
                        animal = Animal.objects.get(id=animal_id, farmer=request.user)
                        logger.info(f"BACKEND_TRANSFER_ANIMAL_CHECK - Animal {animal_id} ({animal.animal_id}): transferred_to={animal.transferred_to}, processed={animal.processed}")

                        # Check if already transferred
                        if animal.transferred_to is not None:
                            if animal.transferred_to.id == processing_unit_id:
                                logger.warning(f"BACKEND_TRANSFER_DIAGNOSTIC - Animal {animal_id} already transferred to SAME processing unit {processing_unit_id}")
                                return Response({'error': f'Animal {animal.animal_id} has already been transferred to this processing unit'}, status=status.HTTP_400_BAD_REQUEST)
                            else:
                                logger.warning(f"BACKEND_TRANSFER_ERROR - Animal {animal_id} already transferred to DIFFERENT processing unit {animal.transferred_to.id}")
                                return Response({'error': f'Animal {animal.animal_id} has already been transferred to another processing unit'}, status=status.HTTP_400_BAD_REQUEST)

                        if animal.processed:
                            logger.warning(f"BACKEND_TRANSFER_ERROR - Animal {animal_id} already processed")
                            return Response({'error': f'Animal {animal.animal_id} has already been processed'}, status=status.HTTP_400_BAD_REQUEST)
                        animals.append(animal)
                    except Animal.DoesNotExist:
                        logger.warning(f"BACKEND_TRANSFER_ERROR - Animal not found or not owned by user: {animal_id}")
                        return Response({'error': f'Animal {animal_id} not found or not owned by you'}, status=status.HTTP_404_NOT_FOUND)

                # Transfer whole animals
                logger.info(f"BACKEND_TRANSFER_EXECUTION_START - Transferring {len(animals)} whole animals")
                for animal in animals:
                    animal.transferred_to = processing_unit
                    animal.transferred_at = timezone.now()
                    animal.save()
                    transferred_animals_count += 1
                    logger.info(f"BACKEND_TRANSFER_ANIMAL_TRANSFERRED - Animal {animal.animal_id} transferred successfully")

                    # Create audit log
                    UserAuditLog.objects.create(
                        performed_by=request.user,
                        affected_user=animal.farmer,
                        processing_unit=processing_unit,
                        action='animal_transferred',
                        description=f'Animal {animal.animal_id} transferred to processing unit {processing_unit.name}',
                        old_values={'transferred_to': None},
                        new_values={'transferred_to': processing_unit.id, 'transferred_at': animal.transferred_at.isoformat()},
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )

            # Handle part-level transfers for split carcasses
            if part_transfers:
                logger.info(f"BACKEND_TRANSFER_PARTS_START - Processing {len(part_transfers)} part transfer requests")
                for part_transfer in part_transfers:
                    animal_id = part_transfer.get('animal_id')
                    part_ids = part_transfer.get('part_ids', [])
                    
                    if not animal_id or not part_ids:
                        logger.warning(f"BACKEND_TRANSFER_ERROR - Invalid part_transfer data: {part_transfer}")
                        return Response({'error': 'Each part_transfer must have animal_id and part_ids'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Validate animal ownership
                    try:
                        animal = Animal.objects.get(id=animal_id, farmer=request.user)
                    except Animal.DoesNotExist:
                        logger.warning(f"BACKEND_TRANSFER_ERROR - Animal not found for part transfer: {animal_id}")
                        return Response({'error': f'Animal {animal_id} not found or not owned by you'}, status=status.HTTP_404_NOT_FOUND)
                    
                    # NEW VALIDATION: Check if animal is slaughtered before allowing part transfers
                    if not animal.slaughtered:
                        logger.warning(f"BACKEND_TRANSFER_ERROR - Animal {animal_id} not slaughtered yet, cannot transfer parts")
                        return Response({'error': f'Animal {animal.animal_id} must be slaughtered before transferring individual parts'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # NEW VALIDATION: Check if animal already transferred as whole
                    if animal.transferred_to is not None:
                        logger.warning(f"BACKEND_TRANSFER_ERROR - Animal {animal_id} already transferred as whole animal, cannot transfer parts")
                        return Response({'error': f'Animal {animal.animal_id} was already transferred as a whole animal. Cannot transfer individual parts.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # NEW VALIDATION: Check if animal has split carcass measurements
                    try:
                        carcass = animal.carcass_measurement
                        if carcass.carcass_type != 'split':
                            logger.warning(f"BACKEND_TRANSFER_ERROR - Animal {animal_id} is not a split carcass, cannot transfer parts")
                            return Response({'error': f'Animal {animal.animal_id} must have split carcass measurements before transferring individual parts'}, status=status.HTTP_400_BAD_REQUEST)
                    except CarcassMeasurement.DoesNotExist:
                        logger.warning(f"BACKEND_TRANSFER_ERROR - Animal {animal_id} has no carcass measurements")
                        return Response({'error': f'Animal {animal.animal_id} must have carcass measurements before transferring parts'}, status=status.HTTP_404_NOT_FOUND)
                    
                    # Validate and transfer parts
                    for part_id in part_ids:
                        try:
                            part = SlaughterPart.objects.get(id=part_id, animal=animal)
                            
                            # Check if part already transferred
                            if part.transferred_to is not None:
                                logger.warning(f"BACKEND_TRANSFER_ERROR - Part {part_id} already transferred")
                                return Response({'error': f'Part {part.part_type} of animal {animal.animal_id} has already been transferred'}, status=status.HTTP_400_BAD_REQUEST)
                            
                            # Transfer the part
                            part.transferred_to = processing_unit
                            part.transferred_at = timezone.now()
                            part.is_selected_for_transfer = True
                            part.save()
                            transferred_parts_count += 1
                            logger.info(f"BACKEND_TRANSFER_PART_TRANSFERRED - Part {part.part_type} of animal {animal.animal_id} transferred")
                            
                        except SlaughterPart.DoesNotExist:
                            logger.warning(f"BACKEND_TRANSFER_ERROR - Part not found: {part_id} for animal {animal_id}")
                            return Response({'error': f'Part {part_id} not found for animal {animal_id}'}, status=status.HTTP_404_NOT_FOUND)
                    
                    # Check if all parts of the animal have been transferred
                    all_parts = animal.slaughter_parts.all()
                    all_transferred = all(part.transferred_to is not None for part in all_parts)
                    
                    # Update animal's transferred_to status if all parts are transferred
                    if all_transferred and len(all_parts) > 0:
                        animal.transferred_to = processing_unit
                        animal.transferred_at = timezone.now()
                        animal.save()
                        logger.info(f"BACKEND_TRANSFER_ANIMAL_STATUS_UPDATED - All parts transferred, animal {animal.animal_id} marked as transferred")
                    
                    # Create audit log for part transfers
                    UserAuditLog.objects.create(
                        performed_by=request.user,
                        affected_user=animal.farmer,
                        processing_unit=processing_unit,
                        action='animal_parts_transferred',
                        description=f'{len(part_ids)} parts of animal {animal.animal_id} transferred to processing unit {processing_unit.name}',
                        old_values={},
                        new_values={'part_ids': part_ids, 'processing_unit_id': processing_unit.id},
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )

            logger.info(f"BACKEND_TRANSFER_SUCCESS - Transferred {transferred_animals_count} animals and {transferred_parts_count} parts to {processing_unit.name}")
            
            message_parts = []
            if transferred_animals_count > 0:
                message_parts.append(f'{transferred_animals_count} animal(s)')
            if transferred_parts_count > 0:
                message_parts.append(f'{transferred_parts_count} part(s)')
            
            message = f"Successfully transferred {' and '.join(message_parts)} to {processing_unit.name}"
            
            return Response({
                'message': message,
                'transferred_animals_count': transferred_animals_count,
                'transferred_parts_count': transferred_parts_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"BACKEND_TRANSFER_ERROR - Exception: {str(e)}", exc_info=True)
            return Response({'error': 'Failed to transfer animals'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='transferred_animals')
    def transferred_animals(self, request):
        """
        Get all animals transferred to the current user's processing unit.
        Only accessible by processing unit users.
        """
        try:
            # Check if user is a processing unit user
            if not hasattr(request.user, 'profile') or request.user.profile.role != 'ProcessingUnit':
                return Response({'error': 'Only processing unit users can access this endpoint'}, status=status.HTTP_403_FORBIDDEN)

            # Get the user's processing unit from profile or active membership
            processing_unit = request.user.profile.processing_unit
            
            # If profile.processing_unit is not set, try to get it from active membership
            if not processing_unit:
                logger.warning(f"User {request.user.username} has role ProcessingUnit but profile.processing_unit is None")
                active_membership = ProcessingUnitUser.objects.filter(
                    user=request.user,
                    is_active=True
                ).select_related('processing_unit').first()
                
                if active_membership:
                    processing_unit = active_membership.processing_unit
                    # Fix the profile to prevent this issue in the future
                    logger.info(f"Auto-fixing profile.processing_unit for user {request.user.username} to {processing_unit.name}")
                    request.user.profile.processing_unit = processing_unit
                    request.user.profile.save()
                else:
                    logger.error(f"User {request.user.username} has no active processing unit membership")
                    return Response({
                        'error': 'You are not associated with any processing unit. Please contact an administrator.',
                        'animals': [],
                        'count': 0
                    }, status=status.HTTP_404_NOT_FOUND)

            # Get animals transferred to this processing unit
            animals = Animal.objects.filter(
                transferred_to=processing_unit,
                transferred_to__isnull=False
            ).select_related('farmer', 'transferred_to')

            logger.info(f"User {request.user.username} querying transferred animals for PU {processing_unit.name}: found {animals.count()} animals")

            # Serialize the animals
            serializer = self.get_serializer(animals, many=True)
            return Response({
                'animals': serializer.data,
                'count': len(serializer.data),
                'processing_unit': {
                    'id': processing_unit.id,
                    'name': processing_unit.name
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting transferred animals for user {request.user.username}: {str(e)}", exc_info=True)
            return Response({'error': 'Failed to get transferred animals'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='my_transferred_animals')
    def my_transferred_animals(self, request):
        """
        Get all animals transferred by the current farmer user.
        Only accessible by farmers.
        """
        try:
            # Check if user is a farmer
            if not hasattr(request.user, 'profile') or request.user.profile.role != 'Farmer':
                return Response({'error': 'Only farmers can access this endpoint'}, status=status.HTTP_403_FORBIDDEN)

            # Get animals transferred by this farmer
            animals = Animal.objects.filter(
                farmer=request.user,
                transferred_to__isnull=False
            ).select_related('farmer', 'transferred_to')

            # Serialize the animals
            serializer = self.get_serializer(animals, many=True)
            return Response({
                'animals': serializer.data,
                'count': len(serializer.data)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting my transferred animals: {str(e)}")
            return Response({'error': 'Failed to get transferred animals'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['put', 'patch'], url_path='slaughter')
    def slaughter(self, request, pk=None):
        """
        Mark an animal as slaughtered.
        Only accessible by farmers who own the animal.
        """
        try:
            animal = self.get_object()
            
            # Check if user is the farmer who owns the animal
            if animal.farmer != request.user:
                return Response({'error': 'You can only slaughter your own animals'}, status=status.HTTP_403_FORBIDDEN)
            
            # Check if animal is already slaughtered
            if animal.slaughtered:
                return Response({'error': 'Animal is already slaughtered'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if animal has been transferred
            if animal.transferred_to is not None:
                return Response({'error': 'Cannot slaughter an animal that has been transferred'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark as slaughtered
            animal.slaughtered = True
            animal.slaughtered_at = timezone.now()
            animal.save()
            
            logger.info(f"Animal {animal.animal_id} (ID: {animal.id}) marked as slaughtered by {request.user.username}")
            
            serializer = self.get_serializer(animal)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error slaughtering animal: {str(e)}", exc_info=True)
            return Response({'error': f'Failed to slaughter animal: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='receive_animals')
    def receive_animals(self, request):
        """
        Receive animals or individual parts that have been transferred to the current user's processing unit.
        Supports both whole carcass and split carcass (part-level) receives.
        Only accessible by processing unit users.
        
        Request data:
        - animal_ids: list of animal IDs for whole carcass receives
        - part_receives: optional list of {animal_id, part_ids} for split carcass part receives
        """
        try:
            logger.info(f"🔵 RECEIVE_START =====================================")
            logger.info(f"🔵 RECEIVE - User: {request.user.username} (ID: {request.user.id})")
            logger.info(f"🔵 RECEIVE - Request data: {request.data}")

            # Check if user is a processing unit user
            if not hasattr(request.user, 'profile'):
                logger.error(f"❌ RECEIVE - User {request.user.username} has no profile!")
                return Response({'error': 'User profile not found'}, status=status.HTTP_403_FORBIDDEN)
                
            logger.info(f"🔵 RECEIVE - User profile role: {request.user.profile.role}")
            
            if request.user.profile.role != 'ProcessingUnit':
                logger.warning(f"⚠️ RECEIVE - User {request.user.username} is not a processing unit user (role: {request.user.profile.role})")
                return Response({'error': 'Only processing unit users can receive animals'}, status=status.HTTP_403_FORBIDDEN)

            # Get the user's processing unit
            processing_unit = request.user.profile.processing_unit
            logger.info(f"🔵 RECEIVE - profile.processing_unit: {processing_unit}")
            
            # If profile.processing_unit is not set, try to get it from active membership
            if not processing_unit:
                logger.warning(f"⚠️ RECEIVE - User {request.user.username} has role ProcessingUnit but profile.processing_unit is None")
                active_membership = ProcessingUnitUser.objects.filter(
                    user=request.user,
                    is_active=True
                ).select_related('processing_unit').first()
                
                logger.info(f"🔍 RECEIVE - Active membership search: {active_membership}")
                
                if active_membership:
                    processing_unit = active_membership.processing_unit
                    logger.info(f"✅ RECEIVE - Auto-fixing profile.processing_unit for user {request.user.username} to {processing_unit.name}")
                    request.user.profile.processing_unit = processing_unit
                    request.user.profile.save()
                else:
                    logger.error(f"❌ RECEIVE - User {request.user.username} has no active processing unit membership")
                    return Response({'error': 'You are not associated with any processing unit'}, status=status.HTTP_403_FORBIDDEN)

            logger.info(f"✅ RECEIVE - Using processing unit: {processing_unit.name} (ID: {processing_unit.id})")

            # Get animal IDs and part receives from request
            animal_ids = request.data.get('animal_ids', [])
            part_receives = request.data.get('part_receives', [])
            
            logger.info(f"🔵 RECEIVE - animal_ids: {animal_ids}")
            logger.info(f"🔵 RECEIVE - part_receives: {part_receives}")
            
            if not animal_ids and not part_receives:
                logger.warning("⚠️ RECEIVE - No animal_ids or part_receives provided")
                return Response({'error': 'animal_ids or part_receives are required'}, status=status.HTTP_400_BAD_REQUEST)

            # Check what animals are actually available to receive
            available_animals = Animal.objects.filter(
                transferred_to=processing_unit,
                received_by__isnull=True
            )
            logger.info(f"📊 RECEIVE - Available animals to receive: {available_animals.count()}")
            for animal in available_animals:
                logger.info(f"   📦 Available: {animal.animal_id} (ID: {animal.id}) - Species: {animal.species}, Farmer: {animal.farmer.username}")

            received_animals_count = 0
            received_parts_count = 0

            # Handle whole animal receives (traditional flow)
            if animal_ids:
                logger.info(f"🔵 RECEIVE - Processing {len(animal_ids)} whole animal receives")
                animals = []
                for animal_id in animal_ids:
                    logger.info(f"🔍 RECEIVE - Looking for animal ID: {animal_id}")
                    try:
                        animal = Animal.objects.get(id=animal_id, transferred_to=processing_unit)
                        logger.info(f"✅ RECEIVE - Found animal: {animal.animal_id}, received_by: {animal.received_by}")
                        
                        # Check if already received
                        if animal.received_by is not None:
                            logger.warning(f"⚠️ RECEIVE - Animal {animal_id} already received by {animal.received_by.username}")
                            return Response({'error': f'Animal {animal.animal_id} has already been received'}, status=status.HTTP_400_BAD_REQUEST)
                        
                        animals.append(animal)
                    except Animal.DoesNotExist:
                        logger.error(f"❌ RECEIVE - Animal {animal_id} not found or not transferred to this unit")
                        logger.info(f"🔍 RECEIVE - Checking if animal {animal_id} exists at all...")
                        try:
                            any_animal = Animal.objects.get(id=animal_id)
                            logger.info(f"🔍 RECEIVE - Animal {animal_id} exists but:")
                            logger.info(f"     transferred_to: {any_animal.transferred_to}")
                            logger.info(f"     expected processing_unit: {processing_unit}")
                            logger.info(f"     Match: {any_animal.transferred_to == processing_unit}")
                        except Animal.DoesNotExist:
                            logger.error(f"❌ RECEIVE - Animal {animal_id} does not exist in database")
                        return Response({'error': f'Animal {animal_id} not found or not transferred to your processing unit'}, status=status.HTTP_404_NOT_FOUND)

                # Receive whole animals
                logger.info(f"BACKEND_RECEIVE_EXECUTION_START - Receiving {len(animals)} whole animals")
                for animal in animals:
                    animal.received_by = request.user
                    animal.received_at = timezone.now()
                    animal.save()
                    received_animals_count += 1
                    logger.info(f"BACKEND_RECEIVE_ANIMAL_RECEIVED - Animal {animal.animal_id} received successfully")

                    # Create audit log
                    UserAuditLog.objects.create(
                        performed_by=request.user,
                        affected_user=animal.farmer,
                        processing_unit=processing_unit,
                        action='animal_received',
                        description=f'Animal {animal.animal_id} received by {request.user.username}',
                        old_values={'received_by': None, 'received_at': None},
                        new_values={'received_by': request.user.id, 'received_at': animal.received_at.isoformat()},
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )

            # Handle part-level receives for split carcasses
            if part_receives:
                logger.info(f"BACKEND_RECEIVE_PARTS_START - Processing {len(part_receives)} part receive requests")
                for part_receive in part_receives:
                    animal_id = part_receive.get('animal_id')
                    part_ids = part_receive.get('part_ids', [])
                    
                    if not animal_id or not part_ids:
                        logger.warning(f"BACKEND_RECEIVE_ERROR - Invalid part_receive data: {part_receive}")
                        return Response({'error': 'Each part_receive must have animal_id and part_ids'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Validate animal
                    try:
                        animal = Animal.objects.get(id=animal_id)
                    except Animal.DoesNotExist:
                        logger.warning(f"BACKEND_RECEIVE_ERROR - Animal not found for part receive: {animal_id}")
                        return Response({'error': f'Animal {animal_id} not found'}, status=status.HTTP_404_NOT_FOUND)
                    
                    # Validate and receive parts
                    for part_id in part_ids:
                        try:
                            part = SlaughterPart.objects.get(id=part_id, animal=animal, transferred_to=processing_unit)
                            
                            # Check if part already received
                            if part.received_by is not None:
                                logger.warning(f"BACKEND_RECEIVE_ERROR - Part {part_id} already received")
                                return Response({'error': f'Part {part.part_type} of animal {animal.animal_id} has already been received'}, status=status.HTTP_400_BAD_REQUEST)
                            
                            # Receive the part
                            part.received_by = request.user
                            part.received_at = timezone.now()
                            part.save()
                            received_parts_count += 1
                            logger.info(f"BACKEND_RECEIVE_PART_RECEIVED - Part {part.part_type} of animal {animal.animal_id} received")
                            
                        except SlaughterPart.DoesNotExist:
                            logger.warning(f"BACKEND_RECEIVE_ERROR - Part not found or not transferred: {part_id} for animal {animal_id}")
                            return Response({'error': f'Part {part_id} not found or not transferred to your processing unit'}, status=status.HTTP_404_NOT_FOUND)
                    
                    # Create audit log for part receives
                    UserAuditLog.objects.create(
                        performed_by=request.user,
                        affected_user=animal.farmer,
                        processing_unit=processing_unit,
                        action='animal_parts_received',
                        description=f'{len(part_ids)} parts of animal {animal.animal_id} received by {request.user.username}',
                        old_values={},
                        new_values={'part_ids': part_ids, 'received_by': request.user.id},
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )

            logger.info(f"BACKEND_RECEIVE_SUCCESS - Received {received_animals_count} animals and {received_parts_count} parts")
            
            message_parts = []
            if received_animals_count > 0:
                message_parts.append(f'{received_animals_count} animal(s)')
            if received_parts_count > 0:
                message_parts.append(f'{received_parts_count} part(s)')
            
            message = f"Successfully received {' and '.join(message_parts)}"
            
            return Response({
                'message': message,
                'received_animals_count': received_animals_count,
                'received_parts_count': received_parts_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"BACKEND_RECEIVE_ERROR - Exception: {str(e)}", exc_info=True)
            return Response({'error': 'Failed to receive animals'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        logger.info(f"🔍 ANIMAL_QUERYSET ===================================")
        logger.info(f"🔍 ANIMAL_QUERYSET - User: {user.username} (ID: {user.id})")
        logger.info(f"🔍 ANIMAL_QUERYSET - Has profile: {hasattr(user, 'profile')}")
        if hasattr(user, 'profile'):
            logger.info(f"🔍 ANIMAL_QUERYSET - Profile role: {user.profile.role}")

        # Handle slaughtered parameter from frontend
        # slaughtered=null -> show all
        # slaughtered=false -> show active (not slaughtered)
        # slaughtered=true -> show slaughtered only
        slaughtered_param = self.request.query_params.get('slaughtered')

        if slaughtered_param is not None:
            if slaughtered_param.lower() == 'true':
                # Show only slaughtered animals
                queryset = queryset.filter(slaughtered=True)
            elif slaughtered_param.lower() == 'false':
                # Show only active (not slaughtered) animals
                queryset = queryset.filter(slaughtered=False)
            # If slaughtered_param is 'null' or any other value, show all animals

        # Farmers can only see their own animals
        if hasattr(user, 'profile') and user.profile.role == 'Farmer':
            queryset = queryset.filter(farmer=user)
            logger.info(f"✅ ANIMAL_QUERYSET - Farmer filter applied. Count: {queryset.count()}")

        # Processing units can see animals transferred to them
        elif hasattr(user, 'profile') and user.profile.role == 'ProcessingUnit':
            logger.info(f"🔍 PROCESSOR_QUERY - User: {user.username} (ID: {user.id}), Role: ProcessingUnit")
            processing_unit = user.profile.processing_unit
            
            logger.info(f"🔍 PROCESSOR_QUERY - profile.processing_unit: {processing_unit}")
            
            # If profile.processing_unit is not set, try to get it from active membership
            if not processing_unit:
                logger.warning(f"⚠️ PROCESSOR_QUERY - User {user.username} has role ProcessingUnit but profile.processing_unit is None")
                active_membership = ProcessingUnitUser.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('processing_unit').first()
                
                logger.info(f"🔍 PROCESSOR_QUERY - Active membership search result: {active_membership}")
                
                if active_membership:
                    processing_unit = active_membership.processing_unit
                    # Fix the profile to prevent this issue in the future
                    logger.info(f"✅ PROCESSOR_QUERY - Auto-fixing profile.processing_unit for user {user.username} to {processing_unit.name}")
                    user.profile.processing_unit = processing_unit
                    user.profile.save()
                else:
                    # No active membership exists - create a processing unit and membership
                    logger.warning(f"⚠️ PROCESSOR_QUERY - User {user.username} has no active processing unit membership - auto-creating")
                    processing_unit = ProcessingUnit.objects.create(
                        name=f"{user.username}'s Processing Unit",
                        description=f"Auto-created processing unit for {user.username}",
                        contact_email=user.email
                    )
                    ProcessingUnitUser.objects.create(
                        user=user,
                        processing_unit=processing_unit,
                        role='owner',
                        permissions='admin',
                        invited_by=user,
                        invited_at=timezone.now(),
                        joined_at=timezone.now(),
                        is_active=True
                    )
                    user.profile.processing_unit = processing_unit
                    user.profile.save()
                    logger.info(f"✅ PROCESSOR_QUERY - Auto-created processing unit {processing_unit.name} (ID: {processing_unit.id}) for user {user.username}")
            
            if processing_unit:
                logger.info(f"🔍 PROCESSOR_QUERY - Using processing_unit: {processing_unit.name} (ID: {processing_unit.id})")
                
                # Count all animals in the database transferred to this processing unit
                total_transferred = Animal.objects.filter(transferred_to=processing_unit).count()
                logger.info(f"📊 PROCESSOR_QUERY - Total animals transferred to {processing_unit.name}: {total_transferred}")
                
                # Show details of transferred animals
                transferred_animals = Animal.objects.filter(transferred_to=processing_unit).values(
                    'id', 'animal_id', 'species', 'farmer__username', 'transferred_at', 'received_by__username', 'received_at'
                )[:10]  # Limit to first 10 for logging
                
                if transferred_animals:
                    logger.info(f"📋 PROCESSOR_QUERY - Sample transferred animals:")
                    for animal in transferred_animals:
                        logger.info(f"   • Animal ID: {animal['animal_id']}, Species: {animal['species']}, "
                                  f"Farmer: {animal['farmer__username']}, "
                                  f"Transferred: {animal['transferred_at']}, "
                                  f"Received by: {animal.get('received_by__username', 'Not received')}")
                else:
                    logger.warning(f"⚠️ PROCESSOR_QUERY - NO animals found transferred to {processing_unit.name}")
                    
                    # Check if there are ANY animals transferred to ANY processing unit
                    any_transferred = Animal.objects.filter(transferred_to__isnull=False).count()
                    logger.info(f"📊 PROCESSOR_QUERY - Total animals transferred to ANY processing unit in system: {any_transferred}")
                    
                    if any_transferred > 0:
                        # Show which processing units have received animals
                        other_units = Animal.objects.filter(transferred_to__isnull=False).values(
                            'transferred_to__id', 'transferred_to__name'
                        ).distinct()
                        logger.info(f"📋 PROCESSOR_QUERY - Processing units that HAVE received animals:")
                        for unit in other_units:
                            count = Animal.objects.filter(transferred_to_id=unit['transferred_to__id']).count()
                            logger.info(f"   • {unit['transferred_to__name']} (ID: {unit['transferred_to__id']}): {count} animals")
                
                # Apply the filter
                queryset = queryset.filter(transferred_to=processing_unit)
                logger.info(f"✅ PROCESSOR_QUERY - Queryset filtered. Result count: {queryset.count()}")
            else:
                # This should never happen now, but keep as fallback
                logger.error(f"❌ PROCESSOR_QUERY - User {user.username} has no active processing unit membership in get_queryset")
                queryset = queryset.none()

        # Shops can see animals whose products are in their inventory
        elif hasattr(user, 'profile') and user.profile.role == 'Shop':
            shop = user.profile.shop
            
            # If profile.shop is not set, try to get it from active membership
            if not shop:
                logger.warning(f"User {user.username} has role Shop but profile.shop is None in get_queryset")
                active_membership = ShopUser.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('shop').first()
                
                if active_membership:
                    shop = active_membership.shop
                    # Fix the profile
                    logger.info(f"Auto-fixing profile.shop for user {user.username} to {shop.name} in get_queryset")
                    user.profile.shop = shop
                    user.profile.save()
                else:
                    # No active membership exists - create a shop and membership
                    logger.warning(f"User {user.username} has no active shop membership - auto-creating")
                    shop = Shop.objects.create(
                        name=f"{user.username}'s Shop",
                        description=f"Auto-created shop for {user.username}",
                        contact_email=user.email,
                        is_active=True
                    )
                    ShopUser.objects.create(
                        user=user,
                        shop=shop,
                        role='owner',
                        permissions='admin',
                        invited_by=user,
                        invited_at=timezone.now(),
                        joined_at=timezone.now(),
                        is_active=True
                    )
                    user.profile.shop = shop
                    user.profile.save()
                    logger.info(f"Auto-created shop {shop.name} for user {user.username}")
            
            if shop:
                queryset = queryset.filter(
                    Q(product__receipt__shop=shop) |
                    Q(product__inventory__shop=shop)
                ).distinct()
            else:
                # This should never happen now, but keep as fallback
                logger.error(f"User {user.username} has no active shop in get_queryset")
                queryset = queryset.none()

        return queryset

    def create(self, request, *args, **kwargs):
        logger.info(f"Animal creation attempt - User: {request.user.username} (ID: {request.user.id}), Role: {getattr(request.user.profile, 'role', 'Unknown')}")
        logger.info(f"Animal data received: {request.data}")

        try:
            logger.info("Starting validation phase")

            # Validate required fields
            required_fields = ['species', 'age']
            missing_fields = [field for field in required_fields if field not in request.data or request.data[field] is None]
            if missing_fields:
                logger.warning(f"Missing required fields: {missing_fields}")
                return Response({'error': f'Missing required fields: {", ".join(missing_fields)}'}, status=status.HTTP_400_BAD_REQUEST)

            logger.info("Required fields validation passed")

            # Validate species
            species_value = request.data.get('species')
            logger.info(f"Validating species: {species_value}")
            if species_value not in dict(Animal.SPECIES_CHOICES):
                logger.warning(f"Invalid species: {species_value}. Valid choices: {dict(Animal.SPECIES_CHOICES)}")
                return Response({'error': 'Invalid species'}, status=status.HTTP_400_BAD_REQUEST)

            logger.info("Species validation passed")

            # Validate age IN
            age_str = request.data.get('age')
            logger.info(f"Validating age: {age_str}")
            try:
                age = float(age_str)
                if age <= 0:
                    logger.warning(f"Invalid age: {age}")
                    return Response({'error': 'Age must be positive'}, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid age format: {age_str}, error: {str(e)}")
                return Response({'error': 'Invalid age format'}, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Age validation passed: {age}")

            # Check if user has permission to create animals (only farmers)
            logger.info("Checking user permissions")
            if not hasattr(request.user, 'profile'):
                logger.warning(f"User {request.user.username} has no profile")
                return Response({'error': 'Only farmers can register animals'}, status=status.HTTP_403_FORBIDDEN)

            user_role = request.user.profile.role
            logger.info(f"User role: {user_role}")
            if user_role != 'Farmer':
                logger.warning(f"User {request.user.username} with role {user_role} attempted to create animal but is not a farmer")
                return Response({'error': 'Only farmers can register animals'}, status=status.HTTP_403_FORBIDDEN)

            logger.info("Permission check passed, proceeding with animal creation")

            # Create the animal
            animal_data = request.data.copy()
            animal_data['farmer'] = request.user.id

            # Remove farm_name if present (field was removed)
            animal_data.pop('farm_name', None)

            logger.info(f"Final animal data for serializer: {animal_data}")

            serializer = self.get_serializer(data=animal_data)
            logger.info("Serializer created, checking validity")

            if not serializer.is_valid():
                logger.error(f"Serializer validation failed: {serializer.errors}")
                logger.error(f"Serializer data: {serializer.data}")
                logger.error(f"Serializer initial data: {serializer.initial_data}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            logger.info("Serializer validation passed, attempting to save")

            try:
                animal = serializer.save()
                logger.info(f"Animal saved successfully: ID={animal.id}, animal_id={animal.animal_id}")
            except Exception as save_error:
                logger.error(f"Error during serializer.save(): {str(save_error)}", exc_info=True)
                raise save_error

            logger.info(f"Animal created successfully: ID={animal.id}, animal_id={animal.animal_id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Unexpected error during animal creation: {str(e)}", exc_info=True)
            logger.error(f"Exception type: {type(e)}")
            logger.error(f"Request data: {request.data}")
            logger.error(f"User: {request.user.username} (ID: {request.user.id})")
            return Response({'error': 'Failed to create animal'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Unit Creation and Management Views

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_processing_unit(request):
    """
    Create a new processing unit and assign the creator as owner.
    """
    try:
        # Get data from request
        name = request.data.get('name')
        description = request.data.get('description', '')
        location = request.data.get('location', '')
        contact_email = request.data.get('contact_email', '')
        contact_phone = request.data.get('contact_phone', '')
        license_number = request.data.get('license_number', '')

        if not name:
            return Response({'error': 'Unit name is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if unit name already exists
        if ProcessingUnit.objects.filter(name=name).exists():
            return Response({'error': 'Processing unit with this name already exists'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the processing unit
        processing_unit = ProcessingUnit.objects.create(
            name=name,
            description=description,
            location=location,
            contact_email=contact_email,
            contact_phone=contact_phone,
            license_number=license_number
        )

        # Create membership for the creator as owner
        membership = ProcessingUnitUser.objects.create(
            user=request.user,
            processing_unit=processing_unit,
            role='owner',
            invited_by=request.user,
            joined_at=timezone.now(),
            is_active=True
        )

        # Update user profile - ensure the user is linked to their processing unit
        profile = request.user.profile
        profile.role = 'ProcessingUnit'
        profile.processing_unit = processing_unit  # This is crucial for linking the user to their unit
        profile.save()

        # Create audit log
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=request.user,
            processing_unit=processing_unit,
            action='unit_created',
            description=f'Created processing unit {processing_unit.name} and assigned as owner',
            old_values={},
            new_values={'name': name, 'role': 'owner'},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        serializer = ProcessingUnitSerializer(processing_unit)
        return Response({
            'message': f'Processing unit "{name}" created successfully',
            'processing_unit': serializer.data,
            'membership': {
                'id': membership.id,
                'role': membership.role,
                'joined_at': membership.joined_at
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error creating processing unit: {str(e)}")
        return Response({'error': 'Failed to create processing unit'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_shop(request):
    """
    Create a new shop and assign the creator as owner.
    """
    try:
        # Get data from request
        name = request.data.get('name')
        description = request.data.get('description', '')
        location = request.data.get('location', '')
        contact_email = request.data.get('contact_email', '')
        contact_phone = request.data.get('contact_phone', '')
        business_license = request.data.get('business_license', '')
        tax_id = request.data.get('tax_id', '')

        if not name:
            return Response({'error': 'Shop name is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if shop name already exists
        if Shop.objects.filter(name=name).exists():
            return Response({'error': 'Shop with this name already exists'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the shop
        shop = Shop.objects.create(
            name=name,
            description=description,
            location=location,
            contact_email=contact_email,
            contact_phone=contact_phone,
            business_license=business_license,
            tax_id=tax_id
        )

        # Create membership for the creator as owner
        membership = ShopUser.objects.create(
            user=request.user,
            shop=shop,
            role='owner',
            invited_by=request.user,
            joined_at=timezone.now(),
            is_active=True
        )

        # Update user profile
        profile = request.user.profile
        profile.role = 'Shop'
        profile.shop = shop
        profile.save()

        # Create audit log
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=request.user,
            shop=shop,
            action='shop_created',
            description=f'Created shop {shop.name} and assigned as owner',
            old_values={},
            new_values={'name': name, 'role': 'owner'},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        serializer = ShopSerializer(shop)
        return Response({
            'message': f'Shop "{name}" created successfully',
            'shop': serializer.data,
            'membership': {
                'id': membership.id,
                'role': membership.role,
                'joined_at': membership.joined_at
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error creating shop: {str(e)}")
        return Response({'error': 'Failed to create shop'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_processing_units(request):
    """
    Search and list processing units for joining.
    """
    try:
        # Get query parameters
        location = request.GET.get('location', '')
        name = request.GET.get('name', '')
        limit = int(request.GET.get('limit', 20))

        # Build queryset
        queryset = ProcessingUnit.objects.all()

        if location:
            queryset = queryset.filter(location__icontains=location)

        if name:
            queryset = queryset.filter(name__icontains=name)

        # Limit results
        queryset = queryset[:limit]

        serializer = ProcessingUnitSerializer(queryset, many=True)
        return Response({
            'processing_units': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error searching processing units: {str(e)}")
        return Response({'error': 'Failed to search processing units'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_shops(request):
    """
    Search and list shops for joining.
    """
    try:
        # Get query parameters
        location = request.GET.get('location', '')
        name = request.GET.get('name', '')
        limit = int(request.GET.get('limit', 20))

        # Build queryset
        queryset = Shop.objects.filter(is_active=True)

        if location:
            queryset = queryset.filter(location__icontains=location)

        if name:
            queryset = queryset.filter(name__icontains=name)

        # Limit results
        queryset = queryset[:limit]

        serializer = ShopSerializer(queryset, many=True)
        return Response({
            'shops': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error searching shops: {str(e)}")
        return Response({'error': 'Failed to search shops'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Join Request Views

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_join_request(request, unit_type, unit_id):
    """
    Create a join request for a processing unit or shop.
    """
    try:
        requested_role = request.data.get('requested_role')
        message = request.data.get('message', '')
        qualifications = request.data.get('qualifications', '')

        if not requested_role:
            return Response({'error': 'Requested role is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate unit type
        if unit_type not in ['processing_unit', 'shop']:
            return Response({'error': 'Invalid unit type. Must be "processing_unit" or "shop"'}, status=status.HTTP_400_BAD_REQUEST)

        # Get the target unit
        if unit_type == 'processing_unit':
            try:
                unit = ProcessingUnit.objects.get(id=unit_id)
                # Check if user is already a member
                if ProcessingUnitUser.objects.filter(user=request.user, processing_unit=unit).exists():
                    return Response({'error': 'You are already a member of this processing unit'}, status=status.HTTP_400_BAD_REQUEST)
                # Check for existing pending request
                if JoinRequest.objects.filter(user=request.user, processing_unit=unit, status='pending').exists():
                    return Response({'error': 'You already have a pending join request for this processing unit'}, status=status.HTTP_400_BAD_REQUEST)
            except ProcessingUnit.DoesNotExist:
                return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)
        else:  # shop
            try:
                unit = Shop.objects.get(id=unit_id)
                # Check if user is already a member
                if ShopUser.objects.filter(user=request.user, shop=unit).exists():
                    return Response({'error': 'You are already a member of this shop'}, status=status.HTTP_400_BAD_REQUEST)
                # Check for existing pending request
                if JoinRequest.objects.filter(user=request.user, shop=unit, status='pending').exists():
                    return Response({'error': 'You already have a pending join request for this shop'}, status=status.HTTP_400_BAD_REQUEST)
            except Shop.DoesNotExist:
                return Response({'error': 'Shop not found'}, status=status.HTTP_404_NOT_FOUND)

        # Validate role
        if unit_type == 'processing_unit':
            valid_roles = ['owner', 'manager', 'supervisor', 'worker', 'quality_control']
        else:
            valid_roles = ['owner', 'manager', 'salesperson', 'cashier', 'inventory_clerk']

        if requested_role not in valid_roles:
            return Response({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Create join request
        join_request = JoinRequest.objects.create(
            user=request.user,
            request_type=unit_type,
            processing_unit=unit if unit_type == 'processing_unit' else None,
            shop=unit if unit_type == 'shop' else None,
            requested_role=requested_role,
            message=message,
            qualifications=qualifications,
            expires_at=timezone.now() + timezone.timedelta(days=30)  # 30 days expiry
        )

        # Create notification for unit owners
        owners = []
        if unit_type == 'processing_unit':
            owners = ProcessingUnitUser.objects.filter(processing_unit=unit, role='owner', is_active=True)
        else:
            owners = ShopUser.objects.filter(shop=unit, role='owner', is_active=True)

        for owner_membership in owners:
            Notification.objects.create(
                user=owner_membership.user,
                notification_type='join_request',
                title=f'New join request for {unit.name}',
                message=f'{request.user.username} has requested to join as {requested_role}',
                data={
                    'join_request_id': join_request.id,
                    'unit_type': unit_type,
                    'unit_id': unit_id,
                    'unit_name': unit.name,
                    'requester_username': request.user.username,
                    'requested_role': requested_role
                },
                action_url=f'/api/v2/join-requests/{join_request.id}/',
                action_text='Review Request'
            )

        serializer = JoinRequestSerializer(join_request)
        return Response({
            'message': f'Join request sent to {unit.name}',
            'join_request': serializer.data
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error creating join request: {str(e)}")
        return Response({'error': 'Failed to create join request'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_user_join_requests(request):
    """
    Get all join requests for the current user.
    """
    try:
        join_requests = JoinRequest.objects.filter(user=request.user).order_by('-created_at')
        serializer = JoinRequestSerializer(join_requests, many=True)
        return Response({
            'join_requests': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error listing user join requests: {str(e)}")
        return Response({'error': 'Failed to get join requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def review_join_request(request, request_id):
    """
    Approve or reject a join request (owners/managers only).
    """
    try:
        # Get the join request
        try:
            join_request = JoinRequest.objects.get(id=request_id)
        except JoinRequest.DoesNotExist:
            return Response({'error': 'Join request not found'}, status=status.HTTP_404_NOT_FOUND)

        if join_request.status != 'pending':
            return Response({'error': 'This join request has already been reviewed'}, status=status.HTTP_400_BAD_REQUEST)

        # Get review data
        new_status = request.data.get('status')
        response_message = request.data.get('response_message', '')

        if new_status not in ['approved', 'rejected']:
            return Response({'error': 'Status must be "approved" or "rejected"'}, status=status.HTTP_400_BAD_REQUEST)

        # Check permissions - user must be owner/manager of the target unit
        if join_request.request_type == 'processing_unit':
            try:
                membership = ProcessingUnitUser.objects.get(
                    user=request.user,
                    processing_unit=join_request.processing_unit,
                    is_active=True
                )
                if membership.role not in ['owner', 'manager']:
                    return Response({'error': 'Only owners and managers can review join requests'}, status=status.HTTP_403_FORBIDDEN)
            except ProcessingUnitUser.DoesNotExist:
                return Response({'error': 'You are not authorized to review this request'}, status=status.HTTP_403_FORBIDDEN)
        else:  # shop
            try:
                membership = ShopUser.objects.get(
                    user=request.user,
                    shop=join_request.shop,
                    is_active=True
                )
                if membership.role not in ['owner', 'manager']:
                    return Response({'error': 'Only owners and managers can review join requests'}, status=status.HTTP_403_FORBIDDEN)
            except ShopUser.DoesNotExist:
                return Response({'error': 'You are not authorized to review this request'}, status=status.HTTP_403_FORBIDDEN)

        # Update join request
        join_request.status = new_status
        join_request.response_message = response_message
        join_request.reviewed_by = request.user
        join_request.reviewed_at = timezone.now()
        join_request.save()

        # If approved, create membership
        if new_status == 'approved':
            if join_request.request_type == 'processing_unit':
                membership = ProcessingUnitUser.objects.create(
                    user=join_request.user,
                    processing_unit=join_request.processing_unit,
                    role=join_request.requested_role,
                    invited_by=request.user,
                    joined_at=timezone.now(),
                    is_active=True
                )
                # Update user profile - ensure the user is linked to their processing unit
                profile = join_request.user.profile
                profile.role = 'ProcessingUnit'
                profile.processing_unit = join_request.processing_unit  # This is crucial for linking the user to their unit
                profile.save()
            else:  # shop
                membership = ShopUser.objects.create(
                    user=join_request.user,
                    shop=join_request.shop,
                    role=join_request.requested_role,
                    invited_by=request.user,
                    joined_at=timezone.now(),
                    is_active=True
                )
                # Update user profile
                profile = join_request.user.profile
                profile.role = 'Shop'
                profile.shop = join_request.shop
                profile.save()

        # Create notification for the requester
        notification_type = 'join_approved' if new_status == 'approved' else 'join_rejected'
        unit_name = join_request.processing_unit.name if join_request.processing_unit else join_request.shop.name

        Notification.objects.create(
            user=join_request.user,
            notification_type=notification_type,
            title=f'Join request {new_status}',
            message=f'Your join request for {unit_name} has been {new_status}',
            data={
                'join_request_id': join_request.id,
                'unit_type': join_request.request_type,
                'unit_name': unit_name,
                'reviewed_by': request.user.username,
                'response_message': response_message
            }
        )

        # Create audit log
        UserAuditLog.objects.create(
            performed_by=request.user,
            affected_user=join_request.user,
            processing_unit=join_request.processing_unit,
            shop=join_request.shop,
            action=f'join_request_{new_status}',
            description=f'{new_status.capitalize()} join request from {join_request.user.username} for {join_request.requested_role} role',
            old_values={'status': 'pending'},
            new_values={'status': new_status, 'response_message': response_message},
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        serializer = JoinRequestSerializer(join_request)
        return Response({
            'message': f'Join request {new_status} successfully',
            'join_request': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error reviewing join request: {str(e)}")
        return Response({'error': 'Failed to review join request'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_unit_join_requests(request, unit_type, unit_id):
    """
    Get all join requests for a specific unit (owners/managers only).
    """
    try:
        # Validate unit type
        if unit_type not in ['processing_unit', 'shop']:
            return Response({'error': 'Invalid unit type. Must be "processing_unit" or "shop"'}, status=status.HTTP_400_BAD_REQUEST)

        # Get the unit and check permissions
        if unit_type == 'processing_unit':
            try:
                unit = ProcessingUnit.objects.get(id=unit_id)
                membership = ProcessingUnitUser.objects.get(
                    user=request.user,
                    processing_unit=unit,
                    is_active=True
                )
                if membership.role not in ['owner', 'manager']:
                    return Response({'error': 'Only owners and managers can view join requests'}, status=status.HTTP_403_FORBIDDEN)
            except ProcessingUnit.DoesNotExist:
                return Response({'error': 'Processing unit not found'}, status=status.HTTP_404_NOT_FOUND)
            except ProcessingUnitUser.DoesNotExist:
                return Response({'error': 'You are not authorized to view these requests'}, status=status.HTTP_403_FORBIDDEN)

            join_requests = JoinRequest.objects.filter(processing_unit=unit)
        else:  # shop
            try:
                unit = Shop.objects.get(id=unit_id)
                membership = ShopUser.objects.get(
                    user=request.user,
                    shop=unit,
                    is_active=True
                )
                if membership.role not in ['owner', 'manager']:
                    return Response({'error': 'Only owners and managers can view join requests'}, status=status.HTTP_403_FORBIDDEN)
            except Shop.DoesNotExist:
                return Response({'error': 'Shop not found'}, status=status.HTTP_404_NOT_FOUND)
            except ShopUser.DoesNotExist:
                return Response({'error': 'You are not authorized to view these requests'}, status=status.HTTP_403_FORBIDDEN)

            join_requests = JoinRequest.objects.filter(shop=unit)

        join_requests = join_requests.order_by('-created_at')
        serializer = JoinRequestSerializer(join_requests, many=True)

        return Response({
            'unit': {
                'id': unit_id,
                'name': unit.name,
                'type': unit_type
            },
            'join_requests': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error listing unit join requests: {str(e)}")
        return Response({'error': 'Failed to get join requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['processing_unit', 'animal', 'product_type', 'category', 'transferred_to']
    search_fields = ['name', 'batch_number', 'manufacturer']
    ordering_fields = ['created_at', 'weight', 'price']
    pagination_class = None  # Disable pagination for products

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Processing units can only see their own products
        if hasattr(user, 'profile') and user.profile.role == 'ProcessingUnit':
            # Get the user's processing unit from profile or active membership
            processing_unit = user.profile.processing_unit

            # If profile.processing_unit is not set, try to get it from active membership
            if not processing_unit:
                logger.warning(f"User {user.username} has role ProcessingUnit but profile.processing_unit is None in ProductViewSet.get_queryset")
                active_membership = ProcessingUnitUser.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('processing_unit').first()

                if active_membership:
                    processing_unit = active_membership.processing_unit
                    # Fix the profile to prevent this issue in the future
                    logger.info(f"Auto-fixing profile.processing_unit for user {user.username} to {processing_unit.name} in ProductViewSet")
                    user.profile.processing_unit = processing_unit
                    user.profile.save()
                else:
                    # No active membership exists - create a processing unit and membership
                    logger.warning(f"User {user.username} has no active processing unit membership - auto-creating in ProductViewSet")
                    processing_unit = ProcessingUnit.objects.create(
                        name=f"{user.username}'s Processing Unit",
                        description=f"Auto-created processing unit for {user.username}",
                        contact_email=user.email
                    )
                    ProcessingUnitUser.objects.create(
                        user=user,
                        processing_unit=processing_unit,
                        role='owner',
                        permissions='admin',
                        invited_by=user,
                        invited_at=timezone.now(),
                        joined_at=timezone.now(),
                        is_active=True
                    )
                    user.profile.processing_unit = processing_unit
                    user.profile.save()
                    logger.info(f"Auto-created processing unit {processing_unit.name} for user {user.username}")

            # Filter by the correct ProcessingUnit instance
            if processing_unit:
                queryset = queryset.filter(processing_unit=processing_unit)
            else:
                # This should never happen now, but keep as fallback
                logger.error(f"User {user.username} has no associated processing unit in ProductViewSet")
                queryset = queryset.none()

        # Shops can see products transferred to them or in their inventory
        elif hasattr(user, 'profile') and user.profile.role == 'Shop':
            shop = user.profile.shop
            
            # If profile.shop is not set, try to get it from active membership
            if not shop:
                logger.warning(f"User {user.username} has role Shop but profile.shop is None in ProductViewSet.get_queryset")
                active_membership = ShopUser.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('shop').first()
                
                if active_membership:
                    shop = active_membership.shop
                    logger.info(f"Auto-fixing profile.shop for user {user.username} to {shop.name} in ProductViewSet")
                    user.profile.shop = shop
                    user.profile.save()
                else:
                    # No active membership exists - create a shop and membership
                    logger.warning(f"User {user.username} has no active shop membership - auto-creating in ProductViewSet")
                    shop = Shop.objects.create(
                        name=f"{user.username}'s Shop",
                        description=f"Auto-created shop for {user.username}",
                        contact_email=user.email,
                        is_active=True
                    )
                    ShopUser.objects.create(
                        user=user,
                        shop=shop,
                        role='owner',
                        permissions='admin',
                        invited_by=user,
                        invited_at=timezone.now(),
                        joined_at=timezone.now(),
                        is_active=True
                    )
                    user.profile.shop = shop
                    user.profile.save()
                    logger.info(f"Auto-created shop {shop.name} for user {user.username}")
            
            if shop:
                queryset = queryset.filter(
                    Q(transferred_to=user) |
                    Q(inventory__shop=shop)
                ).distinct()
            else:
                # This should never happen now, but keep as fallback
                logger.error(f"User {user.username} has no associated shop in ProductViewSet")
                queryset = queryset.none()

        return queryset


class ReceiptViewSet(viewsets.ModelViewSet):
    queryset = Receipt.objects.all()
    serializer_class = ReceiptSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shop', 'product']
    search_fields = ['notes']
    ordering_fields = ['received_at']
    pagination_class = None  # Disable pagination for receipts

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Shops can only see their own receipts
        if hasattr(user, 'profile') and user.profile.role == 'Shop':
            queryset = queryset.filter(shop__shopuser__user=user)

        return queryset


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name']
    pagination_class = None  # Disable pagination for categories


class ProcessingStageViewSet(viewsets.ModelViewSet):
    queryset = ProcessingStage.objects.all()
    serializer_class = ProcessingStageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['order', 'name']
    pagination_class = None  # Disable pagination for processing stages


class ProductTimelineEventViewSet(viewsets.ModelViewSet):
    queryset = ProductTimelineEvent.objects.all()
    serializer_class = ProductTimelineEventSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product', 'stage']
    search_fields = ['action', 'location']
    ordering_fields = ['timestamp']
    pagination_class = None  # Disable pagination for timeline events

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Processing units can only see timeline events for their products
        if hasattr(user, 'profile') and user.profile.role == 'ProcessingUnit':
            # Get the user's processing unit from profile or active membership
            processing_unit = user.profile.processing_unit

            # If profile.processing_unit is not set, try to get it from active membership
            if not processing_unit:
                logger.warning(f"User {user.username} has role ProcessingUnit but profile.processing_unit is None in ProductTimelineEventViewSet.get_queryset")
                active_membership = ProcessingUnitUser.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('processing_unit').first()

                if active_membership:
                    processing_unit = active_membership.processing_unit
                    # Fix the profile to prevent this issue in the future
                    logger.info(f"Auto-fixing profile.processing_unit for user {user.username} to {processing_unit.name} in ProductTimelineEventViewSet")
                    user.profile.processing_unit = processing_unit
                    user.profile.save()
                else:
                    # User has no processing unit association - return empty queryset
                    logger.error(f"User {user.username} has no active processing unit membership in ProductTimelineEventViewSet.get_queryset")
                    return queryset.none()

            # Filter by the correct ProcessingUnit instance
            if processing_unit:
                queryset = queryset.filter(product__processing_unit=processing_unit)
            else:
                # No processing unit found - return empty queryset
                logger.error(f"User {user.username} has no associated processing unit in ProductTimelineEventViewSet")
                queryset = queryset.none()

        return queryset


class InventoryViewSet(viewsets.ModelViewSet):
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shop', 'product']
    search_fields = ['product__name']
    ordering_fields = ['last_updated', 'quantity']
    pagination_class = None  # Disable pagination for inventory

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Shops can only see their own inventory
        if hasattr(user, 'profile') and user.profile.role == 'Shop':
            queryset = queryset.filter(shop__shopuser__user=user)

        return queryset


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['customer', 'shop', 'status']
    search_fields = ['notes', 'delivery_address']
    ordering_fields = ['created_at', 'updated_at', 'total_amount']
    pagination_class = None  # Disable pagination for orders

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Customers can only see their own orders
        if hasattr(user, 'profile') and user.profile.role == 'Customer':
            queryset = queryset.filter(customer=user)

        # Shops can only see orders placed at their shop
        elif hasattr(user, 'profile') and user.profile.role == 'Shop':
            queryset = queryset.filter(shop__shopuser__user=user)

        return queryset


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['order', 'product']
    search_fields = ['product__name']
    ordering_fields = ['quantity', 'unit_price', 'subtotal']
    pagination_class = None  # Disable pagination for order items

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Customers can only see items from their orders
        if hasattr(user, 'profile') and user.profile.role == 'Customer':
            queryset = queryset.filter(order__customer=user)

        # Shops can only see items from orders at their shop
        elif hasattr(user, 'profile') and user.profile.role == 'Shop':
            queryset = queryset.filter(order__shop__shopuser__user=user)

        return queryset


class CarcassMeasurementViewSet(viewsets.ModelViewSet):
    queryset = CarcassMeasurement.objects.all()
    serializer_class = CarcassMeasurementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['animal', 'carcass_type']
    search_fields = ['animal__animal_id']
    ordering_fields = ['created_at']
    pagination_class = None  # Disable pagination for carcass measurements

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Processing units can only see measurements for animals transferred to them
        if hasattr(user, 'profile') and user.profile.role == 'ProcessingUnit':
            queryset = queryset.filter(animal__transferred_to=user)

        return queryset

    def create(self, request, *args, **kwargs):
        """
        Override create to mark animal as slaughtered and provide confirmation dialog.
        """
        try:
            logger.info(f"=== CarcassMeasurement CREATE called ===")
            logger.info(f"User: {request.user.username}")
            logger.info(f"User authenticated: {request.user.is_authenticated}")
            logger.info(f"Request data: {request.data}")
            logger.info(f"User has profile: {hasattr(request.user, 'profile')}")
            if hasattr(request.user, 'profile'):
                logger.info(f"User role: {request.user.profile.role}")
            
            # Get the animal
            animal_id = request.data.get('animal')
            if not animal_id:
                logger.error("Animal ID is missing from request")
                return Response({'error': 'Animal ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                animal = Animal.objects.get(id=animal_id)
            except Animal.DoesNotExist:
                return Response({'error': 'Animal not found'}, status=status.HTTP_404_NOT_FOUND)

            # Check if animal is already slaughtered
            if animal.slaughtered:
                return Response({'error': 'Animal has already been slaughtered'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if user has permission to submit carcass measurements for this animal
            user_can_slaughter = False
            processing_unit_name = None

            if hasattr(request.user, 'profile'):
                user_role = request.user.profile.role

                if user_role == 'Farmer':
                    # Farmers can submit measurements for their own animals
                    if animal.farmer == request.user:
                        user_can_slaughter = True
                        processing_unit_name = 'Direct Farmer Submission'
                        logger.info(f"Farmer {request.user.username} authorized to slaughter animal {animal.animal_id}")
                elif user_role == 'ProcessingUnit':
                    # Processing units can submit measurements for animals transferred to them
                    processing_unit = request.user.profile.processing_unit
                    if processing_unit and animal.transferred_to == processing_unit:
                        user_can_slaughter = True
                        processing_unit_name = processing_unit.name
                        logger.info(f"ProcessingUnit {processing_unit.name} authorized to slaughter animal {animal.animal_id}")
                    else:
                        logger.warning(f"ProcessingUnit check failed - animal.transferred_to: {animal.transferred_to}, user.processing_unit: {processing_unit}")

            if not user_can_slaughter:
                logger.error(f"Permission denied for {request.user.username} to slaughter animal {animal.animal_id}. User role: {request.user.profile.role if hasattr(request.user, 'profile') else 'No profile'}, Animal farmer: {animal.farmer}, Animal transferred_to: {animal.transferred_to}")
                return Response({'error': 'You do not have permission to submit carcass measurements for this animal'}, status=status.HTTP_403_FORBIDDEN)

            # Create the carcass measurement
            response = super().create(request, *args, **kwargs)

            if response.status_code == status.HTTP_201_CREATED:
                # Mark animal as slaughtered
                animal.slaughtered = True
                animal.slaughtered_at = timezone.now()
                animal.save()

                # Create audit log
                audit_context = {}
                if hasattr(request.user, 'profile') and request.user.profile.role == 'ProcessingUnit':
                    audit_context['processing_unit'] = request.user.profile.processing_unit

                UserAuditLog.objects.create(
                    performed_by=request.user,
                    affected_user=animal.farmer,
                    processing_unit=audit_context.get('processing_unit'),
                    action='animal_slaughtered',
                    description=f'Animal {animal.animal_id} slaughtered via carcass measurement submission',
                    old_values={'slaughtered': False},
                    new_values={'slaughtered': True, 'slaughtered_at': animal.slaughtered_at.isoformat()},
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )

                # Add confirmation message to response
                response.data['confirmation'] = {
                    'message': f'Animal {animal.animal_id} has been successfully slaughtered and removed from the registered animals list.',
                    'slaughtered_at': animal.slaughtered_at.isoformat(),
                    'submitted_by': processing_unit_name or 'Farmer'
                }

            return response

        except Exception as e:
            logger.error(f"Error creating carcass measurement: {str(e)}")
            return Response({'error': 'Failed to create carcass measurement'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SlaughterPartViewSet(viewsets.ModelViewSet):
    queryset = SlaughterPart.objects.all()
    serializer_class = SlaughterPartSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['animal', 'part_type', 'transferred_to', 'used_in_product']
    search_fields = ['animal__animal_id', 'part_type']
    ordering_fields = ['created_at', 'weight']
    pagination_class = None  # Disable pagination for slaughter parts

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Processing units can only see slaughter parts from animals transferred to them
        if hasattr(user, 'profile') and user.profile.role == 'ProcessingUnit':
            queryset = queryset.filter(animal__transferred_to=user)

        return queryset


class ProcessingUnitViewSet(viewsets.ModelViewSet):
    queryset = ProcessingUnit.objects.all()
    serializer_class = ProcessingUnitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description', 'location']
    ordering_fields = ['name', 'created_at']
    pagination_class = None  # Disable pagination for processing units


class ProcessingUnitUserViewSet(viewsets.ModelViewSet):
    queryset = ProcessingUnitUser.objects.all()
    serializer_class = ProcessingUnitUserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['processing_unit', 'role', 'is_active', 'is_suspended']
    search_fields = ['user__username', 'user__email']
    ordering_fields = ['joined_at', 'role']
    pagination_class = None  # Disable pagination for processing unit users

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Users can only see memberships in processing units they're members of
        if hasattr(user, 'profile') and user.profile.role == 'ProcessingUnit':
            queryset = queryset.filter(processing_unit__processingunituser__user=user)

        return queryset


class ProductIngredientViewSet(viewsets.ModelViewSet):
    queryset = ProductIngredient.objects.all()
    serializer_class = ProductIngredientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product', 'slaughter_part']
    search_fields = ['slaughter_part__part_type']
    ordering_fields = ['quantity_used']
    pagination_class = None  # Disable pagination for product ingredients

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Processing units can only see ingredients for their products
        if hasattr(user, 'profile') and user.profile.role == 'ProcessingUnit':
            # Get the user's processing unit from profile or active membership
            processing_unit = user.profile.processing_unit

            # If profile.processing_unit is not set, try to get it from active membership
            if not processing_unit:
                logger.warning(f"User {user.username} has role ProcessingUnit but profile.processing_unit is None in ProductIngredientViewSet.get_queryset")
                active_membership = ProcessingUnitUser.objects.filter(
                    user=user,
                    is_active=True
                ).select_related('processing_unit').first()

                if active_membership:
                    processing_unit = active_membership.processing_unit
                    # Fix the profile to prevent this issue in the future
                    logger.info(f"Auto-fixing profile.processing_unit for user {user.username} to {processing_unit.name} in ProductIngredientViewSet")
                    user.profile.processing_unit = processing_unit
                    user.profile.save()
                else:
                    # User has no processing unit association - return empty queryset
                    logger.error(f"User {user.username} has no active processing unit membership in ProductIngredientViewSet.get_queryset")
                    return queryset.none()

            # Filter by the correct ProcessingUnit instance
            if processing_unit:
                queryset = queryset.filter(product__processing_unit=processing_unit)
            else:
                # No processing unit found - return empty queryset
                logger.error(f"User {user.username} has no associated processing unit in ProductIngredientViewSet")
                queryset = queryset.none()

        return queryset


class ShopViewSet(viewsets.ModelViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description', 'location']
    ordering_fields = ['name', 'created_at']
    pagination_class = None  # Disable pagination for shops


class ShopUserViewSet(viewsets.ModelViewSet):
    queryset = ShopUser.objects.all()
    serializer_class = ShopUserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shop', 'role', 'is_active']
    search_fields = ['user__username', 'user__email']
    ordering_fields = ['joined_at', 'role']
    pagination_class = None  # Disable pagination for shop users

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Users can only see memberships in shops they're members of
        if hasattr(user, 'profile') and user.profile.role == 'Shop':
            queryset = queryset.filter(shop__shopuser__user=user)

        return queryset


class UserAuditLogViewSet(viewsets.ModelViewSet):
    queryset = UserAuditLog.objects.all()
    serializer_class = UserAuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['performed_by', 'affected_user', 'processing_unit', 'shop', 'action']
    search_fields = ['description', 'action']
    ordering_fields = ['timestamp']
    pagination_class = None  # Disable pagination for audit logs

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Users can only see audit logs related to their entities
        if hasattr(user, 'profile'):
            if user.profile.role == 'ProcessingUnit':
                queryset = queryset.filter(
                    Q(processing_unit__processingunituser__user=user) |
                    Q(performed_by=user) |
                    Q(affected_user=user)
                ).distinct()
            elif user.profile.role == 'Shop':
                queryset = queryset.filter(
                    Q(shop__shopuser__user=user) |
                    Q(performed_by=user) |
                    Q(affected_user=user)
                ).distinct()

        return queryset


# Activity Feed Views

class ActivityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing farmer activity feed
    """
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['activity_type', 'entity_type']
    search_fields = ['title', 'description']
    ordering_fields = ['timestamp', 'created_at']
    ordering = ['-timestamp']
    pagination_class = None  # Disable pagination for activities

    def get_queryset(self):
        """Filter activities to show only user's own activities"""
        return Activity.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Automatically set user when creating activity"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent activities (last 10 by default)"""
        limit = int(request.query_params.get('limit', 10))
        activities = self.get_queryset()[:limit]
        serializer = self.get_serializer(activities, many=True)
        return Response({'activities': serializer.data})

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get activities filtered by type"""
        activity_type = request.query_params.get('type')
        if not activity_type:
            return Response(
                {'error': 'Activity type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activities = self.get_queryset().filter(activity_type=activity_type)
        serializer = self.get_serializer(activities, many=True)
        return Response({'activities': serializer.data})

    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        """Get activities for a specific entity"""
        entity_id = request.query_params.get('entity_id')
        entity_type = request.query_params.get('entity_type')
        
        if not entity_id:
            return Response(
                {'error': 'entity_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        filters = {'entity_id': entity_id}
        if entity_type:
            filters['entity_type'] = entity_type
        
        activities = self.get_queryset().filter(**filters)
        serializer = self.get_serializer(activities, many=True)
        return Response({'activities': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_activity(request):
    """
    Convenience endpoint to quickly log an activity
    Usage: POST /activities/log/ with activity data
    """
    serializer = ActivitySerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_registration_activity(request):
    """Log an animal registration activity"""
    animal_id = request.data.get('animal_id')
    animal_tag = request.data.get('animal_tag')
    
    if not animal_id or not animal_tag:
        return Response(
            {'error': 'animal_id and animal_tag are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    activity = Activity.objects.create(
        user=request.user,
        activity_type='registration',
        title=f'Animal {animal_tag} registered',
        entity_id=str(animal_id),
        entity_type='animal',
        target_route=f'/animals/{animal_id}',
        timestamp=timezone.now()
    )
    
    serializer = ActivitySerializer(activity)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_transfer_activity(request):
    """Log an animal transfer activity"""
    count = request.data.get('count', 1)
    processor_name = request.data.get('processor_name')
    batch_id = request.data.get('batch_id')
    
    if not processor_name:
        return Response(
            {'error': 'processor_name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    activity = Activity.objects.create(
        user=request.user,
        activity_type='transfer',
        title=f'{count} animal{"s" if count > 1 else ""} transferred to {processor_name}',
        entity_id=str(batch_id) if batch_id else None,
        entity_type='transfer',
        metadata={'count': count, 'processor': processor_name},
        target_route='/farmer/livestock-history',
        timestamp=timezone.now()
    )
    
    serializer = ActivitySerializer(activity)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

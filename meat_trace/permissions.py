from rest_framework import permissions
from .models import UserProfile, ShopUser

class IsFarmer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.profile.role == 'Farmer'

class IsProcessingUnit(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.profile.role == 'ProcessingUnit'

class IsShop(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.profile.role == 'Shop'

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object.
        return obj.farmer == request.user

class IsProcessingUnitOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.processing_unit == request.user

class IsShopOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.shop == request.user


class IsShopMember(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        shop_id = view.kwargs.get('shop_id')
        if shop_id:
            return ShopUser.objects.filter(
                user=request.user,
                shop_id=shop_id,
                is_active=True
            ).exists()
        return False

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check if user is a member of the shop
        try:
            membership = ShopUser.objects.get(
                user=request.user,
                shop=obj,
                is_active=True
            )
            return True
        except ShopUser.DoesNotExist:
            return False


class HasShopPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check if user is a member of the shop
        try:
            membership = ShopUser.objects.get(
                user=request.user,
                shop=obj,
                is_active=True
            )

            # Define permissions based on role
            role_permissions = {
                'owner': ['read', 'write', 'admin'],
                'manager': ['read', 'write'],
                'salesperson': ['read', 'write'],
                'cashier': ['read', 'write'],
                'inventory_clerk': ['read', 'write']
            }

            required_permission = self.get_required_permission(request.method, view.action)
            return membership.permissions in role_permissions.get(membership.role, [])

        except ShopUser.DoesNotExist:
            return False

    def get_required_permission(self, method, action):
        if method in permissions.SAFE_METHODS:
            return 'read'
        elif action in ['create', 'update', 'partial_update', 'destroy']:
            return 'write'
        else:
            return 'admin'


class IsProcessingUnitMember(permissions.BasePermission):
    """
    Check if user is an active member of the processing unit specified in the URL.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        processing_unit_id = view.kwargs.get('processing_unit_id')
        if processing_unit_id:
            from .models import ProcessingUnitUser
            return ProcessingUnitUser.objects.filter(
                user=request.user,
                processing_unit_id=processing_unit_id,
                is_active=True,
                is_suspended=False
            ).exists()
        return False


class CanManageProcessingUnitUsers(permissions.BasePermission):
    """
    Check if user can manage other users in the processing unit (owner/manager only).
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        processing_unit_id = view.kwargs.get('processing_unit_id')
        if processing_unit_id:
            from .models import ProcessingUnitUser
            try:
                membership = ProcessingUnitUser.objects.get(
                    user=request.user,
                    processing_unit_id=processing_unit_id,
                    is_active=True,
                    is_suspended=False
                )
                return membership.role in ['owner', 'manager']
            except ProcessingUnitUser.DoesNotExist:
                return False
        return False
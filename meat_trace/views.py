from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import models
from django.db.models import Prefetch
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage, ProductTimelineEvent, Inventory, Order, OrderItem
from .serializers import AnimalSerializer, ProductSerializer, ReceiptSerializer, ProductCategorySerializer, ProcessingStageSerializer, ProductTimelineEventSerializer, InventorySerializer, OrderSerializer, OrderItemSerializer
from .permissions import IsFarmer, IsProcessingUnit, IsShop, IsOwnerOrReadOnly, IsProcessingUnitOwner, IsShopOwner
import logging

logger = logging.getLogger(__name__)

class AnimalViewSet(viewsets.ModelViewSet):
    serializer_class = AnimalSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['species', 'slaughtered']
    search_fields = ['species', 'animal_id', 'animal_name']
    ordering_fields = ['created_at', 'weight']
    ordering = ['-created_at']
    permission_classes = [IsAuthenticated, IsFarmer]

    def get_queryset(self):
        return Animal.objects.all()  # Return all animals for testing

    def perform_create(self, serializer):
        serializer.save(farmer=self.request.user)

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsFarmer])
    def slaughter(self, request, pk=None):
        animal = self.get_object()
        if animal.farmer != request.user:
            return Response({'error': 'You can only slaughter your own animals'}, status=status.HTTP_403_FORBIDDEN)
        if animal.slaughtered:
            return Response({'error': 'Animal is already slaughtered'}, status=status.HTTP_400_BAD_REQUEST)
        animal.slaughtered = True
        animal.slaughtered_at = timezone.now()
        animal.save()
        logger.info(f"Animal {animal.id} slaughtered by {request.user.username}")
        return Response({'message': 'Animal slaughtered successfully'})

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsFarmer])
    def transfer(self, request):
        logger.info(f"Transfer request data: {request.data}")
        animal_ids = request.data.get('animal_ids', [])
        processing_unit_id = request.data.get('processing_unit_id')

        logger.info(f"Animal IDs: {animal_ids}, Processing Unit ID: {processing_unit_id}")

        if not animal_ids:
            return Response({'error': 'No animals selected for transfer'}, status=status.HTTP_400_BAD_REQUEST)

        if not processing_unit_id:
            return Response({'error': 'Processing unit ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate processing unit exists and has correct role
        try:
            processing_unit = User.objects.get(id=processing_unit_id, profile__role='ProcessingUnit')
        except User.DoesNotExist:
            return Response({'error': 'Invalid processing unit'}, status=status.HTTP_400_BAD_REQUEST)

        transferred_animals = []
        failed_animals = []

        for animal_id in animal_ids:
            try:
                animal = Animal.objects.get(id=animal_id, farmer=request.user)
                if not animal.slaughtered:
                    failed_animals.append({
                        'id': animal_id,
                        'reason': 'Animal not slaughtered'
                    })
                    continue

                # Create transfer record (we'll add this model later)
                # For now, just mark as transferred
                animal.save()  # Could add a transferred field later
                transferred_animals.append(animal_id)

                logger.info(f"Animal {animal.id} transferred by {request.user.username} to processing unit {processing_unit.username}")

            except Animal.DoesNotExist:
                failed_animals.append({
                    'id': animal_id,
                    'reason': 'Animal not found or not owned by you'
                })

        response_data = {
            'transferred_count': len(transferred_animals),
            'transferred_animals': transferred_animals,
            'failed_count': len(failed_animals),
            'failed_animals': failed_animals,
            'processing_unit': processing_unit.username
        }

        if failed_animals:
            response_data['message'] = f'Transferred {len(transferred_animals)} animals, {len(failed_animals)} failed'
        else:
            response_data['message'] = f'Successfully transferred {len(transferred_animals)} animals'

        return Response(response_data, status=status.HTTP_200_OK)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product_type', 'animal']
    search_fields = ['product_type']
    ordering_fields = ['created_at', 'quantity']
    ordering = ['-created_at']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        return Product.objects.select_related('animal').all()  # Return all products for testing

    def perform_create(self, serializer):
        animal = serializer.validated_data['animal']
        if not animal.slaughtered:
            raise serializers.ValidationError("Cannot create product from non-slaughtered animal")
        serializer.save(processing_unit=self.request.user)
        logger.info(f"Product created by {self.request.user.username} from animal {animal.id}")

class ReceiptViewSet(viewsets.ModelViewSet):
    serializer_class = ReceiptSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product']
    search_fields = ['product__product_type']
    ordering_fields = ['received_at']
    ordering = ['-received_at']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        return Receipt.objects.select_related('product').all()  # Return all receipts for testing

    def perform_create(self, serializer):
        serializer.save(shop=self.request.user)
        logger.info(f"Receipt created by {self.request.user.username} for product {serializer.validated_data['product'].id}")

class ProductCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = ProductCategorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        return ProductCategory.objects.all()

class ProcessingStageViewSet(viewsets.ModelViewSet):
    serializer_class = ProcessingStageSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['order']
    ordering = ['order']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        return ProcessingStage.objects.all()

class ProductTimelineEventViewSet(viewsets.ModelViewSet):
    serializer_class = ProductTimelineEventSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product', 'stage']
    search_fields = ['action', 'location']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        return ProductTimelineEvent.objects.select_related('product', 'stage').all()

    def perform_create(self, serializer):
        serializer.save()
        logger.info(f"Timeline event created for product {serializer.validated_data['product'].id}")

class InventoryViewSet(viewsets.ModelViewSet):
    serializer_class = InventorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shop', 'product', 'quantity']
    search_fields = ['product__name', 'product__batch_number']
    ordering_fields = ['quantity', 'last_updated']
    ordering = ['-last_updated']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        return Inventory.objects.select_related('product', 'shop').all()

    def perform_create(self, serializer):
        serializer.save(shop=self.request.user)
        logger.info(f"Inventory created for shop {self.request.user.username}")

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def low_stock(self, request):
        """Get inventory items that are below minimum stock level"""
        low_stock_items = self.get_queryset().filter(
            quantity__lte=models.F('min_stock_level')
        )
        serializer = self.get_serializer(low_stock_items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def adjust_stock(self, request, pk=None):
        """Adjust stock quantity"""
        inventory = self.get_object()
        adjustment = request.data.get('adjustment', 0)
        reason = request.data.get('reason', '')

        try:
            adjustment_value = float(adjustment)
            new_quantity = inventory.quantity + adjustment_value

            if new_quantity < 0:
                return Response(
                    {'error': 'Stock adjustment would result in negative quantity'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            inventory.quantity = new_quantity
            inventory.last_updated = timezone.now()
            inventory.save()

            logger.info(f"Stock adjusted by {adjustment_value} for {inventory.product.name} at {inventory.shop.username}. Reason: {reason}")

            serializer = self.get_serializer(inventory)
            return Response(serializer.data)

        except ValueError:
            return Response(
                {'error': 'Invalid adjustment value'},
                status=status.HTTP_400_BAD_REQUEST
            )

class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['order', 'product']
    search_fields = ['product__name']
    ordering_fields = ['quantity', 'subtotal']
    ordering = ['-quantity']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        return OrderItem.objects.select_related('order', 'product').all()

    def perform_create(self, serializer):
        serializer.save()
        logger.info(f"Order item created for order {serializer.validated_data['order'].id}")

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['customer', 'shop', 'status']
    search_fields = ['customer__username', 'shop__username']
    ordering_fields = ['created_at', 'total_amount', 'updated_at']
    ordering = ['-created_at']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        return Order.objects.select_related('customer', 'shop').prefetch_related('items').all()

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)
        logger.info(f"Order created by {self.request.user.username}")

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_status(self, request, pk=None):
        """Update order status"""
        order = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(Order.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = new_status
        order.save()

        logger.info(f"Order {order.id} status updated to {new_status} by {request.user.username}")

        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_orders(self, request):
        """Get orders for current user (as customer)"""
        orders = self.get_queryset().filter(customer=request.user)
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def shop_orders(self, request):
        """Get orders for current user's shop"""
        orders = self.get_queryset().filter(shop=request.user)
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new user with role-based profile.
    """
    # Enhanced logging for debugging
    logger.info("=== REGISTRATION REQUEST DEBUG ===")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request content type: {request.content_type}")
    logger.info(f"Request data: {request.data}")
    logger.info("===================================")
    
    try:
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        role = request.data.get('role', 'Farmer')  # Default to Farmer

        logger.info(f"Parsed data - Username: {username}, Email: {email}, Role: {role}")

        if not username or not email or not password:
            error_msg = 'Username, email, and password are required'
            logger.warning(f"Registration validation failed: {error_msg}")
            return Response(
                {'error': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(username=username).exists():
            error_msg = 'Username already exists'
            logger.warning(f"Registration failed: {error_msg} - {username}")
            return Response(
                {'error': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            error_msg = 'Email already exists'
            logger.warning(f"Registration failed: {error_msg} - {email}")
            return Response(
                {'error': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate role
        valid_roles = ['Farmer', 'ProcessingUnit', 'Shop']
        if role not in valid_roles:
            error_msg = f'Invalid role. Must be one of: {", ".join(valid_roles)}'
            logger.warning(f"Registration failed: {error_msg} - {role}")
            return Response(
                {'error': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Creating user: {username}")
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        logger.info(f"User created successfully: {user.id}")

        # Update profile with role (profile is created by signal)
        logger.info(f"Updating profile with role: {role}")
        profile = user.profile
        profile.role = role
        profile.save()
        logger.info(f"Profile updated successfully")

        # Generate tokens
        logger.info("Generating JWT tokens")
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        logger.info("JWT tokens generated successfully")

        logger.info(f"User {username} registered successfully with role {role}")

        response_data = {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': role
            },
            'tokens': {
                'refresh': str(refresh),
                'access': access_token
            }
        }
        logger.info(f"Sending response: {response_data}")
        
        return Response(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response(
            {'error': f'Registration failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_file(request):
    """
    Upload a file (image/document) for an entity.
    """
    try:
        uploaded_file = request.FILES.get('file')
        entity_type = request.data.get('entity_type')  # 'animal', 'product', 'receipt'
        entity_id = request.data.get('entity_id')

        if not uploaded_file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not entity_type or not entity_id:
            return Response(
                {'error': 'Entity type and ID are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file size (max 10MB)
        if uploaded_file.size > 10 * 1024 * 1024:
            return Response(
                {'error': 'File size too large (max 10MB)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
        if uploaded_file.content_type not in allowed_types:
            return Response(
                {'error': 'File type not allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save file
        file_name = f"{entity_type}_{entity_id}_{uploaded_file.name}"
        file_path = f"uploads/{entity_type}/{file_name}"

        # Ensure directory exists
        import os
        os.makedirs(f"media/uploads/{entity_type}", exist_ok=True)

        with open(f"media/{file_path}", 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        logger.info(f"File uploaded by {request.user.username}: {file_path}")

        return Response({
            'file_url': f"/media/{file_path}",
            'file_name': file_name,
            'entity_type': entity_type,
            'entity_id': entity_id,
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return Response(
            {'error': 'File upload failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for API connectivity testing.
    """
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def server_info(request):
    """
    Server information endpoint.
    """
    return Response({
        'name': 'Meat Trace API',
        'version': '1.0.0',
        'django_version': '5.2.6',
        'endpoints': [
            '/api/v1/animals/',
            '/api/v1/products/',
            '/api/v1/receipts/',
            '/api/v1/token/',
            '/api/v1/token/refresh/',
            '/api/v1/register/',
            '/api/v1/upload/',
            '/api/v1/health/',
            '/api/v1/info/',
        ]
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def meat_trace_list(request):
    """
    Meat trace endpoint - combines animals, products, and receipts for traceability.
    """
    try:
        # Return sample data for testing since there might not be any data yet
        traces = [
            {
                'id': 'trace_sample_1',
                'animal': {
                    'id': 1,
                    'species': 'Cattle',
                    'weight': 450.0,
                    'farmer': 'sample_farmer',
                    'slaughtered': True,
                    'slaughtered_at': '2025-09-18T10:00:00Z',
                },
                'product': {
                    'id': 1,
                    'product_type': 'Fresh Beef',
                    'quantity': 200.0,
                    'processing_unit': 'sample_processor',
                    'created_at': '2025-09-18T11:00:00Z',
                },
                'receipt': {
                    'id': 1,
                    'received_quantity': 200.0,
                    'shop': 'sample_shop',
                    'received_at': '2025-09-18T12:00:00Z',
                },
                'status': 'complete',
                'created_at': '2025-09-18T09:00:00Z',
            }
        ]
        
        return Response({
            'results': traces,
            'count': len(traces)
        })
        
    except Exception as e:
        logger.error(f"Meat trace list error: {str(e)}")
        return Response(
            {'error': 'Failed to fetch meat traces'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def categories_list(request):
    """
    Product categories endpoint.
    """
    categories = [
        {'id': 1, 'name': 'Fresh Meat', 'description': 'Fresh cuts of meat'},
        {'id': 2, 'name': 'Processed Meat', 'description': 'Processed meat products'},
        {'id': 3, 'name': 'Organic Meat', 'description': 'Organic meat products'},
        {'id': 4, 'name': 'Premium Cuts', 'description': 'Premium quality cuts'},
    ]

    return Response({
        'results': categories,
        'count': len(categories)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Get current user profile with role information.
    """
    try:
        user = request.user
        profile = user.profile

        response_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': profile.role,
            'date_joined': user.date_joined.isoformat(),
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"User profile error: {str(e)}")
        return Response(
            {'error': 'Failed to get user profile'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

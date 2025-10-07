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
from .models import Animal, Product, Receipt, UserProfile, ProductCategory, ProcessingStage, ProductTimelineEvent, Inventory, Order, OrderItem, CarcassMeasurement
from .serializers import AnimalSerializer, ProductSerializer, ReceiptSerializer, ProductCategorySerializer, ProcessingStageSerializer, ProductTimelineEventSerializer, InventorySerializer, OrderSerializer, OrderItemSerializer, CarcassMeasurementSerializer
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
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_profile = user.profile

        if user_profile.role == 'Farmer':
            # Farmers see only their own animals that haven't been transferred
            # Allow filtering by slaughtered status via query parameters
            queryset = Animal.objects.filter(
                farmer=user,
                transferred_to__isnull=True
            ).select_related('farmer')

            # Apply slaughtered filter if specified in query params
            slaughtered_param = self.request.query_params.get('slaughtered')
            if slaughtered_param is not None:
                slaughtered = slaughtered_param.lower() == 'true'
                queryset = queryset.filter(slaughtered=slaughtered)

            return queryset
        elif user_profile.role == 'ProcessingUnit':
            # Processing units see animals transferred to them or received by them
            # Exclude animals that have already been used to create products
            return Animal.objects.filter(
                models.Q(transferred_to=user) | models.Q(received_by=user),
                slaughtered=True
            ).exclude(
                products__isnull=False
            ).select_related('farmer')
        else:
            # Other roles (like Shop) might need different filtering
            return Animal.objects.none()

    def perform_create(self, serializer):
        serializer.save(farmer=self.request.user)

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsFarmer])
    def slaughter(self, request, pk=None):
        animal = self.get_object()
        if animal.farmer != request.user:
            return Response({'error': 'You can only slaughter your own animals'}, status=status.HTTP_403_FORBIDDEN)
        if animal.slaughtered:
            return Response({'error': 'This animal has already been slaughtered'}, status=status.HTTP_400_BAD_REQUEST)
        # Mark animal as slaughtered
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

                # Mark animal as transferred
                animal.transferred_to = processing_unit
                animal.transferred_at = timezone.now()
                animal.save()
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

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsProcessingUnit])
    def transferred_animals(self, request):
        """Get animals transferred to this processing unit"""
        transferred_animals = Animal.objects.filter(
            transferred_to=request.user,
            slaughtered=True
        ).select_related('farmer')

        serializer = self.get_serializer(transferred_animals, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsFarmer])
    def my_transferred_animals(self, request):
        """Get animals transferred by this farmer"""
        transferred_animals = Animal.objects.filter(
            farmer=request.user,
            transferred_to__isnull=False,
            slaughtered=True
        ).select_related('transferred_to')

        serializer = self.get_serializer(transferred_animals, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsProcessingUnit])
    def receive_animals(self, request):
        """Receive transferred animals"""
        animal_ids = request.data.get('animal_ids', [])

        if not animal_ids:
            return Response({'error': 'No animals selected for receipt'}, status=status.HTTP_400_BAD_REQUEST)

        received_animals = []
        failed_animals = []

        for animal_id in animal_ids:
            try:
                animal = Animal.objects.get(
                    id=animal_id,
                    transferred_to=request.user,
                    slaughtered=True
                )

                # Mark animal as received
                animal.transferred_to = None
                animal.received_by = request.user
                animal.received_at = timezone.now()
                animal.save()

                received_animals.append(animal_id)

                logger.info(f"Animal {animal.id} received by processing unit {request.user.username}")

            except Animal.DoesNotExist:
                failed_animals.append({
                    'id': animal_id,
                    'reason': 'Animal not found or not transferred to you'
                })

        response_data = {
            'received_count': len(received_animals),
            'received_animals': received_animals,
            'failed_count': len(failed_animals),
            'failed_animals': failed_animals,
        }

        if failed_animals:
            response_data['message'] = f'Received {len(received_animals)} animals, {len(failed_animals)} failed'
        else:
            response_data['message'] = f'Successfully received {len(received_animals)} animals'

        return Response(response_data, status=status.HTTP_200_OK)
class CarcassMeasurementViewSet(viewsets.ModelViewSet):
    serializer_class = CarcassMeasurementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['animal']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_profile = user.profile

        if user_profile.role == 'Farmer':
            # Farmers see carcass measurements for their own animals
            return CarcassMeasurement.objects.filter(
                animal__farmer=user
            ).select_related('animal')
        elif user_profile.role == 'ProcessingUnit':
            # Processing units see carcass measurements for animals they've received
            return CarcassMeasurement.objects.filter(
                animal__received_by=user
            ).select_related('animal')
        else:
            # Other roles might not need access to carcass measurements
            return CarcassMeasurement.objects.none()

    def perform_create(self, serializer):
        logger.info(f"CarcassMeasurement creation attempt by user {self.request.user.username}")
        logger.info(f"Request data: {self.request.data}")

        # Get animal from animal_id in validated_data
        animal_id = serializer.validated_data.get('animal_id')
        if animal_id:
            try:
                animal = Animal.objects.get(id=animal_id)
            except Animal.DoesNotExist:
                raise serializers.ValidationError("Animal not found.")
        else:
            # Fallback for old serializer format
            animal = serializer.validated_data.get('animal')

        if not animal:
            raise serializers.ValidationError("Animal is required.")

        logger.info(f"Animal ID: {animal.id}, Farmer: {animal.farmer.username}, Slaughtered: {animal.slaughtered}")
        logger.info(f"Animal transferred_to: {animal.transferred_to.username if animal.transferred_to else None}")
        logger.info(f"Animal received_by: {animal.received_by.username if animal.received_by else None}")

        # Ensure the user has permission to create measurements for this animal
        user = self.request.user
        user_profile = user.profile
        logger.info(f"User role: {user_profile.role}")

        if user_profile.role == 'Farmer' and animal.farmer != user:
            logger.warning(f"Farmer {user.username} tried to create measurement for animal {animal.id} owned by {animal.farmer.username}")
            raise serializers.ValidationError("You can only create carcass measurements for your own animals")
        elif user_profile.role == 'ProcessingUnit' and animal.received_by != user:
            logger.warning(f"ProcessingUnit {user.username} tried to create measurement for animal {animal.id} received by {animal.received_by.username if animal.received_by else 'None'}")
            raise serializers.ValidationError("You can only create carcass measurements for animals you've received")

        # Ensure animal is slaughtered
        if not animal.slaughtered:
            logger.warning(f"Attempted to create carcass measurement for non-slaughtered animal {animal.id}")
            raise serializers.ValidationError("Cannot create carcass measurements for non-slaughtered animals")

        logger.info(f"Saving carcass measurement for animal {animal.id}")
        serializer.save()
        logger.info(f"Carcass measurement created successfully for animal {animal.id}")


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product_type', 'animal']
    search_fields = ['product_type', 'name', 'batch_number']
    ordering_fields = ['created_at', 'quantity']
    ordering = ['-created_at']
    permission_classes = [AllowAny]  # Temporarily allow access for testing

    def get_queryset(self):
        user = self.request.user
        user_profile = user.profile

        if user_profile.role == 'ProcessingUnit':
            # Processing units see their own products that haven't been transferred
            return Product.objects.filter(
                processing_unit=user,
                transferred_to__isnull=True
            ).select_related('animal')
        elif user_profile.role == 'Shop':
            # Shops see products transferred to them or received by them
            return Product.objects.filter(
                models.Q(transferred_to=user) | models.Q(received_by=user)
            ).select_related('animal')
        else:
            # Other roles (like Farmer) might need different filtering
            return Product.objects.none()

    def perform_create(self, serializer):
        animal = serializer.validated_data['animal']
        if not animal.slaughtered:
            raise serializers.ValidationError("Cannot create product from non-slaughtered animal")
        serializer.save(processing_unit=self.request.user)
        logger.info(f"Product created by {self.request.user.username} from animal {animal.id}")

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsProcessingUnit])
    def transfer(self, request):
        """Transfer products to a shop"""
        logger.info(f"Product transfer request data: {request.data}")
        product_ids = request.data.get('product_ids', [])
        shop_id = request.data.get('shop_id')

        logger.info(f"Product IDs: {product_ids}, Shop ID: {shop_id}")

        if not product_ids:
            return Response({'error': 'No products selected for transfer'}, status=status.HTTP_400_BAD_REQUEST)

        if not shop_id:
            return Response({'error': 'Shop ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate shop exists and has correct role
        try:
            shop = User.objects.get(id=shop_id, profile__role='Shop')
        except User.DoesNotExist:
            return Response({'error': 'Invalid shop'}, status=status.HTTP_400_BAD_REQUEST)

        transferred_products = []
        failed_products = []

        for product_id in product_ids:
            try:
                product = Product.objects.get(id=product_id, processing_unit=request.user)
                if product.transferred_to is not None:
                    failed_products.append({
                        'id': product_id,
                        'reason': 'Product already transferred'
                    })
                    continue

                # Mark product as transferred
                product.transferred_to = shop
                product.transferred_at = timezone.now()
                product.save()
                transferred_products.append(product_id)

                logger.info(f"Product {product.id} transferred by {request.user.username} to shop {shop.username}")

            except Product.DoesNotExist:
                failed_products.append({
                    'id': product_id,
                    'reason': 'Product not found or not owned by you'
                })

        response_data = {
            'transferred_count': len(transferred_products),
            'transferred_products': transferred_products,
            'failed_count': len(failed_products),
            'failed_products': failed_products,
            'shop': shop.username
        }

        if failed_products:
            response_data['message'] = f'Transferred {len(transferred_products)} products, {len(failed_products)} failed'
        else:
            response_data['message'] = f'Successfully transferred {len(transferred_products)} products'

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsShop])
    def transferred_products(self, request):
        """Get products transferred to this shop"""
        transferred_products = Product.objects.filter(
            transferred_to=request.user
        ).select_related('animal', 'processing_unit')

        serializer = self.get_serializer(transferred_products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsShop])
    def receive_products(self, request):
        """Receive transferred products and automatically add to inventory"""
        product_ids = request.data.get('product_ids', [])

        if not product_ids:
            return Response({'error': 'No products selected for receipt'}, status=status.HTTP_400_BAD_REQUEST)

        received_products = []
        failed_products = []

        for product_id in product_ids:
            try:
                product = Product.objects.get(
                    id=product_id,
                    transferred_to=request.user
                )

                # Mark product as received
                product.transferred_to = None
                product.received_by = request.user
                product.received_at = timezone.now()
                product.save()

                # Create receipt to automatically update inventory
                receipt = Receipt.objects.create(
                    shop=request.user,
                    product=product,
                    received_quantity=product.quantity,
                    received_at=timezone.now()
                )

                received_products.append(product_id)

                logger.info(f"Product {product.id} received by shop {request.user.username} and added to inventory")

            except Product.DoesNotExist:
                failed_products.append({
                    'id': product_id,
                    'reason': 'Product not found or not transferred to you'
                })
            except Exception as e:
                failed_products.append({
                    'id': product_id,
                    'reason': f'Failed to process receipt: {str(e)}'
                })

        response_data = {
            'received_count': len(received_products),
            'received_products': received_products,
            'failed_count': len(failed_products),
            'failed_products': failed_products,
        }

        if failed_products:
            response_data['message'] = f'Received {len(received_products)} products, {len(failed_products)} failed'
        else:
            response_data['message'] = f'Successfully received {len(received_products)} products and added to inventory'

        return Response(response_data, status=status.HTTP_200_OK)

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
        return Inventory.objects.select_related('product', 'shop').filter(
            product__received_by__profile__role='Shop'
        )

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
    authentication_classes = []  # Disable authentication for this viewset

    def get_queryset(self):
        return Order.objects.select_related('customer', 'shop').prefetch_related('items').all()

    def perform_create(self, serializer):
        serializer.save()
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
            '/api/v2/animals/',
            '/api/v2/products/',
            '/api/v2/receipts/',
            '/api/v2/token/',
            '/api/v2/token/refresh/',
            '/api/v2/register/',
            '/api/v2/upload/',
            '/api/v2/health/',
            '/api/v2/info/',
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def processing_units_list(request):
    """
    Get list of all processing units for transfer selection.
    """
    try:
        processing_units = User.objects.filter(
            profile__role='ProcessingUnit'
        ).select_related('profile').values(
            'id', 'username', 'email', 'profile__role'
        )

        response_data = []
        for pu in processing_units:
            response_data.append({
                'id': pu['id'],
                'username': pu['username'],
                'email': pu['email'],
                'role': pu['profile__role']
            })

        return Response({
            'results': response_data,
            'count': len(response_data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Processing units list error: {str(e)}")
        return Response(
            {'error': 'Failed to get processing units list'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def shops_list(request):
    """
    Get list of all shops for product transfer selection.
    """
    try:
        shops = User.objects.filter(
            profile__role='Shop'
        ).select_related('profile').values(
            'id', 'username', 'email', 'profile__role'
        )

        response_data = []
        for shop in shops:
            response_data.append({
                'id': shop['id'],
                'username': shop['username'],
                'email': shop['email'],
                'role': shop['profile__role']
            })

        return Response({
            'results': response_data,
            'count': len(response_data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Shops list error: {str(e)}")
        return Response(
            {'error': 'Failed to get shops list'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsProcessingUnit])
def production_stats(request):
    """
    Get production statistics for the current processing unit.
    """
    try:
        user = request.user
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timezone.timedelta(days=7)

        # Total products created by this processing unit
        total_products = Product.objects.filter(processing_unit=user).count()

        # Products created today
        products_today = Product.objects.filter(
            processing_unit=user,
            created_at__gte=today_start
        ).count()

        # Products created this week
        products_this_week = Product.objects.filter(
            processing_unit=user,
            created_at__gte=week_start
        ).count()

        # Total animals received by this processing unit
        total_animals_received = Animal.objects.filter(
            received_by=user
        ).count()

        # Animals received today
        animals_received_today = Animal.objects.filter(
            received_by=user,
            received_at__gte=today_start
        ).count()

        # Animals received this week
        animals_received_this_week = Animal.objects.filter(
            received_by=user,
            received_at__gte=week_start
        ).count()

        # Processing throughput (products per day this week)
        days_this_week = max(1, (now - week_start).days)
        throughput_per_day = products_this_week / days_this_week

        # Equipment uptime (simulated - in real app this would come from equipment monitoring)
        # For now, we'll simulate based on processing activity
        equipment_uptime = 95.5  # percentage

        # Inventory levels (processing units might have raw materials inventory)
        # For now, we'll show pending animals to process
        pending_animals = Animal.objects.filter(
            received_by=user,
            products__isnull=True  # Animals that haven't been turned into products yet
        ).count()

        # Products transferred stats
        total_products_transferred = Product.objects.filter(
            processing_unit=user,
            transferred_to__isnull=False
        ).count()

        products_transferred_today = Product.objects.filter(
            processing_unit=user,
            transferred_to__isnull=False,
            transferred_at__gte=today_start
        ).count()

        # Transfer success rate (transferred products / total products created)
        transfer_success_rate = (total_products_transferred / total_products * 100) if total_products > 0 else 0.0

        # Operational status
        operational_status = "operational"  # Could be: operational, maintenance, offline

        response_data = {
            'total_products_created': total_products,
            'products_created_today': products_today,
            'products_created_this_week': products_this_week,
            'total_animals_received': total_animals_received,
            'animals_received_today': animals_received_today,
            'animals_received_this_week': animals_received_this_week,
            'processing_throughput_per_day': round(throughput_per_day, 2),
            'equipment_uptime_percentage': equipment_uptime,
            'pending_animals_to_process': pending_animals,
            'operational_status': operational_status,
            'total_products_transferred': total_products_transferred,
            'products_transferred_today': products_transferred_today,
            'transfer_success_rate': round(transfer_success_rate, 1),
            'last_updated': now.isoformat()
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Production stats error: {str(e)}")
        return Response(
            {'error': 'Failed to get production stats'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def yield_trends(request):
    """
    Get yield trends data based on user role and time period.
    """
    try:
        user = request.user
        user_profile = user.profile
        period = request.GET.get('period', '7d')
        role = request.GET.get('role', user_profile.role.lower())
        
        now = timezone.now()
        
        # Calculate date range based on period
        if period == '7d':
            start_date = now - timezone.timedelta(days=7)
            date_format = '%a'  # Mon, Tue, Wed
        elif period == '30d':
            start_date = now - timezone.timedelta(days=30)
            date_format = '%m/%d'  # MM/DD
        elif period == '90d':
            start_date = now - timezone.timedelta(days=90)
            date_format = 'W%U'  # Week number
        elif period == '1y':
            start_date = now - timezone.timedelta(days=365)
            date_format = '%b'  # Jan, Feb, Mar
        else:
            start_date = now - timezone.timedelta(days=7)
            date_format = '%a'
            period = '7d'

        if role == 'farmer':
            return _get_farmer_yield_trends(user, start_date, now, period, date_format, request)
        elif role in ['processingunit', 'processor']:
            return _get_processor_yield_trends(user, start_date, now, period, date_format, request)
        elif role == 'shop':
            return _get_shop_yield_trends(user, start_date, now, period, date_format, request)
        else:
            return Response(
                {'error': 'Invalid role'},
                status=status.HTTP_400_BAD_REQUEST
            )

    except Exception as e:
        logger.error(f"Yield trends error: {str(e)}")
        return Response(
            {'error': 'Failed to get yield trends'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _get_farmer_yield_trends(user, start_date, end_date, period, date_format, request):
    """Get yield trends for farmers"""
    species_filter = request.GET.get('species')
    
    # Base queryset for farmer's animals
    animals_qs = Animal.objects.filter(
        farmer=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    if species_filter:
        animals_qs = animals_qs.filter(species=species_filter)
    
    # Generate time series data
    days = (end_date - start_date).days
    labels = []
    animal_counts = []
    slaughter_rates = []
    transfer_rates = []
    health_scores = []
    
    for i in range(days):
        current_date = start_date + timezone.timedelta(days=i)
        next_date = current_date + timezone.timedelta(days=1)
        
        # Animals created on this day
        daily_animals = animals_qs.filter(
            created_at__gte=current_date,
            created_at__lt=next_date
        ).count()
        
        # Animals slaughtered on this day
        daily_slaughtered = animals_qs.filter(
            slaughtered_at__gte=current_date,
            slaughtered_at__lt=next_date
        ).count()
        
        # Animals transferred on this day
        daily_transferred = animals_qs.filter(
            transferred_at__gte=current_date,
            transferred_at__lt=next_date
        ).count()
        
        # Calculate rates
        total_animals_to_date = animals_qs.filter(created_at__lt=next_date).count()
        slaughter_rate = (daily_slaughtered / max(total_animals_to_date, 1)) * 100
        transfer_rate = (daily_transferred / max(total_animals_to_date, 1)) * 100
        
        # Mock health score (in real app, this would come from health records)
        health_score = 85 + (i % 10) + (daily_animals * 2)
        
        labels.append(current_date.strftime(date_format))
        animal_counts.append(float(daily_animals))
        slaughter_rates.append(slaughter_rate)
        transfer_rates.append(transfer_rate)
        health_scores.append(min(health_score, 100))
    
    # Calculate trends (percentage change from first to last value)
    def calculate_trend(values):
        if len(values) < 2 or values[0] == 0:
            return 0.0
        return ((values[-1] - values[0]) / values[0]) * 100
    
    response_data = {
        'period': period,
        'role': 'farmer',
        'primary_metric': {
            'name': 'Animal Count',
            'values': animal_counts,
            'unit': 'animals',
            'trend': calculate_trend(animal_counts),
            'is_positive': calculate_trend(animal_counts) >= 0,
        },
        'secondary_metrics': [
            {
                'name': 'Slaughter Rate',
                'values': slaughter_rates,
                'unit': '%',
                'trend': calculate_trend(slaughter_rates),
                'is_positive': calculate_trend(slaughter_rates) >= 0,
            },
            {
                'name': 'Transfer Rate',
                'values': transfer_rates,
                'unit': '%',
                'trend': calculate_trend(transfer_rates),
                'is_positive': calculate_trend(transfer_rates) >= 0,
            },
            {
                'name': 'Health Score',
                'values': health_scores,
                'unit': '%',
                'trend': calculate_trend(health_scores),
                'is_positive': calculate_trend(health_scores) >= 0,
            },
        ],
        'labels': labels,
        'last_updated': timezone.now().isoformat(),
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


def _get_processor_yield_trends(user, start_date, end_date, period, date_format, request):
    """Get yield trends for processors"""
    product_type_filter = request.GET.get('product_type')
    
    # Base queryset for processor's products
    products_qs = Product.objects.filter(
        processing_unit=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    if product_type_filter:
        products_qs = products_qs.filter(product_type=product_type_filter)
    
    # Generate time series data
    days = (end_date - start_date).days
    labels = []
    processing_yields = []
    throughputs = []
    quality_scores = []
    waste_reductions = []
    
    for i in range(days):
        current_date = start_date + timezone.timedelta(days=i)
        next_date = current_date + timezone.timedelta(days=1)
        
        # Products created on this day
        daily_products = products_qs.filter(
            created_at__gte=current_date,
            created_at__lt=next_date
        )
        
        product_count = daily_products.count()
        total_quantity = daily_products.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        
        # Animals received on this day
        daily_animals = Animal.objects.filter(
            received_by=user,
            received_at__gte=current_date,
            received_at__lt=next_date
        ).count()
        
        # Calculate processing yield (products per animal)
        processing_yield = (product_count / max(daily_animals, 1)) * 100
        
        # Throughput (products per day)
        throughput = float(product_count)
        
        # Mock quality score and waste reduction
        quality_score = 90 + (i % 8) + min(product_count * 0.5, 10)
        waste_reduction = 15 - (i % 5) + (product_count * 0.1)
        
        labels.append(current_date.strftime(date_format))
        processing_yields.append(min(processing_yield, 100))
        throughputs.append(throughput)
        quality_scores.append(min(quality_score, 100))
        waste_reductions.append(max(waste_reduction, 0))
    
    # Calculate trends
    def calculate_trend(values):
        if len(values) < 2 or values[0] == 0:
            return 0.0
        return ((values[-1] - values[0]) / values[0]) * 100
    
    response_data = {
        'period': period,
        'role': 'processor',
        'primary_metric': {
            'name': 'Processing Yield',
            'values': processing_yields,
            'unit': '%',
            'trend': calculate_trend(processing_yields),
            'is_positive': calculate_trend(processing_yields) >= 0,
        },
        'secondary_metrics': [
            {
                'name': 'Throughput',
                'values': throughputs,
                'unit': 'units/day',
                'trend': calculate_trend(throughputs),
                'is_positive': calculate_trend(throughputs) >= 0,
            },
            {
                'name': 'Quality Score',
                'values': quality_scores,
                'unit': '%',
                'trend': calculate_trend(quality_scores),
                'is_positive': calculate_trend(quality_scores) >= 0,
            },
            {
                'name': 'Waste Reduction',
                'values': waste_reductions,
                'unit': '%',
                'trend': calculate_trend(waste_reductions),
                'is_positive': calculate_trend(waste_reductions) >= 0,
            },
        ],
        'labels': labels,
        'last_updated': timezone.now().isoformat(),
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


def _get_shop_yield_trends(user, start_date, end_date, period, date_format, request):
    """Get yield trends for shops"""
    category_filter = request.GET.get('category')
    
    # Base queryset for shop's orders and inventory
    orders_qs = Order.objects.filter(
        shop=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    inventory_qs = Inventory.objects.filter(shop=user)
    
    if category_filter:
        orders_qs = orders_qs.filter(items__product__category__name=category_filter)
        inventory_qs = inventory_qs.filter(product__category__name=category_filter)
    
    # Generate time series data
    days = (end_date - start_date).days
    labels = []
    sales_volumes = []
    inventory_turnovers = []
    order_fulfillments = []
    customer_satisfactions = []
    
    for i in range(days):
        current_date = start_date + timezone.timedelta(days=i)
        next_date = current_date + timezone.timedelta(days=1)
        
        # Orders created on this day
        daily_orders = orders_qs.filter(
            created_at__gte=current_date,
            created_at__lt=next_date
        )
        
        order_count = daily_orders.count()
        total_amount = daily_orders.aggregate(
            total=models.Sum('total_amount')
        )['total'] or 0
        
        # Calculate metrics
        sales_volume = float(order_count)
        
        # Mock inventory turnover (times per week)
        inventory_turnover = 3.5 + (i % 3) + (order_count * 0.1)
        
        # Order fulfillment rate
        completed_orders = daily_orders.filter(status='delivered').count()
        fulfillment_rate = (completed_orders / max(order_count, 1)) * 100
        
        # Mock customer satisfaction
        satisfaction = 4.0 + (i % 5) * 0.1 + min(order_count * 0.02, 0.5)
        
        labels.append(current_date.strftime(date_format))
        sales_volumes.append(sales_volume)
        inventory_turnovers.append(min(inventory_turnover, 10))
        order_fulfillments.append(min(fulfillment_rate, 100))
        customer_satisfactions.append(min(satisfaction, 5.0))
    
    # Calculate trends
    def calculate_trend(values):
        if len(values) < 2 or values[0] == 0:
            return 0.0
        return ((values[-1] - values[0]) / values[0]) * 100
    
    response_data = {
        'period': period,
        'role': 'shop',
        'primary_metric': {
            'name': 'Sales Volume',
            'values': sales_volumes,
            'unit': 'orders',
            'trend': calculate_trend(sales_volumes),
            'is_positive': calculate_trend(sales_volumes) >= 0,
        },
        'secondary_metrics': [
            {
                'name': 'Inventory Turnover',
                'values': inventory_turnovers,
                'unit': 'times/week',
                'trend': calculate_trend(inventory_turnovers),
                'is_positive': calculate_trend(inventory_turnovers) >= 0,
            },
            {
                'name': 'Order Fulfillment',
                'values': order_fulfillments,
                'unit': '%',
                'trend': calculate_trend(order_fulfillments),
                'is_positive': calculate_trend(order_fulfillments) >= 0,
            },
            {
                'name': 'Customer Satisfaction',
                'values': customer_satisfactions,
                'unit': '/5',
                'trend': calculate_trend(customer_satisfactions),
                'is_positive': calculate_trend(customer_satisfactions) >= 0,
            },
        ],
        'labels': labels,
        'last_updated': timezone.now().isoformat(),
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def comparative_yield_trends(request):
    """
    Get comparative yield trends across all roles.
    """
    try:
        period = request.GET.get('period', '7d')
        
        # Mock comparative data - in real app, this would aggregate data from all users
        now = timezone.now()
        
        if period == '7d':
            labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            days = 7
        elif period == '30d':
            labels = [f'{i+1}/1' for i in range(30)]
            days = 30
        elif period == '90d':
            labels = [f'W{i+1}' for i in range(13)]
            days = 90
        elif period == '1y':
            labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            days = 365
        else:
            labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            days = 7
        
        response_data = {
            'farmer': {
                'period': period,
                'role': 'farmer',
                'primary_metric': {
                    'name': 'Animal Count',
                    'values': [45.0 + i * 2.5 + (i % 3 * 5) for i in range(len(labels))],
                    'unit': 'animals',
                    'trend': 12.5,
                    'is_positive': True,
                },
                'secondary_metrics': [],
                'labels': labels,
                'last_updated': now.isoformat(),
            },
            'processor': {
                'period': period,
                'role': 'processor',
                'primary_metric': {
                    'name': 'Processing Yield',
                    'values': [65.0 + i * 1.8 + (i % 3 * 4) for i in range(len(labels))],
                    'unit': '%',
                    'trend': 18.2,
                    'is_positive': True,
                },
                'secondary_metrics': [],
                'labels': labels,
                'last_updated': now.isoformat(),
            },
            'shop': {
                'period': period,
                'role': 'shop',
                'primary_metric': {
                    'name': 'Sales Volume',
                    'values': [120.0 + i * 8.5 + (i % 3 * 15) for i in range(len(labels))],
                    'unit': 'orders',
                    'trend': 25.3,
                    'is_positive': True,
                },
                'secondary_metrics': [],
                'labels': labels,
                'last_updated': now.isoformat(),
            },
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Comparative yield trends error: {str(e)}")
        return Response(
            {'error': 'Failed to get comparative yield trends'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsProcessingUnit])
def processing_pipeline(request):
    """
    Get current processing pipeline status for the processing unit.
    """
    try:
        user = request.user
        now = timezone.now()
        
        # Get all processing stages
        stages = ProcessingStage.objects.all().order_by('order')
        
        # Get current processing activities
        # Animals received but not yet processed into products
        animals_in_pipeline = Animal.objects.filter(
            received_by=user,
            products__isnull=True
        )
        
        # Products created but not yet transferred
        products_in_pipeline = Product.objects.filter(
            processing_unit=user,
            transferred_to__isnull=True
        )
        
        # Calculate progress for each stage based on real data
        pipeline_stages = []
        
        for stage in stages:
            stage_data = {
                'id': stage.id,
                'name': stage.name,
                'description': stage.description,
                'order': stage.order,
                'progress': 0.0,
                'status': 'Queued',
                'color': '#9CA3AF',  # Default gray
                'estimated_time': None,
                'current_items': 0,
                'completed_items': 0,
                'total_items': 0
            }
            
            if stage.name == 'received':
                # Receiving stage - based on animals received today
                animals_received_today = Animal.objects.filter(
                    received_by=user,
                    received_at__date=now.date()
                ).count()
                
                total_animals = animals_in_pipeline.count()
                stage_data['progress'] = 1.0 if animals_received_today > 0 else 0.0
                stage_data['status'] = 'Complete' if animals_received_today > 0 else 'Pending'
                stage_data['color'] = '#10B981' if animals_received_today > 0 else '#9CA3AF'
                stage_data['current_items'] = animals_received_today
                stage_data['completed_items'] = animals_received_today
                stage_data['total_items'] = max(animals_received_today, 1)
                stage_data['estimated_time'] = 15  # minutes
                
            elif stage.name == 'inspected':
                # Inspection stage - simulate based on carcass measurements
                measurements_today = CarcassMeasurement.objects.filter(
                    animal__received_by=user,
                    created_at__date=now.date()
                ).count()
                
                animals_received_today = Animal.objects.filter(
                    received_by=user,
                    received_at__date=now.date()
                ).count()
                
                if animals_received_today > 0:
                    progress = min(measurements_today / animals_received_today, 1.0)
                    stage_data['progress'] = progress
                    stage_data['status'] = 'Complete' if progress >= 1.0 else 'In Progress' if progress > 0 else 'Pending'
                    stage_data['color'] = '#10B981' if progress >= 1.0 else '#3B82F6' if progress > 0 else '#F59E0B'
                    stage_data['current_items'] = measurements_today
                    stage_data['completed_items'] = measurements_today
                    stage_data['total_items'] = animals_received_today
                    stage_data['estimated_time'] = 30  # minutes
                
            elif stage.name == 'processed':
                # Processing stage - based on products created from received animals
                products_created_today = Product.objects.filter(
                    processing_unit=user,
                    created_at__date=now.date()
                ).count()
                
                animals_received_today = Animal.objects.filter(
                    received_by=user,
                    received_at__date=now.date()
                ).count()
                
                if animals_received_today > 0:
                    progress = min(products_created_today / animals_received_today, 1.0)
                    stage_data['progress'] = progress
                    stage_data['status'] = 'Complete' if progress >= 1.0 else 'In Progress' if progress > 0 else 'Pending'
                    stage_data['color'] = '#10B981' if progress >= 1.0 else '#3B82F6' if progress > 0 else '#F59E0B'
                    stage_data['current_items'] = products_created_today
                    stage_data['completed_items'] = products_created_today
                    stage_data['total_items'] = animals_received_today
                    stage_data['estimated_time'] = 120  # minutes
                
            elif stage.name == 'packaged':
                # Packaging stage - simulate based on products with batch numbers
                packaged_products = Product.objects.filter(
                    processing_unit=user,
                    created_at__date=now.date(),
                    batch_number__isnull=False
                ).exclude(batch_number='').count()
                
                total_products_today = Product.objects.filter(
                    processing_unit=user,
                    created_at__date=now.date()
                ).count()
                
                if total_products_today > 0:
                    progress = min(packaged_products / total_products_today, 1.0)
                    stage_data['progress'] = progress
                    stage_data['status'] = 'Complete' if progress >= 1.0 else 'In Progress' if progress > 0.5 else 'Pending'
                    stage_data['color'] = '#10B981' if progress >= 1.0 else '#3B82F6' if progress > 0.5 else '#F59E0B'
                    stage_data['current_items'] = packaged_products
                    stage_data['completed_items'] = packaged_products
                    stage_data['total_items'] = total_products_today
                    stage_data['estimated_time'] = 60  # minutes
                
            elif stage.name == 'stored':
                # Storage stage - products created but not transferred
                stored_products = products_in_pipeline.count()
                total_products_today = Product.objects.filter(
                    processing_unit=user,
                    created_at__date=now.date()
                ).count()
                
                if total_products_today > 0:
                    progress = min(stored_products / total_products_today, 1.0)
                    stage_data['progress'] = progress
                    stage_data['status'] = 'Complete' if progress >= 1.0 else 'In Progress' if progress > 0 else 'Pending'
                    stage_data['color'] = '#10B981' if progress >= 1.0 else '#3B82F6' if progress > 0 else '#9CA3AF'
                    stage_data['current_items'] = stored_products
                    stage_data['completed_items'] = stored_products
                    stage_data['total_items'] = total_products_today
                    stage_data['estimated_time'] = 30  # minutes
                
            elif stage.name == 'shipped':
                # Shipping stage - products transferred today
                shipped_products = Product.objects.filter(
                    processing_unit=user,
                    transferred_at__date=now.date()
                ).count()
                
                total_products_today = Product.objects.filter(
                    processing_unit=user,
                    created_at__date=now.date()
                ).count()
                
                if total_products_today > 0:
                    progress = min(shipped_products / total_products_today, 1.0)
                    stage_data['progress'] = progress
                    stage_data['status'] = 'Complete' if progress >= 1.0 else 'In Progress' if progress > 0 else 'Queued'
                    stage_data['color'] = '#10B981' if progress >= 1.0 else '#3B82F6' if progress > 0 else '#9CA3AF'
                    stage_data['current_items'] = shipped_products
                    stage_data['completed_items'] = shipped_products
                    stage_data['total_items'] = total_products_today
                    stage_data['estimated_time'] = 45  # minutes
            
            pipeline_stages.append(stage_data)
        
        # Calculate overall pipeline efficiency
        total_progress = sum(stage['progress'] for stage in pipeline_stages)
        overall_efficiency = (total_progress / len(pipeline_stages)) * 100 if pipeline_stages else 0
        
        # Get timeline events for today
        timeline_events = ProductTimelineEvent.objects.filter(
            product__processing_unit=user,
            timestamp__date=now.date()
        ).select_related('product', 'stage').order_by('-timestamp')[:10]
        
        timeline_data = []
        for event in timeline_events:
            timeline_data.append({
                'id': event.id,
                'product_id': event.product.id,
                'product_name': event.product.name,
                'action': event.action,
                'location': event.location,
                'stage': event.stage.name if event.stage else None,
                'timestamp': event.timestamp.isoformat(),
            })
        
        response_data = {
            'stages': pipeline_stages,
            'overall_efficiency': round(overall_efficiency, 1),
            'total_animals_in_pipeline': animals_in_pipeline.count(),
            'total_products_in_pipeline': products_in_pipeline.count(),
            'timeline_events': timeline_data,
            'last_updated': now.isoformat(),
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Processing pipeline error: {str(e)}")
        return Response(
            {'error': 'Failed to get processing pipeline data'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

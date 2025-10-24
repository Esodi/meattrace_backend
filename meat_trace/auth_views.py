from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from .models import UserProfile, ProcessingUnit, ProcessingUnitUser, Shop, ShopUser
from django.utils import timezone
from .auth_logging import (
    log_login_success,
    log_login_failure,
    log_registration_success,
    log_registration_failure,
)

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer to include user profile data in token response"""
    
    def validate(self, attrs):
        try:
            # Get the default token data (contains 'access' and 'refresh')
            data = super().validate(attrs)
            
            # Add user profile information
            user = self.user
            try:
                profile = UserProfile.objects.get(user=user)
                data['user'] = {
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
            except UserProfile.DoesNotExist:
                # If no profile exists, return basic user info
                data['user'] = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': 'unknown',
                }
            
            return data
        except Exception as e:
            # Log failed login attempt
            username = attrs.get('username', 'unknown')
            # Note: request is not available in serializer, will be logged in view
            raise

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view that returns user profile data along with tokens"""
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(APIView):
    """User registration endpoint"""
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        username = data.get('username', '')
        email = data.get('email', '')
        password = data.get('password')
        role = data.get('role', '')

        # Validate required fields
        if not username or not email or not password or not role:
            log_registration_failure(
                username or 'unknown',
                email or 'unknown',
                request,
                'Missing required fields'
            )
            return Response(
                {
                    'error': 'Missing required fields',
                    'detail': 'Username, email, password, and role are required'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            log_registration_failure(
                username,
                email,
                request,
                'Username already exists'
            )
            return Response(
                {
                    'error': 'Username already exists',
                    'detail': 'This username is already registered. Please try logging in or use a different username.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            log_registration_failure(
                username,
                email,
                request,
                'Email already registered'
            )
            return Response(
                {
                    'error': 'Email already registered',
                    'detail': 'This email address is already associated with an account. Please use a different email or try logging in.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create user
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
        except Exception as e:
            log_registration_failure(
                username,
                email,
                request,
                f'User creation failed: {str(e)}'
            )
            return Response(
                {
                    'error': 'Registration failed',
                    'detail': 'Unable to create user account. Please try again.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Create profile if it doesn't exist (should be created by signal, but ensure it exists)
        try:
            profile = user.profile
            print(f"[REGISTRATION] Found existing profile for user {user.username}")
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)
            print(f"[REGISTRATION] Created new profile for user {user.username}")

        # Normalize role to internal value
        normalized_role = role.lower()
        if normalized_role == 'processingunit':
            normalized_role = 'processing_unit'
        profile.role = normalized_role
        profile.save()
        print(f"[REGISTRATION] User {user.username} registered with role: {normalized_role}")

        # Handle ProcessingUnit registration
        if role.lower() in ['processingunit', 'processing_unit']:
            pu_id = data.get('processing_unit_id')
            pu_name = data.get('processing_unit_name')
            
            if pu_id:
                # Joining existing processing unit
                try:
                    processing_unit = ProcessingUnit.objects.get(id=pu_id)
                    print(f"[REGISTRATION] User {user.username} joining existing ProcessingUnit ID {pu_id}")
                    
                    # Create membership with default worker role
                    pu_user = ProcessingUnitUser.objects.create(
                        user=user,
                        processing_unit=processing_unit,
                        role='worker',
                        permissions='write',
                        is_active=True,
                        is_suspended=False,
                        invited_by=user,
                        invited_at=timezone.now(),
                        joined_at=timezone.now()
                    )
                    print(f"[REGISTRATION] Created ProcessingUnitUser membership ID {pu_user.id}")
                    
                    profile.processing_unit = processing_unit
                    profile.save()
                    print(f"[REGISTRATION] Updated user profile with ProcessingUnit ID {processing_unit.id}")
                    
                except ProcessingUnit.DoesNotExist:
                    print(f"[REGISTRATION] ERROR: ProcessingUnit ID {pu_id} not found")
                    return Response(
                        {'error': f'Processing unit with ID {pu_id} not found'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            elif pu_name:
                # Creating new processing unit
                print(f"[REGISTRATION] Creating new ProcessingUnit for user {user.username}: name={pu_name}")
                processing_unit = ProcessingUnit.objects.create(
                    name=pu_name,
                    description=data.get('description', ''),
                    location=data.get('location', ''),
                    contact_email=email,
                    contact_phone=data.get('phone', ''),
                    license_number=data.get('license_number', '')
                )
                print(f"[REGISTRATION] Created ProcessingUnit ID {processing_unit.id}")

                # Assign creator as owner with admin permissions
                pu_user = ProcessingUnitUser.objects.create(
                    user=user,
                    processing_unit=processing_unit,
                    role='owner',
                    permissions='admin',
                    is_active=True,
                    is_suspended=False,
                    invited_by=user,
                    invited_at=timezone.now(),
                    joined_at=timezone.now()
                )
                print(f"[REGISTRATION] Created ProcessingUnitUser owner membership ID {pu_user.id}")

                profile.processing_unit = processing_unit
                profile.save()
                print(f"[REGISTRATION] Updated user profile with ProcessingUnit ID {processing_unit.id}")
            else:
                print(f"[REGISTRATION] WARNING: No processing_unit_id or processing_unit_name provided")
                return Response(
                    {'error': 'Either processing_unit_id or processing_unit_name is required for processing_unit role'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Handle Shop registration
        elif role.lower() == 'shop':
            shop_id = data.get('shop_id')
            shop_name = data.get('shop_name')
            
            if shop_id:
                # Joining existing shop
                try:
                    shop = Shop.objects.get(id=shop_id)
                    print(f"[REGISTRATION] User {user.username} joining existing Shop ID {shop_id}")
                    
                    # Create membership with default salesperson role
                    shop_user = ShopUser.objects.create(
                        user=user,
                        shop=shop,
                        role='salesperson',
                        permissions='write',
                        is_active=True,
                        invited_by=user,
                        invited_at=timezone.now(),
                        joined_at=timezone.now()
                    )
                    print(f"[REGISTRATION] Created ShopUser membership ID {shop_user.id}")
                    
                    profile.shop = shop
                    profile.save()
                    print(f"[REGISTRATION] Updated user profile with Shop ID {shop.id}")
                    
                except Shop.DoesNotExist:
                    print(f"[REGISTRATION] ERROR: Shop ID {shop_id} not found")
                    return Response(
                        {'error': f'Shop with ID {shop_id} not found'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            elif shop_name:
                # Creating new shop
                print(f"[REGISTRATION] Creating new Shop for user {user.username}: name={shop_name}")
                shop = Shop.objects.create(
                    name=shop_name,
                    description=data.get('description', ''),
                    location=data.get('location', ''),
                    contact_email=email,
                    contact_phone=data.get('phone', ''),
                    business_license=data.get('business_license', ''),
                    tax_id=data.get('tax_id', ''),
                    is_active=True
                )
                print(f"[REGISTRATION] Created Shop ID {shop.id}")

                # Assign creator as owner with admin permissions
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
                print(f"[REGISTRATION] Created ShopUser owner membership ID {shop_user.id}")

                profile.shop = shop
                profile.save()
                print(f"[REGISTRATION] Updated user profile with Shop ID {shop.id}")
            else:
                print(f"[REGISTRATION] WARNING: No shop_id or shop_name provided")
                return Response(
                    {'error': 'Either shop_id or shop_name is required for shop role'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Log successful registration
        log_registration_success(user, request, normalized_role)
        
        # Generate tokens for the newly registered user
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        return Response(
            {
                'message': 'User registered successfully',
                'detail': 'Your account has been created successfully. Welcome to MeatTrace Pro!',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': normalized_role,
                    'processing_unit': {
                        'id': profile.processing_unit.id,
                        'name': profile.processing_unit.name,
                    } if profile.processing_unit else None,
                    'shop': {
                        'id': profile.shop.id,
                        'name': profile.shop.name,
                    } if profile.shop else None,
                },
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
            },
            status=status.HTTP_201_CREATED
        )

class CustomAuthLoginView(APIView):
    """Custom login endpoint that returns tokens under 'tokens' key with comprehensive logging"""
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '')
        
        try:
            serializer = CustomTokenObtainPairSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            tokens = {
                'access': data.get('access'),
                'refresh': data.get('refresh')
            }
            user_data = data.get('user')
            
            # Log successful login
            try:
                user = User.objects.get(username=username)
                log_login_success(user, request)
            except User.DoesNotExist:
                pass  # Should not happen if serializer validated
            
            return Response({
                'tokens': tokens,
                'user': user_data,
                'message': 'Login successful'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Log failed login attempt
            error_message = str(e)
            
            # Determine failure reason
            if 'credentials' in error_message.lower() or 'password' in error_message.lower():
                reason = 'Invalid credentials'
            elif 'user' in error_message.lower() and 'not found' in error_message.lower():
                reason = 'User not found'
            else:
                reason = 'Authentication failed'
            
            log_login_failure(username, request, reason=reason)
            
            # Return user-friendly error message
            return Response({
                'error': reason,
                'detail': 'The username or password you entered is incorrect.'
            }, status=status.HTTP_401_UNAUTHORIZED)
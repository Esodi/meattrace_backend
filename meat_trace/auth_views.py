from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from .models import UserProfile, ProcessingUnit, ProcessingUnitUser, Shop, ShopUser
from .models import JoinRequest
from django.utils import timezone
from .auth_logging import (
    log_login_success,
    log_login_failure,
    log_registration_success,
    log_registration_failure,
)
from .auth_progress_service import AuthProgressService
import uuid

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
                    # Check for pending or rejected join requests for this user (processing unit/shop)
                    'has_pending_join_request': False,
                    'has_rejected_join_request': False,
                    'pending_join_request': None,
                    'rejected_join_request': None,
                }
                # Determine if there are any pending or rejected join requests
                try:
                    # Check for pending requests first
                    pending_join_request = JoinRequest.objects.filter(
                        user=user,
                        status='pending'
                    ).select_related('processing_unit', 'shop').first()
                    
                    has_pending_join_request = pending_join_request is not None
                    data['user']['has_pending_join_request'] = has_pending_join_request
                    
                    if has_pending_join_request:
                        pending_join_request_data = {
                            'processing_unit_name': pending_join_request.processing_unit.name if pending_join_request.processing_unit else None,
                            'shop_name': pending_join_request.shop.name if pending_join_request.shop else None,
                            'requested_role': pending_join_request.requested_role,
                            'created_at': pending_join_request.created_at.isoformat() if pending_join_request.created_at else None,
                            'request_type': pending_join_request.request_type,
                        }
                        data['user']['pending_join_request'] = pending_join_request_data
                    
                    # Check for rejected requests if no pending request
                    if not has_pending_join_request:
                        rejected_join_request = JoinRequest.objects.filter(
                            user=user,
                            status='rejected'
                        ).select_related('processing_unit', 'shop').order_by('-updated_at').first()
                        
                        has_rejected_join_request = rejected_join_request is not None
                        data['user']['has_rejected_join_request'] = has_rejected_join_request
                        
                        if has_rejected_join_request:
                            rejected_join_request_data = {
                                'processing_unit_name': rejected_join_request.processing_unit.name if rejected_join_request.processing_unit else None,
                                'shop_name': rejected_join_request.shop.name if rejected_join_request.shop else None,
                                'requested_role': rejected_join_request.requested_role,
                                'created_at': rejected_join_request.created_at.isoformat() if rejected_join_request.created_at else None,
                                'updated_at': rejected_join_request.updated_at.isoformat() if rejected_join_request.updated_at else None,
                                'request_type': rejected_join_request.request_type,
                                'rejection_reason': rejected_join_request.response_message,
                            }
                            data['user']['rejected_join_request'] = rejected_join_request_data
                            
                    print(f"[AUTH_LOGIN] has_pending_join_request: {has_pending_join_request}, has_rejected_join_request: {data['user']['has_rejected_join_request']}")
                except Exception as e:
                    # Do not break login if join request check fails; log and continue
                    print(f'[AUTH_LOGIN] Warning: Failed to determine join request status: {e}')
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
    
    def post(self, request, *args, **kwargs):
        """Override post to add logging without breaking the response"""
        username = request.data.get('username', '')
        
        try:
            # Call parent's post method
            response = super().post(request, *args, **kwargs)
            
            # Log successful login (only if response is successful)
            if response.status_code == 200:
                try:
                    user = User.objects.get(username=username)
                    log_login_success(user, request)
                except Exception as log_error:
                    # Don't let logging errors break the login
                    print(f"Warning: Failed to log login success: {log_error}")
            
            return response
            
        except Exception as e:
            # Log failed login attempt
            try:
                log_login_failure(username, request, reason=str(e))
            except Exception as log_error:
                # Don't let logging errors break the error response
                print(f"Warning: Failed to log login failure: {log_error}")
            
            # Re-raise the original exception
            raise

class RegisterView(APIView):
    """User registration endpoint"""
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        username = data.get('username', '')
        email = data.get('email', '')
        password = data.get('password')
        role = data.get('role', '')
        session_id = data.get('session_id', str(uuid.uuid4()))

        # Send progress: Started
        AuthProgressService.signup_started(session_id, username)

        # Send progress: Validating data
        AuthProgressService.signup_validating_data(session_id)

        # Validate required fields
        if not username or not email or not password or not role:
            log_registration_failure(
                username or 'unknown',
                email or 'unknown',
                request,
                'Missing required fields'
            )
            AuthProgressService.signup_failed_validation(session_id, 'required fields')
            return Response(
                {
                    'error': 'Missing required fields',
                    'detail': 'Username, email, password, and role are required',
                    'session_id': session_id
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Send progress: Checking availability
        AuthProgressService.signup_checking_availability(session_id)

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            log_registration_failure(
                username,
                email,
                request,
                'Username already exists'
            )
            AuthProgressService.signup_failed_username_exists(session_id)
            return Response(
                {
                    'error': 'Username already exists',
                    'detail': 'This username is already registered. Please try logging in or use a different username.',
                    'session_id': session_id
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
            AuthProgressService.signup_failed_email_exists(session_id)
            return Response(
                {
                    'error': 'Email already registered',
                    'detail': 'This email address is already associated with an account. Please use a different email or try logging in.',
                    'session_id': session_id
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Send progress: Creating account
        AuthProgressService.signup_creating_account(session_id)

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
            AuthProgressService.send_error(session_id, 'Failed to create account. Please try again.', 'creation_failed')
            return Response(
                {
                    'error': 'Registration failed',
                    'detail': 'Unable to create user account. Please try again.',
                    'session_id': session_id
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Normalize role to internal value
        # Map frontend role names to backend role values
        print(f"[REGISTRATION] Role received from frontend: '{role}'")
        role_mapping = {
            'abbatoir': 'Abbatoir',
            'processingunit': 'Processor',
            'processing_unit': 'Processor',
            'processor': 'Processor',
            'shop': 'ShopOwner',
            'shopowner': 'ShopOwner',
            'Shop': 'ShopOwner',  # Added explicit capital S mapping
        }
        normalized_role = role_mapping.get(role.lower(), role)
        print(f"[REGISTRATION] Normalized role: '{normalized_role}' (from '{role}' -> '{role.lower()}')")

        # Send progress: Creating profile
        AuthProgressService.signup_creating_profile(session_id, normalized_role)

        # Create profile if it doesn't exist (should be created by signal, but ensure it exists)
        try:
            profile = user.profile
            print(f"[REGISTRATION] Found existing profile for user {user.username}, current role: {profile.role}")
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)
            print(f"[REGISTRATION] Created new profile for user {user.username}")

        profile.role = normalized_role
        profile.save()
        print(f"[REGISTRATION] User {user.username} registered with role: {normalized_role}, profile saved")

        # Send progress: Configuring permissions
        AuthProgressService.signup_configuring_permissions(session_id)

        # Handle ProcessingUnit registration
        if role.lower() in ['processingunit', 'processing_unit']:
            pu_id = data.get('processing_unit_id')
            pu_name = data.get('processing_unit_name')
            
            if pu_id:
                # Joining existing processing unit - create pending join request
                try:
                    processing_unit = ProcessingUnit.objects.get(id=pu_id)
                    print(f"[REGISTRATION] User {user.username} requesting to join ProcessingUnit ID {pu_id}")
                    
                    # Create join request instead of direct membership
                    from .models import JoinRequest
                    from datetime import timedelta
                    join_request = JoinRequest.objects.create(
                        user=user,
                        processing_unit=processing_unit,
                        request_type='processing_unit',
                        requested_role=data.get('requested_role', 'worker'),
                        message=data.get('message', 'I would like to join this processing unit'),
                        status='pending',
                        expires_at=timezone.now() + timedelta(days=30)
                    )
                    print(f"[REGISTRATION] Created JoinRequest ID {join_request.id} - pending approval")
                    
                    # Send notification to processing unit owners/managers
                    try:
                        from .models import Notification
                        owners_and_managers = ProcessingUnitUser.objects.filter(
                            processing_unit=processing_unit,
                            role__in=['owner', 'manager'],
                            is_active=True,
                            is_suspended=False
                        ).select_related('user')
                        
                        for member in owners_and_managers:
                            Notification.objects.create(
                                user=member.user,
                                notification_type='join_request',
                                title=f'New Join Request for {processing_unit.name}',
                                message=f'{user.username} has requested to join as {join_request.requested_role}',
                                priority='high',
                                action_type='approve',
                                data={
                                    'join_request_id': join_request.id,
                                    'requester_username': user.username,
                                    'requested_role': join_request.requested_role,
                                    'processing_unit_id': processing_unit.id,
                                    'processing_unit_name': processing_unit.name,
                                }
                            )
                        print(f"[REGISTRATION] Sent notifications to {owners_and_managers.count()} owners/managers")
                    except Exception as notif_error:
                        print(f"[REGISTRATION] Error sending notifications: {notif_error}")
                    
                    # Update profile but don't link to processing unit yet
                    profile.processing_unit = None  # Will be set when request is approved
                    profile.save()
                    print(f"[REGISTRATION] User profile created - awaiting join request approval")
                    
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
                # Joining existing shop - create pending join request
                try:
                    shop = Shop.objects.get(id=shop_id)
                    print(f"[REGISTRATION] User {user.username} requesting to join Shop ID {shop_id}")
                    
                    # Create join request instead of direct membership
                    from .models import JoinRequest
                    from datetime import timedelta
                    join_request = JoinRequest.objects.create(
                        user=user,
                        shop=shop,
                        request_type='shop',
                        requested_role=data.get('requested_role', 'salesperson'),
                        message=data.get('message', 'I would like to join this shop'),
                        status='pending',
                        expires_at=timezone.now() + timedelta(days=30)
                    )
                    print(f"[REGISTRATION] Created JoinRequest ID {join_request.id} - pending approval")
                    
                    # Update profile but don't link to shop yet
                    profile.shop = None  # Will be set when request is approved
                    profile.save()
                    print(f"[REGISTRATION] User profile created - awaiting join request approval")
                    
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

        # Send progress: Finalizing
        AuthProgressService.signup_finalizing(session_id)

        # Log successful registration
        log_registration_success(user, request, normalized_role)
        
        # Generate tokens for the newly registered user
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        # Check if user has pending join requests
        has_pending_join_request = False
        pending_join_message = None
        
        if role.lower() in ['processingunit', 'processing_unit'] and data.get('processing_unit_id'):
            has_pending_join_request = True
            pending_join_message = 'Your join request is pending approval from the processing unit owner.'
        elif role.lower() == 'shop' and data.get('shop_id'):
            has_pending_join_request = True
            pending_join_message = 'Your join request is pending approval from the shop owner.'
        
        response_message = 'User registered successfully'
        if has_pending_join_request:
            response_message = 'Registration successful. Your join request is pending approval.'
        
        # Send success
        AuthProgressService.signup_success(session_id, username, normalized_role)
        
        return Response(
            {
                'message': response_message,
                'detail': pending_join_message if has_pending_join_request else 'Your account has been created successfully. Welcome to MeatTrace Pro!',
                'has_pending_join_request': has_pending_join_request,
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
                },
                'session_id': session_id
            },
            status=status.HTTP_201_CREATED
        )

class CustomAuthLoginView(APIView):
    """Custom login endpoint that returns tokens under 'tokens' key with comprehensive logging"""
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '')
        session_id = request.data.get('session_id', str(uuid.uuid4()))
        
        try:
            # Send progress: Started
            AuthProgressService.login_started(session_id, username)
            
            # Send progress: Validating credentials
            AuthProgressService.login_validating_credentials(session_id)
            
            serializer = CustomTokenObtainPairSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            
            # Send progress: Checking account
            AuthProgressService.login_checking_account(session_id)
            
            tokens = {
                'access': data.get('access'),
                'refresh': data.get('refresh')
            }
            user_data = data.get('user')
            
            # Send progress: Loading profile
            AuthProgressService.login_loading_profile(session_id)
            
            # Log successful login
            try:
                user = User.objects.get(username=username)
                log_login_success(user, request)
            except User.DoesNotExist:
                pass  # Should not happen if serializer validated
            
            # Send progress: Generating tokens
            AuthProgressService.login_generating_tokens(session_id)
            
            # Send success
            role = user_data.get('role', 'User')
            AuthProgressService.login_success(session_id, username, role)
            
            return Response({
                'tokens': tokens,
                'user': user_data,
                'message': 'Login successful',
                'session_id': session_id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Log failed login attempt
            error_message = str(e)
            
            # Determine failure reason
            if 'credentials' in error_message.lower() or 'password' in error_message.lower():
                reason = 'Invalid credentials'
                AuthProgressService.login_failed_invalid_credentials(session_id)
            elif 'user' in error_message.lower() and 'not found' in error_message.lower():
                reason = 'User not found'
                AuthProgressService.login_failed_invalid_credentials(session_id)
            else:
                reason = 'Authentication failed'
                AuthProgressService.send_error(session_id, reason, 'auth_failed')
            
            log_login_failure(username, request, reason=reason)
            
            # Return user-friendly error message
            return Response({
                'error': reason,
                'detail': 'The username or password you entered is incorrect.',
                'session_id': session_id
            }, status=status.HTTP_401_UNAUTHORIZED)
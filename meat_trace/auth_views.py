from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from .models import UserProfile, ProcessingUnit, ProcessingUnitUser
from django.utils import timezone

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer to include user profile data in token response"""
    
    def validate(self, attrs):
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

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view that returns user profile data along with tokens"""
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(APIView):
    """User registration endpoint"""
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')

        if not username or not email or not password or not role:
            return Response(
                {'error': 'username, email, password, and role are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'username already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(username=username, email=email, password=password)

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

        # Create ProcessingUnit if registering as a processing unit
        if role.lower() in ['processingunit', 'processing_unit']:
            pu_name = data.get('processing_unit_name')
            print(f"[REGISTRATION] Creating ProcessingUnit for user {user.username}: name={pu_name}")
            if pu_name:
                processing_unit = ProcessingUnit.objects.create(
                    name=pu_name,
                    description=data.get('description', ''),
                    location=data.get('location', ''),
                    contact_email=email,
                    contact_phone=data.get('phone', ''),
                    license_number=data.get('license_number', '')
                )
                print(f"[REGISTRATION] Created ProcessingUnit ID {processing_unit.id} for user {user.username}")

                # Assign creator as owner
                pu_user = ProcessingUnitUser.objects.create(
                    user=user,
                    processing_unit=processing_unit,
                    role='owner',
                    is_active=True,
                    invited_by=user,
                    joined_at=timezone.now()
                )
                print(f"[REGISTRATION] Created ProcessingUnitUser ID {pu_user.id} for user {user.username}")

                profile.processing_unit = processing_unit
                profile.save()
                print(f"[REGISTRATION] Updated user profile with ProcessingUnit ID {processing_unit.id}")
            else:
                print(f"[REGISTRATION] WARNING: No processing_unit_name provided for processing_unit role")

        return Response(status=status.HTTP_201_CREATED)

class CustomAuthLoginView(APIView):
    """Custom login endpoint that returns tokens under 'tokens' key"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomTokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tokens = {
            'access': data.get('access'),
            'refresh': data.get('refresh')
        }
        user_data = data.get('user')
        return Response({'tokens': tokens, 'user': user_data}, status=status.HTTP_200_OK)
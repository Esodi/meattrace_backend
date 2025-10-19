from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from meat_trace.models import UserProfile, ProcessingUnit, ProcessingUnitUser, Shop, ShopUser, JoinRequest, Notification
from django.utils import timezone
import json


class SignupFlowTests(TestCase):
    """Comprehensive tests for the complete signup process for all user types"""

    def setUp(self):
        self.client = APIClient()

    def test_farmer_signup_basic_flow(self):
        """Test basic farmer signup flow"""
        farmer_data = {
            'username': 'testfarmer',
            'email': 'farmer@test.com',
            'password': 'testpass123',
            'role': 'Farmer'
        }

        # Test registration
        response = self.client.post('/api/v2/register/', farmer_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify user was created
        user = User.objects.get(username='testfarmer')
        self.assertEqual(user.email, 'farmer@test.com')

        # Verify user profile was created
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, 'Farmer')

        # Test login
        login_data = {
            'username': 'testfarmer',
            'password': 'testpass123'
        }
        response = self.client.post('/api/v2/token/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        # Verify profile endpoint works
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        response = self.client.get('/api/v2/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['profile']['role'], 'Farmer')

    def test_processing_unit_creation_flow(self):
        """Test processing unit creation and owner assignment"""
        # First register the user
        user_data = {
            'username': 'processor_owner',
            'email': 'owner@processor.com',
            'password': 'testpass123',
            'role': 'ProcessingUnit'
        }

        response = self.client.post('/api/v2/auth/register/', user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Login to get tokens
        login_data = {
            'username': 'processor_owner',
            'password': 'testpass123'
        }
        response = self.client.post('/api/v2/token/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data['access']

        # Create processing unit
        unit_data = {
            'name': 'Test Processing Unit',
            'description': 'A test processing unit for quality meat processing',
            'location': 'Nairobi, Kenya',
            'contact_email': 'contact@processingunit.com',
            'contact_phone': '+254700000000',
            'license_number': 'PU001'
        }

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post('/api/v2/processing-units/create/', unit_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify processing unit was created
        unit = ProcessingUnit.objects.get(name='Test Processing Unit')
        self.assertEqual(unit.description, 'A test processing unit for quality meat processing')
        self.assertEqual(unit.location, 'Nairobi, Kenya')

        # Verify user was assigned as owner
        membership = ProcessingUnitUser.objects.get(user__username='processor_owner', processing_unit=unit)
        self.assertEqual(membership.role, 'owner')
        self.assertTrue(membership.is_active)

        # Verify user profile was updated
        profile = UserProfile.objects.get(user__username='processor_owner')
        self.assertEqual(profile.role, 'ProcessingUnit')
        self.assertEqual(profile.processing_unit, unit)

    def test_processing_unit_join_flow(self):
        """Test joining existing processing unit flow"""
        # Create existing processing unit with owner
        owner = User.objects.create_user(
            username='existing_owner',
            email='owner@existing.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=owner, role='ProcessingUnit')

        existing_unit = ProcessingUnit.objects.create(
            name='Existing Processing Unit',
            description='Already established unit'
        )

        ProcessingUnitUser.objects.create(
            user=owner,
            processing_unit=existing_unit,
            role='owner',
            is_active=True
        )

        # Register new user who wants to join
        joiner_data = {
            'username': 'new_joiner',
            'email': 'joiner@test.com',
            'password': 'testpass123',
            'role': 'ProcessingUnit'
        }

        response = self.client.post('/api/v2/auth/register/', joiner_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Login
        login_data = {
            'username': 'new_joiner',
            'password': 'testpass123'
        }
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data['tokens']['access']

        # Submit join request
        join_request_data = {
            'request_type': 'processing_unit',
            'processing_unit': existing_unit.id,
            'requested_role': 'worker',
            'message': 'I would like to join your processing unit',
            'qualifications': '2 years experience in meat processing'
        }

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post(f'/api/v2/join-requests/create/{existing_unit.id}/processing_unit/', join_request_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify join request was created
        join_request = JoinRequest.objects.get(user__username='new_joiner')
        self.assertEqual(join_request.request_type, 'processing_unit')
        self.assertEqual(join_request.processing_unit, existing_unit)
        self.assertEqual(join_request.requested_role, 'worker')
        self.assertEqual(join_request.status, 'pending')

        # Verify notification was created for owner
        notification = Notification.objects.get(user=owner)
        self.assertEqual(notification.notification_type, 'join_request')
        self.assertIn('New join request', notification.title)

    def test_join_request_approval_flow(self):
        """Test join request approval by owner"""
        # Setup: owner, unit, and pending join request
        owner = User.objects.create_user(
            username='approver_owner',
            email='approver@owner.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=owner, role='ProcessingUnit')

        unit = ProcessingUnit.objects.create(name='Approval Test Unit')
        ProcessingUnitUser.objects.create(
            user=owner,
            processing_unit=unit,
            role='owner',
            is_active=True
        )

        requester = User.objects.create_user(
            username='requester_user',
            email='requester@test.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=requester, role='ProcessingUnit')

        join_request = JoinRequest.objects.create(
            user=requester,
            request_type='processing_unit',
            processing_unit=unit,
            requested_role='manager',
            message='Please approve my request',
            status='pending'
        )

        # Login as owner
        login_data = {
            'username': 'approver_owner',
            'password': 'testpass123'
        }
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data['tokens']['access']

        # Approve the request
        review_data = {
            'status': 'approved',
            'response_message': 'Welcome to our team!'
        }

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.patch(f'/api/v2/join-requests/review/{join_request.id}/', review_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify join request was updated
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, 'approved')
        self.assertEqual(join_request.response_message, 'Welcome to our team!')

        # Verify membership was created
        membership = ProcessingUnitUser.objects.get(user=requester, processing_unit=unit)
        self.assertEqual(membership.role, 'manager')
        self.assertTrue(membership.is_active)

        # Verify user profile was updated
        profile = UserProfile.objects.get(user=requester)
        self.assertEqual(profile.processing_unit, unit)

        # Verify notification was sent to requester
        notification = Notification.objects.get(user=requester)
        self.assertEqual(notification.notification_type, 'join_approved')

    def test_join_request_rejection_flow(self):
        """Test join request rejection by owner"""
        # Setup similar to approval test
        owner = User.objects.create_user(
            username='rejector_owner',
            email='rejector@owner.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=owner, role='ProcessingUnit')

        unit = ProcessingUnit.objects.create(name='Rejection Test Unit')
        ProcessingUnitUser.objects.create(
            user=owner,
            processing_unit=unit,
            role='owner',
            is_active=True
        )

        requester = User.objects.create_user(
            username='rejected_user',
            email='rejected@test.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=requester, role='ProcessingUnit')

        join_request = JoinRequest.objects.create(
            user=requester,
            request_type='processing_unit',
            processing_unit=unit,
            requested_role='worker',
            status='pending'
        )

        # Login as owner and reject
        login_data = {
            'username': 'rejector_owner',
            'password': 'testpass123'
        }
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data['tokens']['access']

        review_data = {
            'status': 'rejected',
            'response_message': 'We are not hiring at this time.'
        }

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.patch(f'/api/v2/join-requests/review/{join_request.id}/', review_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify join request was rejected
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, 'rejected')

        # Verify no membership was created
        with self.assertRaises(ProcessingUnitUser.DoesNotExist):
            ProcessingUnitUser.objects.get(user=requester, processing_unit=unit)

        # Verify rejection notification was sent
        notification = Notification.objects.get(user=requester)
        self.assertEqual(notification.notification_type, 'join_rejected')

    def test_shop_creation_flow(self):
        """Test shop creation and owner assignment"""
        # Register user
        user_data = {
            'username': 'shop_owner',
            'email': 'owner@shop.com',
            'password': 'testpass123',
            'role': 'Shop'
        }

        response = self.client.post('/api/v2/auth/register/', user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Login
        login_data = {
            'username': 'shop_owner',
            'password': 'testpass123'
        }
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data['tokens']['access']

        # Create shop
        shop_data = {
            'name': 'Test Meat Shop',
            'description': 'Quality meat products',
            'location': 'Downtown Nairobi',
            'contact_email': 'contact@meatshop.com',
            'contact_phone': '+254711111111',
            'business_license': 'SHOP001',
            'tax_id': 'TXN123456'
        }

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post('/api/v2/shops/create/', shop_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify shop was created
        shop = Shop.objects.get(name='Test Meat Shop')
        self.assertEqual(shop.business_license, 'SHOP001')

        # Verify user was assigned as owner
        membership = ShopUser.objects.get(user__username='shop_owner', shop=shop)
        self.assertEqual(membership.role, 'owner')
        self.assertTrue(membership.is_active)

        # Verify user profile was updated
        profile = UserProfile.objects.get(user__username='shop_owner')
        self.assertEqual(profile.role, 'Shop')
        self.assertEqual(profile.shop, shop)

    def test_shop_join_flow(self):
        """Test joining existing shop flow"""
        # Create existing shop with owner
        owner = User.objects.create_user(
            username='shop_owner_existing',
            email='owner@existing-shop.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=owner, role='Shop')

        existing_shop = Shop.objects.create(
            name='Existing Meat Shop',
            description='Established meat retailer'
        )

        ShopUser.objects.create(
            user=owner,
            shop=existing_shop,
            role='owner',
            is_active=True
        )

        # Register new user who wants to join
        joiner_data = {
            'username': 'shop_joiner',
            'email': 'joiner@shop.com',
            'password': 'testpass123',
            'role': 'Shop'
        }

        response = self.client.post('/api/v2/auth/register/', joiner_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Login and submit join request
        login_data = {
            'username': 'shop_joiner',
            'password': 'testpass123'
        }
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data['tokens']['access']

        join_request_data = {
            'request_type': 'shop',
            'shop': existing_shop.id,
            'requested_role': 'salesperson',
            'message': 'I would like to work in your shop',
            'qualifications': 'Retail experience'
        }

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post(f'/api/v2/join-requests/create/{existing_shop.id}/shop/', join_request_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify join request and notification
        join_request = JoinRequest.objects.get(user__username='shop_joiner')
        self.assertEqual(join_request.request_type, 'shop')
        self.assertEqual(join_request.shop, existing_shop)

        notification = Notification.objects.get(user=owner)
        self.assertEqual(notification.notification_type, 'join_request')

    # Edge Cases and Error Handling Tests

    def test_duplicate_unit_names(self):
        """Test that duplicate processing unit names are rejected"""
        # Create first unit
        owner1 = User.objects.create_user(username='owner1', email='owner1@test.com', password='pass')
        UserProfile.objects.create(user=owner1, role='ProcessingUnit')

        unit1 = ProcessingUnit.objects.create(name='Duplicate Name')
        ProcessingUnitUser.objects.create(user=owner1, processing_unit=unit1, role='owner', is_active=True)

        # Try to create second unit with same name
        owner2 = User.objects.create_user(username='owner2', email='owner2@test.com', password='pass')
        UserProfile.objects.create(user=owner2, role='ProcessingUnit')

        login_data = {'username': 'owner2', 'password': 'pass'}
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        access_token = response.data['tokens']['access']

        unit_data = {'name': 'Duplicate Name', 'description': 'Different description'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post('/api/v2/processing-units/create/', unit_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exists', response.data['error'])

    def test_duplicate_shop_names(self):
        """Test that duplicate shop names are rejected"""
        # Create first shop
        owner1 = User.objects.create_user(username='shop_owner1', email='shop1@test.com', password='pass')
        UserProfile.objects.create(user=owner1, role='Shop')

        shop1 = Shop.objects.create(name='Duplicate Shop Name')
        ShopUser.objects.create(user=owner1, shop=shop1, role='owner', is_active=True)

        # Try to create second shop with same name
        owner2 = User.objects.create_user(username='shop_owner2', email='shop2@test.com', password='pass')
        UserProfile.objects.create(user=owner2, role='Shop')

        login_data = {'username': 'shop_owner2', 'password': 'pass'}
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        access_token = response.data['tokens']['access']

        shop_data = {'name': 'Duplicate Shop Name'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post('/api/v2/shops/create/', shop_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exists', response.data['error'])

    def test_invalid_join_request_data(self):
        """Test join request validation"""
        # Register user
        user_data = {'username': 'invalid_joiner', 'email': 'invalid@test.com', 'password': 'pass', 'role': 'ProcessingUnit'}
        self.client.post('/api/v2/auth/register/', user_data, format='json')

        # Login
        login_data = {'username': 'invalid_joiner', 'password': 'pass'}
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        access_token = response.data['tokens']['access']

        # Try to submit join request without required fields
        invalid_data = {
            'request_type': 'processing_unit',
            'processing_unit': 999,  # Non-existent unit
            # Missing requested_role
        }

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post('/api/v2/join-requests/create/999/processing_unit/', invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthorized_join_request_review(self):
        """Test that only owners/managers can review join requests"""
        # Create unit and join request
        owner = User.objects.create_user(username='review_owner', email='review@test.com', password='pass')
        UserProfile.objects.create(user=owner, role='ProcessingUnit')

        unit = ProcessingUnit.objects.create(name='Review Test Unit')
        ProcessingUnitUser.objects.create(user=owner, processing_unit=unit, role='owner', is_active=True)

        requester = User.objects.create_user(username='review_requester', email='req@test.com', password='pass')
        join_request = JoinRequest.objects.create(
            user=requester,
            request_type='processing_unit',
            processing_unit=unit,
            requested_role='worker',
            status='pending'
        )

        # Try to review as a different user (not member of the unit)
        other_user = User.objects.create_user(username='other_user', email='other@test.com', password='pass')
        login_data = {'username': 'other_user', 'password': 'pass'}
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        access_token = response.data['tokens']['access']

        review_data = {'status': 'approved'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.patch(f'/api/v2/join-requests/review/{join_request.id}/', review_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_join_request_already_reviewed(self):
        """Test that already reviewed requests cannot be reviewed again"""
        owner = User.objects.create_user(username='reviewed_owner', email='reviewed@test.com', password='pass')
        unit = ProcessingUnit.objects.create(name='Reviewed Unit')
        ProcessingUnitUser.objects.create(user=owner, processing_unit=unit, role='owner', is_active=True)

        requester = User.objects.create_user(username='reviewed_req', email='req2@test.com', password='pass')
        join_request = JoinRequest.objects.create(
            user=requester,
            request_type='processing_unit',
            processing_unit=unit,
            requested_role='worker',
            status='approved'  # Already approved
        )

        login_data = {'username': 'reviewed_owner', 'password': 'pass'}
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        access_token = response.data['tokens']['access']

        review_data = {'status': 'rejected'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.patch(f'/api/v2/join-requests/review/{join_request.id}/', review_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already been reviewed', response.data['error'])

    def test_network_error_simulation(self):
        """Test handling of network/server errors during signup"""
        # This would require mocking network failures
        # For now, test with invalid server response
        pass  # Placeholder for network error tests

    def test_permission_checks(self):
        """Test that users can only access appropriate endpoints"""
        # Create users of different roles
        farmer = User.objects.create_user(username='test_farmer', email='farmer@test.com', password='pass')
        UserProfile.objects.create(user=farmer, role='Farmer')

        processor = User.objects.create_user(username='test_processor', email='processor@test.com', password='pass')
        UserProfile.objects.create(user=processor, role='ProcessingUnit')

        shop_owner = User.objects.create_user(username='test_shop_owner', email='shop@test.com', password='pass')
        UserProfile.objects.create(user=shop_owner, role='Shop')

        # Test that farmer cannot create processing unit
        login_data = {'username': 'test_farmer', 'password': 'pass'}
        response = self.client.post('/api/v2/auth/login/', login_data, format='json')
        access_token = response.data['tokens']['access']

        unit_data = {'name': 'Unauthorized Unit'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post('/api/v2/processing-units/create/', unit_data, format='json')
        # This should fail because farmer profile doesn't have processing_unit set
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
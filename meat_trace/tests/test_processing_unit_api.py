import json
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from meat_trace.models import ProcessingUnit, UserProfile, ProcessingUnitUser

User = get_user_model()

class ProcessingUnitAPITests(APITestCase):
    def setUp(self):
        # Create users for testing
        self.processor_user = User.objects.create_user(
            username="processor",
            email="processor@example.com",
            password="testpassword",
            first_name="Processor",
            last_name="User"
        )
        self.processor_user.profile.role = 'processing_unit'
        self.processor_user.profile.save()

        self.farmer_user = User.objects.create_user(
            username="farmer",
            email="farmer@example.com",
            password="testpassword",
            first_name="Farmer",
            last_name="User"
        )
        self.farmer_user.profile.role = 'farmer'
        self.farmer_user.profile.save()

        # Authenticate the processor user
        self.client.force_authenticate(user=self.processor_user)

        self.unit = ProcessingUnit.objects.create(
            name='Test Unit',
            description='A test processing unit',
            location='Test Location',
            contact_email='test@example.com',
            contact_phone='1234567890',
            license_number='LIC123'
        )
        ProcessingUnitUser.objects.create(user=self.processor_user, processing_unit=self.unit, role='owner')
        # Ensure processor user is associated with this processing unit for queryset access
        self.processor_user.profile.processing_unit = self.unit
        self.processor_user.profile.save()

    def test_create_processing_unit(self):
        """
        Ensure a processor can create a new processing unit.
        """
        url = reverse('api-v2:processing-units-list')
        data = {
            'name': 'New Test Unit',
            'description': 'A new test processing unit',
            'location': 'New Test Location',
            'contact_email': 'newtest@example.com',
            'contact_phone': '9876543210',
            'license_number': 'LIC456'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProcessingUnit.objects.count(), 2)
        self.assertTrue(ProcessingUnit.objects.filter(name='New Test Unit').exists())

    def test_create_processing_unit_invalid_data(self):
        """
        Ensure API returns an error when creating a processing unit with invalid data.
        """
        url = reverse('api-v2:processing-units-list')
        data = {
            'name': '',  # Invalid data
            'address': '123 Test St',
            'contact_person': 'John Doe',
            'contact_phone': '1234567890'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # One unit already exists from setUp
        self.assertEqual(ProcessingUnit.objects.count(), 1)

    def test_join_processing_unit(self):
        """
        Ensure a user can request to join a processing unit and an admin can approve it.
        """
        self.client.force_authenticate(user=self.farmer_user)
        join_url = reverse('api-v2:join-requests-list')
        expires_at = timezone.now() + timezone.timedelta(days=7)
        data = {
            'user': self.farmer_user.pk,
            'request_type': 'processing_unit',
            'processing_unit': self.unit.pk,
            'requested_role': 'worker',
            'message': 'I would like to join',
            'expires_at': expires_at.isoformat()
        }
        response = self.client.post(join_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Admin approves the join request
        self.client.force_authenticate(user=self.processor_user)
        approve_url = reverse('api-v2:join-requests-approve', kwargs={'pk': response.data['id']})
        response = self.client.post(approve_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Join request approved.')

        # Verify the farmer is now a member of the unit
        self.unit.refresh_from_db()
        self.assertTrue(ProcessingUnitUser.objects.filter(user=self.farmer_user, processing_unit=self.unit).exists())

    def test_join_non_existent_processing_unit(self):
        """
        Ensure API returns an error when a user tries to join a non-existent processing unit.
        """
        self.client.force_authenticate(user=self.farmer_user)
        join_url = reverse('api-v2:join-requests-list')
        data = {'request_type': 'processing_unit', 'processing_unit': 999, 'requested_role': 'worker', 'message': 'I would like to join'}
        response = self.client.post(join_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suspend_user(self):
        """
        Ensure an admin can suspend a user in their processing unit.
        """
        processing_unit_user = ProcessingUnitUser.objects.create(user=self.farmer_user, processing_unit=self.unit)

        self.client.force_authenticate(user=self.processor_user)
        suspend_url = reverse('api-v2:processing-units-suspend-user', kwargs={'pk': self.unit.pk})
        response = self.client.post(suspend_url, {'user_id': self.farmer_user.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'user suspended')

        pu_user = ProcessingUnitUser.objects.get(user=self.farmer_user, processing_unit=self.unit)
        self.assertFalse(pu_user.is_active)

    def test_reactivate_user(self):
        """
        Ensure an admin can reactivate a suspended user in their processing unit.
        """
        processing_unit_user = ProcessingUnitUser.objects.create(user=self.farmer_user, processing_unit=self.unit)
        processing_unit_user.is_active = False
        processing_unit_user.save()

        self.client.force_authenticate(user=self.processor_user)
        reactivate_url = reverse('api-v2:processing-units-activate-user', kwargs={'pk': self.unit.pk})
        response = self.client.post(reactivate_url, {'user_id': self.farmer_user.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'user activated')

        pu_user = ProcessingUnitUser.objects.get(user=self.farmer_user, processing_unit=self.unit)
        self.assertTrue(pu_user.is_active)

    def test_get_processing_unit_details(self):
        """
        Ensure the API returns the correct details for a processing unit.
        """
        ProcessingUnitUser.objects.create(user=self.farmer_user, processing_unit=self.unit)

        url = reverse('api-v2:processing-units-detail', kwargs={'pk': self.unit.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.unit.name)

    def test_farmer_can_list_processing_units(self):
        """
        Ensure a farmer can list all processing units.
        """
        self.client.force_authenticate(user=self.farmer_user)
        url = reverse('api-v2:processing-units-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(pu['id'] == self.unit.id for pu in response.data))
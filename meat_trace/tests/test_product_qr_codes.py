from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from meat_trace.models import Product, UserProfile, Animal, ProcessingUnit
from django.utils import timezone
import os
from django.conf import settings

class ProductQRCodeTests(TestCase):
    def setUp(self):
        # Create a processing unit
        self.processing_unit_obj = ProcessingUnit.objects.create(
            name='Test Processing Unit',
            description='Test processing unit for QR code tests'
        )

        # Create a processing unit user
        self.processing_unit = User.objects.create_user(
            username='processor1',
            password='testpass123'
        )
        UserProfile.objects.filter(user=self.processing_unit).update(
            role='ProcessingUnit',
            processing_unit=self.processing_unit_obj
        )

        # Create a abbatoir user
        self.abbatoir = User.objects.create_user(
            username='abbatoir1',
            username='farmer1',
>>>>>>> aa57a1f (Implement weight-based selling and inventory management)
            password='testpass123'
        )
        UserProfile.objects.filter(user=self.abbatoir).update(role='Abbatoir')

        # Create an animal
        self.animal = Animal.objects.create(
            abbatoir=self.abbatoir,
            species='cow',
            age=24,
            live_weight=500,
            slaughtered=True,
            slaughtered_at=timezone.now(),
            received_by=self.processing_unit,
            received_at=timezone.now()
        )

        # Create a product with matching processing_unit
        self.product = Product.objects.create(
            processing_unit=self.processing_unit_obj,
            animal=self.animal,
            product_type='meat',
            quantity=100,
            name='Test Product',
            batch_number='BATCH001',
            weight=100,
            weight_unit='kg',
            price=500,
            description='Test description',
            manufacturer='Test Manufacturer'
        )

        self.api_client = APIClient()

    def test_regenerate_qr_code_unauthorized(self):
        # Try to regenerate QR code without authentication
        response = self.api_client.post(f'/api/v2/products/{self.product.id}/regenerate_qr/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regenerate_qr_code_forbidden(self):
        # Log in as abbatoir (who shouldn't have access)
        self.api_client.force_authenticate(user=self.abbatoir)
        response = self.api_client.post(f'/api/v2/products/{self.product.id}/regenerate_qr/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regenerate_qr_code_not_found(self):
        # Log in as processing unit
        self.api_client.force_authenticate(user=self.processing_unit)
        response = self.api_client.post('/api/v2/products/99999/regenerate_qr/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regenerate_qr_code_success(self):
        # Log in as processing unit
        self.api_client.force_authenticate(user=self.processing_unit)

        # Get old QR code path
        old_qr_code = self.product.qr_code
        if old_qr_code:
            old_qr_path = os.path.join(settings.MEDIA_ROOT, old_qr_code)
        else:
            old_qr_path = None

        # Regenerate QR code
        response = self.api_client.post(f'/api/v2/products/{self.product.id}/regenerate_qr/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that we got a new QR code URL
        self.assertIn('qr_code_url', response.data)
        self.assertIsNotNone(response.data['qr_code_url'])

        # Refresh product from database
        self.product.refresh_from_db()

        # Check that the QR code was actually updated
        self.assertNotEqual(self.product.qr_code, old_qr_code)

        # Verify that the old QR code file was deleted (if it existed)
        if old_qr_path:
            self.assertFalse(os.path.exists(old_qr_path))

        # Verify that the new QR code file exists
        new_qr_path = os.path.join(settings.MEDIA_ROOT, self.product.qr_code)
        self.assertTrue(os.path.exists(new_qr_path))

    def test_regenerate_qr_code_wrong_processor(self):
        # Create another processing unit
        other_processor = User.objects.create_user(
            username='processor2',
            password='testpass123'
        )
        UserProfile.objects.filter(user=other_processor).update(role='ProcessingUnit')

        # Log in as the other processing unit
        self.api_client.force_authenticate(user=other_processor)

        # Try to regenerate QR code for a product that belongs to a different processor
        response = self.api_client.post(f'/api/v2/products/{self.product.id}/regenerate_qr/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
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
        # Save through the instance, not .update(). force_authenticate() hands
        # this very User object to the view, and its `.profile` relation is
        # already cached — a queryset .update() changes the row but leaves that
        # cached profile stale, so the view saw the default 'Abbatoir' role.
        profile = self.processing_unit.profile
        profile.role = 'ProcessingUnit'
        profile.processing_unit = self.processing_unit_obj
        profile.save()

        # Create a abbatoir user
        self.abbatoir = User.objects.create_user(
            username='abbatoir1',
            password='testpass123'
        )
        profile = self.abbatoir.profile
        profile.role = 'Abbatoir'
        profile.save()

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

        # The returned URL is the scannable traceability link, not a media path.
        self.assertEqual(response.data['qr_code_url'], self.product.trace_url)
        self.assertTrue(response.data['qr_code_url'].startswith('http'))

        # Refresh product from database
        self.product.refresh_from_db()

        # The filename is derived from the primary key, so the stored path is
        # stable across regenerations — the image is rewritten in place rather
        # than accumulating orphaned files under a new name each time.
        self.assertEqual(self.product.qr_code, f'qr_codes/product_qr_{self.product.pk}.png')
        if old_qr_code:
            self.assertEqual(self.product.qr_code, old_qr_code)

        # The image exists and actually encodes the traceability URL.
        new_qr_path = os.path.join(settings.MEDIA_ROOT, self.product.qr_code)
        self.assertTrue(os.path.exists(new_qr_path))

        import io, hashlib, qrcode
        q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L,
                          box_size=10, border=4)
        q.add_data(self.product.trace_url)
        q.make(fit=True)
        buf = io.BytesIO()
        q.make_image(fill_color='black', back_color='white').save(buf, format='PNG')
        self.assertEqual(
            hashlib.md5(open(new_qr_path, 'rb').read()).hexdigest(),
            hashlib.md5(buf.getvalue()).hexdigest(),
            'QR image on disk does not encode the product trace URL',
        )

    def test_regenerate_qr_code_wrong_processor(self):
        # Create another processing unit
        other_processor = User.objects.create_user(
            username='processor2',
            password='testpass123'
        )
        profile = other_processor.profile
        profile.role = 'ProcessingUnit'
        profile.save()

        # Log in as the other processing unit
        self.api_client.force_authenticate(user=other_processor)

        # Try to regenerate QR code for a product that belongs to a different processor
        response = self.api_client.post(f'/api/v2/products/{self.product.id}/regenerate_qr/')
        # 404, not 403: the product is outside this processor's visible queryset,
        # and answering 403 would confirm that a product with this id exists in
        # another tenant. 403 is reserved for products the caller can legitimately
        # see but does not own (see test_regenerate_qr_code_forbidden).
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
#!/usr/bin/env python
"""
Comprehensive unit tests for split carcass functionality.
Tests models, serializers, views, and API endpoints for split carcass animals.
"""
import json
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from meat_trace.models import (
    Animal, SlaughterPart, ProcessingUnit, UserProfile, CarcassMeasurement,
    Product, ProductCategory
)
from meat_trace.serializers import AnimalSerializer, CarcassMeasurementSerializer


class SplitCarcassModelTests(TestCase):
    """Test split carcass model functionality"""

    def setUp(self):
        """Set up test data"""
        # Clean up any existing test data first
        UserProfile.objects.filter(user__username__in=['test_farmer_model', 'test_processor_model']).delete()
        User.objects.filter(username__in=['test_farmer_model', 'test_processor_model']).delete()
        ProcessingUnit.objects.filter(name='Test Processing Unit Model').delete()

        self.farmer = User.objects.create_user(
            username='test_farmer_model', email='farmer_model@test.com', password='testpass123'
        )
        self.processor = User.objects.create_user(
            username='test_processor_model', email='processor_model@test.com', password='testpass123'
        )
        self.processing_unit = ProcessingUnit.objects.create(
            name='Test Processing Unit Model', location='Test Location'
        )

        # Create user profiles
        UserProfile.objects.create(user=self.farmer, role='farmer')
        UserProfile.objects.create(user=self.processor, role='processing_unit',
                                  processing_unit=self.processing_unit)

    def test_split_carcass_animal_creation(self):
        """Test creating a split carcass animal with measurement"""
        # Create animal
        animal = Animal.objects.create(
            farmer=self.farmer,
            species='cow',
            age=24.0,
            live_weight=500.0,
            animal_id='TEST_SPLIT_001'
        )

        # Create carcass measurement for split carcass
        measurement = CarcassMeasurement.objects.create(
            animal=animal,
            carcass_type='split',
            left_carcass_weight=120.0,
            right_carcass_weight=118.0,
            head_weight=15.0,
            feet_weight=12.0,
            organs_weight=25.0
        )

        # Test properties
        self.assertTrue(animal.is_split_carcass)
        self.assertTrue(animal.has_slaughter_parts)
        self.assertEqual(measurement.carcass_type, 'split')
        self.assertEqual(measurement.calculated_total_weight, 290.0)  # 120+118+15+12+25

    def test_split_carcass_slaughter_parts_creation(self):
        """Test automatic creation of slaughter parts for split carcass"""
        # Create animal
        animal = Animal.objects.create(
            farmer=self.farmer,
            species='cow',
            age=24.0,
            live_weight=500.0,
            animal_id='TEST_SPLIT_002'
        )

        # Create carcass measurement
        measurement = CarcassMeasurement.objects.create(
            animal=animal,
            carcass_type='split',
            left_carcass_weight=120.0,
            right_carcass_weight=118.0,
            head_weight=15.0,
            feet_weight=12.0,
            organs_weight=25.0
        )

        # Create slaughter parts manually (simulating the create_slaughter_parts_from_measurement logic)
        parts_data = [
            ('left_carcass', 120.0),
            ('right_carcass', 118.0),
            ('head', 15.0),
            ('feet', 12.0),
        ]

        parts = []
        for part_type, weight in parts_data:
            part = SlaughterPart.objects.create(
                animal=animal,
                part_type=part_type,
                weight=weight,
                weight_unit='kg'
            )
            parts.append(part)

        # Test slaughter parts
        self.assertEqual(len(parts), 4)
        self.assertTrue(animal.has_slaughter_parts)

        # Test part types and weights
        part_types = [p.part_type for p in parts]
        self.assertIn('left_carcass', part_types)
        self.assertIn('right_carcass', part_types)
        self.assertIn('head', part_types)
        self.assertIn('feet', part_types)

        # Test weights
        left_carcass = next(p for p in parts if p.part_type == 'left_carcass')
        right_carcass = next(p for p in parts if p.part_type == 'right_carcass')
        head = next(p for p in parts if p.part_type == 'head')
        feet = next(p for p in parts if p.part_type == 'feet')

        self.assertEqual(left_carcass.weight, 120.0)
        self.assertEqual(right_carcass.weight, 118.0)
        self.assertEqual(head.weight, 15.0)
        self.assertEqual(feet.weight, 12.0)

    def test_split_carcass_measurement_validation(self):
        """Test validation of split carcass measurements"""
        animal = Animal.objects.create(
            farmer=self.farmer,
            species='cow',
            age=24.0,
            live_weight=500.0,
            animal_id='TEST_SPLIT_003'
        )

        # Test valid split carcass measurement
        measurement = CarcassMeasurement(
            animal=animal,
            carcass_type='split',
            left_carcass_weight=120.0,
            right_carcass_weight=118.0,
            head_weight=15.0,
            feet_weight=12.0,
            organs_weight=25.0
        )

        # Should not raise validation error
        try:
            measurement.clean()
        except Exception as e:
            self.fail(f"Valid split carcass measurement raised validation error: {e}")

        # Test invalid measurement (negative weight)
        invalid_measurement = CarcassMeasurement(
            animal=animal,
            carcass_type='split',
            left_carcass_weight=-10.0,  # Invalid negative weight
            right_carcass_weight=118.0,
            head_weight=15.0,
            feet_weight=12.0,
            organs_weight=25.0
        )

        with self.assertRaises(Exception):
            invalid_measurement.clean()

    def test_animal_lifecycle_status_split_carcass(self):
        """Test lifecycle status for split carcass animals"""
        # Create split carcass animal
        animal = Animal.objects.create(
            farmer=self.farmer,
            species='cow',
            age=24.0,
            live_weight=500.0,
            animal_id='TEST_SPLIT_004'
        )

        # Initially healthy
        self.assertEqual(animal.lifecycle_status, 'HEALTHY')
        self.assertTrue(animal.is_healthy)

        # Create slaughter parts and transfer some
        left_part = SlaughterPart.objects.create(
            animal=animal,
            part_type='left_carcass',
            weight=120.0,
            weight_unit='kg'
        )
        right_part = SlaughterPart.objects.create(
            animal=animal,
            part_type='right_carcass',
            weight=118.0,
            weight_unit='kg'
        )

        # Transfer left part
        left_part.transferred_to = self.processing_unit
        left_part.transferred_at = timezone.now()
        left_part.save()

        # Should be SEMI-TRANSFERRED
        self.assertEqual(animal.lifecycle_status, 'SEMI-TRANSFERRED')
        self.assertTrue(animal.is_semi_transferred_status)

        # Transfer right part
        right_part.transferred_to = self.processing_unit
        right_part.transferred_at = timezone.now()
        right_part.save()

        # Should be TRANSFERRED
        self.assertEqual(animal.lifecycle_status, 'TRANSFERRED')
        self.assertTrue(animal.is_transferred_status)


class SplitCarcassAPITests(APITestCase):
    """Test split carcass API endpoints"""

    def setUp(self):
        """Set up test data and client"""
        self.client = APIClient()

        # Clean up any existing test data first
        UserProfile.objects.filter(user__username__in=['test_farmer_api', 'test_processor_api']).delete()
        User.objects.filter(username__in=['test_farmer_api', 'test_processor_api']).delete()
        ProcessingUnit.objects.filter(name='Test Processing Unit API').delete()
        Animal.objects.filter(animal_id='TEST_SPLIT_API_001').delete()

        # Create users
        self.farmer = User.objects.create_user(
            username='test_farmer_api', email='farmer_api@test.com', password='testpass123'
        )
        self.processor = User.objects.create_user(
            username='test_processor_api', email='processor_api@test.com', password='testpass123'
        )

        # Create processing unit
        self.processing_unit = ProcessingUnit.objects.create(
            name='Test Processing Unit API', location='Test Location'
        )

        # Create profiles
        UserProfile.objects.create(user=self.farmer, role='farmer')
        UserProfile.objects.create(user=self.processor, role='processing_unit',
                                  processing_unit=self.processing_unit)

        # Create split carcass animal
        self.split_animal = Animal.objects.create(
            farmer=self.farmer,
            species='cow',
            age=24.0,
            live_weight=500.0,
            animal_id='TEST_SPLIT_API_001'
        )

        # Create carcass measurement
        self.measurement = CarcassMeasurement.objects.create(
            animal=self.split_animal,
            carcass_type='split',
            left_carcass_weight=120.0,
            right_carcass_weight=118.0,
            head_weight=15.0,
            feet_weight=12.0,
            organs_weight=25.0
        )

        # Create slaughter parts
        self.parts = []
        parts_data = [
            ('left_carcass', 120.0),
            ('right_carcass', 118.0),
            ('head', 15.0),
            ('feet', 12.0),
        ]

        for part_type, weight in parts_data:
            part = SlaughterPart.objects.create(
                animal=self.split_animal,
                part_type=part_type,
                weight=weight,
                weight_unit='kg'
            )
            self.parts.append(part)

    def test_carcass_measurement_api_create_split(self):
        """Test creating split carcass measurement via API"""
        self.client.force_authenticate(user=self.farmer)

        measurement_data = {
            'animal_id': self.split_animal.id,
            'carcass_type': 'split',
            'measurements': {
                'head_weight': {'value': 15.0, 'unit': 'kg'},
                'torso_weight': {'value': 200.0, 'unit': 'kg'},
                'left_carcass_weight': {'value': 120.0, 'unit': 'kg'},
                'right_carcass_weight': {'value': 118.0, 'unit': 'kg'},
                'feet_weight': {'value': 12.0, 'unit': 'kg'},
                'organs_weight': {'value': 25.0, 'unit': 'kg'},
            }
        }

        response = self.client.post('/api/v2/carcass-measurements/', measurement_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify measurement was created
        measurement = CarcassMeasurement.objects.get(animal=self.split_animal)
        self.assertEqual(measurement.carcass_type, 'split')
        self.assertEqual(measurement.get_measurement('head_weight')['value'], 15.0)

    def test_receive_animals_split_carcass_validation(self):
        """Test receiving split carcass animals with proper validation"""
        # First transfer the parts
        for part in self.parts:
            part.transferred_to = self.processing_unit
            part.transferred_at = timezone.now()
            part.save()

        # Authenticate as processor
        self.client.force_authenticate(user=self.processor)

        # Test 1: Try to receive split carcass as whole animal (should fail)
        response = self.client.post('/api/v2/animals/receive_animals/', {
            'animal_ids': [self.split_animal.id]
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('split carcass animal', str(response.data.get('error', '')).lower())

        # Test 2: Receive split carcass parts individually (should succeed)
        part_ids = [p.id for p in self.parts]
        response = self.client.post('/api/v2/animals/receive_animals/', {
            'part_receives': [{
                'animal_id': self.split_animal.id,
                'part_ids': part_ids
            }]
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify animal is received
        self.split_animal.refresh_from_db()
        self.assertEqual(self.split_animal.received_by, self.processor)
        self.assertIsNotNone(self.split_animal.received_at)

        # Verify parts are received
        for part in self.parts:
            part.refresh_from_db()
            self.assertEqual(part.received_by, self.processor)
            self.assertIsNotNone(part.received_at)

    def test_receive_animals_split_carcass_missing_parts(self):
        """Test receiving split carcass with missing required parts"""
        # Transfer only some parts (missing head and feet)
        left_part = self.parts[0]  # left_carcass
        right_part = self.parts[1]  # right_carcass

        left_part.transferred_to = self.processing_unit
        left_part.transferred_at = timezone.now()
        left_part.save()

        right_part.transferred_to = self.processing_unit
        right_part.transferred_at = timezone.now()
        right_part.save()

        # Authenticate as processor
        self.client.force_authenticate(user=self.processor)

        # Try to receive with missing parts
        response = self.client.post('/api/v2/animals/receive_animals/', {
            'part_receives': [{
                'animal_id': self.split_animal.id,
                'part_ids': [left_part.id, right_part.id]  # Missing head and feet
            }]
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('missing required parts', str(response.data.get('error', '')).lower())
        self.assertIn('head', str(response.data.get('error', '')).lower())
        self.assertIn('feet', str(response.data.get('error', '')).lower())

    def test_transfer_split_carcass_parts(self):
        """Test transferring split carcass parts"""
        self.client.force_authenticate(user=self.farmer)

        # Transfer individual parts
        part_ids = [self.parts[0].id, self.parts[1].id]  # left and right carcass

        response = self.client.post('/api/v2/animals/transfer/', {
            'part_transfers': [{
                'animal_id': self.split_animal.id,
                'part_ids': part_ids
            }],
            'processing_unit_id': self.processing_unit.id
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify parts are transferred
        for part in self.parts[:2]:  # left and right carcass
            part.refresh_from_db()
            self.assertEqual(part.transferred_to, self.processing_unit)
            self.assertIsNotNone(part.transferred_at)

        # Other parts should not be transferred
        for part in self.parts[2:]:  # head and feet
            part.refresh_from_db()
            self.assertIsNone(part.transferred_to)

    def test_animal_list_filtering_split_carcass(self):
        """Test animal list filtering for split carcass animals"""
        self.client.force_authenticate(user=self.processor)

        # Transfer some parts
        for part in self.parts[:2]:  # Transfer left and right carcass
            part.transferred_to = self.processing_unit
            part.transferred_at = timezone.now()
            part.save()

        # Test filtering by status
        response = self.client.get('/api/v2/animals/by-status/?status=SEMI-TRANSFERRED')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should include our split carcass animal
        animals_data = response.data['animals']
        animal_ids = [animal['id'] for animal in animals_data]
        self.assertIn(self.split_animal.id, animal_ids)

    def test_split_carcass_measurement_serialization(self):
        """Test serialization of split carcass measurements"""
        serializer = CarcassMeasurementSerializer(self.measurement)
        data = serializer.data

        # Check carcass type
        self.assertEqual(data['carcass_type'], 'split')

        # Check that split-specific fields are included
        self.assertIn('left_carcass_weight', data)
        self.assertIn('right_carcass_weight', data)
        self.assertIn('head_weight', data)
        self.assertIn('feet_weight', data)

        # Check values
        self.assertEqual(float(data['left_carcass_weight']), 120.0)
        self.assertEqual(float(data['right_carcass_weight']), 118.0)
        self.assertEqual(float(data['head_weight']), 15.0)
        self.assertEqual(float(data['feet_weight']), 12.0)


class SplitCarcassIntegrationTests(TransactionTestCase):
    """Integration tests for complete split carcass workflow"""

    def setUp(self):
        """Set up complete test scenario"""
        self.client = APIClient()

        # Clean up any existing test data first
        UserProfile.objects.filter(user__username__in=['farmer_integration', 'processor_integration']).delete()
        User.objects.filter(username__in=['farmer_integration', 'processor_integration']).delete()
        ProcessingUnit.objects.filter(name='Test PU Integration').delete()
        Animal.objects.filter(animal_id='WORKFLOW_TEST_001').delete()
        ProductCategory.objects.filter(name='Test Category').delete()

        # Create users and processing unit
        self.farmer = User.objects.create_user(
            username='farmer_integration', email='farmer_integration@test.com', password='testpass123'
        )
        self.processor = User.objects.create_user(
            username='processor_integration', email='processor_integration@test.com', password='testpass123'
        )
        self.processing_unit = ProcessingUnit.objects.create(
            name='Test PU Integration', location='Test Location'
        )

        UserProfile.objects.create(user=self.farmer, role='farmer')
        UserProfile.objects.create(user=self.processor, role='processing_unit',
                                  processing_unit=self.processing_unit)

    def test_complete_split_carcass_workflow(self):
        """Test complete workflow from creation to product creation"""
        # 1. Create animal
        animal = Animal.objects.create(
            farmer=self.farmer,
            species='cow',
            age=24.0,
            live_weight=500.0,
            animal_id='WORKFLOW_TEST_001'
        )

        # 2. Create split carcass measurement
        self.client.force_authenticate(user=self.farmer)
        measurement_data = {
            'animal_id': animal.id,
            'carcass_type': 'split',
            'measurements': {
                'head_weight': {'value': 15.0, 'unit': 'kg'},
                'left_carcass_weight': {'value': 120.0, 'unit': 'kg'},
                'right_carcass_weight': {'value': 118.0, 'unit': 'kg'},
                'feet_weight': {'value': 12.0, 'unit': 'kg'},
                'organs_weight': {'value': 25.0, 'unit': 'kg'},
            }
        }

        response = self.client.post('/api/v2/carcass-measurements/', measurement_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 3. Transfer parts
        animal.refresh_from_db()
        parts = list(animal.slaughter_parts.all())
        self.assertEqual(len(parts), 4)  # Should have 4 parts

        part_ids = [p.id for p in parts]
        response = self.client.post('/api/v2/animals/transfer/', {
            'part_transfers': [{
                'animal_id': animal.id,
                'part_ids': part_ids
            }],
            'processing_unit_id': self.processing_unit.id
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 4. Receive parts
        self.client.force_authenticate(user=self.processor)
        response = self.client.post('/api/v2/animals/receive_animals/', {
            'part_receives': [{
                'animal_id': animal.id,
                'part_ids': part_ids
            }]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 5. Create products from parts
        category = ProductCategory.objects.create(name='Test Category')

        # Create product from left carcass
        left_part = next(p for p in parts if p.part_type == 'left_carcass')
        product_data = {
            'processing_unit': self.processing_unit.id,
            'animal': animal.id,
            'slaughter_part': left_part.id,
            'product_type': 'meat',
            'name': 'Left Beef Cut',
            'batch_number': 'BATCH001',
            'weight': 100.0,
            'weight_unit': 'kg',
            'quantity': 100.0,
            'price': 50.0,
            'category': category.id
        }

        response = self.client.post('/api/v2/products/', product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify product was created
        product = Product.objects.get(batch_number='BATCH001')
        self.assertEqual(product.name, 'Left Beef Cut')
        self.assertEqual(product.slaughter_part, left_part)
        self.assertEqual(product.animal, animal)

        # Verify workflow completed successfully
        animal.refresh_from_db()
        self.assertEqual(animal.lifecycle_status, 'TRANSFERRED')
        self.assertTrue(animal.is_transferred_status)
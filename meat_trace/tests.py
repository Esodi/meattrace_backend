from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Animal, ProductCategory, Product
from .serializers import AnimalSerializer, ProductSerializer, ProductCategorySerializer

class AnimalModelTest(TestCase):
    def test_animal_creation(self):
        animal = Animal.objects.create(
            animal_id='A001',
            name='Bessie',
            species='cow',
            weight_kg=500.0,
            breed='Holstein',
            abbatoir_name='Green Abbatoir'
        )
        self.assertEqual(animal.animal_id, 'A001')
        self.assertEqual(str(animal), 'Bessie (A001)')

    def test_animal_unique_id(self):
        Animal.objects.create(animal_id='A001', name='Bessie', species='cow', weight_kg=500.0, breed='Holstein', abbatoir_name='Green Abbatoir')
        with self.assertRaises(Exception):
            Animal.objects.create(animal_id='A001', name='Another', species='cow', weight_kg=400.0, breed='Jersey', abbatoir_name='Blue Abbatoir')

class ProductCategoryModelTest(TestCase):
    def test_category_creation(self):
        category = ProductCategory.objects.create(name='Meat', description='Fresh meat products')
        self.assertEqual(category.name, 'Meat')
        self.assertEqual(str(category), 'Meat')

    def test_category_unique_name(self):
        ProductCategory.objects.create(name='Meat')
        with self.assertRaises(Exception):
            ProductCategory.objects.create(name='Meat')

class ProductModelTest(TestCase):
    def setUp(self):
        self.animal = Animal.objects.create(animal_id='A001', name='Bessie', species='cow', weight_kg=500.0, breed='Holstein', abbatoir_name='Green Abbatoir')
        self.category = ProductCategory.objects.create(name='Meat')

    def test_product_creation(self):
        product = Product.objects.create(
            sku='P001',
            name='Beef Steak',
            animal=self.animal,
            category=self.category,
            price=25.99,
            weight_kg=1.5,
            processing_unit='Unit A',
            processing_date=timezone.now().date(),
            batch_number='B001',
            qr_code='QR001'
        )
        self.assertEqual(product.sku, 'P001')
        self.assertEqual(str(product), 'Beef Steak (P001)')

    def test_product_unique_sku(self):
        Product.objects.create(sku='P001', name='Beef Steak', animal=self.animal, category=self.category, price=25.99, weight_kg=1.5, processing_unit='Unit A', processing_date=timezone.now().date(), batch_number='B001', qr_code='QR001')
        with self.assertRaises(Exception):
            Product.objects.create(sku='P001', name='Another', animal=self.animal, category=self.category, price=20.00, weight_kg=1.0, processing_unit='Unit B', processing_date=timezone.now().date(), batch_number='B002', qr_code='QR002')

class ShopReceiptModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.animal = Animal.objects.create(animal_id='A001', name='Bessie', species='cow', weight_kg=500.0, breed='Holstein', abbatoir_name='Green Abbatoir')
        self.category = ProductCategory.objects.create(name='Meat')
        self.product = Product.objects.create(sku='P001', name='Beef Steak', animal=self.animal, category=self.category, price=25.99, weight_kg=1.5, processing_unit='Unit A', processing_date=timezone.now().date(), batch_number='B001', qr_code='QR001')

    def test_receipt_creation(self):
        receipt = ShopReceipt.objects.create(user=self.user, shop_name='Super Market', total_amount=51.98)
        receipt.products.add(self.product)
        self.assertEqual(receipt.shop_name, 'Super Market')
        self.assertEqual(str(receipt), 'Receipt 1 - Super Market')

class AnimalSerializerTest(TestCase):
    def setUp(self):
        self.animal = Animal.objects.create(animal_id='A001', name='Bessie', species='cow', weight_kg=500.0, breed='Holstein', abbatoir_name='Green Abbatoir')

    def test_animal_serializer(self):
        serializer = AnimalSerializer(self.animal)
        self.assertEqual(serializer.data['animal_id'], 'A001')

    def test_animal_serializer_validation(self):
        data = {'animal_id': 'A001', 'name': 'Bessie', 'species': 'cow', 'weight_kg': -10, 'breed': 'Holstein', 'abbatoir_name': 'Green Abbatoir'}
        serializer = AnimalSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('weight_kg', serializer.errors)

class ProductSerializerTest(TestCase):
    def setUp(self):
        self.animal = Animal.objects.create(animal_id='A001', name='Bessie', species='cow', weight_kg=500.0, breed='Holstein', abbatoir_name='Green Abbatoir')
        self.category = ProductCategory.objects.create(name='Meat')

    def test_product_serializer(self):
        product = Product.objects.create(sku='P001', name='Beef Steak', animal=self.animal, category=self.category, price=25.99, weight_kg=1.5, processing_unit='Unit A', processing_date=timezone.now().date(), batch_number='B001', qr_code='QR001')
        serializer = ProductSerializer(product)
        self.assertEqual(serializer.data['sku'], 'P001')

    def test_product_serializer_validation(self):
        data = {'sku': 'P001', 'name': 'Beef Steak', 'animal_id': self.animal.id, 'category_id': self.category.id, 'price': -5, 'weight_kg': 1.5, 'processing_unit': 'Unit A', 'batch_number': 'B001', 'qr_code': 'QR001'}
        serializer = ProductSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('price', serializer.errors)

class AnimalAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)
        self.animal = Animal.objects.create(animal_id='A001', name='Bessie', species='cow', weight_kg=500.0, breed='Holstein', abbatoir_name='Green Abbatoir')

    def test_get_animals(self):
        response = self.client.get('/api/v2/animals/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_animal(self):
        data = {'animal_id': 'A002', 'name': 'Daisy', 'species': 'cow', 'weight_kg': 450.0, 'breed': 'Jersey', 'abbatoir_name': 'Blue Abbatoir'}
        response = self.client.post('/api/v2/animals/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

class ProductAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)
        self.animal = Animal.objects.create(animal_id='A001', name='Bessie', species='cow', weight_kg=500.0, breed='Holstein', abbatoir_name='Green Abbatoir')
        self.category = ProductCategory.objects.create(name='Meat')

    def test_get_products(self):
        response = self.client.get('/api/v2/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_product(self):
        data = {'sku': 'P001', 'name': 'Beef Steak', 'animal_id': self.animal.id, 'category_id': self.category.id, 'price': 25.99, 'weight_kg': 1.5, 'processing_unit': 'Unit A', 'processing_date': timezone.now().date(), 'batch_number': 'B001', 'qr_code': 'QR001'}
        response = self.client.post('/api/v2/products/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_product_detail(self):
        product = Product.objects.create(sku='P001', name='Beef Steak', animal=self.animal, category=self.category, price=25.99, weight_kg=1.5, processing_unit='Unit A', processing_date=timezone.now().date(), batch_number='B001', qr_code='QR001')
        response = self.client.get(f'/api/v2/products/{product.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class ProductCategoryAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)

    def test_get_categories(self):
        response = self.client.get('/api/v2/product_categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_category(self):
        data = {'name': 'Dairy', 'description': 'Milk products'}
        response = self.client.post('/api/v2/product_categories/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

class ShopReceiptAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)
        self.animal = Animal.objects.create(animal_id='A001', name='Bessie', species='cow', weight_kg=500.0, breed='Holstein', abbatoir_name='Green Abbatoir')
        self.category = ProductCategory.objects.create(name='Meat')
        self.product = Product.objects.create(sku='P001', name='Beef Steak', animal=self.animal, category=self.category, price=25.99, weight_kg=1.5, processing_unit='Unit A', processing_date=timezone.now().date(), batch_number='B001', qr_code='QR001')

    def test_create_receipt(self):
        data = {'shop_name': 'Super Market', 'product_ids': [self.product.id], 'total_amount': 25.99}
        response = self.client.post('/api/v2/shop_receipts/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

import unittest
import requests
import json
import os
import sys
from django.contrib.auth import get_user_model
from meat_trace.models import Shop, UserProfile

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Ensure Django is configured before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
import django
django.setup()

User = get_user_model()

class TestShopUnitAPI(unittest.TestCase):
    """
    A comprehensive test suite for the Shop Unit API endpoints.
    """
    BASE_URL = "http://127.0.0.1:8000/api/v2"
    SHOP_OWNER_USERNAME = "shop_user"
    SHOP_OWNER_PASSWORD = "password123"

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class with an authenticated user and a shop.
        """
        super().setUpClass()
        cls.token = cls._get_auth_token(cls.SHOP_OWNER_USERNAME, cls.SHOP_OWNER_PASSWORD)
        if not cls.token:
            raise Exception("Could not authenticate. Ensure the test user is created.")

        cls.user = User.objects.get(username=cls.SHOP_OWNER_USERNAME)
        cls.shop, _ = Shop.objects.get_or_create(name="Test Shop", defaults={"location": "Test Location"})
        cls.user_profile, _ = UserProfile.objects.get_or_create(user=cls.user, defaults={'role': 'shop'})
        cls.user_profile.shop = cls.shop
        cls.user_profile.save()

        cls.headers = {"Authorization": f"Token {cls.token}"}
        cls.shop_id = cls.shop.id
        cls.product_id = cls._create_product(cls, cls.shop.id)

    @staticmethod
    def _get_auth_token(username, password):
        """
        Helper method to authenticate a user and get a token.
        """
        url = "http://127.0.0.1:8000/api-token-auth/"
        data = {"username": username, "password": password}
        response = requests.post(url, data=data)
        if response.status_code == 200:
            return response.json().get("token")
        return None

    def _create_shop(self):
        """
        Helper method to create a shop for testing.
        """
        url = f"{self.BASE_URL}/shops/"
        data = {
            "name": "Another Test Shop",
            "location": "Test Location",
            "description": "A shop for testing purposes"
        }
        response = requests.post(url, headers=self.headers, json=data)
        if response.status_code == 201:
            return response.json()["id"]
        return None

    def _create_product(self, shop_id):
        """
        Helper method to create a product for testing.
        """
        url = f"{self.BASE_URL}/products/"
        data = {
            "name": "Test Product",
            "price": "10.99",
            "description": "A product for testing purposes",
            "shop": shop_id
        }
        response = requests.post(url, headers=self.headers, json=data)
        if response.status_code == 201:
            return response.json()["id"]
        return None

    def test_01_create_shop(self):
        """
        Test creating a new shop.
        """
        url = f"{self.BASE_URL}/shops/"
        shop_name = "Another Test Shop"

        # Ensure the shop does not already exist
        if Shop.objects.filter(name=shop_name).exists():
            self.skipTest("Shop already exists, skipping creation test.")

        data = {
            "name": shop_name,
            "location": "Another Test Location",
            "description": "Another test shop"
        }
        response = requests.post(url, headers=self.headers, json=data)
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.json())

    def test_02_get_shops(self):
        """
        Test retrieving a list of shops.
        """
        url = f"{self.BASE_URL}/shops/"
        response = requests.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_03_get_shop_detail(self):
        """
        Test retrieving a single shop by ID.
        """
        url = f"{self.BASE_URL}/shops/{self.shop_id}/"
        response = requests.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.shop_id)

    def test_04_update_shop(self):
        """
        Test updating an existing shop.
        """
        url = f"{self.BASE_URL}/shops/{self.shop_id}/"
        data = {"name": "Updated Test Shop"}
        response = requests.patch(url, headers=self.headers, json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Updated Test Shop")

    def test_05_delete_shop(self):
        """
        Test deleting a shop.
        """
        shop_to_delete = self._create_shop()
        url = f"{self.BASE_URL}/shops/{shop_to_delete}/"
        response = requests.delete(url, headers=self.headers)
        self.assertEqual(response.status_code, 204)

    def test_06_create_product(self):
        """
        Test creating a new product.
        """
        url = f"{self.BASE_URL}/products/"
        data = {
            "name": "Another Test Product",
            "price": "15.99",
            "description": "Another test product",
            "shop": self.shop_id
        }
        response = requests.post(url, headers=self.headers, json=data)
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.json())

    def test_07_get_products(self):
        """
        Test retrieving a list of products.
        """
        url = f"{self.BASE_URL}/products/"
        response = requests.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_08_get_product_detail(self):
        """
        Test retrieving a single product by ID.
        """
        url = f"{self.BASE_URL}/products/{self.product_id}/"
        response = requests.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.product_id)

    def test_09_update_product(self):
        """
        Test updating an existing product.
        """
        url = f"{self.BASE_URL}/products/{self.product_id}/"
        data = {"name": "Updated Test Product"}
        response = requests.patch(url, headers=self.headers, json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Updated Test Product")

    def test_10_delete_product(self):
        """
        Test deleting a product.
        """
        product_to_delete = self._create_product(self.shop_id)
        url = f"{self.BASE_URL}/products/{product_to_delete}/"
        response = requests.delete(url, headers=self.headers)
        self.assertEqual(response.status_code, 204)

    def test_11_create_order(self):
        """
        Test creating a new order.
        """
        url = f"{self.BASE_URL}/orders/"
        data = {
            "shop": self.shop_id,
            "items": [{"product": self.product_id, "quantity": 2}],
            "customer": self.user.id
        }
        response = requests.post(url, headers=self.headers, json=data)
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.json())

    def test_12_get_orders(self):
        """
        Test retrieving a list of orders.
        """
        self.test_11_create_order()  # Ensure there is at least one order
        url = f"{self.BASE_URL}/orders/"
        response = requests.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_13_error_handling_not_found(self):
        """
        Test that a 404 error is returned for a non-existent resource.
        """
        url = f"{self.BASE_URL}/shops/99999/"
        response = requests.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_14_error_handling_bad_request(self):
        """
        Test that a 400 error is returned for a bad request.
        """
        url = f"{self.BASE_URL}/shops/"
        data = {"name": ""}  # Invalid data
        response = requests.post(url, headers=self.headers, json=data)
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    unittest.main()
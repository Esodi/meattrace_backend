
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
from datetime import timedelta
from .models import Shop, UserProfile, Invoice, InvoicePayment, ShopUser

from django.urls import reverse

class InvoiceActionTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='shopowner', password='testpass')
        self.shop = Shop.objects.create(name='Test Shop')
        
        # Ensure profile exists and has correct info
        profile, created = UserProfile.objects.get_or_create(user=self.user)
        profile.shop = self.shop
        profile.role = 'ShopOwner'
        profile.save()
        
        # Also create ShopUser membership (new system requirement)
        ShopUser.objects.create(
            user=self.user,
            shop=self.shop,
            role='owner',
            is_active=True
        )
        
        # Refresh user to clear any cached relations
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)
        
        self.invoice = Invoice.objects.create(
            invoice_number='INV-001',
            shop=self.shop,
            customer_name='Test Customer',
            total_amount=Decimal('1000.00'),
            amount_paid=Decimal('0.00'),
            due_date=timezone.now().date() + timedelta(days=7),
            status='pending'
        )

    def test_list_invoices(self):
        url = reverse('invoices-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_record_payment_success(self):
        url = reverse('invoices-record-payment', kwargs={'pk': self.invoice.id})
        data = {
            'amount': 500.00,
            'payment_method': 'cash',
            'transaction_reference': 'REF123',
            'notes': 'Partial payment'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal('500.00'))
        self.assertEqual(self.invoice.status, 'partially_paid')
        self.assertEqual(self.invoice.payments.count(), 1)
        
        payment = self.invoice.payments.first()
        self.assertEqual(payment.transaction_reference, 'REF123')

    def test_record_payment_full(self):
        url = reverse('invoices-record-payment', kwargs={'pk': self.invoice.id})
        data = {
            'amount': 1000.00,
            'payment_method': 'cash'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal('1000.00'))
        self.assertEqual(self.invoice.status, 'paid')

    def test_record_payment_exceeds_balance(self):
        url = reverse('invoices-record-payment', kwargs={'pk': self.invoice.id})
        data = {
            'amount': 1500.00,
            'payment_method': 'cash'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds balance due', response.data['error'])

    def test_invoice_stats(self):
        url = reverse('invoices-stats')
        response = self.client.get(url)
        if response.status_code != status.HTTP_200_OK:
            print(f"DEBUG: invoice_stats failed. Status: {response.status_code}, Data: {response.data}")
            
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['pending'], 1)
        self.assertEqual(response.data['total_invoices'], 1)
        self.assertIn('draft', response.data)
        self.assertIn('sent', response.data)
        self.assertIn('partially_paid', response.data)

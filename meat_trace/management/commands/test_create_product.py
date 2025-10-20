from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, force_authenticate
from meat_trace.models import ProcessingUnit, Animal
from meat_trace.views import ProductViewSet
from django.utils import timezone


class Command(BaseCommand):
    help = 'Test product creation via ProductViewSet (integration smoke test)'

    def handle(self, *args, **options):
        self.stdout.write('Starting test_create_product...')

        # Clean up any existing test users
        User.objects.filter(username='pu_test').delete()
        User.objects.filter(username='farmer_x').delete()

        # Create processing unit user
        pu_user = User.objects.create_user(username='pu_test', password='test')
        pu = ProcessingUnit.objects.create(name='PU Test')
        # Ensure profile exists and link processing unit
        try:
            profile = pu_user.profile
        except Exception:
            from meat_trace.models import UserProfile
            profile = UserProfile.objects.create(user=pu_user)
        profile.role = 'ProcessingUnit'
        profile.processing_unit = pu
        profile.save()

        # Create farmer and an animal that is slaughtered and received by the processing unit user
        farmer = User.objects.create_user(username='farmer_x', password='test')
        a = Animal.objects.create(farmer=farmer, species='cow', age=12.0, live_weight=200.0)
        # mark slaughtered and received
        a.slaughtered = True
        a.received_by = pu_user
        a.received_at = timezone.now()
        a.save()

        # Build request
        factory = APIRequestFactory()
        data = {
            'animal': a.id,
            'name': 'Test Product',
            'batch_number': 'B1',
            'product_type': 'meat',
            'quantity': 1,
            'weight': 10,
            'weight_unit': 'kg',
            'price': 50,
        }

        view = ProductViewSet.as_view({'post': 'create'})
        req = factory.post('/api/v2/products/', data, format='json')
        force_authenticate(req, user=pu_user)

        resp = view(req)
        self.stdout.write(f'STATUS: {getattr(resp, "status_code", "N/A")}')
        try:
            self.stdout.write(f'DATA: {resp.data}')
        except Exception as e:
            self.stdout.write(f'Failed to read response data: {e}')

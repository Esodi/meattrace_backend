from django.core.management.base import BaseCommand
from meat_trace.models import ProductCategory, ProcessingStage

class Command(BaseCommand):
    help = 'Populate initial data for product categories and processing stages'

    def handle(self, *args, **options):
        # Create product categories
        categories_data = [
            {'name': 'Fresh Meat', 'description': 'Fresh cuts of meat'},
            {'name': 'Processed Meat', 'description': 'Processed meat products'},
            {'name': 'Organic Meat', 'description': 'Organic meat products'},
            {'name': 'Premium Cuts', 'description': 'Premium quality cuts'},
            {'name': 'Ground Meat', 'description': 'Ground meat products'},
            {'name': 'Sausages', 'description': 'Various sausage products'},
        ]

        for category_data in categories_data:
            category, created = ProductCategory.objects.get_or_create(
                name=category_data['name'],
                defaults={'description': category_data['description']}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created category: {category.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Category already exists: {category.name}')
                )

        # Create processing stages
        stages_data = [
            {'name': 'received', 'description': 'Product received at processing facility', 'order': 1},
            {'name': 'inspected', 'description': 'Quality inspection completed', 'order': 2},
            {'name': 'processed', 'description': 'Processing completed', 'order': 3},
            {'name': 'packaged', 'description': 'Product packaged', 'order': 4},
            {'name': 'stored', 'description': 'Product stored in cold storage', 'order': 5},
            {'name': 'shipped', 'description': 'Product shipped to destination', 'order': 6},
        ]

        for stage_data in stages_data:
            stage, created = ProcessingStage.objects.get_or_create(
                name=stage_data['name'],
                defaults={
                    'description': stage_data['description'],
                    'order': stage_data['order']
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created processing stage: {stage.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Processing stage already exists: {stage.name}')
                )

        self.stdout.write(
            self.style.SUCCESS('Initial data population completed!')
        )
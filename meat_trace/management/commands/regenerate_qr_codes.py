import os
import logging
import qrcode
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from meat_trace.models import Product

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Regenerate QR codes for existing products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product-id',
            type=int,
            help='Regenerate QR code for a specific product ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Regenerate QR codes for all products',
        )

    def handle(self, *args, **options):
        if options['product_id']:
            try:
                product = Product.objects.get(id=options['product_id'])
                self.regenerate_qr_code(product)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully regenerated QR code for product {product.id}')
                )
            except Product.DoesNotExist:
                raise CommandError(f'Product with id {options["product_id"]} does not exist')
        elif options['all']:
            products = Product.objects.all()
            count = 0
            for product in products:
                try:
                    self.regenerate_qr_code(product)
                    count += 1
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f'Failed to regenerate QR code for product {product.id}: {str(e)}')
                    )
            self.stdout.write(
                self.style.SUCCESS(f'Successfully regenerated QR codes for {count} products')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Please specify --product-id or --all')
            )

    def regenerate_qr_code(self, product):
        # Generate the URL for the product API endpoint
        url = f"{settings.SITE_URL or 'http://localhost:8000'}/api/v1/products/{product.id}/"

        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # Create the image
        img = qr.make_image(fill_color="black", back_color="white")

        # Ensure the qr_codes directory exists
        qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
        os.makedirs(qr_dir, exist_ok=True)

        # Remove old QR code file if exists
        if product.qr_code:
            old_path = os.path.join(settings.MEDIA_ROOT, product.qr_code.name)
            if os.path.exists(old_path):
                os.remove(old_path)

        # Save the image
        filename = f"qr_{product.id}.png"
        filepath = os.path.join(qr_dir, filename)
        img.save(filepath)

        # Update the instance with the relative path
        product.qr_code = f"qr_codes/{filename}"
        product.save(update_fields=['qr_code'])

        logger.info(f"QR code regenerated for product {product.id}")
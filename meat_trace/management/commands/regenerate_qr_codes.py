import os
import logging

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from meat_trace.models import Product, write_qr_png

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Generate/regenerate product QR codes pointing at the public traceability '
        'page. Use --missing to backfill only products that have no QR code yet, '
        'or --all to rewrite every image (needed after the encoded URL changes).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--product-id',
            type=int,
            help='Regenerate the QR code for a single product ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Regenerate QR codes for every product (overwrites existing images)',
        )
        parser.add_argument(
            '--missing',
            action='store_true',
            help='Backfill only products with no QR code, or whose image file is gone',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if options['product_id']:
            try:
                products = [Product.objects.get(id=options['product_id'])]
            except Product.DoesNotExist:
                raise CommandError(f'Product with id {options["product_id"]} does not exist')
        elif options['all']:
            products = Product.objects.all().order_by('id')
        elif options['missing']:
            products = [p for p in Product.objects.all().order_by('id') if self._needs_qr(p)]
        else:
            self.stdout.write(self.style.WARNING(
                'Specify one of --product-id, --all or --missing'
            ))
            return

        total = len(products) if isinstance(products, list) else products.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nothing to do — all products already have QR codes.'))
            return

        self.stdout.write(f'{"[dry-run] " if dry_run else ""}Processing {total} product(s)...')

        done = failed = 0
        for product in products:
            try:
                if dry_run:
                    self.stdout.write(f'  would write {product.id}: {product.trace_url}')
                else:
                    self.regenerate_qr_code(product)
                done += 1
            except Exception as e:
                failed += 1
                self.stderr.write(self.style.ERROR(
                    f'  product {product.id}: {e}'
                ))

        style = self.style.SUCCESS if not failed else self.style.WARNING
        self.stdout.write(style(
            f'{"[dry-run] " if dry_run else ""}Done: {done} succeeded, {failed} failed.'
        ))

    def _needs_qr(self, product):
        if not product.qr_code:
            return True
        return not os.path.exists(os.path.join(settings.MEDIA_ROOT, product.qr_code))

    def regenerate_qr_code(self, product):
        """Point the QR at the public traceability page for this product.

        Product.trace_url is the single definition of the encoded URL; see its
        docstring for why it must stay under /api/v2/.
        """
        filename = f"product_qr_{product.id}.png"

        # Drop a previously generated image if it lived under a different name
        # (older builds used qr_<id>.png), so stale files don't accumulate.
        if product.qr_code and product.qr_code != f"qr_codes/{filename}":
            old_path = os.path.join(settings.MEDIA_ROOT, product.qr_code)
            if os.path.exists(old_path):
                os.remove(old_path)

        path = write_qr_png(product.trace_url, filename)
        Product.objects.filter(pk=product.pk).update(qr_code=path)
        product.qr_code = path

        logger.info('QR code regenerated for product %s -> %s', product.id, product.trace_url)

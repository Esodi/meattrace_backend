# Generated migration to fix Product.received_by field

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('meat_trace', '0035_productinfo'),
    ]

    operations = [
        # Remove the old received_by field (User FK)
        migrations.RemoveField(
            model_name='product',
            name='received_by',
        ),
        # Add new received_by_shop field (Shop FK)
        migrations.AddField(
            model_name='product',
            name='received_by_shop',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='received_products_as_shop',
                to='meat_trace.shop'
            ),
        ),
    ]
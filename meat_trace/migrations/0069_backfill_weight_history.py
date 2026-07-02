from django.db import migrations


def backfill_weight_history(apps, schema_editor):
    Animal = apps.get_model('meat_trace', 'Animal')
    AnimalWeightRecord = apps.get_model('meat_trace', 'AnimalWeightRecord')
    records = [
        AnimalWeightRecord(
            animal=animal,
            weight=animal.live_weight,
            recorded_at=animal.created_at,
            note='Backfilled from registration weight',
        )
        for animal in Animal.objects.filter(live_weight__isnull=False)
        if not AnimalWeightRecord.objects.filter(animal=animal).exists()
    ]
    AnimalWeightRecord.objects.bulk_create(records)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('meat_trace', '0068_animalweightrecord'),
    ]

    operations = [
        migrations.RunPython(backfill_weight_history, noop),
    ]

from decimal import Decimal
from ..models import SlaughterPart, Animal, CarcassMeasurement

def create_slaughter_parts_from_measurement(animal: Animal, measurement: CarcassMeasurement):
    """
    Creates SlaughterPart records from a CarcassMeasurement object, but only if the
    carcass type is 'split'.

    Args:
        animal (Animal): The animal instance.
        measurement (CarcassMeasurement): The carcass measurement instance.
    """
    if measurement.carcass_type != 'split':
        print(f"Animal {animal.id} is not a split carcass. No parts will be created.")
        return

    # Delete existing parts to ensure a clean slate, in case this is a re-run
    SlaughterPart.objects.filter(animal=animal).delete()
    print(f"Deleted existing slaughter parts for Animal {animal.id} to ensure a clean slate.")

    parts_to_create = []
    
    # Map of measurement fields to SlaughterPart part_type
    # Must match PART_CHOICES in models.py: whole_carcass, left_side, right_side, head, feet, internal_organs, torso, front_legs, hind_legs, other
    measurement_to_part_map = {
        'head': 'head',
        'feet': 'feet',
        'left_carcass': 'left_carcass',
        'right_carcass': 'right_carcass',
    }
    
    # Standard parts from fixed fields
    for field, part_type in measurement_to_part_map.items():
        if hasattr(measurement, field) and getattr(measurement, field) is not None:
            weight = getattr(measurement, field)
            if weight > 0:
                parts_to_create.append(SlaughterPart(
                    animal=animal,
                    part_type=part_type,
                    weight=weight,
                    weight_unit='kg' # Defaulting to kg as per model definition
                ))
    
    # Custom parts from the JSONField
    if isinstance(measurement.measurements, dict):
        for part_name, data in measurement.measurements.items():
            # Avoid re-creating standard parts if they are also in the JSON
            if part_name in measurement_to_part_map.values():
                continue

            if isinstance(data, dict) and 'value' in data and 'unit' in data:
                try:
                    weight = Decimal(str(data['value']))
                    if weight > 0:
                        parts_to_create.append(SlaughterPart(
                            animal=animal,
                            part_type=part_name.lower().replace(" ", "_"),
                            weight=weight,
                            weight_unit=data.get('unit', 'kg')
                        ))
                except (ValueError, TypeError):
                    print(f"Could not parse weight for custom part '{part_name}' for animal {animal.id}")

    if parts_to_create:
        SlaughterPart.objects.bulk_create(parts_to_create)
        print(f"Created {len(parts_to_create)} slaughter parts for Animal {animal.id}.")

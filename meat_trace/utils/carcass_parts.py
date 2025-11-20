from decimal import Decimal
import uuid
from ..models import SlaughterPart, Animal, CarcassMeasurement

def create_slaughter_parts_from_measurement(animal: Animal, measurement: CarcassMeasurement):
    """
    Creates SlaughterPart records from a CarcassMeasurement object, but only if the
    carcass type is 'split'.

    Args:
        animal (Animal): The animal instance.
        measurement (CarcassMeasurement): The carcass measurement instance.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[CARCASS_PARTS] Creating slaughter parts for animal {animal.animal_id}")
    logger.info(f"[CARCASS_PARTS] Carcass type: {measurement.carcass_type}")
    
    if measurement.carcass_type != 'split':
        logger.info(f"[CARCASS_PARTS] Animal {animal.id} is not a split carcass. No parts will be created.")
        return

    # Delete existing parts to ensure a clean slate
    deleted_count = SlaughterPart.objects.filter(animal=animal).delete()[0]
    logger.info(f"[CARCASS_PARTS] Deleted {deleted_count} existing slaughter parts for Animal {animal.id}")

    parts_to_create = []
    
    # Map measurement field names to SlaughterPart part_type choices
    field_to_part_type_map = {
        'head_weight': 'head',
        'feet_weight': 'feet',
        'left_carcass_weight': 'left_carcass',
        'right_carcass_weight': 'right_carcass',
        'organs_weight': 'internal_organs',
    }
    
    # FIX: Get measurements from the measurements JSON field, not direct attributes
    measurements_data = measurement.measurements if hasattr(measurement, 'measurements') else {}
    logger.info(f"[CARCASS_PARTS] Measurements data: {measurements_data}")
    
    # Create parts from measurements JSON field
    for field_name, part_type in field_to_part_type_map.items():
        # Check if this measurement exists in the measurements JSON
        if field_name in measurements_data:
            measurement_entry = measurements_data[field_name]
            # Extract weight value from the nested dict structure
            weight = measurement_entry.get('value') if isinstance(measurement_entry, dict) else measurement_entry
            weight_unit = measurement_entry.get('unit', 'kg') if isinstance(measurement_entry, dict) else 'kg'
            
            if weight is not None and float(weight) > 0:
                part_id = f"PART_{uuid.uuid4().hex[:12].upper()}"
                logger.info(f"[CARCASS_PARTS] Creating part: {part_type} with weight {weight}{weight_unit} (part_id: {part_id})")
                parts_to_create.append(SlaughterPart(
                    part_id=part_id,
                    animal=animal,
                    part_type=part_type,
                    weight=Decimal(str(weight)),
                    weight_unit=weight_unit,
                    remaining_weight=Decimal(str(weight))  # Initialize remaining weight
                ))

    if parts_to_create:
        SlaughterPart.objects.bulk_create(parts_to_create)
        logger.info(f"[CARCASS_PARTS] Created {len(parts_to_create)} slaughter parts for Animal {animal.id}")
    else:
        logger.info(f"[CARCASS_PARTS] No parts to create for Animal {animal.id}")

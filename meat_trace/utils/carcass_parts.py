from decimal import Decimal
import uuid
from ..models import SlaughterPart, Animal, CarcassMeasurement

# Maps a measurement field name to the SlaughterPart part_type it becomes.
# 'whole' only ever produces head/feet/whole_carcass; 'split' produces
# head/feet/left/right/organs. Both are handled here (rather than only
# 'split', as before) so a 'whole' carcass's head/feet weights get the same
# per-part remaining_weight tracking — and therefore the same fraud
# protection when a product is later created from them — as a 'split' one.
FIELD_TO_PART_TYPE_BY_CARCASS_TYPE = {
    'whole': {
        'head_weight': 'head',
        'feet_weight': 'feet',
        'whole_carcass_weight': 'whole_carcass',
    },
    'split': {
        'head_weight': 'head',
        'feet_weight': 'feet',
        'left_carcass_weight': 'left_carcass',
        'right_carcass_weight': 'right_carcass',
        'organs_weight': 'internal_organs',
    },
}


def create_slaughter_parts_from_measurement(animal: Animal, measurement: CarcassMeasurement):
    """
    Creates SlaughterPart records from a CarcassMeasurement — one per part
    actually weighed, for either carcass type.

    Once parts exist, the Animal's own remaining_weight is zeroed so it's no
    longer separately available for product creation: the SlaughterParts are
    now the sole authoritative pool for what's left of this carcass. Without
    this, the same physical meat could be claimed once against the Animal
    record and again against its parts.

    Args:
        animal (Animal): The animal instance.
        measurement (CarcassMeasurement): The carcass measurement instance.
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"[CARCASS_PARTS] Creating slaughter parts for animal {animal.animal_id}")
    logger.info(f"[CARCASS_PARTS] Carcass type: {measurement.carcass_type}")

    field_to_part_type_map = FIELD_TO_PART_TYPE_BY_CARCASS_TYPE.get(measurement.carcass_type)
    if field_to_part_type_map is None:
        logger.warning(f"[CARCASS_PARTS] Unknown carcass_type '{measurement.carcass_type}' for animal {animal.id}. No parts will be created.")
        return

    # Delete existing parts to ensure a clean slate (covers re-recording and
    # switching carcass type between whole/split).
    deleted_count = SlaughterPart.objects.filter(animal=animal).delete()[0]
    logger.info(f"[CARCASS_PARTS] Deleted {deleted_count} existing slaughter parts for Animal {animal.id}")

    parts_to_create = []

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

        # The parts are now the authoritative remaining-weight pool for this
        # carcass — zero the animal's own so it can't also be picked
        # directly for product creation (double-booking the same meat).
        if animal.remaining_weight != Decimal('0'):
            animal.remaining_weight = Decimal('0')
            animal.save(update_fields=['remaining_weight'])
            logger.info(f"[CARCASS_PARTS] Zeroed remaining_weight on Animal {animal.id} now that its parts carry it")
    else:
        logger.info(f"[CARCASS_PARTS] No parts to create for Animal {animal.id}")

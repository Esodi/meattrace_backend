import logging
from django.utils import timezone
from ..models import Animal, Product, CarcassMeasurement

logger = logging.getLogger(__name__)

def get_product_timeline(product):
    """
    Build a comprehensive traceability timeline for a product.
    Refactored from views.py for reusability.
    """
    timeline = []
    
    # 1. Animal Registration (Farmer Stage)
    if product.animal:
        animal = product.animal
        
        # Get abbatoir contact info
        farmer_details = {
            'Animal ID': animal.animal_id,
            'Animal Name': animal.animal_name or 'Not named',
            'Species': animal.get_species_display(),
            'Gender': animal.get_gender_display() if hasattr(animal, 'gender') else 'Unknown',
            'Age': f'{animal.age} months' if animal.age else 'Not recorded',
            'Live Weight': f'{animal.live_weight} kg' if animal.live_weight else 'Not recorded',
            'Health Status': animal.health_status or 'Not recorded',
            'Breed': animal.breed or 'Not specified',
            'Abbatoir Name': animal.abbatoir.get_full_name() if animal.abbatoir.first_name else animal.abbatoir.username,
            'Abbatoir Email': animal.abbatoir.email or 'Not provided',
            'Notes': animal.notes or 'None'
        }
        
        # Add abbatoir phone if available
        if hasattr(animal.abbatoir, 'profile') and hasattr(animal.abbatoir.profile, 'phone'):
            farmer_details['Abbatoir Phone'] = animal.abbatoir.profile.phone or 'Not provided'
        elif hasattr(animal.abbatoir, 'phone_number'):
            farmer_details['Abbatoir Phone'] = animal.abbatoir.phone_number or 'Not provided'
        
        timeline.append({
            'stage': 'Animal Registration',
            'category': 'abbatoir',
            'timestamp': animal.created_at,
            'location': f'Abbatoir - {animal.abbatoir.username}',
            'actor': animal.abbatoir.get_full_name() if animal.abbatoir.first_name else animal.abbatoir.username,
            'action': f'Animal {animal.animal_id} registered at farm',
            'icon': 'fa-clipboard-list',
            'details': farmer_details
        })
        
        # 2. Animal Transfer to Processing Unit
        if animal.transferred_at and animal.transferred_to:
            transfer_details = {
                'From': f'Abbatoir - {animal.abbatoir.get_full_name() if animal.abbatoir.first_name else animal.abbatoir.username}',
                'To': animal.transferred_to.name,
                'Transfer Date': animal.transferred_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Transfer Mode': 'Live Animal Transport',
                'Animal ID': animal.animal_id,
                'Animal Species': animal.get_species_display(),
                'Live Weight': f'{animal.live_weight} kg' if animal.live_weight else 'Not recorded',
                'Health Status': animal.health_status or 'Not recorded',
                'Processing Unit': animal.transferred_to.name,
                'Processing Unit Location': animal.transferred_to.location if hasattr(animal.transferred_to, 'location') else 'Not specified'
            }
            
            timeline.append({
                'stage': 'Animal Transfer to Processing',
                'category': 'logistics',
                'timestamp': animal.transferred_at,
                'location': animal.transferred_to.name,
                'actor': animal.abbatoir.get_full_name() if animal.abbatoir.first_name else animal.abbatoir.username,
                'action': f'Live animal transported to {animal.transferred_to.name}',
                'icon': 'fa-truck',
                'details': transfer_details
            })
        
        # 3. Animal Reception at Processing Unit
        if animal.received_at and animal.received_by:
            reception_details = {
                'Received By': animal.received_by.get_full_name() if animal.received_by.first_name else animal.received_by.username,
                'Reception Date': animal.received_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Processing Unit': animal.transferred_to.name if animal.transferred_to else 'Unknown',
                'Animal ID': animal.animal_id,
                'Species': animal.get_species_display(),
                'Reception Status': 'Accepted for processing',
                'Health Inspection': animal.health_status or 'Passed',
            }
            
            if hasattr(animal.received_by, 'email'):
                reception_details['Inspector Email'] = animal.received_by.email or 'Not provided'
            
            timeline.append({
                'stage': 'Animal Reception & Inspection',
                'category': 'processing',
                'timestamp': animal.received_at,
                'location': animal.transferred_to.name if animal.transferred_to else 'Processing Unit',
                'actor': animal.received_by.get_full_name() if animal.received_by.first_name else animal.received_by.username,
                'action': f'Animal received, inspected and approved for processing',
                'icon': 'fa-check-circle',
                'details': reception_details
            })
        
        # 4. Slaughter Event
        if animal.slaughtered and animal.slaughtered_at:
            slaughter_details = {
                'Animal ID': animal.animal_id,
                'Species': animal.get_species_display(),
                'Slaughter Date': animal.slaughtered_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Processing Unit': animal.transferred_to.name if animal.transferred_to else 'Unknown',
                'Abbatoir': animal.abbatoir_name or 'Not specified',
                'Pre-Slaughter Weight': f'{animal.live_weight} kg' if animal.live_weight else 'Not recorded',
            }
            
            # Add carcass measurement if available
            try:
                if hasattr(animal, 'carcass_measurement') and animal.carcass_measurement:
                    cm = animal.carcass_measurement
                    slaughter_details['Carcass Weight'] = f'{cm.carcass_weight} kg' if hasattr(cm, 'carcass_weight') and cm.carcass_weight else 'Not recorded'
                    slaughter_details['Dressing Percentage'] = f'{(cm.carcass_weight / animal.live_weight * 100):.1f}%' if animal.live_weight and hasattr(cm, 'carcass_weight') and cm.carcass_weight else 'Not calculated'
            except Exception:
                pass
            
            timeline.append({
                'stage': 'Slaughter',
                'category': 'processing',
                'timestamp': animal.slaughtered_at,
                'location': animal.transferred_to.name if animal.transferred_to else 'Processing Unit',
                'actor': 'Processing Unit Slaughter Team',
                'action': f'Animal {animal.animal_id} ({animal.get_species_display()}) slaughtered',
                'icon': 'fa-cut',
                'details': slaughter_details
            })
            
            # 5. Carcass Breakdown - Detailed Part Tracking
            if animal.slaughter_parts.exists():
                parts = animal.slaughter_parts.all()
                total_parts_weight = sum([p.weight for p in parts if p.weight])
                
                parts_breakdown = {
                    'Total Parts Created': parts.count(),
                    'Total Parts Weight': f'{total_parts_weight} kg',
                    'Breakdown Date': animal.slaughtered_at.strftime('%Y-%m-%d %H:%M:%S'),
                }
                
                for idx, part in enumerate(parts, 1):
                    part_key = f'Part {idx}'
                    part_value = f'{part.get_part_type_display()} - {part.weight} kg'
                    
                    if hasattr(part, 'transferred_to') and part.transferred_to:
                        part_value += f' \u2192 {part.transferred_to.name}'
                    elif hasattr(part, 'processing_unit') and part.processing_unit:
                        part_value += f' (at {part.processing_unit.name})'
                    
                    parts_breakdown[part_key] = part_value
                
                timeline.append({
                    'stage': 'Carcass Breakdown & Distribution',
                    'category': 'processing',
                    'timestamp': animal.slaughtered_at,
                    'location': animal.transferred_to.name if animal.transferred_to else 'Processing Unit',
                    'actor': 'Butchery Team',
                    'action': f'Carcass divided into {parts.count()} parts',
                    'icon': 'fa-th-large',
                    'details': parts_breakdown
                })
    
    # 6. Product Creation
    creation_details = {
        'Product Name': product.name,
        'Batch Number': product.batch_number,
        'Product Type': product.get_product_type_display(),
        'Weight': f'{product.weight} {product.weight_unit}' if product.weight else 'Not recorded',
        'Category': product.category.name if product.category else 'Not categorized',
        'Processing Unit': product.processing_unit.name if product.processing_unit else 'Unknown',
        'Creation Date': product.created_at.strftime('%Y-%m-%d %H:%M:%S'),
    }
    
    if product.animal:
        creation_details['Source Animal'] = product.animal.animal_id
        creation_details['Animal Species'] = product.animal.get_species_display()
    
    if product.slaughter_part:
        creation_details['Carcass Part'] = product.slaughter_part.get_part_type_display()
    
    if product.ingredients.exists():
        ingredients_list = []
        for ing in product.ingredients.all():
            if ing.slaughter_part:
                ingredients_list.append(f'{ing.slaughter_part.get_part_type_display()} ({ing.quantity_used} {ing.quantity_unit})')
        if ingredients_list:
            creation_details['Ingredients'] = ', '.join(ingredients_list)
    
    timeline.append({
        'stage': 'Product Creation',
        'category': 'processing',
        'timestamp': product.created_at,
        'location': product.processing_unit.name if product.processing_unit else 'Processing Unit',
        'actor': 'Production Team',
        'action': f'Product "{product.name}" manufactured',
        'icon': 'fa-box',
        'details': creation_details
    })
    
    # 7. Product Transfer to Shop
    if product.transferred_at and product.transferred_to:
        transfer_details = {
            'From': product.processing_unit.name if product.processing_unit else 'Processing Unit',
            'To': product.transferred_to.name,
            'Transfer Date': product.transferred_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Product': product.name,
            'Batch Number': product.batch_number,
            'Weight': f'{product.weight} {product.weight_unit}',
        }
        
        timeline.append({
            'stage': 'Product Dispatch',
            'category': 'logistics',
            'timestamp': product.transferred_at,
            'location': product.transferred_to.name,
            'actor': product.processing_unit.name if product.processing_unit else 'Processing Unit',
            'action': f'Product dispatched to {product.transferred_to.name}',
            'icon': 'fa-truck-loading',
            'details': transfer_details
        })
    
    # 8. Product Reception at Shop
    if product.received_at and product.received_by_shop:
        reception_details = {
            'Shop Name': product.received_by_shop.name,
            'Reception Date': product.received_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Batch Number': product.batch_number,
            'Status': 'Accepted and Stocked',
        }
        
        timeline.append({
            'stage': 'Reception at Shop',
            'category': 'shop',
            'timestamp': product.received_at,
            'location': product.received_by_shop.name,
            'actor': product.received_by_shop.name,
            'action': f'Product received and stocked',
            'icon': 'fa-store',
            'details': reception_details
        })

    # Sort timeline chronologically
    timeline.sort(key=lambda x: x['timestamp'])
    return timeline

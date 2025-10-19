import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meattrace_backend.settings')
django.setup()

from meat_trace.models import User, ProcessingUnitUser, ProcessingUnit, Animal
from django.utils import timezone

print("="*80)
print("FIXING USER 'nedp'")
print("="*80)

# Get user nedp
try:
    u = User.objects.get(username='nedp')
    print(f"\n✓ Found user: {u.username} (ID: {u.id})")
    print(f"  Profile role: {u.profile.role}")
    print(f"  Profile processing_unit: {u.profile.processing_unit}")
    
    # Check memberships
    memberships = ProcessingUnitUser.objects.filter(user=u)
    print(f"\n  Total memberships: {memberships.count()}")
    for m in memberships:
        print(f"    - PU: {m.processing_unit.name} (ID: {m.processing_unit.id}), Active: {m.is_active}")
    
    # Check all processing units
    print("\n  All Processing Units:")
    pus = ProcessingUnit.objects.all()
    for pu in pus:
        print(f"    - ID: {pu.id}, Name: {pu.name}")
    
    # Check transferred animals
    print("\n  Transferred Animals:")
    animals = Animal.objects.filter(transferred_to__isnull=False)
    for a in animals[:5]:
        print(f"    - Animal {a.animal_id} -> PU {a.transferred_to.id} ({a.transferred_to.name})")
    
    # Now fix the user
    print("\n" + "="*80)
    print("APPLYING FIX")
    print("="*80)
    
    if not u.profile.processing_unit:
        # Check if user has any active memberships
        active_membership = ProcessingUnitUser.objects.filter(user=u, is_active=True).first()
        
        if active_membership:
            print(f"\n✓ Found active membership in: {active_membership.processing_unit.name}")
            u.profile.processing_unit = active_membership.processing_unit
            u.profile.save()
            print(f"✓ Updated profile.processing_unit to: {u.profile.processing_unit.name}")
        else:
            # No active membership - create one
            print("\n✗ No active membership found")
            
            # Check which processing units have animals transferred to them
            pu_with_animals = ProcessingUnit.objects.filter(
                transferred_animals__isnull=False
            ).distinct()
            
            if pu_with_animals.exists():
                pu = pu_with_animals.first()
                print(f"\n  Creating membership for user in PU: {pu.name} (has transferred animals)")
                
                # Create membership
                membership = ProcessingUnitUser.objects.create(
                    user=u,
                    processing_unit=pu,
                    role='owner',
                    invited_by=u,
                    joined_at=timezone.now(),
                    is_active=True
                )
                
                # Update profile
                u.profile.processing_unit = pu
                u.profile.save()
                
                print(f"✓ Created membership ID: {membership.id}")
                print(f"✓ Updated profile.processing_unit to: {pu.name}")
            else:
                # Check all processing units and pick first one
                first_pu = ProcessingUnit.objects.first()
                if first_pu:
                    print(f"\n  Creating membership for user in first PU: {first_pu.name}")
                    
                    membership = ProcessingUnitUser.objects.create(
                        user=u,
                        processing_unit=first_pu,
                        role='owner',
                        invited_by=u,
                        joined_at=timezone.now(),
                        is_active=True
                    )
                    
                    u.profile.processing_unit = first_pu
                    u.profile.save()
                    
                    print(f"✓ Created membership ID: {membership.id}")
                    print(f"✓ Updated profile.processing_unit to: {first_pu.name}")
                else:
                    print("\n✗ No processing units available!")
    else:
        print(f"\n✓ User already has processing_unit set: {u.profile.processing_unit.name}")
    
    # Verify the fix
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    u.refresh_from_db()
    print(f"\nUser: {u.username}")
    print(f"Profile processing_unit: {u.profile.processing_unit}")
    
    if u.profile.processing_unit:
        animals = Animal.objects.filter(transferred_to=u.profile.processing_unit)
        print(f"Transferred animals to this PU: {animals.count()}")
        for a in animals[:3]:
            print(f"  - {a.animal_id}")

except User.DoesNotExist:
    print("\n✗ User 'nedp' not found!")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

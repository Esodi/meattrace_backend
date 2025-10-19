from meat_trace.models import User, ProcessingUnitUser, ProcessingUnit, Animal, UserProfile

print("=" * 80)
print("DEBUGGING RECEIVE ANIMALS SCREEN ISSUE FOR USER 'nedpt'")
print("=" * 80)

# Check user 'nedpt'
try:
    user = User.objects.get(username='nedpt')
    print(f"\n✓ Found user: {user.username} (ID: {user.id})")
    
    # Check user profile
    try:
        profile = UserProfile.objects.get(user=user)
        print(f"\n  USER PROFILE:")
        print(f"    - Role: {profile.role}")
        print(f"    - Processing Unit: {profile.processing_unit}")
        if profile.processing_unit:
            print(f"    - Processing Unit ID: {profile.processing_unit.id}")
            print(f"    - Processing Unit Name: {profile.processing_unit.name}")
    except UserProfile.DoesNotExist:
        print("  ✗ NO UserProfile found!")
    
    # Check memberships
    memberships = ProcessingUnitUser.objects.filter(user=user)
    print(f"\n  PROCESSING UNIT MEMBERSHIPS:")
    print(f"    Total: {memberships.count()}")
    for m in memberships:
        print(f"\n    Membership #{m.id}:")
        print(f"      - PU Name: {m.processing_unit.name}")
        print(f"      - PU ID: {m.processing_unit.id}")
        print(f"      - Role: {m.role}")
        print(f"      - Is Active: {m.is_active}")
        print(f"      - Joined At: {m.joined_at}")
        
        # Check transferred animals for each processing unit
        pu = m.processing_unit
        animals_for_pu = Animal.objects.filter(transferred_to=pu)
        print(f"      - Animals transferred to this PU: {animals_for_pu.count()}")
        
        if animals_for_pu.exists():
            for animal in animals_for_pu[:3]:  # Show first 3
                print(f"          • Animal: {animal.animal_id}")
                print(f"            Farmer: {animal.farmer.username}")
                print(f"            Transferred at: {animal.transferred_at}")
    
    # Simulate the API query
    print("\n" + "=" * 80)
    print("SIMULATING API QUERY FROM views.py transferred_animals()")
    print("=" * 80)
    
    if hasattr(user, 'profile'):
        print(f"\n✓ User has profile")
        print(f"  - Profile role: {user.profile.role}")
        print(f"  - Profile processing_unit: {user.profile.processing_unit}")
        
        if user.profile.processing_unit:
            pu = user.profile.processing_unit
            print(f"\n  Query: Animal.objects.filter(transferred_to={pu.id}, transferred_to__isnull=False)")
            
            # This is the exact query from views.py line 1351-1354
            animals = Animal.objects.filter(
                transferred_to=pu,
                transferred_to__isnull=False
            ).select_related('farmer', 'transferred_to')
            
            print(f"  RESULT: {animals.count()} animals")
            if animals.exists():
                print("\n  Animals found:")
                for animal in animals:
                    print(f"    • {animal.animal_id} (ID: {animal.id})")
                    print(f"      Farmer: {animal.farmer.username}")
                    print(f"      Transferred at: {animal.transferred_at}")
            else:
                print("\n  ✗ NO ANIMALS FOUND WITH THIS QUERY")
                print("\n  DIAGNOSTIC - Checking all transferred animals:")
                all_transferred = Animal.objects.filter(transferred_to__isnull=False)
                print(f"    Total transferred animals in system: {all_transferred.count()}")
                for a in all_transferred[:5]:
                    print(f"      • {a.animal_id}: transferred_to PU {a.transferred_to.id} ({a.transferred_to.name})")
                
        else:
            print("\n  ✗ PROBLEM FOUND: user.profile.processing_unit is None!")
            print("  Even though ProcessingUnitUser memberships exist.")
            print("\n  FIX: Need to set user.profile.processing_unit")
            
            # Suggest fix
            active_membership = ProcessingUnitUser.objects.filter(user=user, is_active=True).first()
            if active_membership:
                print(f"\n  Suggested fix: Set profile.processing_unit to {active_membership.processing_unit.name}")
    else:
        print("\n✗ User has NO profile!")

except User.DoesNotExist:
    print("\n✗ User 'nedpt' not found!")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

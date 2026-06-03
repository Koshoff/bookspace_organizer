import sys
import traceback

try:
    import db
    print("✓ db се импортира")
    
    snapshot = db.get_inventory_snapshot('2026-05-31')
    print(f"✓ get_inventory_snapshot работи, {len(snapshot)} записа")
    
    dead = db.get_dead_inventory()
    print(f"✓ get_dead_inventory работи, {len(dead)} записа")
    
    if dead:
        print(f"  Първи: {dead[0]}")
    
    print("\nВсички функции за 'Годишно приключване' работят чисто.")
    
except Exception as e:
    print(f"\n✗ ГРЕШКА: {type(e).__name__}: {e}")
    print("\nПълен traceback:")
    traceback.print_exc()
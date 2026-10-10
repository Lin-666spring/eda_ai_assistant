"""诊断脚本: 分析真实 PCB 的缺陷注入失败原因"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.bom.parser import BOMParser
from tests.paper_experiments import generate_defects, apply_defect, _parse_cap_value

pcb_dir = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'pcb_designs')
parser = BOMParser()

for design in sorted(os.listdir(pcb_dir)):
    dpath = os.path.join(pcb_dir, design)
    if not os.path.isdir(dpath): continue
    bom_files = [f for f in os.listdir(dpath) if f.lower().startswith('bom') and f.endswith('.xlsx')]
    if not bom_files: continue
    items = parser.parse(os.path.join(dpath, bom_files[0]))

    print(f"\n{'='*60}")
    print(f"  {design}  ({len(items)} items)")
    print(f"{'='*60}")

    # Collect component info
    refs = []
    for item in items:
        for r in item.reference_list:
            refs.append(r)

    caps = [item for item in items if item.reference.startswith('C')]
    resistors = [item for item in items if item.reference.startswith('R')]
    diodes = [item for item in items if item.reference.startswith('D')]
    crystals = [ref for ref in refs if ref.startswith(('X', 'Y'))]
    ldo_items = [item for item in items if 'AMS1117' in item.value or 'LDO' in item.description or '稳压' in item.description or 'ME6211' in item.value]
    dcdc_items = [item for item in items if 'MP' in item.value or 'DC' in item.description]

    print(f"  Capacitors: {len(caps)}")
    if caps:
        vals = sorted(set(item.value for item in caps), key=_parse_cap_value)
        print(f"    Values: {vals[:10]}")
        print(f"    Descriptions: {sorted(set(item.description for item in caps))[:10]}")

    print(f"  Resistors: {len(resistors)}")
    if resistors:
        print(f"    Values: {sorted(set(item.value for item in resistors))[:10]}")

    print(f"  Diodes: {len(diodes)}")
    if diodes:
        for d in diodes:
            print(f"    {d.reference}: value={d.value}, desc={d.description}, pn={d.part_number}")

    print(f"  Crystals: {crystals}")

    # Generate defects and show which ones are created
    defects = generate_defects(items)
    print(f"  Generated defects: {[d.defect_id for d in defects]}")

    # For each defect, check if apply_defect actually changes the BOM
    for defect in defects:
        mutated = apply_defect(items, defect)
        if len(mutated) == len(items):
            # Check if anything actually changed
            same = True
            for i in range(len(items)):
                if items[i] != mutated[i]:
                    same = False
                    break
            if same:
                print(f"    ⚠️  {defect.defect_id}: apply_defect produced NO CHANGES!")
            else:
                print(f"    ✅ {defect.defect_id}: {len(items)} → {len(mutated)} items (changed)")
        else:
            print(f"    ✅ {defect.defect_id}: {len(items)} → {len(mutated)} items")

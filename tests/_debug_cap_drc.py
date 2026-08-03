"""Quick debug: verify capacitor voltage derating DRC rule on real BOM."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.bom.parser import BOMParser
from src.rules.checker import DesignRuleChecker
from tests.paper_experiments import generate_defects, apply_defect

pcb_dir = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'pcb_designs')
parser = BOMParser()
checker = DesignRuleChecker()

for design in sorted(os.listdir(pcb_dir))[:1]:  # Just test bldc first
    dpath = os.path.join(pcb_dir, design)
    if not os.path.isdir(dpath): continue
    bom_files = [f for f in os.listdir(dpath) if f.lower().startswith('bom') and f.endswith('.xlsx')]
    items = parser.parse(os.path.join(dpath, bom_files[0]))

    defects = generate_defects(items)
    for d in defects:
        if d.defect_id != 'cap_voltage_derating': continue
        mutated = apply_defect(items, d)

        # Check what was injected
        for i, (orig, mut) in enumerate(zip(items, mutated)):
            if orig.value != mut.value:
                print(f"  Value change: {orig.reference}: '{orig.value}' → '{mut.value}'")
            if getattr(orig, 'description', '') != getattr(mut, 'description', ''):
                print(f"  Desc change: {orig.reference}: '{orig.description}' → '{mut.description}'")

        # Run DRC on mutated BOM
        violations = checker.check_all(mutated, None, None)
        target_violations = [v for v in violations if '耐压' in v.rule_name or '电压' in v.rule_name or 'derating' in v.rule_name.lower()]
        print(f"\n  Total violations: {len(violations)}")
        print(f"  Voltage-related violations: {len(target_violations)}")
        for v in target_violations:
            print(f"    {v.rule_name}: {v.description}")

        if not target_violations:
            # Debug: manually trace the rule logic
            print("\n  DEBUG: manually tracing rule logic...")
            max_voltage = 3.3  # default
            for item in mutated:
                ref = item.reference.split(",")[0].strip()
                if not ref.upper().startswith("C"): continue
                val = (item.value or "").strip().upper()
                pn = (item.part_number or "").strip().upper()
                vm = re.search(r'(\d+)V', val + " " + pn)
                if vm:
                    rated_v = float(vm.group(1))
                    print(f"  {ref}: val='{val}' pn='{pn}' → rated={rated_v}V, max={max_voltage}V, "
                          f"need>{max_voltage*1.2:.1f}V → {'FIRE' if rated_v < max_voltage*1.2 else 'PASS'}")
                else:
                    print(f"  {ref}: val='{val}' pn='{pn}' → no voltage match")

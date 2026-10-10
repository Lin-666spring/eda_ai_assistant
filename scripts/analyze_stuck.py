# -*- coding: utf-8 -*-
"""分析 2026-09-08 run 中未收敛闭环用例的逐轮违规详情 — 诊断修正 prompt 缺口"""
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

data = json.load(open('experiment_results/run_2026-09-08_full_glm/results.json', encoding='utf-8'))
recs = data['verify_results']

changed = [r for r in recs if r.get('suggested_changes_count', 0) > 0]
failed = [r for r in changed if not r.get('converged', False)]
converged = [r for r in changed if r.get('converged', False)]
print(f"产生BOM变更: {len(changed)} | 收敛: {len(converged)} | 未收敛: {len(failed)}")
print()

# 逐轮违规统计：哪些规则被反复触发（修正不动）
rule_stuck = {}
for r in failed:
    rr = r.get('raw_report', {}).get('rounds', [])
    for rd in rr:
        for v in rd.get('new_violations_list', []):
            key = (v['rule'], v['severity'])
            rule_stuck[key] = rule_stuck.get(key, 0) + 1

print("未收敛用例中被反复触发的规则 (规则 × 出现轮次):")
for (rule, sev), cnt in sorted(rule_stuck.items(), key=lambda x: -x[1]):
    print(f"  {cnt:3d} × [{sev}] {rule}")
print()

# 每个未收敛用例的逐轮轨迹 + 违规内容
for r in failed:
    print("=" * 78)
    print(f"设计: {r['design']} | 类型: {r['suggestion_category']} | 变更数: {r['suggested_changes_count']}")
    print(f"建议原文: {r['suggestion_text'][:180]}")
    rr = r.get('raw_report', {}).get('rounds', [])
    for rd in rr:
        print(f"  Round {rd['round']}: 变更={rd.get('changes_applied')} 新违规={rd['new_violations']} 评分={rd.get('modified_score')} drop={rd.get('score_drop')}")
        for v in rd.get('new_violations_list', [])[:8]:
            print(f"    - [{v['severity']}] {v['rule']}: {v['desc'][:130]}")

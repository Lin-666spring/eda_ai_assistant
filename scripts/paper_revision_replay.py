# -*- coding: utf-8 -*-
"""论文修订批数据重放：R2/R7/R8/R11/R12/R13/R15/S2 全部口径
输出: 论文/review/revision_metrics.json
"""
import json
import random
import statistics as st
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / 'experiment_results/run_thing_full_glm53/results.json').read_text(encoding='utf-8'))
V = d['verify_results']
out = {}


def rounds_of(r):
    return (r.get('raw_report') or {}).get('rounds') or []


# ── R12 流向表 ──
parse_fail = [r for r in V if r['suggestion_category'] != 'safe'
              and (r['suggested_changes_count'] or 0) == 0 and not r['fully_reverted']]
out['parse_fail_n'] = len(parse_fail)
out['parse_fail_status'] = dict(Counter(r['final_status'] for r in parse_fail))
out['parse_fail_accepted'] = sum(1 for r in parse_fail if r['accepted'])
out['parse_fail_categories'] = dict(Counter(r['suggestion_category'] for r in parse_fail))
safe_zero = [r for r in V if r['suggestion_category'] == 'safe']
proposed = [r for r in V if (r['suggested_changes_count'] or 0) > 0]
rev = [r for r in proposed if r['fully_reverted']]
applied = [r for r in V if isinstance(r['applied_changes'], list) and len(r['applied_changes']) > 0]
nonconv = [r for r in V if not r['converged']]
out.update(safe_n=len(safe_zero), proposed_n=len(proposed), reverted_n=len(rev),
           applied_n=len(applied), nonconv_n=len(nonconv),
           flow_sum_check=(len(safe_zero) + len(parse_fail) + len(proposed) == len(V)))

# ── R8 消除率重构 ──
hosts = []
for r in V:
    rr = rounds_of(r)
    if not rr:
        continue
    b1 = rr[0].get('blocking_new', 0)
    if b1 and b1 > 0:
        hosts.append((r, b1))
out['hosts_n'] = len(hosts)
out['hosts_blocking_total'] = sum(b for _, b in hosts)
corr_hosts = [r for r, b in hosts if len(r['applied_changes'] or []) > 0 and r['converged']]
rev_hosts = [r for r, b in hosts if r['fully_reverted']]
nonconv_hosts = [r for r, b in hosts if not r['converged']]
out.update(hosts_corrected=len(corr_hosts), hosts_reverted=len(rev_hosts),
           hosts_nonconv=len(nonconv_hosts))
final_b = [rounds_of(r)[-1].get('blocking_new', 0) for r, _ in hosts]
out['hosts_final_blocking_sum'] = sum(final_b)
out['hosts_final_zero_n'] = sum(1 for x in final_b if x == 0)
out['hosts_ratio_all'] = round(len(hosts) / len(V) * 100, 1)
out['hosts_ratio_proposed'] = round(len(hosts) / len(proposed) * 100, 1)
out['per_round_first'] = dict(Counter(rounds_of(r)[0].get('blocking_new', 0) for r, _ in hosts))

# ── R2 基线臂（重放：首轮直出+单次复检门） ──
base_pass = base_reject = base_block_resid = 0
for r in V:
    rr = rounds_of(r)
    if not rr:
        base_pass += 1
        continue
    nv = rr[0].get('new_violations', 0)
    base_block_resid += rr[0].get('blocking_new', 0)
    if nv == 0:
        base_pass += 1
    else:
        base_reject += 1
out['baseline_arm'] = dict(pass_n=base_pass, reject_n=base_reject,
                           blocking_residual=base_block_resid,
                           accept_rate=round(base_pass / len(V) * 100, 1))
dang = [r for r in V if r['suggestion_category'] == 'dangerous']
dec = Counter()
for r in dang:
    if r['fully_reverted']:
        dec['迭代后全撤销'] += 1
    elif len(r['applied_changes'] or []) > 0:
        dec['修正后落盘'] += 1
    elif (r['suggested_changes_count'] or 0) > 0:
        dec['提出变更但未落盘未撤销'] += 1
    else:
        dec['LLM零变更回应(首轮分析拒绝)'] += 1
out['dangerous_decomposition'] = dict(dec)
out['dangerous_preflight_flagged'] = sum(1 for r in dang if r.get('preflight_flagged'))
out['preflight_probe'] = [dict(flagged=r.get('preflight_flagged'),
                               sugg=r.get('suggested_changes_count'),
                               conv=r.get('converged'), rev=r.get('fully_reverted'))
                          for r in dang[:8]]

# ── R15 ──
conv_proposed = [r for r in proposed if r['converged']]
out['converged_proposed_n'] = len(conv_proposed)
out['correction_convergence_n'] = sum(1 for r in conv_proposed if len(r['applied_changes'] or []) > 0)
out['revert_rate'] = dict(reverted=len(rev), proposed=len(proposed))
dang_applied = [r for r in dang if len(r['applied_changes'] or []) > 0]
out['dangerous_applied_detail'] = [
    dict(design=r['design'], rounds=r['rounds'], n_changes=len(r['applied_changes']),
         sample=[str(c)[:110] for c in (r['applied_changes'] or [])[:3]])
    for r in dang_applied]
chg_types = Counter()
for r in applied:
    for c in (r['applied_changes'] or []):
        if isinstance(c, dict):
            chg_types[str(c.get('action', c.get('type', '?')))] += 1
        else:
            chg_types['raw'] += 1
out['applied_change_types'] = dict(chg_types)
out['applied_change_total'] = sum(chg_types.values())

# ── R11 评分守门 ──
score_gate_only = 0
drops = []
for r in V:
    base_s = r.get('baseline_score')
    for rd in rounds_of(r):
        ms = rd.get('modified_score')
        if ms is None or base_s is None:
            continue
        drop = base_s - ms
        drops.append(round(drop, 1))
        if rd.get('new_violations', 0) == 0 and drop > 2.0:
            score_gate_only += 1
            break
out['score_gate_only_suggestions'] = score_gate_only
out['score_drop_gt2_rounds'] = sum(1 for x in drops if x > 2.0)
out['score_drop_max'] = max(drops) if drops else None

# ── S2 bootstrap CI ──
random.seed(42)
designs = sorted(set(r['design'] for r in V))
by_design = {g: [(r['suggested_changes_count'] or 0) > 0 and r['converged'] for r in V if r['design'] == g]
             for g in designs}


def boot_convergence():
    rates = []
    for _ in range(2000):
        sample = random.choices(designs, k=len(designs))
        prop = conv = 0
        for g in sample:
            for x in by_design[g]:
                prop += 1
                if x:
                    conv += 1
        if prop:
            rates.append(conv / prop)
    rates.sort()
    return round(rates[100] * 100, 1), round(rates[1899] * 100, 1)


out['bootstrap_convergence_ci'] = boot_convergence()
DF = d['defect_results']
dby = {}
for r in DF:
    dby.setdefault(r['design'], []).append(bool(r['detected']))
dn = list(dby)


def boot_detect():
    rates = []
    for _ in range(2000):
        sample = random.choices(dn, k=len(dn))
        t = c = 0
        for g in sample:
            for x in dby[g]:
                t += 1
                if x:
                    c += 1
        rates.append(c / t)
    rates.sort()
    return round(rates[100] * 100, 1), round(rates[1899] * 100, 1)


out['bootstrap_detect_ci'] = boot_detect()

# ── 模型口径 ──
out['models'] = sorted(set(f"{r['provider']}/{r['model']}" for r in V))
out['ma_models'] = sorted(set(f"{r['provider']}/{r['model']}" for r in d['ma_results']))

# ── R13 数据集画像（BOM 规模） ──
import openpyxl
root = ROOT / 'test_data/thing_designs'
sizes = []
for pdir in sorted(root.iterdir()):
    if not pdir.is_dir():
        continue
    xl = sorted(pdir.glob('BOM*.xlsx'))
    if not xl:
        continue
    try:
        wb = openpyxl.load_workbook(xl[0], read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        hdr = None
        for i, row in enumerate(rows[:5]):
            if row and any(c and ('位号' in str(c) or 'Comment' in str(c)) for c in row):
                hdr = i
                break
        cnt = 0
        seen = set()
        ci = None
        if hdr is not None:
            for j, c in enumerate(rows[hdr]):
                if c and '位号' in str(c):
                    ci = j
                    break
        for row in rows[(hdr + 1) if hdr is not None else 1:]:
            if not row or not any(row):
                continue
            key = row[ci] if ci is not None and ci < len(row) else None
            if key and str(key) in seen:
                continue
            if key:
                seen.add(str(key))
            cnt += 1
        sizes.append(cnt)
        wb.close()
    except Exception:
        pass
if sizes:
    out['dataset_bom'] = dict(n=len(sizes), min=min(sizes), median=st.median(sizes),
                              mean=round(st.mean(sizes), 1), max=max(sizes))

(ROOT / '论文/review/revision_metrics.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=1))

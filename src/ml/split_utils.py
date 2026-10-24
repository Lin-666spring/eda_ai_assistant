"""训练/验证切分工具 —— 模板级切分，防泄漏。

2026-10-24（验收 A-9）：模板展开后的样本级随机切分会让同一文本同时落进
train/val（实测 NLU 验证集 81%、元件集 26% 与训练集逐字重复），val_acc
在测记忆而非泛化。正确做法：同一模板的全部展开样本进同一侧，且验证集
与训练集逐字不重叠。
"""

from __future__ import annotations

import random
from collections import defaultdict


def split_by_template(
    items: list[dict], val_split: float = 0.15, label_key: str = "intent"
) -> tuple[list[dict], list[dict]]:
    """按模板分组切分，返回 (train, val)，样本剥离 ``_template`` 内部字段。

    items 的每个样本须带 ``_template``（来源模板原文）与 ``label_key``
    字段。模板数 ≥2 时至少 1 组模板进验证集，保证每类验证侧非空。
    """
    by_template: dict[str, list[dict]] = defaultdict(list)
    for s in items:
        by_template[s["_template"]].append(s)

    templates = list(by_template)
    random.shuffle(templates)

    if len(templates) >= 2:
        n_val = max(1, round(len(templates) * val_split))
    else:
        n_val = 0
    val_templates = set(templates[:n_val])

    train: list[dict] = []
    val: list[dict] = []
    for t in templates:
        target = val if t in val_templates else train
        target.extend(
            {"text": s["text"], label_key: s[label_key]}
            for s in by_template[t]
        )

    # 跨侧逐字去重：不同模板可能填充出相同文本
    train_texts = {s["text"] for s in train}
    seen: set[str] = set()
    deduped_val: list[dict] = []
    for s in val:
        if s["text"] in train_texts or s["text"] in seen:
            continue
        seen.add(s["text"])
        deduped_val.append(s)

    return train, deduped_val

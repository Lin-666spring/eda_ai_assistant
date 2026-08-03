"""
HTML BOM / Verification Map 共享工具函数

从 generator.py 提取，供 ibom.html 和 verification_map.html 共用。
"""

from typing import Optional


def prepare_component_data(
    bom_items: list,
    positions: dict,
) -> list[dict]:
    """将 BOM 数据与坐标数据融合，返回统一组件列表。

    Args:
        bom_items: BOM 物料列表（对象需有 reference/value/package/part_number/description 属性）
        positions: 元件坐标 {"R1": {"x":..., "y":..., "rotation":..., "layer":...}, ...}

    Returns:
        [{"reference":..., "value":..., "package":..., "x":..., "y":..., ...}, ...]
    """
    components = []

    for item in bom_items:
        refs = item.reference.split(",") if hasattr(item, "reference") else []

        for ref in refs:
            ref = ref.strip()
            pos = positions.get(ref, {})

            components.append({
                "reference": ref,
                "value": getattr(item, "value", ""),
                "package": getattr(item, "package", ""),
                "part_number": getattr(item, "part_number", ""),
                "description": getattr(item, "description", ""),
                "x": pos.get("x", 0),
                "y": pos.get("y", 0),
                "rotation": pos.get("rotation", 0),
                "layer": pos.get("layer", "Top"),
                "has_position": bool(pos),
            })

    return components


def calculate_board_stats(positions: dict) -> dict:
    """计算板级统计信息。

    Returns:
        {"total": int, "top_count": int, "bottom_count": int,
         "width_mm": float, "height_mm": float}
    """
    if not positions:
        return {
            "total": 0,
            "top_count": 0,
            "bottom_count": 0,
            "width_mm": 0,
            "height_mm": 0,
        }

    pos_list = list(positions.values())
    x_vals = [p.get("x", 0) for p in pos_list if p]
    y_vals = [p.get("y", 0) for p in pos_list if p]

    return {
        "total": len(pos_list),
        "top_count": sum(1 for p in pos_list if p.get("layer") == "Top"),
        "bottom_count": sum(1 for p in pos_list if p.get("layer") == "Bottom"),
        "width_mm": max(x_vals) - min(x_vals) if x_vals else 0,
        "height_mm": max(y_vals) - min(y_vals) if y_vals else 0,
    }

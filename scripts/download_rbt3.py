"""下载 rbt3 预训练权重（2026-10-14 BERT 批，训练侧一次性步骤）

拉取 hfl/rbt3（3 层中文 RoBERTa-wwm-ext，~38M 参数）到 data/models/rbt3_pretrained/，
供 src/ml/train_intent_bert.py 微调。目录已 gitignore —— 大权重不入库，
克隆后重跑本脚本即可（与 data/*.pt 治理先例一致）。

网络策略：先直连 huggingface.co（新加坡 VPN 常开），失败自动切 hf-mirror.com。
huggingface_hub 属传递依赖已随 chromadb 装好；本脚本不 import transformers。

用法:
    python scripts/download_rbt3.py [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REPO_ID = "hfl/rbt3"
TARGET_DIR = PROJECT_ROOT / "data" / "models" / "rbt3_pretrained"
# pytorch_model.bin 与 model.safetensors 二选一（rbt3 仓库目前只有 .bin）
ALLOW_PATTERNS = ["config.json", "vocab.txt", "pytorch_model.bin", "model.safetensors"]

MIRROR_ENDPOINT = "https://hf-mirror.com"


def _already_downloaded() -> bool:
    has_weights = (TARGET_DIR / "model.safetensors").exists() or (
        TARGET_DIR / "pytorch_model.bin"
    ).exists()
    return has_weights and (TARGET_DIR / "config.json").exists() and (
        TARGET_DIR / "vocab.txt"
    ).exists()


def _download(endpoint: str | None) -> None:
    from huggingface_hub import snapshot_download

    kwargs = {}
    if endpoint:
        kwargs["endpoint"] = endpoint
    snapshot_download(
        repo_id=REPO_ID,
        local_dir=str(TARGET_DIR),
        allow_patterns=ALLOW_PATTERNS,
        **kwargs,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="已下载也重新拉取")
    args = parser.parse_args()

    if _already_downloaded() and not args.force:
        print(f"已存在，跳过下载：{TARGET_DIR}")
        print("如需重新拉取加 --force")
        return 0

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/2] 直连 huggingface.co 拉取 {REPO_ID} ...")
    try:
        _download(None)
    except Exception as e:
        print(f"  直连失败：{type(e).__name__}: {e}")
        print(f"[2/2] 切镜像 {MIRROR_ENDPOINT} 重试 ...")
        try:
            _download(MIRROR_ENDPOINT)
        except Exception as e2:
            print(f"  镜像也失败：{type(e2).__name__}: {e2}")
            print("请检查网络（VPN 是否开启）后重跑本脚本。")
            return 1

    if not _already_downloaded():
        print("下载结束但关键文件缺失（config/vocab/权重），请重跑 --force。")
        return 1

    total_mb = sum(f.stat().st_size for f in TARGET_DIR.rglob("*") if f.is_file()) / 1e6
    print(f"完成：{TARGET_DIR}（{total_mb:.0f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

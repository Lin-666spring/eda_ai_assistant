"""NLU 意图分类 BERT 运行时 — rbt3 ONNX (int8) + tokenizers

2026-10-14 BERT 批：意图底座由字符级 TextCNN 换为 hfl/rbt3 微调模型。
训练/导出侧见 src/ml/train_intent_bert.py（transformers+torch，dev 依赖）；
本模块是运行时唯一入口，只依赖 onnxruntime + tokenizers（requirements.txt
显式声明，exe 随包），torch/transformers 不进运行时。

对外契约与 IntentPredictor（TextCNN）完全一致，NLUEngine 可互换：
    predictor = BertIntentPredictor.from_path("data/models/intent_bert")
    intent, confidence, debug = predictor.classify("检查电源走线")
    # → ("RULE_CHECK", 0.93, {"scores": {...}, "top_two": [...],
    #                         "model": "local_bert_onnx"})

产物目录 data/models/intent_bert/：
    model.onnx          int8 推理图（缺失时 from_path 返回 None → 引擎降级）
    vocab.txt           WordPiece 词表
    intent_config.json  标签序/温度/max_len/tokenizer 规格

温度校准：intent_config.json 的 temperature 在 softmax 前除入 logits
（Temperature Scaling，训练侧验证集 LBFGS 学得）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_TAG = "local_bert_onnx"

# 训练侧 BertTextEncoder 同款规格的缺省值；实际以 intent_config.json 为准
_DEFAULT_MAX_LEN = 32


class BertIntentPredictor:
    """rbt3 ONNX 意图分类推理封装（与 IntentPredictor 契约对齐）"""

    def __init__(self, session, tokenizer, labels: list[str],
                 temperature: float, max_len: int):
        self.session = session
        self.tokenizer = tokenizer
        self.labels = labels
        self.temperature = temperature
        self.max_len = max_len
        self.input_names = {i.name for i in session.get_inputs()}

    # ── 加载 ──

    @staticmethod
    def from_path(model_dir: str | Path) -> Optional["BertIntentPredictor"]:
        """从模型目录加载；任何缺失/异常返回 None（引擎降级，勿抛出）。

        目录布局见模块 docstring。onnxruntime / tokenizers 未安装也走 None。
        """
        model_dir = Path(model_dir)
        onnx_path = model_dir / "model.onnx"
        vocab_path = model_dir / "vocab.txt"
        config_path = model_dir / "intent_config.json"
        if not (onnx_path.exists() and vocab_path.exists() and config_path.exists()):
            return None
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            import onnxruntime as ort
            from tokenizers import BertWordPieceTokenizer

            session = ort.InferenceSession(str(onnx_path),
                                           providers=["CPUExecutionProvider"])
            tok_spec = cfg.get("tokenizer", {})
            tokenizer = BertWordPieceTokenizer(
                str(vocab_path), lowercase=bool(tok_spec.get("lowercase", True)),
            )
            max_len = int(cfg.get("max_len", _DEFAULT_MAX_LEN))
            tokenizer.enable_truncation(max_length=max_len)
            tokenizer.enable_padding(length=max_len,
                                     pad_id=int(tok_spec.get("pad_id", 0)),
                                     pad_token=tok_spec.get("pad_token", "[PAD]"))
            predictor = BertIntentPredictor(
                session=session,
                tokenizer=tokenizer,
                labels=list(cfg["labels"]),
                temperature=float(cfg.get("temperature", 1.0)),
                max_len=max_len,
            )
            logger.info(
                "BertIntentPredictor ready: %s, T=%.4f, max_len=%d, quantized=%s",
                model_dir, predictor.temperature, predictor.max_len,
                cfg.get("quantized"),
            )
            return predictor
        except ImportError as e:
            logger.info("BertIntentPredictor unavailable (runtime deps missing?): %s", e)
            return None
        except FileNotFoundError as e:
            logger.warning("BertIntentPredictor file not found: %s", e)
            return None
        except Exception as e:
            logger.error("Failed to load BertIntentPredictor: %s", e)
            return None

    # ── 推理 ──

    def classify(self, text: str) -> tuple[str, float, dict]:
        """分类用户输入，返回 (intent_name, confidence, debug)。

        契约与 IntentPredictor.classify 一致；debug["model"]="local_bert_onnx"。
        """
        if not text or not text.strip():
            return ("TEXT_CHAT", 0.0, {
                "scores": {}, "top_two": [], "reason": "empty_input",
            })

        enc = self.tokenizer.encode(text)
        inputs = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
        }
        if "token_type_ids" in self.input_names:
            inputs["token_type_ids"] = np.array([enc.type_ids], dtype=np.int64)

        logits = self.session.run(["logits"], inputs)[0][0]
        logits = logits / self.temperature

        # softmax（纯 numpy，避免引 torch）
        exp = np.exp(logits - logits.max())
        probs = exp / exp.sum()

        scores = {name: round(float(probs[i]), 4) for i, name in enumerate(self.labels)}
        sorted_items = sorted(scores.items(), key=lambda x: -x[1])
        best_name, confidence = sorted_items[0]
        debug = {
            "scores": scores,
            "top_two": [(name, score) for name, score in sorted_items[:2]],
            "model": MODEL_TAG,
        }
        return best_name, confidence, debug

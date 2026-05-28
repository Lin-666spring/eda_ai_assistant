"""RAG 检索器 — 查询向量化 + 语义检索 + 上下文拼接"""

import logging
from pathlib import Path
from typing import Optional

import chromadb

from .indexer import DEFAULT_PERSIST_DIR

logger = logging.getLogger(__name__)


class RAGRetriever:
    """知识库检索器

    使用方式:
        retriever = RAGRetriever()
        results = retriever.query("0603封装尺寸是多少")
        for r in results:
            print(r["score"], r["content"][:100])
    """

    def __init__(self, persist_dir: Optional[str] = None):
        persist_dir = persist_dir or DEFAULT_PERSIST_DIR
        if not Path(persist_dir).exists():
            raise FileNotFoundError(
                f"RAG 索引目录不存在: {persist_dir}\n请先运行 RAGIndexer 创建索引。"
            )

        self._client = chromadb.PersistentClient(path=persist_dir)
        try:
            self._collection = self._client.get_collection("lceda_knowledge")
        except Exception:
            raise FileNotFoundError(
                f"未找到 lceda_knowledge 集合。请先运行 RAGIndexer 创建索引。"
            )

        self._embedding = None  # lazy init
        logger.info("RAG retriever ready: %d chunks available", self._collection.count())

    def query(self, question: str, top_k: int = 5) -> list[dict]:
        """检索与问题最相关的文档片段

        Returns:
            [{"content": str, "score": float, "title": str, "source": str, "url": str}, ...]
        """
        try:
            from .indexer import _SiliconFlowEmbedding
            if self._embedding is None:
                self._embedding = _SiliconFlowEmbedding()
            query_vector = self._embedding.embed([question])
            results = self._collection.query(
                query_embeddings=query_vector,
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning("Embedding query failed, falling back to keyword: %s", e)
            self._embedding = None  # reset stale instance for retry
            results = self._collection.query(
                query_texts=[question],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

        return self._normalize_results(results)

    def query_with_context(self, question: str, top_k: int = 5) -> str:
        """检索并拼接为 LLM 可用的上下文文本"""
        results = self.query(question, top_k=top_k)

        if not results:
            return "（未找到相关文档）"

        lines = []
        for i, result in enumerate(results, 1):
            lines.append(
                f"【参考 {i}】(来源: {result['title']}, 相关度: {result['score']:.2f})\n"
                f"{result['content']}"
            )
        return "\n\n---\n\n".join(lines)

    def query_and_answer(
        self,
        question: str,
        llm_client=None,
        top_k: int = 5,
    ) -> str:
        """检索 + LLM 回答（端到端 RAG）

        Args:
            question: 用户问题
            llm_client: LLMClient 实例（可选，不传则只返回检索结果）
            top_k: 检索数量
        """
        context = self.query_with_context(question, top_k=top_k)

        if not llm_client:
            return f"## 检索结果\n\n{context}"

        from ..agent.prompt_templates import PromptTemplates

        prompt = PromptTemplates.get("pcb_doc_qa", context=context, question=question)
        system = PromptTemplates.get_system_prompt("pcb")

        try:
            answer = llm_client.chat(prompt, system_prompt=system)
        except Exception as e:
            logger.warning("LLM QA failed: %s", e)
            answer = f"（AI 回答生成失败: {e}）\n\n以下为检索到的参考资料:\n{context}"

        return answer

    @property
    def chunk_count(self) -> int:
        return self._collection.count()

    def _normalize_results(self, raw: dict) -> list[dict]:
        """规范化 chromadb 返回结果"""
        results = []
        if not raw.get("ids") or not raw["ids"][0]:
            return results

        for i, doc_id in enumerate(raw["ids"][0]):
            content = raw["documents"][0][i] if raw.get("documents") else ""
            meta = raw["metadatas"][0][i] if raw.get("metadatas") else {}
            distance = raw["distances"][0][i] if raw.get("distances") else 1.0

            # 距离 → 相似度分数 (cosine distance → [0,1] similarity)
            score = max(0.0, 1.0 - distance) if distance is not None else 0.0

            results.append({
                "id": doc_id,
                "content": content,
                "score": round(score, 4),
                "title": meta.get("title", ""),
                "source": meta.get("source", ""),
                "url": meta.get("url", ""),
            })

        return results

"""RAG 文档索引器 — 文档切片 + 向量化 + 存储

使用 chromadb 做向量存储，硅基流动 API (BGE-M3) 做嵌入。
"""

import logging
import re
from pathlib import Path
from typing import Optional

import chromadb

logger = logging.getLogger(__name__)

# 默认持久化目录
DEFAULT_PERSIST_DIR = str(Path(__file__).parent.parent.parent / "rag_data")


class RAGIndexer:
    """文档索引器

    使用方式:
        indexer = RAGIndexer()
        indexer.index_documents([{"title": "...", "content": "..."}, ...])
        # 或
        indexer.index_file("lceda_manual.md")
    """

    def __init__(self, persist_dir: Optional[str] = None):
        persist_dir = persist_dir or DEFAULT_PERSIST_DIR
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="lceda_knowledge",
            metadata={"description": "立创EDA中文PCB知识库"},
        )
        logger.info("RAG indexer ready: persist=%s", persist_dir)

    def index_documents(self, docs: list[dict]) -> int:
        """索引文档列表

        Args:
            docs: [{"title": str, "content": str, "source": str, "url": str}, ...]

        Returns:
            索引的总 chunk 数
        """
        total = 0
        for doc in docs:
            chunks = self._split_text(
                doc.get("title", ""),
                doc.get("content", ""),
                doc.get("source", ""),
                doc.get("url", ""),
            )
            if chunks:
                self._add_chunks(chunks)
                total += len(chunks)

        logger.info("Indexed %d chunks from %d documents", total, len(docs))
        return total

    def index_file(self, file_path: str, source: str = "") -> int:
        """从文件读取文本并索引

        支持 .txt 和 .md 文件。自动按 ## 标题边界分片。
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning("File not found: %s", file_path)
            return 0

        content = path.read_text(encoding="utf-8")
        title = path.stem
        return self.index_documents([{
            "title": title,
            "content": content,
            "source": source or path.name,
        }])

    def index_text(self, title: str, text: str, source: str = "") -> int:
        """直接索引文本字符串"""
        return self.index_documents([{
            "title": title,
            "content": text,
            "source": source or title,
        }])

    def clear(self):
        """清空所有索引数据"""
        self._client.delete_collection("lceda_knowledge")
        self._collection = self._client.create_collection(
            name="lceda_knowledge",
            metadata={"description": "立创EDA中文PCB知识库"},
        )
        logger.info("RAG index cleared")

    @property
    def chunk_count(self) -> int:
        """当前索引的 chunk 总数"""
        return self._collection.count()

    # ──── 内部分片 ────

    def _split_text(
        self,
        title: str,
        content: str,
        source: str = "",
        url: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> list[dict]:
        """文本分片（无 langchain 依赖）

        优先按 ## 标题边界分割，其次按段落分割，最后按字符长度滑动窗口。
        """
        chunks = []

        # 按二级标题分节
        sections = re.split(r"\n(?=##\s)", content)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # 提取节标题
            header_match = re.match(r"^##\s+(.+)", section)
            section_title = header_match.group(1).strip() if header_match else title

            # 如果节长度合适，直接作为一个 chunk
            if len(section) <= chunk_size:
                chunks.append({
                    "text": section,
                    "title": f"{title} / {section_title}",
                    "source": source,
                    "url": url,
                })
            else:
                # 按段落再分
                paragraphs = section.split("\n\n")
                current = ""
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    if len(current) + len(para) <= chunk_size:
                        current += ("\n\n" if current else "") + para
                    else:
                        if current:
                            chunks.append({
                                "text": current,
                                "title": f"{title} / {section_title}",
                                "source": source,
                                "url": url,
                            })
                        # 滑动窗口重叠
                        overlap_text = current[-chunk_overlap:] if len(current) > chunk_overlap else ""
                        current = overlap_text + para

                if current:
                    chunks.append({
                        "text": current,
                        "title": f"{title} / {section_title}",
                        "source": source,
                        "url": url,
                    })

        return chunks

    def _add_chunks(self, chunks: list[dict]) -> None:
        """将 chunks 写入 chromadb collection"""
        if not chunks:
            return

        ids = [f"chunk_{self._collection.count() + i}" for i in range(len(chunks))]
        texts = [c["text"] for c in chunks]
        metadatas = [
            {"title": c["title"], "source": c.get("source", ""), "url": c.get("url", "")}
            for c in chunks
        ]

        # 优先使用硅基流动 API，失败则回退 chromadb 内置 embedding
        try:
            embedding_fn = _SiliconFlowEmbedding()
            embeddings = embedding_fn.embed(texts)
            self._collection.add(
                ids=ids, embeddings=embeddings,
                documents=texts, metadatas=metadatas,
            )
            return
        except Exception as e:
            logger.warning("SiliconFlow embedding failed, using local: %s", e)

        # chromadb 内置 DefaultEmbeddingFunction (all-MiniLM-L6-v2)
        self._collection.add(
            ids=ids, documents=texts, metadatas=metadatas,
        )


class _SiliconFlowEmbedding:
    """硅基流动 Embedding API (BGE-M3)

    免费额度充足，零本地 GPU 依赖。
    """

    BASE_URL = "https://api.siliconflow.cn/v1/embeddings"
    MODEL = "BAAI/bge-m3"

    def __init__(self, api_key: Optional[str] = None):
        import os
        self._api_key = api_key or os.environ.get(
            "SILICONFLOW_API_KEY",
            os.environ.get("DEEPSEEK_API_KEY", ""),
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量文本 → 向量"""
        import requests

        if not self._api_key:
            raise RuntimeError("未配置 SILICONFLOW_API_KEY")

        resp = requests.post(
            self.BASE_URL,
            json={
                "model": self.MODEL,
                "input": texts,
                "encoding_format": "float",
            },
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

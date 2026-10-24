"""RAG 文档索引器 — 文档切片 + 向量化 + 存储

使用 chromadb 做向量存储，硅基流动 API (BGE-M3) 做嵌入。
"""

import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import chromadb

logger = logging.getLogger(__name__)


def default_persist_dir() -> Path:
    """向量索引落盘目录。

    开发模式锚定仓库 rag_data/；PyInstaller 打包版的项目根是 _MEIPASS
    （onefile 解包临时目录，进程退出即清空），索引必须写到用户数据目录
    app_home()/rag_index，否则每次启动都全量重索引。
    """
    if getattr(sys, "frozen", False):
        from src.constants import app_home

        return app_home() / "rag_index"
    return Path(__file__).parent.parent.parent / "rag_data"


# 默认持久化目录
DEFAULT_PERSIST_DIR = str(default_persist_dir())


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
            成功索引的 chunk 数（嵌入失败的文档跳过并记 error 日志，不计数）

        P1-21（验收 2026-10-24）：每个文档写入成功后清掉同 source 里未被新内容
        覆盖的旧 chunk —— 重索引（内容变更）时旧的 chunk 永不删除会让同一份
        知识的新旧两版同时在库里，检索命中过期内容。顺序是「先记旧 ID → 写新 →
        删差集」：写入失败时旧数据原样保留，且不会误删刚写入的新 chunk。
        """
        total = 0
        for doc in docs:
            source = doc.get("source", "")
            chunks = self._split_text(
                doc.get("title", ""),
                doc.get("content", ""),
                source,
                doc.get("url", ""),
            )
            if not chunks:
                continue
            stale_ids = self._source_chunk_ids(source)
            try:
                new_ids = self._add_chunks(chunks)
            except Exception as e:
                # P1-21（验收 2026-10-24）：嵌入失败的批次响亮失败 —— 跳过该批并
                # 记 error 日志，绝不把回退向量混进 collection（两种向量空间
                # 混存会让检索质量静默劣化，且无法事后清理）。
                logger.error("RAG index batch failed (skipped): source=%s, %d chunks, error=%s",
                             source or "(no source)", len(chunks), e)
                continue
            self._delete_chunks(i for i in stale_ids if i not in set(new_ids))
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

    def index_directory(self, dir_path: str, manifest_path: str = "") -> dict:
        """增量索引目录中的所有 .md 文件

        基于 .index_manifest.json 记录的文件 mtime 实现增量索引：
        — 新文件或 mtime 变更的文件重新索引
        — 未变更文件跳过

        Args:
            dir_path: 包含 .md 文件的目录路径
            manifest_path: manifest 文件路径，默认为 dir_path/.index_manifest.json

        Returns:
            {"indexed": int, "skipped": int, "errors": list}
        """
        dir_path = str(dir_path)
        if manifest_path:
            manifest_path = str(manifest_path)
        else:
            manifest_path = os.path.join(dir_path, ".index_manifest.json")

        # 加载已有 manifest
        manifest: dict[str, float] = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, OSError):
                logger.warning("Manifest corrupted, rebuilding from scratch")
                manifest = {}

        # 扫描 .md 文件（跳过以 . 开头的文件和 ChromaDB 内部文件）
        md_files: list[Path] = []
        for entry in os.scandir(dir_path):
            if entry.is_file() and entry.name.endswith(".md"):
                md_files.append(Path(entry.path))

        stats: dict[str, any] = {"indexed": 0, "skipped": 0, "errors": []}

        for file_path in sorted(md_files):
            file_key = file_path.name
            current_mtime = file_path.stat().st_mtime

            # 检查是否需要重新索引
            if file_key in manifest and abs(manifest[file_key] - current_mtime) < 1.0:
                stats["skipped"] += 1
                logger.debug("RAG index skip (unchanged): %s", file_key)
                continue

            try:
                indexed = self.index_file(str(file_path), source=file_key)
                manifest[file_key] = current_mtime
                stats["indexed"] += 1
                logger.info("RAG indexed: %s (%d chunks)", file_key, indexed)
            except Exception as e:
                stats["errors"].append({"file": file_key, "error": str(e)})
                logger.exception("RAG index error: %s", file_key)

        # 清理已删除文件的 manifest 条目
        existing_names = {f.name for f in md_files}
        stale_keys = [k for k in manifest if k not in existing_names]
        for k in stale_keys:
            del manifest[k]
            logger.debug("RAG manifest removed stale entry: %s", k)

        # 写回 manifest
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        except OSError as e:
            logger.warning("Failed to write manifest: %s", e)

        logger.info(
            "RAG index_directory complete: %d indexed, %d skipped, %d errors, %d total chunks",
            stats["indexed"], stats["skipped"], len(stats["errors"]), self._collection.count(),
        )
        return stats

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

    def _add_chunks(self, chunks: list[dict]) -> list[str]:
        """将 chunks 写入 chromadb collection，返回写入的 chunk ID 列表。

        P1-21（验收 2026-10-24）：
        - ID 改为内容寻址（source + text 哈希）：旧的 chunk_{count+i} 依赖
          「写入瞬间」的行数，跨进程并发写和重索引删旧 chunk 后必然撞号/
          错位；哈希 ID 让同一份内容重索引时幂等（upsert 覆盖自身）。
        - 嵌入失败不再回退 chromadb 内置 MiniLM 向量 —— 同一 collection 混
          两种向量空间后检索质量静默劣化，这里直接把异常抛给调用方
          （index_documents 记 error 并跳过该批）。
        """
        if not chunks:
            return []

        texts = [c["text"] for c in chunks]
        ids = [self._chunk_id(c) for c in chunks]
        metadatas = [
            {"title": c["title"], "source": c.get("source", ""), "url": c.get("url", "")}
            for c in chunks
        ]

        # 硅基流动 API (BGE-M3) —— 唯一嵌入通道，失败即响亮失败（见 docstring）
        embedding_fn = _SiliconFlowEmbedding()
        embeddings = embedding_fn.embed(texts)
        self._collection.upsert(
            ids=ids, embeddings=embeddings,
            documents=texts, metadatas=metadatas,
        )
        return ids

    @staticmethod
    def _chunk_id(chunk: dict) -> str:
        """内容寻址 chunk ID：同 source 同文本 → 同 ID（重索引幂等）。"""
        digest = hashlib.md5(
            f"{chunk.get('source', '')}\x00{chunk['text']}".encode("utf-8")
        ).hexdigest()
        return f"chunk_{digest}"

    def _source_chunk_ids(self, source: str) -> list[str]:
        """列出某 source 当前在库的 chunk ID（重索引时用于清理旧 chunk）。"""
        if not source:
            return []
        try:
            got = self._collection.get(where={"source": source})
            return list(got.get("ids", []))
        except Exception as e:
            logger.warning("RAG: failed to list chunks of source=%s: %s", source, e)
            return []

    def _delete_chunks(self, ids) -> None:
        """按 ID 删除 chunk（忽略单个删除失败，不阻塞索引主流程）。"""
        ids = list(ids)
        if not ids:
            return
        try:
            self._collection.delete(ids=ids)
        except Exception as e:
            logger.warning("RAG: failed to delete %d stale chunks: %s", len(ids), e)


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

"""P1-21 回归（验收 2026-10-24）：嵌入失败不混回退向量 + 重索引清旧 chunk。

修复前：
- 嵌入失败时批次级回退到 chromadb 内置 MiniLM —— 同一 collection 混两种
  向量空间（BGE-M3 1024 维 / MiniLM 384 维），检索质量静默劣化且无法事后清理；
- 重索引（内容变更）只追加不清旧 chunk，新旧两版知识同时在库里；
- chunk_{count+i} 行数 ID 跨进程并发写必然撞号。

负样本断言方向：嵌入服务失败时 collection 里绝不出现回退向量（条数不增、
维度不混）；重索引后旧 chunk 必须消失。
"""

import logging

import pytest

import src.rag.indexer as indexer_mod
from src.rag.indexer import RAGIndexer

FAKE_DIM = 8   # 与 chromadb 内置回退的 384 维拉开，维度混入必暴露


class _FakeEmbedOK:
    """稳定 8 维假嵌入 —— 维度一致且远异于回退模型的 384 维。"""

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[float(len(t) % 7) + 0.5] * FAKE_DIM for t in texts]


def _md(title: str, sections: dict[str, str], source: str = "kb.md") -> dict:
    """按 '## 标题' 拼一份会切成多 chunk 的文档。"""
    body = "".join(f"## {h}\n{text}\n" for h, text in sections.items())
    return {"title": title, "content": body, "source": source}


@pytest.fixture()
def ok_embed(monkeypatch):
    fake = _FakeEmbedOK()
    monkeypatch.setattr(indexer_mod, "_SiliconFlowEmbedding", lambda *a, **k: fake)
    return fake


@pytest.fixture()
def indexer(tmp_path, ok_embed):
    return RAGIndexer(persist_dir=str(tmp_path / "rag_index"))


def _stored_embeddings(idx: RAGIndexer) -> list[list[float]]:
    got = idx._collection.get(include=["embeddings"])
    return [list(e) for e in got["embeddings"]]


class TestEmbedFailureNeverWritesFallback:
    def test_failed_batch_writes_nothing(self, indexer, ok_embed, caplog):
        doc_a = _md("A", {"S1": "alpha " * 30, "S2": "beta " * 30}, source="a.md")
        assert indexer.index_documents([doc_a]) == 2
        before = indexer.chunk_count

        # 嵌入服务开始失败（网络挂了）
        def _down(texts):
            raise ConnectionError("siliconflow unreachable")
        ok_embed.embed = _down

        with caplog.at_level(logging.ERROR, logger="src.rag.indexer"):
            doc_b = _md("B", {"S1": "gamma " * 30}, source="b.md")
            written = indexer.index_documents([doc_b])

        assert written == 0                       # 失败批次被跳过
        assert indexer.chunk_count == before == 2  # 绝不写入回退向量

    def test_no_dimension_mixing_in_collection(self, indexer, ok_embed):
        """collection 里所有向量维度必须一致（混入 384 维回退即失败）。"""
        indexer.index_documents([_md("A", {"S1": "alpha " * 30}, source="a.md")])

        def _down(texts):
            raise ConnectionError("down")
        ok_embed.embed = _down
        indexer.index_documents([_md("B", {"S1": "beta " * 30}, source="b.md")])

        dims = {len(e) for e in _stored_embeddings(indexer)}
        assert dims == {FAKE_DIM}

    def test_failure_is_loud_not_silent(self, indexer, ok_embed, caplog):
        ok_embed.embed = lambda texts: (_ for _ in ()).throw(ConnectionError("down"))
        with caplog.at_level(logging.ERROR, logger="src.rag.indexer"):
            indexer.index_documents([_md("A", {"S1": "alpha " * 30}, source="a.md")])
        assert any("RAG index batch failed" in r.message for r in caplog.records)

    def test_failed_batch_does_not_poison_next_batches(self, indexer, ok_embed):
        """A 成功 → B 失败 → C 成功：B 跳过，A/C 必须都在。"""
        def _down(texts):
            raise ConnectionError("down")

        indexer.index_documents([_md("A", {"S1": "alpha " * 30}, source="a.md")])
        ok_embed.embed = _down
        indexer.index_documents([_md("B", {"S1": "beta " * 30}, source="b.md")])
        ok_embed.embed = _FakeEmbedOK().embed
        indexer.index_documents([_md("C", {"S1": "gamma " * 30}, source="c.md")])

        assert indexer.chunk_count == 2
        sources = {m["source"] for m in indexer._collection.get()["metadatas"]}
        assert sources == {"a.md", "c.md"}


class TestReindexReplacesOldChunks:
    def test_reindex_drops_stale_chunks(self, indexer):
        old = _md("KB", {"S1": "旧内容 alpha " * 20, "S2": "共享尾巴 " * 20}, source="kb.md")
        indexer.index_documents([old])
        assert indexer.chunk_count == 2

        new = _md("KB", {"S1": "新内容 beta " * 20, "S2": "共享尾巴 " * 20}, source="kb.md")
        indexer.index_documents([new])

        assert indexer.chunk_count == 2                       # 不累积成 4
        texts = " ".join(indexer._collection.get()["documents"])
        assert "新内容 beta" in texts
        assert "旧内容 alpha" not in texts                    # 旧 chunk 必须被清

    def test_unchanged_content_is_idempotent(self, indexer):
        """内容寻址 ID + upsert：同一文档重复索引不产生重复 chunk。"""
        doc = _md("KB", {"S1": "stable " * 20}, source="kb.md")
        indexer.index_documents([doc])
        count = indexer.chunk_count
        indexer.index_documents([doc])
        assert indexer.chunk_count == count == 1

    def test_unchanged_chunk_keeps_stable_id(self, indexer):
        """变更 S1、S2 原样：S2 的 chunk ID 必须保持不变（内容寻址语义）。"""
        old = _md("KB", {"S1": "旧内容 alpha " * 20, "S2": "共享尾巴 " * 20}, source="kb.md")
        indexer.index_documents([old])
        id_before = {
            m["title"]: i
            for i, m in zip(indexer._collection.get()["ids"],
                            indexer._collection.get()["metadatas"])
        }

        new = _md("KB", {"S1": "新内容 beta " * 20, "S2": "共享尾巴 " * 20}, source="kb.md")
        indexer.index_documents([new])
        id_after = {
            m["title"]: i
            for i, m in zip(indexer._collection.get()["ids"],
                            indexer._collection.get()["metadatas"])
        }

        s2_title = next(t for t in id_after if "S2" in t)
        assert id_after[s2_title] == id_before[s2_title]

    def test_failed_write_keeps_old_data(self, indexer, ok_embed):
        """写入失败（嵌入挂）时旧知识原样保留 —— 先删后写会丢数据。"""
        indexer.index_documents([_md("KB", {"S1": "旧内容 alpha " * 20}, source="kb.md")])
        count = indexer.chunk_count

        ok_embed.embed = lambda texts: (_ for _ in ()).throw(ConnectionError("down"))
        indexer.index_documents([_md("KB", {"S1": "新内容 beta " * 20}, source="kb.md")])

        assert indexer.chunk_count == count
        assert "旧内容 alpha" in " ".join(indexer._collection.get()["documents"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document

from utils.config_handler import chroma_conf
from model.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger
import os

from utils.supabase_client import supabase


class VectorStoreService:
    def __init__(self):
        self.vector_store = SupabaseVectorStore(
            embedding=embed_model,
            client=supabase,
            table_name="documents",
            query_name="match_documents"
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

        self._bm25_index = None  # Lazy-built BM25Index
        self._bm25_attempted = False  # Only try once

    def similarity_search(
        self, query: str, k: int = 5, filter_metadata: dict = None
    ) -> list[Document]:
        """
        Vector similarity search via Supabase RPC match_documents.
        Optional metadata filter applied post-retrieval (fine for k=5).
        """
        try:
            query_embedding = embed_model.embed_query(query)
            # Fetch extra results if we need to filter, to keep ~k after filtering
            fetch_k = k * 3 if filter_metadata else k
            res = supabase.rpc(
                self.vector_store.query_name,
                {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.5,
                    "match_count": fetch_k,
                }
            ).execute()

            documents = []
            for item in res.data:
                meta = item.get("metadata", {})
                # Apply metadata filter
                if filter_metadata:
                    if not all(meta.get(k) == v for k, v in filter_metadata.items()):
                        continue
                documents.append(Document(
                    page_content=item.get("content", ""),
                    metadata=meta
                ))
            return documents[:k]
        except Exception as e:
            logger.error(f"VectorStore RPC search failed: {e}")
            return []

    def hybrid_search(
        self, query: str, k: int = 5, filter_metadata: dict = None
    ) -> list[Document]:
        """
        Hybrid search: vector + BM25 with Reciprocal Rank Fusion.
        Falls back to pure vector search if BM25 index is not ready.
        """
        # Vector search
        vector_docs = self.similarity_search(query, k=k * 2, filter_metadata=filter_metadata)
        if not vector_docs:
            return []

        # BM25 search
        self._ensure_bm25()
        bm25_results = self._bm25_index.search(query, k=k * 2) if self._bm25_index and self._bm25_index.is_ready else []

        if not bm25_results:
            return vector_docs[:k]

        # Build a unified doc list for RRF — use hash as stable unique key (no collision on [:100])
        all_docs = list(vector_docs)  # copy
        doc_to_vec_rank = {}
        for i, doc in enumerate(vector_docs):
            doc_to_vec_rank[hash(doc.page_content)] = i + 1  # 1-indexed rank

        # Add any BM25-only docs not in vector results
        for idx, _ in bm25_results:
            doc_text = self._bm25_index._docs[idx]
            if hash(doc_text) not in doc_to_vec_rank:
                all_docs.append(Document(page_content=doc_text, metadata={}))

        # Precompute BM25 rank lookup
        bm25_rank_map = {}
        for j, (bm_idx, _) in enumerate(bm25_results):
            bm25_rank_map[hash(self._bm25_index._docs[bm_idx])] = j + 1
        default_rank = len(all_docs)

        # RRF scoring
        rrf_scores = {}
        for i, doc in enumerate(all_docs):
            key = hash(doc.page_content)
            vec_rank = doc_to_vec_rank.get(key, default_rank)
            bm25_rank = bm25_rank_map.get(key, default_rank)
            rrf_scores[key] = 1.0 / (60 + vec_rank) + 1.0 / (60 + bm25_rank)

        # Sort by RRF score descending
        sorted_docs = sorted(all_docs, key=lambda d: rrf_scores.get(hash(d.page_content), 0), reverse=True)
        return [d for d in sorted_docs if d.page_content.strip()][:k]

    def get_retriever(self, k: int = None, filter_kwargs: dict = None):
        if k is None:
            k = chroma_conf.get("k", 5)
        search_kwargs = {"k": k}
        if filter_kwargs:
            search_kwargs["filter"] = filter_kwargs
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)

    def _ensure_bm25(self):
        """Lazy-build BM25 index from all documents in the vector store."""
        if self._bm25_index and self._bm25_index.is_ready:
            return
        if self._bm25_attempted:
            return  # already tried and failed; don't retry
        self._bm25_attempted = True
        try:
            from rag.bm25_index import BM25Index
            # Fetch all document content from Supabase
            res = supabase.table("documents").select("content").limit(5000).execute()
            docs = [r["content"] for r in res.data if r.get("content")]
            if docs:
                self._bm25_index = BM25Index(docs)
                logger.info(f"BM25 index built: {self._bm25_index.doc_count} documents")
        except Exception as e:
            logger.warning(f"BM25 index build failed, falling back to vector-only: {e}")
            self._bm25_index = None
    
    def load_documents(self):
        """
        从数据文件夹中读取数据文件，转为向量存入向量库
        要计算文件的MD5做去重
        return:None
        """
        def check_md5_hex(md5_for_check: str):
            if not os.path.exists(get_abs_path(chroma_conf["md5_hex_store"])):
                # 创建文件
                open(get_abs_path(chroma_conf["md5_hex_store"]), "w", encoding="utf-8").close()
                return False   # md5 没有处理过
            
            with open(get_abs_path(chroma_conf["md5_hex_store"]), "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if md5_for_check == line:
                        return True # md5 处理过
                
                return False
            
        def save_md5_hex(md5_for_check: str):
            with open(get_abs_path(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str):
            if read_path.endswith("txt"):
                return txt_loader(read_path)
            
            if read_path.endswith("pdf"):
                return pdf_loader(read_path)
            
            return []
        
        allowed_file_path: list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]), 
            tuple(chroma_conf["allow_knowledge_file_type"])
            )
        
        for path in allowed_file_path:
            # 获取文件的MD5
            md5_hex = get_file_md5_hex(path)

            if check_md5_hex(md5_hex):   # 已经处理过
                logger.info(f"[加载知识库]{path}已经存在在知识库内，跳过")
                continue

            try:   # 加载文件
                documents: list[Document] = get_file_documents(path)

                if not documents:   # 文件为空
                    logger.warning(f"[加载知识库]{path}为空文件，跳过")
                    continue
                    
                split_document: list[Document] = self.spliter.split_documents(documents)

                if not split_document:   # 分割为空
                    logger.warning(f"[加载知识库]{path}分片后没有有效的文本内容，跳过")
                    continue
                
                # Update metadata with md5 hex to avoid duplication logically if needed in future
                for doc in split_document:
                    if not doc.metadata:
                        doc.metadata = {}
                    doc.metadata["md5_hex"] = md5_hex

                # 将内容存入向量库
                self.vector_store.add_documents(split_document)

                # 记录这个已经处理好的文件的md5，避免下次重复加载
                save_md5_hex(md5_hex)
                logger.info(f"[加载知识库]{path}成功")

            except Exception as e:
                # exc_info=True 会记录详细的报错堆栈，如果为False 只会记录报错信息
                logger.error(f"[加载知识库]文件{path}加载失败:{str(e)}", exc_info=True)
                continue



if __name__ == "__main__":
    # === 1. 先测试 embedding 模型 ===
    test_query = "联系教授"
    try:
        # 直接调用 embed_query 测试
        embedding = embed_model.embed_query(test_query)
        print(f"embed_query 成功！向量维度: {len(embedding)}")
        print(f"前5个值: {embedding[:5]}")
    except Exception as e:
        print("embedding 模型测试失败:", e)
        import traceback
        traceback.print_exc()
        exit(1)

    # === 2. 继续原有的加载和检索 ===
    vs = VectorStoreService()
    
    # --- 强力调试开始 ---
    abs_data_path = get_abs_path(chroma_conf["data_path"])
    print(f"🔍 正在检查数据目录: {abs_data_path}")
    
    if not os.path.exists(abs_data_path):
        print("❌ 错误：数据目录不存在！")
    else:
        files = os.listdir(abs_data_path)
        print(f"📁 目录下所有文件: {files}")
    
    # 显式调用加载
    vs.load_documents()
    retriever = vs.get_retriever(k=2)
    res = retriever.invoke(test_query)
    
    if not res:
        print("检索结果为空，可能知识库中没有相关文档。")
    else:
        for r in res:
            print(r.page_content)
            print("-" * 20)


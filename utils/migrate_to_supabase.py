import os
import sys
import hashlib
from typing import List
from dotenv import load_dotenv
load_dotenv()  # 这一行是灵魂，没有它，代码看不见 .env 文件
# 确保能找到根目录下的包
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_client import supabase
from model.factory import embed_model
from utils.config_handler import chroma_conf
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def migrate_documents_to_supabase():
    print("🚀 开始数据迁移至 Supabase")
    
    # 1. 初始化相同的切分器
    spliter = RecursiveCharacterTextSplitter(
        chunk_size=chroma_conf["chunk_size"],
        chunk_overlap=chroma_conf["chunk_overlap"],
        separators=chroma_conf["separators"],
        length_function=len,
    )
    
    # 2. 读取允许的知识库文件
    data_path = get_abs_path(chroma_conf["data_path"])
    if not os.path.exists(data_path):
        print(f"❌ 数据文件夹不存在: {data_path}")
        return
        
    allowed_file_path = listdir_with_allowed_type(
        data_path, 
        tuple(chroma_conf["allow_knowledge_file_type"])
    )
    
    print(f"📁 找到 {len(allowed_file_path)} 个待处理文件")
    
    total_chunks = 0
    # 3. 逐个处理
    for path in allowed_file_path:
        md5_hex = get_file_md5_hex(path)
        file_name = os.path.basename(path)
        print(f"🔄 正在处理: {file_name} (MD5: {md5_hex[:8]}...)")
        
        # 检查 Supabase 中是否已存在相同 MD5 的文件，避免重复迁移
        try:
            # 在 metadata 中使用 jsonb 查询 (LangChain SupabaseVectorstore 将 metadata 存在一个 jsonb 字段里)
            response = supabase.table("documents").select("id").contains("metadata", {"md5_hex": md5_hex}).limit(1).execute()
            if response.data:
                print(f"⏭️  文件 {file_name} 已存在于云端，跳过。")
                continue
        except Exception as e:
            print(f"⚠️ 检查 MD5 时出错: {e}，将继续尝试插入。")

        # 加载文档
        documents = []
        if path.endswith("txt"):
            documents = txt_loader(path)
        elif path.endswith("pdf"):
            documents = pdf_loader(path)
            
        if not documents:
            print(f"⚠️ {file_name} 为空或解析失败，跳过。")
            continue
            
        # 分块
        split_docs = spliter.split_documents(documents)
        if not split_docs:
            print(f"⚠️ {file_name} 分块为空，跳过。")
            continue
            
        print(f"✂️  {file_name} 已切分为 {len(split_docs)} 块，正在计算向量并上传...")
        
        # 给这些切块打上统一的 metadata
        for i, doc in enumerate(split_docs):
            if doc.metadata is None:
                doc.metadata = {}
            # 保留原有 metadata (如 source, page) 的同时注入我们的管理字段
            doc.metadata["md5_hex"] = md5_hex
            doc.metadata["file_name"] = file_name
            # 可选：你可以根据文件名自动打标签，例如：
            # if "募集要项" in file_name: doc.metadata["type"] = "admission_guide"
            # if "过去问" in file_name: doc.metadata["type"] = "past_exam"
            
        # 批量获取 Embedding 并插入
        # 这里为了稳定，如果是极大量数据建议手动分批 (batch_size=100)
        batch_size = 100
        for i in range(0, len(split_docs), batch_size):
            batch = split_docs[i:i + batch_size]
            texts = [d.page_content for d in batch]
            metadatas = [d.metadata for d in batch]
            
            try:
                embeddings = embed_model.embed_documents(texts)
                
                # 组装数据并插入 Supabase documents 表
                records = []
                for text, meta, emb in zip(texts, metadatas, embeddings):
                    records.append({
                        "content": text,
                        "metadata": meta,
                        "embedding": emb
                    })
                
                supabase.table("documents").insert(records).execute()
                total_chunks += len(records)
                print(f"✅ 成功插入 {i + len(records)} / {len(split_docs)} 块。")
                
            except Exception as e:
                print(f"❌ 批量插入第 {i} 块时失败: {e}")
                
    print(f"🎉 迁移完成！总共成功上传 {total_chunks} 个向量文档块。")

if __name__ == "__main__":
    migrate_documents_to_supabase()

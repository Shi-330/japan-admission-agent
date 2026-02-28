from dotenv import load_dotenv
load_dotenv()

from langchain_chroma import Chroma
from langchain_core.documents import Document

from utils.config_handler import chroma_conf
from model.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger
import os



class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=chroma_conf["persist_directory"],
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})
    
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

                # 这一块如果数据量太大需要数据校验，用文件效率比较低

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
    vs = VectorStoreService()
    vs.load_documents()
    retriever = vs.get_retriever()
    res = retriever.invoke("研究计划书")
    for r in res:
        print(r.page_content)
        print("-"*20)


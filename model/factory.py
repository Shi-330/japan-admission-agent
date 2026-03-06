import os
from dotenv import load_dotenv
load_dotenv()

from abc import ABC, abstractmethod
from typing import Optional
from langchain.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from utils.config_handler import rag_conf
from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # 适配coding plan

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return ChatOpenAI( # 从ChaTongyi -> ChatOpenAI为了适配coding plan
            model=rag_conf["chat_model_name"],
            api_key=os.getenv("OPENAI_API_KEY"),  # 建议从环境变量读取
            base_url="https://coding.dashscope.aliyuncs.com/v1",  # 关键修改
            streaming=True,
            request_timeout=30, # 缩短为30秒
            max_retries=1 # 失败快速退出，不无限重试
        )
    

class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return DashScopeEmbeddings(
            model=rag_conf["embedding_model_name"],
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"), # 调用的时候用的是dashscope_api_key <- openai_api_key(但是这个是openai的标准件)
            # openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
    

chat_model = ChatModelFactory().generator()
embed_model = EmbeddingModelFactory().generator()

# if __name__ == "__main__":
#     # 测试 Chat 模型（可选）
#     print("Chat 模型配置：", chat_model)
    
#     # 测试 Embedding 模型
#     print("\n开始测试 Embedding 模型...")
#     test_text = "研究计划书"
#     try:
#         # 调用 embed_query 测试单个字符串
#         embedding = embed_model.embed_query(test_text)
#         print(f"embed_query 成功，向量维度：{len(embedding)}")
#         print(f"前5个值：{embedding[:5]}")
        
#         # 也可测试 embed_documents（传入字符串列表）
#         embeddings = embed_model.embed_documents([test_text, "教授邮件"])
#         print(f"embed_documents 成功，返回 {len(embeddings)} 个向量")
#     except Exception as e:
#         print("Embedding 模型调用失败：", e)
#         import traceback
#         traceback.print_exc()
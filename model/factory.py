from abc import ABC, abstractmethod
from typing import Optional
from langchain.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from utils.config_handler import rag_conf
from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # 适配coding plan
import os

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return ChatOpenAI( # 从ChaTongyi -> ChatOpenAI为了适配coding plan
            model=rag_conf["chat_model_name"],
            api_key=os.getenv("OPENAI_API_KEY"),  # 建议从环境变量读取
            base_url="https://coding.dashscope.aliyuncs.com/v1"  # 关键修改
        )
    

class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return OpenAIEmbeddings(
            model=rag_conf["embedding_model_name"],
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
    

chat_model = ChatModelFactory().generator()
embed_model = EmbeddingModelFactory().generator()
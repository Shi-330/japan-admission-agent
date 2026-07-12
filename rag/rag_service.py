"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料交给模型，让模型总结回复
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
# from  import profile


class RagSummarizeService(object):

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()
    def _init_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain
    
    def retriever_docs(self, query: str) -> list[Document]:
        return self.vector_store.hybrid_search(query)

    def get_raw_vector_context(self, query: str) -> str:
        """【新增】快通道：只获取格式化后的原始素材，不调用 LLM"""
        context_docs = self.retriever_docs(query)
        
        context = ""
        for i, doc in enumerate(context_docs, 1):
            # 格式化素材，保留来源，方便 Agent 引用
            context += f"【参考资料{i}】：{doc.page_content} | 来源:{doc.metadata.get('source', '未知')}\n"
        
        return context if context else "未找到相关参考资料。"
    
    def _web_search(self, query: str, max_results: int = 3) -> str:
        """Fallback: DuckDuckGo web search. Returns formatted context or empty string."""
        try:
            from langchain_community.tools import DuckDuckGoSearchResults
            from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
            wrapper = DuckDuckGoSearchAPIWrapper(max_results=max_results)
            search = DuckDuckGoSearchResults(api_wrapper=wrapper)
            results = search.invoke(query)
            if results:
                return f"【网络搜索】{results}"
        except Exception:
            pass
        return ""

    def search_with_fallback(self, query: str) -> str:
        """RAG first, web search fallback. Returns formatted context for LLM prompt."""
        ctx = self.get_raw_vector_context(query)
        if ctx and "未找到" not in ctx:
            return ctx
        web_ctx = self._web_search(query)
        return web_ctx or ctx  # web or original "未找到" message

    def rag_summarize(self, query: str, profile: str) -> str:
        # 直接复用逻辑，减少重复代码
        context = self.get_raw_vector_context(query)
        return self.chain.invoke({
            "input": query,
            "context": context,
            "profile": profile
        })
    
if __name__ == "__main__":
    rag_service = RagSummarizeService()
    print(rag_service.rag_summarize("小户型适合哪些扫地机器人"))
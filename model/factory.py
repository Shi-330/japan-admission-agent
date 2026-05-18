import os, json
# Kill broken system proxy & use HF mirror for China access
for _v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_v, None)
os.environ["NO_PROXY"] = "*"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from dotenv import load_dotenv
load_dotenv()

from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

def _get_deepseek_key() -> str:
    """Read DeepSeek API key from env or Claude settings."""
    for var in ("DEEPSEEK_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        val = os.getenv(var)
        if val and val.startswith("sk-"):
            return val
    # Fallback: read from ~/.claude/settings.json
    settings_path = os.path.expanduser("~/.claude/settings.json")
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            token = json.load(f).get("env", {}).get("ANTHROPIC_AUTH_TOKEN", "")
            if token and token.startswith("sk-"):
                return token
    raise ValueError("DeepSeek API key not found. Set DEEPSEEK_API_KEY in .env or ANTHROPIC_AUTH_TOKEN in ~/.claude/settings.json")


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return ChatOpenAI(
            model="deepseek-chat",
            api_key=_get_deepseek_key(),
            base_url="https://api.deepseek.com/v1",
            streaming=True,
            request_timeout=30,
            max_retries=1,
        )


class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return HuggingFaceEmbeddings(
            model_name="BAAI/bge-large-zh-v1.5",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )


class _LazyEmbedding:
    """Lazy proxy so embedding model download doesn't block chat import."""
    _instance = None

    def _ensure(self):
        if self._instance is None:
            self._instance = EmbeddingModelFactory().generator()

    def __getattr__(self, name):
        self._ensure()
        return getattr(self._instance, name)

    def __repr__(self):
        if self._instance is None:
            return "<LazyEmbedding (not loaded)>"
        return repr(self._instance)


chat_model = ChatModelFactory().generator()
embed_model = _LazyEmbedding()

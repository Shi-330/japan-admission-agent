import os, json
# Kill broken system proxy & use HF mirror for China access
for _v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_v, None)
os.environ["NO_PROXY"] = "*"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"  # Windows no symlink support

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
        base = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",  # 512-dim native
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
            cache_folder=os.path.join(os.path.dirname(__file__), "..", ".hf_cache"),
        )
        return _PadEmbedding(base, target_dim=1024)  # pad to 1024-dim for Supabase schema


class _PadEmbedding:
    """Wrapper that pads short embeddings to target_dim with zeros, preserving cosine similarity."""
    def __init__(self, base, target_dim):
        self._base = base
        self._target = target_dim

    def embed_query(self, text):
        v = self._base.embed_query(text)
        return v + [0.0] * (self._target - len(v))

    def embed_documents(self, texts):
        return [[*v, *([0.0] * (self._target - len(v)))] for v in self._base.embed_documents(texts)]

    def __getattr__(self, name):
        return getattr(self._base, name)


class RemoteEmbeddingFactory(BaseModelFactory):
    """DashScope / OpenAI-compatible embedding API — zero local download."""
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        from langchain_community.embeddings import DashScopeEmbeddings
        return DashScopeEmbeddings(
            model="text-embedding-v4",
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
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

# Embedding mode: "local" = BGE small (24 MB), "api" = DashScope (zero download)
_embed_mode = os.getenv("EMBEDDING_MODE", "local")
if _embed_mode == "api":
    embed_model = RemoteEmbeddingFactory().generator()
else:
    embed_model = _LazyEmbedding()  # lazy-load BGE on first use

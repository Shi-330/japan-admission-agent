import os
from supabase.client import create_client, Client
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

def get_supabase_client() -> Client:
    supabase_url: str = os.environ.get("SUPABASE_URL")
    supabase_key: str = os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("Missing Supabase credentials (SUPABASE_URL or SUPABASE_KEY) in environment variables.")
        
    return create_client(supabase_url, supabase_key)

supabase = get_supabase_client()

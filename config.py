"""
配置管理模块 - 安全地加载环境变量
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 找到项目根目录的 .env 文件
current_dir = Path(__file__).parent.resolve()
env_file = current_dir / ".env"

# 加载 .env 文件（不存在也不报错）
load_dotenv(dotenv_path=env_file, override=False)

# 获取 API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# 打印调试信息（可选）
if not DASHSCOPE_API_KEY:
    print(f"警告：DASHSCOPE_API_KEY 未设置，请检查 .env 文件位置：{env_file}")
if not OPENAI_API_KEY:
    print(f"警告：OPENAI_API_KEY 未设置，请检查 .env 文件位置：{env_file}")

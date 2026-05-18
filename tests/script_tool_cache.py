import sys
from utils.path_tool import get_project_root

# 1. 利用你写的 path_tool 动态锁定根目录
root = get_project_root()
if root not in sys.path:
    sys.path.append(root)

# 2. 现在可以顺畅地导入了
import time
from agent.tools.rag_tools import rag_fetch_context

# 模拟 LangGraph 传入的 state
mock_state = {
    "messages": [
        {"role": "system", "content": "【当前咨询者背景画像】：GPA 3.8, N1 合格, 目标东京大学计算机专业"}
    ]
}

def test_cache_logic():
    query = "东京大学计算机研究室要求"
    
    print("--- 🔄 第一次调用（预期：缓存穿透，执行检索） ---")
    start_time = time.time()
    # 这种方式更接近 Agent 真实的运行逻辑
    result1 = rag_fetch_context.invoke({"query": query, "state": mock_state})
    end_time = time.time()
    print(f"耗时: {end_time - start_time:.4f}s")
    # print(f"返回结果片段: {result1[:50]}...")

    print("\n--- 🚀 第二次调用（预期：缓存命中，瞬间返回） ---")
    start_time = time.time()
    result2 = rag_fetch_context.invoke({"query": query, "state": mock_state})
    end_time = time.time()
    print(f"耗时: {end_time - start_time:.4f}s")

    # 验证逻辑
    if (end_time - start_time) < 0.01:
        print("\n✅ 测试通过：缓存机制生效！")
    else:
        print("\n❌ 测试失败：第二次调用耗时过长，缓存未命中。")

if __name__ == "__main__":
    test_cache_logic()
# tests/test_agent_logic.py
import sys
import os
# 确保能导入 agent 文件夹
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.react_agent import ReactAgent
from agent.prompts import PLANNER_PROMPT

def test_cache_logic():
    # 模拟初始画像
    profile_1 = "JLPT: N2, GPA: 3.5, Major: CS"
    user_input = "我想申请东京大学"
    
    # 1. 初始化第一个 Agent
    print("--- 实验 1: 第一次提问 (预期: 调用 LLM) ---")
    agent = ReactAgent(user_profile={"jlpt": "N2", "gpa": 3.5, "major": "CS"})
    
    res1 = agent.make_decision(PLANNER_PROMPT, profile_1, user_input)
    print(f"回答 1: {res1}\n")

    # 2. 第二次提问 (相同画像，相同输入)
    print("--- 实验 2: 第二次提问 (预期: 命中内部缓存) ---")
    res2 = agent.make_decision(PLANNER_PROMPT, profile_1, user_input)
    print(f"回答 2: {res2}")
    
    # 验证是否一致
    assert res1 == res2, "缓存结果不一致！"

    # 3. 模拟 UI 更新画像 (销毁并重建 Agent)
    print("\n--- 实验 3: 更新画像后提问 (预期: 缓存重置，调用 LLM) ---")
    profile_2 = "JLPT: N1, GPA: 3.8, Major: CS" # 画像变了
    new_agent = ReactAgent(user_profile={"jlpt": "N1", "gpa": 3.8, "major": "CS"})
    
    res3 = new_agent.make_decision(PLANNER_PROMPT, profile_2, user_input)
    print(f"回答 3: {res3}")

# 专门测 LRU 的小实验
def test_lru_overflow():
    small_cache_agent = ReactAgent(cache_size=2) # 只记 2 条
    
    # 存 A, 存 B
    small_cache_agent.make_decision(PLANNER_PROMPT, "P1", "Q1")
    small_cache_agent.make_decision(PLANNER_PROMPT, "P1", "Q2")
    
    # 存 C (此时 A 应该被挤掉)
    small_cache_agent.make_decision(PLANNER_PROMPT, "P1", "Q3")
    
    # 再次问 Q1 (预期: 缓存不命中，重新调 LLM)
    print("再次问 Q1，观察是否被挤掉...")
    small_cache_agent.make_decision(PLANNER_PROMPT, "P1", "Q1")

if __name__ == "__main__":
    # test_cache_logic()
    test_lru_overflow()
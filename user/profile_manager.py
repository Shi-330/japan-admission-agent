import json
import os
import dotenv
dotenv.load_dotenv()
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from supabase import create_client, Client
import uuid

# 1. 定义用户画像的数据结构 (一定要保留，它是 Agent 的灵魂)
class UserProfile(BaseModel):
    """留学生画像模型"""
    jlpt_level: str = Field(default="无", description="日语等级 (N1-N5)")
    eju_score: int = Field(default=0, ge=0, le=800, description="EJU总分")
    gpa: float = Field(default=0.0, ge=0.0, le=4.0, description="平均绩点")
    target_major: str = Field(default="未设定", description="目标专业")
    undergraduate_school: str = Field(default="未设定", description="本科院校背景")
    english_score: str = Field(default="未参加", description="托福/托业成绩") # 刚才规划书里提到的

    def to_dict(self):
        return self.model_dump() # Pydantic v2 使用 model_dump

# 2. 线上版管理器 (Supabase)
class ProfileManager: # 建议直接改名为 ProfileManager，方便 app.py 无缝切换
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            print("⚠️ 警告: 未检测到 SUPABASE_URL 或 SUPABASE_KEY，将无法使用数据库功能")
            self.supabase = None
        else:
            self.supabase: Client = create_client(self.url, self.key)

    def get_profile(self, user_id: str) -> UserProfile:
        """从 Supabase 获取画像，若无则返回默认对象"""
        if not self.supabase:
            return UserProfile()
            
        try:
            response = self.supabase.table("user_profiles").select("*").eq("id", user_id).execute()
            if response.data and len(response.data) > 0:
                # 将数据库字典转回 Pydantic 模型
                return UserProfile(**response.data[0])
        except Exception as e:
            print(f"❌ 读取数据库失败: {e}")
            
        return UserProfile()

    def save_profile(self, user_id: str, profile: UserProfile):
        """保存 UserProfile 对象到数据库"""
        if not self.supabase:
            print("❌ 无法保存：数据库未连接")
            return
            
        data = profile.to_dict()
        data["id"] = user_id # 确保 ID 字段正确
        
        try:
            self.supabase.table("user_profiles").upsert(data).execute()
            print(f"✅ 用户 {user_id} 画像已同步至数据库")
        except Exception as e:
            print(f"❌ 保存数据库失败: {e}")

    def format_for_prompt(self, profile: UserProfile) -> str:
        """将画像格式化为 Agent 容易理解的字符串"""
        return (
            f"【学生背景画像】\n"
            f"- 日语能力: {profile.jlpt_level}\n"
            f"- EJU预估分: {profile.eju_score}\n"
            f"- 本科GPA: {profile.gpa}\n"
            f"- 目标专业: {profile.target_major}\n"
            f"- 院校背景: {profile.undergraduate_school}\n"
            f"- 英语成绩: {profile.english_score}"
        )

# 3. 测试逻辑
if __name__ == "__main__":

    manager = ProfileManager()
    test_id = "00000000-0000-0000-0000-000000000001" #str(uuid.uuid4()) # 注意：如果数据库 id 是 UUID 类型，这里需换成有效的 UUID 字符串
    print(f"--- 正在使用合法 UUID 测试: {test_id} ---")
    print("--- 正在测试 Supabase 保存 ---")
    # new_student = UserProfile(
    #     jlpt_level="N1",
    #     eju_score=710,
    #     gpa=3.8,
    #     target_major="计算机科学",
    #     undergraduate_school="某名牌大学"
    # )
    
    # manager.save_profile(test_id, new_student)
    
    print("\n--- 正在测试 Supabase 读取 ---")
    loaded = manager.get_profile(test_id)
    print(f"读取到的目标专业: {loaded.target_major}")
    
    print("\n--- 提示词格式化预览 ---")
    print(manager.format_for_prompt(loaded))
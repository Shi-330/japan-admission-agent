import json
import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from supabase import AuthApiError
from utils.supabase_client import supabase as _shared_supabase
from utils.logger_handler import logger

# 1. 定义用户画像的数据结构 (一定要保留，它是 Agent 的灵魂)
class UserProfile(BaseModel):
    """留学生画像模型"""
    jlpt_level: str = Field(default="无", description="日语等级 (N1-N5)")
    eju_score: int = Field(default=0, ge=0, le=800, description="EJU总分")
    gpa: float = Field(default=0.0, ge=0.0, le=4.0, description="平均绩点")
    target_major: str = Field(default="未设定", description="目标专业")
    undergraduate_school: str = Field(default="未设定", description="本科院校背景")
    english_score: str = Field(default="未参加", description="托福/托业成绩")
    # --- 新增：报告持久化字段 ---
    report_status: Optional[str] = Field(default="NONE", description="报告状态 (NONE, DRAFT, REFINED)")
    suggestions: Optional[str] = Field(default=None, description="报告的核心建议")
    report_content: Dict[str, Any] = Field(default_factory=dict, description="报告完整结构化内容")
    report_last_updated: Optional[str] = Field(default=None, description="报告更新时间")

    def to_dict(self):
        return self.model_dump()

# 2. 线上版管理器 (Supabase)
class ProfileManager:
    def __init__(self):
        self.supabase = _shared_supabase

    def get_profile(self, user_id: str) -> UserProfile:
        """从 Supabase 获取画像，若无则返回默认对象"""
        if not self.supabase:
            return UserProfile()
            
        try:
            response = self.supabase.table("user_profiles").select("*").eq("id", user_id).execute()
            if response.data and len(response.data) > 0:
                data = response.data[0]
                # Filter out raw report content logic for memory efficiency, only parse known fields
                filtered_data = {k: v for k, v in data.items() if k in UserProfile.model_fields}
                return UserProfile(**filtered_data)
        except Exception as e:
            logger.error(f"读取数据库失败: {e}")

        return UserProfile()

    def save_profile(self, user_id: str, profile: UserProfile):
        """保存 UserProfile 对象到数据库"""
        if not self.supabase:
            logger.warning("无法保存：数据库未连接")
            return

        data = profile.to_dict()
        data["id"] = user_id

        try:
            self.supabase.table("user_profiles").upsert(data).execute()
            logger.info(f"用户 {user_id} 画像已同步至数据库")
        except Exception as e:
            logger.error(f"保存数据库失败: {e}")

    def format_for_prompt(self, profile: UserProfile) -> str:
        """将画像格式化为 Agent 容易理解的字符串"""
        prompt_str = (
            f"【学生背景画像】\n"
            f"- 日语能力: {profile.jlpt_level}\n"
            f"- EJU预估分: {profile.eju_score}\n"
            f"- 本科GPA: {profile.gpa}\n"
            f"- 目标专业: {profile.target_major}\n"
            f"- 院校背景: {profile.undergraduate_school}\n"
            f"- 英语成绩: {profile.english_score}\n"
        )
        if profile.report_status != "NONE" and profile.suggestions:
            prompt_str += (
                f"\n【重要提醒：该用户已有专属升学规划报告】\n"
                f"报告状态: {profile.report_status}\n"
                f"已有核心建议如下:\n{profile.suggestions}\n"
                f"注意：在本次对话中，你的身份是‘基于此报告跟进进度的伴随式导师’，请直接围绕上述建议展开交互，"
                f"无需再次生成全篇报告。如果用户要求调整建议，请予以指导。"
            )
        return prompt_str

    def send_reset_password_email(self, email: str):
        """发送重置密码验证码 (OTP)"""
        if not self.supabase: return
        try:
            return self.supabase.auth.reset_password_for_email(email)
        except AuthApiError as e:
            logger.warning(f"邮件发送失败: {e}")
            if "rate limit" in str(e).lower():
                raise Exception("邮件发送过于频繁，请稍后再试")
            else:
                raise e

    def verify_reset_otp(self, email: str, token: str):
        """验证 6 位验证码"""
        if not self.supabase: return None
        try:
            res = self.supabase.auth.verify_otp({
                "email": email,
                "token": token,
                "type": "recovery"
            })
            return res
        except Exception as e:
            logger.error(f"验证码校验失败: {e}")
            raise e

    def update_password(self, new_password: str):
        """更新密码 (需在 verify_reset_otp 成功后的会话中调用)"""
        if not self.supabase: return
        try:
            return self.supabase.auth.update_user({"password": new_password})
        except Exception as e:
            logger.error(f"更新密码失败: {e}")
            raise e

profile_mgr = ProfileManager() # 创建全局唯一的实例
# 3. 测试逻辑
if __name__ == "__main__":
    test_id = "00000000-0000-0000-0000-000000000001"
    print(f"--- 运行测试: {test_id} ---")
    loaded = profile_mgr.get_profile(test_id)
    print(profile_mgr.format_for_prompt(loaded))
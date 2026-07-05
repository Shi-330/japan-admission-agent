from langchain_core.tools import tool
from pydantic import BaseModel, Field

from user.profile_manager import ProfileManager, UserProfile
from utils.logger_handler import logger

_profile_mgr = ProfileManager()  # shared instance, same pool as the rest of the app


class FetchUserProfileInput(BaseModel):
    user_id: str = Field(description="用户的唯一标识符 UUID (例如 '00000000-0000-0000-0000-000000000001')")


class UpdateReportSuggestionsInput(BaseModel):
    user_id: str = Field(description="用户的唯一标识符 UUID")
    new_suggestions: str = Field(description="更新后的核心建议内容。注意：这会覆盖原有的建议内容，请传入完整的一套建议。")


@tool("fetch_user_profile_from_db", args_schema=FetchUserProfileInput)
def fetch_user_profile_from_db(user_id: str) -> str:
    """
    当需要了解当前咨询者的真实背景（例如日语成绩、GPA、出身校等）时调用此工具。
    如果不提供 user_id，默认尝试不调用或使用占位符。
    """
    try:
        profile = _profile_mgr.get_profile(user_id)
        if profile.jlpt_level == "无" and profile.eju_score == 0 and profile.gpa == 0.0:
            return "未查找到该用户的背景画像。请提示用户补充资料。"
        return str(profile.to_dict())
    except Exception as e:
        logger.error(f"从数据库获取画像失败: {e}")
        return f"工具调用失败，无法获取背景信息: {str(e)}。请继续使用已有信息回答，不要重试。"


@tool("update_report_suggestions", args_schema=UpdateReportSuggestionsInput)
def update_report_suggestions(user_id: str, new_suggestions: str) -> str:
    """
    【强制要求】报告规划生成完毕后，或者你认为需要调整用户的升学规划时，必须【立刻且必然】调用此工具。
    这将把你的核心建议保存到云端数据库中，非常重要！否则用户的看板将永远为空。
    """
    try:
        profile = _profile_mgr.get_profile(user_id)
        profile.suggestions = new_suggestions
        profile.report_status = "REFINED"
        _profile_mgr.save_profile(user_id, profile)
        return "报告建议库已成功更新。你可以回复用户，告诉他们看板上的建议已经刷新。"
    except Exception as e:
        logger.error(f"更新报告建议失败: {e}")
        return f"工具调用失败，无法更新建议: {str(e)}。请告知用户数据库发生异常。"

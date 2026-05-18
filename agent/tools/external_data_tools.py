import json
import os
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger

_external_data = {}
_data_loaded = False


class FetchExternalDataInput(BaseModel):
    user_id: str = Field(description="用户的唯一标识符 UUID")
    month: str = Field(description="月份，格式必须为 YYYY-MM，如 '2025-03'")


def _load_external_data():
    global _external_data, _data_loaded
    if _data_loaded:
        return

    external_data_path = get_abs_path(agent_conf["external_data_path"])
    if not os.path.exists(external_data_path):
        raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

    with open(external_data_path, "r", encoding="utf-8") as f:
        for line in f.readlines()[1:]:
            arr = line.strip().split(",")
            user_id = arr[0].replace('"', '')
            feature = arr[1].replace('"', '')
            efficiency = arr[2].replace('"', '')
            consumables = arr[3].replace('"', '')
            comparison = arr[4].replace('"', '')
            time = arr[5].replace('"', '')

            if user_id not in _external_data:
                _external_data[user_id] = {}

            _external_data[user_id][time] = {
                "特征": feature,
                "效率": efficiency,
                "消耗": consumables,
                "对比": comparison,
            }
    _data_loaded = True


@tool("generate_external_data")
def generate_external_data() -> str:
    """无入参。获取当前系统中记录的所有用户的全家桶使用行为数据（返回 JSON 格式的字符串）。"""
    _load_external_data()
    return json.dumps(_external_data, ensure_ascii=False)


@tool("fetch_external_data", args_schema=FetchExternalDataInput)
def fetch_external_data(user_id: str, month: str) -> str:
    """
    明确查询某个用户在特定月份的系统使用记录时调用。
    注意：只允许查询格式为 YYYY-MM 的月份。如果返回空结果，说明该月无记录，不要更换无效格式重试。
    """
    _load_external_data()
    try:
        data = _external_data[user_id][month]
        lines = [f"{k}: {v}" for k, v in data.items()]
        return "\n".join(lines)
    except KeyError:
        logger.warning(f"[fetch_external_data] 未找到用户 {user_id} 在 {month} 的记录")
        return f"查询成功，系统内无用户 {user_id} 在 {month} 的相关数据记录。请直接回复用户无数据。"
    except Exception as e:
        return f"工具查询异常: {str(e)}。请放弃本次调用。"


@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为提示词切换提供上下文信息")
def fill_context_for_report():
    """
    此工具主要作为一个 'Signal' (信号)。
    Agent 调用它意味着它现在想要进入 '报告生成模式'。
    【重要提醒】：生成完报告后，请记得一定要调用 `update_report_suggestions` 来把建议提炼并固化到数据库！
    """
    return "fill_context_for_report已调用，中间件已感知并切换提示词逻辑"

"""
Conversation Flow Router — LLM judges which flow & depth the user is in.
Injects contextual prompt guidance for each flow.
"""
import json
from typing import Optional

FLOW_PROMPTS = {
    "school_search": {
        0: "学生在考虑选校，还没有明确条件。引导学生说出专业方向、语言要求、地域偏好。",
        1: "学生有了一些方向，正在筛选。帮ta缩小范围。当条件够了（≥2条），建议去广场筛选。",
        2: "条件足够。回复中附带 plaza_action 邀请去广场查看。",
    },
    "professor_contact": {
        0: "学生在了解套磁。问ta目标学校和教授。",
        1: "学生在套磁中。帮ta写邮件、跟进时间线。",
        2: "可以提醒学生：超过2周未回复建议跟进或换教授。",
    },
    "application": {
        0: "学生在了解出愿。问ta哪所学校、什么专业。",
        1: "学生在准备出愿材料。帮ta梳理清单和截止日。",
        2: "可以提醒：确认截止日期，检查材料是否齐备。",
    },
    "exam_prep": {
        0: "学生在了解考试。问ta目标学校和考试类型。",
        1: "学生在备考。给复习建议、过去问方向。",
        2: "可以模拟面试或提醒考试日期。",
    },
    "general": {
        0: "闲聊或知识问答。正常回复即可。",
    },
}

ROUTER_PROMPT = """分析最近对话，判断学生当前在做什么。

最近对话：
{conversation}

输出 JSON（只输出 JSON，不要解释）：
{{
  "flow": "school_search | professor_contact | application | exam_prep | general",
  "depth": 0 | 1 | 2
}}

flow 判断标准：
- school_search：在找学校、筛选、对比院校
- professor_contact：在聊套磁、教授、发邮件
- application：在聊出愿、材料、截止日
- exam_prep：在聊考试、备考、面试
- general：闲聊、知识问答、其他

depth 判断标准：
- 0：刚开始聊这个主题，还没有具体信息
- 1：有了具体方向/学校/条件，正在深入
- 2：条件已明确，可以执行动作（弹卡片/提醒/确认）

JSON:"""


class ConversationRouter:
    """Stateless router — judges flow + depth from conversation history."""

    def route(self, history: list[str], chat_model) -> dict:
        """Call LLM to determine current flow and depth from last 5 turns."""
        if not chat_model:
            return {"flow": "general", "depth": 0, "prompt": ""}

        conversation = "\n---\n".join(history[-5:]) if history else "（新对话）"

        try:
            resp = chat_model.invoke(ROUTER_PROMPT.format(conversation=conversation))
            text = resp.content if hasattr(resp, "content") else str(resp)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            result = json.loads(text.strip())
        except Exception:
            result = {"flow": "general", "depth": 0}

        flow = result.get("flow", "general")
        depth = result.get("depth", 0)
        prompt = FLOW_PROMPTS.get(flow, FLOW_PROMPTS["general"]).get(depth, "")

        return {"flow": flow, "depth": depth, "prompt": prompt}


router = ConversationRouter()

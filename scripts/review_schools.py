"""审批待审核学校(verified=False)的 CLI 工具。

自动入库隔离(P0)后,LLM/web 自动入库的学校一律 pending,不进正式目录。
本脚本是审批入口:列出 pending,交互式通过 / 拒绝。

用法:
  python scripts/review_schools.py          # 交互式逐个审批
  python scripts/review_schools.py --list   # 只列出,不审批

注意:审批后需重启 FastAPI 服务(sudo systemctl restart jp-agent)学生端才会可见,
因为服务器在内存里缓存了学校目录(SCHOOL_CATALOG)。
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.school_database import get_all_schools, set_school_verified, delete_school
from utils.logger_handler import logger


def list_pending():
    """返回所有 verified=False 的学校(即待审批)。"""
    schools = get_all_schools(include_unverified=True)
    return [s for s in schools if not s.verified]


def print_school(i: int, s):
    print(f"\n[{i}] {s.name}")
    print(f"    来源: {s.source} | 学位: {s.degree} | JLPT: {s.jlpt_min or '不要求'}")
    if s.majors:
        print(f"    专业: {', '.join(s.majors)}")
    if s.exam:
        print(f"    考试: {s.exam}")
    if s.notes:
        print(f"    备注: {s.notes}")


def main():
    only_list = "--list" in sys.argv
    pending = list_pending()

    if not pending:
        print("没有待审核的学校。")
        return

    print(f"待审核学校: {len(pending)} 所\n")

    for i, s in enumerate(pending, 1):
        print_school(i, s)
        if only_list:
            continue
        while True:
            choice = input("  通过(a) / 拒绝并删除(r) / 跳过(s) / 退出(q)? ").strip().lower()
            if choice in ("a", "通过", "approve"):
                ok = set_school_verified(s.name, True)
                print(f"  -> 已通过: {s.name}" if ok else f"  -> 通过失败: {s.name}")
                break
            elif choice in ("r", "拒绝", "reject"):
                ok = delete_school(s.name)
                print(f"  -> 已删除: {s.name}" if ok else f"  -> 删除失败: {s.name}")
                break
            elif choice in ("s", "跳过", "skip"):
                print("  -> 跳过")
                break
            elif choice in ("q", "退出", "quit"):
                print("退出")
                return
            else:
                print("  输入无效,请输入 a / r / s / q")

    print("\n完成。若通过了学校,记得重启 FastAPI 使其对学生端可见。")


if __name__ == "__main__":
    main()

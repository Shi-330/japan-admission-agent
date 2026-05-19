"""
结构化的日本大学院/学部申请数据库。

这份数据应该是私塾老师手工维护的，不是 LLM 生成的。
每个字段都是确定性信息，不依赖 AI 推测。
"""

JLPT_RANK = {"N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5}

SCHOOLS = [
    {
        "name": "早稻田大学 经济学研究科",
        "degree": "修士（硕士）",
        "jlpt_min": "N2",
        "eju_min": 260,
        "eju_subjects": ["日语", "数学1"],
        "gpa_min": 2.5,
        "english_note": "TOEFL iBT 80+ 或 TOEIC 750+",
        "deadlines": {
            "4月入学": "前年10月",
            "9月入学": "当年4月",
        },
        "exam": "笔试（经济学基础）+ 面试",
        "capacity": "约15人/年（外国人）",
        "notes": "重视研究计划书质量。近年不要求提交英语成绩但建议有。",
    },
    {
        "name": "庆应义塾大学 经济学研究科",
        "degree": "修士（硕士）",
        "jlpt_min": "N1",
        "eju_min": 300,
        "eju_subjects": ["日语", "数学1", "综合科目"],
        "gpa_min": 3.0,
        "english_note": "TOEFL iBT 85+（必需）",
        "deadlines": {
            "4月入学": "前年9月",
            "9月入学": "当年3月",
        },
        "exam": "书类审查 + 面试（部分年份取消笔试）",
        "capacity": "约10人/年（外国人）",
        "notes": "重视出身校和GPA。研究计划书需要与教授方向匹配。",
    },
    {
        "name": "东京大学 经济学研究科",
        "degree": "修士（硕士）",
        "jlpt_min": "N1",
        "eju_min": 340,
        "eju_subjects": ["日语", "数学1", "综合科目"],
        "gpa_min": 3.5,
        "english_note": "TOEFL iBT 90+ 或 IELTS 7.0+",
        "deadlines": {
            "4月入学": "前年7月",
            "9月入学": "当年1月",
        },
        "exam": "笔试（经济学综合+数学）+ 面试",
        "capacity": "约5人/年（外国人）",
        "notes": "竞争极激烈。笔试难度高，需重点准备微观宏观经济学。",
    },
    {
        "name": "一桥大学 经济学研究科",
        "degree": "修士（硕士）",
        "jlpt_min": "N1",
        "eju_min": 300,
        "eju_subjects": ["日语", "数学1"],
        "gpa_min": 3.0,
        "english_note": "TOEFL iBT 80+",
        "deadlines": {
            "4月入学": "前年8月",
            "9月入学": "当年2月",
        },
        "exam": "笔试（经济学）+ 面试",
        "capacity": "约8人/年（外国人）",
        "notes": "经济学研究实力强。教授人均学生少，指导质量高。",
    },
    {
        "name": "明治大学 经济学研究科",
        "degree": "修士（硕士）",
        "jlpt_min": "N2",
        "eju_min": 240,
        "eju_subjects": ["日语", "数学1"],
        "gpa_min": 2.2,
        "english_note": "TOEFL iBT 70+ 或 TOEIC 650+",
        "deadlines": {
            "4月入学": "前年10月",
            "9月入学": "当年4月",
        },
        "exam": "书类审查 + 面试",
        "capacity": "约20人/年（外国人）",
        "notes": "要求相对宽松，适合保底选择。",
    },
    {
        "name": "立教大学 经济学研究科",
        "degree": "修士（硕士）",
        "jlpt_min": "N2",
        "eju_min": 240,
        "eju_subjects": ["日语"],
        "gpa_min": 2.0,
        "english_note": "不强制要求，但建议 TOEIC 600+",
        "deadlines": {
            "4月入学": "前年11月",
            "9月入学": "当年5月",
        },
        "exam": "面试（无笔试）",
        "capacity": "约25人/年（外国人）",
        "notes": "无笔试，面试为主。对研究计划书更看重。",
    },
    {
        "name": "京都大学 经济学研究科",
        "degree": "修士（硕士）",
        "jlpt_min": "N1",
        "eju_min": 320,
        "eju_subjects": ["日语", "数学1", "综合科目"],
        "gpa_min": 3.2,
        "english_note": "TOEFL iBT 85+",
        "deadlines": {
            "4月入学": "前年8月",
        },
        "exam": "笔试（经济学理论+数学）+ 面试",
        "capacity": "约6人/年（外国人）",
        "notes": "教授制。须事先联系教授并获得内诺。",
    },
]

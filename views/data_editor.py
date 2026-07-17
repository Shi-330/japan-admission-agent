"""
学校数据管理页面：录入、编辑、验证真实院校数据。
V2 schema: School Pydantic 模型，对应 schools 表新列。
"""
import json
import streamlit as st
from demo.school_database import School, get_all_schools, upsert_school, get_schools_by_major
from utils.logger_handler import logger


def render_data_editor():
    st.title("学校数据库管理 V2")
    st.caption("这里的数据应该是真实的——手工录入或从官网采集，不是 LLM 编的。")

    tab1, tab2 = st.tabs(["录入/编辑", "浏览/搜索"])

    with tab1:
        st.subheader("新增或编辑学校")
        mode = st.radio("模式", ["新增", "编辑已有"], horizontal=True)

        if mode == "编辑已有":
            existing = get_all_schools()
            selected_name = st.selectbox("选择学校", [s.name for s in existing] if existing else ["(无)"])
            if selected_name != "(无)":
                selected = next((s for s in existing if s.name == selected_name), None)
            else:
                selected = None
        else:
            selected = None

        with st.form("school_form"):
            name = st.text_input("学校+研究科全称 *", selected.name if selected else "",
                                 placeholder="大阪大学 情報科学研究科")
            col1, col2 = st.columns(2)
            with col1:
                degree = st.selectbox("学位", ["修士", "学部", "博士"],
                                      index=["修士","学部","博士"].index(selected.degree) if selected else 0)
                jlpt_min = st.selectbox("JLPT最低要求", ["", "N1","N2","N3","N4","N5"],
                                        index=["","N1","N2","N3","N4","N5"].index(selected.jlpt_min) if selected and selected.jlpt_min in ["","N1","N2","N3","N4","N5"] else 0)
                gpa_min = st.number_input("GPA最低要求 (4.0制, 0=不设线)", 0.0, 4.0,
                                          selected.gpa_min if selected else 0.0, 0.1)
            with col2:
                # English requirement as JSON text
                default_eng = json.dumps(selected.english_req, ensure_ascii=False) if selected else '{"required": false}'
                eng_req_text = st.text_input("英语要求 (JSON)",
                                             default_eng,
                                             placeholder='{"type":"TOEFL","min":80,"required":true}')
                majors_text = st.text_input("专业 (逗号分隔)",
                                            ", ".join(selected.majors) if selected else "",
                                            placeholder="情報工学, コンピュータ科学")
                tags_text = st.text_input("标签 (逗号分隔)",
                                          ", ".join(selected.tags) if selected else "",
                                          placeholder="情報, 英語必要")

            st.divider()
            st.caption("出愿 & 考试信息")

            # Deadlines as JSON text
            default_dl = json.dumps(selected.deadlines, ensure_ascii=False) if selected else '[]'
            deadlines_text = st.text_area("截止日期 (JSON数组)",
                                           default_dl,
                                           placeholder='[{"name":"出願","start":"2026-12-10","end":"2027-01-09"}]')
            exam = st.text_area("考试形式",
                                selected.exam if selected else "",
                                placeholder="口頭試問+書類審査")

            notes = st.text_area("内部备注",
                                 selected.notes if selected else "",
                                 placeholder="6専攻。受入教員の承認印必須。")
            source = st.selectbox("数据来源", ["manual", "official", "crawled", "imported"],
                                  index=["manual","official","crawled","imported"].index(selected.source) if selected and selected.source in ["manual","official","crawled","imported"] else 0)
            verified = st.checkbox("已验证", selected.verified if selected else False)

            if st.form_submit_button("保存到数据库"):
                if not name.strip():
                    st.error("学校名称不能为空")
                else:
                    try:
                        # Parse JSON fields
                        try:
                            english_req = json.loads(eng_req_text.strip()) if eng_req_text.strip() else {"required": False}
                        except json.JSONDecodeError:
                            st.error("英语要求 JSON 格式错误")
                            return

                        try:
                            deadlines = json.loads(deadlines_text.strip()) if deadlines_text.strip() else []
                            if not isinstance(deadlines, list):
                                st.error("截止日期必须是 JSON 数组")
                                return
                        except json.JSONDecodeError:
                            st.error("截止日期 JSON 格式错误")
                            return

                        majors = [m.strip() for m in majors_text.split(",") if m.strip()]
                        tags = [t.strip() for t in tags_text.split(",") if t.strip()]

                        s = School(
                            name=name, degree=degree,
                            majors=majors, tags=tags,
                            exam=exam, notes=notes,
                            jlpt_min=jlpt_min, gpa_min=gpa_min,
                            english_req=english_req,
                            deadlines=deadlines,
                            source=source, verified=verified,
                        )
                        upsert_school(s)
                        st.success(f"已保存: {name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存失败: {e}")

    with tab2:
        st.subheader("现有数据")
        search_major = st.text_input("按专业搜索", "")
        if search_major:
            schools = get_schools_by_major(search_major)
        else:
            schools = get_all_schools()

        st.metric("总计", f"{len(schools)} 所学校")

        for s in schools:
            verified_badge = "[已验证]" if s.verified else "[未验证]"
            with st.expander(f"{s.name}  {verified_badge} [{s.source}]"):
                st.write(f"学位: {s.degree} | JLPT: {s.jlpt_min or '不要求'} | GPA: {s.gpa_min or '不设线'}")
                eng = s.english_req or {}
                st.write(f"英语: {eng.get('type', '不要求')}{' ' + str(eng.get('min', '')) if eng.get('min') else ''}{' (必需)' if eng.get('required') else ' (不强制)'}")
                st.write(f"考试: {s.exam}")
                if s.majors:
                    st.write(f"专业: {', '.join(s.majors)}")
                if s.tags:
                    st.write(f"标签: {', '.join(s.tags)}")
                if s.deadlines:
                    st.write("截止日期:")
                    for dl in s.deadlines:
                        date_str = dl.get("date", "") or (f"{dl.get('start','')} ~ {dl.get('end','')}" if dl.get("start") else "")
                        raw_str = dl.get("raw", "")
                        st.write(f"  - {dl.get('name','')}: {date_str or raw_str}")
                if s.notes:
                    st.info(s.notes)

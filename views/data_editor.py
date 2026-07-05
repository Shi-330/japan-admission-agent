"""
学校数据管理页面：录入、编辑、验证真实院校数据。
访问方式：在 app.py 中切换到此页面，或直接访问 /data_editor
"""
import streamlit as st
from demo.school_database import School, get_all_schools, upsert_school, get_schools_by_major


def render_data_editor():
    st.title("学校数据库管理")
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
                                 placeholder="早稻田大学 经济学研究科")
            col1, col2 = st.columns(2)
            with col1:
                degree = st.selectbox("学位", ["修士", "学部", "博士"],
                                      index=["修士","学部","博士"].index(selected.degree) if selected else 0)
                jlpt_min = st.selectbox("JLPT最低要求", ["N1","N2","N3","N4","N5"],
                                        index=["N1","N2","N3","N4","N5"].index(selected.jlpt_min) if selected else 1)
                eju_min = st.number_input("EJU最低分", 0, 800,
                                          selected.eju_min if selected else 0)
                gpa_min = st.number_input("GPA最低要求", 0.0, 4.0,
                                          selected.gpa_min if selected else 0.0, 0.1)
            with col2:
                eju_subjects = st.text_input("EJU科目 (逗号分隔)",
                                             selected.eju_subjects if selected else "",
                                             placeholder="日语,数学1")
                english_note = st.text_input("英语要求",
                                             selected.english_note if selected else "",
                                             placeholder="TOEFL iBT 80+")
                target_major = st.text_input("专业关键词",
                                             selected.target_major if selected else "",
                                             placeholder="经济学/计算机/社会学")

            st.divider()
            st.caption("出愿 & 考试信息")
            col3, col4 = st.columns(2)
            with col3:
                deadline_april = st.text_input("4月入学 出愿截止",
                                               selected.deadline_april if selected else "",
                                               placeholder="前年10月")
                deadline_september = st.text_input("9月入学 出愿截止",
                                                   selected.deadline_september if selected else "",
                                                   placeholder="当年4月")
            with col4:
                exam = st.text_area("考试形式",
                                    selected.exam if selected else "",
                                    placeholder="笔试（经济学基础）+ 面试")
                capacity = st.text_input("外国人定员",
                                         selected.capacity if selected else "",
                                         placeholder="约15人/年")

            notes = st.text_area("内部备注（私塾经验）",
                                 selected.notes if selected else "",
                                 placeholder="重视研究计划书质量。田中教授偏好定量方向。")
            source = st.selectbox("数据来源", ["manual", "official", "crawled", "imported"],
                                  index=["manual","official","crawled","imported"].index(selected.source) if selected else 0)
            verified = st.checkbox("已验证", selected.verified if selected else False)

            if st.form_submit_button("保存到数据库"):
                if not name.strip():
                    st.error("学校名称不能为空")
                else:
                    s = School(
                        name=name, degree=degree, jlpt_min=jlpt_min, eju_min=eju_min,
                        eju_subjects=eju_subjects, gpa_min=gpa_min,
                        english_note=english_note,
                        deadline_april=deadline_april,
                        deadline_september=deadline_september,
                        exam=exam, capacity=capacity, notes=notes,
                        source=source, target_major=target_major, verified=verified,
                    )
                    try:
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
            with st.expander(f"{s.name}  [已验证] [{s.source}]" if s.verified else f"{s.name}  [未验证] [{s.source}]"):
                st.write(f"学位: {s.degree} | JLPT: {s.jlpt_min} | EJU: {s.eju_min} | GPA: {s.gpa_min}")
                st.write(f"英语: {s.english_note}")
                st.write(f"4月截止: {s.deadline_april} | 9月截止: {s.deadline_september}")
                st.write(f"考试: {s.exam} | 定员: {s.capacity}")
                st.write(f"专业: {s.target_major}")
                if s.notes:
                    st.info(s.notes)

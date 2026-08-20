"""
文档抽取:募集要項 PDF/Excel → 文本 → LLM 提炼「出願必要書類」材料清单。

只处理数字文字版文档(非扫描件)。表格用 pdfplumber 抽列结构,LLM 从结构化文本还原。
"""
import io
import re
import json
from utils.logger_handler import logger


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """PDF → 文本。优先 pdfplumber 抽表格(募集要項常有「出願書類」表),失败回退 pypdf。

    表格渲染为 `列 | 列` 行并加【表】标记,且排在正文之前——保证后续 LLM 截断时
    优先保留关键表格内容。非表格正文作为上下文附后。
    """
    text = _extract_pdf_with_pdfplumber(pdf_bytes)
    if text:
        return text
    return _extract_pdf_with_pypdf(pdf_bytes)


def _extract_pdf_with_pdfplumber(pdf_bytes: bytes) -> str:
    """pdfplumber 抽取:表格优先(结构化),正文兜底(补章节标题/备注)。"""
    try:
        import pdfplumber
        tables_out, body_out = [], []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    rows = []
                    for row in table:
                        cells = [(c or "").replace("\n", " ").replace("\r", " ").strip() for c in row]
                        if any(cells):
                            rows.append(" | ".join(cells))
                    if rows:
                        tables_out.append("【表】\n" + "\n".join(rows))
                txt = (page.extract_text() or "").strip()
                if txt:
                    body_out.append(txt)
        # 表格在前(关键信息),正文在后;重复内容由 LLM 自行去重。
        return "\n\n".join(tables_out + body_out).strip()
    except Exception as e:
        logger.warning(f"pdfplumber 抽取失败, 回退 pypdf: {e}")
        return ""


def _extract_pdf_with_pypdf(pdf_bytes: bytes) -> str:
    """pypdf 兜底:纯线性文本(无表格结构)。"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text.strip()
    except Exception as e:
        logger.warning(f"PDF 文本抽取失败: {e}")
        return ""


def extract_excel_text(excel_bytes: bytes) -> str:
    """Excel → 文本(pandas + openpyxl)。每个 sheet 转成 CSV 文本,保留表格结构。"""
    try:
        import pandas as pd
        xls = pd.ExcelFile(io.BytesIO(excel_bytes))
        parts = []
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            parts.append(f"【シート: {sheet}】")
            parts.append(df.astype(str).to_csv(index=False))
        return "\n".join(parts)
    except Exception as e:
        logger.warning(f"Excel 文本抽取失败: {e}")
        return ""


def extract_materials(text: str, chat_model) -> list[dict]:
    """LLM 从募集要項文本提炼「出願必要書類」材料清单。

    返回 [{"name": str, "category": str, "required": bool}]。
    """
    if not text or len(text.strip()) < 20:
        return []

    prompt = f"""以下は日本大学院の募集要項から抽出したテキストです。修士課程の出願に必要な書類（提出物）をリストアップしてください。

テキスト中の【表】以降は表の行で、` | ` が列区切りです（例：「入学願書 | 必須 | 所定用紙」）。左端の列が書類名であることが多い。表と重複する本文は無視してよい。

【テキスト（先頭6000字）】
{text[:6000]}

以下のJSON形式で返してください（markdownコードブロック禁止）：
{{"materials":[{{"name":"入学願書","category":"書類","required":true}}]}}

規則：
- name は書類の正式名称（例：入学願書、成績証明書、研究計画書、推薦書、在留カード写し、検定料納付書）
- category は 書類/証明書/成績/その他 のいずれか
- required は true/false（「任意」「該当者のみ」「必要な場合」は false）
- 明記された「必要」な書類だけを抽出。推測・不明なものは含めない。
- 最大20件。

JSON:"""
    try:
        resp = chat_model.invoke(prompt)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return []
        data = json.loads(m.group(0))
        materials = data.get("materials", [])
        return [
            {
                "name": str(item.get("name", "")).strip(),
                "category": str(item.get("category", "書類")),
                "required": bool(item.get("required", True)),
            }
            for item in materials
            if item.get("name")
        ]
    except Exception as e:
        logger.warning(f"材料提取失败: {e}")
        return []

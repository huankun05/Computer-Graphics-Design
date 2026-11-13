# -*- coding: utf-8 -*-
"""
=====================================================================
 gen_report2.py — 生成《计算机图形学》上机实验报告（Word）· 实验二
=====================================================================
格式对齐《计算机图形学上机实验报告模板.doc》：
  A4、上下 2.54cm / 左右 3.17cm，页眉 1.5cm、页脚 1.75cm；
  封面：校名标识 + 楷体 26pt 标题 + 16/15pt 信息栏；
  （版式工具函数与 gen_report.py（实验一）保持一致，改动请同步）；
  正文：宋体 10.5pt、1.25 倍行距、首行缩进 2 字符；
  一级标题宋体 12pt 加粗，二级标题宋体 12pt，三级标题 10.5pt 加粗；
  图/表题宋体 9pt；三线表；代码 Consolas 9pt。
  页眉（封面除外）居中 + 下边框，页脚“第 X 页 共 Y 页”；
  图、表编号用 SEQ 域，正文交叉引用用 REF 域，目录用 TOC 域。
生成的 docx 打开时 Word 会提示更新域（选“是”即可刷新目录/编号）。
=====================================================================
"""

import os

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "运行截图")
ASSETS = os.path.join(BASE, "assets")
OUT = os.path.join(os.path.dirname(BASE), "实验报告二_李焕锟.docx")

FONT_CN = "宋体"
FONT_EN = "Times New Roman"
FONT_KAI = "楷体"
FONT_MONO = "Consolas"

doc = Document()

# ---------------------------------------------------------------------
# 页面与默认样式
# ---------------------------------------------------------------------
sec = doc.sections[0]
sec.page_width = Cm(21.0)
sec.page_height = Cm(29.7)
sec.top_margin = Cm(2.54)
sec.bottom_margin = Cm(2.54)
sec.left_margin = Cm(3.17)
sec.right_margin = Cm(3.17)
sec.header_distance = Cm(1.5)
sec.footer_distance = Cm(1.75)
sec.different_first_page_header_footer = True

normal = doc.styles["Normal"]
normal.font.name = FONT_EN
normal.font.size = Pt(10.5)
normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT_CN)
normal.paragraph_format.line_spacing = 1.25
normal.paragraph_format.space_before = Pt(0)
normal.paragraph_format.space_after = Pt(0)

_bm_id = [100]
_fig_no = [0]
_tab_no = [0]


def set_font(run, cn=FONT_CN, en=FONT_EN, size=10.5, bold=False,
             color=None, italic=False):
    run.font.name = en
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:ascii"), en)
    rFonts.set(qn("w:hAnsi"), en)
    rFonts.set(qn("w:eastAsia"), cn)


def set_outline(p, level):
    pPr = p._p.get_or_add_pPr()
    ol = OxmlElement("w:outlineLvl")
    ol.set(qn("w:val"), str(level - 1))
    pPr.append(ol)


def add_text(p, text, size=10.5, bold=False, cn=FONT_CN, en=FONT_EN,
             color=None, italic=False):
    run = p.add_run(text)
    set_font(run, cn=cn, en=en, size=size, bold=bold, color=color,
             italic=italic)
    return run


def add_field(p, instr, placeholder, bookmark=None, size=10.5):
    """插入复杂域；bookmark 可选，包住整个域以便 REF 交叉引用。"""
    bid = str(_bm_id[0])
    if bookmark:
        _bm_id[0] += 1
        st = OxmlElement("w:bookmarkStart")
        st.set(qn("w:id"), bid)
        st.set(qn("w:name"), bookmark)
        p._p.append(st)

    run = p.add_run()
    set_font(run, size=size)
    el = OxmlElement("w:fldChar")
    el.set(qn("w:fldCharType"), "begin")
    run._r.append(el)

    run = p.add_run()
    set_font(run, size=size)
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    run._r.append(it)

    run = p.add_run()
    set_font(run, size=size)
    el = OxmlElement("w:fldChar")
    el.set(qn("w:fldCharType"), "separate")
    run._r.append(el)

    add_text(p, str(placeholder), size=size)

    run = p.add_run()
    set_font(run, size=size)
    el = OxmlElement("w:fldChar")
    el.set(qn("w:fldCharType"), "end")
    run._r.append(el)

    if bookmark:
        en_el = OxmlElement("w:bookmarkEnd")
        en_el.set(qn("w:id"), bid)
        p._p.append(en_el)


def add_ref(p, kind, n, size=10.5):
    label, prefix = ("图", "Fig") if kind == "fig" else ("表", "Tab")
    add_text(p, label + " ", size=size)
    add_field(p, f" REF {prefix}{n} \\h ", n, size=size)


def cite(p, text):
    """正文中的参考文献引用，上标形式，如 [1][2]。"""
    run = p.add_run(text)
    set_font(run, size=10.5)
    run.font.superscript = True


def h1(text, size=12, page_break=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(12)
    pf.space_after = Pt(6)
    pf.keep_with_next = True
    pf.page_break_before = page_break
    set_outline(p, 1)
    add_text(p, text, size=size, bold=True)
    return p


def h2(text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(8)
    pf.space_after = Pt(4)
    pf.keep_with_next = True
    set_outline(p, 2)
    add_text(p, text, size=12)
    return p


def h3(text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(6)
    pf.space_after = Pt(3)
    pf.keep_with_next = True
    set_outline(p, 3)
    add_text(p, text, size=10.5, bold=True)
    return p


def body(text, indent=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = align
    pf.first_line_indent = Pt(21) if indent else Pt(0)
    add_text(p, text)
    return p


def body_rich(parts, indent=True):
    """parts 元素为 str 或 ('fig', n) / ('tab', n)。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.first_line_indent = Pt(21) if indent else Pt(0)
    for it in parts:
        if isinstance(it, tuple):
            add_ref(p, it[0], it[1])
        else:
            add_text(p, it)
    return p


def formula(text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.space_before = Pt(3)
    pf.space_after = Pt(3)
    add_text(p, text, en=FONT_EN, italic=False)
    return p


def _code_chunk(lines, first, last):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.35)
    pf.right_indent = Cm(0.15)
    pf.space_before = Pt(4) if first else Pt(0)
    pf.space_after = Pt(6) if last else Pt(0)
    pf.line_spacing = 1.0
    pf.keep_together = True
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "6")
    left.set(qn("w:color"), "4F6EF7")
    pBdr.append(left)
    pPr.append(pBdr)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "F7F8FA")
    pPr.append(shd)
    for i, line in enumerate(lines):
        run = p.add_run(line if line.strip() else " ")
        set_font(run, cn=FONT_CN, en=FONT_MONO, size=8.5)
        if i < len(lines) - 1:
            run.add_break()
    return p


def add_code(code):
    """按空行把代码切成逻辑块，避免出现孤行，同时允许块间自然分页。"""
    lines = code.strip("\n").split("\n")
    chunks, cur = [], []
    for line in lines:
        cur.append(line)
        if not line.strip():
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    for i, ch in enumerate(chunks):
        _code_chunk(ch, i == 0, i == len(chunks) - 1)


def add_figure(key, caption, width_cm):
    _fig_no[0] += 1
    n = _fig_no[0]
    path = os.path.join(SHOTS, key)
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.space_before = Pt(6)
    pf.space_after = Pt(3)
    pf.line_spacing = 1.0
    pf.keep_with_next = True
    p.add_run().add_picture(path, width=Cm(width_cm))

    cap = doc.add_paragraph()
    cpf = cap.paragraph_format
    cpf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cpf.space_before = Pt(0)
    cpf.space_after = Pt(8)
    cpf.line_spacing = 1.0
    add_text(cap, "图 ", size=9)
    add_field(cap, " SEQ 图 \\* ARABIC ", n, bookmark=f"Fig{n}", size=9)
    add_text(cap, "　" + caption, size=9)
    return n


def _cell_margins(table):
    tblPr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, w in (("top", 28), ("bottom", 28), ("left", 85),
                    ("right", 85)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(w))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def _three_line(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge, sz in (("top", 12), ("bottom", 12)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    for edge in ("left", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0")
        borders.append(el)
    tblPr.append(borders)


def _header_row_line(table):
    for cell in table.rows[0].cells:
        tcPr = cell._tc.get_or_add_tcPr()
        tcb = OxmlElement("w:tcBorders")
        el = OxmlElement("w:bottom")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "6")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        tcb.append(el)
        tcPr.append(tcb)


def add_table(caption, headers, rows, widths, center_cols=()):
    _tab_no[0] += 1
    n = _tab_no[0]

    cap = doc.add_paragraph()
    cpf = cap.paragraph_format
    cpf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cpf.space_before = Pt(12)
    cpf.space_after = Pt(3)
    cpf.line_spacing = 1.0
    cpf.keep_with_next = True
    add_text(cap, "表 ", size=9)
    add_field(cap, " SEQ 表 \\* ARABIC ", n, bookmark=f"Tab{n}", size=9)
    add_text(cap, "　" + caption, size=9)

    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    table.style = doc.styles["Table Grid"]
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    for ci, w in enumerate(widths):
        for cell in table.columns[ci].cells:
            cell.width = Cm(w)

    _three_line(table)
    _cell_margins(table)

    def fill(cell, text, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT):
        cell.vertical_alignment = 1       # 垂直居中
        p = cell.paragraphs[0]
        p.paragraph_format.alignment = align
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        add_text(p, text, size=10.5, bold=bold)

    for ci, h in enumerate(headers):
        fill(table.rows[0].cells[ci], h, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER)
    _header_row_line(table)

    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            align = (WD_ALIGN_PARAGRAPH.CENTER if ci in center_cols
                     else WD_ALIGN_PARAGRAPH.LEFT)
            fill(table.rows[ri + 1].cells[ci], str(val), align=align)
        trPr = table.rows[ri + 1]._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        trPr.append(cant)

    # 整张表尽量不跨页：除末行外，所有单元格段落“与下段同页”
    for row in table.rows[:-1]:
        for cell in row.cells:
            for para in cell.paragraphs:
                para.paragraph_format.keep_with_next = True

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.line_spacing = 1.0
    for r in spacer.runs:
        r.font.size = Pt(4)
    return n


# ---------------------------------------------------------------------
# 页眉 / 页脚
# ---------------------------------------------------------------------
def _bottom_border(p):
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    el = OxmlElement("w:bottom")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), "6")
    el.set(qn("w:space"), "1")
    el.set(qn("w:color"), "8C8C8C")
    pBdr.append(el)
    pPr.append(pBdr)


def _clear_runs(p):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)


def _fill_header(section):
    """正文页眉：校名 + 报告名，下边框。"""
    section.header.is_linked_to_previous = False
    hp = section.header.paragraphs[0]
    _clear_runs(hp)
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hp.paragraph_format.space_before = Pt(0)
    hp.paragraph_format.space_after = Pt(0)
    add_text(hp, "中国石油大学（北京）　《计算机图形学》上机实验报告", size=9,
             color=(0x40, 0x40, 0x40))
    _bottom_border(hp)


def _fill_footer(section, roman=False, total=False):
    """页脚：前置部分用罗马数字，正文用阿拉伯数字并按节统计总页数。"""
    section.footer.is_linked_to_previous = False
    fp = section.footer.paragraphs[0]
    _clear_runs(fp)
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.space_before = Pt(0)
    fp.paragraph_format.space_after = Pt(0)
    add_text(fp, "第 ", size=9)
    if roman:
        add_field(fp, " PAGE \\* ROMAN ", "I", size=9)
    else:
        add_field(fp, " PAGE ", "1", size=9)
    add_text(fp, " 页", size=9)
    if total:
        add_text(fp, "　共 ", size=9)
        add_field(fp, " SECTIONPAGES ", "1", size=9)
        add_text(fp, " 页", size=9)


def _set_page_numbering(section, fmt):
    """设置本节页码格式，并从 1 重新起算（如 upperRoman / decimal）。"""
    sectPr = section._sectPr
    for el in sectPr.findall(qn("w:pgNumType")):
        sectPr.remove(el)
    el = OxmlElement("w:pgNumType")
    el.set(qn("w:fmt"), fmt)
    el.set(qn("w:start"), "1")
    sectPr.insert_element_before(
        el, "w:cols", "w:formProt", "w:vAlign", "w:noEndnote", "w:titlePg",
        "w:textDirection", "w:bidi", "w:rtlGutter", "w:docGrid",
        "w:printerSettings", "w:sectPrChange")


# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# 封面
# ---------------------------------------------------------------------
logo_p = doc.add_paragraph()
logo_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
logo_p.paragraph_format.space_before = Pt(6)
logo_p.paragraph_format.space_after = Pt(6)
logo_p.add_run().add_picture(os.path.join(ASSETS, "校名标识.jpeg"),
                             width=Cm(13.5))

for _ in range(2):
    sp = doc.add_paragraph()
    sp.paragraph_format.line_spacing = 1.0

tp = doc.add_paragraph()
tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
tp.paragraph_format.space_before = Pt(12)
tp.paragraph_format.space_after = Pt(12)
add_text(tp, "《计算机图形学》上机实验报告", cn=FONT_KAI, size=26, bold=True)

sp = doc.add_paragraph()
sp.paragraph_format.line_spacing = 1.0

np_ = doc.add_paragraph()
np_.paragraph_format.left_indent = Pt(36)
np_.paragraph_format.line_spacing = 1.3
add_text(np_, "实验名称：", size=15, bold=True)
add_text(np_, "二维几何变换与区域裁剪算法的设计与实现", size=15, bold=True)

for _ in range(4):
    sp = doc.add_paragraph()
    sp.paragraph_format.line_spacing = 1.0

for txt in ("中国石油大学（北京）", "人工智能学院"):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    add_text(p, txt, size=16, bold=True)

for _ in range(2):
    sp = doc.add_paragraph()
    sp.paragraph_format.line_spacing = 1.0

for label, value in (("班　　级：", "计算机23-3"),
                     ("学　　号：", "2023011624"),
                     ("姓　　名：", "李焕锟"),
                     ("完成日期：", "2026 年 11 月 13 日")):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Pt(90)
    p.paragraph_format.space_after = Pt(4)
    add_text(p, label, size=15, bold=True)
    add_text(p, value, size=15, bold=True)

doc.add_section(WD_SECTION.NEW_PAGE)

# ---------------------------------------------------------------------
# 目录（TOC 域，打开时更新）
# ---------------------------------------------------------------------
toc_title = doc.add_paragraph()
toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
toc_title.paragraph_format.space_before = Pt(6)
toc_title.paragraph_format.space_after = Pt(12)
add_text(toc_title, "目　　录", size=16, bold=True)

toc_p = doc.add_paragraph()
toc_p.paragraph_format.line_spacing = 1.5
add_field(toc_p, ' TOC \\o "1-2" \\h \\z \\u ',
          "（目录将在打开文档时自动更新；若未刷新，请按 Ctrl+A 后 F9）", size=10.5)

doc.add_section(WD_SECTION.NEW_PAGE)

# ---------------------------------------------------------------------
# 正文
# ---------------------------------------------------------------------
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(0)
p.paragraph_format.space_after = Pt(10)
add_text(p, "实验二：二维几何变换与区域裁剪", size=14, bold=True)


def pick(*names):
    """按候选顺序取第一个存在的截图文件（文件名变更时不必改全文）。"""
    for n in names:
        if os.path.exists(os.path.join(SHOTS, n)):
            return n
    raise FileNotFoundError(" / ".join(names))


# ------------------------------ 一 ------------------------------
h1("一、实验目的与要求")
body("本实验在第一次实验建立的像素画板平台上继续向前，实现二维几何变换与"
     "区域裁剪两类核心操作：一方面让已经画好的点、线段、曲线与填充图元能够"
     "被交互式地平移、旋转、缩放；另一方面实现线段与多边形的区域裁剪，并"
     "为裁剪过程设计可逐帧观察的动画。具体目的与要求如下：")
for txt in (
    "（1）理解二维仿射变换的矩阵表示：把平移、旋转、缩放统一写成 3×3 "
    "齐次矩阵，掌握“绕定点变换 = 移到原点 → 变换 → 移回”的分解方法，"
    "并能说明复合变换中矩阵相乘次序不可交换的原因；",
    "（2）掌握交互式变换的设计要点：选择模型（单击选中、Shift 加选、"
    "空白框选）、定点选取、八方位手柄的缩放语义、顶部手柄的旋转语义，"
    "以及拖拽反馈与数值面板之间的一致性；",
    "（3）掌握圆与椭圆在任意仿射变换下的参数换算：用协方差矩阵的特征"
    "分解精确求出变换后的半轴与旋转角，理解“圆经非等比缩放后变为椭圆”"
    "这一现象的数学依据；",
    "（4）掌握三种线段裁剪算法——Cohen-Sutherland 编码裁剪、中点分割裁剪"
    "与 Liang-Barsky 参数裁剪——的判定规则、收敛性与适用场合；",
    "（5）掌握两种多边形裁剪算法——Sutherland-Hodgman 逐边裁剪与 "
    "Weiler-Atherton 双边裁剪——的原理，理解“逐边裁剪要求窗口为凸多边形”"
    "这一限制的来源，以及双边裁剪为何能支持凹窗口；",
    "（6）设计裁剪动画：使算法沿图形的真实边界逐段判定、当场挖除，"
    "并保证“演完即所得”——动画末帧与画布上的真实裁剪结果逐像素一致；",
    "（7）把变换与裁剪做成可交互、可回放、可撤销的功能并集成进已有的"
    "应用模式与演示模式，用自动化测试锁定算法与交互行为。",
):
    body(txt)

# ------------------------------ 二 ------------------------------
h1("二、实验内容")

h2("2.1 主要设计思路")
h3("2.1.1 需求分析")
body("本次实验的功能需求可以归结为“变换要准、交互要顺、动画要真、"
     "结果要可撤”四条主线。“变换要准”指任意图元经平移、旋转、缩放后"
     "几何参数必须与解析结果一致，且旋转/缩放的定点可预期；“交互要顺”指"
     "选择、拖拽、数值输入三条路径并存且互相不打架；“动画要真”指演示"
     "过程必须作用在真实图元上，不能用一条与边界无关的辅助线代替；"
     "“结果要可撤”指整组变换与整次裁剪都能一步撤销。需求与功能的对应"
     "关系如")
p = doc.paragraphs[-1]
add_ref(p, "tab", 1)
add_text(p, "所示。")
add_table(
    "需求与功能映射",
    ["需求主线", "具体要求", "实现方式"],
    [
        ["变换要准",
         "任意图元的平移/旋转/缩放，几何参数精确更新",
         "3×3 齐次矩阵统一表示；圆/椭圆用协方差矩阵特征分解换算"],
        ["", "变换定点可预期",
         "统一取“所选图元的包围盒中心”，面板与拖拽共用同一基准"],
        ["交互要顺",
         "鼠标拖拽与数值输入并存",
         "拖拽手柄/包围盒/顶部箭头 + 面板 dx/dy、角度、百分比"],
        ["", "多选与框选",
         "Shift+单击加选减选、空白拖拽框选，整组一起变换"],
        ["", "操作有即时反馈",
         "拖拽时包围盒下方实时显示角度/比例/位移读数"],
        ["动画要真",
         "沿图元真实边界逐段判定",
         "直线按整段、多边形按各边、圆/椭圆按真实栅格轮廓切段"],
        ["", "末帧与真实结果一致",
         "末帧取“窗口外像素集合”，与应用侧浮点几何掩膜同口径"],
        ["结果要可撤",
         "整组变换/整次裁剪一步撤销",
         "命令栈：变换组与挖除组各自封装为一条命令"],
    ],
    widths=[2.6, 5.0, 7.0], center_cols=(0,))

h3("2.1.2 功能设计")
body("程序延续第一次实验的“应用模式 + 演示模式”双模式结构。应用模式是"
     "编辑工作区：新增“二维变换”与“区域裁剪”两个工具；演示模式把每种"
     "算法的底层过程逐帧拆开展示。新增能力与所用算法如")
p = doc.paragraphs[-1]
add_ref(p, "tab", 2)
add_text(p, " 所示。")
add_table(
    "模块三、四的算法与交互能力",
    ["模块", "算法/交互", "关键设计"],
    [
        ["模块三\n二维几何变换",
         "平移 T(dx,dy)", "拖包围盒内平移；面板 dx/dy（dy 正 = 向上）"],
        ["", "旋转 R(θ)", "顶部环形箭头拖拽（Shift 吸附 15°）；定点 = 包围盒中心"],
        ["", "缩放 S(sx,sy)", "8 方位手柄（Shift 等比）；面板恒为等比百分比"],
        ["", "复合变换", "T·T(c)·R·S·T(−c)，五阶段逐阶段动画演示"],
        ["", "圆/椭圆参数换算", "协方差矩阵特征分解；非等比缩放时圆自动变椭圆"],
        ["模块四\n区域裁剪",
         "Cohen-Sutherland 编码裁剪", "4 位区域码，逐轮求交截断"],
        ["", "中点分割裁剪", "不求解析交点，对外端点反复二分"],
        ["", "Liang-Barsky 参数裁剪", "一次循环求出参数区间 [u0,u1]"],
        ["", "Sutherland-Hodgman 逐边裁剪", "窗口 = 半平面之交，要求凸窗口"],
        ["", "Weiler-Atherton 双边裁剪", "进入/离开配对，支持任意简单多边形窗口"],
        ["", "区域挖除", "窗口多边形 → 扫描线掩膜 → 图元像素求交后擦除"],
    ],
    widths=[2.6, 5.2, 6.8], center_cols=(0,))

h3("2.1.3 界面设计")
body("程序的总体架构如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 1)
add_text(p, "所示。自上而下分为表现层、课程模块层、核心层与算法层四层，"
             "外加教学引擎：表现层负责双模式界面；课程模块层把每一次实验"
             "封装成一个独立文件夹（本次为 module03_transform2d 与 "
             "module04_clipping），在各自 module.py 中声明自己，主框架不"
             "写死任何具体实验；核心层负责画布渲染、文档与命令栈、图元模型；"
             "算法层零 GUI 依赖，每个算法同时提供“几何出口”与“步骤流出口”"
             "两路输出，使绘图结果与演示动画共用同一份实现。")
add_figure(pick("fig07_二维变换与裁剪总体架构.png",
                 "fig01_系统总体架构.png"),
           "二维变换与区域裁剪模块的系统总体架构", 14.0)
body("应用模式下的变换交互如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 2)
add_text(p, "所示：左侧是图标工具栏，中间为像素画布，顶部为选项条与"
             "变换数值面板，右栏为颜色、图元、视图三张折叠卡。选中图元后"
             "画布上出现虚线包围盒、八个缩放手柄与顶部旋转手柄，整组图元"
             "共享同一个包围盒，因而多选时变换天然作用于整组。")
add_figure("m3_01_二维变换_选中与手柄.png",
           "应用模式：多选后的包围盒、八方位缩放手柄与顶部旋转手柄", 15.0)
body("变换的数值面板如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 3)
add_text(p, "所示。平移给出 dx、dy 两个独立输入（dy 正值为向上，与数学习"
             "惯一致，画布 y 轴向下由矩阵内部取负）；旋转给出当前累计角，"
             "范围 −360°~360°、一档 1°；缩放给出当前累计比例，范围 "
             "5%~800%、面板恒为等比。三个输入框均支持回车直接应用，"
             "拖拽手柄后数值实时回填，换选则基准归零（0°、100%）。")
add_figure("m3_03_二维变换_数值面板.png",
           "二维变换数值面板：平移 dx/dy、旋转累计角、缩放百分比", 15.0)

h2("2.2 算法流程图和数据结构")
h3("2.2.1 总体处理流程")
body("一次变换或裁剪的完整流程如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 4)
add_text(p, "所示。变换侧：交互事件先确定选区与定点，再构造 3×3 矩阵，"
             "最后作用到图元几何参数并按新参数重新光栅化；裁剪侧：先确定"
             "窗口多边形，再由窗口生成像素掩膜，最后与图元像素求交得到"
             "待擦除集合。两条路径都把最终修改封装为一条命令压入命令栈，"
             "从而天然支持撤销与重做。")
add_figure(pick("fig08_二维变换总体流程.png"),
           "二维变换与区域裁剪的总体处理流程", 11.5)

h3("2.2.2 变换数据结构")
body("程序继续沿用第一次实验的“参数化存储 + 绘制时重新光栅化”架构："
     "图元只保存几何参数而不保存位图，任何变换都只修改参数。变换相关"
     "的核心数据如")
p = doc.paragraphs[-1]
add_ref(p, "tab", 3)
add_text(p, " 所示。")
add_table(
    "变换与裁剪相关的数据结构",
    ["结构", "字段", "说明"],
    [
        ["Shape（基类）", "kind / color / width / visible / fill",
         "所有图元的公共属性"],
        ["", "erased: set[(x,y)]",
         "橡皮擦擦除掩码（像素级语义，按点采样映射）"],
        ["", "cuts: list[多边形]",
         "区域裁剪挖除的【几何区域】，随图元一起变换"],
        ["LineShape", "p0 / p1", "直线端点，变换时直接变换端点"],
        ["CircleShape", "center / r", "圆心与半径；非等比变换时原地转为椭圆"],
        ["EllipseShape", "center / rx / ry / angle",
         "椭圆半轴与主轴旋转角（角度归一到 [0,180)）"],
        ["PolygonShape", "vertices", "顶点表，变换时逐顶点变换"],
        ["Mat3", "3×3 齐次矩阵",
         "作用在列向量 (x, y, 1)ᵀ 上；compose(A,B) = A·B 表示先 B 后 A"],
    ],
    widths=[2.8, 4.6, 7.2])

body("其中 cuts 字段是本实验一个关键设计决定。区域裁剪的语义是“挖掉窗口"
     "覆盖的这片区域”，属于【几何操作】，若只记录被擦像素的坐标（即按点"
     "采样映射），图元变换后会被重新光栅化——圆与椭圆还会按协方差矩阵"
     "解析式重参数化——两者不同源，掩膜就会漏格，被挖掉的区域在旋转后"
     "重新冒出一片黑散点。把窗口多边形本身存进 cuts、随矩阵一起变换，"
     "渲染时再按几何重新求交，挖掉的区域就始终是一块连续区域。"
     "与之相对，橡皮擦是【像素级操作】——掩码必须精确等于被擦掉的那些"
     "像素，因此仍按点采样映射。")

h3("2.2.3 二维仿射矩阵内核")
body("平移、旋转、缩放三种基本变换统一写成 3×3 齐次矩阵，作用在列向量上：")
formula("T(dx, dy) = [ 1  0  dx ]        R(θ) = [ cosθ  −sinθ  0 ]"
        "        S(sx, sy) = [ sx  0  0 ]")
formula("                    [ 0  1  dy ]                [ sinθ   cosθ  0 ]"
        "                        [ 0  0   1 ]                [   0      0   1 ]")
body("画布采用屏幕坐标系（y 轴向下），因此标准旋转矩阵在视觉上表现为顺时针"
     "旋转，θ 为正即顺时针。矩阵复合定义为 compose(A, B) = A·B，作用到点"
     "上时 B 先执行、A 最后执行，这一约定让“复合变换 = 各基本矩阵按序相乘”"
     "的写法与直觉一致。矩阵求逆按仿射矩阵的封闭形式直接写出，并用行列式"
     "判定可逆性。")

h3("2.2.4 绕定点变换的分解")
body("绕定点 c 的线性类变换统一写成 T(c)·M·T(−c)：先把定点搬到原点，"
     "在原点做变换，再把定点搬回来。旋转的分解过程如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 5)
add_text(p, "所示，三个阶段分别对应 M₁ = T(−c)、M₂ = R(θ)·M₁、"
             "M₃ = T(c)·M₂，M₃ 即最终矩阵。演示模式把三个阶段各展开成一段"
             "平滑动画并在阶段末尾停留，使“先搬轴心、再绕原点转、最后搬回”"
             "的过程清晰可见；复合变换则按 T(−c) → S → R → T(c) → T(dx,dy) "
             "五个阶段展开。之所以要分阶段而不是直接给出一个合成矩阵，"
             "是因为五步合成为一个 M 之后，平移、旋转、缩放同时发生，"
             "观众看不出先后次序。")
add_figure(pick("fig09_绕轴心旋转三阶段分解.png"),
           "绕轴心旋转的三阶段分解", 10.0)

h3("2.2.5 椭圆参数的精确换算")
body("圆与椭圆不能像直线那样简单地变换端点：旋转一个圆仍是圆，但非等比"
     "缩放后它应当变成椭圆。为此把椭圆写成参数形式 p(t) = c + R(θ)·"
     "diag(rx, ry)·(cos t, sin t)，令其协方差矩阵为 M = R·diag(rx², ry²)"
     "·Rᵀ。经过线性部分 A 后有 M′ = A·M·Aᵀ；对 M′ 做 2×2 对称矩阵的"
     "特征分解，λ₁、λ₂ 即新半轴的平方，特征向量给出主轴方向。该方法对"
     "旋转、非等比缩放与错切都精确成立，不依赖任何近似。特征值由"
     "λ = (tr ± √(tr² − 4det))/2 求出，特征方向由 tan(2θ) = 2b/(a − d) "
     "求出并归一到 [0°, 180°)。")

h2("2.3 裁剪算法")
h3("2.3.1 Cohen-Sutherland 编码裁剪")
body("Cohen-Sutherland 为每个端点计算一个 4 位区域码，位序为 D₃ 下、"
     "D₂ 上、D₁ 右、D₀ 左。判定只有三条：")
formula("code₀ | code₁ == 0000  → 整段在窗口内，直接接受")
formula("code₀ & code₁ != 0000  →  两端同侧在外，整段舍弃")
formula("否则                 →  取窗口外的那个端点，按其区域码所指"
        "的边界求交截断，重复判定")
body("每轮至少消去区域码中的一位，因此最多四轮必然收敛。流程如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 6)
add_text(p, "所示。演示页把两端点的区域码直接标在画面上，并列出 "
             "code₀ & code₁ 与 code₀ | code₁ 两串二进制，配合红框高亮"
             "当前正在使用的那条边界，使判定过程可逐帧核对。")
add_figure(pick("fig10_Cohen-Sutherland编码裁剪.png"),
           "Cohen-Sutherland 编码裁剪算法流程", 10.5)

h3("2.3.2 中点分割裁剪")
body("中点分割裁剪与 Cohen-Sutherland 共用同一套区域码做接受/舍弃判定，"
     "区别是不求交点的解析式，而是对外端点反复二分：取两端中点 M，算 "
     "M 的区域码，若 M 与外端点同侧则把外端点移到 M，否则把内端点移到 M；"
     "当区间长度不超过一个像素时即达到显示分辨率精度，内端点近似为边界"
     "交点。它的全部运算只有移位与加减，没有乘除法，适合硬件实现，"
     "这也是课程把它与前两者并列讲授的原因。")

h3("2.3.3 Liang-Barsky 参数裁剪")
body("Liang-Barsky 把线段参数化：P(t) = P₀ + t·(P₁ − P₀)，t ∈ [0,1]，"
     "对四条窗口边界依次求 p·t ≤ q，其中 p = (−dx, dx, −dy, dy)、"
     "q = (x₀−rx₀, rx₁−x₀, y₀−ry₀, ry₁−y₀)。p < 0 表示从外进入、"
     "更新下界 u₀ = max(u₀, q/p)；p > 0 表示从内离开、更新上界 "
     "u₁ = min(u₁, q/p)；p = 0 且 q < 0 表示平行在外，整段舍弃。"
     "一旦 u₀ > u₁ 即无交集。与编码裁剪相比，它不需要反复编码求交，"
     "一次循环即求出参数区间，乘除次数固定，是三种算法中效率最高的，"
     "流程如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 7)
add_text(p, "所示。")
add_figure(pick("fig11_Liang-Barsky参数裁剪.png"),
           "Liang-Barsky 参数化裁剪算法流程", 10.5)

h3("2.3.4 Sutherland-Hodgman 逐边裁剪")
body("Sutherland-Hodgman 把裁剪窗口表示成“若干半平面的交”，因此逐边裁剪"
     "要求窗口为凸多边形：凸窗口的每条边对应一个半平面，被裁多边形依次"
     "用每个半平面切一遍。对一条边 (S, E) 的处理分四种情形：两端都在"
     "半平面内则整段保留；一端在外则在交点处截断（交点成为新的端点）；"
     "两端都在外则整段出局。切完所有半平面后剩下的那段就在窗口内。流程如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 8)
add_text(p, "所示。几何出口保留浮点精确交点，取整只发生在栅格化那一步——"
             "否则斜边交点会被整体挪动最多半格，实测三角形与三角形窗口的"
             "交集面积因此少算 5.8 px²（2.4%），也会与应用侧的浮点几何"
             "掩膜对不上。")
add_figure(pick("fig12_Sutherland-Hodgman逐边裁剪.png"),
           "Sutherland-Hodgman 逐边裁剪算法流程", 10.5)

h3("2.3.5 Weiler-Atherton 双边裁剪")
body("Weiler-Atherton 沿双边求解：被裁多边形的边与窗口的边互相求交，"
     "按交点把边切成若干子段，用射线法判断子段中点是否落在对方内部，"
     "并标记交点处是【进入】还是【离开】窗口。交集边界由“被裁多边形的边”"
     "与“窗口的边”交替组成，最后把输出段首尾相接成闭合环。由于窗口不再"
     "需要表示成半平面之交，它可以取任意简单多边形——包括凹的。流程如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 9)
add_text(p, "所示，演示页末尾专门演示“双边的另一半”，即窗口的边落在"
             "主体内部的那几段，与逐边裁剪页并列对照，两种算法的能力差异"
             "一目了然。")
add_figure(pick("fig13_Weiler-Atherton双边裁剪.png"),
           "Weiler-Atherton 双边裁剪算法流程", 10.5)

h3("2.3.6 区域挖除的掩膜生成")
body("应用模式的区域裁剪工具采用“挖除”语义：窗口覆盖的像素从图元上"
     "消失，窗口外的几何保持原样。要判定“窗口到底覆盖了哪些像素”，"
     "程序手写了三步：①内部用扫描线求交、交点按 x 排序两两配对（偶奇规则），"
     "与实验一的扫描线填充是同一套判定，因此凹多边形窗口同样正确；"
     "②边界用 Bresenham 逐像素补入——扫描线按半开区间统计，水平边与"
     "最高顶点所在的那一行不会被内部填充覆盖，必须补边；③按扫描线 y 聚合，"
     "使掩膜可以逐行输出，便于演示模式逐行扫描。最后与图元的轮廓∪填充"
     "像素求交，得到待擦除集合。")

h2("2.4 程序开发与实现")
h3("2.4.1 开发环境与工具")
body("程序使用 Python 3.12 编写，图形界面基于 PySide6（Qt 6）的 QWidget 与 "
     "QPainter 自绘，不依赖 OpenGL 或第三方图形库；算法层为纯 Python，"
     "不导入任何 GUI 模块，可独立测试；最终使用 PyInstaller 以 onefile "
     "模式打包为免安装可执行程序。实验环境如")
p = doc.paragraphs[-1]
add_ref(p, "tab", 4)
add_text(p, " 所示。")
add_table(
    "实验环境",
    ["项目", "配置"],
    [
        ["操作系统", "Windows 11"],
        ["开发语言", "Python 3.12.10"],
        ["图形界面", "PySide6 6.12（Qt for Python，QWidget + QPainter 自绘）"],
        ["打包工具", "PyInstaller（onefile，产物 图形画板.exe）"],
        ["数值与绘图", "标准库 math；流程图用 matplotlib 3.10.6 绘制"],
        ["测试框架", "自建断言式脚本（transform_test / clip_test / smoke_test / "
                     "render_test / algo_verify）"],
    ],
    widths=[3.4, 11.2])

h3("2.4.2 关键源代码")
body("（1）3×3 齐次矩阵内核与绕定点复合。矩阵构造、求逆与复合如下，"
     "compose 按参数从左到右相乘，作用到点上时最右边的矩阵最先执行。")
add_code('''
def rotation(angle_deg: float) -> Mat3:
    """旋转矩阵（屏幕坐标下正角 = 视觉顺时针）。"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0.0),
            (s, c, 0.0),
            (0.0, 0.0, 1.0))


def compose(*mats: Mat3) -> Mat3:
    """按参数从左到右复合：compose(A, B, C) 等价于 A @ B @ C。

    作用到点上时 C 最先执行，A 最后执行。
    """
    out = identity()
    for m in mats:
        out = multiply(out, m)
    return out


def around(pivot: Tuple[float, float], m: Mat3) -> Mat3:
    """把线性/缩放类变换绕 pivot 执行（先移到原点，变换，再移回）。"""
    px, py = float(pivot[0]), float(pivot[1])
    return compose(translation(px, py), m, translation(-px, -py))
''')

body("（2）椭圆在任意仿射变换下的参数换算。对协方差矩阵 M′ = A·M·Aᵀ "
     "做 2×2 对称矩阵特征分解，得到新半轴与主轴方向。")
add_code('''
def ellipse_from_matrix(cx, cy, rx, ry, angle_deg, m: Mat3):
    """把椭圆参数经过仿射矩阵 m 变换，返回新的 (cx, cy, rx, ry, angle)。"""
    ncx, ncy = apply(m, (cx, cy))
    a11, a12 = m[0][0], m[0][1]
    a21, a22 = m[1][0], m[1][1]

    m00, m01, m11 = ellipse_covariance(rx, ry, angle_deg)
    # A·M
    am00 = a11 * m00 + a12 * m01
    am01 = a11 * m01 + a12 * m11
    am10 = a21 * m00 + a22 * m01
    am11 = a21 * m01 + a22 * m11
    # (A·M)·A^T
    n00 = am00 * a11 + am01 * a12
    n01 = am00 * a21 + am01 * a22
    n11 = am10 * a21 + am11 * a22

    # 对称矩阵特征值：λ = (trace ± sqrt(trace^2 - 4det)) / 2
    trace = n00 + n11
    det = n00 * n11 - n01 * n01
    disc = max(0.0, trace * trace - 4.0 * det)
    root = math.sqrt(disc)
    lam1 = max(0.0, (trace + root) / 2.0)     # 大特征值 → 长半轴
    lam2 = max(0.0, (trace - root) / 2.0)     # 小特征值 → 短半轴
    nrx = math.sqrt(lam1)
    nry = math.sqrt(lam2)

    # 主轴方向：tan(2θ) = 2b / (a - d)
    if abs(n01) < _EPS and abs(n00 - n11) < _EPS:
        nangle = 0.0
    else:
        nangle = 0.5 * math.degrees(math.atan2(2.0 * n01, n00 - n11))
    nangle = normalize_angle(nangle)
    return ncx, ncy, nrx, nry, nangle
''')

body("（3）图元几何参数的更新。变换只改参数、不动位图；圆在非等比变换后"
     "原地转成椭圆，撤销时可由快照恢复原类型。")
add_code('''
def transform_shape(shape: "Shape", m: tf.Mat3):
    """对图元做任意仿射变换（就地修改，含擦除掩码）。"""
    _map_erased(shape, m)
    if isinstance(shape, LineShape):
        shape.p0 = _round_point(tf.apply(m, shape.p0))
        shape.p1 = _round_point(tf.apply(m, shape.p1))
    elif isinstance(shape, CircleShape):
        cx, cy, rx, ry, ang = tf.ellipse_from_matrix(
            shape.center[0], shape.center[1], shape.r, shape.r, 0.0, m)
        if abs(rx - ry) <= 0.75:                 # 仍接近正圆 → 保持圆
            shape.center = _round_point((cx, cy))
            shape.r = max(1, int(round((rx + ry) / 2.0)))
        else:                                     # 非等比 → 精确转椭圆
            _replace_circle_with_ellipse(shape, cx, cy, rx, ry, ang)
    elif isinstance(shape, EllipseShape):
        cx, cy, rx, ry, ang = tf.ellipse_from_matrix(
            shape.center[0], shape.center[1], shape.rx, shape.ry,
            getattr(shape, "angle", 0.0), m)
        shape.center = _round_point((cx, cy))
        shape.rx = max(1, int(round(rx)))
        shape.ry = max(1, int(round(ry)))
        shape.angle = tf.normalize_angle(ang)
    elif isinstance(shape, PolygonShape):
        shape.vertices = [_round_point(tf.apply(m, v))
                          for v in shape.vertices]
''')

body("（4）擦除掩码与裁剪区域的分工：橡皮擦按像素中心点映射（掩码必须"
     "精确等于被擦掉的像素），区域裁剪按几何区域随矩阵变换（区域必须始终"
     "连续）。")
add_code('''
def _map_erased(shape: "Shape", m: tf.Mat3):
    """擦除掩码跟随几何一起变换（否则移动后擦除洞会留在原地）。"""
    if shape.erased:
        shape.erased = {_round_point(tf.apply(m, p)) for p in shape.erased}
    if getattr(shape, "cuts", None):
        shape.cuts = [[tf.apply(m, v) for v in poly]
                      for poly in shape.cuts]
''')

body("（5）Cohen-Sutherland 编码裁剪的几何出口。求交时按区域码所指边界"
     "代入直线方程，接受前把四舍五入可能推出半格的坐标钳回窗口内，"
     "保证与步骤流出口逐像素一致。")
add_code('''
def cohen_sutherland(x0, y0, x1, y1, rect):
    """裁剪线段；返回窗口内线段 (x0, y0, x1, y1)，完全在外返回 None。"""
    rx0, ry0, rx1, ry1 = rect
    fx0, fy0, fx1, fy1 = float(x0), float(y0), float(x1), float(y1)
    while True:
        c0 = region_code(fx0, fy0, rect)
        c1 = region_code(fx1, fy1, rect)
        if not (c0 | c1):
            ax, ay = _clamp(int(round(fx0)), rx0, rx1), \\
                _clamp(int(round(fy0)), ry0, ry1)
            bx, by = _clamp(int(round(fx1)), rx0, rx1), \\
                _clamp(int(round(fy1)), ry0, ry1)
            return ax, ay, bx, by
        if c0 & c1:
            return None
        code = c0 if c0 else c1
        px, py = _intersect(fx0, fy0, fx1, fy1, code, rect)
        if code == c0:
            fx0, fy0 = px, py
        else:
            fx1, fy1 = px, py
''')

body("（6）Liang-Barsky 参数化裁剪的几何出口。四条边界各算一次，"
     "乘法除法次数固定。")
add_code('''
def liang_barsky(x0, y1_unused, x1, y1, rect):
    """裁剪线段；返回 (x0, y0, x1, y1)，整段在外返回 None。"""
    rx0, ry0, rx1, ry1 = rect
    dx, dy = float(x1 - x0), float(y1 - y0)
    p = (-dx, dx, -dy, dy)
    q = (x0 - rx0, rx1 - x0, y0 - ry0, ry1 - y0)
    u0, u1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None
            continue
        t = qi / pi
        if pi < 0:
            u0 = max(u0, t)
        else:
            u1 = min(u1, t)
        if u0 > u1:
            return None
    ax = _clamp(int(round(x0 + u0 * dx)), rx0, rx1)
    ay = _clamp(int(round(y0 + u0 * dy)), ry0, ry1)
    bx = _clamp(int(round(x0 + u1 * dx)), rx0, rx1)
    by = _clamp(int(round(y0 + u1 * dy)), ry0, ry1)
    return ax, ay, bx, by
''')

body("（7）Sutherland-Hodgman 逐半平面裁剪的核心。四种情形在循环里被"
     "归约为三条分支，几何出口全程保持浮点精确交点。")
add_code('''
def _clip_geometry(points, planes):
    """逐半平面裁剪：返回裁剪后的顶点（浮点，精确交点）。"""
    out = [(float(x), float(y)) for x, y in points]
    for plane in planes:
        if not out:
            break
        src = out
        out = []
        s = src[-1]
        for e in src:
            s_in = plane.inside(s)
            e_in = plane.inside(e)
            if e_in:
                if not s_in:
                    out.append(plane.intersect(s, e))
                out.append(e)
            elif s_in:
                out.append(plane.intersect(s, e))
            s = e
    return out
''')

body("（8）任意多边形窗口的像素掩膜：扫描线配对求内部 + Bresenham 补边，"
     "两步合成窗口覆盖的像素集合。")
add_code('''
def polygon_mask_steps(vertices):
    """任意多边形（可凹）→ 逐扫描线的掩膜步骤流。"""
    n = len(vertices)
    if n < 3:
        return []
    rows: dict = {}
    # ---- 1. 内部：复用扫描线填充的逐行配对（偶奇规则） ----
    for st in scanline_fill_steps(vertices):
        y = st.values.get("y")
        rows.setdefault(y, set()).update(st.pixels)
    # ---- 2. 边界：Bresenham 补边（水平边 / 最高顶点行） ----
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        for px in bresenham_line(x0, y0, x1, y1):
            rows.setdefault(px[1], set()).add(px)
    # ---- 3. 按 y 递增输出步骤（从上到下逐行扫描） ----
    steps = []
    for y in sorted(rows):
        px = sorted(rows[y])
        steps.append(Step(px, {"y": y, "像素": len(px)},
                          f"扫描线 y={y}：内部配对 + 边界补点，"
                          f"掩膜 {len(px)} 像素"))
    return steps
''')

h3("2.4.3 交互实现中的关键处理")
body("（1）选择模型与“点击手柄优先于 Shift 加选”。单击选中图元，"
     "Shift+单击加选或减选，在空白处拖拽则框选矩形内的图元。判定顺序上"
     "手柄命中优先于 Shift 加选，因此可以先按住 Shift 再抓手柄做等比缩放，"
     "不必松开按键重来。")
body("（2）定点统一为包围盒中心。任何图元（包括圆、椭圆）都先被矩形框住，"
     "旋转与缩放一律以所选图元整体的包围盒中心为定点。这条规则的好处是"
     "可预期：多选时整组图元作为一个整体绕其公共中心变换，不会出现"
     "“各自绕自己中心转、整体散架”的现象。拖拽旋转时包围盒中心会显示"
     "定点标记，角度读数实时显示在包围盒下方。")
body("（3）拖拽预览与整组一步撤销。拖拽过程中只更新幽灵预览层、不写入"
     "底图，松手时才提交；提交时把整组图元的变换前快照打包成一条命令，"
     "因此多选图元的一次变换只需一次 Ctrl+Z 即可整体还原。")
body("（4）裁剪窗口的两种形状。矩形窗口可在画布上拖出，并由 8 个手柄"
     "调整；多边形窗口则在画布上逐点单击布点，点回起点或右键/Enter 闭合，"
     "顶点可逐个拖动。窗口形状的选择同时存在于应用模式的工具面板与"
     "演示模式的参数卡中，两处共用同一份数据。")
body("（5）“挖除”语义与结果累积。区域裁剪挖掉的是窗口【内】的部分，"
     "窗口外的几何保持原样；在同一个图形上换一个窗口再裁一次时，"
     "上一轮已经挖掉的部分保留不动，结果是累积的——只有“重播同一轮动画”"
     "才把上一轮还原重来。判定沿【存活的连续边界】走，不会跨过上一轮"
     "挖空的缺口。")
body("（6）演示模式：逐帧动画 + 决策项监视。裁剪演示的像素层画的始终是"
     "真实图元：判定到哪、挖到哪，那块像素直接从画面上消失、露出画板底色，"
     "不再用额外颜色把“待挖除”的区域整片染出来（那种标色既像删除/保留"
     "对调，又会把图形自己的边框一起盖掉）；填充另走淡色通道、轮廓走主色，"
     "两者一眼可分；紫色虚线是算法当前正在判定的那一段，动画末帧等于"
     "画布真实裁剪结果，播完画布那一瞬画面不跳变。右侧“决策项监视”实时"
     "显示当前步的关键量：编码裁剪页给两端区域码与 code₀ & code₁ / "
     "code₀ | code₁，参数裁剪页给 p、q、u₀、u₁ 与收窄过程，逐边裁剪页"
     "给当前半平面与两端判定（内→内 / 内→外 / 外→内 / 外→外），"
     "双边裁剪页给进入点与离开点计数。矩阵值用 MatrixView 矢量绘制成"
     "3×3 仿射矩阵，等宽数字按列右对齐。")
body("（7）速度档位与单步。播放速度滑杆范围为 0.1~240 步/秒，其中 0.1 "
     "步/秒相当于一步 10 秒；裁剪页默认 1 步/秒、变换页默认 4 步/秒。"
     "配合“单步前进/后退”与“按阶段暂停”，判定、求交、参数收窄这类步骤"
     "可以逐帧盯住观察：裁剪页把“沿图形边界的一段”作为阶段边界，"
     "可停在每段判定结束处等待讲解。")

# ------------------------------ 三 ------------------------------
h1("三、实验结果")
body("所有结果均来自程序实际运行：界面图由离屏 Qt 渲染脚本自动抓取，"
     "流程图由脚本绘制，数值由自动化脚本统计，未作人工修饰。")

h3("3.1 实验环境与验证方法")
body("实验在 Windows 11 + Python 3.12.10 + PySide6 6.12 环境下完成，"
     "共使用五类自动化验证，各自覆盖不同的失效模式如")
p = doc.paragraphs[-1]
add_ref(p, "tab", 5)
add_text(p, " 所示。")
add_table(
    "自动化验证的覆盖范围",
    ["测试脚本", "覆盖内容", "结果"],
    [
        ["transform_test.py",
         "矩阵运算、椭圆协方差换算、圆↔椭圆类型互转、旋转椭圆光栅化、"
         "工程文件 v2、几何谓词、区域裁剪",
         "PASS（3893 项）"],
        ["clip_test.py",
         "五页裁剪演示的口径校验：动画末帧等于真实裁剪结果、边框与填充分色、"
         "填充随边界逐段往里退（不得一次性空掉）、空转步必须合并、"
         "阶段键完整可按阶段暂停、同图连续裁两次必须累积、"
         "裁剪后旋转不残留黑散点、多边形窗口挖除、逐边裁剪遇凹窗口必须拒绝、"
         "双边交替路径不得反复播放同一段",
         "PASS（460 项）"],
        ["smoke_test.py",
         "离屏功能烟测：绘制、选择、拖拽变换、撤销、工程文件、演示页加载、"
         "播放与单步、速度档、面板窄宽回归",
         "PASS（206 项）"],
        ["render_test.py",
         "算法像素级回归：比较新旧实现的输出像素集，防止重构引入偏差",
         "PASS（382 组用例）"],
        ["algo_verify.py",
         "数学真值校验：独立于程序实现，按直线/圆/椭圆方程计算理想像素",
         "PASS（2643 例）"],
    ],
    widths=[3.6, 8.6, 2.4], center_cols=(2,))

h3("3.2 平移变换结果")
body("平移演示页的结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 10)
add_text(p, "所示。画面按最终矩阵 T(dx,dy) 逐帧平移，橙色参照层始终显示"
             "初始位置以作对照，右侧决策项监视给出当前步的 dx、dy、"
             "取样点 P 与映射点 P′，矩阵行固定显示最终的 T(dx,dy)。"
             "图中多边形的形状与大小在平移前后完全一致，仅位置发生位移，"
             "说明变换确实只作用于平移分量。")
add_figure("m3_04_平移变换演示.png",
           "平移变换演示：逐帧平移、橙色初始态参照层与最终矩阵监视", 15.0)

h3("3.3 旋转变换结果")
body("旋转变换的分解演示如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 11)
add_text(p, "所示。画面正处在第 ② 阶段“绕原点旋转”：轴心已经搬到原点 O"
             "（图中 O 标记与轴心到 O 的虚线），图形正在绕 O 旋转，"
             "右侧监视器显示本阶段矩阵 M₂ = R(75°)·M₁ 的精确数值 "
             "[0.26 −0.97 11.55; 0.97 0.26 −34.15; 0 0 1]，"
             "与公式卡给出的符号矩阵 R(θ) 相对应。三个阶段分别为"
             "① 轴心移到原点、② 绕原点旋转、③ 轴心移回原位，"
             "每个阶段内部再分 6 帧平滑过渡并在末尾停留，阶段边界清晰可见。")
add_figure("m3_05_旋转变换演示_分解三阶段.png",
           "旋转变换分解演示：第 ② 阶段“绕原点旋转”与本阶段矩阵监视", 15.0)

h3("3.4 缩放变换结果")
body("缩放演示页与旋转页同构，同样分三阶段展开，结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 12)
add_text(p, "所示。由于本例的 sx 与 sy 不同，缩放后图形的长宽比发生变化；"
             "若被缩放的对象是圆，它会按协方差矩阵精确地变成一个椭圆"
             "而不是被拉扁的圆——这正是参数化存储加特征分解换算的价值。")
add_figure("m3_06_缩放变换演示_分解三阶段.png",
           "缩放变换分解演示：第 ② 阶段“绕原点缩放”", 15.0)

h3("3.5 复合变换结果")
body("复合变换按五阶段展开，结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 13)
add_text(p, "所示。图中正处在第 ③ 阶段“旋转 R”，此前已经完成了"
             "轴心移到原点与缩放两个阶段；右侧监视器同时给出本阶段的"
             "转角、缩放比例与累计矩阵。五个阶段依次为 T(−c) → S → R "
             "→ T(c) → T(dx,dy)，顺序不可交换：把五步合成为一个 M 之后"
             "三种变换同时发生，观众将无法分辨先后次序，因此演示页始终"
             "按阶段播放，并支持“按阶段暂停”在每个阶段末自动停住。")
add_figure("m3_07_复合变换演示_五阶段.png",
           "复合变换五阶段演示：第 ③ 阶段“旋转 R”", 15.0)

h3("3.6 应用模式下的交互")
body("拖拽旋转时的实时反馈如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 14)
add_text(p, "所示：包围盒中心显示定点标记，包围盒下方给出当前角度读数"
             "“旋转 135.0°”，画面上浅色的幽灵预览是旋转后的形态，"
             "松手才会真正写入画布。拖拽过程不做全量重绘，只重算预览层，"
             "因此交互是跟手的。")
add_figure("m3_02_二维变换_拖拽旋转读数.png",
           "拖拽旋转：定点标记、幽灵预览与实时角度读数", 15.0)

h3("3.7 编码裁剪结果")
body("编码裁剪演示页的结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 15)
add_text(p, "所示。画面上红色虚线是裁剪窗口，被裁线段用主色画出，"
             "判定到哪、挖到哪，落在窗口内的部分直接从画面上消失、"
             "露出画板底色，端点旁直接标出"
             "二进制区域码“1001 左/下”。右侧监视器给出两端的区域码、"
             "code₀ & code₁ 与 code₀ | code₁ 两串二进制以及当前判定"
             "（本例为“起点编码”），并用人话解释“判断起点 (4, 38) 落在"
             "哪个区域”。鼠标在画布上移动时，窗口四条边延长到画布边缘，"
             "把平面分成九个区域并各自标出区域码，鼠标所在区域淡蓝高亮，"
             "便于直观核对编码判定。")
add_figure("m4_01_编码裁剪_Cohen-Sutherland.png",
           "Cohen-Sutherland 编码裁剪：区域码判定与端点标记", 15.0)

h3("3.8 中点分割裁剪结果")
body("中点分割裁剪的结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 16)
add_text(p, "所示。与编码裁剪的“求交点截断”不同，本页的画面上可以看到"
             "被判定线段的区间在逐轮二分中肉眼可见地收缩，紫色虚线标出"
             "当前正在处理的中点 M，监视器同步显示中点坐标、中点区域码、"
             "当前区间长度与已进行的轮次。当区间长度收敛到 1 个像素以内时"
             "判定结束，两端点即为边界交点的近似。")
add_figure("m4_02_中点分割裁剪.png",
           "中点分割裁剪：区间逐轮二分收缩与中点区域码监视", 15.0)

h3("3.9 参数裁剪结果")
body("参数裁剪的结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 17)
add_text(p, "所示。右侧监视器给出当前正在处理的边界以及该边界的 p、q 值"
             "和当前的参数区间 u₀、u₁，并显示收窄动作本身"
             "（如“p=−50<0 → u₀ = max(0.000, 0.333) = 0.333”）。"
             "画面上当前边界在红框外侧加粗高亮，其余三条边界为灰色虚线，"
             "端点移动箭头直观指出“哪一端被拉了回来”。")
add_figure("m4_03_参数裁剪_Liang-Barsky.png",
           "Liang-Barsky 参数裁剪：p/q 与参数区间 u₀、u₁ 的收窄过程", 15.0)

h3("3.10 多边形逐边裁剪结果")
body("Sutherland-Hodgman 逐边裁剪页的结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 18)
add_text(p, "所示。被裁对象是画布上的一个封闭多边形，判定沿多边形的"
             "各条边一段段进行，每判定完一段，落在窗口内的部分立刻被挖掉，"
             "画面因此呈现“一步步裁掉”的过程；封闭图元的填充按归属随"
             "边界逐段往里退，洞是长出来的而不是整块空出来的。右侧监视器"
             "显示当前使用的"
             "半平面（即窗口的那一条边）、两端判定（内→内 / 内→外 / "
             "外→内 / 外→外）、本段长度与判定结果。窗口必须是凸多边形："
             "若换成凹窗口，本页会直接拒绝并提示改用下一页。")
add_figure("m4_04_多边形裁剪_逐边S-H.png",
           "Sutherland-Hodgman 逐边裁剪：沿多边形各边逐段判定", 15.0)

h3("3.11 多边形双边裁剪结果")
body("Weiler-Atherton 双边裁剪页的结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 19)
add_text(p, "所示。本页的窗口画成了一个【凹】多边形——这正是逐边裁剪"
             "无法处理、而双边裁剪可以处理的情形。右侧监视器显示进入点与"
             "离开点的计数，演示页末尾还会专门演示“双边的另一半”，"
             "即窗口的边落在主体内部的那几段，说明交集边界是由"
             "“被裁多边形的边”与“窗口的边”交替组成的。把两页并列对照，"
             "两种算法的能力差异非常直观。")
add_figure("m4_05_多边形裁剪_双边W-A.png",
           "Weiler-Atherton 双边裁剪：凹窗口下的进入/离开判定", 15.0)

h3("3.12 区域裁剪的挖除效果")
body("应用模式下的区域裁剪如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 20)
add_text(p, "所示：拖出矩形窗口后，红色边框与 8 个手柄可直接调整，"
             "四个坐标也可在面板中直接输入。窗口就绪后按 Enter（或双击"
             "画布、或点“挖除窗口内”）确认，窗口内的部分从所有相交图元上"
             "消失，状态栏给出提示“已挖除 3 个图元的窗口内部分（369 像素，"
             "Ctrl+Z 可撤销）”，挖除结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 21)
add_text(p, "所示：蓝色多边形的窗口内部分被整齐地切掉，边缘是一条"
             "与窗口边界平直的切口，而不是零散的缺失像素。")
add_figure("m4_06_区域裁剪_窗口就绪.png",
           "应用模式区域裁剪：矩形窗口就绪、可拖手柄调整", 15.0)
add_figure("m4_07_区域裁剪_挖除结果.png",
           "区域裁剪的挖除结果：窗口内部分整齐消失", 15.0)

h3("3.13 裁剪结果的稳健性")
body("被挖掉的区域必须跟着图元一起走。把已裁剪的多边形再旋转 30°，"
     "结果如")
p = doc.paragraphs[-1]
add_ref(p, "fig", 22)
add_text(p, "所示：切口随图元一同旋转，仍然是一块干净的连续区域，"
             "没有出现零散的黑点或锯齿。早期实现把挖除区域存成像素采样点，"
             "而图元变换后会被重新光栅化，两者不同源导致掩膜漏格，"
             "旋转后被裁区域会冒出一片黑散点；改为按几何区域存储后问题"
             "不再复发。该行为由 clip_test.py 中的专门用例锁定。")
add_figure("m4_08_裁剪后旋转_几何随图元走.png",
           "裁剪后旋转 30°：被挖除区域随图元一同旋转，保持干净连续", 15.0)

h3("3.14 自动化验证汇总")
body("最终验证结果汇总如")
p = doc.paragraphs[-1]
add_ref(p, "tab", 6)
add_text(p, " 所示。")
add_table(
    "自动化验证汇总",
    ["脚本", "项数", "结论"],
    [
        ["transform_test.py", "3893", "PASS ✓"],
        ["clip_test.py", "460", "PASS ✓"],
        ["smoke_test.py", "206", "PASS ✓"],
        ["render_test.py", "382 组", "PASS ✓"],
        ["algo_verify.py", "2643 例", "PASS ✓"],
    ],
    widths=[6.0, 4.0, 4.6], center_cols=(1, 2))
body("上述脚本均可由项目根目录直接运行复现。随报告提交的附件包括："
     "（1）完整源代码，algorithms/、core/、ui/、modules/、teaching/ "
     "等目录下的关键函数均带中文注释；（2）单文件可执行程序 "
     "图形画板.exe，双击即可运行，无需安装 Python 或 PySide6；"
     "（3）项目说明 README.md，含目录结构、运行方法与测试命令。")

# ------------------------------ 四 ------------------------------
h1("四、实验讨论与体会")

h3("4.1 关键问题与解决")
body("（1）圆与椭圆无法用“变换端点”的方式处理。最初沿用直线的做法直接"
     "缩放圆心与半径，结果非等比缩放后得到的是一个被拉扁的圆而不是椭圆，"
     "形状完全失真。改为把椭圆写成参数形式并对协方差矩阵做特征分解后，"
     "任意仿射变换下的新半轴与旋转角都可以精确求出，圆在非等比缩放时"
     "还会原地转成椭圆并保持对象身份（选中状态不丢），撤销可还原。")
body("（2）裁剪区域与变换不同源导致黑散点。早期把挖除区域记为像素采样点，"
     "图元旋转后会被重新光栅化（圆/椭圆还会按协方差矩阵解析式重参数化），"
     "两者不同源，掩膜漏格，本该被挖掉的像素没被盖住，旋转后被裁区域"
     "重新冒出一片黑散点。把裁剪窗口升格为【几何区域】随矩阵一起变换、"
     "渲染时按几何重新求交之后，残留像素数为 0。")
body("（3）演示对象必须是真实主体。最初为了让算法过程更清楚，裁剪演示"
     "画的是一条与图形边界无关的水平辅助长弦，结果用户看到的是"
     "“一条不相干的线在动”，与真实裁剪完全对不上。改为让判定沿图元"
     "的真实边界逐段进行——直线按整段、多边形按各条边、圆与椭圆取"
     "真实栅格轮廓像素按极角排序后每 5~6 个相邻像素切一段——"
     "判定轨迹与原图逐像素重合，教学过程才与真实操作一致。")
body("（4）末帧必须等于真实裁剪结果。“演完即所得”是裁剪动画的基本要求："
     "若动画末帧与画布真实裁剪结果不一致，播完那一瞬画面就会跳变。"
     "为此把末帧口径统一为“窗口外的图元像素集合”，与应用侧使用同一套"
     "浮点几何掩膜，并用回归用例逐像素比对两种结果。")
body("（5）同一图形上连续裁剪必须累积。演示壳早期在每次重新生成步骤流时"
     "都无条件还原上一轮的真实裁剪，用户反馈“第二次操作把第一次冲掉了”。"
     "根因是把“重播同一轮动画”与“开始新一轮操作”当成了一件事。"
     "改为只有同窗口同参数的重播才还原，换窗口则保留已生效的结果，"
     "并把旧快照作废。")
body("（6）填充与轮廓必须分色。演示层里若填充像素没有全部走淡色通道，"
     "窗口内尚未挖除的填充会退回主色，整块图元糊成一个颜色、边框"
     "完全看不出来。修正为“轮廓 = 主色、填充 = 淡色，且填充通道覆盖"
     "该层的全部像素”，并把画布上封闭图元的填充色改用中性灰与演示层"
     "主色错开；此外演示层用 drawRects 批量绘制时后画的会盖住先画的，"
     "因此必须把轮廓组排到填充组之后画。")
body("（7）填充不能“一次性空掉”。窗口内的填充是一整块连通区域，早期做法是"
     "从刚被挖掉的轮廓往里无限扩散，一段判定完，窗口内整块填充同时消失，"
     "画面中间凭空少一大块，看不出因果。改为按【归属】处理：窗口内每个"
     "填充像素归给离它最近的、落在窗口内的轮廓像素所属的那一段，于是"
     "填总是随边界一段段往里退；再给单帧擦除量设上限（窗口内填充的 1/4），"
     "擦不完的排队，走完边界后在“收尾”阶段按层擦完，洞是“往里长”的。"
     "该行为由 clip_test.py 中“自算窗口内填充量、单帧掉填充不得超过 30%”"
     "的用例锁定。")
body("（8）双边裁剪的动画曾反复播放同一段。根因是求交在【栅格化阶梯轮廓】"
     "上做：斜边走到窗口边界时恰好“歇一步”，同一个真实交点被拆成进入与"
     "离开两个伪交点，而路径行走没有“已消费节点”的约束，外层循环又从伪"
     "进入点重新出发，五个交点的用例被放大成 50 段、每段重复 8 遍。改为"
     "在真实几何上求交（栅格轮廓只用来把交点贴回最近像素以保证轨迹与原图"
     "逐像素重合）、并给行走加上访问约束后，同一用例降到 10 段、图形边与"
     "窗口边交替前进；守卫用例自行推算真实交点数，断言交替段总数与之相等。")
body("（9）空转步要合并，阶段要能停。逐边判定时，窗口的每条边都要判一次，"
     "绝大多数判定对当前这一段没有任何影响，帧与帧之间画面完全相同，"
     "七十多步的演示反而看不清主线。改为把“画面与判定对象都没变”的帧"
     "合并、并把条数写进下一帧的说明；同时把“沿图形边界的一段”作为阶段键，"
     "裁剪页由此接入既有的“按阶段暂停”，可停在每段判定的边界上逐段核对。")

h3("4.2 算法分析与比较")
body("三种线段裁剪算法与两种多边形裁剪算法的对比如")
p = doc.paragraphs[-1]
add_ref(p, "tab", 7)
add_text(p, " 所示。")
add_table(
    "五种裁剪算法的比较",
    ["算法", "窗口形状", "求交方式", "优点", "局限"],
    [
        ["Cohen-Sutherland", "矩形", "按区域码代入直线方程解析求交",
         "判定直观、易讲解，区域码本身就是教学重点",
         "需反复编码求交，最多四轮"],
        ["中点分割裁剪", "矩形", "对区间反复二分，不求解析解",
         "只有移位与加减，无乘除，适合硬件实现",
         "精度取决于二分层数，收敛较慢"],
        ["Liang-Barsky", "矩形", "参数化，一次循环求参数区间",
         "乘法除法次数固定，三者中效率最高",
         "过程不如编码法直观"],
        ["Sutherland-Hodgman", "必须凸多边形",
         "窗口表示成半平面之交，逐半平面切",
         "可裁出完整交集多边形，实现简洁",
         "窗口为凹多边形时结果错误"],
        ["Weiler-Atherton", "任意简单多边形",
         "双边求交，按进入/离开配对",
         "支持凹窗口，交界边界由双方交替组成",
         "实现复杂，需要成环与去重"],
    ],
    widths=[3.0, 2.4, 3.4, 3.4, 2.4])
body("从工程角度看，三种线段裁剪算法共享同一套“双出口”约定——几何出口"
     "返回精确结果，步骤流出口返回可回放的判定过程，且两者末步像素逐像素"
     "一致。新增算法只需实现这两个出口，即可自动接入工具栏、演示页与"
     "测试体系。多边形裁剪的两页并列呈现，让“窗口必须凸”这一限制"
     "不再是一句需要背诵的结论，而成为可以亲眼看到的对照。")

h3("4.3 不足与改进方向")
body("（1）变换的数值面板目前只提供等比缩放，非等比缩放只能靠拖拽手柄"
     "实现。后续可在面板中增加 sx、sy 两个独立输入框，使全部变换类型"
     "都能用数值精确指定；")
body("（2）区域裁剪目前是“挖除窗口内”语义，属于区域裁剪的一种。"
     "真正的 Sutherland-Hodgman 与 Weiler-Atherton 是“保留窗口内”的"
     "裁剪，演示页虽已实现完整算法，应用模式尚未提供对应的保留式入口；")
body("（3）裁剪窗口目前是单一区域。若要支持多窗口取交集或并集，需要"
     "把掩膜的生成改为多窗口的布尔运算；")
body("（4）演示模式的播放速度虽有 0.1 步/秒的慢速档，裁剪页也已能按"
     "阶段暂停，但仍不支持按"
     "决策项断点、导出单帧或录制 GIF，课堂讲解的辅助还可加强；")
body("（5）变换与裁剪目前作用于本地图元，尚未与三维图形管线衔接；"
     "后续的模块（三维观察与变换）需要把这里的 3×3 仿射内核推广到 4×4 "
     "齐次矩阵。")

h3("4.4 心得体会")
body("这次实验最大的收获，是意识到“变换”与“裁剪”这两件事在数学上"
     "远比想象中统一：平移、旋转、缩放都是仿射变换，都能写成矩阵；"
     "而绕定点的旋转之所以要拆成三步，正是因为矩阵乘法不满足交换律——"
     "这个在纸上是一行公式的性质，在交互上却直接决定了演示能不能讲清楚。"
     "把一个合成矩阵直接给出，观众看到的是“图形同时平移旋转缩放了”，"
     "什么也学不到；拆成 T(−c) → S → R → T(c) → T(dx,dy) 五步之后，"
     "次序才变得可见。数学结构与教学表达，在这里是同一件事的两面。")
body("另一处体会来自“演示对象必须是真实主体”。起初为了让过程清楚，"
     "我画了一条与图形边界无关的辅助长弦来做演示，自以为降低了理解"
     "难度，实际却让演示与真实操作完全脱节。真正有效的做法反而是"
     "更“笨”的：让算法老老实实沿真实边界一段段走，每判一段就当场"
     "挖掉，末帧直接等于真实结果。这让我意识到，教学演示的价值不在于"
     "简化，而在于【与真实操作同源】——只要两者共用一份实现、一个口径，"
     "过程自然可信；一旦为了好看而另写一套，问题就藏在那套另写的代码里。")
body("工程上，参数化存储加“绘制时重新光栅化”的架构让变换与裁剪得以"
     "统一：所有操作都只改几何参数，不碰位图，于是旋转、缩放、裁剪、"
     "撤销可以任意组合；配合“双出口”约定，绘图结果与演示动画共用同一"
     "份实现，回归测试也能直接比对两个出口。这种“先定接口、再写实现、"
     "最后用测试锁住行为”的做法，是这两次实验最值得带走的经验。")

# ------------------------------ 五 ------------------------------
h1("五、参考文献")
for ref in (
    "孙家广. 计算机图形学（第三版）[M]. 北京: 清华大学出版社, 1998.",
    "Hearn D, Baker M P. Computer Graphics with OpenGL[M]. 4th ed. Upper "
    "Saddle River: Pearson, 2010.",
    "Cohen J M, Wyvill G. The Sutherland-Hodgman clipping algorithm[J]. "
    "Software—Practice and Experience, 1974, 4(7): 476-480.",
    "Weiler P M, Atherton P. A clipping algorithm for computer graphics[J]. "
    "ACM Transactions on Graphics, 1975, 1(1): 14-24.",
    "Liang Y D, Barsky B A. A new concept and method for line clipping[J]. "
    "IEEE Transactions on Computers, 1984, C-33(7): 462-467.",
    "Blinn J F. A subdivision technique for computer display of curved "
    "surfaces[J]. IEEE Transactions on Computers, 1968, 17(8): 843-852.",
    "Qt Group. Qt for Python Documentation[EB/OL]. "
    "https://doc.qt.io/qtforpython/, 2026-11.",
    "PyInstaller Development Team. PyInstaller Manual[EB/OL]. "
    "https://pyinstaller.org/, 2026-11.",
):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Pt(21)
    p.paragraph_format.first_line_indent = Pt(-21)
    p.paragraph_format.space_after = Pt(2)
    add_text(p, ref, size=10.5)

# ---------------------------------------------------------------------
# 分节页码：封面无页码、目录罗马数字、正文阿拉伯数字从 1 起算
# ---------------------------------------------------------------------
s_cover, s_front, s_body = doc.sections[0], doc.sections[1], doc.sections[2]

# 封面：页眉页脚留空
s_cover.different_first_page_header_footer = False
for hf in (s_cover.header, s_cover.footer):
    hf.is_linked_to_previous = False
    for para in hf.paragraphs:
        _clear_runs(para)

# 目录：无页眉，页脚罗马数字
s_front.different_first_page_header_footer = False
s_front.header.is_linked_to_previous = False
for para in s_front.header.paragraphs:
    _clear_runs(para)
_fill_footer(s_front, roman=True)
_set_page_numbering(s_front, "upperRoman")

# 正文：页眉 + 阿拉伯数字页码，总页数按本节统计
s_body.different_first_page_header_footer = False
_fill_header(s_body)
_fill_footer(s_body, roman=False, total=True)
_set_page_numbering(s_body, "decimal")

# ---------------------------------------------------------------------
# 打开时更新所有域（目录、SEQ、REF）
# ---------------------------------------------------------------------
settings = doc.settings.element
uf = OxmlElement("w:updateFields")
uf.set(qn("w:val"), "true")
settings.append(uf)

props = doc.core_properties
props.title = "《计算机图形学》上机实验报告——二维几何变换与区域裁剪算法的设计与实现"
props.author = "李焕锟"
props.subject = "计算机图形学上机实验二"

doc.save(OUT)
print("saved:", OUT)
print("figures:", _fig_no[0], "tables:", _tab_no[0])

"""Build a 'Boost Your Vocabulary' .docx from passage text + ordered vocab entries.
Generates raw OOXML (no external libs). Arial 9.5pt, green header bar,
two-column table (left passage with red/bold/underlined target words; right defs).
"""
import re, zipfile, os

RED = "CC0000"
GREEN = "2E7D32"
WHITE = "FFFFFF"
BLACK = "000000"
FONT = "Arial"
SZ = "19"   # 9.5pt = 19 half-points

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))

def run(text, *, bold=False, ital=False, underline=False, color=None, size=SZ,
        font=FONT, preserve=True):
    rpr = ["<w:rFonts w:ascii=\"%s\" w:hAnsi=\"%s\" w:cs=\"%s\"/>" % (font, font, font)]
    if bold: rpr.append("<w:b/>")
    if ital: rpr.append("<w:i/>")
    if underline: rpr.append("<w:u w:val=\"single\"/>")
    if color: rpr.append("<w:color w:val=\"%s\"/>" % color)
    rpr.append("<w:sz w:val=\"%s\"/><w:szCs w:val=\"%s\"/>" % (size, size))
    sp = ' xml:space="preserve"' if preserve else ''
    return ("<w:r><w:rPr>%s</w:rPr><w:t%s>%s</w:t></w:r>"
            % ("".join(rpr), sp, esc(text)))

def para(runs_xml, *, spacing_after="80", shd=None, align=None, keep=False):
    ppr = ["<w:spacing w:after=\"%s\" w:line=\"240\" w:lineRule=\"auto\"/>" % spacing_after]
    if shd: ppr.append("<w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"%s\"/>" % shd)
    if align: ppr.append("<w:jc w:val=\"%s\"/>" % align)
    if keep: ppr.append("<w:keepNext/>")
    return "<w:p><w:pPr>%s</w:pPr>%s</w:p>" % ("".join(ppr), runs_xml)

# ---------- highlighting of target words in passage ----------
def build_highlight_regex(terms):
    # longest first so phrases / longer inflections win
    terms = sorted(set(terms), key=lambda t: -len(t))
    parts = []
    for t in terms:
        esc_t = re.escape(t)
        # allow internal whitespace to match any whitespace
        esc_t = esc_t.replace(r"\ ", r"\s+")
        parts.append(esc_t)
    pat = r"(?<![A-Za-z])(" + "|".join(parts) + r")(?![A-Za-z])"
    return re.compile(pat, re.IGNORECASE)

def render_passage_paragraph(text, regex):
    """Return run-xml for one paragraph, highlighting matches."""
    out = []
    pos = 0
    for m in regex.finditer(text):
        if m.start() > pos:
            out.append(run(text[pos:m.start()]))
        out.append(run(m.group(0), bold=True, underline=True, color=RED))
        pos = m.end()
    if pos < len(text):
        out.append(run(text[pos:]))
    return "".join(out)

# ---------- document assembly ----------
def green_bar(page_label):
    left = run("BOOST YOUR VOCABULARY", bold=True, color=WHITE, size="26")
    right = run("    " + page_label, bold=True, color=WHITE, size="22")
    ppr = ('<w:pPr><w:shd w:val="clear" w:color="auto" w:fill="%s"/>'
           '<w:spacing w:before="40" w:after="120" w:line="240" w:lineRule="auto"/>'
           '<w:tabs><w:tab w:val="right" w:pos="9500"/></w:tabs></w:pPr>' % GREEN)
    tab = '<w:r><w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s"/></w:rPr><w:tab/></w:r>' % (FONT, FONT)
    return "<w:p>%s%s%s%s</w:p>" % (ppr, left, tab, right)

def cell(width, content_xml):
    return ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>'
            '<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tcMar>'
            '</w:tcPr>%s</w:tc>' % (width, content_xml))

def two_col_table(left_xml, right_xml):
    borders = ('<w:tblBorders>'
               '<w:top w:val="single" w:sz="4" w:color="BFBFBF"/>'
               '<w:left w:val="single" w:sz="4" w:color="BFBFBF"/>'
               '<w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/>'
               '<w:right w:val="single" w:sz="4" w:color="BFBFBF"/>'
               '<w:insideH w:val="single" w:sz="4" w:color="BFBFBF"/>'
               '<w:insideV w:val="single" w:sz="4" w:color="BFBFBF"/>'
               '</w:tblBorders>')
    tblpr = ('<w:tblPr><w:tblW w:w="9500" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
             + borders + '</w:tblPr>')
    grid = '<w:tblGrid><w:gridCol w:w="5000"/><w:gridCol w:w="4500"/></w:tblGrid>'
    row = "<w:tr>%s%s</w:tr>" % (cell(5000, left_xml), cell(4500, right_xml))
    return "<w:tbl>%s%s%s</w:tbl>" % (tblpr, grid, row)

def build_left_column(passage_num, title, paragraphs, regex):
    parts = []
    head = (run("READING PASSAGE %d  " % passage_num, bold=True, size="32", color=GREEN)
            + run(title, bold=True, size="32", color=BLACK))
    parts.append(para(head, spacing_after="160", keep=True))
    for ptext in paragraphs:
        parts.append(para(render_passage_paragraph(ptext, regex), spacing_after="120"))
    return "".join(parts)

def build_right_column(entries):
    parts = []
    parts.append(para(run("VOCABULARY", bold=True, size="28", color=GREEN),
                      spacing_after="160", keep=True))
    for e in entries:
        # Word= definition  (word bold red, = and def black)
        rxml = (run(e["word"], bold=True, color=RED)
                + run("= " + e["def"], color=BLACK))
        parts.append(para(rxml, spacing_after="20"))
        if e.get("coll"):
            cxml = (run("\u25b8 e.g. ", color=GREEN)
                    + run(e["coll"], ital=True, color=BLACK))
            parts.append(para(cxml, spacing_after="20"))
        if e.get("fam"):
            fxml = (run("\u25b8 Word family: ", bold=True, color=GREEN)
                    + run(e["fam"], color=BLACK))
            parts.append(para(fxml, spacing_after="120"))
        else:
            # add a little gap after entries without family
            parts[-1] = parts[-1].replace('w:after="20"', 'w:after="120"', 1)
    return "".join(parts)

def build_document(passages):
    """passages: list of dicts with num,title,paragraphs(list),entries(list)."""
    body = []
    for i, p in enumerate(passages):
        terms = []
        for e in p["entries"]:
            terms.extend(e["hl"])
        regex = build_highlight_regex(terms)
        page_label = "Reading Passage %d" % p["num"]
        bar = green_bar(page_label)
        if i > 0:
            bar = bar.replace("<w:pPr>", "<w:pPr><w:pageBreakBefore/>", 1)
        left = build_left_column(p["num"], p["title"], p["paragraphs"], regex)
        right = build_right_column(p["entries"])
        body.append(bar)
        body.append(two_col_table(left, right))
        body.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" '
            'w:header="360" w:footer="360" w:gutter="0"/></w:sectPr>')
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body>%s%s</w:body></w:document>' % ("".join(body), sect))
    return doc

CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '</Types>')

RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>')

DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '</Relationships>')

STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
    '<w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
    '</w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
    '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="19"/></w:rPr></w:style>'
    '</w:styles>')

def write_docx(passages, out_path):
    doc = build_document(passages)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", STYLES)
    return out_path

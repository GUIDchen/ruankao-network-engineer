#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown -> (HTML -> PDF) and DOCX renderer with handwritten OOXML."""
import re, os, sys, html, zipfile, subprocess, datetime

BT = chr(96)
INLINE_RE = re.compile(r'(\*\*.+?\*\*|' + BT + r'[^' + BT + r']+' + BT + r'|\[[^\]]+\]\([^)]+\))')

def inline_tokens(text):
    out = []
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith('**') and part.endswith('**') and len(part) > 4:
            out.append((part[2:-2], 'bold'))
        elif part.startswith(BT) and part.endswith(BT) and len(part) > 1:
            out.append((part.strip(BT), 'code'))
        elif part.startswith('['):
            m = re.match(r'\[([^\]]+)\]\(([^)]+)\)', part)
            if m: out.append((m.group(1), 'link', m.group(2)))
            else: out.append((part, 'text'))
        else:
            out.append((part, 'text'))
    return out

def parse_md(md):
    lines = md.split('\n')
    blocks, i, n = [], 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1; continue
        if s == '<!--pagebreak-->':
            blocks.append(('pagebreak',)); i += 1; continue
        if s == '<!--cover-end-->':
            blocks.append(('coverend',)); i += 1; continue
        if s.startswith('~~~') or s.startswith(BT * 3):
            lang = s[3:].strip(); i += 1; buf = []
            while i < n and not (lines[i].strip().startswith('~~~') or lines[i].strip().startswith(BT * 3)):
                buf.append(lines[i].rstrip()); i += 1
            i += 1
            blocks.append(('code', lang, '\n'.join(buf))); continue
        m = re.match(r'^(#{1,4})\s+(.*)$', s)
        if m:
            blocks.append(('h', len(m.group(1)), m.group(2).strip())); i += 1; continue
        if re.match(r'^-{3,}$', s):
            blocks.append(('hr',)); i += 1; continue
        if s.startswith('|'):
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append(lines[i].strip()); i += 1
            blocks.append(('table', rows)); continue
        if s.startswith('>'):
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(re.sub(r'^>\s?', '', lines[i].strip())); i += 1
            blocks.append(('quote', '\n'.join(buf))); continue
        m = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.*)$', lines[i])
        if m:
            items = []
            while i < n:
                m2 = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.*)$', lines[i])
                if not m2:
                    if not lines[i].strip() and i + 1 < n and re.match(r'^\s*([-*+]|\d+\.)\s+', lines[i + 1]):
                        i += 1; continue
                    break
                items.append((len(m2.group(1)) // 2, m2.group(2)[0].isdigit(), m2.group(3).strip()))
                i += 1
            blocks.append(('list', items)); continue
        buf = [lines[i]]; i += 1
        while i < n and lines[i].strip() and not re.match(r'^(#{1,4}\s|~~~|\||>|<!--|\s*([-*+]|\d+\.)\s)', lines[i].strip()) and not lines[i].strip().startswith(BT * 3):
            buf.append(lines[i]); i += 1
        text = ''
        for k2, ln in enumerate(buf):
            piece = ln.strip()
            if k2:
                text += ('\n' if buf[k2 - 1].endswith('  ') else ' ')
            text += piece
        blocks.append(('p', text))
    return blocks

def split_row(row):
    row = row.strip()
    if row.startswith('|'): row = row[1:]
    if row.endswith('|'): row = row[:-1]
    return [c.strip() for c in row.split('|')]

def table_cells(rows):
    return [split_row(r) for r in rows if not re.match(r'^\|?[\s:\-|]+\|?$', r)]

MIN_SHARE = 0.12

def col_fractions(cells):
    ncol = max(len(r) for r in cells)
    wts = []
    for c in range(ncol):
        mx = 4
        for r in cells:
            if c < len(r):
                s = re.sub(r'[*' + BT + r'\[\]\(\)]', '', r[c])
                mx = max(mx, min(sum(2 if ord(ch) > 127 else 1 for ch in s), 30))
        wts.append(mx)
    total = float(sum(wts))
    shares = [w / total for w in wts]
    for _ in range(4):
        deficit = sum(max(0.0, MIN_SHARE - s) for s in shares)
        if deficit <= 1e-9:
            break
        excess = sum(s - MIN_SHARE for s in shares if s > MIN_SHARE)
        if excess <= 1e-9:
            break
        shares = [MIN_SHARE if s <= MIN_SHARE else s - deficit * (s - MIN_SHARE) / excess for s in shares]
    return shares

# ---------------- HTML ----------------
def esc(t):
    return html.escape(t, quote=False)

def inline_html(text):
    out = []
    for tok in inline_tokens(text):
        if tok[1] == 'bold': out.append('<strong>%s</strong>' % esc(tok[0]).replace('\n', '<br/>'))
        elif tok[1] == 'code': out.append('<code>%s</code>' % esc(tok[0]))
        elif tok[1] == 'link': out.append('<a href="%s">%s</a>' % (esc(tok[2]), esc(tok[0])))
        else: out.append(esc(tok[0]).replace('\n', '<br/>'))
    return ''.join(out)

def render_html(meta, blocks, css_path):
    body, in_cover = [], True
    for b in blocks:
        k = b[0]
        if k == 'coverend':
            in_cover = False; body.append('</div>'); continue
        if k == 'pagebreak':
            body.append('<div class="pb"></div>'); continue
        if k == 'h':
            lvl = b[1]
            if in_cover and lvl == 1:
                t = b[2]
                if '）' in t and len(t) > 14:
                    head, tail = t.split('）', 1)
                    thtml = inline_html(head + '）') + '<br/>' + inline_html(tail.strip())
                else:
                    thtml = inline_html(t)
                body.append('<div class="cover"><div class="bar"></div><div class="cover-kicker">%s</div>'
                            '<h1 class="cover-title">%s</h1><div class="cover-sub">%s</div>'
                            % (esc(meta.get('kicker', '')), thtml, inline_html(meta.get('subtitle', ''))))
                continue
            body.append('<h%d>%s</h%d>' % (lvl, inline_html(b[2]), lvl)); continue
        if k == 'p':
            cls = ''
            if re.match(r'^\*\*\d+\.', b[1]): cls = ' class="stem"'
            elif re.match(r'^[A-D]\.\s', b[1]): cls = ' class="opts"'
            body.append('<p%s>%s</p>' % (cls, inline_html(b[1]))); continue
        if k == 'hr':
            body.append('<hr/>'); continue
        if k == 'code':
            body.append('<pre class="code"><code>%s</code></pre>' % esc(b[2])); continue
        if k == 'quote':
            rows_q = [x for x in b[1].split('\n') if not re.match(r'^(副标题|主题)[:：]', x.strip())]
            inner = '<br/>'.join(inline_html(x) for x in rows_q)
            body.append('<div class="cover-meta">%s</div>' % inner if in_cover else '<div class="callout">%s</div>' % inner)
            continue
        if k == 'list':
            tag = 'ol' if b[1][0][1] else 'ul'
            body.append('<%s>' % tag)
            for lvl, ordered, txt in b[1]:
                cls = ' class="lvl2"' if lvl > 0 else ''
                body.append('<li%s>%s</li>' % (cls, inline_html(txt)))
            body.append('</%s>' % tag); continue
        if k == 'table':
            cells = table_cells(b[1])
            shares = col_fractions(cells)
            body.append('<table class="tbl"><colgroup>' +
                        ''.join('<col style="width:%.1f%%"/>' % (s * 100) for s in shares) +
                        '</colgroup>')
            body.append('<thead><tr>' + ''.join('<th>%s</th>' % inline_html(c) for c in cells[0]) + '</tr></thead><tbody>')
            for row in cells[1:]:
                body.append('<tr>' + ''.join('<td>%s</td>' % inline_html(c) for c in row) + '</tr>')
            body.append('</tbody></table>'); continue
    css = open(css_path, encoding='utf-8').read()
    return ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>%s</title>'
            '<style>%s</style></head><body>\n%s\n</body></html>') % (esc(meta.get('title', '')), css, '\n'.join(body))

# ---------------- DOCX ----------------
def xesc(t):
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))

def run(text, bold=False, color=None, size=None, ea=None, asc=None):
    asc = asc or 'Times New Roman'
    ea = ea or '宋体'
    rpr = '<w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s" w:cs="%s"/>' % (asc, asc, ea, asc)
    if bold: rpr += '<w:b/><w:bCs/>'
    if color: rpr += '<w:color w:val="%s"/>' % color
    if size: rpr += '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size)
    return '<w:r><w:rPr>%s</w:rPr><w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, xesc(text))

def code_run(text):
    return ('<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="宋体"/>'
            '<w:shd w:val="clear" w:color="auto" w:fill="E8EEF6"/><w:sz w:val="19"/><w:szCs w:val="19"/>'
            '</w:rPr><w:t xml:space="preserve">%s</w:t></w:r>' % xesc(text))

def _with_breaks(text, bold, color=None, code=False):
    frags = []
    for idx, piece in enumerate(text.split('\n')):
        if idx: frags.append('<w:br/>')
        if piece:
            frags.append(code_run(piece) if code else run(piece, bold, color))
    return ''.join(frags)

def inline_docx(text, bold=False, color=None):
    out = []
    for tok in inline_tokens(text):
        if tok[1] == 'bold': out.append(_with_breaks(tok[0], True, color))
        elif tok[1] == 'code': out.append(code_run(tok[0]))
        elif tok[1] == 'link': out.append(_with_breaks(tok[0], bold, '1F5FA8'))
        else: out.append(_with_breaks(tok[0], bold, color))
    return ''.join(out)

def ppr(style=None, align=None, before=None, after=None, ind=None, hang=None,
        keep=False, shade=None, border=None, line=None, pbb=False):
    x = ['<w:pPr>']
    if style: x.append('<w:pStyle w:val="%s"/>' % style)
    if pbb: x.append('<w:pageBreakBefore/>')
    if keep: x.append('<w:keepNext/><w:keepLines/>')
    if border: x.append('<w:pBdr><w:left w:val="single" w:sz="18" w:space="8" w:color="%s"/></w:pBdr>' % border)
    if shade: x.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shade)
    if line or before is not None or after is not None:
        x.append('<w:spacing%s%s%s/>' % (
            ' w:before="%d"' % (before if before is not None else 0),
            ' w:after="%d"' % (after if after is not None else 0),
            ' w:line="%d" w:lineRule="auto"' % line if line else ''))
    if ind is not None:
        x.append('<w:ind w:left="%d" w:hanging="%d"/>' % (ind, hang) if hang else '<w:ind w:left="%d"/>' % ind)
    if align: x.append('<w:jc w:val="%s"/>' % align)
    x.append('</w:pPr>')
    return ''.join(x)

def para(runs, **kw):
    return '<w:p>%s%s</w:p>' % (ppr(**kw), runs)

def build_document(meta, blocks):
    body, in_cover = [], True
    pending = {'brk': False}
    in_toc = False
    for b in blocks:
        k = b[0]
        if k == 'h' and b[1] == 2 and b[2].strip() == '目录':
            in_toc = True
        elif k == 'h' and b[1] == 1 and in_toc:
            in_toc = False
        if k == 'list' and in_toc:
            # PDF page numbers do not apply to Word pagination: drop the leaders
            b = ('list', [(lvl, od, re.sub(r'\s*\.{3,}\s*\d+$', '', txt)) for lvl, od, txt in b[1]])
        if k == 'coverend':
            in_cover = False; pending['brk'] = True
            continue
        if k == 'pagebreak':
            pending['brk'] = True; continue
        if k == 'h':
            lvl = b[1]
            if in_cover and lvl == 1:
                body.append(para(run(meta.get('kicker', ''), True, '7F7F7F', 20), align='center', before=1800, after=260))
                t = b[2]
                if '）' in t and len(t) > 14:
                    head, tail = t.split('）', 1)
                    trun = run(head + '）', True, '1F3864', 48, '黑体') + '<w:r><w:br/></w:r>' + run(tail.strip(), True, '1F3864', 48, '黑体')
                else:
                    trun = run(t, True, '1F3864', 48, '黑体')
                body.append(para(trun, align='center', after=320))
                body.append(para(run(meta.get('subtitle', ''), True, '2E5496', 24), align='center', after=520))
                continue
            body.append(para(inline_docx(b[2]), style='Heading%d' % lvl,
                             pbb=bool(pending['brk'] and lvl > 1)))
            if pending['brk'] and lvl > 1:
                pending['brk'] = False
            continue
        if k == 'p':
            p = para(inline_docx(b[1]), keep=bool(re.match(r'^\*\*\d+\.', b[1])),
                     pbb=bool(pending['brk']))
            pending['brk'] = False
            body.append(p); continue
        if k == 'hr':
            body.append(para('<w:r><w:rPr><w:color w:val="C9D3E0"/><w:sz w:val="18"/></w:rPr>'
                             '<w:t>――――――――――――――――――――</w:t></w:r>', align='center', before=40, after=40)); continue
        if k == 'code':
            runs = []
            for idx, ln in enumerate(b[2].split('\n')):
                if idx: runs.append('<w:br/>')
                runs.append('<w:t xml:space="preserve">%s</w:t>' % xesc(ln))
            body.append('<w:p>%s<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="宋体"/>'
                        '<w:sz w:val="17"/></w:rPr>%s</w:r></w:p>'
                        % (ppr(shade='F4F6F9', border='7E97B8', before=100, after=100, line=300, keep=True), ''.join(runs)))
            continue
        if k == 'quote':
            inner = b[1].split('\n')
            if in_cover:
                for ln in inner:
                    if re.match(r'^(副标题|主题)[:：]', ln.strip()): continue
                    body.append(para(inline_docx(ln), align='center', after=40))
            else:
                body.append(para(inline_docx(' '.join(inner)), shade='EFF5FC', border='2E5496',
                                 before=120, after=120, line=320))
            continue
        if k == 'list':
            for lvl, ordered, txt in b[1]:
                body.append(para(run('•  ') + inline_docx(txt), ind=340 + 320 * lvl, hang=230, after=30, line=320))
            continue
        if k == 'table':
            cells = table_cells(b[1])
            if not cells: continue
            ncol = max(len(r) for r in cells)
            total = 9026
            shares = col_fractions(cells)
            cols = [max(900, int(total * s)) for s in shares]
            cols[-1] += total - sum(cols)
            grid = ''.join('<w:gridCol w:w="%d"/>' % c for c in cols)
            tbl = ['<w:tbl><w:tblPr><w:tblW w:type="pct" w:w="5000"/><w:tblLayout w:type="fixed"/><w:tblBorders>'
                   '<w:top w:val="single" w:sz="6" w:space="0" w:color="9DB0C8"/>'
                   '<w:left w:val="single" w:sz="6" w:space="0" w:color="9DB0C8"/>'
                   '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="9DB0C8"/>'
                   '<w:right w:val="single" w:sz="6" w:space="0" w:color="9DB0C8"/>'
                   '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="C9D3E0"/>'
                   '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="C9D3E0"/></w:tblBorders>'
                   '<w:tblCellMar><w:top w:w="50" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
                   '<w:bottom w:w="50" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar>'
                   '</w:tblPr><w:tblGrid>%s</w:tblGrid>' % grid]
            for ri, row in enumerate(cells):
                trpr = '<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>' if ri == 0 else '<w:trPr><w:cantSplit/></w:trPr>'
                tcs = []
                for ci in range(ncol):
                    txt = row[ci] if ci < len(row) else ''
                    if ri == 0:
                        runs = run(re.sub(r'\*\*', '', txt), True, 'FFFFFF')
                        shade, al = '1F3864', 'center'
                    else:
                        runs = inline_docx(txt)
                        shade, al = ('F7F9FC' if ri % 2 == 0 else None), None
                    tcpr = '<w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s<w:vAlign w:val="center"/></w:tcPr>' % (
                        cols[ci], '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shade if shade else '')
                    tcs.append('<w:tc>%s%s</w:tc>' % (tcpr, para(runs, style='TableText', align=al)))
                tbl.append('<w:tr>%s%s</w:tr>' % (trpr, ''.join(tcs)))
            tbl.append('</w:tbl>')
            body.append(''.join(tbl))
            body.append(para('', after=0, line=200))
            continue
    sect = ('<w:sectPr><w:footerReference w:type="default" r:id="rId3"/><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418" '
            'w:header="845" w:footer="845" w:gutter="0"/><w:docGrid w:linePitch="312"/></w:sectPr>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<w:body>%s%s</w:body></w:document>') % (''.join(body), sect)

STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
<w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/>
</w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:line="340" w:lineRule="auto" w:after="120"/><w:jc w:val="both"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:pageBreakBefore/>
<w:pBdr><w:bottom w:val="single" w:sz="12" w:space="6" w:color="1F3864"/></w:pBdr>
<w:spacing w:before="360" w:after="240" w:line="300" w:lineRule="auto"/><w:jc w:val="left"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:rFonts w:eastAsia="黑体"/><w:b/><w:color w:val="1F3864"/><w:sz w:val="34"/><w:szCs w:val="34"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="300" w:after="140" w:line="300" w:lineRule="auto"/><w:jc w:val="left"/><w:outlineLvl w:val="1"/></w:pPr>
<w:rPr><w:rFonts w:eastAsia="黑体"/><w:b/><w:color w:val="2E5496"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="220" w:after="100" w:line="300" w:lineRule="auto"/><w:jc w:val="left"/><w:outlineLvl w:val="2"/></w:pPr>
<w:rPr><w:rFonts w:eastAsia="黑体"/><w:b/><w:color w:val="1F3864"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="180" w:after="80" w:line="300" w:lineRule="auto"/><w:jc w:val="left"/><w:outlineLvl w:val="3"/></w:pPr>
<w:rPr><w:rFonts w:eastAsia="黑体"/><w:b/><w:color w:val="404040"/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:basedOn w:val="Normal"/>
<w:pPr><w:spacing w:before="10" w:after="10" w:line="264" w:lineRule="auto"/><w:jc w:val="left"/></w:pPr>
<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:style>
</w:styles>'''

FOOTER = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="0"/></w:pPr>
<w:r><w:rPr><w:color w:val="8C8C8C"/><w:sz w:val="17"/></w:rPr><w:t xml:space="preserve">软考中级网络工程师 · 近三年真题研究与考点精讲     </w:t></w:r>
<w:fldSimple w:instr=" PAGE "><w:r><w:rPr><w:color w:val="8C8C8C"/><w:sz w:val="17"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>
</w:p></w:ftr>'''

SETTINGS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:zoom w:percent="100"/><w:defaultTabStop w:val="420"/>
<w:characterSpacingControl w:val="compressPunctuation"/>
<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
<w:themeFontLang w:val="en-US" w:eastAsia="zh-CN"/></w:settings>'''

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''

RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''

DOC_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
</Relationships>'''

def core_xml(meta):
    now = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>%s</dc:title><dc:subject>%s</dc:subject><dc:creator>%s</dc:creator>'
            '<cp:keywords>软考,网络工程师,真题,考点</cp:keywords>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>'
            '<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>'
            '</cp:coreProperties>') % (xesc(meta.get('title', '')), xesc(meta.get('subtitle', '')),
                                       xesc(meta.get('author', '')), now, now)

APP_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
           'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
           '<Application>DSH Document Builder</Application><DocSecurity>0</DocSecurity>'
           '<ScaleCrop>false</ScaleCrop><Company></Company><LinksUpToDate>false</LinksUpToDate>'
           '<SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged>'
           '<AppVersion>16.0000</AppVersion></Properties>')

def write_docx(meta, blocks, path):
    doc = build_document(meta, blocks)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', CONTENT_TYPES)
        z.writestr('_rels/.rels', RELS)
        z.writestr('word/document.xml', doc)
        z.writestr('word/styles.xml', STYLES)
        z.writestr('word/settings.xml', SETTINGS)
        z.writestr('word/footer1.xml', FOOTER)
        z.writestr('word/_rels/document.xml.rels', DOC_RELS)
        z.writestr('docProps/core.xml', core_xml(meta))
        z.writestr('docProps/app.xml', APP_XML)

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

def html_to_pdf(html_path, pdf_path):
    if os.path.exists(pdf_path): os.remove(pdf_path)
    node_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pdf.mjs')
    if os.path.exists(node_script):
        r = subprocess.run(['node', node_script, html_path, pdf_path],
                           capture_output=True, text=True, timeout=240)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000:
            return
        print('NODE PDF STDERR:', r.stderr[-1500:])
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
           '--run-all-compositor-stages-before-draw', '--virtual-time-budget=15000',
           '--print-to-pdf=' + pdf_path, 'file://' + os.path.abspath(html_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not os.path.exists(pdf_path):
        print('CHROME STDERR:', r.stderr[-2000:])
        raise SystemExit('PDF generation failed')

def read_meta(md):
    meta = {}
    lines = md.split('\n')
    meta['title'] = lines[0].lstrip('# ').strip() if lines and lines[0].startswith('# ') else 'document'
    for ln in lines[:8]:
        m = re.match(r'>\s*(副标题|主题)[:：]\s*(.*)', ln.strip())
        if m: meta['subtitle'] = m.group(2).strip()
        m2 = re.match(r'>\s*([^：|]{2,10})[：:]\s*(.*)', ln.strip())
        if m2 and m2.group(1) in ('版本', '成文日期', '编制', '适用'):
            meta[m2.group(1)] = m2.group(2).split('｜')[0].strip()
    meta.setdefault('subtitle', '')
    meta.setdefault('kicker', '软考 · 中级 · 网络工程师')
    meta.setdefault('author', 'DSH 研究整理')
    return meta

def main():
    md_path, out_base = sys.argv[1], sys.argv[2]
    md = open(md_path, encoding='utf-8').read()
    meta = read_meta(md)
    blocks = parse_md(md)
    here = os.path.dirname(os.path.abspath(__file__))
    html_out = out_base + '.html'
    open(html_out, 'w', encoding='utf-8').write(render_html(meta, blocks, os.path.join(here, 'style.css')))
    write_docx(meta, blocks, out_base + '.docx')
    html_to_pdf(html_out, out_base + '.pdf')
    print('OK', out_base, os.path.getsize(out_base + '.docx'), os.path.getsize(out_base + '.pdf'))

if __name__ == '__main__':
    main()

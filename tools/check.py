#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产物自检：PDF 页数与纸张、DOCX 包结构与 XML、Markdown 目录完整性。

用法：python3 tools/check.py dist/<basename>
退出码 0 表示全部通过。
"""
import os
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

FENCE = chr(96) * 3

REQUIRED_DOCX_PARTS = [
    '[Content_Types].xml', '_rels/.rels', 'word/document.xml', 'word/styles.xml',
    'word/settings.xml', 'word/footer1.xml', 'word/_rels/document.xml.rels',
    'docProps/core.xml', 'docProps/app.xml',
]

fails = []

def ok(msg):
    print('  OK  ' + msg)

def bad(msg):
    fails.append(msg)
    print('  FAIL ' + msg)

def check_pdf(path):
    print('PDF')
    if not os.path.exists(path):
        bad('缺少文件 ' + path)
        return
    try:
        out = subprocess.run(['pdfinfo', path], capture_output=True, text=True).stdout
    except FileNotFoundError:
        bad('未找到 pdfinfo（需安装 poppler）')
        return
    pages = re.search(r'^Pages:\s+(\d+)', out, re.M)
    size = re.search(r'^Page size:\s+([\d.]+) x ([\d.]+) pts \((\w+)\)', out, re.M)
    if not pages:
        bad('无法读取页数')
        return
    n = int(pages.group(1))
    if n < 10:
        bad('页数异常：%d' % n)
    else:
        ok('页数 %d' % n)
    if size and size.group(3) == 'A4':
        ok('纸张 A4（%s x %s pt）' % (size.group(1), size.group(2)))
    else:
        bad('纸张不是 A4：%s' % (size.group(0) if size else '未知'))

def check_docx(path):
    print('DOCX')
    if not os.path.exists(path):
        bad('缺少文件 ' + path)
        return
    with zipfile.ZipFile(path) as z:
        corrupt = z.testzip()
        if corrupt:
            bad('压缩包损坏：' + corrupt)
        else:
            ok('压缩包完整')
        names = set(z.namelist())
        missing = [p for p in REQUIRED_DOCX_PARTS if p not in names]
        if missing:
            bad('缺少部件：%s' % ', '.join(missing))
        else:
            ok('必需部件齐全（%d 个）' % len(REQUIRED_DOCX_PARTS))
        for part in ('word/document.xml', 'word/styles.xml', 'word/footer1.xml'):
            try:
                ET.fromstring(z.read(part))
            except Exception as exc:  # noqa: BLE001
                bad('%s XML 非法：%s' % (part, exc))
            else:
                ok('%s XML 合法' % part)
        doc = z.read('word/document.xml').decode('utf-8')
        tables = doc.count('<w:tbl>')
        if tables >= 20:
            ok('表格 %d 个' % tables)
        else:
            bad('表格数量异常：%d' % tables)
        if chr(167) in doc:
            bad('正文残留占位符 U+00A7')

def check_md(path):
    print('Markdown')
    if not os.path.exists(path):
        bad('缺少文件 ' + path)
        return
    text = open(path, encoding='utf-8').read()
    if '<!--cover-end-->' not in text:
        bad('缺少封面标记')
    else:
        ok('封面标记存在')
    toc = re.search(r'^## 目录\n(.+?)\n# ', text, re.S | re.M)
    if not toc:
        bad('未找到目录块')
    else:
        block = toc.group(1)
        entries = len(re.findall(r'^\s*-\s', block, re.M))
        numbered = len(re.findall(r'\.{3,}\s*\d+$', block, re.M))
        ok('目录 %d 条，含页码 %d 条' % (entries, numbered))
        if entries < 10:
            bad('目录条目过少')
    if text.count(FENCE) % 2:
        bad('代码围栏数量为奇数，可能未闭合')
    else:
        ok('代码围栏成对')

def main():
    if len(sys.argv) < 2:
        raise SystemExit('用法：python3 tools/check.py dist/<basename>')
    base = sys.argv[1]
    check_md(base + '.md')
    check_pdf(base + '.pdf')
    check_docx(base + '.docx')
    print()
    if fails:
        print('检查未通过：%d 项' % len(fails))
        sys.exit(1)
    print('全部检查通过')

if __name__ == '__main__':
    main()

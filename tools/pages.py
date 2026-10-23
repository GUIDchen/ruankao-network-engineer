#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate heading pages in the rendered PDF and dump heading -> page json."""
import json, re, subprocess, sys

def norm(s):
    return re.sub(r'\s+', '', s)

def main():
    pdf, md_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    txt = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout
    pages = txt.split('\f')
    heads = []
    in_cover = True
    for ln in open(md_path, encoding='utf-8'):
        if ln.strip() == '<!--cover-end-->':
            in_cover = False
        if in_cover:
            continue
        if ln.startswith('# ') or ln.startswith('## '):
            t = ln.lstrip('#').strip()
            if t and t != '目录':
                heads.append(t)
    start = 0
    for i, p in enumerate(pages):
        if norm(p).startswith('摘要与阅读指南'):
            start = i
            break
    lvl1 = set()
    in_cover = True
    for ln in open(md_path, encoding='utf-8'):
        if ln.strip() == '<!--cover-end-->':
            in_cover = False
        if in_cover:
            continue
        if ln.startswith('# '):
            lvl1.add(ln[2:].strip())

    res, missing = {}, []
    for h in heads:
        nh = norm(h)
        found = None
        if h in lvl1:  # level-1 headings start a new page
            for i in range(start, len(pages)):
                if norm(pages[i]).startswith(nh):
                    found = i + 1
                    break
        if found is None:
            for i in range(start, len(pages)):
                if nh in norm(pages[i]):
                    found = i + 1
                    break
        if found:
            res[h] = found
        else:
            missing.append(h)
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('pages found:', len(res), 'missing:', missing[:5])
    print('page1 map sample:', list(res.items())[:3])

if __name__ == '__main__':
    main()

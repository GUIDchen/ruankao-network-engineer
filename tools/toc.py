#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate the TOC block in the markdown, optionally with page numbers."""
import json, re, sys

def width(s):
    return sum(2 if ord(c) > 127 else 1 for c in s)

def main():
    md_path = sys.argv[1]
    mapping = {}
    if '--map' in sys.argv:
        mapping = json.load(open(sys.argv[sys.argv.index('--map') + 1], encoding='utf-8'))

    lines = open(md_path, encoding='utf-8').read().split('\n')

    heads = []
    in_cover = True
    for ln in lines:
        if ln.strip() == '<!--cover-end-->':
            in_cover = False
            continue
        if in_cover:
            continue
        if ln.startswith('# ') or ln.startswith('## '):
            t = ln.lstrip('#').strip()
            if t and t != '目录':
                lvl = 1 if ln.startswith('# ') else 2
                heads.append((lvl, t))

    entries = []
    for lvl, t in heads:
        page = mapping.get(t)
        pad_to = 66 if lvl == 1 else 64
        label = ('**%s**' % t) if lvl == 1 else t
        raw_w = width(t) + (2 if lvl == 1 else 0)
        dots = '.' * max(3, pad_to - raw_w)
        tail = (' %s %d' % (dots, page)) if page else ''
        prefix = '' if lvl == 1 else '  '
        entries.append('%s- %s%s' % (prefix, label, tail))

    out, i, inside = [], 0, False
    n = len(lines)
    while i < n:
        ln = lines[i]
        if ln.strip() == '## 目录':
            out.append('## 目录')
            out.append('')
            out.extend(entries)
            out.append('')
            i += 1
            while i < n and not lines[i].startswith('# '):
                i += 1
            continue
        out.append(ln)
        i += 1

    open(md_path, 'w', encoding='utf-8').write('\n'.join(out))
    print('toc entries:', len(entries), 'with pages:', sum(1 for l, t in heads if t in mapping))

if __name__ == '__main__':
    main()

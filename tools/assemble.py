#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble src/part*.md into the deliverable markdown."""
import re, sys

BT = chr(96)

def split_options(line):
    if not re.match(r'^\**A\.\s', line.strip()):
        return [line]
    body = line.rstrip()
    if not all((' %s. ' % c) in body for c in 'BCD'):
        return [line]
    idx = [m.start() for m in re.finditer(r'(?<=\s)(?=[ABCD]\.\s)', body)]
    if len(idx) < 3:
        return [line]
    cuts = [0] + idx
    pieces = [body[cuts[i]:cuts[i + 1] if i + 1 < len(cuts) else len(body)].strip() for i in range(len(cuts))]
    pieces = [p for p in pieces if p]
    if len(pieces) != 4:
        return [line]
    total = sum(2 if ord(ch) > 127 else 1 for ch in body)
    if total <= 58:
        return ['A. ' + re.sub(r'^A\.\s*', '', ' '.join(pieces))]
    return [p + ('  ' if i < 3 else '') for i, p in enumerate(pieces)]

def main(parts, out):
    chunks = []
    for p in parts:
        txt = open(p, encoding='utf-8').read()
        lines = []
        for ln in txt.split('\n'):
            if ln.lstrip().startswith('~~~'):
                ln = ln.replace('~~~', BT * 3, 1)
            lines.append(ln)
        txt = '\n'.join(lines).replace('\u00a7', BT).replace('\u3000', ' ')
        # split option lines into one-per-line with hard breaks
        out_lines = []
        for ln in txt.split('\n'):
            out_lines.extend(split_options(ln))
        chunks.append('\n'.join(out_lines).rstrip('\n'))
    final = '\n\n'.join(chunks) + '\n'
    open(out, 'w', encoding='utf-8').write(final)
    print('wrote', out, len(final), 'chars')

if __name__ == '__main__':
    main(['src/part1.md', 'src/part2.md', 'src/part3.md', 'src/part4.md'], sys.argv[1])

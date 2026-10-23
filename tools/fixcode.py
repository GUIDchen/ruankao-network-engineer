import re, sys

def align(lines):
    out = []
    for ln in lines:
        if '#' in ln and not ln.lstrip().startswith('#'):
            code, sep, comment = ln.partition('#')
            if sep and code.endswith(' ') and code.strip():
                code_s = code.rstrip()
                pad = 40 - len(code_s)
                if pad < 2:
                    pad = 2
                ln = code_s + ' ' * pad + '#' + comment
        out.append(ln)
    return out

for path in sys.argv[1:]:
    lines = open(path, encoding='utf-8').read().split('\n')
    out, buf, in_code = [], [], False
    for ln in lines:
        if ln.strip().startswith('~~~'):
            if in_code:
                out.extend(align(buf)); buf = []
            in_code = not in_code
            out.append(ln)
            continue
        if in_code:
            buf.append(ln)
        else:
            out.append(ln)
    open(path, 'w', encoding='utf-8').write('\n'.join(out))
print('aligned')

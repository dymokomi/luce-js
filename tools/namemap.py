import re,sys,collections
def snake(n):
    raw = n.startswith('_')
    n = n.lstrip('_')
    if n.startswith('JS_'): n = n[3:]
    n = n.lstrip('_')
    n = n.replace('UInt','Uint').replace('BigInt','Bigint').replace('HTMLDDA','Htmldda').replace('URI','Uri').replace('JSON','Json').replace('UTF8','Utf8').replace('UTF16','Utf16').replace('ToPrimitive','ToPrimitive')
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', n)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    s = s.lower().replace('__','_')
    if raw: s += '_raw'
    return s
names=set(l.split()[4] for l in open('all_funcs.txt') if len(l.split())>4 and re.match(r'^[A-Za-z_][A-Za-z0-9_]*$',l.split()[4]) and not l.split()[4].startswith('__attr'))
m=collections.defaultdict(list)
for n in sorted(names): m[snake(n)].append(n)
for k,v in m.items():
    if len(v)>1: print("COLLISION",k,v)
with open('namemap.txt','w') as f:
    for k,v in sorted(m.items()):
        for n in v:
            if n!=k: f.write(f"{n} {k}\n")

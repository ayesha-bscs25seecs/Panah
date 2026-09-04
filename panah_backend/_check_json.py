path = r'c:\Projects\Panah\panah_backend\knowledge_base.json'
s = open(path, encoding='utf-8').read()

stack = []
line = 1
i = 0
n = len(s)
in_str = False
pairs = []
while i < n:
    c = s[i]
    if c == '\n':
        line += 1
        i += 1
        continue
    if in_str:
        if c == '\\':
            i += 2
            continue
        if c == '"':
            in_str = False
        i += 1
        continue
    if c == '"':
        in_str = True
        i += 1
        continue
    if c in '{[':
        stack.append((c, line))
    elif c in '}]':
        if stack:
            op, ol = stack.pop()
            pairs.append((line, c, ol))
    i += 1

# print pairings for closers on interesting lines
interesting = [p for p in pairs if p[0] in (1248, 1249, 1250, 1416, 1417, 1418)]
for cl, ch, ol in interesting:
    print('closer %r on line %d matched opener on line %d' % (ch, cl, ol))

# Also show the last 8 pairings in the file
print('--- last 8 pairings ---')
for cl, ch, ol in pairs[-8:]:
    print('closer %r on line %d matched opener on line %d' % (ch, cl, ol))

print('--- openers never closed ---')
for ch, ln in stack:
    print('%r opened at line %d' % (ch, ln))

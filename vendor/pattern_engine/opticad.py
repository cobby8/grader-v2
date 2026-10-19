# OptiCad(«OptiCad Adobe Export») .ai 읽기 — PostScript(AI3) 본문에서 조각·레이어·글자를 꺼낸다
#   parse(path) → (bbox, items)   items: {t:"path", layers:[사이즈?, "CUT|SEW|DRAW"], note:조각이름, seg:[(M|L|C, …pt)]} · {t:"text", …}
#   load_sized(path) → {사이즈: {조각: {cut, sew}}}  — 좌표 mm, y 위쪽(+), 베지어는 16토막으로 편다
import re, json, sys, math
def parse(path):
    txt=open(path,'rb').read().decode('cp949',errors='replace')
    lines=txt.splitlines()
    bbox=None; stack=[]; out=[]; cur=None; note=None; tp=None; tf=None
    for ln in lines:
        s=ln.strip()
        if s.startswith('%%BoundingBox:'): bbox=list(map(float,s.split()[1:]))
        if s.startswith('%AI5_BeginLayer'): stack.append(None); continue
        if s.startswith('%AI5_EndLayer'): stack.pop(); continue
        if s.startswith('%AI3_Note:'): note=s[10:]; continue
        m=re.match(r'^\((.*)\) Ln$',s)
        if m: stack[-1]=m.group(1); continue
        m=re.match(r'^\((.*)\) Tx$',s)
        if m: out.append(dict(t='text',layers=list(stack),s=m.group(1),pos=tp,size=tf)); continue
        p=s.split()
        if not p: continue
        op=p[-1]
        if op=='Tp': tp=[float(p[4]),float(p[5])]
        elif op=='Tf': tf=float(p[1])
        elif op=='m': cur=dict(t='path',layers=list(stack),note=note,seg=[('M',float(p[0]),float(p[1]))])
        elif op in('l','L') and cur and len(p)==3: cur['seg'].append(('L',float(p[0]),float(p[1])))
        elif op in('c','C') and cur and len(p)==7: cur['seg'].append(('C',*map(float,p[:6])))
        elif op in('v','V') and cur: x2,y2,x3,y3=map(float,p[:4]); px,py=cur['seg'][-1][-2:]; cur['seg'].append(('C',px,py,x2,y2,x3,y3))
        elif op in('y','Y') and cur: x1,y1,x3,y3=map(float,p[:4]); cur['seg'].append(('C',x1,y1,x3,y3,x3,y3))
        elif op in('S','s','f','F','b','B','N','n') and cur:
            cur['closed']=op in('s','f','b','n'); cur['op']=op; out.append(cur); cur=None; note=None
    return bbox,out
def pts(seg):
    P=[]
    for s in seg:
        if s[0] in 'ML': P.append(s[1:3])
        else:
            x0,y0=P[-1]; x1,y1,x2,y2,x3,y3=s[1:]
            for k in range(1,9):
                t=k/8; a=(1-t)**3; b=3*(1-t)**2*t; c=3*(1-t)*t*t; d=t**3
                P.append((a*x0+b*x1+c*x2+d*x3, a*y0+b*y1+c*y2+d*y3))
    return P


MM = 25.4 / 72
SIZES13 = ["5XS", "4XS", "3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]


def flat(seg):
    P = []
    for s in seg:
        if s[0] in "ML": P.append((s[1] * MM, s[2] * MM))
        else:
            x0, y0 = P[-1]; x1, y1, x2, y2, x3, y3 = [v * MM for v in s[1:]]
            for k in range(1, 17):
                t = k / 16; a = (1 - t) ** 3; b = 3 * (1 - t) ** 2 * t; c = 3 * (1 - t) * t * t; d = t ** 3
                P.append((a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3))
    return P


def load_sized(path):
    """OptiCad .ai → {사이즈: {조각이름: {cut, sew}}} (한 사이즈 파일이면 사이즈 None 또는 레이어 이름)"""
    _, items = parse(path); out = {}
    for i in items:
        if i["t"] != "path": continue
        lay = i["layers"]; kind = lay[-1]
        size = next((l for l in lay if l in SIZES13), None)
        p = out.setdefault(size, {}).setdefault(i.get("note"), {"cut": None, "sew": None})
        if kind in ("CUT", "SEW") and p[kind.lower()] is None: p[kind.lower()] = flat(i["seg"])
    return out

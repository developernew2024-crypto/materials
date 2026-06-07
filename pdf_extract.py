import sys, zlib, re

def load_objects(data):
    objs = {}
    for m in re.finditer(rb'(\d+)\s+0\s+obj(.*?)endobj', data, re.DOTALL):
        num = int(m.group(1))
        objs[num] = m.group(2)
    return objs

def get_stream(body):
    m = re.search(rb'stream\r?\n(.*?)endstream', body, re.DOTALL)
    if not m: return None
    raw = m.group(1)
    if raw.endswith(b'\r\n'): raw = raw[:-2]
    elif raw.endswith(b'\n'): raw = raw[:-1]
    try:
        return zlib.decompress(raw)
    except Exception:
        return raw

def parse_cmap(stream):
    mapping = {}
    if stream is None: return mapping
    # bfchar
    for blk in re.finditer(rb'beginbfchar(.*?)endbfchar', stream, re.DOTALL):
        for cm in re.finditer(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk.group(1)):
            src = int(cm.group(1),16)
            dsthex = cm.group(2).decode()
            # may be multiple utf16 units
            dst = ''.join(chr(int(dsthex[i:i+4],16)) for i in range(0,len(dsthex),4))
            mapping[src]=dst
    # bfrange
    for blk in re.finditer(rb'beginbfrange(.*?)endbfrange', stream, re.DOTALL):
        for cm in re.finditer(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk.group(1)):
            lo=int(cm.group(1),16); hi=int(cm.group(2),16); start=int(cm.group(3),16)
            for i,code in enumerate(range(lo,hi+1)):
                mapping[code]=chr(start+i)
    return mapping

def build_font_cmaps(objs):
    # font obj num -> cmap dict
    fontcmap = {}
    for num, body in objs.items():
        if b'/ToUnicode' in body:
            m = re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R', body)
            if m:
                tu = int(m.group(1))
                if tu in objs:
                    fontcmap[num] = parse_cmap(get_stream(objs[tu]))
    return fontcmap

def decode_string(s, cmap):
    # s is bytes of pdf string, 2-byte codes
    out=[]
    for i in range(0,len(s)-1,2):
        code = (s[i]<<8)|s[i+1]
        out.append(cmap.get(code, ''))
    return ''.join(out)

def unescape_pdf_string(raw):
    # raw bytes inside (...) with escapes
    out=bytearray()
    i=0
    while i<len(raw):
        c=raw[i]
        if c==0x5c: # backslash
            i+=1
            if i>=len(raw): break
            n=raw[i]
            mp={0x6e:0x0a,0x72:0x0d,0x74:0x09,0x62:0x08,0x66:0x0c,0x28:0x28,0x29:0x29,0x5c:0x5c}
            if n in mp:
                out.append(mp[n]); i+=1
            elif 0x30<=n<=0x37:
                oct_=bytes([n]); i+=1
                for _ in range(2):
                    if i<len(raw) and 0x30<=raw[i]<=0x37:
                        oct_+=bytes([raw[i]]); i+=1
                    else: break
                out.append(int(oct_,8)&0xFF)
            else:
                out.append(n); i+=1
        else:
            out.append(c); i+=1
    return bytes(out)

def decode_content(content, fontmap, fontcmap):
    # fontmap: name(bytes) -> font obj num ; fontcmap: objnum->cmap
    result=[]
    cur_cmap={}
    # tokenize: find Tf, and string ops
    # We process operators sequentially.
    # Find tokens: /Name num Tf | (..)Tj | [..]TJ | Td/TD/T* for spacing/newlines
    i=0
    tokp = re.compile(rb"""/([A-Za-z0-9_.+-]+)\s+[\d.]+\s+Tf|\((?:[^()\\]|\\.)*\)\s*Tj|\[(?:[^\[\]]|\\.)*\]\s*TJ|(-?[\d.]+)\s+(-?[\d.]+)\s+(Td|TD)|T\*|ET""", re.DOTALL)
    last_was_text=False
    for m in tokp.finditer(content):
        tok=m.group(0)
        if tok.endswith(b'Tf'):
            name=m.group(1)
            objn=fontmap.get(b'/'+name) or fontmap.get(name)
            cur_cmap=fontcmap.get(objn, {}) if objn else {}
        elif tok.endswith(b'Tj'):
            sm=re.search(rb'\((.*)\)\s*Tj', tok, re.DOTALL)
            raw=unescape_pdf_string(sm.group(1))
            result.append(decode_string(raw, cur_cmap))
        elif tok.endswith(b'TJ'):
            arr=re.search(rb'\[(.*)\]\s*TJ', tok, re.DOTALL).group(1)
            parts=[]
            for sm in re.finditer(rb'\((?:[^()\\]|\\.)*\)', arr, re.DOTALL):
                raw=unescape_pdf_string(sm.group(0)[1:-1])
                parts.append(decode_string(raw, cur_cmap))
            result.append(''.join(parts))
        elif tok.endswith(b'Td') or tok.endswith(b'TD') or tok==b'T*':
            pass  # per-glyph positioning; real spaces/newlines are encoded in text
    return ''.join(result)

def get_page_fonts(resbody, objs):
    # find /Font << ... >> possibly indirect
    m=re.search(rb'/Font\s*(\d+)\s+0\s+R', resbody)
    fontdict_body=None
    if m:
        fontdict_body=objs.get(int(m.group(1)),b'')
    else:
        m=re.search(rb'/Font\s*<<(.*?)>>', resbody, re.DOTALL)
        if m: fontdict_body=m.group(1)
    fontmap={}
    if fontdict_body:
        for fm in re.finditer(rb'/([A-Za-z0-9_.+-]+)\s+(\d+)\s+0\s+R', fontdict_body):
            fontmap[b'/'+fm.group(1)]=int(fm.group(2))
    return fontmap

def main(path):
    data=open(path,'rb').read()
    objs=load_objects(data)
    fontcmap=build_font_cmaps(objs)
    # find pages in order
    pages=[]
    for num,body in objs.items():
        if re.search(rb'/Type\s*/Page[^s]', body):
            pages.append((num,body))
    # Order pages by /Kids? Simpler: use object number order (often sequential). 
    pages.sort()
    full=[]
    for num,body in pages:
        # resources
        resm=re.search(rb'/Resources\s*(\d+)\s+0\s+R', body)
        if resm:
            resbody=objs.get(int(resm.group(1)),b'')
        else:
            resm=re.search(rb'/Resources\s*<<(.*?)>>', body, re.DOTALL)
            resbody=resm.group(1) if resm else b''
        fontmap=get_page_fonts(resbody, objs)
        # contents
        contents=b''
        cm=re.search(rb'/Contents\s+(\d+)\s+0\s+R', body)
        if cm:
            s=get_stream(objs.get(int(cm.group(1)),b''))
            if s: contents=s
        else:
            am=re.search(rb'/Contents\s*\[(.*?)\]', body, re.DOTALL)
            if am:
                for r in re.finditer(rb'(\d+)\s+0\s+R', am.group(1)):
                    s=get_stream(objs.get(int(r.group(1)),b''))
                    if s: contents+=s+b'\n'
        txt=decode_content(contents, fontmap, fontcmap)
        full.append("\n\n########## PAGE obj %d ##########\n"%num + txt)
    return '\n'.join(full)

if __name__=='__main__':
    out=main(sys.argv[1])
    sys.stdout.buffer.write(out.encode('utf-8','replace'))

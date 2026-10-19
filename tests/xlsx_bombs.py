# -*- coding: utf-8 -*-
"""엑셀 폭탄 4종 — 주문서 읽기(합성 /api/order/parse · 마커 /api/cad/order/counts)가 «열기 전에» 막는지 시험할 때 쓴다.

왜(비유): 엑셀(.xlsx)은 압축 파일이라, 올린 크기는 100KB 남짓인데 풀면 수십 MB XML 이 되고,
  그 XML 을 파이썬이 읽으면 다시 20~30배로 커진다(2026-10-20 재리뷰 실측: 1GB 넘게). 서버 프로세스 안에서 읽으므로 서버가 죽는다.
  ① 스타일 폭탄       xl/styles.xml 에 셀 서식 수십만 개(풀면 약 37MB)
  ② 한 행 230만 칸    시트 한 장의 한 행에 칸 230만 개(약 48MB)
  ③ 공유 문자열 270만  xl/sharedStrings.xml 에 글자 270만 개(약 46MB)
  ④ 시트 3만 장       시트 파일 3만 개(올린 크기 약 10MB · 풀면 약 18MB) — 하나씩은 작아도 열기만 몇 분
모두 «진짜 엑셀처럼» 열리는 구조라 상한이 없으면 openpyxl 이 끝까지 읽으려 든다.
"""
import io
import zipfile


def _base(rows=(("이니셜", "배번", "사이즈"), ("김가", "1", "L"))):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Sheet"
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO(); wb.save(buf)
    return zipfile.ZipFile(io.BytesIO(buf.getvalue()))


def _rewrite(change):
    """기본 엑셀의 항목을 change(이름, 바이트) → 바이트 로 바꿔 다시 묶는다"""
    src = _base(); out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for it in src.infolist():
            z.writestr(it.filename, change(it.filename, src.read(it.filename)))
    return out.getvalue()


def styles_bomb(n=300000):
    def ch(name, data):
        if name != "xl/styles.xml":
            return data
        xf = b'<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="left"/></xf>'
        return data.replace(b'<cellXfs count="1">', b'<cellXfs count="%d">' % (n + 1)).replace(b"</cellXfs>", xf * n + b"</cellXfs>")
    return _rewrite(ch)


def wide_row_bomb(n=2300000):
    def ch(name, data):
        if name != "xl/worksheets/sheet1.xml":
            return data
        return data.replace(b"</sheetData>", b'<row r="3">' + b'<c t="n"><v>1</v></c>' * n + b"</row></sheetData>")
    return _rewrite(ch)


def shared_strings_bomb(n=2700000):
    def ch(name, data):
        if name == "[Content_Types].xml" and b"sharedStrings" not in data:
            return data.replace(b"</Types>", b'<Override PartName="/xl/sharedStrings.xml" '
                                b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>')
        if name == "xl/_rels/workbook.xml.rels" and b"sharedStrings" not in data:
            return data.replace(b"</Relationships>", b'<Relationship Id="rIdSS" Type="http://schemas.openxmlformats.org/officeDocument/'
                                b'2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
        return data
    raw = _rewrite(ch)
    src = zipfile.ZipFile(io.BytesIO(raw)); out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for it in src.infolist():
            z.writestr(it.filename, src.read(it.filename))
        z.writestr("xl/sharedStrings.xml", b'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/'
                   b'spreadsheetml/2006/main" count="%d" uniqueCount="%d">' % (n, n) + b"<si><t>a</t></si>" * n + b"</sst>")
    return out.getvalue()


def many_sheets_bomb(n=30000):
    """시트 n 장 — workbook.xml·rels·[Content_Types] 를 직접 짠다"""
    W = b'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    R = b'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    sheet = (b'<?xml version="1.0" encoding="UTF-8"?><worksheet ' + W + b'><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>x'
             b'</t></is></c></row></sheetData></worksheet>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("[Content_Types].xml", b'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
                   b'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
                   b'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" '
                   b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   + b"".join(b'<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-'
                              b'officedocument.spreadsheetml.worksheet+xml"/>' % i for i in range(1, n + 1)) + b"</Types>")
        z.writestr("_rels/.rels", b'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   b'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                   b'relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", b'<?xml version="1.0" encoding="UTF-8"?><workbook ' + W + b" " + R + b"><sheets>"
                   + b"".join(b'<sheet name="s%d" sheetId="%d" r:id="rId%d"/>' % (i, i, i) for i in range(1, n + 1))
                   + b"</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", b'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
                   b'openxmlformats.org/package/2006/relationships">' + b"".join(
                       b'<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                       b'worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i) for i in range(1, n + 1)) + b"</Relationships>")
        for i in range(1, n + 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet)
    return out.getvalue()


BOMBS = {"styles": styles_bomb, "wide_row": wide_row_bomb, "shared_strings": shared_strings_bomb, "many_sheets": many_sheets_bomb}

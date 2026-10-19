/* ============================================================
   패턴 의뢰 — 목록 풀이 + 도식
   ① resolve(catalog, baseKey, sel)
        고른 부품(sel)대로 사진·치수·질문 칸 목록을 만든다.
        목록 파일(catalog.json)의 when/unless/variants 를 여기서 한 번에 푼다 —
        의뢰 화면과 검토 화면이 같은 규칙을 쓰게 하려고 한곳에 둔다.
   ② render(sel, panel)
        납작하게 편 옷 그림(SVG 문자열)을 그리고, 사진 칸이면 «찍을 자리 틀»,
        치수 칸이면 «줄자 선»을 겹친다. panel 은 목록 파일의 fig 한 칸.
   색은 dg-* 클래스로만 칠한다 — 실제 색은 화면 CSS(var(--...))가 정한다.
   브라우저에선 window.PatternIntake, 노드(점검 스크립트)에선 require 로 쓴다.
   ============================================================ */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PatternIntake = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* ---------- ① 목록 풀이 ---------- */

  // 고른 것 → {"neck:v_rib", "extra:yoke", ...} 꼴의 표식 묶음
  function tokens(sel) {
    const t = new Set();
    for (const [g, v] of Object.entries(sel || {})) {
      if (g === "base") continue;
      if (Array.isArray(v)) v.forEach((x) => t.add(g + ":" + x));
      else if (v) t.add(g + ":" + v);
    }
    return t;
  }

  // 기본 형태의 기본 선택값 (목록 파일의 default)
  function defaults(base) {
    const sel = { base: base.key };
    for (const g of base.groups || []) sel[g.key] = Array.isArray(g.default) ? g.default.slice() : g.default;
    return sel;
  }

  function resolve(catalog, baseKey, sel) {
    const base = (catalog.bases || []).find((b) => b.key === baseKey);
    if (!base || !base.ready) return null;
    const t = tokens(sel);
    const any = (list) => list.some((k) => t.has(k));
    const pick = (item) => {
      if (item.when && !any(item.when)) return null;          // when: 하나라도 맞으면 넣는다
      if (item.unless && any(item.unless)) return null;       // unless: 하나라도 맞으면 뺀다
      const out = Object.assign({}, item);
      for (const v of item.variants || []) if (any(v.when)) Object.assign(out, v);   // 맞는 변형을 순서대로 덮어쓴다
      delete out.variants; delete out.when; delete out.unless;
      return out;
    };
    const list = (arr) => (arr || []).map(pick).filter(Boolean);
    return {
      base,
      shots: list(base.shots),
      measures: list(base.measures).map((m) => Object.assign({ values: [{ key: "v", label: "" }] }, m)),
      questions: list(base.questions),
    };
  }

  /* ---------- ② 도식 ---------- */

  const W = 400, H = 398, CX = 200;                         // 옷 그림 아래 끝 = 쇠자 아래
  const VIEWBOX = { front: [0, 0, W, H], back: [0, 0, W, H], inside: [0, 0, W, H], hood: [70, 50, 280, 370], collar: [30, 140, 340, 160] };

  const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
  const mul = (a, k) => [a[0] * k, a[1] * k];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1];
  const unit = (a) => mul(a, 1 / Math.hypot(a[0], a[1]));
  const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  const mir = (p) => [W - p[0], p[1]];                       // 왼쪽 점 → 오른쪽 점 (좌우 대칭)
  const r1 = (n) => Math.round(n * 10) / 10;
  const pt = (p) => r1(p[0]) + "," + r1(p[1]);
  const quad = (a, c, b, t) => { const u = 1 - t; return [u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]; };
  function quadAtY(a, c, b, y) {                             // 2차 곡선 위에서 높이 y 인 점(근사)
    let best = a, bd = Infinity;
    for (let i = 0; i <= 200; i++) { const p = quad(a, c, b, i / 200); const dd = Math.abs(p[1] - y); if (dd < bd) { bd = dd; best = p; } }
    return best;
  }
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  let uidSeq = 0;
  const FS = 16;                                            // 글자 크기 (그림 폭 400 기준)

  // 고른 것에 맞춰 기준점(P)·선(path)·영역(region)을 만든다. 점은 선택과 상관없이 모두 만든다 —
  // 그려지지 않는 부품이라도 점 이름이 없어서 깨지는 일이 없게.
  function geometry(sel) {
    sel = sel || {};
    const t = tokens(sel), has = (k) => t.has(k);
    const neck = sel.neck || "round_rib";
    const long = has("length:long"), raglan = has("sleeve:raglan");
    const P = {}, path = {};

    // 몸판 — 왼쪽(_L)만 정하고 오른쪽은 좌우 대칭
    P.HPS_L = [170, 110]; P.NECK_MID = [CX, 110]; P.TOP_L = [166, 104];
    const drop = { round_rib: 32, v_rib: 70, collar: 24, hood: 30, zip_collar: 16 }[neck] || 32;
    P.FNP = [CX, 110 + drop];                                // 앞목 봉제선 맨 아래 (V 면 꼭짓점)
    P.BNP = [CX, 119];                                       // 뒷목 봉제선 가운데
    P.RIB_B = [CX, 111];                                     // 뒷목 립 끝
    // 비율 ≈ 1cm : 3.4 (M 기준 — 총장 72·가슴 단면 54·어깨 46·긴팔 62)
    P.SP_L = [122, 127]; P.AP_L = [108, 202];
    P.HEM_L = [110, 364]; P.HEM_C = [CX, 364];
    const sideAt = (y) => lerp(P.AP_L, P.HEM_L, (y - P.AP_L[1]) / (P.HEM_L[1] - P.AP_L[1]));
    P.CH_L = sideAt(P.AP_L[1] + 8.5);                        // 겨드랑이 2.5cm 아래
    const fc = [CX, 2 * P.FNP[1] - 110], bc = [CX, 2 * P.BNP[1] - 110];   // 앞목·뒷목 곡선 조절점
    const AC = [127, 176];                                   // 진동(소매 단 선) 곡선 조절점

    // 래글런선 위 끝 — 목 봉제선 위
    P.RAG_F_L = neck === "v_rib" ? lerp(P.HPS_L, P.FNP, 0.2) : quad(P.HPS_L, fc, mir(P.HPS_L), 0.2);
    P.RAG_B_L = quad(P.HPS_L, bc, mir(P.HPS_L), 0.25);

    // 소매 — 어깨끝에서 d 방향으로 뻗는다. n 은 윗선 → 아랫선(겨드랑이 쪽)
    const d = unit(long ? [-0.45, 0.89] : [-0.87, 0.5]);
    const n = [d[1], -d[0]];
    P.CUFF_T_L = add(P.SP_L, mul(d, long ? 211 : 75));
    P.CUFF_B_L = add(P.CUFF_T_L, mul(n, long ? 40 : 60));
    const du = unit(sub(P.AP_L, P.CUFF_B_L));                // 아랫선: 소매 끝 → 겨드랑이
    const cband = { rib: 16, elastic: 11 }[sel.cuff] || 12;
    P.CS_T_L = sub(P.CUFF_T_L, mul(d, cband));               // 커프스(고무줄) 이은 선
    P.CS_B_L = add(P.CUFF_B_L, mul(du, cband));
    P.CF_T_L = sub(P.CUFF_T_L, mul(d, 7));                   // 접어박기 박음선
    P.CF_B_L = add(P.CUFF_B_L, mul(du, 7));
    P.BI_U_L = add(P.AP_L, mul(unit(sub(P.CUFF_B_L, P.AP_L)), 9));   // 겨드랑이 2.5cm 아래(그림 비율)
    P.BI_T_L = add(P.SP_L, mul(d, dot(sub(P.BI_U_L, P.SP_L), d)));    // 그 점에서 윗선에 내린 수직

    // 밑단
    const hband = { rib: 20, elastic: 14 }[sel.hem] || 16;
    P.HEM_IN_L = [P.HEM_L[0] + 16, P.HEM_L[1]];
    P.HF_IN_L = [P.HEM_L[0] + 16, P.HEM_L[1] - 8];
    P.HB_IN_L = [P.HEM_L[0] + 16, P.HEM_L[1] - hband];
    P.HB_L = sideAt(P.HEM_L[1] - hband);
    P.HF_L = sideAt(P.HEM_L[1] - 8);

    // 요크 — V넥이면 V 꼭짓점이 앞 요크선 위에 온다(럭비 저지)
    const yf = neck === "v_rib" ? P.FNP[1] : 168, yb = 160;
    P.YOKE_F_C = [CX, yf]; P.YOKE_B_C = [CX, yb];
    P.YOKE_F_L = raglan ? lerp(P.RAG_F_L, P.AP_L, (yf - P.RAG_F_L[1]) / (P.AP_L[1] - P.RAG_F_L[1])) : quadAtY(P.SP_L, AC, P.AP_L, yf);
    P.YOKE_B_L = raglan ? lerp(P.RAG_B_L, P.AP_L, (yb - P.RAG_B_L[1]) / (P.AP_L[1] - P.RAG_B_L[1])) : quadAtY(P.SP_L, AC, P.AP_L, yb);

    // 인서트 — V넥이면 V 아래, 아니면 목 앞 가운데 아래 작은 조각
    const vInsert = neck === "v_rib";
    if (vInsert) {
      const yTop = P.FNP[1] - 34, a = [175, 103], b = [CX, P.FNP[1] - 12];
      P.INS_T_L = [lerp(a, b, (yTop - a[1]) / (b[1] - a[1]))[0], yTop];
      P.INS_TC = [CX, yTop]; P.INS_B = [CX, P.FNP[1] - 12];
    } else {
      P.INS_T_L = [188, P.FNP[1] + 8]; P.INS_TC = [CX, P.FNP[1] + 8]; P.INS_B = [CX, P.FNP[1] + 30];
    }
    P.INS_T_R = mir(P.INS_T_L);

    // 옆 절개
    P.SPN_TO_L = sideAt(P.AP_L[1] + 8);
    P.SPN_T_L = add(P.SPN_TO_L, [26, 0]);
    P.SPN_B_L = add(P.HEM_L, [26, 0]);

    // 지퍼
    P.ZC_TOP = [CX, 94];
    P.ZIP_TOP = neck === "zip_collar" ? P.ZC_TOP : [CX, P.FNP[1] + 2];
    P.ZIP_BOT = has("extra:front_zip") ? [CX, P.HEM_L[1] - 6] : [CX, P.FNP[1] + 62];

    // 주머니 — 후드인데 앞 지퍼가 없으면 캥거루, 아니면 옆 입구(양쪽)
    const kangaroo = neck === "hood" && !has("extra:front_zip");
    if (kangaroo) { P.PK_A = [160, 262]; P.PK_B = [148, 302]; P.PK_D = [160, 340]; P.PK_HEM = [148, P.HEM_L[1]]; }
    else { P.PK_A = [140, 266]; P.PK_B = [150, 308]; P.PK_D = [140, 330]; P.PK_HEM = [150, P.HEM_L[1]]; }

    // 옆 트임 · 시접
    P.SLIT_TOP_L = sideAt(P.HEM_L[1] - 34);
    P.SEAM_A_L = sideAt(260); P.SEAM_B_L = add(P.SEAM_A_L, [5, 0]);   // 오버록 띠(안쪽 5)

    // 칼라 여밈(앞)
    P.PLK_T = [CX, P.FNP[1]]; P.PLK_B = [CX, P.FNP[1] + 58];
    P.PLK_W_L = [192, P.FNP[1] + 44]; P.PLK_W_R = [208, P.FNP[1] + 44];

    // 펼친 칼라 (칼라 그림)
    const cIn = [[72, 262], [CX, 206], [328, 262]], cOut = [[50, 226], [CX, 150], [350, 226]];
    P.COL_IN_C = quad(cIn[0], cIn[1], cIn[2], 0.5); P.COL_OUT_C = quad(cOut[0], cOut[1], cOut[2], 0.5);
    P.COL_TIP_L = cOut[0]; P.COL_TIP_R = cOut[2];
    path.collar_outer = Array.from({ length: 21 }, (_, i) => quad(cOut[0], cOut[1], cOut[2], i / 20));
    path.collar_inner = Array.from({ length: 21 }, (_, i) => quad(cIn[0], cIn[1], cIn[2], i / 20));

    // 옆으로 편 후드 (후드 그림)
    P.HD_NECK = [205, 392]; P.HD_TOP = [205, 80]; P.HD_FACE = [107, 239]; P.HD_BACK = [318, 239];

    // 오른쪽 점 = 왼쪽 점의 좌우 대칭
    for (const k of Object.keys(P)) if (k.endsWith("_L") && !P[k.slice(0, -2) + "_R"]) P[k.slice(0, -2) + "_R"] = mir(P[k]);
    for (const k of ["PK_A", "PK_B", "PK_D", "PK_HEM"]) P[k + "_R"] = mir(P[k]);       // 주머니는 이름에 _L 이 없다

    const box = (pts, pad) => {
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      return [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad];
    };
    const neckTop = neck === "hood" ? 22 : neck === "zip_collar" ? 82 : 96;
    const neckBot = neck === "collar" ? P.FNP[1] + 64 : P.FNP[1] + 14;
    const region = {
      whole: () => box([P.CUFF_T_L, P.CUFF_T_R, P.HEM_L, P.HEM_R, [CX, neck === "hood" ? 24 : neck === "zip_collar" ? 84 : 100]], 10),
      neck: () => [158, neckTop, 242, neckBot],
      neck_b: () => [158, neck === "hood" ? 18 : 82, 242, 132],
      rib_b: () => [180, 100, 220, 128],
      armpit_l: (view) => raglan ? box([view === "back" ? P.RAG_B_L : P.RAG_F_L, P.AP_L], 16) : box([P.SP_L, P.AP_L], 16),
      yoke_l: (view) => { const p = view === "back" ? P.YOKE_B_L : P.YOKE_F_L; return [p[0] - 18, p[1] - 22, p[0] + 36, p[1] + 22]; },
      cuff_l: () => box([P.CUFF_T_L, P.CUFF_B_L, sub(P.CUFF_T_L, mul(d, 28)), add(P.CUFF_B_L, mul(du, 28))], 8),
      hem_side_l: () => [P.HEM_L[0] - 16, P.HEM_L[1] - 42, P.HEM_L[0] + 40, P.HEM_L[1] + 10],
      label: () => [[189, 116, 211, 136], [P.HEM_L[0] - 3, 296, P.HEM_L[0] + 20, 328]],
      placket: () => [176, P.FNP[1] - 10, 224, P.FNP[1] + 66],
      zip_top: () => box([P.ZIP_TOP], 14),
      zip_bottom: () => box([P.ZIP_BOT], 14),
      insert: () => box([P.INS_T_L, P.INS_T_R, P.INS_B], 10),
      side_panel_l: () => [P.SPN_TO_L[0] - 8, P.AP_L[1] - 4, P.SPN_T_L[0] + 12, P.HEM_L[1] + 6],
      pocket_l: () => box([P.PK_A, P.PK_B, P.PK_D, P.PK_HEM], 10),
      slit_l: () => [P.HEM_L[0] - 14, P.SLIT_TOP_L[1] - 10, P.HEM_L[0] + 22, P.HEM_L[1] + 8],
      seam_l: () => [P.SEAM_A_L[0] - 18, 244, P.SEAM_A_L[0] + 28, 276],
      collar_flat: () => [40, 140, 360, 272],
      hood_flat: () => [92, 70, 330, 402],
    };

    const vbTop = neck === "hood" ? 12 : neck === "zip_collar" ? 72 : 86;   // 옷 그림 위 끝 (빈 곳 없이)
    return { sel, vbTop, neck, long, raglan, kangaroo, vInsert, P, path, region, d, du, n, fc, bc, AC, has, sideAt };
  }

  /* ---------- 옷 그림 ---------- */

  function silhouette(P) {
    const R = (k) => mir(P[k]);
    return "M" + pt(P.TOP_L) + " L" + pt(P.SP_L) + " L" + pt(P.CUFF_T_L) + " L" + pt(P.CUFF_B_L) + " L" + pt(P.AP_L) +
      " L" + pt(P.HEM_L) + " L" + pt(R("HEM_L")) + " L" + pt(R("AP_L")) + " L" + pt(R("CUFF_B_L")) + " L" + pt(R("CUFF_T_L")) +
      " L" + pt(R("SP_L")) + " L" + pt(R("TOP_L")) + " Q" + pt([CX, 118]) + " " + pt(P.TOP_L) + " Z";
  }

  // 앞목 곡선 (V 는 꺾은선) — from 에서 to 로
  function frontNeck(G, reverse) {
    const { P, fc } = G, a = reverse ? P.HPS_R : P.HPS_L, b = reverse ? P.HPS_L : P.HPS_R;
    return G.neck === "v_rib" ? " L" + pt(P.FNP) + " L" + pt(b) : " Q" + pt(fc) + " " + pt(b);
  }

  function drawGarment(G, view) {
    const { P } = G, o = [], R = (k) => mir(P[k]);
    const front = view !== "back", inside = view === "inside";
    const seams = [];                                        // 안쪽 그림에서 오버록 띠를 깔 봉제선

    // 1) 후드는 어깨 뒤에 깔린다 — 몸판보다 먼저
    if (G.neck === "hood" && front) o.push('<path class="dg-body' + (inside ? " dg-body--in" : "") + '" d="M164,114 C142,62 160,30 200,28 C240,30 258,62 236,114 Z"/>');

    // 2) 몸판 윤곽
    const clip = "dgc" + (++uidSeq);
    o.push('<clipPath id="' + clip + '"><path d="' + silhouette(P) + '"/></clipPath>');
    o.push('<path class="dg-body' + (inside ? " dg-body--in" : "") + '" d="' + silhouette(P) + '"/>');

    // 3) 목
    const backSeam = "M" + pt(P.HPS_L) + " Q" + pt(G.bc) + " " + pt(P.HPS_R);
    const backBand = "M" + pt(P.TOP_L) + " Q" + pt([CX, 118]) + " " + pt(R("TOP_L")) + " L" + pt(P.HPS_R) + " Q" + pt(G.bc) + " " + pt(P.HPS_L) + " Z";
    if (front) {
      // 목 구멍으로 보이는 뒤판 안쪽
      o.push('<path class="dg-in" d="' + backSeam + frontNeck(G, true) + ' Z"/>');
      if (G.neck === "round_rib" || G.neck === "v_rib") {
        o.push('<path class="dg-rib" d="' + backBand + '"/>');
        const inner = G.neck === "v_rib"
          ? " L226,103 L" + pt([CX, P.FNP[1] - 12]) + " L174,103 Z"
          : " L228,103 Q" + pt([CX, 2 * (P.FNP[1] - 9) - 103]) + " 172,103 Z";
        o.push('<path class="dg-rib" d="M' + pt(P.HPS_L) + frontNeck(G, false) + inner + '"/>');
      } else if (G.neck === "collar") {
        o.push('<path class="dg-body" d="' + backBand + '"/>');
        o.push('<rect class="dg-body" x="192" y="' + r1(P.FNP[1]) + '" width="16" height="58"/>');
        o.push('<circle class="dg-button" cx="200" cy="' + r1(P.FNP[1] + 22) + '" r="2.4"/><circle class="dg-button" cx="200" cy="' + r1(P.FNP[1] + 42) + '" r="2.4"/>');
        o.push('<path class="dg-body" d="M166,106 L184,158 L199,141 L199,130 Q186,118 166,106 Z"/>');
        o.push('<path class="dg-body" d="M234,106 L216,158 L201,141 L201,130 Q214,118 234,106 Z"/>');
      } else if (G.neck === "hood") {
        o.push('<path class="dg-in" d="M176,122 C170,82 182,56 200,55 C218,56 230,82 224,122 Z"/>');
      } else if (G.neck === "zip_collar") {
        o.push('<path class="dg-in" d="M172,88 Q200,80 228,88 L230,110 Q' + pt(G.bc) + ' 170,110 Z"/>');
        o.push('<path class="dg-body" d="M170,110 L172,88 Q200,100 228,88 L230,110' + " Q" + pt(G.fc) + ' 170,110 Z"/>');
      }
      o.push('<path class="dg-seam" d="M' + pt(P.HPS_L) + frontNeck(G, false) + '"/>');
      seams.push("M" + pt(P.HPS_L) + frontNeck(G, false));
    } else {
      if (G.neck === "round_rib" || G.neck === "v_rib") o.push('<path class="dg-rib" d="' + backBand + '"/>');
      else if (G.neck === "collar") o.push('<path class="dg-body" d="M164,100 Q200,108 236,100 L' + pt(P.HPS_R) + " Q" + pt(G.bc) + " " + pt(P.HPS_L) + ' Z"/>');
      else if (G.neck === "zip_collar") o.push('<path class="dg-body" d="M170,110 L172,88 Q200,82 228,88 L230,110 Q' + pt(G.bc) + ' 170,110 Z"/>');
      if (G.neck === "hood") {
        o.push('<path class="dg-body" d="M162,118 C136,66 158,24 200,22 C242,24 264,66 238,118 Q200,128 162,118 Z"/>');
        o.push('<path class="dg-seam" d="M200,22 L200,124"/>');
      }
      o.push('<path class="dg-seam" d="' + backSeam + '"/>');
    }

    // 4) 소매 달림 — 일반: 어깨선 + 진동 곡선 / 래글런: 목에서 겨드랑이로 사선
    for (const side of ["L", "R"]) {
      const S = (k) => (side === "L" ? P[k + "_L"] : P[k + "_R"]);
      const ac = side === "L" ? G.AC : mir(G.AC);
      if (G.raglan) {
        const top = front ? S("RAG_F") : S("RAG_B"), ap = S("AP");
        const c = add(lerp(top, ap, 0.5), [side === "L" ? -6 : 6, 4]);
        const dd = "M" + pt(top) + " Q" + pt(c) + " " + pt(ap);
        o.push('<path class="dg-seam" d="' + dd + '"/>'); seams.push(dd);
      } else {
        const dd = "M" + pt(S("HPS")) + " L" + pt(S("SP")) + " Q" + pt(ac) + " " + pt(S("AP"));
        o.push('<path class="dg-seam" d="' + dd + '"/>'); seams.push(dd);
      }
      seams.push("M" + pt(S("AP")) + " L" + pt(S("HEM")), "M" + pt(S("AP")) + " L" + pt(S("CUFF_B")));
    }

    // 5) 요크 · 옆 절개 · 옆 트임
    if (G.has("extra:yoke")) {
      const a = front ? P.YOKE_F_L : P.YOKE_B_L, b = front ? P.YOKE_F_R : P.YOKE_B_R;
      o.push('<path class="dg-seam" d="M' + pt(a) + " L" + pt(b) + '"/>'); seams.push("M" + pt(a) + " L" + pt(b));
    }
    if (G.has("extra:side_panel")) for (const s of ["L", "R"]) {
      const dd = "M" + pt(P["SPN_T_" + s]) + " L" + pt(P["SPN_B_" + s]);
      o.push('<path class="dg-seam" d="' + dd + '"/>'); seams.push(dd);
    }
    if (G.has("extra:side_slit")) for (const s of ["L", "R"]) {
      const hem = P["HEM_" + s], top = P["SLIT_TOP_" + s], k = s === "L" ? 1 : -1;
      o.push('<path class="dg-in" d="M' + pt(hem) + " L" + pt(top) + " L" + pt(add(hem, [5 * k, 0])) + ' Z"/>');
      o.push('<path class="dg-tack" d="M' + pt(top) + " L" + pt(add(top, [7 * k, 0])) + '"/>');
    }

    // 6) 소매 끝
    for (const s of ["L", "R"]) {
      const T = P["CUFF_T_" + s], B = P["CUFF_B_" + s], CT = P["CS_T_" + s], CB = P["CS_B_" + s];
      if (G.sel.cuff === "rib" || G.sel.cuff === "elastic") {
        const cls = G.sel.cuff === "rib" ? "dg-rib" : "dg-body";
        o.push('<path class="' + cls + '" d="M' + pt(CT) + " L" + pt(T) + " L" + pt(B) + " L" + pt(CB) + ' Z"/>');
        for (let i = 1; i < 6; i++) {
          const u = i / 6;
          o.push('<path class="' + (G.sel.cuff === "rib" ? "dg-ribline" : "dg-gather") + '" d="M' + pt(lerp(CT, CB, u)) + " L" + pt(lerp(T, B, u)) + '"/>');
        }
        o.push('<path class="dg-seam" d="M' + pt(CT) + " L" + pt(CB) + '"/>'); seams.push("M" + pt(CT) + " L" + pt(CB));
      } else {
        o.push('<path class="dg-stitch" d="M' + pt(P["CF_T_" + s]) + " L" + pt(P["CF_B_" + s]) + '"/>');
      }
    }

    // 7) 밑단
    if (G.sel.hem === "rib" || G.sel.hem === "elastic") {
      const y = P.HB_L[1];
      o.push('<path class="' + (G.sel.hem === "rib" ? "dg-rib" : "dg-body") + '" d="M' + pt(P.HB_L) + " L" + pt(P.HEM_L) + " L" + pt(P.HEM_R) + " L" + pt(P.HB_R) + ' Z"/>');
      for (let x = P.HB_L[0] + 7; x < P.HB_R[0] - 3; x += 7) o.push('<path class="' + (G.sel.hem === "rib" ? "dg-ribline" : "dg-gather") + '" d="M' + r1(x) + "," + r1(y + 2) + " L" + r1(x) + "," + r1(P.HEM_L[1] - 2) + '"/>');
      o.push('<path class="dg-seam" d="M' + pt(P.HB_L) + " L" + pt(P.HB_R) + '"/>'); seams.push("M" + pt(P.HB_L) + " L" + pt(P.HB_R));
    } else {
      o.push('<path class="dg-stitch" d="M' + pt(P.HF_L) + " L" + pt(P.HF_R) + '"/>');
    }

    // 8) 앞에만 있는 것 — 인서트 · 주머니 · 지퍼
    if (front) {
      if (G.has("extra:insert")) {
        const dd = G.vInsert
          ? "M" + pt(P.INS_T_L) + " L" + pt(P.INS_T_R) + " L" + pt(P.INS_B) + " Z"
          : "M" + pt(P.INS_T_L) + " L" + pt(P.INS_T_R) + " L" + pt([P.INS_T_R[0], P.INS_B[1]]) + " L" + pt([P.INS_T_L[0], P.INS_B[1]]) + " Z";
        o.push('<path class="dg-insert" d="' + dd + '"/>'); seams.push(dd);
      }
      if (G.has("extra:pocket")) {
        if (G.kangaroo) {
          o.push('<path class="dg-seam" d="M160,262 L240,262 L254,340 L146,340 Z"/>');
          o.push('<path class="dg-opening" d="M' + pt(P.PK_A) + " L" + pt(P.PK_B) + '"/><path class="dg-opening" d="M' + pt(P.PK_A_R) + " L" + pt(P.PK_B_R) + '"/>');
        } else {
          for (const s of ["L", "R"]) {
            const A = s === "L" ? P.PK_A : P.PK_A_R, B = s === "L" ? P.PK_B : P.PK_B_R, D = s === "L" ? P.PK_D : P.PK_D_R, k = s === "L" ? 1 : -1;
            o.push('<path class="dg-stitch" d="M' + pt(A) + " L" + pt(add(A, [30 * k, 0])) + " L" + pt([A[0] + 30 * k, D[1]]) + " L" + pt(D) + '"/>');
            o.push('<path class="dg-opening" d="M' + pt(A) + " L" + pt(B) + '"/>');
          }
        }
      }
      if (G.neck === "zip_collar" || G.has("extra:front_zip")) {
        o.push('<path class="dg-zip" d="M' + pt(P.ZIP_TOP) + " L" + pt(P.ZIP_BOT) + '"/>');
        o.push('<rect class="dg-zippull" x="' + r1(P.ZIP_TOP[0] - 3) + '" y="' + r1(P.ZIP_TOP[1] + 2) + '" width="6" height="11" rx="2"/>');
      }
    }

    // 9) 안쪽 그림 — 봉제선마다 오버록 띠(옷 안쪽으로만), 라벨
    if (inside) {
      o.push('<g clip-path="url(#' + clip + ')">' + seams.map((dd) => '<path class="dg-overlock" d="' + dd + '"/>').join("") + "</g>");
      o.push('<rect class="dg-labeltag" x="193" y="120" width="14" height="12" rx="1.5"/>');
      o.push('<rect class="dg-labeltag" x="' + r1(P.HEM_L[0] + 1) + '" y="300" width="15" height="24" rx="1.5"/>');
    }
    return o.join("");
  }

  function drawHood() {
    return '<path class="dg-body" d="M120,382 C100,300 98,170 140,120 C165,90 185,80 205,80 C270,80 318,150 318,232 C318,300 306,350 292,392 Q205,398 120,382 Z"/>' +
      '<path class="dg-rib" d="M120,382 C100,300 98,170 140,120 C165,90 185,80 205,80 L205,90 C188,90 170,98 148,126 C110,175 112,300 130,380 Z"/>' +
      '<path class="dg-seam" d="M292,392 Q205,398 120,382"/>';
  }
  function drawCollar(G) {
    const o = G.path.collar_outer, i = G.path.collar_inner;
    const d = "M" + pt(o[0]) + o.slice(1).map((p) => " L" + pt(p)).join("") + " L" + pt(i[20]) + i.slice(0, 20).reverse().map((p) => " L" + pt(p)).join("") + " Z";
    return '<path class="dg-body" d="' + d + '"/>' + '<path class="dg-stitch" d="M' + i.map(pt).join(" L") + '"/>';
  }

  /* ---------- 표시 (틀 · 줄자 선 · 글자) ---------- */

  const NAMES = {
    HPS: "옆목점", SP: "어깨끝", AP: "겨드랑이점", CH: "옆선", HEM: "밑단 끝", HEM_C: "밑단 끝",
    CUFF_T: "소매 끝", CUFF_B: "소매 끝", NECK_MID: "옆목점 잇는 선", BNP: "뒷목 봉제선",
    RAG_F: "목 봉제선", RAG_B: "목 봉제선", YOKE_F_C: "요크 이음선", YOKE_B_C: "요크 이음선",
  };
  function nameOf(k, sel) {
    if (k === "FNP") return sel.neck === "v_rib" ? "V 꼭짓점" : "앞목 맨 아래";
    return NAMES[k] || NAMES[k.replace(/_[LR]$/, "")] || "";
  }
  function getP(G, k) {
    const p = G.P[k];
    if (!p) throw new Error("도식: 모르는 점 이름 " + k);
    return p;
  }
  function getRegion(G, name, view) {
    const f = G.region[name];
    if (!f) throw new Error("도식: 모르는 영역 이름 " + name);
    const r = f(view);
    return Array.isArray(r[0]) ? r : [r];                   // 상자 하나 또는 여러 개
  }
  const unionBox = (bs) => [Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))];
  // 확대 그림 — 너무 가늘거나 납작하지 않게 가로:세로 1.15~1.8, 최소 폭 90
  function fitBox(b) {
    let [x0, y0, x1, y1] = b, w = x1 - x0, h = y1 - y0;
    if (w < 90) { x0 -= (90 - w) / 2; x1 += (90 - w) / 2; w = 90; }
    if (w / h < 1.15) { const nw = h * 1.15; x0 -= (nw - w) / 2; x1 += (nw - w) / 2; w = nw; }
    if (w / h > 1.8) { const nh = w / 1.8; y0 -= (nh - h) / 2; y1 += (nh - h) / 2; h = nh; }
    return [x0, y0, x1, y1];
  }

  // 줄자 선 하나의 점 목록과 끝 글자 위치
  function linePts(G, ln) {
    if (ln.path) { const p = G.path[ln.path]; if (!p) throw new Error("도식: 모르는 선 이름 " + ln.path); return p; }
    return [ln.a].concat(ln.via || [], [ln.b]).map((k) => getP(G, k));
  }
  function labelAt(p, u, text, s) {                         // u: 선 끝에서 바깥쪽 방향
    const q = add(p, mul(u, 9 * s));
    let anchor = "middle", dy = 4 * s;
    if (Math.abs(u[0]) > 0.5) anchor = u[0] < 0 ? "end" : "start";
    if (u[1] < -0.5) dy = -2 * s; else if (u[1] > 0.5) dy = 13 * s;
    return { x: q[0], y: q[1] + dy, anchor, text };
  }
  function midLabel(a, b, text, s) {
    const u = unit(sub(b, a)); let nn = [-u[1], u[0]];
    if (nn[1] > 0.01 || (Math.abs(nn[1]) <= 0.01 && nn[0] > 0)) nn = mul(nn, -1);   // 위쪽(또는 왼쪽)으로
    const m = add(lerp(a, b, 0.5), mul(nn, 9 * s));
    const anchor = Math.abs(nn[0]) > 0.5 ? (nn[0] < 0 ? "end" : "start") : "middle";
    return { x: m[0], y: m[1] + (nn[1] < -0.5 ? -1 * s : 4 * s), anchor, text };
  }
  function textBox(l, fs) {
    const w = [...l.text].reduce((acc, ch) => acc + (ch === " " ? 0.35 : /[\x20-\x7e]/.test(ch) ? 0.6 : 1), 0) * fs;
    const x0 = l.anchor === "start" ? l.x : l.anchor === "end" ? l.x - w : l.x - w / 2;
    return [x0, l.y - fs, x0 + w, l.y + 2];
  }

  function marks(G, panel, s) {
    const out = [], labels = [], allPts = [];
    for (const ln of panel.refs || []) {
      const a = getP(G, ln.a), b = getP(G, ln.b);
      out.push('<path class="dg-ref" d="M' + pt(a) + " L" + pt(b) + '"/>');
      if (ln.note) labels.push(Object.assign(midLabel(a, b, ln.note, s), { cls: "dg-note" }));
      allPts.push(a, b);
    }
    for (const ln of panel.lines || []) {
      const pts = linePts(G, ln);
      allPts.push(...pts);
      out.push('<path class="dg-line" d="M' + pts.map(pt).join(" L") + '"/>');
      const a = pts[0], b = pts[pts.length - 1];
      const ua = unit(sub(pts[0], pts[1])), ub = unit(sub(b, pts[pts.length - 2]));
      for (const [p, u] of [[a, ua], [b, ub]]) {
        const nn = [-u[1] * 6 * s, u[0] * 6 * s];
        out.push('<path class="dg-tick" d="M' + pt(add(p, nn)) + " L" + pt(sub(p, nn)) + '"/>');
        out.push('<circle class="dg-dot" cx="' + r1(p[0]) + '" cy="' + r1(p[1]) + '" r="' + r1(2.6 * s) + '"/>');
      }
      const la = ln.la !== undefined ? ln.la : ln.a ? nameOf(ln.a, G.sel) : "";
      const lb = ln.lb !== undefined ? ln.lb : ln.b ? nameOf(ln.b, G.sel) : "";
      if (la) labels.push(labelAt(a, ua, la, s));
      if (lb) labels.push(labelAt(b, ub, lb, s));
      if (ln.mid) labels.push(Object.assign(midLabel(pts[0], pts[1], ln.mid, s), { cls: "dg-text dg-text--mid" }));
    }
    return { out, labels, allPts };
  }

  function render(sel, panel, opts) {
    opts = opts || {};
    const G = geometry(sel);
    const view = panel.view;
    if (!VIEWBOX[view]) throw new Error("도식: 모르는 그림 " + view);
    let vb = VIEWBOX[view].slice();
    vb = [vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3]];       // [x0,y0,x1,y1]
    if (view === "front" || view === "back" || view === "inside") vb[1] = G.vbTop;

    if (panel.zoom) {
      const base = unionBox(getRegion(G, panel.zoom, view));
      const first = marks(G, panel, 1);
      let b = fitBox(unionBox([base].concat(first.allPts.length ? [unionBox(first.allPts.map((p) => [p[0], p[1], p[0], p[1]]))] : [])).map((v, i) => v + (i < 2 ? -8 : 8)));
      const s0 = (b[2] - b[0]) / W;                           // 글자 크기를 화면에서 같게 하려는 비율
      const m0 = marks(G, panel, s0);
      b = fitBox(unionBox([b].concat(m0.labels.map((l) => textBox(l, FS * s0)))).map((v, i) => v + (i < 2 ? -3 * s0 : 3 * s0)));
      vb = b;
    }
    const s = (vb[2] - vb[0]) / W, fs = FS * s;
    const m = marks(G, panel, s);

    const body = view === "hood" ? drawHood() : view === "collar" ? drawCollar(G) : drawGarment(G, view);
    const o = [body];

    // 사진 칸 — 찍을 자리 틀과 사진기 표시
    for (const name of panel.frame || []) {
      for (const r of getRegion(G, name, view)) {
        const p = 4 * s;
        o.push('<rect class="dg-frame" x="' + r1(r[0] - p) + '" y="' + r1(r[1] - p) + '" width="' + r1(r[2] - r[0] + 2 * p) + '" height="' + r1(r[3] - r[1] + 2 * p) + '" rx="' + r1(7 * s) + '"/>');
        const cx = r[0] - p + 2 * s, cy = r[1] - p - 2 * s, k = 1.1 * s;
        o.push('<g class="dg-cam" transform="translate(' + r1(cx) + "," + r1(cy) + ") scale(" + r1(k * 100) / 100 + ')"><rect x="-2" y="-9" width="18" height="12" rx="2.5"/><circle class="dg-cam__lens" cx="7" cy="-3" r="3.4"/></g>');
      }
    }
    if (panel.ruler) {                                        // 전체 사진 — 옷 아래에 쇠자
      const y = 380, x0 = 130, x1 = 270;
      o.push('<rect class="dg-ruler" x="' + x0 + '" y="' + y + '" width="' + (x1 - x0) + '" height="9" rx="1.5"/>');
      for (let x = x0 + 7, i = 1; x < x1; x += 7, i++) o.push('<path class="dg-ruler-tick" d="M' + x + "," + y + " L" + x + "," + (y + (i % 5 === 0 ? 6 : 3.5)) + '"/>');
    }

    // 치수 칸 — 기준선·줄자 선·끝 글자
    o.push(...m.out);
    for (const l of m.labels) {
      const bx = textBox(l, fs);                              // 그림 밖으로 나가지 않게 밀어 넣기
      let x = l.x;
      if (bx[0] < vb[0] + 2) x += vb[0] + 2 - bx[0];
      if (bx[2] > vb[2] - 2) x -= bx[2] - (vb[2] - 2);
      const y = Math.min(Math.max(l.y, vb[1] + fs + 1), vb[3] - 3);
      o.push('<text class="' + (l.cls || "dg-text") + '" x="' + r1(x) + '" y="' + r1(y) + '" text-anchor="' + l.anchor + '" font-size="' + r1(fs) + '" stroke-width="' + r1(3.2 * s) + '">' + esc(l.text) + "</text>");
    }
    if (panel.tag) o.push('<text class="dg-tag" x="' + r1(vb[0] + 10 * s) + '" y="' + r1(vb[1] + 20 * s) + '" font-size="' + r1(15 * s) + '">' + esc(panel.tag) + "</text>");

    const label = opts.label ? ' aria-label="' + esc(opts.label) + '"' : "";
    return '<svg class="dg" xmlns="http://www.w3.org/2000/svg" viewBox="' + [vb[0], vb[1], vb[2] - vb[0], vb[3] - vb[1]].map(r1).join(" ") + '" role="img"' + label + ">" + o.join("") + "</svg>";
  }

  // 화면에 넣을 기본 색 — 그레이더 디자인 토큰만 쓴다
  const CSS = [
    ".dg{display:block;width:100%;height:auto}",
    // 옷 선은 확대해도 굵어지지 않게 (오버록 띠만 옷과 같이 커진다)
    ".dg .dg-body,.dg .dg-in,.dg .dg-rib,.dg .dg-insert,.dg .dg-ribline,.dg .dg-gather,.dg .dg-seam,.dg .dg-stitch,.dg .dg-opening,.dg .dg-tack,.dg .dg-zip,.dg .dg-button,.dg .dg-labeltag{vector-effect:non-scaling-stroke}",
    ".dg .dg-body{fill:var(--paper);stroke:var(--ink-700);stroke-width:1.4;stroke-linejoin:round}",
    ".dg .dg-body--in{fill:var(--ink-50)}",
    ".dg .dg-in{fill:var(--ink-100);stroke:var(--ink-700);stroke-width:1.2}",
    ".dg .dg-rib{fill:var(--ink-150);stroke:var(--ink-700);stroke-width:1.2;stroke-linejoin:round}",
    ".dg .dg-insert{fill:var(--ink-200);stroke:var(--ink-700);stroke-width:1.2}",
    ".dg .dg-ribline{stroke:var(--ink-400);stroke-width:.7}",
    ".dg .dg-gather{stroke:var(--ink-400);stroke-width:.8;stroke-dasharray:2 2}",
    ".dg .dg-seam{fill:none;stroke:var(--ink-700);stroke-width:1.1}",
    ".dg .dg-stitch{fill:none;stroke:var(--ink-500);stroke-width:.9;stroke-dasharray:3 2.2}",
    ".dg .dg-opening{fill:none;stroke:var(--ink-800);stroke-width:2.4;stroke-linecap:round}",
    ".dg .dg-tack{stroke:var(--ink-800);stroke-width:2.2}",
    ".dg .dg-zip{stroke:var(--ink-700);stroke-width:3;stroke-dasharray:1.4 1.4}",
    ".dg .dg-zippull{fill:var(--ink-600)}",
    ".dg .dg-button{fill:var(--paper);stroke:var(--ink-700);stroke-width:.9}",
    ".dg .dg-overlock{fill:none;stroke:var(--ink-300);stroke-width:10;stroke-dasharray:1.6 1.2}",
    ".dg .dg-labeltag{fill:var(--paper);stroke:var(--ink-600);stroke-width:.9}",
    ".dg .dg-frame{fill:var(--blue-bg);fill-opacity:.35;stroke:var(--blue-600);stroke-width:2;stroke-dasharray:6 4;vector-effect:non-scaling-stroke}",
    ".dg .dg-cam rect{fill:var(--blue-600)}",
    ".dg .dg-cam .dg-cam__lens{fill:var(--paper)}",
    ".dg .dg-ruler{fill:var(--amber-bg);stroke:var(--amber-600);stroke-width:1}",
    ".dg .dg-ruler-tick{stroke:var(--amber-700);stroke-width:.8}",
    ".dg .dg-line{fill:none;stroke:var(--stiz-red);stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}",
    ".dg .dg-tick{stroke:var(--stiz-red);stroke-width:2;vector-effect:non-scaling-stroke}",
    ".dg .dg-dot{fill:var(--stiz-red)}",
    ".dg .dg-ref{stroke:var(--ink-500);stroke-width:1.2;stroke-dasharray:4 3;vector-effect:non-scaling-stroke}",
    ".dg .dg-text,.dg .dg-note,.dg .dg-tag{font-family:var(--font-sans);paint-order:stroke;stroke:var(--paper);stroke-linejoin:round}",
    ".dg .dg-text{fill:var(--text-strong);font-weight:600}",
    ".dg .dg-text--mid{fill:var(--stiz-red-strong)}",
    ".dg .dg-note{fill:var(--text-muted)}",
    ".dg .dg-tag{fill:var(--text-subtle);font-weight:700}",
  ].join("\n");

  return { tokens, defaults, resolve, geometry, render, CSS };
});

/**
 * illustrator-scripts/ai_to_svg.jsx
 *
 * AI(.ai) → SVG 배치 변환 스크립트 (Adobe Illustrator ExtendScript)
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 목적
 * ─────────────────────────────────────────────────────────────────────────
 *   grader-v2의 그레이딩 엔진(engine/pattern.py)은 패턴 조각을 SVG의
 *   <polyline points="..."> 로 읽는다. 디자이너가 작업한 .ai 사이즈 원본을
 *   엔진이 읽을 수 있는 SVG로 한 번에(배치) 변환하기 위한 스크립트다.
 *
 *   목표 형식(예: data/patterns/농구_U넥_양면/XS.svg):
 *     <svg ... viewBox="0 0 W H">
 *       <defs><style> .st0 { fill:none; stroke:#231815; ... } </style></defs>
 *       <polyline class="st0" points="x y x y ..."/>   ← 조각마다 1개
 *       ...
 *     </svg>
 *   → CSS를 <style>+class(.st0)로 빼는 형식이라 SVGExportOptions에서
 *     cssProperties = ENTITIES 로 맞춘다.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 입력: 이 스크립트와 같은 폴더의 ai_to_svg_input.json
 * ─────────────────────────────────────────────────────────────────────────
 *   두 가지 작성 방식 중 하나를 쓰면 된다.
 *
 *   [방식 1] jobs 배열을 직접 나열 (입력/출력 경로를 하나씩 지정)
 *   {
 *     "jobs": [
 *       { "input_path": "C:/work/uniform/XL.ai",  "output_path": "C:/work/out/XL.svg" },
 *       { "input_path": "C:/work/uniform/L.ai",   "output_path": "C:/work/out/L.svg" }
 *     ]
 *   }
 *
 *   [방식 2] 폴더 + 사이즈 목록 + 파일명 패턴으로 자동 전개 (편리)
 *   {
 *     "input_dir":  "C:/work/uniform",
 *     "output_dir": "C:/work/out",
 *     "sizes": ["5XS", "4XS", "3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL"],
 *     "name_pattern": "양면유니폼_V넥_스탠다드_{size}.ai"
 *   }
 *   → {size} 자리에 sizes의 각 값을 넣어 input_path를 만든다.
 *     예) input_dir/양면유니폼_V넥_스탠다드_XL.ai → output_dir/XL.svg
 *     (출력 파일명은 사이즈명 + ".svg" 로 자동 생성)
 *
 *   ※ 경로는 절대경로 권장. 슬래시(/)·역슬래시(\) 모두 인식한다.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 출력: 같은 폴더의 ai_to_svg_result.json
 * ─────────────────────────────────────────────────────────────────────────
 *   {
 *     "success": true,                  // 전체 중 1개라도 성공하면 true (요약은 summary 참고)
 *     "summary": { "total": 10, "ok": 9, "fail": 1 },
 *     "jobs": [
 *       { "success": true,  "input_path": "...", "output_path": "...XL.svg", "output_size": 12345 },
 *       { "success": false, "input_path": "...", "error": "입력 AI 파일 없음: ..." }
 *     ]
 *   }
 *   ※ input.json 자체가 잘못된 경우(파일 없음/파싱 실패)는
 *     { "success": false, "error": "..." } 형태로만 작성된다.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 실행 방법 (사용자 수동)
 * ─────────────────────────────────────────────────────────────────────────
 *   1. 같은 폴더에 ai_to_svg_input.json 작성 (위 방식 1 또는 2)
 *   2. Illustrator에서  File → Scripts → Other Script...  →  ai_to_svg.jsx 선택
 *   3. 같은 폴더의 ai_to_svg_result.json 을 열어 결과 확인 (ok/fail 개수)
 *
 * ─────────────────────────────────────────────────────────────────────────
 * ⚠️ polyline 보존 리스크 (반드시 읽기)
 * ─────────────────────────────────────────────────────────────────────────
 *   Illustrator의 SVG 내보내기는 패스 모양에 따라 출력 태그가 달라진다.
 *     · 직선으로만 이루어진 패스  → <polyline> / <polygon>  (엔진이 읽음 ✅)
 *     · 곡선(베지어)이 섞인 패스   → <path d="...C...">       (엔진이 못 읽음 ❌)
 *   engine/pattern.py 의 parse_svg()는 <polyline>/<polygon>만 읽으므로,
 *   <path>로 나오면 조각이 0개로 읽혀 그레이딩이 실패한다.
 *
 *   → 그래서 "1개 사이즈를 먼저 시험 변환"한 뒤 아래 검증을 통과하는지
 *     반드시 확인하고 나서 전체 배치를 돌리길 권장한다.
 *
 *   [변환 검증 한 줄] (프로젝트 루트에서 실행, 숫자가 실제 조각 수와 같아야 정상)
 *     python -c "from engine.pattern import parse_svg; print(len(parse_svg(r'C:/work/out/XL.svg')))"
 *     예) 농구 V넥 양면이 앞판/뒤판/넥 3조각이면 → 3 이 나와야 정상.
 *         0 이 나오면 패스가 <path>로 떨어진 것 → 일러스트에서 패스를
 *         '직선 점'으로 정리하거나 다른 export 옵션이 필요하다.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 참고
 * ─────────────────────────────────────────────────────────────────────────
 *   - 골격: grader(v1)/illustrator-scripts/ai_to_pdf.jsx (IIFE + result 보장 패턴)
 *   - 목표 형식: data/patterns/농구_U넥_양면/XS.svg (<style>+class, <polyline>)
 *   - 엔진: engine/pattern.py parse_svg() → List[Polyline] 반환
 */

// 왜 IIFE(즉시 실행 함수)로 감싸는가:
//   ExtendScript 최상위 스크립트에서 `return`은 동작이 보장되지 않는다.
//   함수 안에 넣고 마지막 줄에서 호출하면 모든 실행 경로에서 return이 정상 동작.
(function main() {

    // (1) 스크립트가 위치한 폴더 기준으로 입출력 JSON 경로 계산
    //     File($.fileName)은 현재 실행 중인 .jsx 파일의 절대 경로다.
    var scriptFile = new File($.fileName);
    var scriptDir = scriptFile.parent;
    var inputJsonPath = scriptDir + "/ai_to_svg_input.json";
    var resultJsonPath = scriptDir + "/ai_to_svg_result.json";

    // (2) 결과 JSON을 같은 폴더에 쓰는 헬퍼 (호출 측/사용자가 이 파일로 성공 판정)
    function writeResult(obj) {
        var f = new File(resultJsonPath);
        f.encoding = "UTF-8";
        f.open("w");
        f.write(JSON.stringify(obj));
        f.close();
    }

    // (3) 경로 문자열 끝의 슬래시/역슬래시를 정리하는 헬퍼
    //     방식 2에서 input_dir + "/" + 파일명 으로 합칠 때 중복 슬래시를 피한다.
    function trimTrailingSlash(p) {
        return String(p).replace(/[\\\/]+$/, "");
    }

    // (4) 출력 파일이 들어갈 폴더가 없으면 만들어 두는 헬퍼
    //     Folder.create()는 이미 있으면 그냥 true를 돌려준다.
    function ensureParentFolder(outPath) {
        var outFile = new File(outPath);
        var parent = outFile.parent;          // Folder 객체
        if (parent && !parent.exists) {
            parent.create();                  // 중간 경로까지 생성 시도
        }
    }

    // (5) 메인 try/catch — 어떤 예외가 나도 result JSON은 반드시 작성한다.
    try {
        // (5-1) 입력 JSON 존재 검증
        var inputFile = new File(inputJsonPath);
        if (!inputFile.exists) {
            writeResult({
                success: false,
                error: "ai_to_svg_input.json 파일이 없습니다: " + inputJsonPath
            });
            return;
        }

        // (5-2) 입력 JSON 읽기 + 파싱
        //       ExtendScript는 CC 2014+에서 JSON.parse/stringify 기본 지원.
        inputFile.encoding = "UTF-8";
        inputFile.open("r");
        var jsonStr = inputFile.read();
        inputFile.close();

        var input;
        try {
            input = JSON.parse(jsonStr);
        } catch (parseErr) {
            writeResult({
                success: false,
                error: "ai_to_svg_input.json 파싱 실패: " + (parseErr && parseErr.message ? parseErr.message : String(parseErr))
            });
            return;
        }

        // (5-3) 두 스키마를 공통 jobs 배열로 정규화
        //       방식 1: input.jobs 가 이미 있음 → 그대로 사용
        //       방식 2: input_dir + sizes + name_pattern → jobs로 전개
        var jobs = [];

        if (input && input.jobs && input.jobs.length) {
            // [방식 1] 그대로 복사 (얕은 복사로 충분 — 객체 필드만 사용)
            for (var i = 0; i < input.jobs.length; i++) {
                jobs.push(input.jobs[i]);
            }
        } else if (input && input.input_dir && input.sizes && input.sizes.length) {
            // [방식 2] 폴더 + 사이즈 + 파일명 패턴으로 전개
            var inDir = trimTrailingSlash(input.input_dir);
            // output_dir 생략 시 input_dir과 동일 폴더에 떨군다.
            var outDir = trimTrailingSlash(input.output_dir ? input.output_dir : input.input_dir);
            // 패턴 생략 시 기본값 "{size}.ai"
            var pattern = input.name_pattern ? String(input.name_pattern) : "{size}.ai";

            for (var s = 0; s < input.sizes.length; s++) {
                var sizeName = String(input.sizes[s]);
                // {size} 자리표시자를 사이즈명으로 치환 (전역 치환)
                var fileName = pattern.replace(/\{size\}/g, sizeName);
                jobs.push({
                    input_path: inDir + "/" + fileName,
                    output_path: outDir + "/" + sizeName + ".svg"  // 출력은 사이즈명.svg
                });
            }
        } else {
            // 두 방식 어느 것도 충족 못 함 → 안내
            writeResult({
                success: false,
                error: "input.json 형식 오류: 'jobs' 배열 또는 ('input_dir'+'sizes')가 필요합니다"
            });
            return;
        }

        // (5-4) SVGExportOptions 설정 — 목표 형식(U넥 SVG)에 최대한 근접
        //       (옵션 객체는 모든 job에서 재사용)
        var svgOpts = new SVGExportOptions();

        // CSS를 <style>+class(.st0)로 빼서 목표 형식과 동일하게 한다.
        //   ENTITIES = <defs><style> 블록 + class 참조 방식.
        svgOpts.cssProperties = SVGCSSPropertyLocation.ENTITIES;

        // 좌표 소수 자릿수 (목표 SVG는 소수 2자리 수준) → points 정밀도 유지하며 용량 절감.
        svgOpts.coordinatePrecision = 2;

        // 글자는 윤곽선(아웃라인)으로 — 폰트 의존성 없이 어디서나 동일하게 보이게.
        svgOpts.fontType = SVGFontType.OUTLINEFONT;

        // 래스터 이미지 임베드 안 함 — 패턴은 벡터만 필요하므로 용량 절감.
        svgOpts.embedRasterImages = false;

        // 책갈피/슬라이스/문서 분할 비활성 — 단순 단일 SVG 출력.
        try { svgOpts.documentEncoding = SVGDocumentEncoding.UTF8; } catch (encErr) {}

        // (5-5) jobs 순회 변환
        var results = [];
        var okCount = 0;
        var failCount = 0;

        for (var j = 0; j < jobs.length; j++) {
            var job = jobs[j];
            var inPath = job ? job.input_path : null;
            var outPath = job ? job.output_path : null;

            // 필드 검증
            if (!inPath || !outPath) {
                failCount++;
                results.push({
                    success: false,
                    input_path: inPath || null,
                    error: "input_path 또는 output_path 누락"
                });
                continue;
            }

            // 입력 AI 존재 검증
            var aiFile = new File(inPath);
            if (!aiFile.exists) {
                failCount++;
                results.push({
                    success: false,
                    input_path: inPath,
                    error: "입력 AI 파일 없음: " + inPath
                });
                continue;
            }

            // 한 job씩 try/catch — 한 파일이 실패해도 나머지는 계속 변환.
            var doc = null;
            try {
                // 출력 폴더 보장
                ensureParentFolder(outPath);

                // 열기 (실패 시 null 또는 예외)
                doc = app.open(aiFile);
                if (!doc) {
                    failCount++;
                    results.push({
                        success: false,
                        input_path: inPath,
                        error: "app.open 실패: " + inPath
                    });
                    continue;
                }

                // SVG로 내보내기 (saveAs 대신 exportFile + ExportType.SVG)
                var outFile = new File(outPath);
                doc.exportFile(outFile, ExportType.SVG, svgOpts);

                // 저장 직후 크기 측정 (캐시 회피용으로 객체 새로 생성)
                var outFresh = new File(outPath);
                var outSize = outFresh.exists ? outFresh.length : 0;

                okCount++;
                results.push({
                    success: true,
                    input_path: inPath,
                    output_path: outPath,
                    output_size: outSize
                });

            } catch (jobErr) {
                failCount++;
                var jMsg = (jobErr && jobErr.message) ? jobErr.message : String(jobErr);
                var jLine = (jobErr && jobErr.line) ? " (line " + jobErr.line + ")" : "";
                results.push({
                    success: false,
                    input_path: inPath,
                    error: "변환 중 오류: " + jMsg + jLine
                });
            } finally {
                // 문서 닫기 — 저장 안 함(exportFile로 이미 별도 파일 작성 완료).
                //   닫지 않으면 다음 job에서 Illustrator가 문서로 가득 차 느려진다.
                if (doc) {
                    try {
                        doc.close(SaveOptions.DONOTSAVECHANGES);
                    } catch (closeErr) {
                        // 무시 — close 실패는 결과에 영향 없음
                    }
                }
            }
        }

        // (5-6) 전체 결과 작성 — 1개라도 성공이면 success:true (세부는 summary로 판단)
        writeResult({
            success: (okCount > 0),
            summary: { total: jobs.length, ok: okCount, fail: failCount },
            jobs: results
        });

    } catch (e) {
        // (6) 최상위 예외 처리 — 어떤 단계에서 터졌든 result JSON 반드시 작성
        var errMsg = (e && e.message) ? e.message : String(e);
        var errLine = (e && e.line) ? " (line " + e.line + ")" : "";
        writeResult({
            success: false,
            error: "JSX 실행 중 오류: " + errMsg + errLine
        });
    }

})();

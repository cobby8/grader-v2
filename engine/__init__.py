# -*- coding: utf-8 -*-
"""grader-v2 engine — 웹과 완전 분리된 순수 Python 출력 엔진.

설계서(DESIGN.md) 7번 파이프라인의 코어. 웹 없이 커맨드라인으로 항상 테스트 가능.

모듈 구성
  pdfutil  : PDF 콘텐츠 스트림 저수준 헬퍼 (숫자 표기, 클립/배치 연산자)
  pattern  : 패턴 파일(SVG, 추후 DXF) → 조각별 윤곽 점 목록
  compose  : 디자인 + 사이즈별 조각 레이아웃 → 단일 임베드 합성 CMYK PDF (코어)
  verify   : 출력물 검증 (CMYK 보존 / 단일 임베드 / 벡터 유지 / 투명도 / 색공간)
  preview  : PyMuPDF로 검수용 PNG 렌더
  fixtures : selftest용 합성 CMYK 샘플 + PoC 기하 (외부 파일 없이 PoC 재현)

핵심 원칙
  - 디자인은 Form XObject로 '단 1회만' 임베드하고, 모든 배치는 참조(Do)만 반복 → 경량.
  - device CMYK(k/K 연산자)만 사용 → ICC/RGB 변환 없이 색값 무손실 통과.
  - 무손실 deflate 압축만 사용 → 색/이미지 무변형.
"""

from .compose import Piece, SizeLayout, compose
from .pattern import parse_svg, Polyline

__all__ = ["Piece", "SizeLayout", "compose", "parse_svg", "Polyline"]

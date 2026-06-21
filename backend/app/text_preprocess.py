"""
헤드라인 텍스트 전처리

문제: 스마트 인용부호·말줄임표·장식 기호가 ELECTRA 토크나이저에서 독립 토큰이 되어
     어텐션 가중치가 해당 기호에 쏠리는 현상 (Evidence Token이 따옴표만 나오는 등).

해결: 추론 직전, 그리고 크롤링 시 헤드라인을 정제.
     - 감정적으로 유의미한 ?!,. 는 보존
     - 인용부호·말줄임·장식 기호는 제거
"""

import re

# 인용부호 — ASCII + 스마트/유니코드 모두 제거
# \x22=" \x27=' \x60=`  +  unicode smart quotes/brackets
_SMART_QUOTE = re.compile(
    "[\x22\x27\x60"           # ASCII: " ' `
    "“”"             # “=” (smart double quotes)
    "‘’"             # ‘’ (smart single quotes)
    "「」『』" # 「」『』
    "‹›«»" # ‹›«»
    "″′〝〞]" # ″′〝〞
)
# 말줄임표 (2개 이상 연속 마침표 또는 유니코드 말줄임 U+2026 …)
_ELLIPSIS = re.compile(r"\.{2,}|…+")
# 단어 구분 역할 기호 → 스페이스 (·U+00B7, •U+2022)
_WORD_SEP = re.compile("[·•]")
# 순수 장식 기호 → 제거
_DECORATIVE = re.compile(
    "[◆◇▶◀▷◁▲▽▼"  # ◆◇▶◀▷◁▲▽▼
    "★☆♦♣♠♥"                       # ★☆♦♣♠♥
    "►▻◉○●※]"                      # ►▻◉○●※
)
# 연속 공백
_SPACES = re.compile(r"\s+")


def preprocess_headline(text: str) -> str:
    """
    추론 전 헤드라인 정제.
    원본 DB 값은 보존하고 이 함수는 토크나이저에 넘기기 직전에 호출한다.
    """
    text = _SMART_QUOTE.sub("", text)
    text = _ELLIPSIS.sub("", text)
    text = _WORD_SEP.sub(" ", text)    # · → 스페이스 (단어 경계 유지)
    text = _DECORATIVE.sub("", text)
    text = _SPACES.sub(" ", text)
    return text.strip()

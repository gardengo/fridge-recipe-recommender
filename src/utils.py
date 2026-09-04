"""공통 유틸리티 모듈.

``scoring`` / ``recommender`` / ``app`` 어디에서나 필요한 함수를 모아 둔다.
Streamlit에 의존하지 않으므로 CLI나 테스트에서도 그대로 사용할 수 있다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: 연속된 공백(전각 공백 포함)을 찾기 위한 패턴.
_WHITESPACE_PATTERN = re.compile(r"[\s　]+")

#: 정렬 시 값이 없는 레시피가 앞으로 오지 않도록 쓰는 기본값.
UNKNOWN_COOKING_TIME = 10**6
UNKNOWN_DIFFICULTY = 5


def normalize_ingredient(name: str) -> str:
    """재료명을 비교 가능한 형태로 정규화한다.

    사용자가 ``" 계란 "``, ``"대 파"``처럼 입력해도 레시피 데이터와 매칭되도록
    모든 공백을 제거하고, 영문은 소문자로 통일한다.

    >>> normalize_ingredient(" 대 파 ")
    '대파'
    """
    return _WHITESPACE_PATTERN.sub("", str(name)).lower()


def normalize_ingredients(names: Iterable[str]) -> list[str]:
    """재료명 목록을 정규화한다. 빈 값과 중복은 제거하고 입력 순서는 유지한다."""
    normalized: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = normalize_ingredient(name)
        if key and key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _as_int(value: object, default: int) -> int:
    """정수로 해석할 수 없는 값이면 ``default``를 돌려준다."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default


def get_cooking_time(recipe: dict) -> int:
    """레시피의 조리시간(분). 값이 없거나 형식이 잘못되면 매우 큰 값으로 본다."""
    return _as_int(recipe.get("cooking_time"), UNKNOWN_COOKING_TIME)


def get_difficulty(recipe: dict) -> int:
    """레시피의 난이도(1~5). 값이 없거나 형식이 잘못되면 가장 어려운 값으로 본다."""
    return _as_int(recipe.get("difficulty"), UNKNOWN_DIFFICULTY)


def get_recipe_name(recipe: dict) -> str:
    """정렬·표시에 사용할 레시피 이름."""
    return str(recipe.get("name") or recipe.get("id") or "")

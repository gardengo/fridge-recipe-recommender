"""공통 유틸리티 모듈.

``scoring`` / ``recommender`` / ``app`` 어디에서나 필요한 함수를 모아 둔다.
Streamlit에 의존하지 않으므로 CLI나 테스트에서도 그대로 사용할 수 있다.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

#: 연속된 공백(전각 공백 포함)을 찾기 위한 패턴.
_WHITESPACE_PATTERN = re.compile(r"[\s　]+")

#: 정렬 시 값이 없는 레시피가 앞으로 오지 않도록 쓰는 기본값.
UNKNOWN_COOKING_TIME = 10**6
UNKNOWN_DIFFICULTY = 5

#: 이 파일 위치를 기준으로 계산하므로 어느 디렉터리에서 실행해도 같은 곳을 가리킨다.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RECIPES_PATH = DATA_DIR / "recipes.json"
INGREDIENTS_PATH = DATA_DIR / "ingredients.json"


class DataFileError(RuntimeError):
    """데이터 파일이 없거나 내용이 잘못되었을 때 발생한다."""


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


def split_user_input(raw: str) -> list[str]:
    """쉼표나 줄바꿈으로 구분된 자유 입력을 재료 목록으로 나눈다.

    >>> split_user_input("미나리, 순대 , ")
    ['미나리', '순대']
    """
    return [chunk.strip() for chunk in re.split(r"[,\n]+", raw or "") if chunk.strip()]


def merge_ingredient_inputs(selected: Iterable[str], extra_text: str) -> list[str]:
    """목록에서 고른 재료와 직접 입력한 재료를 중복 없이 합친다.

    비교는 정규화된 이름으로 하되, 돌려주는 값은 화면에 보여줄 원래 표기를 유지한다.
    """
    merged: list[str] = []
    seen: set[str] = set()
    for name in [*selected, *split_user_input(extra_text)]:
        key = normalize_ingredient(name)
        if key and key not in seen:
            seen.add(key)
            merged.append(str(name).strip())
    return merged


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


def _load_json(path: Path) -> Any:
    """JSON 파일을 읽는다. 실패하면 원인을 설명하는 :class:`DataFileError` 로 바꿔 던진다."""
    if not path.is_file():
        raise DataFileError(
            f"데이터 파일을 찾을 수 없습니다: {path}\n"
            f"프로젝트의 data 디렉터리에 '{path.name}' 파일이 있는지 확인하세요."
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DataFileError(
            f"'{path.name}' 파일이 UTF-8로 저장되어 있지 않습니다. UTF-8로 다시 저장해 주세요."
        ) from exc
    except OSError as exc:
        raise DataFileError(f"'{path.name}' 파일을 읽는 중 오류가 발생했습니다: {exc}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataFileError(
            f"'{path.name}' 파일의 JSON 형식이 올바르지 않습니다. "
            f"{exc.lineno}번째 줄 {exc.colno}번째 칸 부근을 확인하세요. (원인: {exc.msg})"
        ) from exc


def load_recipes(path: Path | None = None) -> list[dict[str, Any]]:
    """레시피 목록을 읽어온다.

    Raises:
        DataFileError: 파일이 없거나, JSON이 깨졌거나, 최상위 구조가 배열이 아닐 때.
    """
    target = path or RECIPES_PATH
    data = _load_json(target)
    if not isinstance(data, list):
        raise DataFileError(f"'{target.name}' 의 최상위 구조는 레시피 객체의 배열이어야 합니다.")
    for index, recipe in enumerate(data):
        if not isinstance(recipe, dict):
            raise DataFileError(f"'{target.name}' 의 {index}번째 항목이 객체(object)가 아닙니다.")
    return data


def load_ingredients(path: Path | None = None) -> list[str]:
    """선택 가능한 재료 목록을 읽어온다.

    Raises:
        DataFileError: 파일이 없거나, JSON이 깨졌거나, 문자열 배열이 아닐 때.
    """
    target = path or INGREDIENTS_PATH
    data = _load_json(target)
    if not isinstance(data, list) or any(not isinstance(name, str) for name in data):
        raise DataFileError(f"'{target.name}' 의 최상위 구조는 재료 이름 문자열의 배열이어야 합니다.")
    return data

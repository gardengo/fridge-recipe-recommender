"""추천 점수 계산 모듈.

사용자가 가진 재료와 레시피의 재료를 비교해 0~100점 사이의 점수를 만든다.

점수 구성
    * 필수 재료 충족 비율 : 최대 60점
    * 선택 재료 충족 비율 : 최대 20점
    * 전체 재료 일치 비율 : 최대 20점
    * 부족한 필수 재료 1개당 15점 감점

계산은 전부 :func:`evaluate_recipe` 한 곳에서 이루어지고, 개별 지표 함수는
그 결과에서 필요한 값만 꺼내 쓴다. 같은 로직이 여러 곳에 흩어지지 않게 하기 위함이다.
"""

from __future__ import annotations

from typing import Any, TypedDict

from src.utils import normalize_ingredient, normalize_ingredients

#: 점수 배분 가중치.
REQUIRED_WEIGHT = 60.0
OPTIONAL_WEIGHT = 20.0
TOTAL_WEIGHT = 20.0

#: 부족한 필수 재료 1개당 감점.
MISSING_REQUIRED_PENALTY = 15.0

MIN_SCORE = 0.0
MAX_SCORE = 100.0


class RecipeEvaluation(TypedDict):
    """한 레시피에 대한 평가 결과."""

    score: float
    required_match_rate: float
    optional_match_rate: float
    total_match_rate: float
    missing_required: list[str]
    missing_optional: list[str]
    matched_ingredients: list[str]


def split_recipe_ingredients(recipe: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """레시피 재료를 (필수, 선택) 두 개의 ``{정규화명: 표시명}`` 매핑으로 나눈다.

    - 재료가 문자열로만 들어온 경우에는 필수 재료로 간주한다.
    - 같은 재료가 필수와 선택에 모두 있으면 필수로 취급한다.
    - 표시명은 원본 그대로 두어 화면에 자연스럽게 보이도록 한다.
    """
    required: dict[str, str] = {}
    optional: dict[str, str] = {}

    for item in recipe.get("ingredients") or []:
        if isinstance(item, dict):
            display = str(item.get("name", ""))
            is_required = bool(item.get("required", False))
        else:
            display, is_required = str(item), True

        key = normalize_ingredient(display)
        if not key:
            continue
        bucket = required if is_required else optional
        bucket.setdefault(key, display.strip())

    for key in required:
        optional.pop(key, None)
    return required, optional


def _match_rate(matched_count: int, total_count: int) -> float:
    """충족률(0.0~1.0). 비교 대상이 없으면 부족한 것도 없으므로 1.0으로 본다."""
    if total_count <= 0:
        return 1.0
    return matched_count / total_count


def evaluate_recipe(user_ingredients: list[str], recipe: dict[str, Any]) -> RecipeEvaluation:
    """레시피 하나를 평가해 점수와 세부 지표를 한 번에 계산한다."""
    owned = set(normalize_ingredients(user_ingredients))
    required, optional = split_recipe_ingredients(recipe)

    missing_required = [display for key, display in required.items() if key not in owned]
    missing_optional = [display for key, display in optional.items() if key not in owned]
    matched_ingredients = [
        display
        for key, display in (required | optional).items()
        if key in owned
    ]

    required_rate = _match_rate(len(required) - len(missing_required), len(required))
    optional_rate = _match_rate(len(optional) - len(missing_optional), len(optional))
    total_count = len(required) + len(optional)
    total_rate = _match_rate(len(matched_ingredients), total_count)

    score = (
        REQUIRED_WEIGHT * required_rate
        + OPTIONAL_WEIGHT * optional_rate
        + TOTAL_WEIGHT * total_rate
        - MISSING_REQUIRED_PENALTY * len(missing_required)
    )
    score = round(min(max(score, MIN_SCORE), MAX_SCORE), 2)

    return RecipeEvaluation(
        score=score,
        required_match_rate=required_rate,
        optional_match_rate=optional_rate,
        total_match_rate=total_rate,
        missing_required=missing_required,
        missing_optional=missing_optional,
        matched_ingredients=matched_ingredients,
    )


def calculate_recipe_score(user_ingredients: list[str], recipe: dict[str, Any]) -> float:
    """레시피 추천 점수(0~100)를 계산한다."""
    return evaluate_recipe(user_ingredients, recipe)["score"]


def calculate_required_match_rate(user_ingredients: list[str], recipe: dict[str, Any]) -> float:
    """필수 재료 충족률(0.0~1.0)."""
    return evaluate_recipe(user_ingredients, recipe)["required_match_rate"]


def calculate_optional_match_rate(user_ingredients: list[str], recipe: dict[str, Any]) -> float:
    """선택 재료 충족률(0.0~1.0)."""
    return evaluate_recipe(user_ingredients, recipe)["optional_match_rate"]


def calculate_total_match_rate(user_ingredients: list[str], recipe: dict[str, Any]) -> float:
    """전체 재료 일치율(0.0~1.0)."""
    return evaluate_recipe(user_ingredients, recipe)["total_match_rate"]


def find_missing_required(user_ingredients: list[str], recipe: dict[str, Any]) -> list[str]:
    """부족한 필수 재료 목록."""
    return evaluate_recipe(user_ingredients, recipe)["missing_required"]


def find_missing_optional(user_ingredients: list[str], recipe: dict[str, Any]) -> list[str]:
    """부족한 선택 재료 목록."""
    return evaluate_recipe(user_ingredients, recipe)["missing_optional"]

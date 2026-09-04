"""추천 엔진.

레시피 목록을 평가해 점수가 높은 순으로 정렬하고 상위 N개를 돌려준다.
점수 계산 자체는 :mod:`src.scoring` 이 담당하고, 이 모듈은 정렬·필터·개수 제한만 맡는다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.scoring import evaluate_recipe
from src.utils import get_cooking_time, get_difficulty, get_recipe_name

#: 추천 결과 한 건의 타입 별칭. ``recipe`` 와 평가 지표가 함께 들어 있다.
Recommendation = dict[str, Any]

#: 카테고리 필터에서 "제한하지 않음"을 뜻하는 값.
CATEGORY_ALL = "전체"

#: 화면에 노출할 카테고리 순서. 여기에 없는 카테고리는 뒤에 이름순으로 붙는다.
CATEGORY_ORDER: tuple[str, ...] = ("밥", "면", "국/찌개", "반찬", "간식")


def available_categories(recipes: list[dict[str, Any]]) -> list[str]:
    """데이터에 실제로 존재하는 카테고리를 정해진 순서로 돌려준다(맨 앞은 "전체")."""
    available = {str(recipe.get("category") or "") for recipe in recipes or []}
    ordered = [name for name in CATEGORY_ORDER if name in available]
    extras = sorted(available - set(CATEGORY_ORDER) - {""})
    return [CATEGORY_ALL, *ordered, *extras]


def filter_recipes(
    recipes: list[dict[str, Any]],
    max_cooking_time: int | None = None,
    max_difficulty: int | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """조리시간·난이도·카테고리 조건에 맞는 레시피만 남긴다.

    각 조건은 ``None`` (카테고리는 ``None`` 또는 ``"전체"``)이면 제한하지 않는다.
    """

    def matches(recipe: dict[str, Any]) -> bool:
        if max_cooking_time is not None and get_cooking_time(recipe) > max_cooking_time:
            return False
        if max_difficulty is not None and get_difficulty(recipe) > max_difficulty:
            return False
        if category not in (None, CATEGORY_ALL) and recipe.get("category") != category:
            return False
        return True

    return [recipe for recipe in recipes or [] if matches(recipe)]


def build_recommendation(user_ingredients: list[str], recipe: dict[str, Any]) -> Recommendation:
    """레시피 하나를 평가해 추천 결과 한 건으로 만든다."""
    return {"recipe": recipe, **evaluate_recipe(user_ingredients, recipe)}


#: 지원하는 추천 기준.
SORT_MODE_INGREDIENT_MATCH = "ingredient_match"
SORT_MODE_COOKING_TIME = "cooking_time"
SORT_MODE_MISSING_INGREDIENTS = "missing_ingredients"


def _by_ingredient_match(item: Recommendation) -> tuple[Any, ...]:
    """재료 일치율(점수) 우선. 동점이면 부족한 필수 재료 → 조리시간 → 난이도 순."""
    recipe = item["recipe"]
    return (
        -item["score"],
        len(item["missing_required"]),
        get_cooking_time(recipe),
        get_difficulty(recipe),
    )


def _by_cooking_time(item: Recommendation) -> tuple[Any, ...]:
    """조리시간이 짧은 것 우선. 같은 시간이면 점수가 높은 순."""
    recipe = item["recipe"]
    return (
        get_cooking_time(recipe),
        -item["score"],
        len(item["missing_required"]),
        get_difficulty(recipe),
    )


def _by_missing_ingredients(item: Recommendation) -> tuple[Any, ...]:
    """부족한 재료가 적은 것 우선. 같으면 점수 → 조리시간 → 난이도 순."""
    recipe = item["recipe"]
    return (
        len(item["missing_required"]),
        len(item["missing_optional"]),
        -item["score"],
        get_cooking_time(recipe),
        get_difficulty(recipe),
    )


#: 추천 기준 이름 → 정렬 키 함수.
SORT_MODES = {
    SORT_MODE_INGREDIENT_MATCH: _by_ingredient_match,
    SORT_MODE_COOKING_TIME: _by_cooking_time,
    SORT_MODE_MISSING_INGREDIENTS: _by_missing_ingredients,
}


def resolve_sort_mode(sort_mode: str) -> Callable[[Recommendation], tuple[Any, ...]]:
    """추천 기준 이름에 해당하는 정렬 키 함수를 찾는다.

    Raises:
        ValueError: 지원하지 않는 이름일 때.
    """
    try:
        return SORT_MODES[sort_mode]
    except (KeyError, TypeError):
        supported = ", ".join(SORT_MODES)
        raise ValueError(
            f"지원하지 않는 sort_mode 입니다: {sort_mode!r} (사용 가능한 값: {supported})"
        ) from None


def _sort_key(
    item: Recommendation,
    key_builder: Callable[[Recommendation], tuple[Any, ...]],
    prefer_complete: bool,
) -> tuple[Any, ...]:
    """추천 기준별 정렬 키를 만든다.

    ``prefer_complete`` 가 참이면 필수 재료를 모두 갖춘 레시피를 어떤 기준에서든 앞으로 보낸다.
    마지막 이름 비교는 결과 순서를 항상 동일하게 유지하기 위한 것이다.
    """
    complete_first = (0 if not item["missing_required"] else 1) if prefer_complete else 0
    return (complete_first, *key_builder(item), get_recipe_name(item["recipe"]))


def recommend_recipes(
    user_ingredients: list[str],
    recipes: list[dict[str, Any]],
    top_n: int | None = 5,
    minimum_score: float = 0.0,
    prefer_complete: bool = True,
    sort_mode: str = SORT_MODE_INGREDIENT_MATCH,
    max_cooking_time: int | None = None,
    max_difficulty: int | None = None,
    category: str | None = None,
) -> list[Recommendation]:
    """보유 재료로 만들 수 있는 레시피를 점수순으로 추천한다.

    Args:
        user_ingredients: 사용자가 가진 재료 이름 목록.
        recipes: 후보 레시피 목록.
        top_n: 최대 결과 개수. ``None`` 이면 제한하지 않는다.
        minimum_score: 이 점수 미만인 레시피는 결과에서 제외한다.
        prefer_complete: 참이면 필수 재료를 모두 갖춘 레시피를 항상 앞에 배치한다.
        sort_mode: 추천 기준. ``"ingredient_match"``, ``"cooking_time"``,
            ``"missing_ingredients"`` 중 하나.
        max_cooking_time: 이 시간(분)을 넘는 레시피를 제외한다.
        max_difficulty: 이 난이도를 넘는 레시피를 제외한다.
        category: 이 카테고리만 남긴다. ``None`` 또는 ``"전체"`` 면 제한하지 않는다.

    Returns:
        선택한 기준으로 정렬된 추천 결과 목록. 각 항목은 ``recipe``, ``score``,
        ``required_match_rate``, ``total_match_rate``, ``missing_required``,
        ``missing_optional`` 등을 담고 있다.

    Raises:
        ValueError: ``sort_mode`` 가 지원하지 않는 값일 때.
    """
    key_builder = resolve_sort_mode(sort_mode)
    candidates = filter_recipes(
        recipes,
        max_cooking_time=max_cooking_time,
        max_difficulty=max_difficulty,
        category=category,
    )
    evaluated = [build_recommendation(user_ingredients, recipe) for recipe in candidates]
    ranked = [item for item in evaluated if item["score"] >= minimum_score]
    ranked.sort(key=lambda item: _sort_key(item, key_builder, prefer_complete))

    if top_n is not None:
        ranked = ranked[: max(top_n, 0)]
    return ranked

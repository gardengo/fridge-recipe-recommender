"""추천 엔진.

레시피 목록을 평가해 점수가 높은 순으로 정렬하고 상위 N개를 돌려준다.
점수 계산 자체는 :mod:`src.scoring` 이 담당하고, 이 모듈은 정렬·필터·개수 제한만 맡는다.
"""

from __future__ import annotations

from typing import Any

from src.scoring import evaluate_recipe
from src.utils import get_cooking_time, get_difficulty, get_recipe_name

#: 추천 결과 한 건의 타입 별칭. ``recipe`` 와 평가 지표가 함께 들어 있다.
Recommendation = dict[str, Any]


def build_recommendation(user_ingredients: list[str], recipe: dict[str, Any]) -> Recommendation:
    """레시피 하나를 평가해 추천 결과 한 건으로 만든다."""
    return {"recipe": recipe, **evaluate_recipe(user_ingredients, recipe)}


def _sort_key(item: Recommendation, prefer_complete: bool) -> tuple[Any, ...]:
    """점수 내림차순 정렬 키.

    점수가 같으면 (1) 부족한 필수 재료가 적은 순 → (2) 조리시간이 짧은 순 →
    (3) 난이도가 낮은 순으로 정렬한다. 마지막 이름 비교는 결과 순서를 항상
    동일하게 유지하기 위한 것이다.

    ``prefer_complete`` 가 참이면 필수 재료를 모두 갖춘 레시피를 앞으로 보낸다.
    """
    recipe = item["recipe"]
    complete_first = (0 if not item["missing_required"] else 1) if prefer_complete else 0
    return (
        complete_first,
        -item["score"],
        len(item["missing_required"]),
        get_cooking_time(recipe),
        get_difficulty(recipe),
        get_recipe_name(recipe),
    )


def recommend_recipes(
    user_ingredients: list[str],
    recipes: list[dict[str, Any]],
    top_n: int | None = 5,
    minimum_score: float = 0.0,
    prefer_complete: bool = True,
) -> list[Recommendation]:
    """보유 재료로 만들 수 있는 레시피를 점수순으로 추천한다.

    Args:
        user_ingredients: 사용자가 가진 재료 이름 목록.
        recipes: 후보 레시피 목록.
        top_n: 최대 결과 개수. ``None`` 이면 제한하지 않는다.
        minimum_score: 이 점수 미만인 레시피는 결과에서 제외한다.
        prefer_complete: 참이면 필수 재료를 모두 갖춘 레시피를 항상 앞에 배치한다.

    Returns:
        점수가 높은 순으로 정렬된 추천 결과 목록. 각 항목은 ``recipe``, ``score``,
        ``required_match_rate``, ``total_match_rate``, ``missing_required``,
        ``missing_optional`` 등을 담고 있다.
    """
    evaluated = [build_recommendation(user_ingredients, recipe) for recipe in recipes or []]
    ranked = [item for item in evaluated if item["score"] >= minimum_score]
    ranked.sort(key=lambda item: _sort_key(item, prefer_complete))

    if top_n is not None:
        ranked = ranked[: max(top_n, 0)]
    return ranked

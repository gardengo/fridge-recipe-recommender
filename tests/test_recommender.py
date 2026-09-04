"""``src.recommender`` 추천 엔진 테스트."""

from __future__ import annotations

import pytest

from src.recommender import (
    SORT_MODE_COOKING_TIME,
    SORT_MODE_INGREDIENT_MATCH,
    SORT_MODE_MISSING_INGREDIENTS,
    available_categories,
    filter_recipes,
    recommend_recipes,
)
from src.utils import load_recipes


@pytest.fixture(scope="module")
def real_recipes() -> list[dict]:
    """실제 서비스 데이터(data/recipes.json)."""
    return load_recipes()


def names_of(results: list[dict]) -> list[str]:
    """추천 결과에서 레시피 이름만 뽑는다."""
    return [item["recipe"]["name"] for item in results]


def test_추천_결과는_점수가_높은_순서다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(
        user_ingredients, sample_recipes, top_n=None, prefer_complete=False
    )

    scores = [item["score"] for item in results]
    assert scores == sorted(scores, reverse=True)
    assert names_of(results)[0] == "김치볶음밥"


def test_필수_재료를_모두_갖춘_레시피가_먼저_나온다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(user_ingredients, sample_recipes, top_n=None)

    complete_flags = [not item["missing_required"] for item in results]
    assert complete_flags == sorted(complete_flags, reverse=True)


def test_추천_결과에_필요한_정보가_모두_들어_있다(sample_recipes, user_ingredients) -> None:
    item = recommend_recipes(user_ingredients, sample_recipes, top_n=1)[0]

    assert set(item) >= {
        "recipe",
        "score",
        "required_match_rate",
        "total_match_rate",
        "missing_required",
        "missing_optional",
    }


@pytest.mark.parametrize(
    ("top_n", "expected_count"),
    [(1, 1), (2, 2), (10, 4), (0, 0), (None, 4)],
)
def test_top_n이_결과_개수를_제한한다(
    sample_recipes, user_ingredients, top_n, expected_count
) -> None:
    results = recommend_recipes(user_ingredients, sample_recipes, top_n=top_n)

    assert len(results) == expected_count


def test_minimum_score_미만은_제외된다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(
        user_ingredients, sample_recipes, top_n=None, minimum_score=70.0
    )

    assert names_of(results) == ["김치볶음밥", "계란국"]
    assert all(item["score"] >= 70.0 for item in results)


def test_조리시간_필터가_동작한다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(
        user_ingredients, sample_recipes, top_n=None, max_cooking_time=10
    )

    assert all(item["recipe"]["cooking_time"] <= 10 for item in results)
    assert sorted(names_of(results)) == ["계란국", "라면"]


def test_난이도_필터가_동작한다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(
        user_ingredients, sample_recipes, top_n=None, max_difficulty=1
    )

    assert all(item["recipe"]["difficulty"] <= 1 for item in results)
    assert sorted(names_of(results)) == ["김치볶음밥", "라면"]


def test_카테고리_필터가_동작한다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(user_ingredients, sample_recipes, top_n=None, category="면")

    assert names_of(results) == ["라면"]


def test_카테고리_전체는_필터링하지_않는다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(user_ingredients, sample_recipes, top_n=None, category="전체")

    assert len(results) == len(sample_recipes)


def test_필터를_모두_적용하면_결과가_비어_있을_수_있다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(
        user_ingredients, sample_recipes, top_n=None, category="면", max_cooking_time=1
    )

    assert results == []


def test_filter_recipes는_원본_목록을_바꾸지_않는다(sample_recipes) -> None:
    before = len(sample_recipes)

    filter_recipes(sample_recipes, max_cooking_time=10)

    assert len(sample_recipes) == before


def test_available_categories는_전체를_맨_앞에_둔다(sample_recipes) -> None:
    assert available_categories(sample_recipes) == ["전체", "밥", "면", "국/찌개", "반찬"]


def test_ingredient_match_정렬은_점수가_높은_순이다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(
        user_ingredients, sample_recipes, top_n=None, sort_mode=SORT_MODE_INGREDIENT_MATCH
    )

    assert names_of(results) == ["김치볶음밥", "계란국", "라면", "제육볶음"]


def test_cooking_time_정렬은_조리시간이_짧은_순이다(sample_recipes, user_ingredients) -> None:
    results = recommend_recipes(
        user_ingredients,
        sample_recipes,
        top_n=None,
        sort_mode=SORT_MODE_COOKING_TIME,
        prefer_complete=False,
    )

    times = [item["recipe"]["cooking_time"] for item in results]
    assert times == sorted(times)
    assert names_of(results) == ["라면", "계란국", "김치볶음밥", "제육볶음"]


def test_cooking_time_정렬도_만들_수_있는_레시피를_먼저_보여준다(
    sample_recipes, user_ingredients
) -> None:
    results = recommend_recipes(
        user_ingredients, sample_recipes, top_n=None, sort_mode=SORT_MODE_COOKING_TIME
    )

    assert names_of(results)[:2] == ["계란국", "김치볶음밥"]


def test_missing_ingredients_정렬은_부족한_재료가_적은_순이다(
    sample_recipes, user_ingredients
) -> None:
    results = recommend_recipes(
        user_ingredients,
        sample_recipes,
        top_n=None,
        sort_mode=SORT_MODE_MISSING_INGREDIENTS,
    )

    missing_counts = [
        len(item["missing_required"]) + len(item["missing_optional"]) for item in results
    ]
    assert missing_counts == sorted(missing_counts)
    assert names_of(results) == ["김치볶음밥", "계란국", "라면", "제육볶음"]


@pytest.mark.parametrize("bad_mode", ["score", "", None, 123, "INGREDIENT_MATCH"])
def test_잘못된_sort_mode는_ValueError를_발생시킨다(
    sample_recipes, user_ingredients, bad_mode
) -> None:
    with pytest.raises(ValueError, match="sort_mode"):
        recommend_recipes(user_ingredients, sample_recipes, sort_mode=bad_mode)


def test_사용자_재료가_없어도_예외없이_동작한다(sample_recipes) -> None:
    results = recommend_recipes([], sample_recipes, top_n=3)

    assert len(results) == 3
    assert all(item["score"] >= 0 for item in results)


def test_레시피_목록이_비어_있으면_빈_결과를_돌려준다(user_ingredients) -> None:
    assert recommend_recipes(user_ingredients, []) == []


# --------------------------------------------------------------------------
# 실제 데이터(data/recipes.json)를 사용하는 통합 시나리오
# --------------------------------------------------------------------------


def test_시나리오A_김치_밥_계란이면_김치볶음밥_계열이_상위에_온다(real_recipes) -> None:
    top_names = names_of(recommend_recipes(["김치", "밥", "계란"], real_recipes, top_n=3))

    assert any("김치볶음밥" in name for name in top_names), top_names


def test_시나리오B_계란_밥_간장이면_간장계란밥_계열이_상위에_온다(real_recipes) -> None:
    top_names = names_of(recommend_recipes(["계란", "밥", "간장"], real_recipes, top_n=3))

    assert any("계란밥" in name for name in top_names), top_names


def test_시나리오C_두부_김치면_두부김치가_상위에_온다(real_recipes) -> None:
    top_names = names_of(recommend_recipes(["두부", "김치"], real_recipes, top_n=3))

    assert "두부김치" in top_names, top_names


def test_시나리오D_재료가_없어도_오류가_나지_않는다(real_recipes) -> None:
    results = recommend_recipes([], real_recipes, top_n=5)

    assert len(results) == 5
    assert all(0 <= item["score"] <= 100 for item in results)


def test_시나리오E_조리시간_10분_제한이_지켜진다(real_recipes) -> None:
    results = recommend_recipes(
        ["김치", "밥", "계란"], real_recipes, top_n=None, max_cooking_time=10
    )

    assert results, "10분 이내 레시피가 하나도 없으면 필터 테스트가 무의미하다"
    assert all(item["recipe"]["cooking_time"] <= 10 for item in results)


def test_실제_데이터로도_모든_추천_기준이_동작한다(real_recipes) -> None:
    for mode in (SORT_MODE_INGREDIENT_MATCH, SORT_MODE_COOKING_TIME, SORT_MODE_MISSING_INGREDIENTS):
        results = recommend_recipes(["김치", "밥", "계란"], real_recipes, top_n=5, sort_mode=mode)

        assert len(results) == 5, mode
        assert all(0 <= item["score"] <= 100 for item in results), mode

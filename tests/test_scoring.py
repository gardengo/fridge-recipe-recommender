"""``src.scoring`` 점수 계산 테스트."""

from __future__ import annotations

import pytest

from src.scoring import (
    MAX_SCORE,
    MIN_SCORE,
    calculate_optional_match_rate,
    calculate_recipe_score,
    calculate_required_match_rate,
    calculate_total_match_rate,
    evaluate_recipe,
    find_missing_optional,
    find_missing_required,
    split_recipe_ingredients,
)
from tests.conftest import make_recipe


def test_모든_필수_재료가_있으면_필수_충족률이_1이다(simple_recipe) -> None:
    result = evaluate_recipe(["밥", "김치"], simple_recipe)

    assert result["required_match_rate"] == 1.0
    assert result["missing_required"] == []
    assert result["missing_optional"] == ["계란"]
    assert result["score"] == pytest.approx(73.33, abs=0.01)


def test_일부_필수_재료가_없으면_충족률이_낮아지고_감점된다(simple_recipe) -> None:
    result = evaluate_recipe(["밥"], simple_recipe)

    assert result["required_match_rate"] == pytest.approx(0.5)
    assert result["missing_required"] == ["김치"]
    # 60*0.5 + 20*0 + 20*(1/3) - 15 = 21.67
    assert result["score"] == pytest.approx(21.67, abs=0.01)
    assert result["score"] < calculate_recipe_score(["밥", "김치"], simple_recipe)


def test_모든_재료가_있으면_만점이다(simple_recipe) -> None:
    result = evaluate_recipe(["밥", "김치", "계란"], simple_recipe)

    assert result["score"] == MAX_SCORE
    assert result["required_match_rate"] == 1.0
    assert result["optional_match_rate"] == 1.0
    assert result["total_match_rate"] == 1.0
    assert result["missing_required"] == []
    assert result["missing_optional"] == []


def test_사용자_재료가_없으면_0점이고_모든_재료가_부족하다(simple_recipe) -> None:
    result = evaluate_recipe([], simple_recipe)

    assert result["score"] == MIN_SCORE
    assert result["required_match_rate"] == 0.0
    assert result["missing_required"] == ["밥", "김치"]
    assert result["missing_optional"] == ["계란"]


def test_레시피_재료가_비어_있어도_예외없이_계산된다() -> None:
    empty_recipe = make_recipe("empty", "빈 레시피", [])

    result = evaluate_recipe(["밥"], empty_recipe)

    assert result["missing_required"] == []
    assert result["missing_optional"] == []
    assert MIN_SCORE <= result["score"] <= MAX_SCORE


def test_ingredients_키가_아예_없어도_예외없이_계산된다() -> None:
    assert calculate_recipe_score(["밥"], {"name": "필드 없음"}) <= MAX_SCORE


@pytest.mark.parametrize(
    "user_input",
    [
        ["밥", "김치", "계란"],
        [" 밥 ", "김 치", "  계란"],
        ["밥", "밥", "김치", "계란"],
        ["BAP", "밥", "김치", "계란"],
    ],
)
def test_공백과_중복이_있어도_동일하게_매칭된다(simple_recipe, user_input) -> None:
    assert calculate_recipe_score(user_input, simple_recipe) == MAX_SCORE


def test_점수는_항상_0에서_100_사이다(sample_recipes) -> None:
    inputs = [[], ["밥"], ["밥", "김치"], ["밥", "김치", "계란"], ["없는재료"] * 10]

    for recipe in sample_recipes:
        for user_input in inputs:
            assert MIN_SCORE <= calculate_recipe_score(user_input, recipe) <= MAX_SCORE


def test_문자열로만_적힌_재료는_필수로_취급한다() -> None:
    recipe = {"name": "문자열 재료", "ingredients": ["밥", "김치"]}

    required, optional = split_recipe_ingredients(recipe)

    assert list(required) == ["밥", "김치"]
    assert optional == {}
    assert find_missing_required(["밥"], recipe) == ["김치"]


def test_같은_재료가_필수와_선택에_모두_있으면_필수로_본다() -> None:
    recipe = make_recipe("dup", "중복 재료", ["계란"], ["계란", "대파"])

    required, optional = split_recipe_ingredients(recipe)

    assert list(required) == ["계란"]
    assert list(optional) == ["대파"]


def test_개별_지표_함수는_evaluate_recipe와_같은_값을_돌려준다(simple_recipe) -> None:
    user_input = ["밥", "계란"]
    result = evaluate_recipe(user_input, simple_recipe)

    assert calculate_recipe_score(user_input, simple_recipe) == result["score"]
    assert calculate_required_match_rate(user_input, simple_recipe) == result["required_match_rate"]
    assert calculate_optional_match_rate(user_input, simple_recipe) == result["optional_match_rate"]
    assert calculate_total_match_rate(user_input, simple_recipe) == result["total_match_rate"]
    assert find_missing_required(user_input, simple_recipe) == result["missing_required"]
    assert find_missing_optional(user_input, simple_recipe) == result["missing_optional"]

"""테스트 공용 헬퍼와 픽스처.

실제 ``data/recipes.json`` 대신 작고 예측 가능한 레시피 집합을 쓰면
데이터가 바뀌어도 테스트가 깨지지 않는다.
"""

from __future__ import annotations

from typing import Any

import pytest


def make_recipe(
    recipe_id: str,
    name: str,
    required: list[str],
    optional: list[str] | None = None,
    *,
    category: str = "밥",
    difficulty: int = 1,
    cooking_time: int = 10,
) -> dict[str, Any]:
    """테스트용 레시피 한 건을 만든다."""
    ingredients = [{"name": item, "required": True} for item in required]
    ingredients += [{"name": item, "required": False} for item in optional or []]
    return {
        "id": recipe_id,
        "name": name,
        "category": category,
        "ingredients": ingredients,
        "seasonings": ["간장"],
        "difficulty": difficulty,
        "cooking_time": cooking_time,
        "description": f"{name} 설명",
        "steps": [f"{name}를 만든다."],
    }


@pytest.fixture
def simple_recipe() -> dict[str, Any]:
    """필수 재료 2개(밥, 김치)와 선택 재료 1개(계란)를 가진 레시피."""
    return make_recipe("r0", "김치볶음밥", ["밥", "김치"], ["계란"])


@pytest.fixture
def sample_recipes() -> list[dict[str, Any]]:
    """카테고리·난이도·조리시간이 서로 다른 4개의 레시피."""
    return [
        make_recipe("r1", "김치볶음밥", ["밥", "김치"], ["계란"],
                    category="밥", difficulty=1, cooking_time=15),
        make_recipe("r2", "계란국", ["계란"], ["대파"],
                    category="국/찌개", difficulty=2, cooking_time=10),
        make_recipe("r3", "제육볶음", ["돼지고기", "양파"], ["대파"],
                    category="반찬", difficulty=3, cooking_time=25),
        make_recipe("r4", "라면", ["라면"], ["계란", "대파"],
                    category="면", difficulty=1, cooking_time=5),
    ]


@pytest.fixture
def user_ingredients() -> list[str]:
    """``sample_recipes`` 와 함께 쓰는 기준 보유 재료."""
    return ["밥", "김치", "계란"]

"""``src.ai_chef`` 테스트.

실제 OpenAI를 호출하지 않는다. 네트워크에 의존하는 테스트는 느리고 불안정하며
비용도 들기 때문에, 호출 경계는 가짜 클라이언트로 대체하고 정제·검증 로직만 검사한다.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src import ai_chef
from src.ai_chef import AIChefError, build_recipe, clean_ingredient_name, clean_title

VALID_PAYLOAD: dict[str, Any] = {
    "name": "김치두부덮밥",
    "category": "밥",
    "description": "남은 김치와 두부로 만드는 덮밥.",
    "ingredients": [
        {"name": "김치", "required": True},
        {"name": "두부", "required": True},
        {"name": "계란", "required": False},
    ],
    "seasonings": ["간장", "참기름"],
    "difficulty": 2,
    "cooking_time": 15,
    "steps": ["김치를 볶는다.", "두부를 넣는다.", "밥 위에 올린다."],
    "tip": "두부 물기를 빼면 좋습니다.",
}


class FakeResponses:
    """``client.responses`` 를 대신한다."""

    def __init__(self, output_text: str, error: Exception | None = None) -> None:
        self.output_text = output_text
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return type("Response", (), {"output_text": self.output_text})()


class FakeClient:
    def __init__(self, output_text: str = "", error: Exception | None = None) -> None:
        self.responses = FakeResponses(output_text, error)


@pytest.fixture
def with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """실제 .env를 읽지 않고 키가 설정된 상태를 만든다."""
    monkeypatch.setattr(ai_chef, "load_env_file", lambda _path=None: False)
    monkeypatch.setenv(ai_chef.API_KEY_ENV, "test-key")
    monkeypatch.delenv(ai_chef.MODEL_ENV, raising=False)


@pytest.fixture
def without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_chef, "load_env_file", lambda _path=None: False)
    monkeypatch.delenv(ai_chef.API_KEY_ENV, raising=False)


# --------------------------------------------------------------------------
# 설정
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("without_api_key")
def test_키가_없으면_비활성화된다() -> None:
    assert ai_chef.is_enabled() is False


@pytest.mark.usefixtures("with_api_key")
def test_키가_있으면_활성화된다() -> None:
    assert ai_chef.is_enabled() is True


@pytest.mark.usefixtures("with_api_key")
def test_모델은_환경변수로_바꿀_수_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ai_chef.get_model() == ai_chef.DEFAULT_MODEL

    monkeypatch.setenv(ai_chef.MODEL_ENV, "gpt-4o-mini")
    assert ai_chef.get_model() == "gpt-4o-mini"


# --------------------------------------------------------------------------
# 응답 정제
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('김치 (잘 익은 것) - 1컵(썰어둠)"', "김치"),
        ("두부 1/2모", "두부"),
        ("밥 2공기", "밥"),
        ("대파 1대(송송 썰기)", "대파"),
        ("돼지고기 200g", "돼지고기"),
        ("  양파  ", "양파"),
        ("계란", "계란"),
        ("방울토마토", "방울토마토"),
    ],
)
def test_재료명에서_수량과_설명을_떼어낸다(raw: str, expected: str) -> None:
    assert clean_ingredient_name(raw) == expected


def test_요리_이름에서는_숫자를_지우지_않는다() -> None:
    # "3분 카레"처럼 숫자가 이름의 일부인 경우를 망가뜨리면 안 된다.
    assert clean_title("3분 카레") == "3분 카레"
    assert clean_title('"김치볶음밥" (매운맛)') == "김치볶음밥"


def test_정상_응답은_데이터와_같은_스키마로_변환된다() -> None:
    recipe = build_recipe(VALID_PAYLOAD)

    assert set(recipe) >= {
        "id", "name", "category", "ingredients", "seasonings",
        "difficulty", "cooking_time", "description", "steps",
    }
    assert recipe["source"] == "ai"
    assert [item["name"] for item in recipe["ingredients"]] == ["김치", "두부", "계란"]


def test_생성된_레시피는_기존_추천_엔진에_그대로_넣을_수_있다() -> None:
    from src.recommender import recommend_recipes

    recipe = build_recipe(VALID_PAYLOAD)
    results = recommend_recipes(["김치", "두부", "계란"], [recipe])

    assert results[0]["score"] == 100.0
    assert results[0]["missing_required"] == []


def test_난이도와_조리시간은_범위_안으로_보정된다() -> None:
    recipe = build_recipe({**VALID_PAYLOAD, "difficulty": 99, "cooking_time": -5})

    assert recipe["difficulty"] == ai_chef.MAX_DIFFICULTY
    assert recipe["cooking_time"] >= 1


def test_알_수_없는_카테고리는_기본값으로_바뀐다() -> None:
    recipe = build_recipe({**VALID_PAYLOAD, "category": "디저트"})

    assert recipe["category"] in ai_chef.CATEGORIES


def test_중복_재료와_빈_재료는_제거된다() -> None:
    recipe = build_recipe({
        **VALID_PAYLOAD,
        "ingredients": [
            {"name": "김치", "required": True},
            {"name": " 김 치 ", "required": False},
            {"name": "   ", "required": True},
            {"name": "두부 1모", "required": False},
        ],
    })

    assert [item["name"] for item in recipe["ingredients"]] == ["김치", "두부"]


def test_필수_재료가_하나도_없으면_첫_재료를_필수로_올린다() -> None:
    recipe = build_recipe({
        **VALID_PAYLOAD,
        "ingredients": [{"name": "김치", "required": False}, {"name": "두부", "required": False}],
    })

    assert recipe["ingredients"][0]["required"] is True


@pytest.mark.parametrize(
    "broken",
    [
        {"name": ""},
        {"steps": []},
        {"ingredients": []},
    ],
)
def test_필수_정보가_비면_AIChefError를_던진다(broken: dict[str, Any]) -> None:
    with pytest.raises(AIChefError):
        build_recipe({**VALID_PAYLOAD, **broken})


# --------------------------------------------------------------------------
# 호출 흐름 (가짜 클라이언트)
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("without_api_key")
def test_키가_없으면_호출하지_않고_에러를_던진다() -> None:
    with pytest.raises(AIChefError, match=ai_chef.API_KEY_ENV):
        ai_chef.generate_recipe(["김치"])


@pytest.mark.usefixtures("with_api_key")
def test_재료가_없으면_호출하지_않는다() -> None:
    with pytest.raises(AIChefError, match="재료"):
        ai_chef.generate_recipe([])


@pytest.mark.usefixtures("with_api_key")
def test_생성_성공_시_레시피를_돌려준다(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(json.dumps(VALID_PAYLOAD, ensure_ascii=False))
    monkeypatch.setattr(ai_chef, "_create_client", lambda _api_key: client)

    recipe = ai_chef.generate_recipe(["김치", "두부"], exclude_names=["김치찌개"])

    assert recipe["name"] == "김치두부덮밥"
    call = client.responses.calls[0]
    assert call["model"] == ai_chef.DEFAULT_MODEL
    assert call["text"]["format"]["strict"] is True
    # 보유 재료와 제외 목록이 프롬프트에 실제로 들어갔는지 확인한다.
    user_message = call["input"][1]["content"]
    assert "김치" in user_message
    assert "김치찌개" in user_message


@pytest.mark.usefixtures("with_api_key")
def test_JSON이_아닌_응답은_친절한_에러가_된다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken_client = FakeClient("이건 JSON이 아니다")
    monkeypatch.setattr(ai_chef, "_create_client", lambda _api_key: broken_client)

    with pytest.raises(AIChefError, match="이해하지 못했"):
        ai_chef.generate_recipe(["김치"])


@pytest.mark.parametrize(
    ("error_name", "expected"),
    [
        ("AuthenticationError", "API 키"),
        ("RateLimitError", "잠시 후"),
        ("APITimeoutError", "지연"),
        ("SomeUnknownError", "실패"),
    ],
)
@pytest.mark.usefixtures("with_api_key")
def test_API_예외는_사용자용_메시지로_바뀐다(
    monkeypatch: pytest.MonkeyPatch, error_name: str, expected: str
) -> None:
    error = type(error_name, (Exception,), {})("boom")
    monkeypatch.setattr(ai_chef, "_create_client", lambda _api_key: FakeClient(error=error))

    with pytest.raises(AIChefError, match=expected):
        ai_chef.generate_recipe(["김치"])


@pytest.mark.usefixtures("with_api_key")
def test_openai_패키지가_없으면_설치_안내를_한다(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "openai":
            raise ImportError("no module named openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(AIChefError, match="openai"):
        ai_chef.generate_recipe(["김치"])

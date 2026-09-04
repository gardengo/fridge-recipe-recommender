"""냉장고 털기 레시피 추천기 - Streamlit 진입점.

이 파일은 화면 구성과 사용자 입력 처리만 담당한다.
점수 계산과 추천 로직은 ``src`` 패키지에 있으므로, UI를 바꿔도 알고리즘은 그대로 재사용된다.
"""

from __future__ import annotations

import os
from typing import Any

import streamlit as st
from streamlit.errors import StreamlitAPIException

from src import ai_chef
from src.ai_chef import AIChefError
from src.recommender import (
    SORT_MODE_COOKING_TIME,
    SORT_MODE_INGREDIENT_MATCH,
    SORT_MODE_MISSING_INGREDIENTS,
    available_categories,
    build_recommendation,
    recommend_recipes,
)
from src.utils import (
    DataFileError,
    difficulty_stars,
    get_cooking_time,
    get_difficulty,
    get_match_message,
    load_ingredients,
    load_recipes,
    merge_ingredient_inputs,
)

PAGE_TITLE = "냉장고 털기"
PAGE_ICON = "🍳"
SUBTITLE = "집에 있는 재료로 오늘 뭐 먹을지 찾아보세요."
SEARCH_BUTTON_LABEL = f"{PAGE_ICON} 뭐 먹지?"

#: 화면에 보여줄 추천 개수.
TOP_N = 5

#: 겹치는 재료가 하나도 없는(0점) 레시피까지 보여주면 결과가 오히려 방해가 되므로 걸러낸다.
MINIMUM_SCORE = 1.0

#: 사이드바에 노출할 조리시간 선택지. ``None`` 은 "제한하지 않음"을 뜻한다.
COOKING_TIME_OPTIONS: dict[str, int | None] = {
    "10분": 10,
    "20분": 20,
    "30분": 30,
    "60분": 60,
    "제한 없음": None,
}

#: 사이드바 라디오 버튼 라벨 → 추천 엔진의 sort_mode 값.
SORT_MODE_OPTIONS: dict[str, str] = {
    "재료 일치율 우선": SORT_MODE_INGREDIENT_MATCH,
    "조리시간 우선": SORT_MODE_COOKING_TIME,
    "부족한 재료 최소화": SORT_MODE_MISSING_INGREDIENTS,
}

#: 버튼을 한 번이라도 눌렀는지 기억해, 입력을 바꿔도 결과가 유지되도록 한다.
SEARCHED_KEY = "searched"

#: AI 응답을 캐시해 둘 시간(초). 같은 재료 조합으로는 이 시간 안에 다시 호출하지 않는다.
AI_CACHE_TTL = 3600

EMPTY_INPUT_MESSAGE = "재료를 하나 이상 선택하거나 입력해 주세요."
EMPTY_RESULT_MESSAGE = "조건에 맞는 음식이 없습니다. 조리시간이나 난이도 조건을 조금 넓혀보세요."


@st.cache_data(show_spinner=False)
def load_app_data() -> tuple[list[dict[str, Any]], list[str]]:
    """레시피와 재료 목록을 읽어 캐시한다."""
    return load_recipes(), load_ingredients()


def bridge_secrets_to_env() -> None:
    """Streamlit Secrets에 있는 값을 환경변수로 옮긴다.

    ``src`` 패키지가 streamlit에 의존하지 않도록, 키를 읽는 창구는 환경변수 하나로 통일한다.
    로컬에서는 ``.env``, Streamlit Cloud에서는 Secrets가 같은 환경변수를 채우는 셈이다.
    이미 환경변수가 있으면 덮어쓰지 않는다.
    """
    for name in (ai_chef.API_KEY_ENV, ai_chef.MODEL_ENV):
        if os.environ.get(name):
            continue
        try:
            value = st.secrets[name]
        except (KeyError, FileNotFoundError, StreamlitAPIException):
            continue
        os.environ[name] = str(value)


def render_header() -> None:
    """상단 제목과 안내 문구."""
    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    st.caption(SUBTITLE)


def render_ingredient_form(options: list[str]) -> list[str]:
    """보유 재료 입력 UI를 그리고, 선택·입력된 재료를 합쳐서 돌려준다."""
    st.subheader("보유 재료")
    selected = st.multiselect(
        "냉장고에 있는 재료를 골라주세요",
        options=options,
        placeholder="재료를 검색하거나 선택하세요",
    )
    extra_text = st.text_input(
        "추가 재료",
        placeholder="목록에 없는 재료는 쉼표로 구분해 입력하세요 (예: 미나리, 순대)",
        help="직접 입력한 재료도 추천에 함께 반영됩니다.",
    )

    user_ingredients = merge_ingredient_inputs(selected, extra_text)
    st.caption(f"🥕 현재 선택한 재료: {len(user_ingredients)}개")
    return user_ingredients


def render_sidebar_filters(categories: list[str]) -> dict[str, Any]:
    """사이드바 필터를 그리고, 추천 엔진에 그대로 넘길 수 있는 형태로 돌려준다."""
    with st.sidebar:
        st.header("🔎 필터")
        time_label = st.selectbox(
            "최대 조리시간",
            options=list(COOKING_TIME_OPTIONS),
            index=len(COOKING_TIME_OPTIONS) - 1,
        )
        max_difficulty = st.slider("최대 난이도", min_value=1, max_value=5, value=5)
        category = st.selectbox("카테고리", options=categories)

        st.divider()
        sort_label = st.radio("추천 기준", options=list(SORT_MODE_OPTIONS))

    return {
        "max_cooking_time": COOKING_TIME_OPTIONS[time_label],
        "max_difficulty": max_difficulty,
        "category": category,
        "sort_mode": SORT_MODE_OPTIONS[sort_label],
    }


def render_ai_toggle() -> bool:
    """AI 셰프 사용 여부를 사이드바에서 고르게 한다.

    API 키가 없으면 토글 대신 안내만 보여주고 항상 꺼진 상태로 둔다.
    """
    with st.sidebar:
        st.divider()
        if not ai_chef.is_enabled():
            st.caption(
                "🤖 AI 셰프는 꺼져 있습니다. "
                f"`{ai_chef.API_KEY_ENV}` 를 설정하면 새 레시피 제안 기능이 켜집니다."
            )
            return False
        return st.toggle(
            "🤖 AI 셰프 제안 받기",
            value=True,
            help="보유 재료로 만들 수 있는 새 레시피를 AI가 만들어 제안합니다.",
        )


def render_missing_ingredients(item: dict[str, Any]) -> None:
    """부족한 재료를 상황에 맞는 색으로 안내한다."""
    if item["missing_required"]:
        st.warning("부족한 필수 재료 · " + ", ".join(item["missing_required"]))
    elif item["missing_optional"]:
        st.info(
            "필수 재료는 모두 있어요. 없어도 되는 재료 · "
            + ", ".join(item["missing_optional"])
        )
    else:
        st.success("필요한 재료를 모두 갖췄습니다.")


def render_steps(recipe: dict[str, Any]) -> None:
    """조리법을 접이식 영역에 보여준다."""
    with st.expander("📖 레시피 보기"):
        for number, step in enumerate(recipe.get("steps") or [], start=1):
            st.write(f"{number}. {step}")
        seasonings = recipe.get("seasonings")
        if seasonings:
            st.caption("양념 · " + ", ".join(seasonings))


def render_recipe_metrics(item: dict[str, Any]) -> None:
    """1위 카드에서 추천 점수·조리시간·난이도를 크게 보여준다."""
    recipe = item["recipe"]
    score_column, time_column, difficulty_column = st.columns(3)
    score_column.metric("추천 점수", f"{item['score']:.0f}점")
    time_column.metric("조리시간", f"{get_cooking_time(recipe)}분")
    difficulty_column.metric("난이도", difficulty_stars(get_difficulty(recipe)))


def format_recipe_summary(item: dict[str, Any]) -> str:
    """2위 이하 카드에서 같은 정보를 한 줄로 압축한다."""
    recipe = item["recipe"]
    return (
        f"추천 점수 **{item['score']:.0f}점**"
        f"  ·  조리시간 {get_cooking_time(recipe)}분"
        f"  ·  난이도 {difficulty_stars(get_difficulty(recipe))}"
    )


def render_recipe_card(item: dict[str, Any], *, heading: str, highlight: bool = False) -> None:
    """추천 결과 한 건을 카드 형태로 그린다.

    강조 카드는 지표를 크게 펼쳐 보여주고, 나머지는 한 줄 요약으로 압축해
    결과 목록이 숫자로 빽빽해지지 않도록 한다.
    """
    recipe = item["recipe"]
    match_rate = item["total_match_rate"]

    with st.container(border=True):
        if highlight:
            st.markdown(f"## {heading}")
            st.caption(recipe.get("description", ""))
            render_recipe_metrics(item)
        else:
            st.markdown(f"#### {heading}")
            st.markdown(format_recipe_summary(item))
            st.caption(recipe.get("description", ""))

        st.progress(match_rate, text=f"재료 일치율 {match_rate:.0%}")
        st.write(get_match_message(match_rate))
        render_missing_ingredients(item)
        if recipe.get("tip"):
            st.caption(f"💡 {recipe['tip']}")
        render_steps(recipe)


@st.cache_data(show_spinner=False, ttl=AI_CACHE_TTL)
def generate_ai_recipe(
    ingredients: tuple[str, ...],
    exclude_names: tuple[str, ...],
) -> tuple[dict[str, Any] | None, str | None]:
    """AI 레시피를 생성한다. ``(레시피, 오류 메시지)`` 중 한쪽만 채워진다.

    예외를 던지지 않고 값으로 실패를 돌려주는 이유는, ``st.cache_data`` 가 예외는
    캐시하지 않아 필터를 조작할 때마다 실패한 호출이 반복되기 때문이다.
    같은 재료 조합에 대해서는 API를 한 번만 호출한다.
    """
    try:
        recipe = ai_chef.generate_recipe(list(ingredients), exclude_names=list(exclude_names))
    except AIChefError as exc:
        return None, str(exc)
    return recipe, None


def render_ai_section(user_ingredients: list[str], exclude_names: list[str]) -> None:
    """규칙 기반 추천 아래에 AI가 생성한 레시피를 덧붙인다."""
    st.write("")
    st.subheader("🤖 AI 셰프의 제안")

    with st.spinner("AI 셰프가 레시피를 궁리하는 중..."):
        recipe, error = generate_ai_recipe(tuple(user_ingredients), tuple(exclude_names))

    if recipe is None:
        st.warning(f"AI 제안을 가져오지 못했어요. {error}")
        return

    st.caption(
        "보유 재료를 바탕으로 방금 만들어낸 레시피입니다. "
        "실제 조리 시 간과 불 세기는 조절해 주세요."
    )
    render_recipe_card(
        build_recommendation(user_ingredients, recipe),
        heading=recipe["name"],
        highlight=True,
    )


def render_results(
    user_ingredients: list[str],
    recipes: list[dict[str, Any]],
    options: dict[str, Any],
    *,
    use_ai: bool = False,
) -> None:
    """추천을 실행하고 결과를 화면에 그린다."""
    results = recommend_recipes(
        user_ingredients, recipes, top_n=TOP_N, minimum_score=MINIMUM_SCORE, **options
    )
    if not results:
        st.info(EMPTY_RESULT_MESSAGE)
        return

    st.subheader("🏆 오늘의 추천")
    render_recipe_card(results[0], heading=results[0]["recipe"]["name"], highlight=True)

    if len(results) > 1:
        st.write("")
        st.subheader("이런 것도 만들 수 있어요")
        for rank, item in enumerate(results[1:], start=2):
            render_recipe_card(item, heading=f"{rank}. {item['recipe']['name']}")
            st.write("")

    if use_ai:
        render_ai_section(user_ingredients, [item["recipe"]["name"] for item in results])


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")
    bridge_secrets_to_env()
    render_header()

    try:
        recipes, ingredient_options = load_app_data()
    except DataFileError as exc:
        st.error(str(exc))
        st.stop()

    options = render_sidebar_filters(available_categories(recipes))
    use_ai = render_ai_toggle()
    input_column, result_column = st.columns([1, 1.6], gap="large")

    with input_column:
        user_ingredients = render_ingredient_form(ingredient_options)
        st.write("")
        if st.button(SEARCH_BUTTON_LABEL, type="primary", width="stretch"):
            st.session_state[SEARCHED_KEY] = True

    with result_column:
        if not st.session_state.get(SEARCHED_KEY):
            st.info("왼쪽에서 재료를 고르고 **뭐 먹지?** 버튼을 눌러보세요.")
            return
        if not user_ingredients:
            st.warning(EMPTY_INPUT_MESSAGE)
            return
        render_results(user_ingredients, recipes, options, use_ai=use_ai)


main()

"""냉장고 털기 레시피 추천기 - Streamlit 진입점.

이 파일은 화면 구성과 사용자 입력 처리만 담당한다.
점수 계산과 추천 로직은 ``src`` 패키지에 있으므로, UI를 바꿔도 알고리즘은 그대로 재사용된다.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.recommender import (
    SORT_MODE_COOKING_TIME,
    SORT_MODE_INGREDIENT_MATCH,
    SORT_MODE_MISSING_INGREDIENTS,
    available_categories,
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


@st.cache_data(show_spinner=False)
def load_app_data() -> tuple[list[dict[str, Any]], list[str]]:
    """레시피와 재료 목록을 읽어 캐시한다."""
    return load_recipes(), load_ingredients()


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
    return merge_ingredient_inputs(selected, extra_text)


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


def render_recipe_card(item: dict[str, Any], rank: int, *, highlight: bool = False) -> None:
    """추천 결과 한 건을 카드 형태로 그린다.

    ``highlight`` 가 참이면 1위 레시피용으로 조금 더 크게 보여준다.
    """
    recipe = item["recipe"]
    match_rate = item["total_match_rate"]

    with st.container(border=True):
        if highlight:
            st.markdown(f"## {recipe['name']}")
        else:
            st.markdown(f"#### {rank}. {recipe['name']}")
        st.caption(recipe.get("description", ""))

        score_column, time_column, difficulty_column = st.columns(3)
        score_column.metric("추천 점수", f"{item['score']:.0f}점")
        time_column.metric("조리시간", f"{get_cooking_time(recipe)}분")
        difficulty_column.metric("난이도", difficulty_stars(get_difficulty(recipe)))

        st.progress(match_rate, text=f"재료 일치율 {match_rate:.0%}")
        st.write(get_match_message(match_rate))
        render_missing_ingredients(item)
        render_steps(recipe)


def render_results(
    user_ingredients: list[str],
    recipes: list[dict[str, Any]],
    options: dict[str, Any],
) -> None:
    """추천을 실행하고 결과를 화면에 그린다."""
    results = recommend_recipes(user_ingredients, recipes, top_n=TOP_N, **options)
    if not results:
        st.info("추천할 수 있는 레시피가 없습니다.")
        return

    st.subheader("🏆 오늘의 추천")
    render_recipe_card(results[0], rank=1, highlight=True)

    if len(results) > 1:
        st.subheader("이런 것도 만들 수 있어요")
        for rank, item in enumerate(results[1:], start=2):
            render_recipe_card(item, rank=rank)


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")
    render_header()

    try:
        recipes, ingredient_options = load_app_data()
    except DataFileError as exc:
        st.error(str(exc))
        st.stop()

    options = render_sidebar_filters(available_categories(recipes))
    input_column, result_column = st.columns([1, 1.6], gap="large")

    with input_column:
        user_ingredients = render_ingredient_form(ingredient_options)
        if st.button(SEARCH_BUTTON_LABEL, type="primary", width="stretch"):
            st.session_state[SEARCHED_KEY] = True

    with result_column:
        if not st.session_state.get(SEARCHED_KEY):
            return
        if not user_ingredients:
            st.warning("재료를 하나 이상 선택하거나 입력해 주세요.")
            return
        render_results(user_ingredients, recipes, options)


main()

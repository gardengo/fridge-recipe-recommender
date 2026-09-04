"""냉장고 털기 레시피 추천기 - Streamlit 진입점.

이 파일은 화면 구성과 사용자 입력 처리만 담당한다.
점수 계산과 추천 로직은 ``src`` 패키지에 있으므로, UI를 바꿔도 알고리즘은 그대로 재사용된다.
"""

from __future__ import annotations

import streamlit as st

from src.utils import (
    DataFileError,
    load_ingredients,
    load_recipes,
    merge_ingredient_inputs,
)

PAGE_TITLE = "냉장고 털기"
PAGE_ICON = "🍳"
SUBTITLE = "집에 있는 재료로 오늘 뭐 먹을지 찾아보세요."
SEARCH_BUTTON_LABEL = f"{PAGE_ICON} 뭐 먹지?"

#: 버튼을 한 번이라도 눌렀는지 기억해, 필터를 바꿔도 결과가 유지되도록 한다.
SEARCHED_KEY = "searched"


@st.cache_data(show_spinner=False)
def load_app_data() -> tuple[list[dict], list[str]]:
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


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")
    render_header()

    try:
        recipes, ingredient_options = load_app_data()
    except DataFileError as exc:
        st.error(str(exc))
        st.stop()

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
        st.info(f"선택한 재료 {len(user_ingredients)}개로 추천을 준비하고 있습니다.")


main()

"""AI 셰프 - OpenAI로 보유 재료에 맞는 새 레시피를 생성한다.

규칙 기반 추천(:mod:`src.recommender`)을 대체하지 않고 보완한다.
데이터에 마땅한 레시피가 없을 때 "지금 있는 재료로 만들 수 있는 다른 요리"를 제안하는 것이 목적이다.

설계 원칙
    * **선택 기능이다.** API 키가 없으면 :func:`is_enabled` 이 거짓을 돌려주고,
      앱의 나머지 기능은 아무 영향 없이 그대로 동작한다.
    * **streamlit에 의존하지 않는다.** 키는 환경변수에서만 읽는다.
      (Streamlit Cloud의 Secrets는 ``app.py`` 가 환경변수로 옮겨 준다.)
    * **모델 출력을 믿지 않는다.** 생성 결과는 :func:`build_recipe` 에서 정제·검증한 뒤에만 쓴다.
    * **openai 패키지가 없어도 import는 성공한다.** 실제 호출 시점에만 필요하다.

생성된 레시피는 ``data/recipes.json`` 과 같은 스키마이므로, 기존 점수 계산과
카드 렌더링을 그대로 재사용할 수 있다.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from src.utils import normalize_ingredient

#: 환경변수 이름.
API_KEY_ENV = "OPENAI_API_KEY"
MODEL_ENV = "OPENAI_MODEL"

#: 기본 모델. 재료명을 군더더기 없이 돌려주고 응답이 빨라 이 용도에 적합하다.
#: OPENAI_MODEL 환경변수로 바꿀 수 있다.
DEFAULT_MODEL = "gpt-4.1-mini"

#: 응답 대기 상한(초)과 최대 출력 토큰.
REQUEST_TIMEOUT = 30.0
MAX_OUTPUT_TOKENS = 1500

#: 생성 결과를 표시할 때 쓰는 고정 id.
GENERATED_RECIPE_ID = "ai_generated"

#: 레시피 카테고리(데이터와 동일하게 유지한다).
CATEGORIES = ("밥", "면", "국/찌개", "반찬", "간식")

MAX_DIFFICULTY = 5
MAX_COOKING_TIME = 240

#: 프로젝트 루트의 .env 경로.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

_env_loaded = False


class AIChefError(RuntimeError):
    """AI 레시피 생성에 실패했을 때 발생한다. 메시지는 사용자에게 그대로 보여줄 수 있다."""


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------


def load_env_file(path: Path | None = None) -> bool:
    """``.env`` 파일이 있으면 환경변수로 읽어들인다.

    이미 설정된 환경변수는 덮어쓰지 않는다. python-dotenv가 없거나 파일이 없으면
    아무 일도 하지 않고 ``False`` 를 돌려준다. 여러 번 불러도 한 번만 읽는다.
    """
    global _env_loaded
    target = path or ENV_FILE
    if _env_loaded and path is None:
        return True
    if not target.is_file():
        return False

    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    load_dotenv(target, override=False)
    if path is None:
        _env_loaded = True
    return True


def get_api_key() -> str:
    """설정된 API 키. 없으면 빈 문자열."""
    load_env_file()
    return (os.environ.get(API_KEY_ENV) or "").strip()


def get_model() -> str:
    """사용할 모델 이름."""
    load_env_file()
    return (os.environ.get(MODEL_ENV) or "").strip() or DEFAULT_MODEL


def is_enabled() -> bool:
    """AI 셰프 기능을 쓸 수 있는 상태인지 확인한다."""
    return bool(get_api_key())


# ---------------------------------------------------------------------------
# 프롬프트와 응답 스키마
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """너는 한국 가정식 전문 요리사다.
사용자가 가진 재료와 집에 흔히 있는 기본 양념만으로 실제로 만들 수 있는 요리 한 가지를 제안한다.

규칙:
- ingredients에는 사용자가 가진 재료를 우선 사용한다. 없어도 되는 재료는 required를 false로 한다.
- ingredients의 name에는 재료 이름만 쓴다. 수량, 단위, 괄호 설명을 절대 넣지 않는다.
  올바른 예: "김치", "두부"   잘못된 예: "김치 1컵", "두부 1/2모(150g)"
- 간장, 소금, 설탕, 식용유, 참기름 같은 기본 양념은 ingredients가 아니라 seasonings에 넣는다.
- difficulty는 1~5 사이 정수, cooking_time은 분 단위 정수다.
- steps는 3~6개의 짧고 명확한 한국어 문장이다.
- description과 tip은 각각 한 문장으로 쓴다.
- 제외 목록에 있는 요리와 겹치지 않는, 새로운 요리를 제안한다."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "요리 이름"},
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "description": {"type": "string", "description": "한 문장 소개"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "재료 이름만. 수량 금지"},
                    "required": {"type": "boolean"},
                },
                "required": ["name", "required"],
                "additionalProperties": False,
            },
        },
        "seasonings": {"type": "array", "items": {"type": "string"}},
        "difficulty": {"type": "integer"},
        "cooking_time": {"type": "integer"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "tip": {"type": "string", "description": "한 문장 요리 팁"},
    },
    "required": [
        "name",
        "category",
        "description",
        "ingredients",
        "seasonings",
        "difficulty",
        "cooking_time",
        "steps",
        "tip",
    ],
    "additionalProperties": False,
}


def build_user_prompt(user_ingredients: list[str], exclude_names: list[str]) -> str:
    """모델에 보낼 사용자 메시지를 만든다."""
    lines = ["보유 재료: " + ", ".join(user_ingredients)]
    if exclude_names:
        lines.append("다음 요리와 겹치지 않게 제안할 것: " + ", ".join(exclude_names))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 응답 정제
# ---------------------------------------------------------------------------

#: 재료명에 딸려 오는 괄호 설명·수량·단위를 떼어내기 위한 패턴.
#: 모델이 "김치 (잘 익은 것) - 1컵" 처럼 보내와도 "김치"만 남기는 것이 목적이다.
_PARENTHESES = re.compile("[(\uff08\\[][^)\uff09\\]]*[)\uff09\\]]")
_QUANTITY_TAIL = re.compile("\\s*[-\u2013\u2014:,]\\s*\\S.*$")
_LEADING_QUANTITY = re.compile(r"^[\d/.~\s]+")
#: 끝에 붙은 "2공기", "1/2모", "200g" 같은 수량 표기. 단위는 짧은 한글/영문 단어로 본다.
_TRAILING_QUANTITY = re.compile(r"\s*\d[\d/.~]*\s*[가-힣A-Za-z]{0,4}$")


def clean_ingredient_name(raw: str) -> str:
    """모델이 붙여 보낸 수량·단위·설명을 떼고 재료 이름만 남긴다.

    >>> clean_ingredient_name('김치 (잘 익은 것) - 1컵(썰어둠)"')
    '김치'
    >>> clean_ingredient_name("두부 1/2모")
    '두부'
    """
    name = str(raw).replace('"', "").replace("'", "")
    name = _PARENTHESES.sub("", name)
    name = _QUANTITY_TAIL.sub("", name)
    name = _LEADING_QUANTITY.sub("", name)
    name = _TRAILING_QUANTITY.sub("", name)
    return name.strip()


def clean_title(raw: str) -> str:
    """요리 이름에서 따옴표와 괄호 설명만 떼어낸다.

    수량 제거는 하지 않는다. "3분 카레"처럼 숫자가 이름의 일부인 경우가 있기 때문이다.
    """
    return _PARENTHESES.sub("", str(raw).replace('"', "").replace("'", "")).strip()


def _clamp_int(value: object, low: int, high: int, default: int) -> int:
    """정수로 해석해 ``low``~``high`` 범위로 자른다."""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return min(max(number, low), high)


def _clean_ingredients(raw_items: object) -> list[dict[str, Any]]:
    """재료 목록을 정제한다. 이름이 비었거나 중복이면 버린다."""
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        name = clean_ingredient_name(item.get("name", ""))
        key = normalize_ingredient(name)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append({"name": name, "required": bool(item.get("required", False))})
    return cleaned


def _clean_text_list(raw_items: object, limit: int) -> list[str]:
    """문자열 목록에서 빈 값을 걸러내고 개수를 제한한다."""
    if not isinstance(raw_items, list):
        return []
    texts = [str(item).strip() for item in raw_items]
    return [text for text in texts if text][:limit]


def build_recipe(payload: dict[str, Any]) -> dict[str, Any]:
    """모델 응답을 데이터 파일과 같은 스키마의 레시피로 정제한다.

    Raises:
        AIChefError: 요리 이름이나 조리법처럼 필수 정보가 비어 있을 때.
    """
    name = clean_title(payload.get("name", ""))
    steps = _clean_text_list(payload.get("steps"), limit=10)
    ingredients = _clean_ingredients(payload.get("ingredients"))

    if not name:
        raise AIChefError("AI가 요리 이름을 만들지 못했습니다.")
    if not steps:
        raise AIChefError("AI가 조리법을 만들지 못했습니다.")
    if not any(item["required"] for item in ingredients):
        # 필수 재료가 하나도 없으면 점수 계산이 의미를 잃으므로 첫 재료를 필수로 올린다.
        if not ingredients:
            raise AIChefError("AI가 재료 목록을 만들지 못했습니다.")
        ingredients[0]["required"] = True

    category = payload.get("category")
    return {
        "id": GENERATED_RECIPE_ID,
        "name": name,
        "category": category if category in CATEGORIES else CATEGORIES[0],
        "ingredients": ingredients,
        "seasonings": _clean_text_list(payload.get("seasonings"), limit=12),
        "difficulty": _clamp_int(payload.get("difficulty"), 1, MAX_DIFFICULTY, 2),
        "cooking_time": _clamp_int(payload.get("cooking_time"), 1, MAX_COOKING_TIME, 20),
        "description": str(payload.get("description") or "").strip(),
        "steps": steps,
        "tip": str(payload.get("tip") or "").strip(),
        "source": "ai",
    }


# ---------------------------------------------------------------------------
# OpenAI 호출
# ---------------------------------------------------------------------------


def _create_client(api_key: str) -> Any:
    """OpenAI 클라이언트를 만든다. 패키지가 없으면 안내 메시지를 담아 예외를 던진다."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AIChefError(
            "openai 패키지가 설치되어 있지 않습니다. "
            "pip install -r requirements.txt 를 실행해 주세요."
        ) from exc
    return OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT)


def _describe_error(exc: Exception) -> str:
    """OpenAI 예외를 사용자에게 보여줄 한 줄 메시지로 바꾼다."""
    name = type(exc).__name__
    if name == "AuthenticationError":
        return "API 키가 올바르지 않습니다. OPENAI_API_KEY를 확인해 주세요."
    if name == "PermissionDeniedError":
        return "이 API 키로는 해당 모델을 사용할 수 없습니다. OPENAI_MODEL을 확인해 주세요."
    if name == "NotFoundError":
        return f"모델을 찾을 수 없습니다: {get_model()}"
    if name == "RateLimitError":
        return "요청이 많아 잠시 후 다시 시도해 주세요."
    if name in {"APITimeoutError", "APIConnectionError"}:
        return "AI 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요."
    return f"AI 호출에 실패했습니다. ({name})"


def generate_recipe(
    user_ingredients: list[str],
    exclude_names: list[str] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """보유 재료로 만들 수 있는 레시피 한 건을 생성한다.

    Args:
        user_ingredients: 사용자가 가진 재료 이름 목록.
        exclude_names: 이미 추천한 요리 이름. 중복 제안을 피하는 데 쓴다.
        model: 사용할 모델. 생략하면 ``OPENAI_MODEL`` 또는 기본값을 쓴다.

    Returns:
        ``data/recipes.json`` 과 같은 스키마의 레시피 dict. ``tip`` 과
        ``source="ai"`` 필드가 추가로 들어 있다.

    Raises:
        AIChefError: 키가 없거나, 호출이 실패했거나, 응답을 쓸 수 없을 때.
    """
    if not user_ingredients:
        raise AIChefError("재료를 하나 이상 알려주셔야 레시피를 만들 수 있습니다.")

    api_key = get_api_key()
    if not api_key:
        raise AIChefError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    user_prompt = build_user_prompt(user_ingredients, exclude_names or [])
    client = _create_client(api_key)
    try:
        response = client.responses.create(
            model=model or get_model(),
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "recipe",
                    "schema": RESPONSE_SCHEMA,
                    "strict": True,
                }
            },
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except AIChefError:
        raise
    except Exception as exc:
        raise AIChefError(_describe_error(exc)) from exc

    try:
        payload = json.loads(response.output_text)
    except (AttributeError, TypeError, json.JSONDecodeError) as exc:
        raise AIChefError("AI 응답을 이해하지 못했습니다. 다시 시도해 주세요.") from exc

    return build_recipe(payload)

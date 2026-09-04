# 🍳 냉장고 털기

**집에 있는 재료로 오늘 뭐 먹을지 찾아주는 레시피 추천 웹 앱입니다.**

장을 보러 가기 전에, 배달앱을 열기 전에. 냉장고에 남은 재료를 골라 넣으면
지금 만들 수 있는 음식을 재료 일치율 순으로 추천해 줍니다.

외부 API나 유료 서비스를 쓰지 않고 **로컬 JSON 데이터 + 규칙 기반 점수 계산**으로만 동작하므로,
클론해서 `streamlit run app.py` 한 줄이면 바로 실행됩니다.

---

## 주요 기능

- **보유 재료 선택** — 45종 재료 목록에서 고르거나, 목록에 없는 재료는 직접 입력
- **재료 기반 레시피 추천** — 한국 가정식 레시피 45종 중 상위 5개 추천
- **재료 일치율 계산** — 0~100점 추천 점수와 진행바로 시각화
- **부족한 재료 안내** — 꼭 필요한 재료와 없어도 되는 재료를 구분해 표시
- **조리시간 필터** — 10 / 20 / 30 / 60분 / 제한 없음
- **난이도 필터** — 1~5 단계
- **카테고리 필터** — 밥 / 면 / 국·찌개 / 반찬 / 간식
- **추천 기준 변경** — 재료 일치율 우선 / 조리시간 우선 / 부족한 재료 최소화

---

## 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| 언어 | Python 3.11+ |
| UI | Streamlit |
| 테스트 | pytest |
| 데이터 | JSON (로컬 파일) |

의존성은 `streamlit`과 `pytest` 둘뿐입니다. 데이터베이스도, API 키도 필요하지 않습니다.

---

## 프로젝트 구조

```
fridge-recipe-recommender/
├── app.py                    # Streamlit 진입점 (화면과 입력 처리만 담당)
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── config.toml           # 테마 및 서버 설정
├── data/
│   ├── recipes.json          # 레시피 45종
│   └── ingredients.json      # 주요 식재료 45종 (기본 양념 제외)
├── src/
│   ├── __init__.py
│   ├── recommender.py        # 추천 엔진 (필터 · 정렬 · 개수 제한)
│   ├── scoring.py            # 추천 점수 계산
│   └── utils.py              # 데이터 로딩, 재료명 정규화, 표시 헬퍼
└── tests/
    ├── __init__.py
    ├── conftest.py           # 테스트 공용 픽스처
    ├── test_recommender.py
    └── test_scoring.py
```

`src` 패키지는 Streamlit을 import하지 않습니다. 그래서 추천 로직을 CLI, 노트북, 다른 웹 프레임워크에
그대로 옮겨 쓸 수 있고, 테스트도 UI 없이 실행됩니다.

---

## 실행 방법

```bash
git clone https://github.com/gardengo/fridge-recipe-recommender.git
cd fridge-recipe-recommender
```

가상환경을 만듭니다.

```bash
python -m venv .venv
```

**Windows**

```bash
.venv\Scripts\activate
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

의존성을 설치하고 앱을 실행합니다.

```bash
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 <http://localhost:8501> 이 열립니다.

### 테스트

```bash
python -m pytest -v
```

---

## 추천 알고리즘 설명

각 레시피의 재료는 **필수(required)** 와 **선택(optional)** 로 나뉩니다.
김치볶음밥이라면 밥과 김치는 필수, 계란은 선택입니다.

### 점수 계산 (`src/scoring.py`)

사용자가 가진 재료와 레시피 재료를 비교해 **0~100점**을 계산합니다.

| 항목 | 배점 | 설명 |
| --- | --- | --- |
| 필수 재료 충족 비율 | 60점 | 없으면 만들 수 없는 재료를 얼마나 갖췄는가 |
| 선택 재료 충족 비율 | 20점 | 있으면 더 맛있는 재료를 얼마나 갖췄는가 |
| 전체 재료 일치 비율 | 20점 | 전체 재료 중 몇 개를 갖췄는가 |
| 부족한 필수 재료 | −15점 / 개 | 필수 재료가 빌 때마다 감점 |

최종 점수는 0~100 범위로 잘라냅니다. 비교 전에 재료명의 공백을 제거하고 영문은 소문자로 통일하므로,
`" 계란 "` 이나 `"대 파"` 처럼 입력해도 정상적으로 매칭됩니다.

> **예시** — 필수 2개(밥·김치) + 선택 1개(계란)인 김치볶음밥
> - 전부 보유 → `60 + 20 + 20 = 100점`
> - 필수만 보유 → `60 + 0 + 13.3 = 73.3점`
> - 밥만 보유 → `30 + 0 + 6.7 − 15 = 21.7점`

### 정렬 (`src/recommender.py`)

점수를 매긴 뒤 **필터 → 정렬 → 상위 N개**의 순서로 결과를 추립니다.

기본적으로 **필수 재료를 모두 갖춘 레시피가 항상 먼저** 나옵니다. 지금 당장 만들 수 있는 음식이
먼저 보이는 편이 유용하기 때문입니다. 그 안에서 선택한 기준으로 정렬합니다.

| `sort_mode` | 정렬 기준 |
| --- | --- |
| `ingredient_match` (기본) | 점수 내림차순 → 부족한 필수 재료 → 조리시간 → 난이도 |
| `cooking_time` | 조리시간 오름차순 → 점수 → 부족한 필수 재료 → 난이도 |
| `missing_ingredients` | 부족한 필수 재료 → 부족한 선택 재료 → 점수 → 조리시간 |

마지막에 이름으로 한 번 더 비교하기 때문에, 같은 입력에는 항상 같은 순서가 나옵니다.

### 직접 호출하기

추천 엔진은 UI와 분리되어 있어 파이썬에서 그대로 쓸 수 있습니다.

```python
from src.recommender import recommend_recipes
from src.utils import load_recipes

results = recommend_recipes(
    ["김치", "밥", "계란"],
    load_recipes(),
    top_n=5,
    sort_mode="ingredient_match",
    max_cooking_time=20,
)

for item in results:
    print(item["recipe"]["name"], item["score"], item["missing_required"])
```

---

## 향후 개선 계획

- **사용자 선호도 저장** — 자주 고르는 재료와 최근 본 레시피 기억
- **레시피 데이터 확대** — 카테고리별 균형과 계절 메뉴 보강
- **임베딩 기반 유사도 추천** — 재료명을 벡터로 바꿔 "비슷한 재료"까지 매칭
  (예: 대파 ↔ 쪽파, 돼지고기 ↔ 소고기)
- **ML 기반 개인화** — 선택 이력을 학습해 개인별 가중치 적용
- **LLM 레시피 생성** — 데이터에 없는 재료 조합에 대해 새 레시피 제안

추천 방식이 늘어나도 `recommend_recipes()` 인터페이스는 그대로 두고 내부 구현만 교체할 수 있도록
점수 계산(`scoring.py`)과 정렬·필터(`recommender.py`)를 분리해 두었습니다.

---

## 라이선스

MIT

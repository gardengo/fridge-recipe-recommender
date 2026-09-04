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
- **🤖 AI 셰프의 제안** *(선택)* — 데이터에 없는 요리를 보유 재료만으로 새로 만들어 제안
  (OpenAI API 키가 있을 때만 켜지고, 없으면 이 기능만 숨겨집니다)

---

## 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| 언어 | Python 3.11+ |
| UI | Streamlit |
| 테스트 | pytest |
| 데이터 | JSON (로컬 파일) |
| AI (선택) | OpenAI Responses API |

**추천 기능 자체는 API 키 없이 완전히 동작합니다.** 데이터베이스도 필요 없습니다.
OpenAI는 "AI 셰프의 제안" 한 기능에만 쓰이고, 키가 없으면 그 섹션만 조용히 사라집니다.

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
├── .env.example              # AI 기능용 환경변수 예시 (.env는 git에 올라가지 않음)
├── src/
│   ├── __init__.py
│   ├── recommender.py        # 추천 엔진 (필터 · 정렬 · 개수 제한)
│   ├── scoring.py            # 추천 점수 계산
│   ├── ai_chef.py            # AI 레시피 생성 (선택 기능)
│   └── utils.py              # 데이터 로딩, 재료명 정규화, 표시 헬퍼
└── tests/
    ├── __init__.py
    ├── conftest.py           # 테스트 공용 픽스처
    ├── test_recommender.py
    ├── test_scoring.py
    └── test_ai_chef.py
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

### AI 셰프 켜기 (선택)

키를 넣지 않아도 앱은 정상 동작합니다. 새 레시피 생성 기능을 쓰고 싶을 때만 설정하세요.

```bash
cp .env.example .env    # Windows: copy .env.example .env
```

`.env` 를 열어 `OPENAI_API_KEY` 에 키를 넣고 앱을 다시 실행하면, 사이드바에
**🤖 AI 셰프 제안 받기** 토글이 나타납니다. `.env` 는 `.gitignore` 에 등록되어 있어
저장소에 올라가지 않습니다.

### 테스트

```bash
python -m pytest -v
```

AI 관련 테스트는 실제 OpenAI를 호출하지 않습니다. 가짜 클라이언트를 주입해
정제·검증 로직만 확인하므로, 키가 없어도 전체 테스트가 통과합니다.

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

### AI 셰프 (`src/ai_chef.py`)

규칙 기반 추천이 끝난 뒤, 보유 재료로 만들 수 있는 **새 레시피 한 건**을 OpenAI로 생성합니다.
데이터에 마땅한 요리가 없을 때 "그래도 이건 만들 수 있어요"를 보여주는 것이 목적입니다.

설계에서 신경 쓴 부분은 네 가지입니다.

1. **선택 기능이다** — 키가 없으면 `is_enabled()` 가 거짓이 되고 섹션 자체가 렌더링되지 않습니다.
   나머지 기능은 영향을 받지 않습니다.
2. **`src`는 여전히 streamlit을 모른다** — 키는 환경변수에서만 읽습니다. 로컬은 `.env`,
   Streamlit Cloud는 Secrets가 같은 환경변수를 채우고, 그 연결은 `app.py` 가 담당합니다.
3. **모델 출력을 믿지 않는다** — 구조화 출력(`json_schema`, strict)으로 받은 뒤에도
   재료명에 섞여 오는 수량·단위·괄호 설명을 코드에서 떼어냅니다
   (`"김치 (잘 익은 것) - 1컵"` → `"김치"`). 난이도·조리시간도 범위 안으로 보정합니다.
   이 과정을 거치지 않으면 재료 매칭이 전부 어긋납니다.
4. **같은 스키마로 돌려준다** — 생성된 레시피는 `data/recipes.json` 과 동일한 형태라서,
   기존 점수 계산과 카드 렌더링을 그대로 재사용합니다. 모델이 없는 재료를 끼워 넣으면
   "부족한 재료"로 정직하게 표시됩니다.

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | 없으면 기능 비활성화 |
| `OPENAI_MODEL` | `gpt-4.1-mini` | 응답이 빠르고 재료명을 깔끔하게 돌려줌 |

같은 재료 조합에 대한 응답은 1시간 동안 캐시하므로, 필터를 조작해도 API를 다시 호출하지 않습니다.

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
- ~~**LLM 레시피 생성**~~ — 구현 완료 (`src/ai_chef.py`)
- **생성 레시피 저장** — 마음에 든 AI 레시피를 `data/recipes.json` 에 편입

추천 방식이 늘어나도 `recommend_recipes()` 인터페이스는 그대로 두고 내부 구현만 교체할 수 있도록
점수 계산(`scoring.py`)과 정렬·필터(`recommender.py`)를 분리해 두었습니다.

---

## 배포 (Streamlit Community Cloud)

무료로 웹에 올릴 수 있습니다. 별도의 서버나 결제 수단이 필요하지 않습니다.

### 1. GitHub repository 생성

GitHub에서 새 public repository를 만듭니다.

### 2. 코드 push

```bash
git init
git add .
git commit -m "Initial commit: fridge recipe recommender"
git branch -M main
git remote add origin <GITHUB_REPOSITORY_URL>
git push -u origin main
```

### 3. Streamlit Community Cloud 접속

<https://share.streamlit.io> 에 GitHub 계정으로 로그인합니다.

### 4. Create app

| 항목 | 값 |
| --- | --- |
| Repository | 방금 push한 저장소 |
| Branch | `main` |
| Main file path | `app.py` |

### 5. Deploy

**Deploy** 를 누르면 `requirements.txt` 를 읽어 자동으로 의존성을 설치하고 앱을 띄웁니다.
1~2분 뒤 아래 형태의 주소가 발급됩니다.

```
https://<YOUR_APP_NAME>.streamlit.app
```

이후 `main` 브랜치에 push할 때마다 배포된 앱이 자동으로 갱신됩니다.

### (선택) AI 셰프를 배포에서도 쓰려면

Streamlit Cloud 앱 화면에서 **Settings → Secrets** 에 아래를 붙여 넣습니다.

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4.1-mini"
```

앱이 시작할 때 Secrets 값을 환경변수로 옮기므로, 로컬(`.env`)과 배포 환경이 같은 코드로 동작합니다.
**설정하지 않아도 앱은 정상 배포되고, AI 섹션만 보이지 않습니다.**

> **참고**
> - `.env` 는 `.gitignore` 에 등록되어 있습니다. API 키를 저장소에 커밋하지 마세요.
> - 데이터 파일(`data/*.json`)은 저장소에 포함되어 있어 별도 업로드가 필요 없습니다.
> - Python 버전은 Advanced settings에서 3.11 이상을 선택하는 것을 권장합니다.

---

## 라이선스

MIT

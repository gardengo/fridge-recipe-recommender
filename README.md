# 냉장고 털기 레시피 추천기

집에 남아 있는 재료를 입력하면, 그 재료로 만들 수 있는 레시피를 추천해 주는
가벼운 Streamlit 웹 앱입니다.

- 유료 API 없이 **로컬 데이터 + 규칙 기반(rule-based)** 으로 동작합니다.
- 추천 엔진은 인터페이스 뒤에 숨겨 두어, 이후 ML / LLM 방식으로 교체·확장할 수 있습니다.

## 상태

초기 구성 단계입니다. 아래 체크리스트가 진행 상황입니다.

- [x] 프로젝트 뼈대 / 의존성 / 배포 설정
- [ ] 레시피 데이터 스키마 및 샘플 데이터
- [ ] 재료명 정규화 (동의어 처리)
- [ ] 규칙 기반 추천 엔진
- [ ] Streamlit UI
- [ ] 테스트

## 프로젝트 구조

```
.
├── app.py                  # Streamlit 진입점 (UI 전용, 로직 없음)
├── requirements.txt        # 배포용 의존성
├── requirements-dev.txt    # 개발/테스트용 의존성
├── .streamlit/
│   └── config.toml         # 테마 및 서버 설정
├── data/                   # 레시피 데이터(JSON)
├── src/                    # 도메인 로직 패키지
│   └── recommender/        # 추천 엔진 (rule-based → ML/LLM 확장 지점)
└── tests/                  # pytest 테스트
```

**설계 원칙**: `app.py`는 입력을 받아 `src`에 넘기고 결과를 그리기만 합니다.
추천 로직은 Streamlit에 의존하지 않으므로 CLI·API·노트북에서도 그대로 재사용할 수 있습니다.

## 로컬 실행

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 http://localhost:8501 로 접속합니다.

## 테스트

```bash
pip install -r requirements-dev.txt
pytest
```

## 배포 (Streamlit Community Cloud)

1. 이 저장소를 GitHub에 public으로 push 합니다.
2. https://share.streamlit.io 에서 **New app** → 저장소/브랜치 선택.
3. Main file path 에 `app.py` 를 지정합니다.
4. Advanced settings 에서 Python 버전을 **3.11** 로 지정하는 것을 권장합니다.

> 참고: Streamlit 은 최신 Python(3.14 등)에서 의존 패키지 휠이 아직 없을 수 있습니다.
> 로컬에서도 3.11 ~ 3.13 가상환경 사용을 권장합니다.

## 라이선스

MIT

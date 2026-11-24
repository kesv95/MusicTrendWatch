# 작업 핸드오프

## 진행 상태

구현 완료. KST 일일 스냅샷 수집기, 전일 대비 순위·조회수 차이, 분석→검토→작성 LLM 체인, 키/호출 실패 시 규칙 기반 브리핑, 대시보드 카드, GitHub Actions, Mock 테스트를 추가했습니다. JavaScript 문법과 diff 공백 검사는 통과했습니다. 이 실행 환경에는 Python 런처가 없어 Mock 테스트는 작성했지만 실행 결과를 확인하지 못했습니다.

사용자 제약 파일인 `static/chart-data.json`, `scripts/update_chart_data.py`, `music_api.py`는 변경하지 않았습니다.

## 남은 작업

- Actions를 운영에 적용하려면 저장소에서 Contents write 권한을 허용해야 합니다(이미 workflow 파일은 `contents: write` 요청).
- 선택 사항: Actions Secrets에 역할별 `*_API_KEY`와 필요 시 Variables의 역할별 `*_API_URL`, `*_MODEL`을 설정합니다. 미설정이면 규칙 기반으로 동작합니다.
- GitHub Pages에서 첫 일일 Actions 실행이 끝난 뒤 브리핑 카드를 확인합니다.
- Python이 설치된 환경에서 아래 Mock 테스트 명령을 실행해 통과를 확인합니다.

## 완료 기준

- KST 00:05 실행이 전날 날짜 파일을 `static/daily-snapshots/YYYY-MM-DD.json`에 생성한다.
- 전일 스냅샷과 비교해 같은 video ID에 순위·조회수 변화량을 쓰고 신규 진입을 표시한다.
- LLM 체인이 분석→검토→작성 순서로 동작하며 키 누락 또는 LLM 실패 시 `static/daily-briefing.json`에 규칙 브리핑을 쓴다.
- 대시보드에 날짜, 생성 모드, 한국어 브리핑이 표시된다.
- Mock 테스트가 통과하고 제한된 세 파일의 변경이 없다.

## 확인 명령

```powershell
python -m unittest discover -s tests
node --check static/app.js
git diff --check
git status --short
```

## 구현 메모

- 스케줄은 UTC 15:05(한국 시간 00:05)이며 전날의 차트 데이터를 날짜별 마감 데이터로 저장합니다.
- LLM 호출은 `scripts/daily_briefing.py`의 OpenAI 호환 Chat Completions 인터페이스이며 역할별 API URL/모델/키를 받습니다.
- 이 저장소에는 이전 `HANDOFF.md`가 없어 이어받기 문서는 새로 작성했습니다. 이어받으며 문서만으로 판단 불가한 내용은 발견되지 않아 `docs/HANDOFF_GAPS.md`는 만들지 않았습니다.

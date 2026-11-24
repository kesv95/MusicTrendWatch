# Music Trend Watch

YouTube Data API v3에서 한국과 일본의 음악 카테고리 인기 영상 차트를 수집해 K-POP/J-POP 상위 30개와 순위·조회수 변화를 보여줍니다.

## GitHub Pages 동적 차트 설정

GitHub Pages는 Flask 서버를 실행하지 않으므로 GitHub Actions가 15분마다 API를 호출하고 `static/chart-data.json`을 갱신합니다. Pages는 이 파일을 읽어 차트를 표시합니다. 예약 실행은 GitHub 상황에 따라 늦어질 수 있습니다.

1. Google Cloud Console에서 YouTube Data API v3를 활성화하고 API 키를 만듭니다. 가능하면 키를 YouTube Data API v3로 제한합니다.
2. GitHub 저장소의 **Settings → Secrets and variables → Actions**에서 `YOUTUBE_API_KEY` 이름으로 API 키를 저장합니다. 키를 소스 파일이나 프런트엔드 HTML/JS에 넣지 마세요.
3. 저장소의 **Settings → Actions → General → Workflow permissions**에서 **Read and write permissions**를 허용합니다.
4. **Actions → Refresh K-POP and J-POP charts → Run workflow**로 첫 수집을 시작합니다. 수집 스크립트/workflow 변경을 기본 브랜치에 push해도 실행되며, 이후 15분 cron으로 자동 갱신됩니다. Secret만 새로 등록한 경우에는 workflow를 수동 실행하세요.
5. GitHub Pages 배포 소스를 기본 브랜치의 루트로 설정합니다. 차트 데이터 커밋이 올라오면 Pages가 다시 배포합니다.

수집 실패 시 Actions가 실패 유형을 `chart-data.json`에 기록하고 직전 정상 차트 값과 수집 시각을 유지합니다. 화면에는 오류 유형/메시지와 마지막 정상 차트가 표시됩니다. 변동 비교는 직전 수집값과 비교하며, 최초 수집 영상은 `NEW`로 표시합니다.

## KST 데일리 브리핑

`Create KST daily chart briefing` Actions가 매일 00:05 KST(UTC 15:05)에 실행됩니다.

1. 그 시점의 `static/chart-data.json`을 전날 KST 날짜의 마감 스냅샷 `static/daily-snapshots/YYYY-MM-DD.json`으로 저장합니다. 이미 저장된 날짜의 스냅샷은 덮어쓰지 않습니다. 수동 재실행은 브리핑만 다시 만들며, 꼭 다시 찍어야 할 때만 `python scripts/daily_briefing.py --force`를 사용합니다.
2. 그보다 앞선 가장 최근 스냅샷(보통 전일)과 video ID로 비교해 순위 변화(양수=상승)·조회수 변화·신규 진입을 계산합니다. 실행이 하루 빠졌으면 그 이전 스냅샷과 비교하고, 비교 기준 날짜를 `compared_to`에 기록합니다.
3. 최신 한국어 브리핑을 `static/daily-briefing.json`에 저장하고, 대시보드 상단 카드에 날짜·비교 기준·생성 방식과 함께 표시합니다. 첫 실행에는 비교할 스냅샷이 없어 전일 비교 불가 안내가 표시됩니다.

LLM을 사용하려면 Actions Secrets에 `ANALYST_API_KEY`, `REVIEWER_API_KEY`, `WRITER_API_KEY`를 설정하세요. 세 역할은 **분석**(변화 정리) → **검토**(원자료와 수치·과장 대조) → **작성**(원자료·분석·검토 메모를 받아 한국어 3~5문장 작성) 순으로 실행됩니다. 각 역할은 기본으로 OpenAI 호환 Chat Completions URL과 `gpt-4o-mini`를 사용하며, Actions Variables의 `ANALYST_API_URL`/`ANALYST_MODEL`, `REVIEWER_API_URL`/`REVIEWER_MODEL`, `WRITER_API_URL`/`WRITER_MODEL`로 역할마다 다른 제공자와 모델을 지정할 수 있습니다. 키가 하나라도 없거나 호출이 실패하면 규칙 기반 한국어 브리핑을 저장하므로, LLM 키 없이도 끝까지 동작합니다(`mode`: `rules` 또는 `rules (LLM chain failed: …)`).

테스트는 실제 네트워크 호출 없이 Mock HTTP 응답으로 실행되며, 실수로 실제 `requests.post`를 부르면 실패하도록 막혀 있습니다: `python -m unittest discover -s tests`. 데일리 workflow도 브리핑 생성 전에 이 테스트를 실행합니다.

## 로컬 실행

로컬 Flask 앱은 `.env`의 `YOUTUBE_API_KEY`를 사용합니다. 의존성을 설치한 뒤 `python music_api.py`로 실행하세요. GitHub Pages 경로의 주기 수집은 Actions workflow가 담당합니다.

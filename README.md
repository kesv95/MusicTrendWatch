# Music Trend Watch

YouTube Data API v3에서 한국과 일본의 음악 카테고리 인기 영상 차트를 수집해 K-POP/J-POP 상위 30개와 순위·조회수 변화를 보여줍니다.

## GitHub Pages 동적 차트 설정

GitHub Pages는 Flask 서버를 실행하지 않으므로 GitHub Actions가 15분마다 API를 호출하고 `static/chart-data.json`을 갱신합니다. Pages는 이 파일을 읽어 차트를 표시합니다. 예약 실행은 GitHub 상황에 따라 늦어질 수 있습니다.

1. Google Cloud Console에서 YouTube Data API v3를 활성화하고 API 키를 만듭니다. 가능하면 키를 YouTube Data API v3로 제한합니다.
2. GitHub 저장소의 **Settings → Secrets and variables → Actions**에서 `YOUTUBE_API_KEY` 이름으로 API 키를 저장합니다. 키를 소스 파일이나 프런트엔드 HTML/JS에 넣지 마세요.
3. 저장소의 **Settings → Actions → General → Workflow permissions**에서 **Read and write permissions**를 허용합니다.
4. **Actions → Refresh K-POP and J-POP charts → Run workflow**로 첫 수집을 시작합니다. 이후 15분 cron으로 자동 갱신됩니다.
5. GitHub Pages 배포 소스를 기본 브랜치의 루트로 설정합니다. 차트 데이터 커밋이 올라오면 Pages가 다시 배포합니다.

수집 실패 시 Actions가 실패 유형을 `chart-data.json`에 기록하고 직전 정상 차트 값과 수집 시각을 유지합니다. 화면에는 오류 유형/메시지와 마지막 정상 차트가 표시됩니다. 변동 비교는 직전 수집값과 비교하며, 최초 수집 영상은 `NEW`로 표시합니다.

## 로컬 실행

로컬 Flask 앱은 `.env`의 `YOUTUBE_API_KEY`를 사용합니다. 의존성을 설치한 뒤 `python music_api.py`로 실행하세요. GitHub Pages 경로의 주기 수집은 Actions workflow가 담당합니다.

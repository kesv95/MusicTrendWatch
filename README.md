# Music Trend Watch

K-POP/J-POP 음악 트렌드를 보여주는 Flask 앱입니다. `index.html`과 정적 파일은 GitHub Pages에서도 배포할 수 있지만, Pages는 Flask 서버를 실행하지 않으므로 API 기능에는 별도 백엔드가 필요합니다.

## GitHub Pages와 백엔드 연결

1. Flask 앱을 HTTPS를 지원하는 서버에 배포하고 `YOUTUBE_API_KEY` 환경 변수를 설정합니다. API 키는 프런트엔드나 GitHub 저장소에 넣지 마세요.
2. 백엔드의 `CORS_ALLOWED_ORIGINS` 환경 변수에 Pages 사이트의 **origin**을 설정합니다. 예: `https://<사용자명>.github.io` (저장소 경로는 포함하지 않습니다.)
3. `index.html`의 `music-api-base` 메타 태그 `content`에 백엔드 기본 주소를 입력합니다. 예: `content="https://<백엔드-주소>"` (끝의 `/`는 생략합니다.)
4. GitHub Pages의 배포 소스를 프로젝트 루트로 설정하고 `index.html`, `static/` 폴더를 배포합니다.

백엔드 주소가 비어 있으면 `localhost`에서 Flask와 같은 출처로 동작합니다. 배포된 정적 사이트에서 주소가 비어 있으면 페이지에 설정 안내가 표시됩니다.

## 로컬 실행

프로젝트 루트에서 가상환경을 활성화한 뒤 의존성을 설치하고 `.env`에 `YOUTUBE_API_KEY`를 설정하세요. 실행 명령은 `python music_api.py`입니다.

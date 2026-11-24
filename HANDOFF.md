# 작업 핸드오프

## 요청 요약

KST 날짜별 마감 스냅샷을 저장해 전일 대비 순위·조회수 변화량을 계산하고, 역할별 LLM 체인(분석 → 검토 → 작성)으로 한국어 데일리 브리핑을 만들어 대시보드에 표시한다.

제약:
- `static/chart-data.json`, `scripts/update_chart_data.py`, `music_api.py`는 수정하지 않는다.
- API 키가 없어도 규칙 기반 브리핑으로 끝까지 동작해야 한다.
- 테스트는 실제 LLM 호출 없이 Mock으로 작성한다.

## 진행 상태

**구현 및 검증 완료. 로컬 `retest-a` 브랜치에 커밋하지 않은 변경으로 남아 있음(커밋·push는 사용자 확인 후 진행).**

세션 기록:
1. **세션 1 (커밋 `Retest A (Codex/Luna)…`)**: 첫 구현. 실행 환경에 Python이 없어 테스트를 돌리지 못함.
2. **세션 2 (이번 세션)**: 이 문서를 먼저 읽고 이어받음. Python 3.13에서 테스트를 처음 실행함(기존 5개 통과). 코드 검토 중 아래 결함을 발견해 수정함.
   - `env or os.environ` 때문에 `env={}`(키 없음)를 넘겨도 실제 환경변수 키를 읽음. 키가 설정된 환경에서는 테스트가 **실제 LLM을 호출할 수 있었음**. `env is None`일 때만 `os.environ`을 쓰도록 수정함.
   - 같은 날짜로 수동 재실행하면 전날 마감 스냅샷이 그날 차트로 덮어써짐. 이제 기존 스냅샷을 보존하고 `--force`로만 덮어씀.
   - 전일 스냅샷이 없으면(실행이 하루 빠짐) 비교가 끊김. 이제 더 앞선 가장 최근 스냅샷과 비교하고 `compared_to`에 기준 날짜를 기록함.
   - 작성(writer) 역할이 검토 메모만 받아 수치를 확인할 수 없었음. 이제 원자료·분석·검토 메모를 모두 전달함.
   - 첫 실행에서 모든 곡이 `is_new=true`로 표시됨. 비교 기준이 없을 때는 `false`로 수정함.
   - 규칙 브리핑의 고정 조사("…로")가 받침 있는 제목에서 문법 오류를 냄. 조사가 필요 없는 형식으로 바꾸고, 최대 상승·최대 하락·조회수 최대 증가 곡을 추가함.
   - 데일리 workflow의 push가 15분 주기 차트 갱신 push와 충돌할 수 있었음. rebase 후 다시 시도하도록 하고, 브리핑 생성 전에 Mock 테스트를 실행하는 단계를 추가함.
   - 대시보드 카드에 비교 기준 날짜와 "규칙 기반 (AI 실패)" 상태를 표시함.
   - 테스트를 5개에서 18개로 늘림. 모든 테스트에 실제 `requests.post` 호출을 막는 가드를 둠.

변경 파일: `scripts/daily_briefing.py`, `tests/test_daily_briefing.py`, `static/app.js`, `.github/workflows/daily-briefing.yml`(**미적용**, 남은 작업 참고), `README.md`, `HANDOFF.md`, `docs/HANDOFF_GAPS.md`(신규).
제약 파일 3개의 SHA-256 해시가 작업 전과 같음을 확인함.

## 남은 작업

- [ ] **workflow 변경을 직접 적용.** `.github/workflows/daily-briefing.yml`은 원격 도구로 쓸 수 없는 보호 파일이라 세션 2의 수정이 로컬 폴더에 반영되지 않았음. 아래 diff를 적용할 것(push 재시도와 Mock 테스트 단계 추가).

```diff
--- a/.github/workflows/daily-briefing.yml
+++ b/.github/workflows/daily-briefing.yml
@@ -27,6 +27,8 @@
           python-version: "3.12"
       - name: Install requests
         run: python -m pip install requests
+      - name: Run mock tests (no network)
+        run: python -m unittest discover -s tests
       - name: Save daily snapshot and write briefing
         run: python scripts/daily_briefing.py
         env:
@@ -40,6 +42,7 @@
           WRITER_API_URL: ${{ vars.WRITER_API_URL }}
           WRITER_MODEL: ${{ vars.WRITER_MODEL }}
       - name: Commit snapshot and briefing
+        shell: bash
         run: |
           git config user.name "github-actions[bot]"
           git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
@@ -49,4 +52,11 @@
             exit 0
           fi
           git commit -m "Save KST daily chart briefing"
+          # refresh-charts.yml pushes every 15 minutes; rebase onto it if we raced.
+          # The two workflows touch disjoint files, so the rebase cannot conflict.
+          for attempt in 1 2 3; do
+            if git push; then exit 0; fi
+            echo "Push rejected (attempt ${attempt}); rebasing on latest default branch."
+            git pull --rebase origin "${{ github.event.repository.default_branch }}"
+          done
           git push
```

- [ ] 변경 사항을 `retest-a`에 커밋하고 push(사용자 확인 필요). 이번 세션에는 GitHub 연결이 없어 원격 상태를 확인하지 못함.
- [ ] `retest-a`를 기본 브랜치(`main`)에 병합. 두 workflow 모두 **기본 브랜치를 checkout**하므로 병합 전에는 Actions에서 새 코드가 실행되지 않음.
- [ ] 저장소 Settings → Actions → General → Workflow permissions를 Read and write로 설정(workflow는 `contents: write`를 요청함).
- [ ] 선택: Actions Secrets에 `ANALYST_API_KEY`/`REVIEWER_API_KEY`/`WRITER_API_KEY`를, 필요하면 Variables에 역할별 `*_API_URL`/`*_MODEL`을 설정. 설정하지 않으면 규칙 기반으로 동작함.
- [ ] 병합 후 `Create KST daily chart briefing`을 수동 실행해 첫 스냅샷과 브리핑 카드를 GitHub Pages에서 확인. 다음 날 00:05 KST 실행 후 전일 비교 수치가 표시되는지 확인.

## 완료 기준

- 00:05 KST 실행이 전날 KST 날짜의 `static/daily-snapshots/YYYY-MM-DD.json`을 만들고, 재실행해도 덮어쓰지 않는다(`--force` 제외).
- 직전 스냅샷과 같은 video ID끼리 `rank_change`(양수=상승), `view_change`, `previous_rank`, `is_new`를 계산하고 `compared_to`를 기록한다.
- 세 역할 키가 모두 있으면 analyst → reviewer → writer 순으로 호출하고, 키가 하나라도 없거나 어느 단계에서든 실패하면 `static/daily-briefing.json`에 규칙 브리핑을 쓴다(`mode`로 구분).
- 대시보드 카드에 날짜, 비교 기준, 생성 방식, 한국어 브리핑이 표시된다.
- `python -m unittest discover -s tests`가 통과한다. `*_API_KEY` 환경변수가 설정되어 있어도 네트워크 호출 없이 통과한다.
- 제약 파일 3개에 diff가 없다.

## 확인 명령

```powershell
python -m unittest discover -s tests -v
# 키가 있어도 실제 호출이 없는지 확인 (PowerShell)
$env:ANALYST_API_KEY="x"; $env:REVIEWER_API_KEY="x"; $env:WRITER_API_KEY="x"; python -m unittest discover -s tests; Remove-Item Env:ANALYST_API_KEY,Env:REVIEWER_API_KEY,Env:WRITER_API_KEY
node --check static/app.js
git diff --check
git diff --stat -- static/chart-data.json scripts/update_chart_data.py music_api.py   # 출력이 비어 있어야 함
git status --short
```

## 구현 메모

- 스케줄은 UTC 15:05(KST 00:05)이고, 그 시점의 `chart-data.json`을 전날 마감값으로 씀. 원본 수집 시각은 스냅샷의 `source_updated_at`에 기록함.
- LLM 호출은 `scripts/daily_briefing.py`의 `call_llm()`이 담당하는 OpenAI 호환 Chat Completions 인터페이스이며, 역할별로 URL·모델·키를 따로 받음. LLM에는 URL과 썸네일을 뺀 핵심 필드만 보냄.
- 비교 기준이 없는 첫날에는 LLM을 호출하지 않음(분석할 변화가 없음).
- 문서만으로 판단할 수 없었던 점은 `docs/HANDOFF_GAPS.md`에 기록함.

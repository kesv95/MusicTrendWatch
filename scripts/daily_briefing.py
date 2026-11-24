"""Create immutable KST daily chart snapshots and a Korean daily briefing.

Flow (run once per KST day, shortly after 00:00 KST):
1. Read the latest ``static/chart-data.json`` (written by update_chart_data.py,
   which this script never modifies) and save it as the previous KST day's
   closing snapshot ``static/daily-snapshots/YYYY-MM-DD.json``.
2. Compare it with the most recent earlier snapshot (normally the day before)
   by video ID to get rank / view-count changes and new entries.
3. Build a Korean briefing with an LLM chain (analyst -> reviewer -> writer).
   If any role key is missing or any call fails, fall back to a rule-based
   briefing so the job always finishes.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

# KST is UTC+09:00 year-round; a fixed offset avoids requiring Windows tzdata.
KST = timezone(timedelta(hours=9), name="KST")
COUNTRIES = {"korea": "K-POP", "japan": "J-POP"}
ROLES = ("analyst", "reviewer", "writer")
DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
ROLE_INSTRUCTIONS = {
    "analyst": "음악 차트 데이터 분석가입니다. 주어진 수치만 근거로 전일 대비 핵심 변화를 객관적으로 정리하세요.",
    "reviewer": "팩트체커입니다. 분석의 수치를 원자료와 대조해 틀린 값, 근거 없는 추측, 과장을 찾아 교정하세요.",
    "writer": "한국어 음악 뉴스 에디터입니다. 검토 결과를 반영해 원자료에 있는 수치만 사용한 브리핑을 작성하세요.",
}

PostFn = Callable[..., Any]


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def snapshot_tracks(chart_data: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """Return per-country tracks with day-over-day changes keyed by video ID."""
    result: dict[str, list[dict[str, Any]]] = {}
    old_countries = (previous or {}).get("countries", {})
    for country in COUNTRIES:
        old_by_id = {
            str(track.get("video_id")): track
            for track in old_countries.get(country, [])
            if track.get("video_id")
        }
        tracks = []
        current = chart_data.get("countries", {}).get(country, {}).get("data", [])
        for track in current:
            video_id = str(track.get("video_id") or "")
            if not video_id:
                continue
            rank = _int_or_none(track.get("rank")) or 0
            views = _int_or_none(track.get("view_count")) or 0
            old = old_by_id.get(video_id)
            old_rank = _int_or_none(old.get("rank")) if old else None
            old_views = _int_or_none(old.get("view_count")) if old else None
            tracks.append({
                "video_id": video_id,
                "title": track.get("title") or "제목 없음",
                "artist": track.get("artist") or track.get("channel") or "",
                "url": track.get("url", ""),
                "rank": rank,
                "view_count": views,
                "previous_rank": old_rank,
                "rank_change": old_rank - rank if old_rank else None,  # positive = moved up
                "view_change": views - old_views if old_views is not None else None,
                "is_new": previous is not None and old is None,
            })
        tracks.sort(key=lambda t: t["rank"] or 10**6)
        result[country] = tracks
    return result


def summarize(countries: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Small, structured digest used by both the rule briefing and the LLM prompts."""
    summary: dict[str, dict[str, Any]] = {}
    for country in COUNTRIES:
        tracks = countries.get(country, [])
        known = [t for t in tracks if t["rank_change"] is not None]
        up = sorted((t for t in known if t["rank_change"] > 0), key=lambda t: (-t["rank_change"], t["rank"]))
        down = sorted((t for t in known if t["rank_change"] < 0), key=lambda t: (t["rank_change"], t["rank"]))
        views = sorted((t for t in tracks if t["view_change"] is not None), key=lambda t: -t["view_change"])
        summary[country] = {
            "track_count": len(tracks),
            "compared_count": len(known),
            "new_entries": [t["title"] for t in tracks if t["is_new"]],
            "top": tracks[0] if tracks else None,
            "biggest_riser": up[0] if up else None,
            "biggest_faller": down[0] if down else None,
            "top_view_gainer": views[0] if views and views[0]["view_change"] > 0 else None,
        }
    return summary


def build_rule_briefing(day: str, countries: dict[str, list[dict[str, Any]]], compared_to: str | None = None) -> str:
    if compared_to:
        header = f"{day} KST 마감 기준 데일리 차트 브리핑입니다. ({compared_to} 마감과 비교)"
    else:
        header = f"{day} KST 마감 기준 데일리 차트 브리핑입니다."
    parts = [header]
    for country, label in COUNTRIES.items():
        s = summarize(countries)[country]
        if not s["track_count"]:
            parts.append(f"{label}: 수집된 차트 데이터가 없습니다.")
            continue
        top = s["top"]
        if compared_to is None:
            parts.append(
                f"{label}: 1위 「{top['title']}」. "
                "전일 비교 스냅샷이 없어 순위·조회수 변화는 다음 마감부터 제공됩니다."
            )
            continue
        if top["is_new"]:
            top_note = "신규 진입"
        elif top["rank_change"] == 0:
            top_note = "자리 유지"
        elif top["rank_change"] is not None and top["rank_change"] > 0:
            top_note = f"{top['previous_rank']}위에서 상승"
        else:
            top_note = "순위 변동"
        lines = [
            f"1위 「{top['title']}」({top_note}).",
            f"전일과 이어진 곡 {s['compared_count']}곡, 신규 진입 {len(s['new_entries'])}곡.",
        ]
        if s["biggest_riser"]:
            t = s["biggest_riser"]
            lines.append(f"최대 상승 「{t['title']}」 {t['rank_change']}계단↑ → {t['rank']}위.")
        if s["biggest_faller"]:
            t = s["biggest_faller"]
            lines.append(f"최대 하락 「{t['title']}」 {-t['rank_change']}계단↓ → {t['rank']}위.")
        if s["top_view_gainer"]:
            t = s["top_view_gainer"]
            lines.append(f"조회수 최대 증가 「{t['title']}」 +{t['view_change']:,}회.")
        detail = " ".join(lines)
        parts.append(f"{label}: {detail}")
    return "\n".join(parts)


def call_llm(role: str, prompt: str, *, env: Mapping[str, str], post: PostFn) -> str:
    """Call the role's OpenAI-compatible endpoint; callers handle provider failures."""
    prefix = role.upper()
    key = env.get(f"{prefix}_API_KEY")
    if not key:
        raise RuntimeError(f"{role} API key is not configured")
    endpoint = env.get(f"{prefix}_API_URL") or DEFAULT_API_URL
    model = env.get(f"{prefix}_MODEL") or DEFAULT_MODEL
    response = post(endpoint, headers={"Authorization": f"Bearer {key}"}, json={
        "model": model,
        "messages": [
            {"role": "system", "content": f"[{role}] {ROLE_INSTRUCTIONS[role]} 반드시 한국어로 응답하세요."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }, timeout=60)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"{role} returned empty content")
    return content.strip()


def _llm_payload(day: str, compared_to: str | None, countries: dict[str, list[dict[str, Any]]]) -> str:
    keep = ("rank", "previous_rank", "rank_change", "title", "artist", "view_count", "view_change", "is_new")
    compact = {
        COUNTRIES[c]: [{k: t[k] for k in keep} for t in countries.get(c, [])]
        for c in COUNTRIES
    }
    return json.dumps(
        {"date": day, "compared_to": compared_to, "rank_change_note": "양수=상승", "charts": compact},
        ensure_ascii=False,
    )


def create_briefing(
    day: str,
    countries: dict[str, list[dict[str, Any]]],
    *,
    compared_to: str | None = None,
    env: Mapping[str, str] | None = None,
    post: PostFn = requests.post,
) -> tuple[str, str]:
    """Return (briefing_text, mode). mode is "llm", "rules" or "rules (LLM chain failed: ...)"."""
    env = os.environ if env is None else env
    fallback = build_rule_briefing(day, countries, compared_to)
    if not all(env.get(f"{role.upper()}_API_KEY") for role in ROLES):
        return fallback, "rules"
    if compared_to is None:
        # Nothing to analyse yet; the rule text already explains that.
        return fallback, "rules"
    data = _llm_payload(day, compared_to, countries)
    try:
        analysis = call_llm("analyst", f"전일 대비 차트 변화를 분석하세요.\n원자료: {data}", env=env, post=post)
        review = call_llm(
            "reviewer",
            f"분석을 원자료와 대조해 수치 오류와 과장을 교정한 검토 메모를 작성하세요.\n원자료: {data}\n분석: {analysis}",
            env=env, post=post,
        )
        draft = call_llm(
            "writer",
            "검토 메모의 교정 사항을 반영해 K-POP과 J-POP을 모두 다루는 한국어 3~5문장 데일리 브리핑을 작성하세요. "
            f"원자료에 없는 수치는 쓰지 마세요.\n날짜: {day} (비교 기준 {compared_to})\n원자료: {data}\n분석: {analysis}\n검토 메모: {review}",
            env=env, post=post,
        )
        return draft, "llm"
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, RuntimeError) as exc:
        return fallback, f"rules (LLM chain failed: {type(exc).__name__})"


def find_previous_snapshot(snapshot_dir: Path, day: str) -> Path | None:
    """Most recent snapshot strictly before ``day`` (normally day-1; tolerates skipped runs)."""
    candidates = []
    for path in snapshot_dir.glob("*.json"):
        try:
            snap_day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if snap_day < date.fromisoformat(day):
            candidates.append((snap_day, path))
    return max(candidates)[1] if candidates else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(
    root: Path,
    *,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
    post: PostFn = requests.post,
    force: bool = False,
) -> tuple[Path, Path]:
    now = now or datetime.now(KST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    now_kst = now.astimezone(KST)
    day = (now_kst.date() - timedelta(days=1)).isoformat()
    snapshot_dir = root / "static" / "daily-snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{day}.json"

    if snapshot_path.exists() and not force:
        # A closing snapshot is immutable: a manual re-run later in the day must not
        # replace yesterday's close with today's chart. Rebuild only the briefing.
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        countries = snapshot["countries"]
        compared_to = snapshot.get("compared_to")
    else:
        previous_path = find_previous_snapshot(snapshot_dir, day)
        previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path else None
        compared_to = previous_path.stem if previous_path else None
        chart_data = json.loads((root / "static" / "chart-data.json").read_text(encoding="utf-8"))
        countries = snapshot_tracks(chart_data, previous)
        _write_json(snapshot_path, {
            "date": day,
            "timezone": "Asia/Seoul",
            "captured_at": now_kst.isoformat(),
            "source_updated_at": chart_data.get("updated_at"),
            "compared_to": compared_to,
            "countries": countries,
        })

    briefing, mode = create_briefing(day, countries, compared_to=compared_to, env=env, post=post)
    briefing_path = root / "static" / "daily-briefing.json"
    _write_json(briefing_path, {
        "date": day,
        "timezone": "Asia/Seoul",
        "generated_at": now_kst.isoformat(),
        "compared_to": compared_to,
        "mode": mode,
        "text": briefing,
    })
    return snapshot_path, briefing_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="overwrite an existing closing snapshot")
    args = parser.parse_args(argv)
    snapshot, brief = run(Path(__file__).resolve().parents[1], force=args.force)
    mode = json.loads(brief.read_text(encoding="utf-8"))["mode"]
    print(f"Snapshot: {snapshot}\nBriefing: {brief} (mode: {mode})")


if __name__ == "__main__":
    main()

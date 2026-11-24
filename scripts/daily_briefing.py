"""Create immutable KST daily chart snapshots and a Korean daily briefing."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

# KST is UTC+09:00 year-round; a fixed offset avoids requiring Windows tzdata.
KST = timezone(timedelta(hours=9), name="KST")
COUNTRIES = {"korea": "K-POP", "japan": "J-POP"}


def snapshot_tracks(chart_data: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
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
            video_id = str(track.get("video_id", ""))
            if not video_id:
                continue
            rank = int(track.get("rank") or 0)
            views = int(track.get("view_count") or 0)
            old = old_by_id.get(video_id)
            old_rank = int(old.get("rank") or 0) if old else None
            old_views = int(old.get("view_count") or 0) if old else None
            tracks.append({
                "video_id": video_id,
                "title": track.get("title", "제목 없음"),
                "artist": track.get("artist") or track.get("channel", ""),
                "url": track.get("url", ""),
                "rank": rank,
                "view_count": views,
                "rank_change": old_rank - rank if old_rank is not None else None,
                "view_change": views - old_views if old_views is not None else None,
                "is_new": old is None,
            })
        result[country] = tracks
    return result


def build_rule_briefing(day: str, countries: dict[str, list[dict[str, Any]]]) -> str:
    parts = [f"{day} KST 마감 기준 데일리 차트 브리핑입니다."]
    for country, label in COUNTRIES.items():
        tracks = countries.get(country, [])
        known = [t for t in tracks if t["rank_change"] is not None]
        movers = sorted((t for t in known if t["rank_change"] > 0), key=lambda t: (-t["rank_change"], t["rank"]))
        new_count = sum(t["is_new"] for t in tracks)
        top = tracks[0] if tracks else None
        if not known:
            detail = "전일 비교 스냅샷이 없어 순위·조회수 변화는 다음 마감부터 제공됩니다."
        else:
            detail = f"전일 대비 {len(known)}곡을 비교했고 신규 진입은 {new_count}곡입니다."
            if movers:
                t = movers[0]
                detail += f" 가장 크게 오른 곡은 {t['title']}로 {t['rank_change']}계단 상승했습니다."
            if top and top.get("view_change") is not None:
                detail += f" 1위 {top['title']}의 조회수는 {top['view_change']:+,}회 변했습니다."
        parts.append(f"{label}: {detail}")
    return "\n".join(parts)


def call_llm(role: str, prompt: str, *, env: dict[str, str] | None = None, post=requests.post) -> str:
    """Call the role's OpenAI-compatible endpoint; callers handle provider failures."""
    env = env or os.environ
    key = env.get(f"{role.upper()}_API_KEY")
    if not key:
        raise RuntimeError(f"{role} API key is not configured")
    endpoint = env.get(f"{role.upper()}_API_URL") or "https://api.openai.com/v1/chat/completions"
    model = env.get(f"{role.upper()}_MODEL") or "gpt-4o-mini"
    response = post(endpoint, headers={"Authorization": f"Bearer {key}"}, json={
        "model": model,
        "messages": [
            {"role": "system", "content": f"당신은 음악 차트 브리핑의 {role} 역할입니다. 한국어로 응답하세요."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }, timeout=30)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"{role} returned empty content")
    return content.strip()


def create_briefing(day: str, countries: dict[str, list[dict[str, Any]]], *, env: dict[str, str] | None = None, post=requests.post) -> tuple[str, str]:
    fallback = build_rule_briefing(day, countries)
    env = env or os.environ
    roles = ("analyst", "reviewer", "writer")
    if not all(env.get(f"{role.upper()}_API_KEY") for role in roles):
        return fallback, "rules"
    data = json.dumps(countries, ensure_ascii=False)
    try:
        analysis = call_llm("analyst", f"차트의 전일 대비 핵심 변화를 객관적으로 분석하세요. 데이터: {data}", env=env, post=post)
        review = call_llm("reviewer", f"다음 분석의 수치와 과장 여부를 검토하고 교정안을 작성하세요. 원자료: {data}\n분석: {analysis}", env=env, post=post)
        draft = call_llm("writer", f"검토된 내용을 한국어 3~5문장 데일리 브리핑으로 작성하세요. 날짜: {day}\n검토: {review}", env=env, post=post)
        return draft, "llm"
    except (requests.RequestException, KeyError, TypeError, ValueError, RuntimeError) as exc:
        return fallback, f"rules (LLM chain failed: {type(exc).__name__})"


def run(root: Path, *, now: datetime | None = None, env: dict[str, str] | None = None, post=requests.post) -> tuple[Path, Path]:
    now = now or datetime.now(KST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    day = (now.astimezone(KST).date() - timedelta(days=1)).isoformat()
    previous_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    chart_path = root / "static" / "chart-data.json"
    snapshot_dir = root / "static" / "daily-snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    previous_path = snapshot_dir / f"{previous_day}.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else None
    chart_data = json.loads(chart_path.read_text(encoding="utf-8"))
    countries = snapshot_tracks(chart_data, previous)
    snapshot = {"date": day, "timezone": "Asia/Seoul", "captured_at": now.astimezone(KST).isoformat(), "source_updated_at": chart_data.get("updated_at"), "countries": countries}
    snapshot_path = snapshot_dir / f"{day}.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    briefing, mode = create_briefing(day, countries, env=env, post=post)
    briefing_path = root / "static" / "daily-briefing.json"
    briefing_path.write_text(json.dumps({"date": day, "timezone": "Asia/Seoul", "generated_at": now.astimezone(KST).isoformat(), "mode": mode, "text": briefing}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot_path, briefing_path


if __name__ == "__main__":
    _, brief = run(Path(__file__).resolve().parents[1])
    print(f"Wrote daily snapshot and briefing: {brief}")

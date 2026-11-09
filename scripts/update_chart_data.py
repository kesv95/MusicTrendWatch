"""Fetch the KR/JP YouTube Music charts and retain changes between runs."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "chart-data.json"
API_URL = "https://www.googleapis.com/youtube/v3/videos"
COUNTRIES = {
    "korea": {"name": "South Korea", "region": "KR"},
    "japan": {"name": "Japan", "region": "JP"},
}


class ChartFetchError(Exception):
    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_previous():
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"countries": {}, "updated_at": None}


def fetch_chart(country, info, api_key):
    try:
        response = requests.get(
            API_URL,
            params={
                "part": "snippet,statistics",
                "chart": "mostPopular",
                "regionCode": info["region"],
                "videoCategoryId": "10",
                "maxResults": 50,
                "key": api_key,
            },
            timeout=30,
        )
    except requests.RequestException as error:
        raise ChartFetchError(
            "NETWORK_ERROR", f"YouTube API 요청 실패 ({type(error).__name__})"
        ) from None

    try:
        payload = response.json()
    except ValueError:
        raise ChartFetchError(
            f"HTTP_{response.status_code}", "YouTube API가 JSON이 아닌 응답을 반환했습니다."
        ) from None

    if not response.ok:
        errors = payload.get("error", {}).get("errors", [])
        reason = errors[0].get("reason") if errors else None
        message = payload.get("error", {}).get("message", "YouTube API 요청 실패")
        error_type = f"YOUTUBE_API_{reason}" if reason else f"HTTP_{response.status_code}"
        raise ChartFetchError(error_type, message)

    items = payload.get("items")
    if not isinstance(items, list) or len(items) < 30:
        raise ChartFetchError(
            "DATA_ERROR", f"차트 응답이 30개 미만입니다 ({len(items or [])}개)."
        )

    tracks = []
    for rank, video in enumerate(items[:30], start=1):
        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})
        video_id = video.get("id")
        if not video_id:
            continue

        thumbnails = snippet.get("thumbnails", {})
        thumbnail = (
            thumbnails.get("medium")
            or thumbnails.get("high")
            or thumbnails.get("default")
            or {}
        )
        tracks.append({
            "rank": rank,
            "original_rank": rank,
            "source_type": "chart",
            "video_id": video_id,
            "title": snippet.get("title", "제목 없음"),
            "artist": snippet.get("channelTitle", ""),
            "channel": snippet.get("channelTitle", ""),
            "thumbnail": thumbnail.get("url", ""),
            "published_at": snippet.get("publishedAt", ""),
            "view_count": int(statistics.get("viewCount", 0)),
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })

    if len(tracks) < 30:
        raise ChartFetchError(
            "DATA_ERROR", f"유효한 차트 영상이 30개 미만입니다 ({len(tracks)}개)."
        )
    return tracks


def attach_changes(tracks, previous_tracks):
    previous_by_id = {
        track.get("video_id"): track
        for track in previous_tracks
        if track.get("video_id")
    }
    result = []

    for track in tracks:
        previous = previous_by_id.get(track["video_id"])
        if not previous:
            result.append({
                **track,
                "rank_status": "NEW",
                "rank_difference": None,
                "view_status": "NEW",
                "view_difference": None,
            })
            continue

        rank_difference = int(previous.get("rank", track["rank"])) - track["rank"]
        view_difference = track["view_count"] - int(previous.get("view_count", 0))
        result.append({
            **track,
            "rank_status": (
                "UP" if rank_difference > 0
                else "DOWN" if rank_difference < 0
                else "SAME"
            ),
            "rank_difference": rank_difference,
            "view_status": (
                "UP" if view_difference > 0
                else "DOWN" if view_difference < 0
                else "SAME"
            ),
            "view_difference": view_difference,
        })
    return result


def main():
    api_key = os.getenv("YOUTUBE_API_KEY")
    previous = load_previous()
    old_countries = previous.get("countries", {})
    countries = {}
    data_changed = False
    observed_at = now_utc()

    for country, info in COUNTRIES.items():
        old = old_countries.get(country, {})
        try:
            if not api_key:
                raise ChartFetchError(
                    "CONFIGURATION_ERROR",
                    "GitHub Actions secret YOUTUBE_API_KEY가 설정되지 않았습니다.",
                )
            tracks = attach_changes(
                fetch_chart(country, info, api_key), old.get("data", [])
            )
            current = {
                "country": country,
                "country_name": info["name"],
                "chart_count": len(tracks),
                "data": tracks,
                "updated_at": old.get("updated_at"),
            }
            status_fields = {
                "rank_status", "rank_difference", "view_status", "view_difference"
            }
            current_values = [
                {key: value for key, value in track.items() if key not in status_fields}
                for track in tracks
            ]
            previous_values = [
                {key: value for key, value in track.items() if key not in status_fields}
                for track in old.get("data", [])
            ]
            if current_values != previous_values:
                current["updated_at"] = observed_at
                data_changed = True
            countries[country] = current
        except ChartFetchError as error:
            failure = {
                "type": error.error_type,
                "message": str(error),
            }
            current = dict(old)
            current["error"] = failure
            countries[country] = current
            print(f"{country} chart fetch failed: {error.error_type}: {error}")
        except Exception as error:
            failure = {
                "type": "PROCESSING_ERROR",
                "message": f"차트 처리 중 오류가 발생했습니다 ({type(error).__name__}).",
            }
            current = dict(old)
            current["error"] = failure
            countries[country] = current
            print(f"{country} chart processing failed: {failure['message']}")

    output = {
        "source": "YouTube Data API v3",
        "updated_at": observed_at if data_changed or not previous.get("updated_at") else previous["updated_at"],
        "countries": countries,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(OUTPUT)
    print("Chart data saved; failed countries retain their last successful values.")


if __name__ == "__main__":
    main()

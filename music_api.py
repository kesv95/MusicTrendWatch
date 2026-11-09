import json
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta

import requests
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# index.html은 프로젝트 루트에 두고, 정적 파일은 기본 static/ 경로에서 제공한다.
app = Flask(__name__, template_folder=BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, "database", "music.db")

API_KEY = os.getenv("YOUTUBE_API_KEY")
CORS_ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}
VIDEO_API_URL = "https://www.googleapis.com/youtube/v3/videos"
SEARCH_API_URL = "https://www.googleapis.com/youtube/v3/search"

# search.list는 할당량 소모가 크므로 국가별 검색 ID를 24시간 캐시한다.
SEARCH_CACHE_SECONDS = 24 * 60 * 60
SEARCH_QUERIES = {
    "korea": {
        "q": "한국 대중음악 발라드 힙합 R&B 인디 밴드 인기곡",
        "region": "KR",
        "language": "ko",
    },
    "japan": {
        "q": "日本 人気音楽 J-POP バラード ロック ヒップホップ",
        "region": "JP",
        "language": "ja",
    },
}
COUNTRIES = {
    "korea": {"name": "South Korea", "code": "KR"},
    "japan": {"name": "Japan", "code": "JP"},
}

# 새 순위 기준은 기존 기록과 분리한다.
# 기존 music_snapshots 행은 삭제하지 않고 그대로 보존한다.
SNAPSHOT_CHARTS = {"kpop_v2", "jpop_v2"}


def db_connect():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS music_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chart TEXT NOT NULL,
                video_id TEXT NOT NULL,
                rank INTEGER NOT NULL,
                view_count INTEGER NOT NULL,
                captured_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_music_snapshots
            ON music_snapshots (chart, video_id, id)
        """)
        # 검색 ID 캐시 테이블 추가. 기존 순위 기록 테이블은 변경하지 않는다.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS music_search_cache (
                country TEXT PRIMARY KEY,
                video_ids TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)


initialize_database()


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "").rstrip("/")
    if origin in CORS_ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Vary"] = "Origin"
    return response


def youtube_get(url, params):
    """YouTube API 호출 및 오류 메시지 정리."""
    response = requests.get(url, params=params, timeout=20)

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not response.ok:
        error = payload.get("error", {})
        errors = error.get("errors", [])
        reason = errors[0].get("reason") if errors else None
        message = error.get("message") or f"YouTube API HTTP {response.status_code}"
        raise RuntimeError(f"{reason or 'YOUTUBE_API_ERROR'}: {message}")

    return payload


def convert_video(video, rank=None, source_type="chart"):
    snippet = video.get("snippet", {})
    statistics = video.get("statistics", {})
    video_id = video.get("id")

    return {
        "rank": rank,
        "original_rank": rank,
        "source_type": source_type,
        "video_id": video_id,
        "title": snippet.get("title", ""),
        # YouTube channelTitle은 실제 아티스트명이 아닐 수 있다.
        "artist": snippet.get("channelTitle", ""),
        "channel": snippet.get("channelTitle", ""),
        "thumbnail": (
            snippet.get("thumbnails", {})
            .get("medium", {})
            .get("url", "")
        ),
        "published_at": snippet.get("publishedAt", ""),
        "view_count": int(statistics.get("viewCount", 0)),
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


def get_popular_music(country):
    country_info = COUNTRIES[country]
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": country_info["code"],
        "videoCategoryId": "10",
        "maxResults": 50,
        "key": API_KEY,
    }
    result = youtube_get(VIDEO_API_URL, params)

    tracks = []
    for index, video in enumerate(result.get("items", []), start=1):
        tracks.append(convert_video(video, rank=index, source_type="chart"))
    return tracks


def get_cached_search_ids(country):
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT video_ids, expires_at
            FROM music_search_cache
            WHERE country = ?
            """,
            (country,),
        ).fetchone()

    if row and time.time() < row[1]:
        try:
            ids = json.loads(row[0])
            if isinstance(ids, list):
                print(f"{country} 검색 ID: 24시간 캐시 사용")
                return ids
        except (TypeError, ValueError):
            pass

    query = SEARCH_QUERIES[country]
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=180)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")

    params = {
        "part": "snippet",
        "q": query["q"],
        "type": "video",
        "regionCode": query["region"],
        "relevanceLanguage": query["language"],
        "videoCategoryId": "10",
        "order": "viewCount",
        "publishedAfter": published_after,
        "maxResults": 50,
        "key": API_KEY,
    }

    result = youtube_get(SEARCH_API_URL, params)
    ids = [
        item.get("id", {}).get("videoId")
        for item in result.get("items", [])
        if item.get("id", {}).get("videoId")
    ]

    fetched_at = datetime.now(timezone.utc).isoformat()
    expires_at = time.time() + SEARCH_CACHE_SECONDS

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO music_search_cache
                (country, video_ids, fetched_at, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(country) DO UPDATE SET
                video_ids = excluded.video_ids,
                fetched_at = excluded.fetched_at,
                expires_at = excluded.expires_at
            """,
            (country, json.dumps(ids), fetched_at, expires_at),
        )

    return ids


def get_country_search_music(country):
    """국가별 검색 후보. 검색 ID는 24시간 캐시하고 조회수는 매번 갱신."""
    video_ids = get_cached_search_ids(country)
    if not video_ids:
        return []

    tracks = []
    # videos.list는 한 번에 최대 50개 ID를 조회할 수 있다.
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]
        params = {
            "part": "snippet,statistics",
            "id": ",".join(batch),
            "key": API_KEY,
        }
        result = youtube_get(VIDEO_API_URL, params)
        for video in result.get("items", []):
            tracks.append(convert_video(video, rank=None, source_type="search"))

    tracks.sort(key=lambda item: item["view_count"], reverse=True)
    for index, track in enumerate(tracks, start=1):
        track["search_rank"] = index
    return tracks


def merge_tracks(chart_tracks, search_tracks):
    """동일 video_id는 한 번만 남기고 인기 차트 출처를 우선한다."""
    merged = []
    seen = set()

    for track in chart_tracks + search_tracks:
        video_id = track.get("video_id")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        merged.append(track)

    return merged


def save_music_snapshot(chart, tracks):
    if chart not in SNAPSHOT_CHARTS:
        raise ValueError("지원하지 않는 순위 기록 구분입니다.")

    changes = {}
    captured_at = datetime.now(timezone.utc).isoformat()

    with db_connect() as conn:
        for track in tracks:
            video_id = track.get("video_id")
            if not video_id:
                continue

            current_rank = int(track.get("rank", 0))
            current_views = int(track.get("view_count", 0))

            previous = conn.execute(
                """
                SELECT rank, view_count
                FROM music_snapshots
                WHERE chart = ? AND video_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (chart, video_id),
            ).fetchone()

            if previous:
                previous_rank, previous_views = previous
                rank_difference = previous_rank - current_rank
                view_difference = current_views - previous_views

                rank_status = (
                    "UP" if rank_difference > 0
                    else "DOWN" if rank_difference < 0
                    else "SAME"
                )
                view_status = (
                    "UP" if view_difference > 0
                    else "DOWN" if view_difference < 0
                    else "SAME"
                )

                changes[video_id] = {
                    "rank_status": rank_status,
                    "rank_difference": rank_difference,
                    "view_status": view_status,
                    "view_difference": view_difference,
                    "previous_rank": previous_rank,
                }
            else:
                changes[video_id] = {
                    "rank_status": "NEW",
                    "rank_difference": None,
                    "view_status": "NEW",
                    "view_difference": None,
                    "previous_rank": None,
                }

            conn.execute(
                """
                INSERT INTO music_snapshots
                    (chart, video_id, rank, view_count, captured_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chart, video_id, current_rank, current_views, captured_at),
            )

    return changes


def get_music_data(country):
    if not API_KEY:
        return {
            "success": False,
            "error": "API_KEY_MISSING",
            "message": "YouTube API 키가 설정되지 않았습니다.",
        }

    if country not in COUNTRIES:
        return {
            "success": False,
            "error": "INVALID_COUNTRY",
            "message": "지원하지 않는 국가입니다.",
        }

    try:
        chart_tracks = get_popular_music(country)
        search_warning = None
        search_tracks = []

        try:
            search_tracks = get_country_search_music(country)
        except (
            requests.exceptions.RequestException,
            ValueError,
            RuntimeError,
        ) as error:
            search_warning = str(error)
            app.logger.warning("%s 검색 데이터 수집 오류: %s", country, error)

        tracks = merge_tracks(chart_tracks, search_tracks)

        return {
            "success": True,
            "country": country,
            "country_name": COUNTRIES[country]["name"],
            "count": len(tracks),
            "chart_count": len(chart_tracks),
            "search_count": len(search_tracks),
            "search_warning": search_warning,
            "search_cache_hours": 24,
            "data": tracks,
            "message": (
                "국가별 인기 차트와 국가 대상 음악 검색 결과를 통합했습니다. "
                "검색 결과는 공식 순위가 아닌 검색 후보입니다."
            ),
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "TIMEOUT",
            "message": "YouTube API 응답 시간이 초과되었습니다.",
        }
    except requests.exceptions.RequestException as error:
        return {
            "success": False,
            "error": "REQUEST_ERROR",
            "message": str(error),
        }
    except ValueError:
        return {
            "success": False,
            "error": "JSON_ERROR",
            "message": "API 응답을 JSON으로 변환하지 못했습니다.",
        }
    except RuntimeError as error:
        message = str(error)
        error_code = message.split(":", 1)[0]
        return {
            "success": False,
            "error": error_code,
            "message": message,
        }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/music/<country>")
def music(country):
    result = get_music_data(country)
    status_code = 200 if result["success"] else 500
    if result.get("error") == "INVALID_COUNTRY":
        status_code = 400
    return jsonify(result), status_code


@app.route("/api/music/snapshot/<chart>", methods=["POST"])
def music_snapshot(chart):
    if chart not in SNAPSHOT_CHARTS:
        return jsonify({
            "success": False,
            "message": "지원하지 않는 차트 기록 구분입니다.",
        }), 400

    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("tracks"), list):
        return jsonify({
            "success": False,
            "message": "저장할 음악 데이터가 없습니다.",
        }), 400

    try:
        changes = save_music_snapshot(chart, data["tracks"])
        return jsonify({
            "success": True,
            "chart": chart,
            "count": len(data["tracks"]),
            "changes": changes,
        })
    except (TypeError, ValueError) as error:
        return jsonify({
            "success": False,
            "message": str(error),
        }), 400


if __name__ == "__main__":
    app.run(debug=True)

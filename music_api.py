
import os
import time
import requests

from flask import Flask, jsonify, render_template
from dotenv import load_dotenv

# 환경변수 불러오기
load_dotenv()

app = Flask(__name__)

# YouTube API 설정
API_KEY = os.getenv("YOUTUBE_API_KEY")

VIDEO_API_URL = "https://www.googleapis.com/youtube/v3/videos"
SEARCH_API_URL = "https://www.googleapis.com/youtube/v3/search"

# J-POP 검색 결과 캐시
JPOP_SEARCH_CACHE = {
    "data": [],
    "expires_at": 0
}

# 검색 결과 캐시 시간: 24시간
CACHE_DURATION = 24 * 60 * 60

# 국가별 설정
COUNTRIES = {
    "korea": {
        "name": "South Korea",
        "code": "KR"
    },
    "japan": {
        "name": "Japan",
        "code": "JP"
    }
}


# =========================================
# 동영상 데이터 변환
# =========================================

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
        "artist": snippet.get("channelTitle", ""),
        "thumbnail": snippet.get(
            "thumbnails", {}
        ).get("medium", {}).get("url", ""),
        "published_at": snippet.get("publishedAt", ""),
        "view_count": int(
            statistics.get("viewCount", 0)
        ),
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }


# =========================================
# 기존 국가별 인기 음악 데이터 수집
# =========================================

def get_popular_music(country):

    country_info = COUNTRIES[country]

    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": country_info["code"],
        "videoCategoryId": "10",
        "maxResults": 50,
        "key": API_KEY
    }

    response = requests.get(
        VIDEO_API_URL,
        params=params,
        timeout=15
    )

    result = response.json()

    if response.status_code != 200:

        error_info = result.get("error", {})

        raise RuntimeError(
            error_info.get(
                "message",
                "YouTube 인기 차트 요청 실패"
            )
        )

    videos = result.get("items", [])

    music_list = []

    for index, video in enumerate(videos, start=1):

        music_list.append(
            convert_video(
                video,
                rank=index,
                source_type="chart"
            )
        )

    return music_list


# =========================================
# J-POP 검색 데이터 수집
# =========================================

def get_jpop_search_data():

    global JPOP_SEARCH_CACHE

    # 캐시 유효성 확인
    if time.time() < JPOP_SEARCH_CACHE["expires_at"]:

        print("J-POP 검색 데이터: 캐시 사용")

        return JPOP_SEARCH_CACHE["data"]

    print("J-POP 검색 데이터: YouTube 검색 API 호출")

    # YouTube 검색 API 요청
    search_params = {
        "part": "snippet",
        "q": "J-POP 人気曲",
        "type": "video",
        "regionCode": "JP",
        "relevanceLanguage": "ja",
        "videoCategoryId": "10",
        "order": "viewCount",
        "maxResults": 50,
        "key": API_KEY
    }

    search_response = requests.get(
        SEARCH_API_URL,
        params=search_params,
        timeout=15
    )

    search_result = search_response.json()

    if search_response.status_code != 200:

        error_info = search_result.get("error", {})

        raise RuntimeError(
            error_info.get(
                "message",
                "J-POP 검색 API 요청 실패"
            )
        )

    # 검색 결과에서 동영상 ID 추출
    search_items = search_result.get("items", [])

    video_ids = [
        item.get("id", {}).get("videoId")
        for item in search_items
        if item.get("id", {}).get("videoId")
    ]

    if not video_ids:

        JPOP_SEARCH_CACHE = {
            "data": [],
            "expires_at": time.time() + CACHE_DURATION
        }

        return []

    # 동영상 상세 정보 요청
    video_params = {
        "part": "snippet,statistics",
        "id": ",".join(video_ids),
        "key": API_KEY
    }

    video_response = requests.get(
        VIDEO_API_URL,
        params=video_params,
        timeout=15
    )

    video_result = video_response.json()

    if video_response.status_code != 200:

        error_info = video_result.get("error", {})

        raise RuntimeError(
            error_info.get(
                "message",
                "J-POP 동영상 상세 정보 요청 실패"
            )
        )

    videos = video_result.get("items", [])

    search_list = []

    for video in videos:

        search_list.append(
            convert_video(
                video,
                rank=None,
                source_type="search"
            )
        )

    # 조회수 기준 정렬
    search_list.sort(
        key=lambda item: item["view_count"],
        reverse=True
    )

    # 검색 결과 캐시 저장
    JPOP_SEARCH_CACHE = {
        "data": search_list,
        "expires_at": time.time() + CACHE_DURATION
    }

    return search_list


# =========================================
# 국가별 음악 데이터 수집
# =========================================

def get_music_data(country):

    if not API_KEY:

        return {
            "success": False,
            "error": "API_KEY_MISSING",
            "message": "YouTube API 키가 설정되지 않았습니다."
        }

    if country not in COUNTRIES:

        return {
            "success": False,
            "error": "INVALID_COUNTRY",
            "message": "지원하지 않는 국가입니다."
        }

    country_info = COUNTRIES[country]

    try:

        # 기존 인기 차트 수집
        music_list = get_popular_music(country)

        search_warning = None
        search_count = 0

        # 일본 데이터일 때만 J-POP 검색 결과 추가
        if country == "japan":

            try:

                search_list = get_jpop_search_data()

                music_list.extend(search_list)

                search_count = len(search_list)

            except (
                requests.exceptions.RequestException,
                ValueError,
                RuntimeError
            ) as error:

                search_warning = str(error)

                print(
                    "J-POP 검색 데이터 수집 오류:",
                    search_warning
                )

        return {
            "success": True,
            "country": country,
            "country_name": country_info["name"],
            "count": len(music_list),
            "chart_count": len(
                [
                    item for item in music_list
                    if item["source_type"] == "chart"
                ]
            ),
            "search_count": search_count,
            "search_warning": search_warning,
            "data": music_list
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "error": "TIMEOUT",
            "message": "YouTube API 응답 시간이 초과되었습니다."
        }

    except requests.exceptions.RequestException as error:

        return {
            "success": False,
            "error": "REQUEST_ERROR",
            "message": str(error)
        }

    except ValueError:

        return {
            "success": False,
            "error": "JSON_ERROR",
            "message": "API 응답을 JSON으로 변환하지 못했습니다."
        }

    except RuntimeError as error:

        return {
            "success": False,
            "error": "YOUTUBE_API_ERROR",
            "message": str(error)
        }


# =========================================
# 메인 페이지
# =========================================

@app.route("/")
def index():

    return render_template("index.html")


# =========================================
# 국가별 음악 데이터 API
# =========================================

@app.route("/api/music/<country>")
def music(country):

    result = get_music_data(country)

    status_code = 200 if result["success"] else 500

    if result.get("error") == "INVALID_COUNTRY":
        status_code = 400

    return jsonify(result), status_code


if __name__ == "__main__":

    app.run(debug=True)

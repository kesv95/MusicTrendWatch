/* =========================================
   MUSIC TREND WATCH
   K-POP / J-POP CHART
========================================= */


// =========================================
// 1. HTML 요소
// =========================================

const koreaList = document.getElementById("kpop-list");
const japanList = document.getElementById("jpop-list");

const koreaCount = document.getElementById("kpop-count");
const japanCount = document.getElementById("jpop-count");

const updateTime = document.getElementById("update-time");
const refreshButton = document.getElementById("refresh-button");


// =========================================
// 2. K-POP 분류 키워드
// =========================================

const KPOP_KEYWORDS = [
    "bts",
    "blackpink",
    "illit",
    "resc ene",
    "resc ene - topic",
    "res cene",
    "rescene",
    "treasure",
    "riize",
    "jisoo",
    "hybe labels",
    "a2o",
    "aespa",
    "newjeans",
    "ive",
    "le sserafim",
    "stray kids",
    "twice",
    "seventeen",
    "enhypen",
    "txt",
    "nct",
    "exo",
    "red velvet",
    "nmixx",
    "itzy",
    "akmu",
    "day6",
    "babymonster",
    "gidle",
    "(g)i-dle",
    "kiss of life",
    "zerobaseone",
    "boynextdoor",
    "tws",
    "stayc",
    "ateez",
    "monsta x",
    "shinee",
    "super junior",
    "bigbang",
    "exo",
    "iu",
    "taeyeon"
];


// =========================================
// 3. J-POP 분류 키워드
// =========================================

const JPOP_KEYWORDS = [
    "be:first",
    "m!lk",
    "hana official",
    "kenshi yonezu",
    "米津玄師",
    "mrs. green apple",
    "hey! say! jump",
    "key to lit",
    "超特急",
    "ak-69",
    "tatsuya kitani",
    "キタニタツヤ",
    "radwimps",
    "桑田佳祐",
    "buddiis",
    "back number",
    "fujii kaze",
    "藤井風",
    "travis japan",
    "sixtones",
    "jo1",
    "one ok rock",
    "aimyon",
    "あいみょん",
    "one n' only",
    "ado",
    "yoasobi",
    "official髭男dism",
    "髭男",
    "king gnu",
    "imase",
    "優里",
    "yuri",
    "vaundy",
    "atarashii gakko",
    "新しい学校のリーダーズ",
    "snow man",
    "naniwa danshi",
    "number_i",
    "sakanaction",
    "サカナクション",
    "aimer",
    "liSA",
    "eill",
    "yonezu"
];


// =========================================
// 4. 장르 분류
// =========================================

function classifyGenre(track) {

    const channel = (track.artist || "").toLowerCase();
    const title = (track.title || "").toLowerCase();

    const searchText = `${channel} ${title}`;

    // K-POP 확인
    const isKpop = KPOP_KEYWORDS.some(keyword =>
        searchText.includes(keyword.toLowerCase())
    );

    if (isKpop) {
        return "kpop";
    }

    // J-POP 확인
    const isJpop = JPOP_KEYWORDS.some(keyword =>
        searchText.includes(keyword.toLowerCase())
    );

    if (isJpop) {
        return "jpop";
    }

    // 분류되지 않은 음악
    return "other";
}


// =========================================
// 5. 숫자 형식 변환
// =========================================

function formatNumber(number) {

    return Number(number || 0).toLocaleString("ko-KR");

}


// =========================================
// 6. 날짜 형식 변환
// =========================================

function formatDate(dateString) {

    if (!dateString) {
        return "날짜 정보 없음";
    }

    const date = new Date(dateString);

    if (Number.isNaN(date.getTime())) {
        return "날짜 정보 없음";
    }

    return date.toLocaleDateString("ko-KR");

}


// =========================================
// 7. 음악 카드 생성
// =========================================

function createTrackCard(track) {

    // 카드
    const card = document.createElement("article");
    card.className = "track-card";


    // 순위
    const rank = document.createElement("div");
    rank.className = "track-rank";

    rank.textContent = String(
        track.genreRank || track.rank || "-"
    ).padStart(2, "0");


    // 썸네일 링크
    const thumbnailLink = document.createElement("a");

    thumbnailLink.className = "thumbnail-link";
    thumbnailLink.href = track.url || "#";
    thumbnailLink.target = "_blank";
    thumbnailLink.rel = "noopener noreferrer";


    // 썸네일 이미지
    const thumbnail = document.createElement("img");

    thumbnail.className = "track-thumbnail";
    thumbnail.src = track.thumbnail || "";
    thumbnail.alt = track.title || "음악 썸네일";
    thumbnail.loading = "lazy";

    thumbnailLink.appendChild(thumbnail);


    // 음악 정보 영역
    const info = document.createElement("div");
    info.className = "track-info";


    // 제목
    const title = document.createElement("a");

    title.className = "track-title";
    title.href = track.url || "#";
    title.target = "_blank";
    title.rel = "noopener noreferrer";

    title.textContent = track.title || "제목 없음";


    // 채널명
    const channel = document.createElement("div");

    channel.className = "track-channel";
    channel.textContent = track.artist || "채널 정보 없음";


    // 조회수
    const views = document.createElement("div");

    views.className = "track-views";

    views.textContent =
        `조회수 ${formatNumber(track.view_count)}회`;


    // 게시일
    const date = document.createElement("div");

    date.className = "track-date";
    date.textContent = formatDate(track.published_at);


    // 국가 표시
    const region = document.createElement("span");

    region.className = "region-label";


    if (track.source_type === "search") {

        region.textContent = "J-POP SEARCH";

    } else {

        const countryLabel =
            track.sourceCountry === "korea"
                ? "KR CHART"
                : "JP CHART";

        region.textContent =
            `${countryLabel} #${track.original_rank || track.rank}`;

    }


    // 요소 추가
    info.appendChild(title);
    info.appendChild(channel);
    info.appendChild(views);
    info.appendChild(date);

    card.appendChild(rank);
    card.appendChild(thumbnailLink);
    card.appendChild(info);
    card.appendChild(region);

    return card;

}


// =========================================
// 8. 차트 화면 출력
// =========================================

function renderChart(container, tracks, countElement) {

    container.innerHTML = "";

    // 데이터가 없는 경우
    if (!tracks || tracks.length === 0) {

        const message = document.createElement("div");

        message.className = "empty-message";
        message.textContent = "표시할 음악 데이터가 없습니다.";

        container.appendChild(message);

        countElement.textContent = "0 TRACKS";

        return;
    }


    // 음악 카드 출력
    tracks.forEach(track => {

        const card = createTrackCard(track);

        container.appendChild(card);

    });


    // 곡 개수 표시
    countElement.textContent =
        `${tracks.length} TRACKS`;

}


// =========================================
// 9. 국가별 API 데이터 가져오기
// =========================================

async function fetchCountry(country) {

    const response = await fetch(
        `/api/music/${country}`
    );

    const result = await response.json();


    // API 오류 확인
    if (!response.ok || !result.success) {

        throw new Error(
            result.message ||
            result.error ||
            `${country} 데이터 수집 실패`
        );

    }


    // 국가 정보 추가
    return result.data.map(track => ({

        ...track,

        sourceCountry: country

    }));

}


// =========================================
// 10. 중복 동영상 제거
// =========================================

function removeDuplicates(tracks) {

    const seen = new Set();

    return tracks.filter(track => {

        if (!track.video_id) {
            return true;
        }

        if (seen.has(track.video_id)) {
            return false;
        }

        seen.add(track.video_id);

        return true;

    });

}


// =========================================
// 11. 순위 정렬
// =========================================


function sortByRank(a, b) {

    const aIsSearch = a.source_type === "search";
    const bIsSearch = b.source_type === "search";

    // 기존 차트 데이터를 검색 데이터보다 먼저 배치
    if (aIsSearch !== bIsSearch) {

        return aIsSearch ? 1 : -1;

    }

    // 기존 차트 데이터는 원본 순위 기준
    if (!aIsSearch) {

        return (
            (a.original_rank || a.rank || 9999) -
            (b.original_rank || b.rank || 9999)
        );

    }

    // 검색 데이터는 조회수 기준
    return b.view_count - a.view_count;

}


// =========================================
// 12. 전체 음악 데이터 갱신
// =========================================

async function refreshMusic() {

    // 새로고침 버튼 비활성화
    refreshButton.disabled = true;

    refreshButton.textContent = "불러오는 중...";


    // 각 국가의 데이터 수집 결과
    let koreaData = [];
    let japanData = [];

    let koreaSuccess = false;
    let japanSuccess = false;

    const errors = [];


    try {

        // 한국 데이터 수집
        try {

            koreaData = await fetchCountry("korea");

            koreaSuccess = true;

        } catch (error) {

            console.error("한국 API 오류:", error);

            errors.push(`한국: ${error.message}`);

            koreaList.innerHTML = "";

            const message = document.createElement("div");

            message.className = "empty-message";
            message.textContent =
                `한국 데이터를 불러오지 못했습니다: ${error.message}`;

            koreaList.appendChild(message);

            koreaCount.textContent = "ERROR";

        }


        // 일본 데이터 수집
        try {

            japanData = await fetchCountry("japan");

            japanSuccess = true;

        } catch (error) {

            console.error("일본 API 오류:", error);

            errors.push(`일본: ${error.message}`);

            japanList.innerHTML = "";

            const message = document.createElement("div");

            message.className = "empty-message";
            message.textContent =
                `일본 데이터를 불러오지 못했습니다: ${error.message}`;

            japanList.appendChild(message);

            japanCount.textContent = "ERROR";

        }


        // 수집된 데이터 합치기
        const allTracks = [
            ...koreaData,
            ...japanData
        ];

        // 장르별 분류
        let kpopTracks = allTracks.filter(track => {

            return classifyGenre(track) === "kpop";

        });

        let jpopTracks = allTracks.filter(track => {

            return classifyGenre(track) === "jpop";

        });


        // 순위 정렬
        kpopTracks.sort(sortByRank);
        jpopTracks.sort(sortByRank);


        // 중복 제거
        kpopTracks = removeDuplicates(kpopTracks);
        jpopTracks = removeDuplicates(jpopTracks);


        // 장르별 순위 부여 및 최대 30곡 선정
        kpopTracks = kpopTracks
            .slice(0, 30)
            .map((track, index) => ({
                ...track,
                genreRank: index + 1
            }));

        jpopTracks = jpopTracks
            .slice(0, 30)
            .map((track, index) => ({
                ...track,
                genreRank: index + 1
            }));

        // K-POP 출력
        if (koreaSuccess || japanSuccess) {

            renderChart(
                koreaList,
                kpopTracks,
                koreaCount
            );

        }


        // J-POP 출력
        if (koreaSuccess || japanSuccess) {

            renderChart(
                japanList,
                jpopTracks,
                japanCount
            );

        }


        // 미분류 곡 개수
        const otherCount = allTracks.filter(track => {

            return classifyGenre(track) === "other";

        }).length;


        // 조회 상태 표시
        const now = new Date();

        if (errors.length > 0) {

            updateTime.textContent =
                `일부 데이터 조회 실패 | ${errors.join(" / ")}`;

        } else {

            updateTime.textContent =
                `마지막 조회: ${now.toLocaleString("ko-KR")} | 미분류 ${otherCount}개`;

        }


        // 콘솔 확인
        console.log("한국 데이터:", koreaData);
        console.log("일본 데이터:", japanData);
        console.log("K-POP 데이터:", kpopTracks);
        console.log("J-POP 데이터:", jpopTracks);
        console.log("미분류 데이터:", otherCount);


    } catch (error) {

        console.error("전체 차트 오류:", error);

        updateTime.textContent =
            `차트 갱신 오류: ${error.message}`;

    } finally {

        // 새로고침 버튼 복구
        refreshButton.disabled = false;

        refreshButton.textContent = "↻ 새로고침";

    }

}


// =========================================
// 13. TOP 버튼
// =========================================

function initializeTopButton() {

    const topButton = document.getElementById("top-button");

    if (!topButton) {
        return;
    }

    topButton.addEventListener("click", () => {

        const topElement = document.getElementById("top");

        if (topElement) {

            topElement.scrollIntoView({

                behavior: "smooth",

                block: "start"

            });

        }

    });

}


// =========================================
// 14. 새로고침 버튼
// =========================================

function initializeRefreshButton() {

    if (!refreshButton) {
        return;
    }

    refreshButton.addEventListener("click", refreshMusic);

}


// =========================================
// 15. 페이지 초기화
// =========================================

function initializeApp() {

    console.log("MUSIC TREND WATCH 시작");

    // TOP 버튼 이벤트
    initializeTopButton();

    // 새로고침 버튼 이벤트
    initializeRefreshButton();

    // 최초 데이터 수집
    refreshMusic();

}


// DOM 로딩 완료 후 실행
if (document.readyState === "loading") {

    document.addEventListener(
        "DOMContentLoaded",
        initializeApp
    );

} else {

    initializeApp();

}

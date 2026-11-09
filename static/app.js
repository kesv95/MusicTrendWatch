/* =========================================
   MUSIC TREND WATCH
   K-POP / J-POP : country-wide music trends
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
const configuredApiBase = document
    .querySelector('meta[name="music-api-base"]')
    ?.content.trim().replace(/\/+$/, "") || "";
const isLocalServer = ["localhost", "127.0.0.1", "::1"].includes(
    window.location.hostname
);
const isStaticChartMode = !configuredApiBase && !isLocalServer;

function apiUrl(path) {
    if (configuredApiBase) return `${configuredApiBase}${path}`;

    if (isStaticChartMode) {
        throw new Error(
            "정적 차트 모드에서는 Flask API를 호출할 수 없습니다."
        );
    }

    return path;
}

// =========================================
// 2. 갱신 설정
// =========================================

// 페이지가 열려 있는 동안 1시간마다 갱신
const REFRESH_INTERVAL = 15 * 60 * 1000;
const DISPLAY_LIMIT = 30;

let isRefreshing = false;

// =========================================
// 3. 공통 유틸리티
// =========================================

function formatNumber(number) {
    return Number(number || 0).toLocaleString("ko-KR");
}

function formatDate(dateString) {
    if (!dateString) return "날짜 정보 없음";

    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return "날짜 정보 없음";

    return date.toLocaleDateString("ko-KR");
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return dateString || "시간 정보 없음";
    return date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
}

function formatRankChange(track) {
    if (track.rank_status === "NEW") return "NEW";
    if (track.rank_status === "UP") return `↑ ${track.rank_difference}`;
    if (track.rank_status === "DOWN") {
        return `↓ ${Math.abs(track.rank_difference)}`;
    }
    if (track.rank_status === "SAME") return "—";
    return "비교 정보 없음";
}

function formatViewChange(track) {
    if (track.view_status === "NEW") return "첫 수집";
    if (track.view_difference === null ||
        track.view_difference === undefined) {
        return "비교 정보 없음";
    }
    if (track.view_status === "UP") {
        return `↑ ${formatNumber(track.view_difference)}`;
    }
    if (track.view_status === "DOWN") {
        return `↓ ${formatNumber(Math.abs(track.view_difference))}`;
    }
    if (track.view_status === "SAME") return "—";
    return "비교 정보 없음";
}

// =========================================
// 4. 국가별 차트 구분
// =========================================

// 이 프로젝트의 K-POP/J-POP은 아이돌 장르만 뜻하지 않는다.
// 한국/일본을 대상으로 수집한 대중음악 후보 묶음이다.
function getDisplayChart(track) {
    return track.sourceCountry === "korea" ? "kpop" : "jpop";
}

// =========================================
// 5. 음악 카드 생성
// =========================================

function createTrackCard(track) {
    const card = document.createElement("article");
    card.className = "track-card";

    const rank = document.createElement("div");
    rank.className = "track-rank";
    rank.textContent = String(track.genreRank || "-").padStart(2, "0");

    const thumbnailLink = document.createElement("a");
    thumbnailLink.className = "thumbnail-link";
    thumbnailLink.href = track.url || "#";
    thumbnailLink.target = "_blank";
    thumbnailLink.rel = "noopener noreferrer";

    const thumbnail = document.createElement("img");
    thumbnail.className = "track-thumbnail";
    thumbnail.src = track.thumbnail || "";
    thumbnail.alt = track.title || "음악 썸네일";
    thumbnail.loading = "lazy";
    thumbnailLink.appendChild(thumbnail);

    const info = document.createElement("div");
    info.className = "track-info";
    info.style.minWidth = "0";

    const title = document.createElement("a");
    title.className = "track-title";
    title.href = track.url || "#";
    title.target = "_blank";
    title.rel = "noopener noreferrer";
    title.textContent = track.title || "제목 없음";
    title.title = track.title || "제목 없음";
    title.style.display = "block";
    title.style.maxWidth = "100%";
    title.style.overflow = "hidden";
    title.style.whiteSpace = "nowrap";
    title.style.textOverflow = "ellipsis";
    title.style.paddingRight = "85px";
    title.style.boxSizing = "border-box";

    const channel = document.createElement("div");
    channel.className = "track-channel";
    channel.textContent = track.channel || track.artist || "채널 정보 없음";

    const views = document.createElement("div");
    views.className = "track-views";
    views.textContent = `조회수 ${formatNumber(track.view_count)}회`;

    const date = document.createElement("div");
    date.className = "track-date";
    date.textContent = formatDate(track.published_at);

    const trend = document.createElement("div");
    trend.className = "track-trend";

    const rankTrend = document.createElement("span");
    rankTrend.className = "rank-trend";
    rankTrend.textContent = `순위 ${formatRankChange(track)}`;

    const viewTrend = document.createElement("span");
    viewTrend.className = "view-trend";
    viewTrend.textContent = `조회수 ${formatViewChange(track)}`;

    if (track.rank_status === "UP") {
        rankTrend.classList.add("trend-up");
    } else if (track.rank_status === "DOWN") {
        rankTrend.classList.add("trend-down");
    }

    if (track.view_status === "UP") {
        viewTrend.classList.add("trend-up");
    } else if (track.view_status === "DOWN") {
        viewTrend.classList.add("trend-down");
    }

    trend.appendChild(rankTrend);
    trend.appendChild(viewTrend);

    const region = document.createElement("span");
    region.className = "region-label";

    const countryLabel = track.sourceCountry === "korea" ? "KR" : "JP";
    if (track.source_type === "search") {
        region.textContent = `${countryLabel} SEARCH`;
    } else {
        region.textContent =
            `${countryLabel} CHART #${track.original_rank || track.rank || "-"}`;
    }

    info.appendChild(title);
    info.appendChild(channel);
    info.appendChild(views);
    info.appendChild(date);
    info.appendChild(trend);

    card.appendChild(rank);
    card.appendChild(thumbnailLink);
    card.appendChild(info);
    card.appendChild(region);

    return card;
}

// =========================================
// 6. 차트 화면 출력
// =========================================

function renderChart(container, tracks, countElement) {
    container.innerHTML = "";

    if (!tracks || tracks.length === 0) {
        const message = document.createElement("div");
        message.className = "empty-message";
        message.textContent = "표시할 음악 데이터가 없습니다.";
        container.appendChild(message);
        countElement.textContent = "0 TRACKS";
        return;
    }

    tracks.forEach(track => {
        container.appendChild(createTrackCard(track));
    });

    countElement.textContent = `${tracks.length} TRACKS`;
}

// =========================================
// 7. 국가별 API 데이터 가져오기
// =========================================

async function fetchCountry(country) {
    if (isStaticChartMode) {
        const response = await fetch("static/chart-data.json", {
            cache: "no-store"
        });
        if (!response.ok) {
            throw new Error(`최신 차트 파일을 불러오지 못했습니다 (${response.status})`);
        }

        const chartData = await response.json();
        const result = chartData.countries?.[country];
        if (!result) throw new Error("해당 국가의 차트 데이터가 없습니다.");

        return {
            tracks: (result.data || []).map(track => ({
                ...track,
                sourceCountry: country
            })),
            warning: result.error
                ? `${result.error.type}: ${result.error.message} · ` +
                  `마지막 정상 수집 ${result.updated_at ? formatDateTime(result.updated_at) : "기록 없음"}`
                : chartData.source?.includes("initial snapshot")
                    ? "초기 스냅샷입니다. Actions 최초 수집 전에는 실제 곡 제목이 표시되지 않습니다."
                    : null,
            chartCount: result.chart_count || 0,
            searchCount: 0,
            updatedAt: chartData.updated_at || result.updated_at || null,
            isInitialSnapshot: chartData.source?.includes("initial snapshot") || false
        };
    }

    const response = await fetch(apiUrl(`/api/music/${country}`));

    let result;
    try {
        result = await response.json();
    } catch {
        throw new Error(`응답 JSON 변환 실패 (${response.status})`);
    }

    if (!response.ok || !result.success) {
        throw new Error(
            result.message ||
            result.error ||
            `${country} 데이터 수집 실패`
        );
    }

    const tracks = (result.data || []).map(track => ({
        ...track,
        sourceCountry: country
    }));

    return {
        tracks,
        warning: result.search_warning || null,
        chartCount: result.chart_count || 0,
        searchCount: result.search_count || 0
    };
}

// =========================================
// 8. 중복 제거 및 통합 정렬
// =========================================

function mergeAndSortTracks(tracks) {
    const chartTracks = tracks
        .filter(track => track.source_type === "chart")
        .sort((a, b) =>
            (a.original_rank || a.rank || 9999) -
            (b.original_rank || b.rank || 9999)
        );

    const searchTracks = tracks
        .filter(track => track.source_type === "search")
        .sort((a, b) =>
            Number(b.view_count || 0) - Number(a.view_count || 0)
        );

    // TOP 30에 기존 국가 인기 차트 20개와 검색 후보 최대 10개를 반영한다.
    // 중복 등으로 검색 후보가 부족하면 남은 차트 데이터로 채운다.
    const selected = [];
    const seen = new Set();

    function addUnique(list, limit) {
        let added = 0;

        for (const track of list) {
            if (!track.video_id || seen.has(track.video_id)) continue;

            seen.add(track.video_id);
            selected.push(track);
            added += 1;

            if (added >= limit || selected.length >= DISPLAY_LIMIT) break;
        }
    }

    addUnique(chartTracks, 20);
    addUnique(searchTracks, DISPLAY_LIMIT - selected.length);

    // 검색 결과가 부족해 TOP 30이 채워지지 않으면 남은 차트 데이터로 보충
    if (selected.length < DISPLAY_LIMIT) {
        addUnique(chartTracks, DISPLAY_LIMIT - selected.length);
    }

    return selected.slice(0, DISPLAY_LIMIT).map((track, index) => ({
        ...track,
        genreRank: index + 1
    }));
}

// =========================================
// 9. 순위 및 조회수 변동 기록
// =========================================

async function saveChartSnapshot(chart, tracks) {
    const response = await fetch(apiUrl(`/api/music/snapshot/${chart}_v2`), {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            tracks: tracks.map(track => ({
                video_id: track.video_id,
                rank: track.genreRank,
                view_count: track.view_count
            }))
        })
    });

    let result;
    try {
        result = await response.json();
    } catch {
        throw new Error(`Snapshot 응답 변환 실패 (${response.status})`);
    }

    if (!response.ok || !result.success) {
        throw new Error(
            result.message || `Snapshot 저장 실패: ${response.status}`
        );
    }

    return result.changes || {};
}

function attachChanges(tracks, changes) {
    return tracks.map(track => ({
        ...track,
        ...(changes[track.video_id] || {})
    }));
}

// =========================================
// 10. 오류 메시지 출력
// =========================================

function showCountryError(container, countElement, country, error) {
    container.innerHTML = "";

    const message = document.createElement("div");
    message.className = "empty-message";
    message.textContent =
        `${country} 데이터를 불러오지 못했습니다: ${error.message}`;

    container.appendChild(message);
    countElement.textContent = "ERROR";
}

// =========================================
// 11. 전체 음악 데이터 갱신
// =========================================

async function refreshMusic() {
    if (isRefreshing) return;

    isRefreshing = true;

    if (refreshButton) {
        refreshButton.disabled = true;
        refreshButton.textContent = "불러오는 중...";
    }

    const errors = [];
    const warnings = [];

    try {
        // 한국과 일본 데이터를 병렬로 수집
        const [koreaResult, japanResult] = await Promise.allSettled([
            fetchCountry("korea"),
            fetchCountry("japan")
        ]);

        let kpopTracks = [];
        let jpopTracks = [];
        let koreaSuccess = false;
        let japanSuccess = false;

        if (koreaResult.status === "fulfilled") {
            koreaSuccess = true;
            const result = koreaResult.value;

            // 국가별 대중음악 후보를 K-POP 차트에 통합
            kpopTracks = mergeAndSortTracks(result.tracks);

            if (result.warning) {
                warnings.push(`${isStaticChartMode ? "한국 차트 수집" : "한국 검색"}: ${result.warning}`);
            }
        } else {
            errors.push(`한국: ${koreaResult.reason.message}`);
            showCountryError(
                koreaList, koreaCount, "한국",
                koreaResult.reason
            );
        }

        if (japanResult.status === "fulfilled") {
            japanSuccess = true;
            const result = japanResult.value;

            // 국가별 대중음악 후보를 J-POP 차트에 통합
            jpopTracks = mergeAndSortTracks(result.tracks);

            if (result.warning) {
                warnings.push(`${isStaticChartMode ? "일본 차트 수집" : "일본 검색"}: ${result.warning}`);
            }
        } else {
            errors.push(`일본: ${japanResult.reason.message}`);
            showCountryError(
                japanList, japanCount, "일본",
                japanResult.reason
            );
        }

        // 순위 기록은 국가별로 독립 저장
        const snapshotTasks = [];

        if (!isStaticChartMode && koreaSuccess) {
            snapshotTasks.push(
                saveChartSnapshot("kpop", kpopTracks)
                    .then(changes => {
                        kpopTracks = attachChanges(kpopTracks, changes);
                    })
                    .catch(error => {
                        console.error("K-POP 순위 기록 오류:", error);
                        warnings.push(`K-POP 순위 기록: ${error.message}`);
                    })
            );
        }

        if (!isStaticChartMode && japanSuccess) {
            snapshotTasks.push(
                saveChartSnapshot("jpop", jpopTracks)
                    .then(changes => {
                        jpopTracks = attachChanges(jpopTracks, changes);
                    })
                    .catch(error => {
                        console.error("J-POP 순위 기록 오류:", error);
                        warnings.push(`J-POP 순위 기록: ${error.message}`);
                    })
            );
        }

        await Promise.all(snapshotTasks);

        if (koreaSuccess) {
            renderChart(koreaList, kpopTracks, koreaCount);
        }

        if (japanSuccess) {
            renderChart(japanList, jpopTracks, japanCount);
        }

        const now = new Date();
        const staticUpdate = isStaticChartMode
            ? koreaResult.status === "fulfilled"
                ? koreaResult.value.updatedAt
                : japanResult.status === "fulfilled"
                    ? japanResult.value.updatedAt
                    : null
            : null;
        const isInitialSnapshot = isStaticChartMode && (
            (koreaResult.status === "fulfilled" && koreaResult.value.isInitialSnapshot) ||
            (japanResult.status === "fulfilled" && japanResult.value.isInitialSnapshot)
        );
        const statusParts = [
            ...(isStaticChartMode
                ? [isInitialSnapshot
                    ? "초기 스냅샷 · GitHub Actions 최초 수집 전"
                    : `마지막 차트 변경 반영: ${staticUpdate ? formatDateTime(staticUpdate) : "기록 없음"}`]
                : [`마지막 조회: ${now.toLocaleString("ko-KR")}`]),
            `K-POP ${koreaSuccess ? kpopTracks.length + "곡" : "수집 실패"}`,
            `J-POP ${japanSuccess ? jpopTracks.length + "곡" : "수집 실패"}`
        ];

        if (errors.length) statusParts.push(errors.join(" / "));
        if (warnings.length) statusParts.push(warnings.join(" / "));

        updateTime.textContent = statusParts.join(" | ");

        console.log("한국 음악 후보:", kpopTracks);
        console.log("일본 음악 후보:", jpopTracks);
        console.log("수집 오류:", errors);
        console.log("수집 경고:", warnings);

    } catch (error) {
        console.error("전체 차트 오류:", error);
        updateTime.textContent = `차트 갱신 오류: ${error.message}`;
    } finally {
        isRefreshing = false;

        if (refreshButton) {
            refreshButton.disabled = false;
            refreshButton.textContent = "↻ 새로고침";
        }
    }
}

// =========================================
// 12. TOP 버튼
// =========================================

function initializeTopButton() {
    const topButton = document.getElementById("top-button");
    if (!topButton) return;

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
// 13. 새로고침 버튼
// =========================================

function initializeRefreshButton() {
    if (!refreshButton) return;
    refreshButton.addEventListener("click", refreshMusic);
}

// =========================================
// 14. 자동 갱신
// =========================================

function initializeAutoRefresh() {
    window.setInterval(refreshMusic, REFRESH_INTERVAL);
}

// =========================================
// 15. 페이지 초기화
// =========================================

function initializeApp() {
    console.log("MUSIC TREND WATCH 시작");

    initializeTopButton();
    initializeRefreshButton();
    initializeAutoRefresh();

    refreshMusic();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeApp);
} else {
    initializeApp();
}

"""Mock-only tests: no test here may reach a real LLM or YouTube endpoint."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from scripts import daily_briefing
from scripts.daily_briefing import build_rule_briefing, create_briefing, run, snapshot_tracks

ALL_KEYS = {f"{role.upper()}_API_KEY": f"mock-{role}-key" for role in ("analyst", "reviewer", "writer")}
# 2026-11-24 00:05 KST -> closes KST day 2026-11-23
CAPTURED = datetime(2026, 11, 23, 15, 5, tzinfo=timezone.utc)


def response(text="완성된 한국어 브리핑"):
    result = Mock()
    result.raise_for_status.return_value = None
    result.json.return_value = {"choices": [{"message": {"content": text}}]}
    return result


def chart(korea, japan=()):
    return {
        "updated_at": "2026-11-23T14:55:00Z",
        "countries": {"korea": {"data": list(korea)}, "japan": {"data": list(japan)}},
    }


def track(video_id, rank, views, title=None):
    return {"video_id": video_id, "title": title or f"곡 {video_id}", "artist": "가수", "rank": rank, "view_count": views}


def make_root(directory, chart_data):
    root = Path(directory)
    (root / "static").mkdir()
    (root / "static" / "chart-data.json").write_text(json.dumps(chart_data), encoding="utf-8")
    return root


class GuardRealNetwork(unittest.TestCase):
    """Fail loudly if any code path falls through to the real requests.post."""

    def setUp(self):
        guard = patch.object(requests, "post", side_effect=AssertionError("real HTTP call attempted"))
        guard.start()
        self.addCleanup(guard.stop)
        # create_briefing/run bind requests.post as a default argument at import time.
        for fn in (daily_briefing.create_briefing, daily_briefing.run):
            original = fn.__kwdefaults__["post"]
            fn.__kwdefaults__["post"] = requests.post
            self.addCleanup(fn.__kwdefaults__.__setitem__, "post", original)


class SnapshotTests(GuardRealNetwork):
    def test_day_over_day_rank_and_view_changes(self):
        current = chart([track("a", 2, 120), track("b", 1, 10)])
        previous = {"countries": {"korea": [{"video_id": "a", "rank": 5, "view_count": 100}]}}
        tracks = snapshot_tracks(current, previous)["korea"]
        by_id = {t["video_id"]: t for t in tracks}
        self.assertEqual([t["video_id"] for t in tracks], ["b", "a"])  # sorted by rank
        self.assertEqual((by_id["a"]["rank_change"], by_id["a"]["view_change"]), (3, 20))
        self.assertEqual(by_id["a"]["previous_rank"], 5)
        self.assertTrue(by_id["b"]["is_new"])
        self.assertIsNone(by_id["b"]["rank_change"])

    def test_first_snapshot_marks_nothing_new(self):
        tracks = snapshot_tracks(chart([track("a", 1, 10)]), None)["korea"]
        self.assertFalse(tracks[0]["is_new"])
        self.assertIsNone(tracks[0]["rank_change"])

    def test_rank_drop_is_negative(self):
        previous = {"countries": {"korea": [{"video_id": "a", "rank": 1, "view_count": 50}]}}
        t = snapshot_tracks(chart([track("a", 4, 40)]), previous)["korea"][0]
        self.assertEqual((t["rank_change"], t["view_change"]), (-3, -10))


class RuleBriefingTests(GuardRealNetwork):
    def test_rules_fallback_without_keys(self):
        countries = snapshot_tracks(chart([track("a", 1, 10)]), None)
        text, mode = create_briefing("2026-11-23", countries, env={})
        self.assertEqual(mode, "rules")
        self.assertIn("전일 비교 스냅샷이 없어", text)

    def test_empty_env_never_reads_process_environment(self):
        # Regression: `env or os.environ` treated {} as "use real keys".
        with patch.dict(os.environ, ALL_KEYS):
            text, mode = create_briefing("2026-11-23", {"korea": [], "japan": []}, compared_to="2026-11-22", env={})
        self.assertEqual(mode, "rules")

    def test_rule_briefing_reports_movers_and_views(self):
        previous = {"countries": {
            "korea": [
                {"video_id": "a", "rank": 1, "view_count": 1000},
                {"video_id": "b", "rank": 9, "view_count": 100},
            ],
            "japan": [{"video_id": "j", "rank": 1, "view_count": 5}],
        }}
        current = chart(
            [track("a", 3, 1100, "하강곡"), track("b", 1, 2100, "급상승곡"), track("n", 2, 50, "신곡")],
            [track("j", 1, 5, "제이곡")],
        )
        text = build_rule_briefing("2026-11-23", snapshot_tracks(current, previous), "2026-11-22")
        self.assertIn("2026-11-22 마감과 비교", text)
        self.assertIn("최대 상승 「급상승곡」 8계단↑ → 1위", text)
        self.assertIn("최대 하락 「하강곡」 2계단↓ → 3위", text)
        self.assertIn("조회수 최대 증가 「급상승곡」 +2,000회", text)
        self.assertIn("신규 진입 1곡", text)
        self.assertIn("K-POP: 1위 「급상승곡」(9위에서 상승).", text)
        self.assertIn("J-POP: 1위 「제이곡」(자리 유지).", text)


class LlmChainTests(GuardRealNetwork):
    def countries(self):
        previous = {"countries": {"korea": [{"video_id": "a", "rank": 3, "view_count": 1}]}}
        return snapshot_tracks(chart([track("a", 1, 999, "원자료곡")]), previous)

    def test_llm_roles_are_called_in_order_with_context(self):
        calls = []

        def mocked_post(url, **kwargs):
            calls.append(kwargs["json"])
            return response(f"{len(calls)}단계 결과")

        text, mode = create_briefing("2026-11-23", self.countries(), compared_to="2026-11-22", env=ALL_KEYS, post=mocked_post)
        self.assertEqual((mode, text), ("llm", "3단계 결과"))
        self.assertEqual([c["messages"][0]["content"].split("]")[0] for c in calls], ["[analyst", "[reviewer", "[writer"])
        reviewer_prompt, writer_prompt = calls[1]["messages"][1]["content"], calls[2]["messages"][1]["content"]
        self.assertIn("1단계 결과", reviewer_prompt)          # reviewer sees the analysis
        self.assertIn("2단계 결과", writer_prompt)            # writer sees the review
        self.assertIn("원자료곡", writer_prompt)              # ...and the raw data to check numbers

    def test_role_specific_provider_and_model(self):
        env = dict(ALL_KEYS, REVIEWER_API_URL="https://reviewer.example/v1/chat/completions", REVIEWER_MODEL="review-model")
        post = Mock(return_value=response())
        create_briefing("2026-11-23", self.countries(), compared_to="2026-11-22", env=env, post=post)
        (a_url,), a_kw = post.call_args_list[0]
        (r_url,), r_kw = post.call_args_list[1]
        self.assertEqual(a_url, daily_briefing.DEFAULT_API_URL)
        self.assertEqual(r_url, "https://reviewer.example/v1/chat/completions")
        self.assertEqual(r_kw["json"]["model"], "review-model")
        self.assertEqual(r_kw["headers"]["Authorization"], "Bearer mock-reviewer-key")

    def test_missing_one_role_key_uses_rules_without_calls(self):
        env = {k: v for k, v in ALL_KEYS.items() if not k.startswith("WRITER")}
        post = Mock()
        _, mode = create_briefing("2026-11-23", self.countries(), compared_to="2026-11-22", env=env, post=post)
        self.assertEqual(mode, "rules")
        post.assert_not_called()

    def test_llm_error_returns_rules_briefing(self):
        for failure in (requests.ConnectionError("down"), RuntimeError("boom")):
            post = Mock(side_effect=failure)
            text, mode = create_briefing("2026-11-23", self.countries(), compared_to="2026-11-22", env=ALL_KEYS, post=post)
            self.assertTrue(mode.startswith("rules (LLM chain failed"), mode)
            self.assertIn("2026-11-23", text)

    def test_mid_chain_failure_and_malformed_reply_fall_back(self):
        bad = Mock(); bad.raise_for_status.return_value = None; bad.json.return_value = {"choices": []}
        empty = response("   ")
        for second in (bad, empty):
            post = Mock(side_effect=[response("분석"), second])
            _, mode = create_briefing("2026-11-23", self.countries(), compared_to="2026-11-22", env=ALL_KEYS, post=post)
            self.assertTrue(mode.startswith("rules (LLM chain failed"), mode)

    def test_no_llm_call_without_comparison_baseline(self):
        post = Mock()
        _, mode = create_briefing("2026-11-23", self.countries(), compared_to=None, env=ALL_KEYS, post=post)
        self.assertEqual(mode, "rules")
        post.assert_not_called()


class RunTests(GuardRealNetwork):
    def test_run_writes_kst_close_snapshot_and_brief(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory, chart([track("a", 1, 10)]))
            snapshot, brief = run(root, now=CAPTURED, env={})
            self.assertEqual(snapshot.name, "2026-11-23.json")
            saved = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual((saved["date"], saved["compared_to"]), ("2026-11-23", None))
            payload = json.loads(brief.read_text(encoding="utf-8"))
            self.assertEqual((payload["date"], payload["mode"]), ("2026-11-23", "rules"))

    def test_run_compares_with_previous_day_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory, chart([track("a", 1, 150)]))
            snaps = root / "static" / "daily-snapshots"
            snaps.mkdir()
            (snaps / "2026-11-22.json").write_text(json.dumps({"countries": {"korea": [{"video_id": "a", "rank": 4, "view_count": 100}]}}), encoding="utf-8")
            snapshot, brief = run(root, now=CAPTURED, env={})
            t = json.loads(snapshot.read_text(encoding="utf-8"))["countries"]["korea"][0]
            self.assertEqual((t["rank_change"], t["view_change"]), (3, 50))
            self.assertEqual(json.loads(brief.read_text(encoding="utf-8"))["compared_to"], "2026-11-22")

    def test_run_skipped_day_uses_latest_earlier_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory, chart([track("a", 1, 150)]))
            snaps = root / "static" / "daily-snapshots"
            snaps.mkdir()
            for day in ("2026-11-19", "2026-11-21"):
                (snaps / f"{day}.json").write_text(json.dumps({"countries": {"korea": [{"video_id": "a", "rank": 2, "view_count": 1}]}}), encoding="utf-8")
            (snaps / "notes.json").write_text("{}", encoding="utf-8")  # ignored: not a date
            snapshot, _ = run(root, now=CAPTURED, env={})
            self.assertEqual(json.loads(snapshot.read_text(encoding="utf-8"))["compared_to"], "2026-11-21")

    def test_rerun_keeps_closing_snapshot_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory, chart([track("a", 1, 10)]))
            snapshot, _ = run(root, now=CAPTURED, env={})
            original = snapshot.read_text(encoding="utf-8")
            # Chart moves on during the day; a manual re-run must not replace yesterday's close.
            (root / "static" / "chart-data.json").write_text(json.dumps(chart([track("z", 1, 999)])), encoding="utf-8")
            run(root, now=CAPTURED.replace(hour=20), env={})
            self.assertEqual(snapshot.read_text(encoding="utf-8"), original)
            run(root, now=CAPTURED, env={}, force=True)
            self.assertIn('"z"', snapshot.read_text(encoding="utf-8"))

    def test_run_with_llm_chain_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory, chart([track("a", 1, 150)]))
            snaps = root / "static" / "daily-snapshots"
            snaps.mkdir()
            (snaps / "2026-11-22.json").write_text(json.dumps({"countries": {"korea": [{"video_id": "a", "rank": 2, "view_count": 100}]}}), encoding="utf-8")
            post = Mock(side_effect=[response("분석"), response("검토"), response("최종 브리핑")])
            _, brief = run(root, now=CAPTURED, env=ALL_KEYS, post=post)
            payload = json.loads(brief.read_text(encoding="utf-8"))
            self.assertEqual((payload["mode"], payload["text"]), ("llm", "최종 브리핑"))
            self.assertEqual(post.call_count, 3)

    def test_naive_datetime_is_treated_as_kst(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory, chart([]))
            snapshot, _ = run(root, now=datetime(2026, 11, 24, 0, 5), env={})
            self.assertEqual(snapshot.name, "2026-11-23.json")


if __name__ == "__main__":
    unittest.main()

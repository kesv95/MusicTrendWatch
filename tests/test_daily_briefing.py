import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from scripts.daily_briefing import create_briefing, run, snapshot_tracks


def response(text="완성된 한국어 브리핑"):
    result = Mock()
    result.raise_for_status.return_value = None
    result.json.return_value = {"choices": [{"message": {"content": text}}]}
    return result


class DailyBriefingTests(unittest.TestCase):
    def test_day_over_day_rank_and_view_changes(self):
        chart = {"countries": {"korea": {"data": [
            {"video_id": "a", "title": "곡 A", "rank": 2, "view_count": 120},
            {"video_id": "b", "title": "곡 B", "rank": 1, "view_count": 10},
        ]}}}
        previous = {"countries": {"korea": [
            {"video_id": "a", "rank": 5, "view_count": 100},
        ]}}
        tracks = snapshot_tracks(chart, previous)["korea"]
        self.assertEqual((tracks[0]["rank_change"], tracks[0]["view_change"]), (3, 20))
        self.assertTrue(tracks[1]["is_new"])
        self.assertIsNone(tracks[1]["rank_change"])

    def test_rules_fallback_without_keys(self):
        text, mode = create_briefing("2026-11-23", {"korea": [], "japan": []}, env={}, post=Mock())
        self.assertEqual(mode, "rules")
        self.assertIn("전일 비교 스냅샷", text)

    def test_llm_roles_are_called_in_order(self):
        calls = []

        def mocked_post(url, **kwargs):
            calls.append((url, kwargs["json"]["messages"][0]["content"]))
            return response(f"{len(calls)} 단계 결과")

        env = {f"{role.upper()}_API_KEY": "mock-key" for role in ("analyst", "reviewer", "writer")}
        text, mode = create_briefing("2026-11-23", {"korea": [], "japan": []}, env=env, post=mocked_post)
        self.assertEqual(mode, "llm")
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(
            role in system_prompt
            for role, (_, system_prompt) in zip(("analyst", "reviewer", "writer"), calls)
        ))
        self.assertEqual(text, "3 단계 결과")

    def test_llm_error_returns_rules_briefing(self):
        env = {f"{role.upper()}_API_KEY": "mock-key" for role in ("analyst", "reviewer", "writer")}
        text, mode = create_briefing("2026-11-23", {"korea": [], "japan": []}, env=env, post=Mock(side_effect=RuntimeError("mock failure")))
        self.assertTrue(mode.startswith("rules (LLM chain failed"))
        self.assertIn("2026-11-23", text)

    def test_run_writes_kst_close_snapshot_and_brief(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "static").mkdir()
            (root / "static" / "chart-data.json").write_text(json.dumps({"updated_at": "2026-11-23T14:55:00Z", "countries": {"korea": {"data": []}, "japan": {"data": []}}}), encoding="utf-8")
            captured = datetime(2026, 11, 23, 15, 5, tzinfo=timezone.utc)  # 2026-11-24 00:05 KST
            snapshot, brief = run(root, now=captured, env={}, post=Mock())
            self.assertEqual(snapshot.name, "2026-11-23.json")
            self.assertTrue(snapshot.exists())
            self.assertEqual(json.loads(brief.read_text(encoding="utf-8"))["date"], "2026-11-23")


if __name__ == "__main__":
    unittest.main()

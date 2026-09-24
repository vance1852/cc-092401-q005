from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

from robot_trials.api import JsonApplication
from robot_trials.service import TrialService


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.app = JsonApplication(TrialService(self.connection))

    def tearDown(self) -> None:
        self.connection.close()

    def test_health(self) -> None:
        response = self.app.handle("GET", "/health")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["status"], "ok")

    def test_json_error_shape(self) -> None:
        response = self.app.handle("POST", "/users", body=b"not-json")
        self.assertEqual(response.status, 422)
        self.assertEqual(response.body["error"]["code"], "validation_failed")

    def test_user_route(self) -> None:
        payload = json.dumps({"user_id": "u1", "display_name": "操作员", "role": "operator"}).encode()
        response = self.app.handle("POST", "/users", body=payload)
        self.assertEqual(response.status, 201)
        self.assertEqual(response.body["role"], "operator")

    def test_negative_count_error_points_to_metric_path(self) -> None:
        service = self.app.service
        service.create_user("operator", "操作员", "operator")
        service.create_user("stat", "统计负责人", "statistician")
        service.register_robot("operator", "robot-a", "A 型", "厂商")
        service.register_build("operator", "build-a", "robot-a", "1.0", "b" * 64)
        protocol = json.loads(
            (Path(__file__).resolve().parents[1] / "fixtures" / "demo_protocol.json").read_text(encoding="utf-8")
        )
        service.publish_protocol("stat", protocol)
        service.create_batch("operator", "batch-a", "demo-delivery-v1", 1, "build-a")
        service.start_batch("operator", "batch-a", 1)
        observation = {
            "source_batch": "hall-a-20260921",
            "source_row": "001",
            "robot_id": "robot-a",
            "protocol_id": "demo-delivery-v1",
            "protocol_version": 1,
            "stratum_key": "clear-aisle",
            "observed_at": "2026-09-21T09:00:00+08:00",
            "metrics": {"completed": 1, "completion_seconds": "42.8", "interventions": -1},
            "excluded_reason": None,
        }
        response = self.app.handle(
            "POST",
            "/batches/batch-a/observations",
            headers={"X-Actor-Id": "operator", "Idempotency-Key": "key-negative"},
            body=json.dumps({"observations": [observation]}).encode(),
        )
        self.assertEqual(response.status, 422)
        self.assertEqual(response.body["error"]["code"], "validation_failed")
        self.assertIn("observation.metrics.interventions", response.body["error"]["message"])
        stored = self.connection.execute("SELECT count(*) FROM observations").fetchone()[0]
        self.assertEqual(stored, 0)


if __name__ == "__main__":
    unittest.main()

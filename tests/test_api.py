from __future__ import annotations

import json
import sqlite3
import unittest

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

    def test_negative_count_import_has_stable_error_shape(self) -> None:
        self._prepare_running_batch()
        row = {
            "source_batch": "hall-a",
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
            headers={"X-Actor-Id": "operator", "Idempotency-Key": "key-1"},
            body=json.dumps({"observations": [row]}).encode(),
        )
        self.assertEqual(response.status, 422)
        error = response.body["error"]
        self.assertEqual(error["code"], "validation_failed")
        self.assertIn("observation.metrics.interventions", error["message"])

    def _prepare_running_batch(self) -> None:
        self.app.handle(
            "POST", "/users",
            body=json.dumps({"user_id": "operator", "display_name": "操作员", "role": "operator"}).encode(),
        )
        self.app.handle(
            "POST", "/users",
            body=json.dumps({"user_id": "stat", "display_name": "统计", "role": "statistician"}).encode(),
        )
        self.app.handle(
            "POST", "/robots", headers={"X-Actor-Id": "operator"},
            body=json.dumps({"robot_id": "robot-a", "model_name": "A 型", "vendor": "厂商"}).encode(),
        )
        self.app.handle(
            "POST", "/builds", headers={"X-Actor-Id": "operator"},
            body=json.dumps(
                {"build_id": "build-a", "robot_id": "robot-a", "version": "1.0", "content_sha256": "b" * 64}
            ).encode(),
        )
        protocol = {
            "protocol_id": "demo-delivery-v1",
            "version": 1,
            "title": "室内递送基础重复试验",
            "task_family": "indoor-delivery",
            "seed": 20260921,
            "bootstrap_samples": 500,
            "strata": [
                {"key": "clear-aisle", "label": "无遮挡", "required_trials": 1},
                {"key": "cross-traffic", "label": "横向人流", "required_trials": 1},
            ],
            "metrics": [
                {"key": "completed", "label": "是否完成", "kind": "binary", "unit": None, "direction": "higher"},
                {"key": "completion_seconds", "label": "用时", "kind": "continuous", "unit": "s", "direction": "lower"},
                {"key": "interventions", "label": "干预次数", "kind": "count", "unit": "count", "direction": "lower"},
            ],
            "stratum_weights": {"clear-aisle": "0.5", "cross-traffic": "0.5"},
            "admission_rules": [
                {"metric": "completed", "operator": "gte", "threshold": "0.1"},
            ],
        }
        published = self.app.handle(
            "POST", "/protocols", headers={"X-Actor-Id": "stat"},
            body=json.dumps(protocol).encode(),
        )
        self.assertEqual(published.status, 201)
        self.app.handle(
            "POST", "/batches", headers={"X-Actor-Id": "operator"},
            body=json.dumps(
                {"batch_id": "batch-a", "protocol_id": "demo-delivery-v1",
                 "protocol_version": 1, "build_id": "build-a"}
            ).encode(),
        )
        started = self.app.handle(
            "POST", "/batches/batch-a/start", headers={"X-Actor-Id": "operator"},
            body=json.dumps({"expected_revision": 1}).encode(),
        )
        self.assertEqual(started.status, 200)


if __name__ == "__main__":
    unittest.main()

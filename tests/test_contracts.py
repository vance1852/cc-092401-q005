from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from robot_trials.contracts import Observation, Protocol, ValidationError
from robot_trials.jsonio import load_json


ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_protocol = load_json(ROOT / "fixtures" / "demo_protocol.json")
        self.protocol = Protocol.from_dict(self.raw_protocol)

    def test_protocol_builds_indexes(self) -> None:
        self.assertEqual(self.protocol.version, 1)
        self.assertEqual(self.protocol.stratum_keys, {"clear-aisle", "cross-traffic"})
        self.assertEqual(set(self.protocol.metric_map), {"completed", "completion_seconds", "interventions"})

    def test_protocol_rejects_duplicate_metric(self) -> None:
        raw = deepcopy(self.raw_protocol)
        raw["metrics"].append(deepcopy(raw["metrics"][0]))
        with self.assertRaisesRegex(ValidationError, "不能重复"):
            Protocol.from_dict(raw)

    def test_observation_rejects_unknown_stratum(self) -> None:
        raw = {
            "source_batch": "batch",
            "source_row": "1",
            "robot_id": "r1",
            "protocol_id": self.protocol.protocol_id,
            "protocol_version": self.protocol.version,
            "stratum_key": "unknown",
            "observed_at": "2026-09-21T10:00:00+08:00",
            "metrics": {"completed": 1, "completion_seconds": 4, "interventions": 0},
            "excluded_reason": None,
        }
        with self.assertRaisesRegex(ValidationError, "未在协议中声明"):
            Observation.from_dict(raw, self.protocol)

    def test_binary_metric_is_strict(self) -> None:
        raw = {
            "source_batch": "batch",
            "source_row": "1",
            "robot_id": "r1",
            "protocol_id": self.protocol.protocol_id,
            "protocol_version": self.protocol.version,
            "stratum_key": "clear-aisle",
            "observed_at": "2026-09-21T10:00:00+08:00",
            "metrics": {"completed": 2, "completion_seconds": 4, "interventions": 0},
            "excluded_reason": None,
        }
        with self.assertRaisesRegex(ValidationError, "必须是 0 或 1"):
            Observation.from_dict(raw, self.protocol)

    def _observation_raw(self, metrics: dict[str, object]) -> dict[str, object]:
        return {
            "source_batch": "batch",
            "source_row": "1",
            "robot_id": "r1",
            "protocol_id": self.protocol.protocol_id,
            "protocol_version": self.protocol.version,
            "stratum_key": "clear-aisle",
            "observed_at": "2026-09-21T10:00:00+08:00",
            "metrics": metrics,
            "excluded_reason": None,
        }

    def test_count_metric_rejects_negative(self) -> None:
        raw = self._observation_raw(
            {"completed": 1, "completion_seconds": 4, "interventions": -1}
        )
        with self.assertRaisesRegex(
            ValidationError, r"observation\.metrics\.interventions 必须是大于等于零的整数"
        ):
            Observation.from_dict(raw, self.protocol)

    def test_count_metric_accepts_zero(self) -> None:
        raw = self._observation_raw(
            {"completed": 0, "completion_seconds": 4, "interventions": 0}
        )
        observation = Observation.from_dict(raw, self.protocol)
        self.assertEqual(observation.metrics["interventions"], 0)

    def test_count_metric_rejects_fraction(self) -> None:
        raw = self._observation_raw(
            {"completed": 1, "completion_seconds": 4, "interventions": "1.5"}
        )
        with self.assertRaisesRegex(ValidationError, r"observation\.metrics\.interventions"):
            Observation.from_dict(raw, self.protocol)

    def test_count_metric_rejects_non_finite(self) -> None:
        raw = self._observation_raw(
            {"completed": 1, "completion_seconds": 4, "interventions": "Infinity"}
        )
        with self.assertRaisesRegex(
            ValidationError, r"observation\.metrics\.interventions 必须是有限数值"
        ):
            Observation.from_dict(raw, self.protocol)

    def test_continuous_metric_keeps_unconstrained_semantics(self) -> None:
        # 连续指标不引入非负约束，语义保持不变。
        raw = self._observation_raw(
            {"completed": 1, "completion_seconds": -3.2, "interventions": 0}
        )
        observation = Observation.from_dict(raw, self.protocol)
        self.assertEqual(float(observation.metrics["completion_seconds"]), -3.2)

    def test_binary_metric_still_accepts_zero_and_one(self) -> None:
        raw = self._observation_raw(
            {"completed": 0, "completion_seconds": 4, "interventions": 2}
        )
        observation = Observation.from_dict(raw, self.protocol)
        self.assertEqual(observation.metrics["completed"], 0)
        self.assertEqual(observation.metrics["interventions"], 2)


if __name__ == "__main__":
    unittest.main()


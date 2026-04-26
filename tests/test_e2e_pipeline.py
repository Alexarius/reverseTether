"""End-to-end smoke coverage for the mock benchmark-to-analysis pipeline."""

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from analysis.aggregate import apply_final_evidence_filter
from client.matrix import main as matrix_main


class TestMockPipelineFinalEvidence(unittest.TestCase):
    """Verify final-suite mock matrix output survives strict evidence filtering."""

    def test_mock_matrix_final_dataset_survives_final_evidence_filter(self):
        repo_root = Path(__file__).resolve().parents[1]
        suite_path = repo_root / "configs" / "prompts" / "dataset_suite_v1.json"

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "mock_matrix"

            with patch(
                "sys.argv",
                [
                    "client.matrix",
                    "--node",
                    "yoga",
                    "--backend",
                    "cpu",
                    "--regimes",
                    "warm",
                    "--repetitions",
                    "1",
                    "--prompt-id",
                    "final_short_01",
                    "--suite-path",
                    str(suite_path),
                    "--cache-policy",
                    "cleared_by_restart",
                    "--mock",
                    "--output-dir",
                    str(output_dir),
                ],
            ), patch("sys.stdout", new_callable=io.StringIO), patch(
                "sys.stderr", new_callable=io.StringIO
            ):
                matrix_main()

            raw_metrics_path = output_dir / "raw_metrics.jsonl"
            self.assertTrue(raw_metrics_path.exists())

            records = [
                json.loads(line)
                for line in raw_metrics_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertGreater(len(records), 0)

            filtered = apply_final_evidence_filter(pd.DataFrame(records))

            self.assertFalse(filtered.empty)
            self.assertEqual(filtered["suite_type"].tolist(), ["final_dataset"])
            self.assertEqual(filtered["cache_policy"].tolist(), ["cleared_by_restart"])
            self.assertEqual(filtered["cache_observed"].tolist(), ["full_eval"])
            self.assertEqual(filtered["cache_mismatch"].tolist(), [False])

    def test_mock_matrix_all_final_prompts_survives_final_evidence_filter(self):
        repo_root = Path(__file__).resolve().parents[1]
        suite_path = repo_root / "configs" / "prompts" / "dataset_suite_v1.json"

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "mock_matrix_all_final"

            with patch(
                "sys.argv",
                [
                    "client.matrix",
                    "--node",
                    "yoga",
                    "--backend",
                    "cpu",
                    "--regimes",
                    "warm",
                    "--repetitions",
                    "1",
                    "--all-final-prompts",
                    "--suite-path",
                    str(suite_path),
                    "--cache-policy",
                    "cleared_by_restart",
                    "--mock",
                    "--output-dir",
                    str(output_dir),
                ],
            ), patch("sys.stdout", new_callable=io.StringIO), patch(
                "sys.stderr", new_callable=io.StringIO
            ):
                matrix_main()

            raw_metrics_path = output_dir / "raw_metrics.jsonl"
            self.assertTrue(raw_metrics_path.exists())

            records = [
                json.loads(line)
                for line in raw_metrics_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertGreater(len(records), 0)

            filtered = apply_final_evidence_filter(pd.DataFrame(records))

            self.assertEqual(len(filtered), len(records))


if __name__ == "__main__":
    unittest.main()

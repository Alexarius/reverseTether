"""Tests for aggregation output layout."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from analysis.aggregate import compute_aggregates, main as aggregate_main


class TestAggregateOutputLayout(unittest.TestCase):
    """Tests for aggregation run artifact placement."""

    def test_main_writes_timestamped_subdirectory_with_stable_filenames(self):
        """Each aggregation invocation should isolate artifacts in one run folder."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "results"
            output_dir = root / "summaries"
            run_dir = input_dir / "20260420_120000_yoga_cpu_warm"
            run_dir.mkdir(parents=True)
            (run_dir / "metadata.json").write_text("{}\n", encoding="utf-8")
            (run_dir / "raw_metrics.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "run-1",
                        "benchmark_condition_id": "yoga_cpu_local_Q4_0",
                        "regime": "warm",
                        "prompt_tier": "short",
                        "stop_reason": "eos",
                        "ttft_ms": 100.0,
                        "decode_tps": 12.5,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "analysis.aggregate.plot_ttft_comparison"
            ) as ttft_plot_mock, patch(
                "analysis.aggregate.plot_decode_tps_comparison"
            ) as decode_plot_mock, patch(
                "sys.argv",
                [
                    "analysis.aggregate",
                    "--input",
                    str(input_dir),
                    "--output",
                    str(output_dir),
                ],
            ):
                exit_code = aggregate_main()

            self.assertEqual(exit_code, 0)

            run_output_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
            self.assertEqual(len(run_output_dirs), 1)
            run_output_dir = run_output_dirs[0]
            self.assertRegex(run_output_dir.name, r"^aggregation_\d{8}_\d{6}$")

            self.assertTrue((run_output_dir / "summary.csv").exists())
            self.assertTrue((run_output_dir / "summary.md").exists())
            self.assertTrue((run_output_dir / "raw_export.csv").exists())
            self.assertFalse((output_dir / "summary.csv").exists())
            self.assertFalse((output_dir / "raw_export.csv").exists())

            ttft_plot_mock.assert_called_once()
            decode_plot_mock.assert_called_once()
            self.assertEqual(
                ttft_plot_mock.call_args[0][1].resolve(),
                (run_output_dir / "ttft_comparison.png").resolve(),
            )
            self.assertEqual(
                decode_plot_mock.call_args[0][1].resolve(),
                (run_output_dir / "decode_tps_comparison.png").resolve(),
            )


class TestAggregateFiltering(unittest.TestCase):
    """Tests for opt-in evidence filters."""

    def test_final_evidence_only_excludes_legacy_smoke_and_cache_mismatch(self):
        """Strict final-evidence mode should keep only eligible records."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "results"
            output_dir = root / "summaries"
            input_dir.mkdir()

            mocked_df = pd.DataFrame(
                [
                    {
                        "run_id": "legacy-run",
                        "benchmark_condition_id": "yoga_cpu_local_Q4_0",
                        "regime": "warm",
                        "prompt_tier": "short",
                        "stop_reason": "eos",
                        "ttft_ms": 100.0,
                        "decode_tps": 10.0,
                        "source_dir": "legacy_dir",
                    },
                    {
                        "run_id": "smoke-run",
                        "benchmark_condition_id": "yoga_cpu_local_Q4_0",
                        "regime": "warm",
                        "prompt_tier": "short",
                        "stop_reason": "eos",
                        "ttft_ms": 110.0,
                        "decode_tps": 11.0,
                        "source_dir": "smoke_dir",
                        "suite_type": "smoke",
                        "cache_policy": "system_managed",
                    },
                    {
                        "run_id": "cache-mismatch-run",
                        "benchmark_condition_id": "yoga_cpu_local_Q4_0",
                        "regime": "warm",
                        "prompt_tier": "short",
                        "stop_reason": "eos",
                        "ttft_ms": 120.0,
                        "decode_tps": 12.0,
                        "source_dir": "cache_mismatch_dir",
                        "suite_type": "final_dataset",
                        "cache_policy": "cache_mismatch",
                    },
                    {
                        "run_id": "final-run",
                        "benchmark_condition_id": "yoga_cpu_local_Q4_0",
                        "regime": "warm",
                        "prompt_tier": "short",
                        "stop_reason": "eos",
                        "ttft_ms": 130.0,
                        "decode_tps": 13.0,
                        "source_dir": "final_dir",
                        "suite_type": "final_dataset",
                        "cache_policy": "system_managed",
                    },
                ]
            )

            with patch(
                "analysis.aggregate.collect_runs", return_value=mocked_df
            ), patch(
                "analysis.aggregate.plot_ttft_comparison"
            ), patch(
                "analysis.aggregate.plot_decode_tps_comparison"
            ), patch(
                "sys.argv",
                [
                    "analysis.aggregate",
                    "--input",
                    str(input_dir),
                    "--output",
                    str(output_dir),
                    "--final-evidence-only",
                ],
            ), self.assertLogs("analysis.aggregate", level="INFO") as logs:
                exit_code = aggregate_main()

            self.assertEqual(exit_code, 0)
            self.assertIn(
                "Final evidence strict filter dropped 3 records.",
                "\n".join(logs.output),
            )

            run_output_dir = next(path for path in output_dir.iterdir() if path.is_dir())
            raw_export = pd.read_csv(run_output_dir / "raw_export.csv")
            self.assertEqual(raw_export["run_id"].tolist(), ["final-run"])


class TestAggregateGrouping(unittest.TestCase):
    """Tests for aggregation grouping options."""

    def test_group_by_prompt_id_splits_shared_condition_and_tier(self):
        """Prompt ID should become part of the group key only when requested."""
        df = pd.DataFrame(
            [
                {
                    "run_id": "run-1",
                    "benchmark_condition_id": "yoga_cpu_local_Q4_0",
                    "regime": "warm",
                    "prompt_tier": "short",
                    "prompt_id": "short_final_v1",
                    "stop_reason": "eos",
                    "ttft_ms": 100.0,
                    "decode_tps": 10.0,
                    "source_dir": "dir_a",
                },
                {
                    "run_id": "run-2",
                    "benchmark_condition_id": "yoga_cpu_local_Q4_0",
                    "regime": "warm",
                    "prompt_tier": "short",
                    "prompt_id": "short_final_v2",
                    "stop_reason": "eos",
                    "ttft_ms": 200.0,
                    "decode_tps": 20.0,
                    "source_dir": "dir_b",
                },
            ]
        )

        grouped = compute_aggregates(df, group_by_prompt_id=True).sort_values(
            "prompt_id"
        )

        self.assertEqual(len(grouped), 2)
        self.assertEqual(
            grouped["prompt_id"].tolist(), ["short_final_v1", "short_final_v2"]
        )
        self.assertEqual(grouped["sample_count"].tolist(), [1, 1])
        self.assertEqual(grouped["ttft_p50_ms"].tolist(), [100.0, 200.0])

        default_grouped = compute_aggregates(df)
        self.assertEqual(len(default_grouped), 1)
        self.assertNotIn("prompt_id", default_grouped.columns)
        self.assertEqual(default_grouped["sample_count"].iloc[0], 2)
        self.assertEqual(default_grouped["decode_tps_mean"].iloc[0], 15.0)


if __name__ == "__main__":
    unittest.main()

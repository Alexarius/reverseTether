"""Tests for aggregation output layout."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis.aggregate import main as aggregate_main


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


if __name__ == "__main__":
    unittest.main()

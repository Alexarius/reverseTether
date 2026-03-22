"""Tests for benchmark execution logging."""

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from client.benchmark import BenchmarkConfig, run_benchmark
from client.metrics import TimingData


class TestBenchmarkLogging(unittest.TestCase):
    """Tests for run directory logging artifacts."""

    def test_run_benchmark_writes_metadata_and_populates_token_timestamps(self):
        """Successful runs should emit metadata.json and timestamped raw metrics."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            model_name="Llama-3.2-1B-Instruct",
        )
        request_sent_wallclock = datetime(2026, 3, 22, 12, 0, 0)
        first_token_wallclock = datetime(2026, 3, 22, 12, 0, 1)
        final_token_wallclock = datetime(2026, 3, 22, 12, 0, 3)
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=5,
            request_sent_wallclock=request_sent_wallclock,
            first_token_wallclock=first_token_wallclock,
            final_token_wallclock=final_token_wallclock,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, [{"tokens_evaluated": 42}], "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                record = run_benchmark(
                    prompt="Test prompt",
                    prompt_id="short_v1",
                    config=config,
                    output_dir=output_dir,
                    repetition_index=0,
                )

            metadata_path = output_dir / "metadata.json"
            raw_metrics_path = output_dir / "raw_metrics.jsonl"

            self.assertTrue(metadata_path.exists())
            self.assertTrue(raw_metrics_path.exists())

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["node"], "yoga")
            self.assertEqual(metadata["backend"], "cpu")
            self.assertEqual(metadata["run_type"], "warm")
            self.assertEqual(metadata["prompt_tier"], "short")
            self.assertEqual(metadata["server_mode"], "local")
            self.assertEqual(metadata["model_name"], "Llama-3.2-1B-Instruct")

            raw_record = json.loads(raw_metrics_path.read_text(encoding="utf-8").strip())
            self.assertEqual(record.request_sent_timestamp, request_sent_wallclock.isoformat())
            self.assertEqual(record.first_token_timestamp, first_token_wallclock.isoformat())
            self.assertEqual(record.final_token_timestamp, final_token_wallclock.isoformat())
            self.assertEqual(raw_record["request_sent_timestamp"], request_sent_wallclock.isoformat())
            self.assertEqual(raw_record["first_token_timestamp"], first_token_wallclock.isoformat())
            self.assertEqual(raw_record["final_token_timestamp"], final_token_wallclock.isoformat())


if __name__ == "__main__":
    unittest.main()

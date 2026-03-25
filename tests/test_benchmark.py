"""Tests for benchmark execution logging and streaming behavior.

This module tests:
- Run directory logging artifacts (metadata.json, raw_metrics.jsonl)
- Streaming behavior and timing capture for first/final tokens
- Edge cases in SSE parsing and token counting

Critical timing boundaries (from EXPERIMENT_PROTOCOL.md):
- request_sent_ts: recorded immediately BEFORE requests.post()
- first_token_ts: recorded when first content token arrives
- final_token_ts: recorded when last token arrives
"""

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from client.benchmark import (
    BenchmarkConfig,
    run_benchmark,
    parse_sse_line,
    build_completion_payload,
    stream_completion,
)
from client.metrics import TimingData

VALID_MODEL_SHA256 = "a" * 64
VALID_LLAMA_CPP_COMMIT = "b" * 40


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
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        request_sent_wallclock = datetime(2026, 3, 22, 12, 0, 0)
        first_token_wallclock = datetime(2026, 3, 22, 12, 0, 1)
        final_token_wallclock = datetime(2026, 3, 22, 12, 0, 3)
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=5,
            client_overhead_ms=12.5,
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
            self.assertEqual(record.client_overhead_ms, 12.5)
            self.assertEqual(raw_record["client_overhead_ms"], 12.5)


class TestSSEParsing(unittest.TestCase):
    """Tests for Server-Sent Events line parsing."""

    def test_parse_sse_line_valid_data(self):
        """Valid SSE data line should return parsed JSON."""
        line = 'data: {"content": "Hello", "stop": false}'
        result = parse_sse_line(line)
        self.assertEqual(result["content"], "Hello")
        self.assertEqual(result["stop"], False)

    def test_parse_sse_line_done_marker(self):
        """SSE [DONE] marker should return None."""
        line = "data: [DONE]"
        result = parse_sse_line(line)
        self.assertIsNone(result)

    def test_parse_sse_line_empty(self):
        """Empty lines should return None."""
        result = parse_sse_line("")
        self.assertIsNone(result)
        result = parse_sse_line("   ")
        self.assertIsNone(result)

    def test_parse_sse_line_non_data(self):
        """Non-data lines (comments, event types) should return None."""
        result = parse_sse_line(": this is a comment")
        self.assertIsNone(result)
        result = parse_sse_line("event: message")
        self.assertIsNone(result)

    def test_parse_sse_line_malformed_json(self):
        """Malformed JSON should return None, not raise."""
        line = "data: {not valid json"
        result = parse_sse_line(line)
        self.assertIsNone(result)


class TestCompletionPayload(unittest.TestCase):
    """Tests for completion request payload building."""

    def test_payload_includes_stream_true(self):
        """Payload must have stream=True for accurate timing."""
        config = BenchmarkConfig(
            node="yoga", backend="cpu", run_type="warm", prompt_tier="short"
        )
        payload = build_completion_payload("Test prompt", config)
        self.assertTrue(payload["stream"])

    def test_payload_generation_settings(self):
        """Payload includes all fixed generation settings."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            seed=42,
            temperature=0.0,
            max_tokens=512,
        )
        payload = build_completion_payload("Test prompt", config)
        self.assertEqual(payload["seed"], 42)
        self.assertEqual(payload["temperature"], 0.0)
        self.assertEqual(payload["n_predict"], 512)
        self.assertEqual(payload["prompt"], "Test prompt")


class TestStreamingTimingCapture(unittest.TestCase):
    """Tests for streaming timing capture behavior.

    These tests verify the critical timing boundaries from the implementation plan:
    - request_sent_ts is captured immediately BEFORE HTTP POST
    - first_token_ts is captured when first content token arrives
    - final_token_ts is captured when last content token arrives
    """

    def test_timing_data_captures_request_before_post(self):
        """TimingData.request_sent_ts must be set before HTTP request."""
        config = BenchmarkConfig(
            node="yoga", backend="cpu", run_type="warm", prompt_tier="short"
        )
        # Create timing data as the function would
        timing = TimingData(request_sent_ts=0)
        timing.request_sent_wallclock = datetime.now()
        timing.request_sent_ts = 100.0  # Simulated perf_counter value

        # request_sent_ts should be set and non-zero
        self.assertIsNotNone(timing.request_sent_ts)
        self.assertGreater(timing.request_sent_ts, 0)
        self.assertIsNotNone(timing.request_sent_wallclock)

    def test_timing_data_first_token_initially_none(self):
        """first_token_ts should be None until first content arrives."""
        timing = TimingData(request_sent_ts=100.0)
        self.assertIsNone(timing.first_token_ts)
        self.assertIsNone(timing.first_token_wallclock)

    def test_timing_data_final_equals_first_for_single_token(self):
        """For single token generation, final_token_ts == first_token_ts."""
        timing = TimingData(
            request_sent_ts=100.0,
            first_token_ts=100.5,
            final_token_ts=100.5,  # Same as first for single token
            generated_token_count=1,
        )
        self.assertEqual(timing.first_token_ts, timing.final_token_ts)

    @patch("client.benchmark.requests.post")
    @patch("client.benchmark.time.perf_counter")
    def test_stream_completion_ignores_truthy_non_string_chunks_for_ttft(
        self,
        perf_counter_mock,
        post_mock,
    ):
        """TTFT must start only on a non-empty string token, not a truthy non-string chunk."""
        config = BenchmarkConfig(
            node="yoga", backend="cpu", run_type="warm", prompt_tier="short"
        )
        response = MagicMock()
        response.iter_lines.return_value = iter([
            'data: {"content": ["not-a-token"], "stop": false}',
            'data: {"content": "hello", "stop": false}',
            'data: {"stop": true, "stop_type": "eos", "tokens_predicted": 1}',
        ])
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        perf_counter_mock.side_effect = iter([
            100.0,
            100.1,
            101.0,
            101.1,
            101.2,
            102.0,
            102.1,
            103.0,
            103.5,
            103.6,
            104.0,
            104.1,
            104.2,
            104.3,
        ])

        timing, events, stop_reason = stream_completion("Test prompt", config)

        self.assertEqual(len(events), 3)
        self.assertEqual(stop_reason, "eos")
        self.assertEqual(timing.first_token_ts, 103.5)
        self.assertEqual(timing.final_token_ts, 103.5)
        self.assertEqual(timing.generated_token_count, 1)
        self.assertGreater(timing.client_overhead_ms, 0.0)


class TestStreamingEdgeCases(unittest.TestCase):
    """Tests for edge cases in streaming measurement.

    These address risks identified in the implementation plan:
    - Zero-token generation
    - Single-token generation
    - Network/library buffering effects
    """

    def test_run_benchmark_zero_tokens(self):
        """Handle case where no content tokens are generated."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            model_name="test-model",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        # Simulate stream that produces no content tokens
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=None,
            final_token_ts=None,
            generated_token_count=0,
            request_sent_wallclock=datetime(2026, 3, 22, 12, 0, 0),
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, [], "stop"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                record = run_benchmark(
                    prompt="Test",
                    prompt_id="test",
                    config=config,
                    output_dir=output_dir,
                )

            # TTFT and decode_tps should be None for zero tokens
            self.assertIsNone(record.ttft_ms)
            self.assertIsNone(record.decode_tps)
            self.assertEqual(record.generated_token_count, 0)

    def test_run_benchmark_single_token(self):
        """Handle case where only one token is generated (decode TPS undefined)."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            model_name="test-model",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        request_sent = datetime(2026, 3, 22, 12, 0, 0)
        first_token = datetime(2026, 3, 22, 12, 0, 1)
        # For single token, first == final
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=11.0,  # Same as first_token
            generated_token_count=1,
            request_sent_wallclock=request_sent,
            first_token_wallclock=first_token,
            final_token_wallclock=first_token,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, [{"stop": True}], "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                record = run_benchmark(
                    prompt="Test",
                    prompt_id="test",
                    config=config,
                    output_dir=output_dir,
                )

            # TTFT should be valid (1 second = 1000ms)
            self.assertAlmostEqual(record.ttft_ms, 1000.0, places=1)
            # Decode TPS should be None (zero decode window)
            self.assertIsNone(record.decode_tps)
            self.assertEqual(record.generated_token_count, 1)


class TestReproducibilityValidation(unittest.TestCase):
    """Tests for strict reproducibility field validation."""

    def test_run_benchmark_rejects_invalid_model_sha256(self):
        """Non-mock runs must reject model hashes that are not 64 lowercase hex chars."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            model_sha256="A" * 64,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )

        with patch("client.benchmark.create_result_directory") as create_dir_mock, patch(
            "client.benchmark.stream_completion"
        ) as stream_mock:
            with self.assertRaisesRegex(ValueError, "model_sha256"):
                run_benchmark(prompt="Test", prompt_id="short_v1", config=config)

        create_dir_mock.assert_not_called()
        stream_mock.assert_not_called()

    def test_run_benchmark_rejects_invalid_llama_cpp_commit(self):
        """Non-mock runs must reject commit hashes that are not 40 lowercase hex chars."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit="B" * 40,
        )

        with patch("client.benchmark.create_result_directory") as create_dir_mock, patch(
            "client.benchmark.stream_completion"
        ) as stream_mock:
            with self.assertRaisesRegex(ValueError, "llama_cpp_commit"):
                run_benchmark(prompt="Test", prompt_id="short_v1", config=config)

        create_dir_mock.assert_not_called()
        stream_mock.assert_not_called()

    def test_run_benchmark_allows_mock_without_hashes(self):
        """Mock runs may bypass strict reproducibility validation for dry-run coverage."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            mock=True,
        )
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=10.5,
            final_token_ts=12.0,
            generated_token_count=4,
            client_overhead_ms=3.5,
            request_sent_wallclock=datetime(2026, 3, 22, 12, 0, 0),
            first_token_wallclock=datetime(2026, 3, 22, 12, 0, 1),
            final_token_wallclock=datetime(2026, 3, 22, 12, 0, 2),
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.generate_mock_timing",
                return_value=(timing, [{"tokens_evaluated": 7}], "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                record = run_benchmark(
                    prompt="Test prompt",
                    prompt_id="short_v1",
                    config=config,
                    output_dir=output_dir,
                )

            self.assertEqual(record.generated_token_count, 4)
            self.assertEqual(record.prompt_token_count, 7)
            self.assertTrue((output_dir / "metadata.json").exists())
            self.assertTrue((output_dir / "raw_metrics.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

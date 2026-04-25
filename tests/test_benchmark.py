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
    MatrixConfig,
    MatrixRunResult,
    build_completion_payload,
    extract_prompt_token_count,
    parse_sse_line,
    run_benchmark,
    run_matrix,
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
            suite_type="smoke",
            cache_policy="system_managed",
            fixture_prompt_token_count=45,
            model_name="Llama-3.2-1B-Instruct",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
            start_temperature_c=32.5,
            end_temperature_c=34.0,
            temperature_source="sysfs_power_supply_battery_temp",
            start_battery_level_percent=81,
            end_battery_level_percent=80,
            battery_status="Discharging",
            background_apps_minimized=True,
            known_anomalies="none",
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
                    prompt_id="short_smoke_v1",
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
            self.assertEqual(metadata["start_temperature_c"], 32.5)
            self.assertEqual(metadata["end_temperature_c"], 34.0)
            self.assertEqual(metadata["temperature_source"], "sysfs_power_supply_battery_temp")
            self.assertEqual(metadata["start_battery_level_percent"], 81)
            self.assertEqual(metadata["end_battery_level_percent"], 80)
            self.assertEqual(metadata["battery_status"], "Discharging")
            self.assertTrue(metadata["background_apps_minimized"])
            self.assertEqual(metadata["known_anomalies"], "none")

            raw_record = json.loads(raw_metrics_path.read_text(encoding="utf-8").strip())
            self.assertEqual(record.request_sent_timestamp, request_sent_wallclock.isoformat())
            self.assertEqual(record.first_token_timestamp, first_token_wallclock.isoformat())
            self.assertEqual(record.final_token_timestamp, final_token_wallclock.isoformat())
            self.assertEqual(raw_record["request_sent_timestamp"], request_sent_wallclock.isoformat())
            self.assertEqual(raw_record["first_token_timestamp"], first_token_wallclock.isoformat())
            self.assertEqual(raw_record["final_token_timestamp"], final_token_wallclock.isoformat())
            self.assertEqual(record.client_overhead_ms, 12.5)
            self.assertEqual(raw_record["client_overhead_ms"], 12.5)
            self.assertEqual(record.suite_type, "smoke")
            self.assertEqual(record.cache_policy, "system_managed")
            self.assertEqual(record.fixture_prompt_token_count, 45)
            self.assertEqual(record.runtime_prompt_eval_token_count, 42)
            self.assertFalse(record.cache_expected)
            self.assertEqual(record.cache_observed, "full_eval")
            self.assertFalse(record.cache_mismatch)
            self.assertEqual(raw_record["suite_type"], "smoke")
            self.assertEqual(raw_record["cache_policy"], "system_managed")
            self.assertEqual(raw_record["fixture_prompt_token_count"], 45)
            self.assertEqual(raw_record["runtime_prompt_eval_token_count"], 42)
            self.assertFalse(raw_record["cache_expected"])
            self.assertEqual(raw_record["cache_observed"], "full_eval")
            self.assertFalse(raw_record["cache_mismatch"])
            self.assertEqual(raw_record["start_temperature_c"], 32.5)
            self.assertEqual(raw_record["end_temperature_c"], 34.0)
            self.assertEqual(raw_record["temperature_source"], "sysfs_power_supply_battery_temp")
            self.assertEqual(raw_record["start_battery_level_percent"], 81)
            self.assertEqual(raw_record["end_battery_level_percent"], 80)
            self.assertEqual(raw_record["battery_status"], "Discharging")
            self.assertTrue(raw_record["background_apps_minimized"])
            self.assertEqual(raw_record["known_anomalies"], "none")
            self.assertNotIn("device_temperature_c", raw_record)
            self.assertNotIn("battery_level_percent", raw_record)


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


class TestPromptTokenCountExtraction(unittest.TestCase):
    """Tests for robust prompt token extraction from llama.cpp metadata."""

    def test_extract_prompt_token_count_from_tokens_evaluated(self):
        """Should extract prompt token count from tokens_evaluated."""
        events = [
            {"content": "hello", "stop": False},
            {"stop": True, "tokens_evaluated": 142},
        ]

        self.assertEqual(extract_prompt_token_count(events), 142)

    def test_extract_prompt_token_count_from_prompt_tokens(self):
        """Should extract prompt token count from prompt_tokens."""
        events = [
            {"content": "hello", "stop": False},
            {"stop": True, "prompt_tokens": 87},
        ]

        self.assertEqual(extract_prompt_token_count(events), 87)

    def test_extract_prompt_token_count_from_nested_timings_prompt_n(self):
        """Should extract prompt token count from timings.prompt_n."""
        events = [
            {"content": "hello", "stop": False},
            {"stop": True, "timings": {"prompt_n": 65}},
        ]

        self.assertEqual(extract_prompt_token_count(events), 65)

    def test_extract_prompt_token_count_checks_recent_events(self):
        """Should find metadata in a recent event even if the final event lacks it."""
        events = [
            {"content": "older", "tokens_evaluated": 10},
            {"content": "token", "stop": False},
            {"timings": {"prompt_n": 99}},
            {"stop": True, "stop_type": "eos"},
        ]

        self.assertEqual(extract_prompt_token_count(events), 99)

    def test_extract_prompt_token_count_returns_none_when_missing(self):
        """Should return None when prompt token metadata is unavailable."""
        events = [
            {"content": "hello", "stop": False},
            {"stop": True, "tokens_predicted": 12},
        ]

        self.assertIsNone(extract_prompt_token_count(events))


class TestCachePolicyEvaluation(unittest.TestCase):
    """Tests for runtime prompt eval cache mismatch evidence."""

    def _run_with_runtime_prompt_count(
        self,
        *,
        cache_policy: str,
        fixture_prompt_token_count: int,
        runtime_prompt_eval_token_count: int,
        suite_type: str = "smoke",
    ):
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            suite_type=suite_type,
            cache_policy=cache_policy,
            fixture_prompt_token_count=fixture_prompt_token_count,
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=5,
            client_overhead_ms=2.0,
            request_sent_wallclock=datetime(2026, 3, 25, 12, 0, 0),
            first_token_wallclock=datetime(2026, 3, 25, 12, 0, 1),
            final_token_wallclock=datetime(2026, 3, 25, 12, 0, 3),
        )
        events = [{"stop": True, "tokens_evaluated": runtime_prompt_eval_token_count}]

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, events, "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                record = run_benchmark(
                    prompt="Test prompt",
                    prompt_id="short_final_1",
                    config=config,
                    output_dir=output_dir,
                )

            raw_record = json.loads(
                (output_dir / "raw_metrics.jsonl").read_text(encoding="utf-8").strip()
            )

        return record, raw_record

    def test_collapsed_prompt_eval_without_expected_cache_sets_mismatch(self):
        """A tiny runtime prompt eval count should flag cache contamination."""
        record, raw_record = self._run_with_runtime_prompt_count(
            cache_policy="disabled",
            fixture_prompt_token_count=100,
            runtime_prompt_eval_token_count=1,
        )

        self.assertEqual(record.runtime_prompt_eval_token_count, 1)
        self.assertEqual(record.prompt_token_count, 1)
        self.assertFalse(record.cache_expected)
        self.assertEqual(record.cache_observed, "collapsed_eval")
        self.assertTrue(record.cache_mismatch)
        self.assertEqual(raw_record["runtime_prompt_eval_token_count"], 1)
        self.assertTrue(raw_record["cache_mismatch"])

    def test_less_than_ten_percent_prompt_eval_sets_mismatch(self):
        """A runtime prompt eval count below 10% of the fixture is collapsed."""
        record, _ = self._run_with_runtime_prompt_count(
            cache_policy="disabled",
            fixture_prompt_token_count=200,
            runtime_prompt_eval_token_count=19,
        )

        self.assertEqual(record.cache_observed, "collapsed_eval")
        self.assertTrue(record.cache_mismatch)

    def test_warm_cache_policy_allows_collapsed_prompt_eval(self):
        """Explicit warm-cache policy should not mark expected reuse as mismatch."""
        record, _ = self._run_with_runtime_prompt_count(
            cache_policy="warm_cache",
            fixture_prompt_token_count=100,
            runtime_prompt_eval_token_count=1,
        )

        self.assertTrue(record.cache_expected)
        self.assertEqual(record.cache_observed, "collapsed_eval")
        self.assertFalse(record.cache_mismatch)

    def test_final_dataset_expected_cache_policy_raises_before_streaming(self):
        """Final evidence runs must fail before invocation if cache reuse is expected."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            suite_type="final_dataset",
            cache_policy="warm_cache",
            fixture_prompt_token_count=100,
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch("client.benchmark.stream_completion") as stream_mock:
                with self.assertRaisesRegex(RuntimeError, "Final dataset cache gate"):
                    run_benchmark(
                        prompt="Test prompt",
                        prompt_id="short_final_1",
                        config=config,
                        output_dir=output_dir,
                    )

            stream_mock.assert_not_called()
            self.assertFalse((output_dir / "raw_metrics.jsonl").exists())

    def test_final_dataset_runtime_cache_mismatch_raises_without_success_record(self):
        """Collapsed prompt evaluation must fail final runs before raw success logging."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            suite_type="final_dataset",
            cache_policy="disabled",
            fixture_prompt_token_count=100,
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=5,
            client_overhead_ms=2.0,
            request_sent_wallclock=datetime(2026, 3, 25, 12, 0, 0),
            first_token_wallclock=datetime(2026, 3, 25, 12, 0, 1),
            final_token_wallclock=datetime(2026, 3, 25, 12, 0, 3),
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, [{"stop": True, "tokens_evaluated": 1}], "eos"),
            ) as stream_mock:
                with self.assertRaisesRegex(RuntimeError, "Final dataset cache gate"):
                    run_benchmark(
                        prompt="Test prompt",
                        prompt_id="short_final_1",
                        config=config,
                        output_dir=output_dir,
                    )

            stream_mock.assert_called_once()
            self.assertFalse((output_dir / "raw_metrics.jsonl").exists())


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
                run_benchmark(prompt="Test", prompt_id="short_smoke_v1", config=config)

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
                run_benchmark(prompt="Test", prompt_id="short_smoke_v1", config=config)

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
                    prompt_id="short_smoke_v1",
                    config=config,
                    output_dir=output_dir,
                )

            self.assertEqual(record.generated_token_count, 4)
            self.assertEqual(record.prompt_token_count, 7)
            self.assertEqual(record.runtime_prompt_eval_token_count, 7)
            self.assertEqual(record.cache_observed, "full_eval")
            self.assertTrue((output_dir / "metadata.json").exists())
            self.assertTrue((output_dir / "raw_metrics.jsonl").exists())


class TestPromptMetadataInJSONL(unittest.TestCase):
    """Tests for prompt metadata in JSONL records.

    Per Issue 09 requirements:
    - prompt_id must be logged in every record for reproducibility
    - prompt_token_count must be captured from server response (not guessed)
    - These fields enable tracking prompt drift and token count accuracy
    """

    def test_jsonl_contains_prompt_id(self):
        """Each JSONL record must contain the prompt_id field."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=5,
            client_overhead_ms=2.0,
            request_sent_wallclock=datetime(2026, 3, 25, 12, 0, 0),
            first_token_wallclock=datetime(2026, 3, 25, 12, 0, 1),
            final_token_wallclock=datetime(2026, 3, 25, 12, 0, 3),
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, [{"tokens_evaluated": 25}], "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                run_benchmark(
                    prompt="Test prompt",
                    prompt_id="short_smoke_v1",
                    config=config,
                    output_dir=output_dir,
                )

            metrics_file = output_dir / "raw_metrics.jsonl"
            record = json.loads(metrics_file.read_text(encoding="utf-8").strip())

            self.assertIn("prompt_id", record)
            self.assertEqual(record["prompt_id"], "short_smoke_v1")

    def test_jsonl_contains_prompt_token_count_from_server(self):
        """prompt_token_count must come from server metadata, not guessed."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="medium",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=50,
            client_overhead_ms=2.0,
            request_sent_wallclock=datetime(2026, 3, 25, 12, 0, 0),
            first_token_wallclock=datetime(2026, 3, 25, 12, 0, 1),
            final_token_wallclock=datetime(2026, 3, 25, 12, 0, 3),
        )
        # Server reports 142 prompt tokens via a supported metadata field.
        events = [{"prompt_tokens": 142, "stop": True}]

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, events, "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                run_benchmark(
                    prompt="Test prompt",
                    prompt_id="medium_smoke_v1",
                    config=config,
                    output_dir=output_dir,
                )

            metrics_file = output_dir / "raw_metrics.jsonl"
            record = json.loads(metrics_file.read_text(encoding="utf-8").strip())

            self.assertIn("prompt_token_count", record)
            self.assertEqual(record["prompt_token_count"], 142)
            self.assertIn("runtime_prompt_eval_token_count", record)
            self.assertEqual(record["runtime_prompt_eval_token_count"], 142)

    def test_jsonl_contains_prompt_token_count_from_nested_timings(self):
        """run_benchmark should use the helper for timings.prompt_n metadata."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="medium",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=50,
            client_overhead_ms=2.0,
            request_sent_wallclock=datetime(2026, 3, 25, 12, 0, 0),
            first_token_wallclock=datetime(2026, 3, 25, 12, 0, 1),
            final_token_wallclock=datetime(2026, 3, 25, 12, 0, 3),
        )
        events = [
            {"content": "partial", "stop": False},
            {"timings": {"prompt_n": 91}},
            {"stop": True, "stop_type": "eos"},
        ]

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, events, "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                run_benchmark(
                    prompt="Test prompt",
                    prompt_id="medium_smoke_v1",
                    config=config,
                    output_dir=output_dir,
                )

            metrics_file = output_dir / "raw_metrics.jsonl"
            record = json.loads(metrics_file.read_text(encoding="utf-8").strip())

            self.assertIn("prompt_token_count", record)
            self.assertEqual(record["prompt_token_count"], 91)
            self.assertIn("runtime_prompt_eval_token_count", record)
            self.assertEqual(record["runtime_prompt_eval_token_count"], 91)

    def test_jsonl_prompt_token_count_null_when_not_reported(self):
        """prompt_token_count should be null if server doesn't report it."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=5,
            client_overhead_ms=2.0,
            request_sent_wallclock=datetime(2026, 3, 25, 12, 0, 0),
            first_token_wallclock=datetime(2026, 3, 25, 12, 0, 1),
            final_token_wallclock=datetime(2026, 3, 25, 12, 0, 3),
        )
        # Server response without tokens_evaluated
        events = [{"stop": True}]

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, events, "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                run_benchmark(
                    prompt="Test prompt",
                    prompt_id="short_smoke_v1",
                    config=config,
                    output_dir=output_dir,
                )

            metrics_file = output_dir / "raw_metrics.jsonl"
            record = json.loads(metrics_file.read_text(encoding="utf-8").strip())

            # Field should exist but be null
            self.assertIn("prompt_token_count", record)
            self.assertIsNone(record["prompt_token_count"])
            self.assertIn("runtime_prompt_eval_token_count", record)
            self.assertIsNone(record["runtime_prompt_eval_token_count"])

    def test_jsonl_prompt_tier_matches_config(self):
        """prompt_tier field should reflect the configured tier."""
        config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="soak",
            prompt_tier="soak",
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        timing = TimingData(
            request_sent_ts=10.0,
            first_token_ts=11.0,
            final_token_ts=13.0,
            generated_token_count=5,
            client_overhead_ms=2.0,
            request_sent_wallclock=datetime(2026, 3, 25, 12, 0, 0),
            first_token_wallclock=datetime(2026, 3, 25, 12, 0, 1),
            final_token_wallclock=datetime(2026, 3, 25, 12, 0, 3),
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch(
                "client.benchmark.stream_completion",
                return_value=(timing, [{"tokens_evaluated": 100}], "eos"),
            ), patch("client.benchmark.uuid.uuid4", return_value="test-run-id"):
                run_benchmark(
                    prompt="Soak test prompt",
                    prompt_id="soak_smoke_v1",
                    config=config,
                    output_dir=output_dir,
                )

            metrics_file = output_dir / "raw_metrics.jsonl"
            record = json.loads(metrics_file.read_text(encoding="utf-8").strip())

            self.assertIn("prompt_tier", record)
            self.assertEqual(record["prompt_tier"], "soak")

    def test_matrix_jsonl_all_records_have_prompt_metadata(self):
        """All matrix run records must include prompt_id and prompt_token_count."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            suite_type="smoke",
            cache_policy="cache_mismatch",
            fixture_prompt_token_count=999,
            mock=True,
        )
        matrix_config = MatrixConfig(
            regimes=["warm", "soak"],
            repetitions=2,
            prompt_tier="short",
            prompt_tiers_by_id={
                "short_smoke_v1": "short",
                "soak_smoke_v1": "soak",
            },
            soak_prompt={
                "text": "Soak prompt",
                "id": "soak_smoke_v1",
                "fixture_prompt_token_count": 88,
            },
            dry_run=False,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            run_matrix(
                prompts=[
                    {
                        "text": "Test prompt",
                        "id": "short_smoke_v1",
                        "fixture_prompt_token_count": 37,
                    }
                ],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

            metrics_file = output_dir / "raw_metrics.jsonl"
            lines = metrics_file.read_text(encoding="utf-8").strip().split("\n")

            # All 4 records (2 regimes * 2 reps) must have prompt metadata
            self.assertEqual(len(lines), 4)

            for line in lines:
                record = json.loads(line)
                self.assertIn("prompt_id", record)
                self.assertIn("prompt_token_count", record)
                self.assertIn("prompt_tier", record)
                self.assertIn("suite_type", record)
                self.assertIn("cache_policy", record)
                self.assertIn("fixture_prompt_token_count", record)
                self.assertIn("runtime_prompt_eval_token_count", record)
                self.assertIn("cache_expected", record)
                self.assertIn("cache_observed", record)
                self.assertIn("cache_mismatch", record)
                self.assertEqual(record["suite_type"], "smoke")
                self.assertEqual(record["cache_policy"], "cache_mismatch")

            records = [json.loads(line) for line in lines]
            self.assertEqual(
                [
                    (
                        record["regime"],
                        record["prompt_id"],
                        record["prompt_tier"],
                        record["fixture_prompt_token_count"],
                    )
                    for record in records
                ],
                [
                    ("warm", "short_smoke_v1", "short", 37),
                    ("warm", "short_smoke_v1", "short", 37),
                    ("soak", "soak_smoke_v1", "soak", 88),
                    ("soak", "soak_smoke_v1", "soak", 88),
                ],
            )


class TestMatrixRunner(unittest.TestCase):
    """Tests for the benchmark matrix runner.

    These tests verify Issue 08 requirements:
    - Correct repetition count per regime
    - Proper regime labels in JSONL records
    - Matrix metadata in output directory
    - Error handling for failed runs (no silent skipping)
    """

    def test_run_matrix_correct_repetition_count(self):
        """Matrix runner should execute exact repetition count per regime."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",  # Will be overridden per regime
            prompt_tier="short",
            mock=True,
        )
        matrix_config = MatrixConfig(
            regimes=["cold", "warm", "soak"],
            repetitions=2,
            prompt_tier="short",
            prompt_tiers_by_id={
                "short_smoke_v1": "short",
                "soak_smoke_v1": "soak",
            },
            soak_prompt={"text": "Soak prompt", "id": "soak_smoke_v1"},
            dry_run=False,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            results = run_matrix(
                prompts=[{"text": "Test prompt", "id": "short_smoke_v1"}],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

            # 3 regimes * 2 repetitions = 6 total runs
            self.assertEqual(len(results), 6)

            # Verify JSONL line count matches
            metrics_file = output_dir / "raw_metrics.jsonl"
            lines = metrics_file.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 6)

    def test_run_matrix_correct_regime_labels(self):
        """Each record should have the correct regime label."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            mock=True,
        )
        matrix_config = MatrixConfig(
            regimes=["cold", "warm", "soak"],
            repetitions=2,
            prompt_tier="short",
            prompt_tiers_by_id={
                "short_smoke_v1": "short",
                "soak_smoke_v1": "soak",
            },
            soak_prompt={"text": "Soak prompt", "id": "soak_smoke_v1"},
            dry_run=False,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            results = run_matrix(
                prompts=[{"text": "Test prompt", "id": "short_smoke_v1"}],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

            # Verify regime labels in results
            regime_counts = {"cold": 0, "warm": 0, "soak": 0}
            for result in results:
                self.assertIn(result.regime, regime_counts)
                regime_counts[result.regime] += 1

            # Each regime should have exactly 2 runs
            for regime, count in regime_counts.items():
                self.assertEqual(count, 2, f"Regime {regime} should have 2 runs")

            # Verify regime labels in JSONL
            metrics_file = output_dir / "raw_metrics.jsonl"
            jsonl_regime_counts = {"cold": 0, "warm": 0, "soak": 0}
            for line in metrics_file.read_text(encoding="utf-8").strip().split("\n"):
                record = json.loads(line)
                self.assertIn("regime", record)
                self.assertIn(record["regime"], jsonl_regime_counts)
                jsonl_regime_counts[record["regime"]] += 1

            for regime, count in jsonl_regime_counts.items():
                self.assertEqual(count, 2, f"JSONL regime {regime} should have 2 records")

    def test_run_matrix_correct_repetition_indices(self):
        """Each record should have the correct repetition_index."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            mock=True,
        )
        matrix_config = MatrixConfig(
            regimes=["warm"],
            repetitions=3,
            prompt_tier="short",
            dry_run=False,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            results = run_matrix(
                prompts=[{"text": "Test prompt", "id": "short_smoke_v1"}],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

            # Verify repetition indices in results
            indices = [r.repetition_index for r in results]
            self.assertEqual(indices, [0, 1, 2])

            # Verify repetition indices in JSONL
            metrics_file = output_dir / "raw_metrics.jsonl"
            jsonl_indices = []
            for line in metrics_file.read_text(encoding="utf-8").strip().split("\n"):
                record = json.loads(line)
                self.assertIn("repetition_index", record)
                jsonl_indices.append(record["repetition_index"])

            self.assertEqual(jsonl_indices, [0, 1, 2])

    def test_run_matrix_orders_regime_prompt_repetition(self):
        """Matrix runner should loop Regime -> Prompt -> Repetition exactly."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="",
            mock=False,
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        matrix_config = MatrixConfig(
            regimes=["cold", "warm"],
            repetitions=2,
            prompt_tiers_by_id={
                "prompt_a": "short",
                "prompt_b": "medium",
            },
            dry_run=True,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            results = run_matrix(
                prompts=[
                    {"text": "Prompt A", "id": "prompt_a"},
                    {"text": "Prompt B", "id": "prompt_b"},
                ],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

        self.assertEqual(
            [
                (result.regime, result.prompt_id, result.repetition_index)
                for result in results
            ],
            [
                ("cold", "prompt_a", 0),
                ("cold", "prompt_a", 1),
                ("cold", "prompt_b", 0),
                ("cold", "prompt_b", 1),
                ("warm", "prompt_a", 0),
                ("warm", "prompt_a", 1),
                ("warm", "prompt_b", 0),
                ("warm", "prompt_b", 1),
            ],
        )

    def test_run_matrix_records_per_prompt_tier_metadata(self):
        """Multi-prompt matrix runs should keep each record's prompt tier explicit."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="",
            mock=True,
        )
        matrix_config = MatrixConfig(
            regimes=["warm"],
            repetitions=1,
            prompt_tiers_by_id={
                "prompt_short": "short",
                "prompt_long": "long",
            },
            dry_run=False,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            run_matrix(
                prompts=[
                    {
                        "text": "Short prompt",
                        "id": "prompt_short",
                        "fixture_prompt_token_count": 123,
                    },
                    {
                        "text": "Long prompt",
                        "id": "prompt_long",
                        "fixture_prompt_token_count": 1300,
                    },
                ],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

            metrics_file = output_dir / "raw_metrics.jsonl"
            records = [
                json.loads(line)
                for line in metrics_file.read_text(encoding="utf-8").strip().splitlines()
            ]

        self.assertEqual(
            [
                (
                    record["prompt_id"],
                    record["prompt_tier"],
                    record["fixture_prompt_token_count"],
                )
                for record in records
            ],
            [
                ("prompt_short", "short", 123),
                ("prompt_long", "long", 1300),
            ],
        )

    def test_run_matrix_uses_fixed_soak_prompt_for_soak_regime(self):
        """Mixed warm/soak matrices must run normal prompts only for warm and soak only for soak."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="",
            mock=True,
        )
        matrix_config = MatrixConfig(
            regimes=["warm", "soak"],
            repetitions=1,
            prompt_tiers_by_id={
                "prompt_short": "short",
                "prompt_medium": "medium",
                "prompt_soak": "soak",
            },
            soak_prompt={"text": "Soak prompt", "id": "prompt_soak"},
            dry_run=False,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            run_matrix(
                prompts=[
                    {"text": "Short prompt", "id": "prompt_short"},
                    {"text": "Medium prompt", "id": "prompt_medium"},
                ],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

            metrics_file = output_dir / "raw_metrics.jsonl"
            records = [
                json.loads(line)
                for line in metrics_file.read_text(encoding="utf-8").strip().splitlines()
            ]

        self.assertEqual(
            [(record["regime"], record["prompt_id"], record["prompt_tier"])
             for record in records],
            [
                ("warm", "prompt_short", "short"),
                ("warm", "prompt_medium", "medium"),
                ("soak", "prompt_soak", "soak"),
            ],
        )

    def test_run_matrix_writes_matrix_metadata(self):
        """Matrix run should write metadata.json with matrix configuration."""
        base_config = BenchmarkConfig(
            node="s25ultra",
            backend="opencl",
            run_type="warm",
            prompt_tier="soak",
            mock=True,
        )
        matrix_config = MatrixConfig(
            regimes=["soak"],
            repetitions=5,
            prompt_tier="soak",
            prompt_tiers_by_id={"soak_smoke_v1": "soak"},
            soak_prompt={"text": "Test prompt", "id": "soak_smoke_v1"},
            dry_run=False,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            run_matrix(
                prompts=[],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

            metadata_file = output_dir / "metadata.json"
            self.assertTrue(metadata_file.exists())

            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            self.assertEqual(metadata["run_type"], "matrix")
            self.assertEqual(metadata["regimes"], ["soak"])
            self.assertEqual(metadata["repetitions"], 5)
            self.assertEqual(metadata["prompt_selection_mode"], "prompt_tier")
            self.assertEqual(metadata["prompt_tier"], "soak")
            self.assertIsNone(metadata["prompt_id"])
            self.assertFalse(metadata["all_final_prompts"])
            self.assertEqual(metadata["selected_prompt_ids"], ["soak_smoke_v1"])
            self.assertEqual(metadata["node"], "s25ultra")
            self.assertEqual(metadata["backend"], "opencl")

    def test_run_matrix_dry_run_no_execution(self):
        """Dry run should not execute actual benchmarks but still return results."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            mock=False,  # Non-mock, but dry_run should prevent execution
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
        )
        matrix_config = MatrixConfig(
            regimes=["cold", "warm"],
            repetitions=2,
            prompt_tier="short",
            dry_run=True,  # Dry run mode
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            results = run_matrix(
                prompts=[{"text": "Test prompt", "id": "short_smoke_v1"}],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
            )

            # Should have results for all planned runs
            self.assertEqual(len(results), 4)

            # All results should be success with dry_run error message
            for result in results:
                self.assertTrue(result.success)
                self.assertEqual(result.error_message, "dry_run")
                self.assertIsNone(result.record)

            # JSONL should not exist (no actual runs)
            metrics_file = output_dir / "raw_metrics.jsonl"
            self.assertFalse(metrics_file.exists())

    def test_run_matrix_callbacks_invoked(self):
        """Matrix runner should invoke callbacks at appropriate times."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            mock=True,
        )
        matrix_config = MatrixConfig(
            regimes=["cold", "warm"],
            repetitions=2,
            prompt_tier="short",
            dry_run=False,
        )

        regime_starts = []
        run_completes = []

        def on_regime_start(regime: str) -> None:
            regime_starts.append(regime)

        def on_run_complete(result: MatrixRunResult) -> None:
            run_completes.append((result.regime, result.repetition_index))

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            run_matrix(
                prompts=[{"text": "Test prompt", "id": "short_smoke_v1"}],
                base_config=base_config,
                matrix_config=matrix_config,
                output_dir=output_dir,
                on_regime_start=on_regime_start,
                on_run_complete=on_run_complete,
            )

        # on_regime_start should be called once per regime
        self.assertEqual(regime_starts, ["cold", "warm"])

        # on_run_complete should be called for each run
        expected_completes = [
            ("cold", 0), ("cold", 1),
            ("warm", 0), ("warm", 1),
        ]
        self.assertEqual(run_completes, expected_completes)

    def test_run_matrix_handles_failed_runs(self):
        """Matrix runner should durably log failed runs without stopping."""
        base_config = BenchmarkConfig(
            node="yoga",
            backend="cpu",
            run_type="warm",
            prompt_tier="short",
            suite_type="smoke",
            cache_policy="system_managed",
            fixture_prompt_token_count=999,
            model_sha256=VALID_MODEL_SHA256,
            llama_cpp_commit=VALID_LLAMA_CPP_COMMIT,
            mock=False,
            start_temperature_c=35.0,
            end_temperature_c=36.5,
            temperature_source="dumpsys_battery_temperature",
            start_battery_level_percent=76,
            end_battery_level_percent=75,
        )
        matrix_config = MatrixConfig(
            regimes=["warm"],
            repetitions=3,
            prompt_tier="short",
            dry_run=False,
        )

        # Mock stream_completion to fail on second call
        call_count = [0]

        def mock_stream(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise ConnectionError("Simulated network failure")
            # Return valid mock timing for successful calls
            timing = TimingData(
                request_sent_ts=10.0,
                first_token_ts=10.5,
                final_token_ts=12.0,
                generated_token_count=5,
                client_overhead_ms=2.0,
                request_sent_wallclock=datetime(2026, 3, 25, 12, 0, 0),
                first_token_wallclock=datetime(2026, 3, 25, 12, 0, 1),
                final_token_wallclock=datetime(2026, 3, 25, 12, 0, 2),
            )
            return timing, [{"tokens_evaluated": 10}], "eos"

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch("client.benchmark.stream_completion", side_effect=mock_stream):
                results = run_matrix(
                    prompts=[
                        {
                            "text": "Test prompt",
                            "id": "short_smoke_v1",
                            "fixture_prompt_token_count": 37,
                        }
                    ],
                    base_config=base_config,
                    matrix_config=matrix_config,
                    output_dir=output_dir,
                )

            metrics_file = output_dir / "raw_metrics.jsonl"
            lines = metrics_file.read_text(encoding="utf-8").strip().splitlines()
            records = [json.loads(line) for line in lines]

        # All runs should be attempted
        self.assertEqual(len(results), 3)

        # First run: success
        self.assertTrue(results[0].success)
        self.assertIsNotNone(results[0].record)

        # Second run: failure (captured, not silently skipped)
        self.assertFalse(results[1].success)
        self.assertIn("network failure", results[1].error_message.lower())
        self.assertIsNotNone(results[1].record)
        self.assertEqual(results[1].record.stop_reason, "error")
        self.assertEqual(results[1].record.notes, "Simulated network failure")

        # Third run: success (matrix continued after failure)
        self.assertTrue(results[2].success)
        self.assertIsNotNone(results[2].record)
        self.assertEqual(len(lines), 3)
        self.assertEqual([record["repetition_index"] for record in records], [0, 1, 2])

        failed_record = records[1]
        self.assertEqual(failed_record["regime"], "warm")
        self.assertEqual(failed_record["repetition_index"], 1)
        self.assertEqual(failed_record["ttft_ms"], 0.0)
        self.assertEqual(failed_record["decode_tps"], 0.0)
        self.assertEqual(failed_record["generated_token_count"], 0)
        self.assertEqual(failed_record["stop_reason"], "error")
        self.assertEqual(failed_record["notes"], "Simulated network failure")
        self.assertEqual(failed_record["suite_type"], "smoke")
        self.assertEqual(failed_record["cache_policy"], "system_managed")
        self.assertEqual(failed_record["fixture_prompt_token_count"], 37)
        self.assertIsNone(failed_record["runtime_prompt_eval_token_count"])
        self.assertFalse(failed_record["cache_expected"])
        self.assertEqual(failed_record["cache_observed"], "unknown")
        self.assertFalse(failed_record["cache_mismatch"])
        self.assertEqual(failed_record["start_temperature_c"], 35.0)
        self.assertEqual(failed_record["end_temperature_c"], 36.5)
        self.assertEqual(failed_record["temperature_source"], "dumpsys_battery_temperature")
        self.assertEqual(failed_record["start_battery_level_percent"], 76)
        self.assertEqual(failed_record["end_battery_level_percent"], 75)


if __name__ == "__main__":
    unittest.main()

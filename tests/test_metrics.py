"""Unit tests for client.metrics module.

Tests verify TTFT and decode TPS computation according to EXPERIMENT_PROTOCOL.md:
- TTFT: elapsed time from request send to first token receive
- Decode TPS: token rate from first token to final token (tokens after first / time)
"""

import unittest
from client.metrics import (
    TimingData,
    ComputedMetrics,
    compute_ttft_ms,
    compute_decode_tps,
    compute_metrics,
    RunRecord,
)


class TestTTFTComputation(unittest.TestCase):
    """Tests for TTFT (Time To First Token) calculation."""

    def test_ttft_basic(self):
        """TTFT is difference between first token and request send, in ms."""
        request_sent = 1000.0
        first_token = 1000.5  # 500ms later
        ttft = compute_ttft_ms(request_sent, first_token)
        self.assertAlmostEqual(ttft, 500.0, places=1)

    def test_ttft_subsecond(self):
        """TTFT correctly handles sub-second precision."""
        request_sent = 0.0
        first_token = 0.123  # 123ms
        ttft = compute_ttft_ms(request_sent, first_token)
        self.assertAlmostEqual(ttft, 123.0, places=1)

    def test_ttft_long_wait(self):
        """TTFT handles longer wait times (e.g., cold start)."""
        request_sent = 100.0
        first_token = 105.5  # 5.5 seconds = 5500ms
        ttft = compute_ttft_ms(request_sent, first_token)
        self.assertAlmostEqual(ttft, 5500.0, places=1)


class TestDecodeTpsComputation(unittest.TestCase):
    """Tests for decode TPS (Tokens Per Second) calculation."""

    def test_decode_tps_basic(self):
        """Decode TPS is (total_tokens - 1) / decode_window_seconds.

        The first token marks the START of the decode window.
        We measure tokens generated AFTER the first token.
        """
        first_token = 1000.0
        final_token = 1010.0  # 10 seconds later
        generated_tokens = 51  # 50 tokens in decode window (51 - 1)
        tps = compute_decode_tps(first_token, final_token, generated_tokens)
        self.assertAlmostEqual(tps, 5.0, places=1)  # 50 tokens / 10 seconds

    def test_decode_tps_fast_generation(self):
        """Decode TPS for fast generation rate."""
        first_token = 0.0
        final_token = 1.0  # 1 second
        generated_tokens = 21  # 20 tokens in decode window
        tps = compute_decode_tps(first_token, final_token, generated_tokens)
        self.assertAlmostEqual(tps, 20.0, places=1)

    def test_decode_tps_single_token(self):
        """Decode TPS is None when only one token generated (no decode window)."""
        first_token = 0.0
        final_token = 0.1
        generated_tokens = 1  # Only the first token
        tps = compute_decode_tps(first_token, final_token, generated_tokens)
        self.assertIsNone(tps)

    def test_decode_tps_zero_duration(self):
        """Decode TPS is None when decode window has zero duration."""
        first_token = 5.0
        final_token = 5.0  # Same time
        generated_tokens = 10
        tps = compute_decode_tps(first_token, final_token, generated_tokens)
        self.assertIsNone(tps)

    def test_decode_tps_no_tokens(self):
        """Decode TPS is None when no tokens in decode window."""
        first_token = 0.0
        final_token = 1.0
        generated_tokens = 0  # No tokens
        tps = compute_decode_tps(first_token, final_token, generated_tokens)
        self.assertIsNone(tps)

    def test_decode_tps_negative_duration(self):
        """Decode TPS is None when decode window is negative (clock anomaly)."""
        first_token = 5.0
        final_token = 4.9  # Clock went backwards (should not happen, but defensive)
        generated_tokens = 10
        tps = compute_decode_tps(first_token, final_token, generated_tokens)
        self.assertIsNone(tps)


class TestComputeMetrics(unittest.TestCase):
    """Tests for the compute_metrics helper function."""

    def test_compute_metrics_complete(self):
        """Compute both TTFT and decode TPS from timing data."""
        timing = TimingData(
            request_sent_ts=0.0,
            first_token_ts=0.5,  # 500ms TTFT
            final_token_ts=5.5,  # 5 second decode window
            generated_token_count=26  # 25 tokens in decode window -> 5 TPS
        )
        metrics = compute_metrics(timing)

        self.assertAlmostEqual(metrics.ttft_ms, 500.0, places=1)
        self.assertAlmostEqual(metrics.decode_tps, 5.0, places=1)

    def test_compute_metrics_no_first_token(self):
        """Handle missing first token timestamp (e.g., timeout)."""
        timing = TimingData(
            request_sent_ts=0.0,
            first_token_ts=None,
            final_token_ts=None,
            generated_token_count=0
        )
        metrics = compute_metrics(timing)

        self.assertIsNone(metrics.ttft_ms)
        self.assertIsNone(metrics.decode_tps)

    def test_compute_metrics_only_ttft(self):
        """Handle case with first token but no final token."""
        timing = TimingData(
            request_sent_ts=0.0,
            first_token_ts=0.5,
            final_token_ts=None,
            generated_token_count=1
        )
        metrics = compute_metrics(timing)

        self.assertAlmostEqual(metrics.ttft_ms, 500.0, places=1)
        self.assertIsNone(metrics.decode_tps)


class TestRunRecord(unittest.TestCase):
    """Tests for RunRecord dataclass."""

    def test_run_record_defaults(self):
        """RunRecord has sensible defaults."""
        record = RunRecord(
            timestamp="2024-01-01T00:00:00",
            run_id="test-123",
            regime="warm",
            node="yoga",
            backend="cpu"
        )

        self.assertEqual(record.quantization, "Q4_0")
        self.assertEqual(record.context_length, 2048)
        self.assertEqual(record.seed, 42)
        self.assertEqual(record.temperature, 0.0)
        self.assertEqual(record.max_new_tokens, 512)
        self.assertEqual(record.server_mode, "local")
        self.assertEqual(record.suite_type, "unknown")
        self.assertEqual(record.prompt_suite_id, "")
        self.assertEqual(record.prompt_suite_version, "")
        self.assertEqual(record.cache_policy, "unknown")
        self.assertIsNone(record.fixture_prompt_token_count)
        self.assertIsNone(record.runtime_prompt_eval_token_count)
        self.assertFalse(record.cache_expected)
        self.assertEqual(record.cache_observed, "unknown")
        self.assertFalse(record.cache_mismatch)
        self.assertEqual(record.prompt_token_count_source, "")
        self.assertEqual(record.dataset_name, "")
        self.assertEqual(record.dataset_split, "")
        self.assertEqual(record.dataset_source_id, "")
        self.assertEqual(record.source_article_sha256, "")
        self.assertEqual(record.truncation_rule, "")
        self.assertEqual(record.prompt_fixture_sha256, "")
        self.assertEqual(record.tokenizer_runtime_used, "")
        self.assertEqual(record.client_overhead_ms, 0.0)
        self.assertIsNone(record.start_temperature_c)
        self.assertIsNone(record.end_temperature_c)
        self.assertEqual(record.temperature_source, "")
        self.assertIsNone(record.start_battery_level_percent)
        self.assertIsNone(record.end_battery_level_percent)
        self.assertFalse(hasattr(record, "device_temperature_c"))
        self.assertFalse(hasattr(record, "battery_level_percent"))

    def test_run_record_metrics_optional(self):
        """Metrics fields can be None initially."""
        record = RunRecord(
            timestamp="2024-01-01T00:00:00",
            run_id="test-123",
            regime="cold",
            node="yoga",
            backend="cpu"
        )

        self.assertIsNone(record.ttft_ms)
        self.assertIsNone(record.decode_tps)
        self.assertIsNone(record.prompt_token_count)
        self.assertEqual(record.client_overhead_ms, 0.0)

    def test_run_record_preserves_client_overhead_ms(self):
        """RunRecord explicitly stores client_overhead_ms for raw log output."""
        record = RunRecord(
            timestamp="2024-01-01T00:00:00",
            run_id="test-123",
            regime="warm",
            node="yoga",
            backend="cpu",
            client_overhead_ms=7.25,
        )

        self.assertEqual(record.client_overhead_ms, 7.25)


class TestMetricIntegrity(unittest.TestCase):
    """Tests ensuring metric semantics stay correct per EXPERIMENT_PROTOCOL.md."""

    def test_ttft_does_not_include_decode_time(self):
        """TTFT only measures time to FIRST token, not full generation."""
        timing = TimingData(
            request_sent_ts=0.0,
            first_token_ts=0.1,  # 100ms to first token
            final_token_ts=10.0,  # 10 seconds total generation
            generated_token_count=100
        )
        metrics = compute_metrics(timing)

        # TTFT should be 100ms, not 10000ms
        self.assertAlmostEqual(metrics.ttft_ms, 100.0, places=1)
        self.assertLess(metrics.ttft_ms, 1000.0)

    def test_decode_tps_excludes_first_token_wait(self):
        """Decode TPS only measures decode window, excludes prefill."""
        # Scenario: 5 second prefill, then 5 tokens in 1 second
        timing = TimingData(
            request_sent_ts=0.0,
            first_token_ts=5.0,  # 5 seconds to first token (prefill)
            final_token_ts=6.0,  # 1 second decode window
            generated_token_count=6  # 5 tokens in decode window
        )
        metrics = compute_metrics(timing)

        # Decode TPS should be 5.0, not diluted by prefill time
        self.assertAlmostEqual(metrics.decode_tps, 5.0, places=1)


if __name__ == "__main__":
    unittest.main()

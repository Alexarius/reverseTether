"""Tests for benchmark CLI validation behavior."""

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from client.cli import main as cli_main, load_prompt_suite, get_prompt_for_tier
from client.matrix import main as matrix_main


class TestPromptSuiteLoading(unittest.TestCase):
    """Tests for prompt suite fixture loading.

    Per Issue 09 requirements:
    - Smoke suite must be loaded from configs/prompts/smoke_suite.json
    - Smoke suite must contain versioned smoke prompt IDs
    - Load errors must fail loudly, not silently
    """

    def test_load_prompt_suite_valid_json(self):
        """Valid smoke_suite.json should load and return dict."""
        suite_content = {
            "version": "1.0.0",
            "prompts": {
                "short": {
                    "id": "short_smoke_v1",
                    "tier": "short",
                    "text": "Test prompt",
                }
            }
        }

        with TemporaryDirectory() as temp_dir:
            suite_path = Path(temp_dir) / "smoke_suite.json"
            with open(suite_path, "w", encoding="utf-8") as f:
                json.dump(suite_content, f)

            result = load_prompt_suite(suite_path)

            self.assertEqual(result["version"], "1.0.0")
            self.assertIn("prompts", result)
            self.assertIn("short", result["prompts"])

    def test_load_prompt_suite_file_not_found(self):
        """Missing smoke suite should raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            load_prompt_suite(Path("/nonexistent/smoke_suite.json"))

    def test_load_prompt_suite_invalid_json(self):
        """Malformed JSON should raise JSONDecodeError."""
        with TemporaryDirectory() as temp_dir:
            suite_path = Path(temp_dir) / "smoke_suite.json"
            with open(suite_path, "w", encoding="utf-8") as f:
                f.write("{not valid json")

            with self.assertRaises(json.JSONDecodeError):
                load_prompt_suite(suite_path)


class TestPromptTierExtraction(unittest.TestCase):
    """Tests for prompt tier extraction.

    Per Issue 09 requirements:
    - get_prompt_for_tier must return (text, id) tuple
    - prompt_id must be used in log records for reproducibility
    - Missing tiers must fail loudly
    """

    def setUp(self):
        """Set up test suite fixture."""
        self.suite = {
            "version": "1.0.0",
            "prompts": {
                "short": {
                    "id": "short_smoke_v1",
                    "tier": "short",
                    "text": "Short prompt text",
                },
                "medium": {
                    "id": "medium_smoke_v2",
                    "tier": "medium",
                    "text": "Medium prompt text",
                },
                "soak": {
                    "id": "soak_smoke_v1",
                    "tier": "soak",
                    "text": "Soak prompt text",
                }
            }
        }

    def test_get_prompt_for_tier_returns_text_and_id(self):
        """Should return (text, id) tuple for valid tier."""
        text, prompt_id = get_prompt_for_tier(self.suite, "short")

        self.assertEqual(text, "Short prompt text")
        self.assertEqual(prompt_id, "short_smoke_v1")

    def test_get_prompt_for_tier_versioned_id(self):
        """Prompt ID should include version for reproducibility tracking."""
        _, prompt_id = get_prompt_for_tier(self.suite, "medium")

        self.assertEqual(prompt_id, "medium_smoke_v2")
        # Verify format: <tier>_smoke_v<version>
        self.assertTrue(prompt_id.startswith("medium_smoke_v"))

    def test_get_prompt_for_tier_missing_tier_raises(self):
        """Missing tier should raise KeyError, not return None."""
        with self.assertRaises(KeyError):
            get_prompt_for_tier(self.suite, "nonexistent")

    def test_get_prompt_for_tier_all_tiers(self):
        """Should work for all configured tiers."""
        for tier in ["short", "medium", "soak"]:
            text, prompt_id = get_prompt_for_tier(self.suite, tier)
            self.assertIsInstance(text, str)
            self.assertIsInstance(prompt_id, str)
            self.assertTrue(len(text) > 0)
            self.assertTrue(len(prompt_id) > 0)


class TestRealPromptSuiteIntegrity(unittest.TestCase):
    """Integration tests for the actual configs/prompts/smoke_suite.json file.

    These tests verify the smoke prompt suite remains clearly marked and compatible.
    """

    def setUp(self):
        """Load the actual smoke suite."""
        self.suite_path = Path("configs/prompts/smoke_suite.json")
        if not self.suite_path.exists():
            self.skipTest("Smoke suite not found")
        self.suite = load_prompt_suite(self.suite_path)

    def test_smoke_suite_has_required_tiers(self):
        """Smoke suite must have all required prompt tiers."""
        required_tiers = ["short", "medium", "long", "soak"]
        for tier in required_tiers:
            self.assertIn(tier, self.suite["prompts"], f"Missing tier: {tier}")

    def test_smoke_suite_is_marked_development_only(self):
        """Smoke suite description must reject final-evidence use."""
        self.assertEqual(
            self.suite["description"],
            "SMOKE/DEVELOPMENT ONLY. Not for final evidence. Token counts are approximate; actual counts from runtime.",
        )

    def test_smoke_suite_has_versioned_smoke_ids(self):
        """All prompts must have versioned smoke IDs (format: <tier>_smoke_v<N>)."""
        import re
        version_pattern = re.compile(r"^[a-z]+_smoke_v\d+$")

        for tier, prompt_data in self.suite["prompts"].items():
            prompt_id = prompt_data["id"]
            self.assertTrue(
                version_pattern.match(prompt_id),
                f"Prompt ID '{prompt_id}' for tier '{tier}' must match pattern '<tier>_smoke_v<N>'"
            )
            # ID should match tier
            self.assertTrue(prompt_id.startswith(f"{tier}_smoke_v"))

    def test_smoke_suite_ids_are_expected_v1_values(self):
        """Smoke prompt IDs should use the approved _smoke_v1 names."""
        expected_ids = {
            "short": "short_smoke_v1",
            "medium": "medium_smoke_v1",
            "long": "long_smoke_v1",
            "soak": "soak_smoke_v1",
        }
        for tier, expected_id in expected_ids.items():
            self.assertEqual(self.suite["prompts"][tier]["id"], expected_id)
            self.assertEqual(self.suite["prompts"][tier]["tier"], tier)

    def test_smoke_suite_ids_match_tiers(self):
        """Prompt IDs must start with their tier name."""
        for tier, prompt_data in self.suite["prompts"].items():
            prompt_id = prompt_data["id"]
            self.assertTrue(
                prompt_id.startswith(tier),
                f"Prompt ID '{prompt_id}' should start with tier '{tier}'"
            )

    def test_smoke_suite_has_non_empty_text(self):
        """All prompts must have non-empty text."""
        for tier, prompt_data in self.suite["prompts"].items():
            self.assertIn("text", prompt_data, f"Missing 'text' in tier '{tier}'")
            self.assertTrue(
                len(prompt_data["text"]) > 0,
                f"Empty text in tier '{tier}'"
            )

    def test_soak_prompt_is_fixed(self):
        """Soak prompt must be deterministic for thermal throttling measurement."""
        soak_data = self.suite["prompts"]["soak"]
        # Soak prompt should exist and have meaningful content
        self.assertIn("text", soak_data)
        self.assertTrue(len(soak_data["text"]) > 50)
        # Soak ID should be versioned
        self.assertTrue(soak_data["id"].startswith("soak_smoke_v"))

    def test_final_suite_placeholder_exists(self):
        """Final suite placeholder should be present but empty until approved."""
        final_suite_path = Path("configs/prompts/final_suite.json")
        self.assertTrue(final_suite_path.exists())
        final_suite = load_prompt_suite(final_suite_path)
        self.assertIn("reserved for the final dissertation benchmark prompts", final_suite["description"].lower())
        self.assertEqual(final_suite["prompts"], {})


class TestCliValidation(unittest.TestCase):
    """Tests for CLI fail-fast validation of reproducibility fields."""

    def test_main_exits_before_running_when_hashes_are_missing(self):
        """Real runs should exit non-zero before directory creation if hashes are missing."""
        suite = {"prompts": {"short": {"text": "Test prompt", "id": "short_smoke_v1"}}}

        with patch("client.cli.load_prompt_suite", return_value=suite) as load_suite_mock, patch(
            "client.cli.create_result_directory"
        ) as create_dir_mock, patch("client.cli.run_benchmark") as run_mock, patch(
            "sys.stderr",
            new_callable=io.StringIO,
        ), patch(
            "sys.argv",
            [
                "client.cli",
                "--node",
                "yoga",
                "--backend",
                "cpu",
                "--run-type",
                "warm",
                "--prompt-tier",
                "short",
            ],
        ):
            with self.assertRaises(SystemExit) as exc:
                cli_main()

        self.assertEqual(exc.exception.code, 1)
        load_suite_mock.assert_called_once_with(Path("configs/prompts/smoke_suite.json"))
        create_dir_mock.assert_not_called()
        run_mock.assert_not_called()


class TestMatrixCliValidation(unittest.TestCase):
    """Tests for matrix run CLI validation."""

    def test_run_matrix_requires_valid_regimes(self):
        """Matrix run should reject invalid regime values."""
        suite = {"prompts": {"short": {"text": "Test prompt", "id": "short_smoke_v1"}}}

        with patch("client.matrix.load_prompt_suite", return_value=suite) as load_suite_mock, patch(
            "sys.stderr",
            new_callable=io.StringIO,
        ), patch(
            "sys.argv",
            [
                "client.matrix",
                "--node",
                "yoga",
                "--backend",
                "cpu",
                "--regimes",
                "cold,invalid_regime",  # Invalid regime
                "--repetitions",
                "2",
                "--prompt-tier",
                "short",
                "--mock",  # Use mock to avoid hash validation
            ],
        ):
            with self.assertRaises(SystemExit) as exc:
                matrix_main()

        self.assertEqual(exc.exception.code, 1)
        load_suite_mock.assert_called_once_with(Path("configs/prompts/smoke_suite.json"))

    def test_run_matrix_dry_run_succeeds(self):
        """Matrix dry run should succeed without server connection."""
        suite = {"prompts": {"short": {"text": "Test prompt", "id": "short_smoke_v1"}}}

        with patch("client.matrix.load_prompt_suite", return_value=suite) as load_suite_mock, patch(
            "client.matrix.create_matrix_output_directory"
        ) as create_dir_mock, patch(
            "client.matrix.run_matrix"
        ) as run_matrix_mock, patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ), patch(
            "sys.argv",
            [
                "client.matrix",
                "--node",
                "yoga",
                "--backend",
                "cpu",
                "--regimes",
                "cold,warm",
                "--repetitions",
                "2",
                "--prompt-tier",
                "short",
                "--dry-run",
                "--mock",  # Use mock to avoid hash validation
            ],
        ):
            create_dir_mock.return_value = Path("results/test_matrix_run")
            run_matrix_mock.return_value = []
            # Should not exit with error
            try:
                matrix_main()
            except SystemExit as e:
                self.fail(f"Dry run should not exit with error, got code {e.code}")

        load_suite_mock.assert_called_once_with(Path("configs/prompts/smoke_suite.json"))
        create_dir_mock.assert_called_once()
        requested_output_dir = create_dir_mock.call_args[0][1]
        self.assertRegex(
            str(requested_output_dir).replace("\\", "/"),
            r"^results/\d{8}_\d{6}_yoga_cpu_matrix$",
        )


if __name__ == "__main__":
    unittest.main()

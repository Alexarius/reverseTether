"""Tests for benchmark CLI validation behavior."""

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from client.cli import (
    get_prompt_for_tier,
    load_prompt_suite,
    main as cli_main,
    validate_prompt_suite,
)
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
            "suite_type": "smoke",
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


class TestPromptSuiteValidation(unittest.TestCase):
    """Tests for prompt suite structural validation."""

    def _valid_final_suite(self):
        prompts = {}
        for tier, count in [("short", 5), ("medium", 5), ("long", 5), ("soak", 1)]:
            for index in range(1, count + 1):
                prompt_key = f"final_{tier}_{index}"
                prompts[prompt_key] = {
                    "id": prompt_key,
                    "tier": tier,
                    "text": f"{tier} prompt {index}",
                    "fixture_prompt_token_count": index,
                }

        return {
            "version": "1.0.0",
            "suite_type": "final_dataset",
            "dataset_metadata": {"status": "stub"},
            "prompts": prompts,
        }

    def test_valid_smoke_suite_passes(self):
        """Valid smoke suite should pass validation."""
        suite = {
            "suite_type": "smoke",
            "prompts": {
                "short": {
                    "id": "short_smoke_v1",
                    "text": "Short prompt text",
                }
            },
        }

        validate_prompt_suite(suite)

    def test_valid_final_suite_passes(self):
        """Valid final dataset suite should pass validation."""
        validate_prompt_suite(self._valid_final_suite())

    def test_duplicate_ids_fail_loudly(self):
        """Duplicate prompt IDs should fail validation."""
        suite = {
            "suite_type": "smoke",
            "prompts": {
                "short": {"id": "duplicate_id", "text": "Short prompt"},
                "medium": {"id": "duplicate_id", "text": "Medium prompt"},
            },
        }

        with self.assertRaisesRegex(ValueError, "Duplicate prompt id"):
            validate_prompt_suite(suite)

    def test_missing_text_fails_loudly(self):
        """Prompts missing text should fail validation."""
        suite = {
            "suite_type": "smoke",
            "prompts": {
                "short": {"id": "short_smoke_v1"},
            },
        }

        with self.assertRaisesRegex(ValueError, "text"):
            validate_prompt_suite(suite)

    def test_final_suite_missing_fixture_token_count_fails_loudly(self):
        """Final dataset prompts must include fixture token counts."""
        suite = self._valid_final_suite()
        del suite["prompts"]["final_short_1"]["fixture_prompt_token_count"]

        with self.assertRaisesRegex(ValueError, "fixture_prompt_token_count"):
            validate_prompt_suite(suite)

    def test_final_suite_incorrect_bucket_counts_fails_loudly(self):
        """Final dataset suite must enforce exact tier bucket counts."""
        suite = self._valid_final_suite()
        suite["prompts"]["final_short_1"]["tier"] = "medium"

        with self.assertRaisesRegex(ValueError, "bucket counts"):
            validate_prompt_suite(suite)


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
            "suite_type": "smoke",
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

    def test_get_prompt_for_tier_matches_prompt_tier_when_key_differs(self):
        """Should find the first prompt with a matching tier when keys are fixture IDs."""
        suite = {
            "version": "1.0.0",
            "suite_type": "final_dataset",
            "prompts": {
                "final_short_stub_01": {
                    "id": "final_short_stub_01",
                    "tier": "short",
                    "text": "First short prompt",
                },
                "final_short_stub_02": {
                    "id": "final_short_stub_02",
                    "tier": "short",
                    "text": "Second short prompt",
                },
            },
        }

        text, prompt_id = get_prompt_for_tier(suite, "short")

        self.assertEqual(text, "First short prompt")
        self.assertEqual(prompt_id, "final_short_stub_01")

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

    def test_smoke_suite_has_smoke_suite_type(self):
        """Smoke suite must be explicitly marked as smoke."""
        self.assertEqual(self.suite["suite_type"], "smoke")

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

    def test_final_suite_exists_with_approved_bucket_structure(self):
        """Final suite should be present with approved bucket structure."""
        final_suite_path = Path("configs/prompts/final_suite.json")
        self.assertTrue(final_suite_path.exists())
        final_suite = load_prompt_suite(final_suite_path)
        self.assertEqual(final_suite["suite_type"], "final_dataset")
        self.assertIn("dataset_metadata", final_suite)
        self.assertEqual(len(final_suite["prompts"]), 16)

        bucket_counts = {"short": 0, "medium": 0, "long": 0, "soak": 0}
        for prompt_data in final_suite["prompts"].values():
            bucket_counts[prompt_data["tier"]] += 1
            self.assertIs(type(prompt_data["fixture_prompt_token_count"]), int)

        self.assertEqual(bucket_counts, {"short": 5, "medium": 5, "long": 5, "soak": 1})

    def test_final_suite_has_final_metadata(self):
        """Final suite metadata should mark the fixture as approved final content."""
        final_suite = load_prompt_suite(Path("configs/prompts/final_suite.json"))
        self.assertEqual(
            final_suite["dataset_metadata"],
            {
                "status": "final",
                "approval_state": "content approved; ready for final evidence",
                "fixture_prompt_token_count_method": (
                    "precomputed via Llama-3.2-1B-Instruct tokenizer"
                ),
                "notes": "Dataset derived from CNN/DailyMail. Fixed offline.",
            },
        )
        self.assertNotIn("stub", final_suite["description"].lower())

    def test_final_suite_schema_shape_is_unchanged(self):
        """Final suite must not add fields beyond the approved prompt schema."""
        final_suite = load_prompt_suite(Path("configs/prompts/final_suite.json"))
        self.assertEqual(
            set(final_suite),
            {"version", "suite_type", "description", "dataset_metadata", "prompts"},
        )
        self.assertEqual(
            set(final_suite["dataset_metadata"]),
            {
                "status",
                "approval_state",
                "fixture_prompt_token_count_method",
                "notes",
            },
        )
        for prompt_data in final_suite["prompts"].values():
            self.assertEqual(
                set(prompt_data),
                {"id", "tier", "fixture_prompt_token_count", "description", "text"},
            )

    def test_final_suite_prompt_ids_and_token_count_bands(self):
        """Final prompts should be versioned, distinct, and near approved token bands."""
        import re

        final_suite = load_prompt_suite(Path("configs/prompts/final_suite.json"))
        id_pattern = re.compile(r"^final_(short|medium|long|soak)_\d{2}$")
        count_ranges = {
            "short": (40, 70),
            "medium": (450, 550),
            "long": (1400, 1550),
            "soak": (100, 140),
        }
        texts = []

        for prompt_key, prompt_data in final_suite["prompts"].items():
            prompt_id = prompt_data["id"]
            tier = prompt_data["tier"]
            count = prompt_data["fixture_prompt_token_count"]
            low, high = count_ranges[tier]
            self.assertEqual(prompt_key, prompt_id)
            self.assertRegex(prompt_id, id_pattern)
            self.assertGreaterEqual(count, low)
            self.assertLessEqual(count, high)
            self.assertNotIn("stub", prompt_data["description"].lower())
            self.assertNotIn("stub", prompt_data["text"].lower())
            texts.append(prompt_data["text"])

        self.assertEqual(len(texts), len(set(texts)))

    def test_final_suite_prompt_patterns(self):
        """Final prompts should match the approved tier-specific text patterns."""
        final_suite = load_prompt_suite(Path("configs/prompts/final_suite.json"))
        medium_instruction = (
            "Summarize the main arguments and identify two key individuals mentioned "
            "in the article above."
        )
        long_instruction = (
            "Provide a detailed review of the text above, extract the main invariants, "
            "risks, and summarize the outcome."
        )
        soak_instruction = (
            "Summarize the key benefits and timeline mentioned in this excerpt."
        )

        for prompt_data in final_suite["prompts"].values():
            text = prompt_data["text"]
            if prompt_data["tier"] == "short":
                self.assertTrue(text.startswith("Summarize this event: "))
            elif prompt_data["tier"] == "medium":
                self.assertTrue(text.endswith(medium_instruction))
            elif prompt_data["tier"] == "long":
                self.assertTrue(text.endswith(long_instruction))
            elif prompt_data["tier"] == "soak":
                self.assertTrue(text.startswith("The following is a news excerpt. "))
                self.assertTrue(text.endswith(soak_instruction))

    def test_temporary_tokenizer_helper_not_committed(self):
        """Temporary tokenizer code and dependencies must not remain in the harness."""
        self.assertFalse(Path("scripts/precompute_tokens.py").exists())
        requirements = Path("requirements.txt").read_text(encoding="utf-8").lower()
        self.assertNotIn("transformers", requirements)


class TestCliValidation(unittest.TestCase):
    """Tests for CLI fail-fast validation of reproducibility fields."""

    def test_main_exits_before_running_when_hashes_are_missing(self):
        """Real runs should exit non-zero before directory creation if hashes are missing."""
        suite = {
            "suite_type": "smoke",
            "prompts": {"short": {"text": "Test prompt", "id": "short_smoke_v1"}},
        }

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
        suite = {
            "suite_type": "smoke",
            "prompts": {"short": {"text": "Test prompt", "id": "short_smoke_v1"}},
        }

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
        suite = {
            "suite_type": "smoke",
            "prompts": {"short": {"text": "Test prompt", "id": "short_smoke_v1"}},
        }

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

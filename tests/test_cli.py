"""Tests for benchmark CLI validation behavior."""

import io
import unittest
from pathlib import Path
from unittest.mock import patch

from client.cli import main as cli_main
from client.matrix import main as matrix_main


class TestCliValidation(unittest.TestCase):
    """Tests for CLI fail-fast validation of reproducibility fields."""

    def test_main_exits_before_running_when_hashes_are_missing(self):
        """Real runs should exit non-zero before directory creation if hashes are missing."""
        suite = {"prompts": {"short": {"text": "Test prompt", "id": "short_v1"}}}

        with patch("client.cli.load_prompt_suite", return_value=suite), patch(
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
        create_dir_mock.assert_not_called()
        run_mock.assert_not_called()


class TestMatrixCliValidation(unittest.TestCase):
    """Tests for matrix run CLI validation."""

    def test_run_matrix_requires_valid_regimes(self):
        """Matrix run should reject invalid regime values."""
        suite = {"prompts": {"short": {"text": "Test prompt", "id": "short_v1"}}}

        with patch("client.matrix.load_prompt_suite", return_value=suite), patch(
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

    def test_run_matrix_dry_run_succeeds(self):
        """Matrix dry run should succeed without server connection."""
        suite = {"prompts": {"short": {"text": "Test prompt", "id": "short_v1"}}}

        with patch("client.matrix.load_prompt_suite", return_value=suite), patch(
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


if __name__ == "__main__":
    unittest.main()

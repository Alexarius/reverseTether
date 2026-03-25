"""Tests for benchmark CLI validation behavior."""

import io
import unittest
from unittest.mock import patch

from client.cli import main


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
                main()

        self.assertEqual(exc.exception.code, 1)
        create_dir_mock.assert_not_called()
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()

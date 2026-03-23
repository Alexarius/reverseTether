"""Tests for preflight ADB and server health checks."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

import requests

from client.preflight import (
    PreflightResult,
    check_adb_device,
    check_adb_forward,
    check_server_health,
    has_exact_forward_mapping,
    main,
    run_preflight,
)


class TestCheckAdbDevice(unittest.TestCase):
    """Tests for ADB device connectivity check."""

    def test_device_connected(self):
        """Should return True when device is connected."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\nABC123\tdevice\n"

        with patch("client.preflight.subprocess.run", return_value=mock_result):
            success, error = check_adb_device()

        self.assertTrue(success)
        self.assertIsNone(error)

    def test_no_device(self):
        """Should return False with error when no device found."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\n"

        with patch("client.preflight.subprocess.run", return_value=mock_result):
            success, error = check_adb_device()

        self.assertFalse(success)
        self.assertEqual(error, "ADB device offline or not found.")

    def test_device_offline(self):
        """Should return False when device is offline."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\nABC123\toffline\n"

        with patch("client.preflight.subprocess.run", return_value=mock_result):
            success, error = check_adb_device()

        self.assertFalse(success)
        self.assertEqual(error, "ADB device offline or not found.")

    def test_adb_not_found(self):
        """Should return False when ADB is not installed."""
        with patch(
            "client.preflight.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            success, error = check_adb_device()

        self.assertFalse(success)
        self.assertIn("ADB not found", error)

    def test_adb_timeout(self):
        """Should return False when ADB command times out."""
        with patch(
            "client.preflight.subprocess.run",
            side_effect=subprocess.TimeoutExpired("adb", 10),
        ):
            success, error = check_adb_device()

        self.assertFalse(success)
        self.assertIn("timed out", error)


class TestCheckAdbForward(unittest.TestCase):
    """Tests for ADB port forwarding check."""

    def test_exact_mapping_detected_with_serial(self):
        """Should match the exact forwarding tuple in three-column adb output."""
        self.assertTrue(has_exact_forward_mapping("ABC123 tcp:8080 tcp:8080\n"))

    def test_exact_mapping_detected_without_serial(self):
        """Should also accept two-column local/remote output."""
        self.assertTrue(has_exact_forward_mapping("tcp:8080 tcp:8080\n"))

    def test_exact_mapping_rejects_wrong_remote(self):
        """Should reject matches where only the local side is tcp:8080."""
        self.assertFalse(has_exact_forward_mapping("ABC123 tcp:8080 tcp:9090\n"))

    def test_forward_active(self):
        """Should return True when port forwarding is active."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ABC123 tcp:8080 tcp:8080\n"

        with patch("client.preflight.subprocess.run", return_value=mock_result):
            success, error = check_adb_forward()

        self.assertTrue(success)
        self.assertIsNone(error)

    def test_forward_not_active(self):
        """Should return False when no forwarding rule exists."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("client.preflight.subprocess.run", return_value=mock_result):
            success, error = check_adb_forward()

        self.assertFalse(success)
        self.assertIn("Port forwarding not active", error)

    def test_different_port_forwarded(self):
        """Should return False when different port is forwarded."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ABC123 tcp:9090 tcp:9090\n"

        with patch("client.preflight.subprocess.run", return_value=mock_result):
            success, error = check_adb_forward()

        self.assertFalse(success)
        self.assertIn("Port forwarding not active", error)

    def test_same_local_port_but_wrong_remote_port_fails(self):
        """Should return False when local port matches but remote port does not."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ABC123 tcp:8080 tcp:9090\n"

        with patch("client.preflight.subprocess.run", return_value=mock_result):
            success, error = check_adb_forward()

        self.assertFalse(success)
        self.assertIn("Port forwarding not active", error)


class TestCheckServerHealth(unittest.TestCase):
    """Tests for server health endpoint check."""

    def test_server_healthy(self):
        """Should return True when server returns 200 OK."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        with patch("client.preflight.requests.Session", return_value=mock_session):
            success, error = check_server_health()

        self.assertTrue(success)
        self.assertIsNone(error)
        mock_session.close.assert_called_once()

    def test_server_unhealthy_status(self):
        """Should return False when server returns non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        with patch("client.preflight.requests.Session", return_value=mock_session):
            success, error = check_server_health()

        self.assertFalse(success)
        self.assertIn("HTTP 500", error)
        mock_session.close.assert_called_once()

    def test_connection_refused(self):
        """Should return descriptive error when connection is refused."""
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError()

        with patch("client.preflight.requests.Session", return_value=mock_session):
            success, error = check_server_health()

        self.assertFalse(success)
        self.assertIn("Connection refused", error)
        self.assertIn("llama.cpp server running", error)
        mock_session.close.assert_called_once()

    def test_timeout(self):
        """Should return error when health check times out."""
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.Timeout()

        with patch("client.preflight.requests.Session", return_value=mock_session):
            success, error = check_server_health()

        self.assertFalse(success)
        self.assertIn("timed out", error)
        mock_session.close.assert_called_once()

    def test_session_closed_on_success(self):
        """Session must be closed to prevent connection reuse in benchmarks."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        with patch("client.preflight.requests.Session", return_value=mock_session):
            check_server_health()

        mock_session.close.assert_called_once()

    def test_session_closed_on_error(self):
        """Session must be closed even when health check fails."""
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError()

        with patch("client.preflight.requests.Session", return_value=mock_session):
            check_server_health()

        mock_session.close.assert_called_once()


class TestRunPreflight(unittest.TestCase):
    """Tests for full preflight sequence."""

    def test_all_checks_pass(self):
        """Should return successful result when all checks pass."""
        with patch("client.preflight.check_adb_device", return_value=(True, None)), \
             patch("client.preflight.check_adb_forward", return_value=(True, None)), \
             patch("client.preflight.check_server_health", return_value=(True, None)):

            result = run_preflight()

        self.assertTrue(result.adb_connected)
        self.assertTrue(result.port_forwarded)
        self.assertTrue(result.server_healthy)
        self.assertIsNone(result.error_message)

    def test_adb_device_fails(self):
        """Should fail early when ADB device check fails."""
        with patch(
            "client.preflight.check_adb_device",
            return_value=(False, "ADB device offline or not found."),
        ), patch("client.preflight.check_adb_forward") as mock_forward, \
           patch("client.preflight.check_server_health") as mock_health:

            result = run_preflight()

        self.assertFalse(result.adb_connected)
        self.assertFalse(result.port_forwarded)
        self.assertFalse(result.server_healthy)
        self.assertEqual(result.error_message, "ADB device offline or not found.")

        # Subsequent checks should not be called
        mock_forward.assert_not_called()
        mock_health.assert_not_called()

    def test_port_forward_fails(self):
        """Should fail when port forwarding check fails."""
        with patch("client.preflight.check_adb_device", return_value=(True, None)), \
             patch(
                 "client.preflight.check_adb_forward",
                 return_value=(False, "Port forwarding not active."),
             ), \
             patch("client.preflight.check_server_health") as mock_health:

            result = run_preflight()

        self.assertTrue(result.adb_connected)
        self.assertFalse(result.port_forwarded)
        self.assertFalse(result.server_healthy)
        self.assertEqual(result.error_message, "Port forwarding not active.")

        mock_health.assert_not_called()

    def test_server_health_fails(self):
        """Should fail when server health check fails."""
        error_msg = "Connection refused on 127.0.0.1:8080. Is the llama.cpp server running on the phone?"

        with patch("client.preflight.check_adb_device", return_value=(True, None)), \
             patch("client.preflight.check_adb_forward", return_value=(True, None)), \
             patch("client.preflight.check_server_health", return_value=(False, error_msg)):

            result = run_preflight()

        self.assertTrue(result.adb_connected)
        self.assertTrue(result.port_forwarded)
        self.assertFalse(result.server_healthy)
        self.assertEqual(result.error_message, error_msg)

    def test_skip_adb_checks(self):
        """Should skip ADB checks when skip_adb=True."""
        with patch("client.preflight.check_adb_device") as mock_device, \
             patch("client.preflight.check_adb_forward") as mock_forward, \
             patch("client.preflight.check_server_health", return_value=(True, None)):

            result = run_preflight(skip_adb=True)

        self.assertTrue(result.adb_connected)
        self.assertTrue(result.port_forwarded)
        self.assertTrue(result.server_healthy)
        self.assertIsNone(result.error_message)

        # ADB checks should not be called
        mock_device.assert_not_called()
        mock_forward.assert_not_called()

    def test_custom_host_port(self):
        """Should pass custom host and port to health check."""
        with patch("client.preflight.check_adb_device", return_value=(True, None)), \
             patch("client.preflight.check_adb_forward", return_value=(True, None)), \
             patch("client.preflight.check_server_health", return_value=(True, None)) as mock_health:

            run_preflight(host="192.168.1.100", port=9090)

        mock_health.assert_called_once_with("192.168.1.100", 9090)


class TestMain(unittest.TestCase):
    """Tests for standalone preflight CLI entry point."""

    def test_main_exits_zero_when_server_is_healthy(self):
        """Standalone main should succeed when all checks pass."""
        with patch(
            "client.preflight.run_preflight",
            return_value=PreflightResult(True, True, True, None),
        ), patch("client.preflight.print_preflight_result") as mock_print, \
             patch("sys.argv", ["client.preflight"]):
            main()

        mock_print.assert_called_once()

    def test_main_exits_one_when_server_is_unhealthy(self):
        """Standalone main should exit non-zero on preflight failure."""
        with patch(
            "client.preflight.run_preflight",
            return_value=PreflightResult(True, True, False, "server down"),
        ), patch("client.preflight.print_preflight_result"), \
             patch("sys.argv", ["client.preflight"]):
            with self.assertRaises(SystemExit) as exc:
                main()

        self.assertEqual(exc.exception.code, 1)


if __name__ == "__main__":
    unittest.main()

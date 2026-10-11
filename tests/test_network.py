"""
Unit tests — Network / connectivity module.
"""

from unittest.mock import patch

import pytest

from flashdock.core.network import NetworkMonitor, check_connectivity


class TestCheckConnectivity:
    """Test the synchronous check_connectivity() function."""

    @patch("flashdock.core.network.urlopen")
    def test_returns_true_on_204(self, mock_urlopen):
        mock_resp = mock_urlopen.return_value.__enter__.return_value
        mock_resp.status = 204
        assert check_connectivity(timeout=1) is True

    @patch("flashdock.core.network.urlopen")
    def test_returns_true_on_200(self, mock_urlopen):
        mock_resp = mock_urlopen.return_value.__enter__.return_value
        mock_resp.status = 200
        assert check_connectivity(timeout=1) is True

    @patch("flashdock.core.network.urlopen", side_effect=OSError("no network"))
    def test_returns_false_on_error(self, mock_urlopen):
        assert check_connectivity(timeout=1) is False


class TestNetworkMonitor:
    def test_initial_state_is_offline(self):
        mon = NetworkMonitor(interval=60)
        assert mon.is_online is False

    def test_status_label(self):
        mon = NetworkMonitor()
        assert mon.status_label == "Offline"
        mon.is_online = True
        assert mon.status_label == "Online"

    @patch("flashdock.core.network.check_connectivity", return_value=True)
    def test_check_now(self, mock_check):
        mon = NetworkMonitor()
        result = mon.check_now()
        assert result is True
        assert mon.is_online is True

    @patch("flashdock.core.network.check_connectivity", return_value=True)
    def test_on_change_callback_called(self, mock_check):
        called = []
        mon = NetworkMonitor(on_change=lambda online: called.append(online))
        mon.check_now()
        assert True in called

    @patch("flashdock.core.network.check_connectivity", return_value=False)
    def test_no_callback_when_state_unchanged(self, mock_check):
        called = []
        mon = NetworkMonitor(on_change=lambda online: called.append(online))
        # Initial state is already False, so no change
        mon.check_now()
        assert len(called) == 0

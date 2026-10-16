from unittest.mock import MagicMock, patch
import pytest
import requests

from p2p_network.p2p_client import P2PClient
from p2p_network.peer_manager import PeerManager

@pytest.fixture
def mock_peer_manager():
    """Erstellt einen Mock-PeerManager, um Aufrufe von add_peer zu prüfen."""
    pm = MagicMock(spec=PeerManager)
    pm.get_all_peers.return_value = ["192.168.1.10:5000"]
    return pm

@pytest.fixture
def p2p_client(mock_peer_manager):
    """Erstellt einen P2PClient mit eigener Adresse und gemocktem PeerManager."""
    client = P2PClient("172.0.0.1:5000", peer_manager=mock_peer_manager)
    return client

@patch('p2p_network.p2p_client.requests.get')
def test_bootstrap_success_and_filtering(mock_requests_get, p2p_client, mock_peer_manager):
    """Testet, ob Peers erfolgreich geladen und die eigene Adresse herausgefiltert wird."""
    
    # Wir simulieren das Antwort-Objekt von requests.get
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"peers": ["172.0.0.1:5000", "192.168.1.10:5000", "192.168.1.20:5000"]}
    
    # Wenn requests.get aufgerufen wird, geben wir das gemockte Response-Objekt zurück
    mock_requests_get.return_value = mock_response

    # Methode ausführen
    p2p_client.bootstrap()

    # Prüfen, ob die fremden Peers hinzugefügt wurden
    mock_peer_manager.add_peer.assert_any_call("192.168.1.10:5000")
    mock_peer_manager.add_peer.assert_any_call("192.168.1.20:5000")
    
    # Sicherstellen, dass die eigene Adresse ("localhost:5000") nicht per add_peer hinzugefügt wurde
    for call in mock_peer_manager.add_peer.call_args_list:
        assert "localhost:5000" not in call[0][0]


def test_request_success(p2p_client, mock_peer_manager):
    """Testet einen erfolgreichen HTTP-Request."""
    with patch("p2p_network.p2p_client.requests.request") as mock_req:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_req.return_value = mock_response

        response = p2p_client.request("192.168.1.50:5000", "GET", "/chain")

        assert response.status_code == 200
        mock_req.assert_called_once_with("GET", "http://192.168.1.50:5000/chain", timeout=3)
        mock_peer_manager.mark_peer_dead.assert_not_called()


def test_request_server_error_500(p2p_client, mock_peer_manager):
    """Testet, ob ein Statuscode >= 500 den Peer als tot markiert und None zurückgibt."""
    with patch("p2p_network.p2p_client.requests.request") as mock_req:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_req.return_value = mock_response

        response = p2p_client.request("192.168.1.50:5000", "POST", "/sync/peers")

        assert response is None
        mock_peer_manager.mark_peer_dead.assert_called_once_with("192.168.1.50:5000")


def test_request_connection_exception(p2p_client, mock_peer_manager):
    """Testet, ob eine Exception (z. B. Timeout) den Peer als tot markiert und None zurückgibt."""
    with patch("p2p_network.p2p_client.requests.request") as mock_req:
        mock_req.side_effect = requests.exceptions.ConnectTimeout("Verbindung fehlgeschlagen")

        response = p2p_client.request("192.168.1.50:5000", "GET", "/chain")

        assert response is None
        mock_peer_manager.mark_peer_dead.assert_called_once_with("192.168.1.50:5000")
# test_p2p_server.py

import json
from p2p_network.util import json_response

import requests
import pytest
from unittest.mock import patch, MagicMock
from app import create_app

@pytest.fixture
def p2p_server_env():
    """Erstellt eine isolierte Testumgebung über die Application Factory."""
    # App im Test-Modus erzeugen
    app = create_app({
        "TESTING": True,
        "PROPAGATE_EXCEPTIONS": True  # <--- Das sorgt dafür, dass echte Exceptions direkt in Pytest landen!
        })

    # Die Instanzen hängen dank deines Factory-Musters direkt an der App!
    peer_manager = app.peer_manager
    p2p_server = app.p2p_server
      
    return p2p_server, peer_manager, app.test_client() 


def test_publish_some_peer_ips(p2p_server_env):
    """Testet den Endpunkt, der die bekannten Peers ausgibt."""
    p2p_server, peer_manager, test_client = p2p_server_env
    peer_manager.add_peer("192.168.1.50:5000")
    
    # Test-Client von Flask nutzen, um den Endpunkt aufzurufen
    response = test_client.get('/peers')
    assert response.status_code == 200
    
    # JSON-Antwort parsen
    data = json.loads(response.data.decode('utf-8'))
    
    # Prüfen, ob der erwartete Key im JSON vorhanden ist und die IP übereinstimmt
    server_ip = data.get("peer_ip")
    assert server_ip == peer_manager.own_address, f"Erwartete IP: {peer_manager.own_address}, aber erhalten: {server_ip}"
    
    # Optional: Gleich noch prüfen, ob das known_peers-Feld als Liste existiert
    assert "known_peers" in data
    assert isinstance(data["known_peers"], list)

def test_sync_peers(p2p_server_env):
    # Test des POST /sync/peers-Endpunkts
    p2p_server, peer_manager, test_client = p2p_server_env
       

    # Vorbereitung: Der Server kennt bereits einen Peer, den der Client gleich NICHT mitschickt
    peer_manager.add_peer("172.18.0.50:5000")


    # "172.18.0.99:5000" ist ein bekannter Peer, dessen Adresse er mögicherweise vom Bootstrap-Server erhalten hat (falls dieser lief),
    # "172.18.0.100:5000" ist ein neuer Peer, den er noch nicht kennt.
    response_post = test_client.post('/sync/peers', json={
        "peers": ["172.18.0.99:5000","172.18.0.100:5000"]   
    })
    assert response_post.status_code == 200
    data_post = json.loads(response_post.data.decode('utf-8'))
    
    server_ip = data_post.get("peer_ip")
    assert server_ip == peer_manager.own_address, f"Erwartete IP: {peer_manager.own_address}, aber erhalten: {server_ip}"

    print(f"Erhaltene diff_peers: {data_post.get('diff_peers')}")
    assert data_post.get("diff_peers") == ["172.18.0.50:5000"], \
        f"Erwartete diff_peers: ['172.18.0.50:5000'], aber erhalten: " + str(data_post.get("diff_peers")) 


def test_background_peers_sync_success(p2p_server_env):
    """Testet, ob neue Peers aus dem Diff während des Hintergrund-Syncs erfolgreich übernommen werden."""
    p2p_server, peer_manager, test_client = p2p_server_env

    peer_manager.get_all_peers().clear()
    peer_manager.add_peer("172.18.0.99:5000")

    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"diff_peers": ["172.18.0.88:5000"]}

    with patch("p2p_network.p2p_client.P2PClient.request", return_value=mock_response):
        p2p_server._background_peers_sync()

    assert "172.18.0.88:5000" in peer_manager.get_all_peers()
    assert "172.18.0.99:5000" in peer_manager.get_all_peers()

def test_background_peers_sync_failure_removes_peer(p2p_server_env):
    """Testet, ob ein Peer nach einem Fehlversuch sofort in den Cooldown/Quarantäne wandert."""
    p2p_server, peer_manager, test_client = p2p_server_env

    peer_manager.get_all_peers().clear()
    peer_manager.add_peer("172.18.0.99:5000")

   # Simulieren eines Connection-Timeouts beim Client-Request
    with patch("p2p_network.p2p_client.P2PClient.request", side_effect=requests.exceptions.ConnectTimeout("Timeout")):
        p2p_server._background_peers_sync()

    # Nach dem Fehlversuch muss der Peer im Quarantäne-Cooldown sein / aus der Liste fliegen
    assert "172.18.0.99:5000" not in peer_manager.get_all_peers()


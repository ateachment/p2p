"""
File: test_publishSomePeerIPs.py
Tests for the publishSomePeerIPs module.
"""

import json
import socket
import publishSomePeerIPs
from publishSomePeerIPs import app
import requests
import pytest
from unittest.mock import patch, MagicMock

# Eigene IP-Adresse einmalig beim Start ermitteln (global), bleibt dann konstant, da sich die IP-Adresse während der Laufzeit nicht ändert.
MY_IP = socket.gethostbyname(socket.gethostname())
MY_PORT = 5000
MY_ADDRESS = f"{MY_IP}:{MY_PORT}"


@pytest.fixture(autouse=True)
def reset_state():
    """Setzt globale Variablen vor jedem Test zurück, um Seiteneffekte zu vermeiden."""
    publishSomePeerIPs.known_peers = set()
    if hasattr(publishSomePeerIPs, "peer_failure_counts"):
        publishSomePeerIPs.peer_failure_counts.clear()
    yield

def test_publish_some_peer_ips():
    # Test-Client von Flask nutzen, um den Endpunkt aufzurufen
    response = app.test_client().get('/')
    assert response.status_code == 200
    
    # JSON-Antwort parsen
    data = json.loads(response.data.decode('utf-8'))
    
    # Prüfen, ob der erwartete Key im JSON vorhanden ist und die IP übereinstimmt
    server_ip = data.get("peer_ip")
    assert server_ip == MY_ADDRESS, f"Erwartete IP: {MY_ADDRESS}, aber erhalten: {server_ip}"
    
    # Optional: Gleich noch prüfen, ob das known_peers-Feld als Liste existiert
    assert "known_peers" in data
    assert isinstance(data["known_peers"], list)

def test_sync_peers():
    # Test des POST /sync/peers-Endpunkts

    # Vorbereitung: Der Server kennt bereits einen Peer, den der Client gleich NICHT mitschickt
    publishSomePeerIPs.known_peers.add("172.18.0.50:5000")

    # "172.18.0.99:5000" ist ein bekannter Peer, dessen Adresse er mögicherweise vom Bootstrap-Server erhalten hat (falls dieser lief),
    # "172.18.0.100:5000" ist ein neuer Peer, den er noch nicht kennt.
    response_post = app.test_client().post('/sync/peers', json={
        "peers": ["172.18.0.99:5000","172.18.0.100:5000"]   
    })
    assert response_post.status_code == 200
    data_post = json.loads(response_post.data.decode('utf-8'))
    
    server_ip = data_post.get("peer_ip")
    assert server_ip == MY_ADDRESS, f"Erwartete IP: {MY_ADDRESS}, aber erhalten: {server_ip}"

    print(f"Erhaltene diff_peers: {data_post.get('diff_peers')}")
    assert data_post.get("diff_peers") == ["172.18.0.50:5000"], \
        f"Erwartete diff_peers: ['172.18.0.50:5000'], aber erhalten: " + str(data_post.get("diff_peers")) 


def test_background_sync_success():
    """Testet, ob neue Peers aus dem Diff während des Hintergrund-Syncs erfolgreich übernommen werden."""
    publishSomePeerIPs.known_peers = {"172.18.0.99:5000"}
    #publishSomePeerIPs.MY_ADDRESS = "172.18.0.2:5000"  # Explizit eine andere IP
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"diff_peers": ["172.18.0.88:5000"]}

    # side_effect=[None, InterruptedError]: 
    # 1. Aufruf von time.sleep tut nichts (Schleife läuft los und macht den Request).
    # 2. Aufruf von time.sleep (beim nächsten Takt) bricht dann mit InterruptedError ab.
    with patch("publishSomePeerIPs.requests.post", return_value=mock_response) as mock_post, \
         patch("publishSomePeerIPs.time.sleep", side_effect=[None, InterruptedError]):
        try:
            publishSomePeerIPs.background_sync_loop()
        except InterruptedError:
            pass

    mock_post.assert_called_once()
    assert "172.18.0.88:5000" in publishSomePeerIPs.known_peers
    assert "172.18.0.99:5000" in publishSomePeerIPs.known_peers

def test_background_sync_failure_removes_peer():
    """Testet, ob ein Peer nach MAX_FAILURES (3) Fehlversuchen im Hintergrund-Loop entfernt wird."""
    publishSomePeerIPs.known_peers = {"172.18.0.99:5000"}

    # 3 Durchläufe mit Timeout, beim 4. Mal bricht die Schleife via InterruptedError ab
    sleep_side_effect = [None, None, None, InterruptedError]

    with patch("publishSomePeerIPs.requests.post", side_effect=requests.exceptions.ConnectTimeout("Timeout")), \
         patch("publishSomePeerIPs.time.sleep", side_effect=sleep_side_effect):
        try:
            publishSomePeerIPs.background_sync_loop()
        except InterruptedError:
            pass

    assert "172.18.0.99:5000" not in publishSomePeerIPs.known_peers
    assert len(publishSomePeerIPs.known_peers) == 0


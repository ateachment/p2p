import json
import socket
from publishSomePeerIPs import app

def test_publish_some_peer_ips():
    # Test-Client von Flask nutzen, um den Endpunkt aufzurufen
    response = app.test_client().get('/')
    assert response.status_code == 200
    
    # Eigene IP des Testsystems ermitteln
    expected_ip = socket.gethostbyname(socket.gethostname())
    
    # JSON-Antwort parsen
    data = json.loads(response.data.decode('utf-8'))
    
    # Prüfen, ob der erwartete Key im JSON vorhanden ist und die IP übereinstimmt
    server_ip = data.get("peer ip")
    assert server_ip == expected_ip
    
    # Optional: Gleich noch prüfen, ob das known_peers-Feld als Liste existiert
    assert "known_peers" in data
    assert isinstance(data["known_peers"], list)

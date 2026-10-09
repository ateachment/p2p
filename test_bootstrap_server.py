import json
from bootstrap_server import app

def test_get_peers():
    # Test-Client des Bootstrap-Servers nutzen
    response = app.test_client().get('/peers')
    
    # Prüfen, ob der Statuscode 200 OK ist
    assert response.status_code == 200
    
    # JSON-Antwort parsen
    data = json.loads(response.data.decode('utf-8'))
    
    # Prüfen, ob das "peers"-Feld existiert und eine Liste ist
    assert "peers" in data
    assert isinstance(data["peers"], list)
    
    # Prüfen, ob die vordefinierten Test-IPs in der Liste enthalten sind
    peers = data["peers"]
    assert "172.18.0.2:5000" in peers
    assert "172.18.0.99:5000" in peers

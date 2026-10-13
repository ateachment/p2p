"""
File: test_blockchain_node.py
Tests for the blockchain_node module.
"""

import hashlib
import json
import socket
import blockchain_node
from blockchain_node import app, blockchain, MY_ADDRESS
import requests
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def reset_state():
    """Setzt globale Variablen vor jedem Test zurück, um Seiteneffekte zu vermeiden."""
    # 1. Netzwerk-Peers leeren
    blockchain_node.peer_manager.reset()
    
    # 2. Peer-Fehlerzähler zurücksetzen (falls global definiert)
    if hasattr(blockchain_node, "peer_failure_counts"):
        blockchain_node.peer_failure_counts.clear()
        
    # 3. Bestehende Blockchain-Instanz sauber zurücksetzen 
    blockchain_node.blockchain.__init__()

    yield

@pytest.fixture
def client():
    """Erstellt einen Flask-Testclient für die Endpunkte."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


# Testfälle für p2p-Funktionalität

@pytest.fixture
def peer_manager():
    """Pytest-Fixture, die einen frischen PeerManager bereitstellt."""
    from peer_manager import PeerManager
    return PeerManager(my_address=MY_ADDRESS)

def test_bootstrap(peer_manager, monkeypatch):
    """Testet die Bootstrap-Logik mit MagicMock für requests und Fallback-Verhalten."""
    mock_get = MagicMock()

    # Erste URL schlägt fehl (Status 500), zweite URL liefert erfolgreich Peers
    response_fail = MagicMock()
    response_fail.status_code = 500

    response_success = MagicMock()
    response_success.status_code = 200
    # Wir geben absichtlich auch die eigene IP mit, um zu prüfen, ob der PeerManager sie filtert
    response_success.json.return_value = {
        "peers": ["192.168.1.100:5000", peer_manager.my_address]
    }

    mock_get.side_effect = [response_fail, response_success]

    # Variablen im Zielmodul patchen
    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(blockchain_node, "peer_manager", peer_manager)
    monkeypatch.setattr(blockchain_node, "BOOTSTRAP_URLS", ["http://dead-server:5000", "http://good-server:5000"])
    monkeypatch.setattr(blockchain_node, "DEBUG", False)

    # Funktion ausführen
    blockchain_node.bootstrap()

    # Validierung
    peers = peer_manager.get_all_peers()
    assert "192.168.1.100:5000" in peers
    assert peer_manager.my_address not in peers
    assert len(peers) == 1
    
    # Prüfen, ob durch den Fallback genau zweimal angefragt wurde
    assert mock_get.call_count == 2

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
    blockchain_node.peer_manager.add_peer("172.18.0.50:5000")

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



def test_background_peers_sync_success():
    """Testet, ob neue Peers aus dem Diff während des Hintergrund-Syncs erfolgreich übernommen werden."""
    blockchain_node.peer_manager.get_all_peers().clear()
    blockchain_node.peer_manager.add_peer("172.18.0.99:5000")

    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"diff_peers": ["172.18.0.88:5000"]}

    with patch("blockchain_node.p2p_client.request", return_value=mock_response):
        blockchain_node.background_peers_sync()

    assert "172.18.0.88:5000" in blockchain_node.peer_manager.get_all_peers()
    assert "172.18.0.99:5000" in blockchain_node.peer_manager.get_all_peers()

def test_background_peers_sync_failure_removes_peer():
    """Testet, ob ein Peer nach einem Fehlversuch sofort in den Cooldown/Quarantäne wandert."""
    blockchain_node.peer_manager.get_all_peers().clear()
    blockchain_node.peer_manager.add_peer("172.18.0.99:5000")

   # Simulieren eines Connection-Timeouts beim Client-Request
    with patch("blockchain_node.p2p_client.request", side_effect=requests.exceptions.ConnectTimeout("Timeout")):
        blockchain_node.background_peers_sync()

    # Nach dem Fehlversuch muss der Peer im Quarantäne-Cooldown sein / aus der Liste fliegen
    assert "172.18.0.99:5000" not in blockchain_node.peer_manager.get_all_peers()

# Testfälle für Blockchain-Endpunkte

def test_initial_chain(client):
    """Testet, ob die Kette beim Start korrekt den Genesis-Block enthält."""
    response = client.get('/chain')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['length'] == 1
    assert data['chain'][0]['index'] == 0

def test_new_transaction(client):
    """Testet das Hinzufügen einer neuen Transaktion."""
    response = client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 50
    })
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'Transaktion' in data['message']

def test_mine_block(client):
    """Testet das Mining eines neuen Blocks inklusive Transaktionen und Belohnung."""
    # Erst eine Transaktion erzeugen
    client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 25
    })
    
    # Block minen
    response = client.get('/mine')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Der neue Block muss Index 1 haben (nach dem Genesis-Block)
    assert data['index'] == 1
    # Transaktionen sollten die vorherige User-Transaktion + die Miner-Belohnung enthalten
    assert len(data['transactions']) == 2
    assert data['block_hash'].startswith("0000"), f"Der Block-Hash {data['block_hash']} hat keine 4 führenden Nullen!"


def test_valid_chain_success(client):
    """Testet, ob eine intakte Kette mit Transaktionen als gültig erkannt wird."""

    client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 10
    })
    client.get('/mine')

    chain_data = [b.to_dict() for b in blockchain.chain]
    
    assert blockchain.valid_chain(chain_data) is True

def test_valid_chain_invalid_genesis1(client):
    """Testet, ob eine Kette mit manipuliertem Genesis-Block sofort abgelehnt wird."""
    
    chain_data = [b.to_dict() for b in blockchain.chain]
    # Genesis-Block Index manipulieren (muss 0 sein)
    chain_data[0]['index'] = 99
    
    assert blockchain.valid_chain(chain_data) is False

def test_valid_chain_invalid_genesis2():
    """Testet, ob hash und proof des Genesis-Blocks korrekt sind."""
    
    chain_data = [b.to_dict() for b in blockchain.chain]
    # Genesis-Block hashen und prüfen, ob er die 4 führenden Nullen hat
    genesis_hash = hashlib.sha256(json.dumps(chain_data[0], sort_keys=True).encode()).hexdigest()
    
    assert genesis_hash[:4] == "0000"

def test_valid_chain_broken_link(client):
    """Testet, ob eine Kette mit gebrochenem previous_hash abgelehnt wird."""
    client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 10
    })
    client.get('/mine')
    
    chain_data = [b.to_dict() for b in blockchain.chain]
    # Den previous_hash von Block 1 absichtlich zerstören
    chain_data[1]['previous_hash'] = "0000000000000000000000000000000000000000000000000000000000000000"
    
    assert blockchain.valid_chain(chain_data) is False

def test_valid_chain_invalid_pow(client):
    """Testet, ob ein Block ohne gelösten Proof-of-Work (keine 4 Nullen im Hash) abgelehnt wird."""
    client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 10
    })
    client.get('/mine')
    
    chain_data = [b.to_dict() for b in blockchain.chain]
    # Den Proof von Block 1 so verändern, dass der Hash keine 4 führenden Nullen hat
    chain_data[1]['proof'] = 999999  
    
    assert blockchain.valid_chain(chain_data) is False


def test_sync_replaces_chain(monkeypatch):
    """Testet, ob Blockchain.check_and_sync_with_peer die eigene Kette durch eine längere Peer-Kette ersetzt."""
    # 1. Test-Peer hinzufügen
    blockchain_node.peer_manager.add_peer('192.168.1.100:5000')

    # 2. Aktuelle Kette als Basis holen
    current_chain_dicts = [b.to_dict() for b in blockchain.chain]
    original_length = len(current_chain_dicts)

    # 3. Eine längere Fake-Kette vom Peer simulieren
    peer_chain_data = {
        'length': original_length + 1,
        'chain': current_chain_dicts + [{
            'index': original_length,
            'timestamp': 1700000000.0,
            'transactions': [],
            'proof': 12345,
            'previous_hash': blockchain.last_block.hash()
        }]
    }

    # 4. Mock-Response mit MagicMock aufbauen
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = peer_chain_data

    # 5. P2PClient und valid_chain patchen
    monkeypatch.setattr('blockchain_node.p2p_client.request', lambda peer, method, url, **kwargs: mock_response)
    monkeypatch.setattr(blockchain, 'valid_chain', lambda *args: True)

    # 6. Synchronisation als Methode auf der Blockchain ausführen
    replaced = blockchain.check_and_sync_chain_with_peer('192.168.1.100:5000')

    # Assertions
    assert replaced is True
    assert len(blockchain.chain) == original_length + 1


def test_sync_keeps_own_chain(monkeypatch):
    """Testet, ob die Kette behalten wird, wenn die Peer-Kette kürzer/gleich lang ist."""
    blockchain_node.peer_manager.add_peer('192.168.1.100:5000')

    current_chain_dicts = [b.to_dict() for b in blockchain.chain]

    # Peer liefert eine Kette mit gleicher Länge
    peer_chain_data = {
        'length': len(current_chain_dicts),
        'chain': current_chain_dicts
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = peer_chain_data

    monkeypatch.setattr('blockchain_node.requests.get', lambda url, timeout=3: mock_response)

    replaced = blockchain.check_and_sync_chain_with_peer('192.168.1.100:5000')

    # Assertions: Es wurde nichts ersetzt
    assert replaced is False
    assert len(blockchain.chain) == len(current_chain_dicts)
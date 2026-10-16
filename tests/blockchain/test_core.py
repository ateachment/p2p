# Testfälle für Blockchain-Endpunkte

import hashlib
import json
from unittest.mock import MagicMock
import pytest
from app import create_app




@pytest.fixture
def blockchain_env():
    """Erstellt eine isolierte Testumgebung über die Application Factory."""
    # App im Test-Modus erzeugen
    app = create_app({
        "TESTING": True,
        "PROPAGATE_EXCEPTIONS": True  # <--- Das sorgt dafür, dass echte Exceptions direkt in Pytest landen!
        })

    # Die Instanzen hängen dank deines Factory-Musters direkt an der App!
    blockchain = app.blockchain
    peer_manager = app.peer_manager
    
      
    return peer_manager, blockchain, app.test_client() 


def test_initial_chain(blockchain_env):
    """Testet, ob die Kette beim Start korrekt den Genesis-Block enthält."""
    peer_manager, blockchain, test_client = blockchain_env
    response = test_client.get('/chain')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['length'] == 1
    assert data['chain'][0]['index'] == 0

def test_new_transaction(blockchain_env):
    """Testet das Hinzufügen einer neuen Transaktion."""
    peer_manager, blockchain, test_client = blockchain_env
    response = test_client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 50
    })
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'Transaktion' in data['message']

def test_mine_block(blockchain_env):
    """Testet das Mining eines neuen Blocks inklusive Transaktionen und Belohnung."""
    peer_manager, blockchain, test_client = blockchain_env
    # Erst eine Transaktion erzeugen
    test_client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 25
    })
    
    # Block minen
    response = test_client.get('/mine')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Der neue Block muss Index 1 haben (nach dem Genesis-Block)
    assert data['index'] == 1
    # Transaktionen sollten die vorherige User-Transaktion + die Miner-Belohnung enthalten
    assert len(data['transactions']) == 2
    assert data['block_hash'].startswith("0000"), f"Der Block-Hash {data['block_hash']} hat keine 4 führenden Nullen!"


def test_valid_chain_success(blockchain_env):
    """Testet, ob eine intakte Kette mit Transaktionen als gültig erkannt wird."""
    peer_manager, blockchain, test_client = blockchain_env
    test_client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 10
    })
    test_client.get('/mine')

    chain_data = [b.to_dict() for b in blockchain.chain]
    
    assert blockchain.valid_chain(chain_data) is True

def test_valid_chain_invalid_genesis1(blockchain_env):
    """Testet, ob eine Kette mit manipuliertem Genesis-Block sofort abgelehnt wird."""
    peer_manager, blockchain, test_client = blockchain_env
    
    chain_data = [b.to_dict() for b in blockchain.chain]
    # Genesis-Block Index manipulieren (muss 0 sein)
    chain_data[0]['index'] = 99
    
    assert blockchain.valid_chain(chain_data) is False

def test_valid_chain_invalid_genesis2(blockchain_env):
    """Testet, ob hash und proof des Genesis-Blocks korrekt sind."""
    peer_manager, blockchain, test_client = blockchain_env
    
    chain_data = [b.to_dict() for b in blockchain.chain]
    # Genesis-Block hashen und prüfen, ob er die 4 führenden Nullen hat
    genesis_hash = hashlib.sha256(json.dumps(chain_data[0], sort_keys=True).encode()).hexdigest()
    
    assert genesis_hash[:4] == "0000"

def test_valid_chain_broken_link(blockchain_env):
    """Testet, ob eine Kette mit gebrochenem previous_hash abgelehnt wird."""
    peer_manager, blockchain, test_client = blockchain_env

    test_client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 10
    })
    test_client.get('/mine')
    
    chain_data = [b.to_dict() for b in blockchain.chain]
    # Den previous_hash von Block 1 absichtlich zerstören
    chain_data[1]['previous_hash'] = "0000000000000000000000000000000000000000000000000000000000000000"
    
    assert blockchain.valid_chain(chain_data) is False

def test_valid_chain_invalid_pow(blockchain_env):
    """Testet, ob ein Block ohne gelösten Proof-of-Work (keine 4 Nullen im Hash) abgelehnt wird."""
    peer_manager, blockchain, test_client = blockchain_env
    test_client.post('/transactions/new', json={
        'sender': 'Alice',
        'recipient': 'Bob',
        'amount': 10
    })
    test_client.get('/mine')
    
    chain_data = [b.to_dict() for b in blockchain.chain]
    # Den Proof von Block 1 so verändern, dass der Hash keine 4 führenden Nullen hat
    chain_data[1]['proof'] = 999999  
    
    assert blockchain.valid_chain(chain_data) is False


def test_sync_replaces_chain(monkeypatch, blockchain_env):
    """Testet, ob Blockchain.check_and_sync_with_peer die eigene Kette durch eine längere Peer-Kette ersetzt."""
    peer_manager, blockchain, test_client = blockchain_env
    # 1. Test-Peer hinzufügen
    peer_manager.add_peer('192.168.1.100:5000')

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
    monkeypatch.setattr('p2p_network.p2p_client.P2PClient.request', lambda *args, **kwargs: mock_response)
    monkeypatch.setattr(blockchain, 'valid_chain', lambda *args: True)

    # 6. Synchronisation als Methode auf der Blockchain ausführen
    replaced = blockchain._check_and_sync_chain_with_peer('192.168.1.100:5000')

    # Assertions
    assert replaced is True
    assert len(blockchain.chain) == original_length + 1


def test_sync_keeps_own_chain(monkeypatch, blockchain_env):
    """Testet, ob die Kette behalten wird, wenn die Peer-Kette kürzer/gleich lang ist."""
    peer_manager, blockchain, test_client = blockchain_env
    peer_manager.add_peer('192.168.1.100:5000')

    current_chain_dicts = [b.to_dict() for b in blockchain.chain]

    # Peer liefert eine Kette mit gleicher Länge
    peer_chain_data = {
        'length': len(current_chain_dicts),
        'chain': current_chain_dicts
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = peer_chain_data

    monkeypatch.setattr('p2p_network.p2p_client.P2PClient.request', lambda *args, **kwargs: mock_response)

    replaced = blockchain._check_and_sync_chain_with_peer('192.168.1.100:5000')

    # Assertions: Es wurde nichts ersetzt
    assert replaced is False
    assert len(blockchain.chain) == len(current_chain_dicts)
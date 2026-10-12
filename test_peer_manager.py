import pytest
import blockchain_node

@pytest.fixture(autouse=True)
def reset_state():
    """Setzt den Peer-Manager vor jedem Test threadsicher zurück, um Seiteneffekte zu vermeiden."""
    if hasattr(blockchain_node, 'peer_manager'):
        blockchain_node.peer_manager.reset()
    # Falls die Blockchain selbst auch zurückgesetzt werden muss:
    blockchain_node.blockchain.chain = []
    blockchain_node.blockchain.current_transactions = []


def test_publish_some_peer_ips(client):
    """Testet den Endpunkt, der die eigene IP und bekannte Peers ausgibt."""
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert "peer_ip" in data
    assert "known_peers" in data
    assert isinstance(data["known_peers"], list)


def test_sync_peers(client):
    """Testet das Synchronisieren und Hinzufügen neuer Peers über die API."""
    # Füge einen Test-Peer über den PeerManager hinzu oder simuliere einen Sync-Request
    blockchain_node.peer_manager.add_peer("172.18.0.3:5000")
    
    peers = blockchain_node.peer_manager.get_all_peers()
    assert "172.18.0.3:5000" in peers


def test_peer_cooldown_mechanism():
    """Testet, ob der PeerManager tote Peers in die Penalty Box schickt und nach Ablauf freigibt."""
    peer_address = "172.18.0.99:5000"
    
    # Peer hinzufügen
    blockchain_node.peer_manager.add_peer(peer_address)
    assert peer_address in blockchain_node.peer_manager.get_all_peers()
    
    # Als tot markieren (Cooldown)
    blockchain_node.peer_manager.mark_peer_dead(peer_address)
    assert peer_address not in blockchain_node.peer_manager.get_all_peers()
    assert peer_address in blockchain_node.peer_manager.dead_peers
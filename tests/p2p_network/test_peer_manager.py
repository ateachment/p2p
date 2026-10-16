import time
from p2p_network.peer_manager import PeerManager   
import pytest

@pytest.fixture
def peer_manager():
    """Pytest-Fixture, die einen PeerManager mit automatisch ermittelter eigener IP bereitstellt."""
    pm = PeerManager("127.0.0.1:5000")
    return pm

# --- Unit Tests ---

def test_add_peer_basic(peer_manager):
    """Testet das erfolgreiche Hinzufügen eines normalen Peers."""
    peer_manager.add_peer("192.168.1.10:5000")
    
    peers = peer_manager.get_all_peers()
    assert "192.168.1.10:5000" in peers
    assert len(peers) == 1

def test_filter_own_address(peer_manager):
    """Testet, ob die dynamisch ermittelte eigene Adresse konsequent ignoriert wird."""
    # Versuchen, die eigene Adresse (aus der Fixture) hinzuzufügen
    peer_manager.add_peer(peer_manager.own_address)
    
    # Versuchen, sich selbst über ein Update einzuschleusen
    peer_manager.update_peers([peer_manager.own_address, "192.168.1.20:5000"])
    
    peers = peer_manager.get_all_peers()
    assert peer_manager.own_address not in peers
    assert "192.168.1.20:5000" in peers
    assert len(peers) == 1

def test_mark_peer_dead(peer_manager):
    """Testet das Verschieben eines fehlerhaften Peers in die Penalty Box."""
    peer = "192.168.1.10:5000"
    
    peer_manager.add_peer(peer)
    assert peer in peer_manager.get_all_peers()

    # Als tot markieren
    peer_manager.mark_peer_dead(peer)
    assert peer not in peer_manager.get_all_peers()
    assert peer in peer_manager.dead_peers

def test_cooldown_expiration(peer_manager, monkeypatch):
    """Testet, ob Peers nach Ablauf der Cooldown-Zeit wieder freigegeben werden."""
    # Cooldown für den Test explizit setzen falls nötig, oder Standard nutzen
    peer_manager.cooldown_seconds = 60
    peer = "192.168.1.10:5000"
    
    peer_manager.add_peer(peer)
    peer_manager.mark_peer_dead(peer)
    assert peer not in peer_manager.get_all_peers()

    # Zeitreise simulieren: 61 Sekunden in die Zukunft springen
    initial_time = time.time()
    monkeypatch.setattr(time, "time", lambda: initial_time + 61.0)

    # Prüfen, ob der Peer nach Cleanup/Hinzufügen entlassen wurde
    peer_manager.add_peer(peer)
    assert peer in peer_manager.get_all_peers()
    assert peer not in peer_manager.dead_peers

def test_update_peers_bulk(peer_manager):
    """Testet die Massenaktualisierung der Peer-Liste."""
    incoming = ["192.168.1.1:5000", "192.168.1.2:5000", peer_manager.own_address]
    peer_manager.update_peers(incoming)
    
    peers = peer_manager.get_all_peers()
    assert len(peers) == 2
    assert peer_manager.own_address not in peers
    assert "192.168.1.1:5000" in peers
    assert "192.168.1.2:5000" in peers

def test_get_random_peers(peer_manager):
    """Testet die zufällige Auswahl von Peers für Gossip/Pushes."""
    peer_manager.update_peers(["p1:5000", "p2:5000", "p3:5000"])
    
    sample = peer_manager.get_random_peers(count=2)
    assert len(sample) == 2
    for p in sample:
        assert p in ["p1:5000", "p2:5000", "p3:5000"]

    all_sample = peer_manager.get_random_peers(count=10)
    assert len(all_sample) == 3

def test_dead_peer_failure_counting(peer_manager):
    """Testet, ob Fehlschläge korrekt mitgezählt werden, solange max_failures nicht erreicht ist."""
    peer_manager.max_failures = 3
    peer = "192.168.1.50:5000"
    
    peer_manager.add_peer(peer)
    assert peer in peer_manager.get_all_peers()
    
    # 1. Fehlschlag
    peer_manager.mark_peer_dead(peer)
    assert peer not in peer_manager.get_all_peers()
    assert peer in peer_manager.dead_peers
    assert peer_manager.dead_peers[peer][1] == 1  # 1. Fehler

    # Schonzeit aktiv => Fehler wird nicht hochgezählt
    peer_manager.mark_peer_dead(peer)
    assert peer not in peer_manager.get_all_peers()
    assert peer in peer_manager.dead_peers
    assert peer_manager.dead_peers[peer][1] == 1  # 1. Fehler
    
    # Da eine Schonzeit aktiv ist, müssen wir im Test den Zeitstempel künstlich zurücksetzen,
    # damit der nächste Fehlschlag nicht durch den Cooldown blockiert wird!
    # (Passe den Key/Index an, je nachdem wie du den Timestamp speicherst, z.B. peer_manager.dead_peers[peer][0])
    peer_manager.dead_peers[peer][0] = time.time() - 61  # z.B. 61 Sekunden in der Vergangenheit

    # 2. Fehlschlag (nachdem er kurz wieder aktiv war oder direkt erneut markiert)
    # Da mark_peer_dead ihn direkt aus .peers wirft, simulieren wir einen erneuten Tod:
    peer_manager.mark_peer_dead(peer)
    assert peer_manager.dead_peers[peer][1] == 2  # 2. Fehler
    assert peer in peer_manager.dead_peers  # Noch nicht evictet (max_failures = 3)

def test_peer_permanent_eviction(peer_manager):
    """Testet, ob ein Peer nach Erreichen von max_failures komplett aus der Penalty Box gelöscht wird."""
    peer_manager.max_failures = 3
    peer = "192.168.1.99:5000"
    
    peer_manager.add_peer(peer)
    
    # 3 Fehlschläge hintereinander mit Schonzeit simulieren (entspricht max_failures)
    peer_manager.mark_peer_dead(peer)  # 1
    peer_manager.dead_peers[peer][0] = time.time() - 61
    peer_manager.mark_peer_dead(peer)  # 2
    peer_manager.dead_peers[peer][0] = time.time() - 61
    peer_manager.mark_peer_dead(peer)  # 3 -> Limit erreicht!
    
    # Der Peer muss nun komplett verschwunden sein (weder aktiv noch in dead_peers)
    assert peer not in peer_manager.get_all_peers()
    assert peer not in peer_manager.dead_peers
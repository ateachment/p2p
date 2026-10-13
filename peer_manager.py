# PeerManager mit Cooldown-Mechanismus (Penalty Box)

from re import DEBUG
import time
import threading
import random

class PeerManager:
    def __init__(self, my_address, cooldown_seconds=60, max_failures=3):
        """
        Verwaltet bekannte Peers, blockiert nicht erreichbare Peers 
        (Penalty Box = dead_peers) für eine bestimmte Zeit (cooldown_seconds).
        Filtert dabei konsequent die eigene Adresse heraus.
        """
        self.my_address = my_address
        self.peers = set()                 # Aktive, erreichbare Peers
        self.dead_peers = {}               # Dictionary: { peer_address: [timestamp_when_dead, failure_count] }
        self.cooldown_seconds = cooldown_seconds
        self.max_failures = max_failures
        self.lock = threading.Lock()       # Verhindert Race Conditions bei Multithreading

    def add_peer(self, peer: str):
        """Fügt einen Peer hinzu, sofern er nicht die eigene Adresse ist und nicht im Cooldown ist."""
        with self.lock:
            self._cleanup_cooldown_unlocked()
            if peer not in self.dead_peers and peer != self.my_address:
                self.peers.add(peer)

    def mark_peer_dead(self, peer: str):
        """Setzt einen Peer in den Cooldown und entfernt ihn aus den aktiven Peers."""
        with self.lock:
            self.peers.discard(peer)
            # Prüfen, ob er schon in der Penalty Box ist
            if peer in self.dead_peers:
                timestamp, failures = self.dead_peers[peer]
                failures += 1
            else:
                failures = 1
            
            timestamp = time.time()
            
            # Prüfen ob endgültig rauswerfen
            if failures >= self.max_failures:
                if DEBUG:
                    print(f"[PeerManager] Peer {peer} nach {self.max_failures} Fehlern endgültig gelöscht.")
                self.dead_peers.pop(peer, None)
            else: # timestamp und failures updaten in dead_peers
                self.dead_peers[peer] = [timestamp, failures]

    def update_peers(self, incoming_peers):
        """
        Aktualisiert die Peer-Liste von außen (z.B. nach Sync), 
        ignoriert dabei sich selbst und die Cooldown-Peers.
        """
        with self.lock:
            self._cleanup_cooldown_unlocked()
            for peer in incoming_peers:
                if peer not in self.dead_peers and peer != self.my_address:
                    self.peers.add(peer)

    def get_all_peers(self) -> list:
        """
        Gibt eine Liste aller aktuell gültigen, aktiven Peers 
        exkl. der eigenen Adresse zurück (thread-sicher).
        """
        with self.lock:
            self._cleanup_cooldown_unlocked()
            return list(self.peers)

    def get_random_peers(self, count=2) -> list:
        """Wählt eine zufällige Menge von Peers für Unicast-Pushes aus."""
        active_peers = self.get_all_peers()
        if not active_peers:
            return []
        sample_size = min(len(active_peers), count)
        return random.sample(active_peers, sample_size)

    def cleanup_cooldown(self):
        """
        Öffentliche Methode mit Lock für externen Aufruf.
        Prüft, ob Cooldowns abgelaufen sind, und entlässt Peers aus der Penalty Box.
        """
        with self.lock:
            self._cleanup_cooldown_unlocked()

    def _cleanup_cooldown_unlocked(self):
        """
        Interne Methode OHNE Lock (verhindert Deadlocks).
        Interne Methode ohne Lock (wird von anderen Methoden aufgerufen).
        """
        now = time.time()
        expired_peers = [
            peer for peer, (timestamp, failures) in self.dead_peers.items()
            if now - timestamp > self.cooldown_seconds
        ]
        for peer in expired_peers:
            del self.dead_peers[peer]
            # Optional: Direkt wieder zu den Peers hinzufügen oder auf nächsten Sync warten
            # self.peers.add(peer)

    def reset(self):
        """Setzt alle Peers und Dead-Peers komplett zurück (für Tests)."""
        with self.lock:
            self.peers.clear()
            self.dead_peers.clear()
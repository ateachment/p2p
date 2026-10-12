# PeerManager mit Cooldown-Mechanismus (Penalty Box)

import time
import threading
import random

class PeerManager:
    def __init__(self, cooldown_seconds=60):
        """
        Verwaltet bekannte Peers und blockiert ausgefallene Peers 
        für eine bestimmte Cooldown-Zeit (Standard: 60 Sekunden).
        """
        self.peers = set()                 # Aktive, erreichbare Peers
        self.dead_peers = {}               # Dictionary: { peer_address: timestamp_when_marked_dead }
        self.cooldown_seconds = cooldown_seconds
        self.lock = threading.Lock()       # Verhindert Race Conditions bei Multithreading

    def add_peer(self, peer: str):
        """Fügt einen Peer hinzu, sofern er nicht im Cooldown ist."""
        with self.lock:
            self._cleanup_cooldown_unlocked()
            if peer not in self.dead_peers:
                self.peers.add(peer)

    def mark_peer_dead(self, peer: str):
        """Setzt einen Peer in den Cooldown (Penalty Box) und entfernt ihn aus den aktiven Peers."""
        with self.lock:
            self.peers.discard(peer)
            self.dead_peers[peer] = time.time()

    def update_peers(self, incoming_peers):
        """Aktualisiert die Peer-Liste von außen (z.B. nach Sync), ignoriert aber Cooldown-Peers."""
        with self.lock:
            self.cleanup_cooldown()
            for peer in incoming_peers:
                if peer not in self.dead_peers:
                    self.peers.add(peer)

    def get_all_peers(self) -> list:
        """Gibt eine Liste aller aktuell gültigen, aktiven Peers zurück (thread-sicher)."""
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
            peer for peer, timestamp in self.dead_peers.items()
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
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
                self.peers.add(peer)  # doppelter Eintag ist nicht möglich wegen set()

    def mark_peer_dead(self, peer: str):
        """Setzt einen Peer in den Cooldown. Verhindert das Hochzählen 
        innerhalb der Cooldown-Zeit"""
        with self.lock:
            self.peers.discard(peer)
            now = time.time()

            failures = 1
            timestamp = now

            # Prüfen, ob er schon in dead_peers war
            if peer in self.dead_peers:
                _, old_failures = self.dead_peers[peer]
            
                # Prüfen, ob die Cooldown-Zeit noch läuft
                if now - timestamp < self.cooldown_seconds:
                    # Innerhalb des Cooldowns: Ignorieren, kein Zähler-Update, kein neuer Zeitstempel!
                    return
                else:
                    # Cooldown ist abgelaufen, aber er schlägt wieder fehl -> Zähler erhöhen
                    failures = old_failures + 1
            else:
                # Erster Fehler überhaupt
                failures = 1

            if DEBUG:
                print(f"[PeerManager.mark_peer_dead] Peer {peer} {failures}x erfolglos aufgerufen.")
            

            # Wenn max_failures erreicht sind, endgültig aus der Liste entfernen
            if failures >= self.max_failures:
                if DEBUG:
                    print(f"[PeerManager.mark_peer_dead] Peer {peer} nach {self.max_failures} Fehlern endgültig gelöscht.")
                self.dead_peers.pop(peer, None)
            else:
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
        Interne Methode ohne Lock (wird von anderen bereits gelockten Methoden aufgerufen).
        => kein Dead Lock
        """
        now = time.time()
        expired_peers = [
            peer for peer, (timestamp, failures) in self.dead_peers.items()
            if now - timestamp > self.cooldown_seconds
        ]
        for peer in expired_peers:
            del self.dead_peers[peer]
            self.peers.add(peer)
            if DEBUG:
                print(f"[PeerManager._cleanup_cooldown_unlocked] Cooldown für Peer {peer} abgelaufen. Wieder aktiv.")

    def reset(self):
        """Setzt alle Peers und Dead-Peers komplett zurück (für Tests)."""
        with self.lock:
            self.peers.clear()
            self.dead_peers.clear()
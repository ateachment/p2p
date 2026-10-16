import random
import threading
import time

from config import DEBUG

class P2PServer:
    def __init__(self, own_address, peer_manager, p2p_client):

        self.own_address = own_address
        self.peer_manager = peer_manager
        self.p2p_client = p2p_client

        if DEBUG:
            print(f"[BOOT] Eigene IP im P2PServer ermittelt: {self.own_address}")

    @property
    def get_node_identifier(self):
        return self.__node_identifier
    @property
    def get_own_address(self):
        return self.__own_address

    # Background-Funktionen werden in eigenen Threads aufgerufen

    def _background_peers_sync(self):
        target_peers = self.peer_manager.get_random_peers(count=1)
            
        for target_peer in list(target_peers):
            if DEBUG:
                print(f"[BACKGROUND] Starte Sync mit {target_peer}...")
            
            payload = {"peers": [self.own_address] + list(self.peer_manager.get_all_peers())}

            try:
                # Der P2PClient übernimmt das Senden, Timeouts, 
                # Fehlerhandling und das automatische Quarantänemangement!
                response = self.p2p_client.request(
                    target_peer, 
                    'POST', 
                    '/sync/peers', 
                    json=payload
                )
                
                if response and response.status_code == 200:
                    data = response.json()
                    remote_peers = data.get("diff_peers", [])
                    
                    # Peers zentral über den PeerManager aktualisieren
                    if remote_peers:
                        self.peer_manager.update_peers(remote_peers)
                        
                    if DEBUG:
                        print(f"[BACKGROUND] Sync erfolgreich. Aktuelle Peers: {list(self.peer_manager.get_all_peers())}")
                else:
                    if DEBUG and response:
                        print(f"[BACKGROUND] Fehler vom Peer {target_peer}: Status {response.status_code}")
            except Exception as e:
                if DEBUG:
                    print(f"[BACKGROUND CRITICAL ERROR] {e}", flush=True)
                # Hier wird der Peer bei einem Timeout oder Netzwerkfehler sofort als tot markiert:
                self.peer_manager.mark_peer_dead(target_peer)
                
        if DEBUG:
            print(f"[BACKGROUND] Sync-Durchgang abgeschlossen. Aktuelle Peers: {list(self.peer_manager.get_all_peers())}")

    def start_background_sync(self):
        """Startet Hintergrund-Sync-Loops asynchron als Daemon-Threads."""
        
        # Peer-Gossip-Loop starten
        peers_thread = threading.Thread(target=self._background_peers_sync_loop, daemon=True)
        peers_thread.start()
        
        if DEBUG:
            print("[P2PServer] Hintergrund-Sync-Threads gestartet.")

    def _background_peers_sync_loop(self, interval=10):
        """
        Schickt in einem bestimmten Intervall einen Sync-Request an zufällige Peers (Gossip-Protokoll).
        Nutzt den zentralen P2PClient für robustes Fehler- und Quarantänemanagement.
        """
        MAX_JITTER = 3  # Sekunden, um gleichzeitige Syncs zu vermeiden
        jitter = random.uniform(0, MAX_JITTER)
        # Initiale Pause mit Jitter
        time.sleep(jitter)

        while True:
            time.sleep(interval)
            try:
                self._background_peers_sync()
            except Exception as e:
                if DEBUG:
                    print(f"[BACKGROUND LOOP ERROR] {e}", flush=True)
                    

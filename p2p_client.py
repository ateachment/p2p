import requests

class P2PClient:
    def __init__(self, peer_manager, debug=False):
        self.peer_manager = peer_manager
        self.debug = debug

    def request(self, peer: str, method: str, endpoint: str, **kwargs):
        """
        Führt einen sicheren HTTP-Request an einen Peer aus.
        Bei Timeouts, Netzwerkfehlern oder Server-Crashes (>= 500) 
        wird der Peer automatisch vom PeerManager in Quarantäne (dead_peers) geschickt.
        """
        url = f"http://{peer}{endpoint}"
        
        # Standard-Timeout auf 3 Sekunden setzen, falls nicht anders angegeben
        kwargs.setdefault('timeout', 3)
        
        try:
            response = requests.request(method, url, **kwargs)
            
            # Auch bei schweren Server-Fehlern als tot betrachten
            if response.status_code >= 500:
                if self.debug:
                    print(f"[Network] Server-Fehler {response.status_code} von {peer} bei {endpoint}")
                self.peer_manager.mark_peer_dead(peer)
                return None
                
            return response
            
        except Exception as e:
            if self.debug:
                print(f"[P2PClient.request] Verbindung zu {peer} fehlgeschlagen bei {endpoint}: {e}")
            
            # Automatische Bestrafung im PeerManager
            self.peer_manager.mark_peer_dead(peer)
            return None
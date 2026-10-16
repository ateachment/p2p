# Filename: p2p_client.py

import requests

class P2PClient:
    def __init__(self, own_address, peer_manager, debug=False):

        self.own_address = own_address
        self.peer_manager = peer_manager
        self.debug = debug

    def bootstrap(self):
        """Fragt beim Start den Bootstrap-Server ab, füllt die Peer-Liste 
        und filtert die eigene IP-Adresse heraus."""

        # Hier die URL(s) der Bootstrap-Server hardcodiert eintragen, die beim Start abgefragt werden sollen.
        # Sie werden mit versioniert, um Missbrauch zu verhindern. Die Peers können dann die bekannten Peers an andere Peers weitergeben, 
        # die diese dann in ihrer Liste aufnehmen und die dann ihre anderen Peers zurückgeben.
        BOOTSTRAP_URLS = ["http://localhost:5000", "http://bootstrap:5000", "http://nonExistent:5000"] 

        for BOOTSTRAP_URL in BOOTSTRAP_URLS:
            BOOTSTRAP_URL = f"{BOOTSTRAP_URL}/peers"
            print(f"[Bootstrap] Frage Bootstrap-Server an: {BOOTSTRAP_URL}")
            
            try:
                response = requests.get(BOOTSTRAP_URL, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    raw_peers = data.get("peers", [])
                    
                    for peer in raw_peers:
                        # Prüfen, ob die eigene IP (mit oder ohne Port) in dem Eintrag steckt
                        if self.own_address not in peer:
                            self.peer_manager.add_peer(peer)
                            print(f"[Bootstrap] Fremden Peer hinzugefügt: {peer}")
                        else:
                            print(f"[Bootstrap] Eigene IP übersprungen: {peer}")          
                else:
                    print(f"[Bootstrap] Fehler vom Server: Status {response.status_code}")
            except Exception as e:
                print(f"[Bootstrap] Konnte Bootstrap-Server nicht erreichen: {e}")

        print(f"[Bootstrap] Finale bekannte Peers: {list(self.peer_manager.get_all_peers())}")

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
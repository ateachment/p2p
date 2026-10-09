# File:publishSomePeerIPs.py
# Comment: This file is used to publish the IP address of the peer running this code. It is used by the other peers to connect to this peer.

from flask import Flask
import json
import os
import socket
import requests

app = Flask(__name__)

# Lokale Liste für bekannte Peers
known_peers = set()

# Hier die URL(s) der Bootstrap-Server hardcodiert eintragen, die beim Start abgefragt werden sollen.
# Sie werden versioniert
BOOTSTRAP_URLs = ["http://localhost:5000", "http://bootstrap:5000", "http://nonExistent:5000"]  

def bootstrap():
    """Fragt beim Start den Bootstrap-Server ab, füllt die Peer-Liste 
    und filtert die eigene IP-Adresse heraus."""
    own_ip = socket.gethostbyname(socket.gethostname())
    port = os.environ.get("PORT", "5000")
    
    print(f"[Bootstrap] Eigene IP ermittelt: {own_ip}:{port}")

    for BOOTSTRAP_URL in BOOTSTRAP_URLs:
        BOOTSTRAP_URL = f"{BOOTSTRAP_URL}/peers"
        print(f"[Bootstrap] Frage Bootstrap-Server an: {BOOTSTRAP_URL}")
        
        try:
            response = requests.get(BOOTSTRAP_URL, timeout=3)
            if response.status_code == 200:
                data = response.json()
                raw_peers = data.get("peers", [])
                
                for peer in raw_peers:
                    # Prüfen, ob die eigene IP (mit oder ohne Port) in dem Eintrag steckt
                    if own_ip not in peer:
                        known_peers.add(peer)
                        print(f"[Bootstrap] Fremden Peer hinzugefügt: {peer}")
                    else:
                        print(f"[Bootstrap] Eigene IP übersprungen: {peer}")
                    
            else:
                print(f"[Bootstrap] Fehler vom Server: Status {response.status_code}")
        except Exception as e:
            print(f"[Bootstrap] Konnte Bootstrap-Server nicht erreichen: {e}")

    print(f"[Bootstrap] Finale bekannte Peers: {list(known_peers)}")


@app.route('/', methods=['GET'])
def publish_some_peer_ips():
    ip = socket.gethostbyname(socket.gethostname())  # Eigene IP ermitteln
    return json.dumps({ 
        "peer ip": ip, 
        "known_peers": list(known_peers) 
    }) + "\n", 200  # 200 OK

if __name__ == '__main__':
    # Bootstrap-Funktion direkt beim Start ausführen, damit der peer seine bekannten Peers hat, bevor er Anfragen beantwortet.
    bootstrap()
    
    # Flask-Server starten
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # has to run in docker containers    
# File:publishSomePeerIPs.py
# Comment: This file is used to publish the IP address of the peer running this code. It is used by the other peers to connect to this peer.

from flask import Flask, request, Response
import json
import os
import socket
import requests

app = Flask(__name__)


# Eigene IP-Adresse einmalig beim Start ermitteln (global), bleibt dann konstant, da sich die IP-Adresse während der Laufzeit nicht ändert.
MY_IP = socket.gethostbyname(socket.gethostname())
MY_PORT = 5000
MY_ADDRESS = f"{MY_IP}:{MY_PORT}"

print(f"[Start] Eigene IP ermittelt: {MY_IP}:{MY_PORT}")

# Lokale Liste für bekannte Peers
known_peers = set()

# Hier die URL(s) der Bootstrap-Server hardcodiert eintragen, die beim Start abgefragt werden sollen.
# Sie werden mit versioniert, um Missbrauch zu verhindern. Die Peers können dann die bekannten Peers an andere Peers weitergeben, 
# die diese dann in ihrer Liste aufnehmen und die dann ihre anderen Peers zurückgeben.
BOOTSTRAP_URLS = ["http://localhost:5000", "http://bootstrap:5000", "http://nonExistent:5000"]  

def bootstrap():
    """Fragt beim Start den Bootstrap-Server ab, füllt die Peer-Liste 
    und filtert die eigene IP-Adresse heraus."""
    own_ip = socket.gethostbyname(socket.gethostname())
    port = os.environ.get("PORT", "5000")
    
    print(f"[Bootstrap] Eigene IP ermittelt: {own_ip}:{port}")

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

# Route zum Veröffentlichen bekannter Peer-IPs
@app.route('/', methods=['GET'])
def publish_some_peer_ips():
    return json.dumps({ 
        "peer_ip": MY_ADDRESS, 
        "known_peers": list(known_peers) 
    }) + "\n", 200  # 200 OK

# Peers hinter NAT oder in Docker-Containern können ihre IP-Adresse nicht direkt veröffentlichen, 
# da sie möglicherweise nicht von außen erreichbar ist.
# => Daher pushen die Peers ihre bekannten Peers an andere Peers, die diese dann in ihrer Liste aufnehmen und
# die dann ihre anderen Peers zurückgeben. 
@app.route('/sync/peers', methods=['POST'])
def sync_peers():
    global known_peers
    data = request.get_json() or {}
    incoming_peers = data.get("peers", [])
    
    # 1. Fremde Peers aufnehmen
    for p in incoming_peers:
        if p not in known_peers and p != MY_ADDRESS:
            known_peers.add(p)
            print(f"[SYNC] Neuer Peer erhalten: {p}")
            print(f"[SYNC] Aktuelle bekannte Peers: {list(known_peers)}")
            
    # 2. Nur das zurückgeben, was der Absender noch nicht hatte (Diff)
    diff_peers = [p for p in known_peers if p not in incoming_peers and p != MY_ADDRESS]
    
    return json.dumps({
        "peer_ip": MY_ADDRESS,
        "diff_peers": diff_peers
    }) + "\n", 200


if __name__ == '__main__':
    # Bootstrap-Funktion direkt beim Start ausführen, damit der peer seine bekannten Peers hat, bevor er Anfragen beantwortet.
    bootstrap()
    
    # Flask-Server starten
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # has to run in docker containers    
# File:publishSomePeerIPs.py
# Comment: This file is used to publish the IP address of the peer running this code. It is used by the other peers to connect to this peer.

import random
import threading
import time

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


def background_sync_loop():
    """
    Schickt alle X Sekunden einen Sync-Request an einen zufälligen Peer.
    Dabei werden die bekannten Peers an den Peer geschickt, der dann seine bekannten Peers zurückgibt.
    Falls der Peer nicht erreichbar ist, wird er aus der Liste entfernt.
    Im Gegensatz zu einem Full Sweep sollten nur 1 bis 2 Peers pro Durchgang synchronisiert werden, um die Netzwerklast klein zu halten.
    => Gossip Protokoll (dt. Klatsch, Tratsch oder Gerücht) Prinzip: Jeder Peer kennt nur einen Teil der Peers, die er dann an andere Peers weitergibt.
    """

    # Dictionary, um die Fehlversuche pro Peer mitzuzählen: { "IP:Port": fehler_anzahl }
    peer_failure_counts = {}
    MAX_FAILURES = 3  # Nach so vielen Versuchen in Folge fliegt er raus

    INTERVAL = 10  # Sekunden zwischen den Syncs
    MAX_JITTER = 3   # Sekunden, um die Intervalle zufällig zu variieren, damit nicht alle Peers gleichzeitig syncen

    jitter = random.uniform(0, MAX_JITTER)  # Optional: Zufällige Verzögerung, um gleichzeitige Syncs aller peers beim Start zu vermeiden
    while True:
        time.sleep(INTERVAL + jitter)  # Alle INTERVAL Sekunden syncen (Test)
        if not known_peers:
            continue

        # 1 bis maximal 2 zufällige Peers auswählen
        peers_list = list(known_peers)
        # shuffle mischt die Liste durch, danach nehmen wir z.B. die ersten 2 (oder weniger, falls die Liste kleiner ist)
        random.shuffle(peers_list)
        target_peers = peers_list[:1]   # Hier kann man die Anzahl der Peers anpassen, die man gleichzeitig syncen möchte (hier 1 Peer)
            
        for target_peer in list(target_peers):  # Kopie der Liste, da wir sie während der Iteration ändern könnten
            if target_peer == MY_ADDRESS:
                continue  # Eigene Adresse überspringen
            
            print(f"[BACKGROUND] Starte Sync mit {target_peer}...")
            try:
                payload = {"peers": [MY_ADDRESS] + list(known_peers)}
                response = requests.post(f"http://{target_peer}/sync/peers", json=payload, timeout=3)
                
                if response.status_code == 200:
                    data = response.json()
                    remote_peers = data.get("diff_peers", [])
                    # Zurück-Mergen
                    for p in remote_peers:
                        if p not in known_peers and p != MY_ADDRESS:
                            known_peers.add(p)
                    print(f"[BACKGROUND] Sync erfolgreich. Aktuelle Peers: {list(known_peers)}")
                else:
                    print(f"[BACKGROUND] Fehler vom Peer {target_peer}: Status {response.status_code}")
            except Exception as e:
                
                peer_failure_counts[target_peer] = peer_failure_counts.get(target_peer, 0) + 1
                print(f"[BACKGROUND] Konnte Peer {target_peer} nicht erreichen: {e} (Fehleranzahl: {peer_failure_counts[target_peer]})")
                if peer_failure_counts[target_peer] >= MAX_FAILURES:
                    known_peers.remove(target_peer)
                    del peer_failure_counts[target_peer]
                    print(f"[BACKGROUND] Peer {target_peer} nach {MAX_FAILURES} Fehlversuchen entfernt. Aktuelle Peers: {list(known_peers)}")
        print(f"[BACKGROUND] Sync-Durchgang abgeschlossen. Aktuelle Peers: {list(known_peers)}")




if __name__ == '__main__':
    # Bootstrap-Funktion direkt beim Start ausführen, damit der peer seine bekannten Peers hat, bevor er Anfragen beantwortet.
    bootstrap()

    # Hintergrund-Thread für den periodischen Sync starten
    sync_thread = threading.Thread(target=background_sync_loop, daemon=True)
    sync_thread.start()
    
    # Flask-Server starten
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # has to run in docker containers    
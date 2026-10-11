# File: blockchain_node.py
# Comment: This file is used to publish the IP address of the peer running this code. It is used by the other peers to connect to this peer.

import random
import threading
import time
from time import time as timestamp_fn

from flask import Flask, request, Response
import hashlib
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


class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        
        # Den allerersten Block erstellen (Genesis-Block)
        # Ein Startwert (proof=100) und ein Start-Hash (previous_hash='1')
        self.new_block(previous_hash='1', proof=100)

    def new_block(self, proof, previous_hash=None):
        """
        Erstellt einen neuen Block und fügt ihn der Kette hinzu.
        """
        block = {
            'index': len(self.chain) + 1,
            'timestamp': timestamp_fn(),
            'transactions': self.current_transactions,
            'proof': proof,   # Die gefundene Lösungszahl, so dass der Hash des Blocks die Schwierigkeit erfüllt (hier 4 führende Nullen)
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # Die transaktionsliste für den nächsten Block zurücksetzen
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Fügt eine neue Transaktion zur Liste der noch nicht geminten Transaktionen hinzu.
        """
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        """
        Erstellt einen SHA-256-Hash eines Blocks.
        Wichtig: sort_keys=True stellt sicher, dass das JSON immer exakt 
        gleich formatiert ist, egal in welcher Reihenfolge die Keys erstellt wurden.
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof): # Arbeitsnachweis 
        """
        Einfacher Proof-of-Work-Algorithmus:
        - Finde eine Zahl 'proof', sodass sha256(last_proof * proof) mit 4 Nullen beginnt ("0000").
        - Je mehr Nullen, desto schwieriger wird es (Rechenaufwand).
        """
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Validiert den Proof: Beginnt der Hash aus vorigem Proof und aktuellem Proof mit '0000'?
        """
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def valid_chain(self, chain):
        """
        Prüft, ob eine fremde Blockchain gültig ist.
        Dazu wird jeder Block mit dem Hash seines Vorgängers 
        und dem Proof-of-Work überprüft.
        """
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            
            # 1. Prüfen, ob der Hash des Vorgängers korrekt ist
            if block['previous_hash'] != self.hash(last_block):
                return False
            
            # 2. Prüfen, ob der Proof-of-Work korrekt gelöst wurde
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        Konsens-Algorithmus: Geht alle bekannten Peers durch, fragt deren 
        Kette ab und ersetzt unsere eigene, falls eine längere gültige gefunden wird.
        """
        neighbours = known_peers
        new_chain = None

        # Wir interessieren uns nur für Ketten, die länger sind als unsere eigene
        max_length = len(self.chain)

        for node in neighbours:
            if node == MY_ADDRESS:
                continue
            try:
                # Wir fragen den Peer nach seiner Kette (über unseren /chain Endpoint)
                response = requests.get(f'http://{node}/chain', timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    length = data['length']
                    chain = data['chain']

                    # Ist die Kette länger und mathematisch gültig?
                    if length > max_length and self.valid_chain(chain):
                        max_length = length
                        new_chain = chain
            except Exception as e:
                print(f"[Consensus] Konnte Kette von {node} nicht abrufen: {e}")

        # Wenn wir eine längere, gültige Kette gefunden haben, übernehmen wir sie
        if new_chain:
            self.chain = new_chain
            print(f"[Consensus] Kette erfolgreich durch längere gültige Kette ersetzt.")
            return True

        return False

# Globale Blockchain-Instanz erzeugen
blockchain = Blockchain()

# Eine eindeutige ID für diesen Node (z.B. als Empfänger der Mining-Belohnung)
node_identifier = str(socket.gethostname())


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


# --- FLASK ENDPOINTS: P2P & GOSSIP ---

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
    try:
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
    except Exception as e:
        print(f"[BACKGROUND CRITICAL ERROR] {e}", flush=True)


# --- FLASK ENDPOINTS: Blockchain ---

"""
    Konsens-Endpoint: Fragt alle bekannten Peers ab und ersetzt die eigene Kette, falls eine längere gültige gefunden wird.
    Rückgabe: JSON mit der neuen Kette (falls ersetzt) oder der eigenen Kette
"""
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Unsere Kette wurde durch eine längere ersetzt!',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Unsere Kette ist bereits auf dem neuesten Stand.',
            'chain': blockchain.chain
        }

    return json.dumps(response), 200

"""
    Transaktion-Endpoint: Erstellt eine neue Transaktion und fügt sie der Liste hinzu.
    Rückgabe: JSON mit einer Bestätigungsmeldung
"""
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Prüfen, ob alle Pflichtfelder da sind
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Fehlende Werte', 400

    # Transaktion zur Liste hinzufügen
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    return json.dumps({'message': f'Transaktion wird zu Block {index} hinzugefügt'}), 201

"""
    Mining-Endpoint: Führt den Proof-of-Work aus, erstellt eine neue Transaktion für die Mining-Belohnung und fügt einen neuen Block hinzu.
    Rückgabe: JSON mit den Details des neuen Blocks
"""
@app.route('/mine', methods=['GET'])
def mine():
    # 1. Den Proof-of-Work für den letzten Block berechnen
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # 2. Belohnung für den Miner gutschreiben (Absender "0" symbolisiert das System)
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # 3. Den neuen Block der Kette hinzufügen
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "Neuer Block erfolgreich gemined!",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return json.dumps(response), 200

"""
    Chain-Endpoint: Gibt die gesamte Blockchain zurück.
    Rückgabe: JSON mit der Kette und deren Länge
"""
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return json.dumps(response), 200


if __name__ == '__main__':
    # Bootstrap-Funktion direkt beim Start ausführen, damit der peer seine bekannten Peers hat, bevor er Anfragen beantwortet.
    bootstrap()

    # Hintergrund-Thread für den periodischen Sync starten
    sync_thread = threading.Thread(target=background_sync_loop, daemon=True)
    sync_thread.start()
    
    # Flask-Server starten
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # has to run in docker containers    
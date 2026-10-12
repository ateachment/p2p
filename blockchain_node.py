# File: blockchain_node.py
# Comment: This file is used to publish the IP address of the peer running this code. It is used by the other peers to connect to this peer.

import random
import threading
import time

from flask import Flask, jsonify, request, Response
import hashlib
import json
import os
import socket
import requests

app = Flask(__name__)

# Globale Debug-Schalter-Konstante
DEBUG = True


# Eigene IP-Adresse einmalig beim Start ermitteln (global), bleibt dann konstant, da sich die IP-Adresse während der Laufzeit nicht ändert.
MY_IP = socket.gethostbyname(socket.gethostname())
MY_PORT = 5000
MY_ADDRESS = f"{MY_IP}:{MY_PORT}"

if DEBUG:
    print(f"[Start] Eigene IP ermittelt: {MY_IP}:{MY_PORT}")

# Lokale Liste für bekannte Peers
known_peers = set()

# Hier die URL(s) der Bootstrap-Server hardcodiert eintragen, die beim Start abgefragt werden sollen.
# Sie werden mit versioniert, um Missbrauch zu verhindern. Die Peers können dann die bekannten Peers an andere Peers weitergeben, 
# die diese dann in ihrer Liste aufnehmen und die dann ihre anderen Peers zurückgeben.
BOOTSTRAP_URLS = ["http://localhost:5000", "http://bootstrap:5000", "http://nonExistent:5000"]  


class Block:
    def __init__(self, index, transactions, proof, previous_hash, timestamp=None):
        self.index = index
        self.timestamp = timestamp or time.time()
        self.transactions = transactions
        self.proof = proof
        self.previous_hash = previous_hash

    def to_dict(self):
        """Konvertiert den Block in ein sortiertes Dictionary für deterministisches Hashen und JSON."""
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'proof': self.proof,
            'previous_hash': self.previous_hash
        }

    def hash(self):
        """Berechnet den SHA-256-Hash dieses spezifischen Block-Headers."""
        block_string = json.dumps(self.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        
        # Den allerersten Block erstellen (Genesis-Block)
        # Ein Startwert (proof=100) und ein Start-Hash (previous_hash='0') werden verwendet, um die Kette zu initialisieren.
        # Genesis-Block erstellen (Index 0, Vorgänger-Hash "0")
        genesis_block = Block(
            index=0,
            transactions=[],
            proof=100,
            previous_hash="0"
        )
        self.chain.append(genesis_block)

    def new_block(self, proof, previous_hash, timestamp=None):
        """Erstellt einen neuen Block mit Index 0, 1, 2..."""
        block = Block(
            index=len(self.chain), 
            transactions=list(self.current_transactions),
            proof=proof,
            previous_hash=previous_hash,
            timestamp=timestamp
        )
        
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
        return self.last_block.index + 1

    @staticmethod
    def hash(block):
        """Statische Hilfsmethode für Kompatibilität."""
        return block.hash()

    @property
    def last_block(self):
        return self.chain[-1]

    def valid_proof(self, index, timestamp, proof, previous_hash):
        """Prüft, ob der simulierte Block die Schwierigkeit (4 führende Nullen) erfüllt."""
        test_block = Block(
            index=index,
            transactions=list(self.current_transactions),
            proof=proof,
            previous_hash=previous_hash,
            timestamp=timestamp
        )
        return test_block.hash()[:4] == "0000"

    def proof_of_work(self, last_block):
        """Eingefrorener Proof-of-Work auf Basis des Block-Headers."""
        previous_hash = last_block.hash()
        
        index = len(self.chain)
        timestamp = time.time()
        
        proof = 0
        while not self.valid_proof(index, timestamp, proof, previous_hash):
            proof += 1

        return proof, timestamp

    @staticmethod
    def hash(block):
        """Statische Hilfsmethode für Kompatibilität."""
        return block.hash()

    def distribute_block(self, block):
        """
        Leitet einen frisch geminten Block per gezieltem Unicast-Push-Loop
        an eine zufällige Auswahl bekannter Nachbarn weiter.
        """
        if DEBUG:
            print(f"[DISTRIBUTE BLOCK] aufgerufen mit parameter block: {block.to_dict()}")

        neighbors = list(getattr(self, 'nodes', set()))
        if not neighbors:
            return

        # Wähle z. B. maximal 2-3 zufällige Peers aus
        sample_size = min(len(neighbors), 2)
        target_peers = random.sample(neighbors, sample_size)

        for node in target_peers:
            try:
                url = f'http://{node}/nodes/receive_block'
                if DEBUG:
                    print(f"[DISTRIBUTE BLOCK] Sende an: {url}")
                payload = block.to_dict()
                requests.post(url, json=payload, timeout=1.5)
            except requests.exceptions.RequestException:
                # Knoten ist nicht erreichbar -> ignorieren
                continue

    
    def valid_chain(self, chain):
        """
        Prüft, ob eine fremde Blockchain (als Liste von Dicts oder Objekten) gültig ist.
        """
        if not chain:
            return False

        # Konvertiere ggf. JSON-Daten in Block-Objekte
        block_objects = []
        for b in chain:
            if isinstance(b, dict):
                block_objects.append(Block(
                    index=b['index'],
                    transactions=b['transactions'],
                    proof=b['proof'],
                    previous_hash=b['previous_hash'],
                    timestamp=b['timestamp']
                ))
            else:
                block_objects.append(b)

        # 1. Prüfe den Genesis-Block (Index 0 muss "0" als previous_hash haben)
        genesis = block_objects[0]
        if genesis.index != 0 or genesis.previous_hash != "0":
            return False

        # 2. Prüfe alle weiteren Blöcke
        current_index = 1
        while current_index < len(block_objects):
            block = block_objects[current_index]
            prev_block = block_objects[current_index - 1]

            # A) Stimmt der previous_hash mit dem echten Hash des Vorgängers überein?
            if block.previous_hash != prev_block.hash():
                return False

            # B) Proof-of-Work-Prüfung (beginnt der *eigene* Hash des Blocks mit 0000?)
            if block.hash()[:4] != "0000":
                return False

            # WICHTIGER HINWEIS ZUM PREVIOUS_HASH:
            # Der *previous_hash* von Block 1 zeigt auf den Genesis-Block. 
            # Da der Genesis-Block nicht gemined wurde, hat dessen Hash KEINE 4 führenden Nullen.
            # Das ist völlig korrekt und kein Fehler! 
            # Erst ab Block 2 zeigt der previous_hash auf einen geminten Block (der mit 0000 beginnt).

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
                if DEBUG:
                    print(f"[Consensus] Konnte Kette von {node} nicht abrufen: {e}")

        # Wenn wir eine längere, gültige Kette gefunden haben, übernehmen wir sie
        if new_chain:
            self.chain = new_chain
            if DEBUG:
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
    
    if DEBUG:
        print(f"[Bootstrap] Eigene IP ermittelt: {own_ip}:{port}")

    for BOOTSTRAP_URL in BOOTSTRAP_URLS:
        BOOTSTRAP_URL = f"{BOOTSTRAP_URL}/peers"
        if DEBUG:
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
                        if DEBUG:
                            print(f"[Bootstrap] Fremden Peer hinzugefügt: {peer}")
                    else:
                        if DEBUG:
                            print(f"[Bootstrap] Eigene IP übersprungen: {peer}")

            else:
                if DEBUG:
                    print(f"[Bootstrap] Fehler vom Server: Status {response.status_code}")
        except Exception as e:
            if DEBUG:
                print(f"[Bootstrap] Konnte Bootstrap-Server nicht erreichen: {e}")

    if DEBUG:
        print(f"[Bootstrap] Finale bekannte Peers: {list(known_peers)}")


def json_response(data, status=200):
    if DEBUG:
        # formatiert mit Einrückung, Umlauten und Zeilenumbruch für die Konsole
        content = json.dumps(data, indent=4, ensure_ascii=False) + "\n"
    else:
        # kompakt für Performance/Produktion
        content = json.dumps(data, ensure_ascii=False)
        
    return Response(content, status, mimetype='application/json')

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
            if DEBUG:
                print(f"[SYNC] Neuer Peer erhalten: {p}")
            if DEBUG:
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
Eingehenden Block entgegennehmen, validieren und anhängen, falls er gültig ist.
Rückgabe: JSON mit einer Bestätigungsmeldung
"""
@app.route('/nodes/receive_block', methods=['POST'])
def receive_block():

    values = request.get_json()
    
    required = ['index', 'timestamp', 'transactions', 'proof', 'previous_hash']
    if not all(k in values for k in required):
        return json_response({'message': 'Fehlende Block-Daten'}, status=400)

    # Erstelle ein Block-Objekt aus den empfangenen Daten
    incoming_block = Block(
        index=values['index'],
        transactions=values['transactions'],
        proof=values['proof'],
        previous_hash=values['previous_hash'],
        timestamp=values['timestamp']
    )

    last_block = blockchain.last_block

    # Prüffall 1: Der Block passt exakt auf unsere aktuelle Kette auf
    if incoming_block.previous_hash == last_block.hash() and incoming_block.index == last_block.index + 1:
        if incoming_block.hash()[:4] == "0000":
            blockchain.chain.append(incoming_block)
            # Transaktionen bereinigen, falls sie lokal noch im Pool lagen
            # ...
            return json_response({'message': 'Block akzeptiert und angehängt.'}), 201

    # Prüffall 2: Unser Node hat den Anschluss verpasst oder liegt zurück -> Konsens starten!
    if incoming_block.index > last_block.index + 1:
        replaced = blockchain.resolve_conflicts()
        if replaced:
            return json_response({'message': 'Kette durch Konfliktloesung aktualisiert.'}), 200

    return json_response({'message': 'Block abgelehnt (Ungueltig oder veraltet).'}), 400


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
        return json_response({'message': 'Fehlende Werte'}, status=400)

    # Transaktion zur Liste hinzufügen
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    return json_response({'message': f'Transaktion wird zu Block {index} hinzugefügt'}), 201


"""
    Mining-Endpoint: Führt den Proof-of-Work aus, erstellt eine neue Transaktion für die Mining-Belohnung und fügt einen neuen Block hinzu.
    Rückgabe: JSON mit den Details des neuen Blocks
"""
@app.route('/mine', methods=['GET'])
def mine():
    # 1. Den Proof-of-Work für den letzten Block berechnen
    last_block = blockchain.last_block

    proof, block_timestamp = blockchain.proof_of_work(last_block)

    # 2. Belohnung für den Miner gutschreiben (Absender "0" symbolisiert das System)
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # 3. JETZT den Proof-of-Work berechnen (auf Basis ALLER Transaktionen inkl. Belohnung)
    proof, block_timestamp = blockchain.proof_of_work(last_block)

    # 4. Neuen Block erstellen
    previous_hash = last_block.hash()
    block = blockchain.new_block(proof, previous_hash, timestamp=block_timestamp)

    # 5. Gezielte Weiterleitung an zufällige ausgewählte Peers (Unicast-Push-Loop)
    blockchain.distribute_block(block)

    response = {
        'message': "Neuer Block erfolgreich gemined!",
        'index': block.index,           # .index statt ['index']
        'timestamp': block.timestamp,   # .timestamp statt ['timestamp']
        'transactions': block.transactions, # .transactions statt ['transactions']
        'proof': block.proof,           # .proof statt ['proof']
        'previous_hash': block.previous_hash, # .previous_hash statt ['previous_hash']
        'block_hash': block.hash()      # Direkt die Block-Hash-Methode nutzen
    }
    return json_response(response, 200)

"""
    Chain-Endpoint: Gibt die gesamte Blockchain zurück.
    Rückgabe: JSON mit der Kette und deren Länge
"""
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': [block.to_dict() for block in blockchain.chain], # Wichtig: .to_dict() aufrufen!
        'length': len(blockchain.chain),
    }
    return json_response(response, 200)


if __name__ == '__main__':
    # Bootstrap-Funktion direkt beim Start ausführen, damit der peer seine bekannten Peers hat, bevor er Anfragen beantwortet.
    bootstrap()

    # Hintergrund-Thread für den periodischen Sync starten
    sync_thread = threading.Thread(target=background_sync_loop, daemon=True)
    sync_thread.start()
    
    # Flask-Server starten
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # has to run in docker containers    
# File: blockchain_node.py
# Comment: This file is used to publish the IP address of the peer running this code. It is used by the other peers to connect to this peer.

import random
import threading
import time

from flask import Flask, request, Response
import hashlib
import json
import os
import socket

import peer_manager as pm
from p2p_client import P2PClient


app = Flask(__name__)

# Globale Debug-Schalter-Konstante
DEBUG = True



# Eigene IP-Adresse einmalig beim Start ermitteln (global), bleibt dann konstant, da sich die IP-Adresse während der Laufzeit nicht ändert.
MY_IP = socket.gethostbyname(socket.gethostname())
MY_PORT = 5000
MY_ADDRESS = f"{MY_IP}:{MY_PORT}"

if DEBUG:
    print(f"[Start] Eigene IP ermittelt: {MY_IP}:{MY_PORT}")

# Instanziierung der PeerManager-Klasse (mit 60 Sekunden Cooldown)
peer_manager = pm.PeerManager(my_address=MY_ADDRESS, cooldown_seconds=60)

# P2PClient Instanz erzeugen (gibt ihm den peer_manager und das debug-Flag mit)
p2p_client = P2PClient(peer_manager=peer_manager, debug=DEBUG)


# Funktion, um zufällige Peers auszuwählen
def choose_random_peers(n=1):
    # n zufällige Peers auswählen (oder weniger, falls die Liste kleiner ist, ca. 1-2 Peers pro Sync-Durchgang)
    peers_list = peer_manager.get_all_peers()
    # shuffle mischt die Liste durch, danach nehmen wir z.B. die ersten n (oder weniger, falls die Liste kleiner ist)
    random.shuffle(peers_list)
    return peers_list[:n]   # Hier kann man die Anzahl der Peers anpassen, die man gleichzeitig syncen möchte

# Hier die URL(s) der Bootstrap-Server hardcodiert eintragen, die beim Start abgefragt werden sollen.
# Sie werden mit versioniert, um Missbrauch zu verhindern. Die Peers können dann die bekannten Peers an andere Peers weitergeben, 
# die diese dann in ihrer Liste aufnehmen und die dann ihre anderen Peers zurückgeben.
BOOTSTRAP_URLS = ["localhost:5000", "bootstrap:5000", "nonExistent:5000"]  


class Block:
    def __init__(self, index, transactions, proof, previous_hash, timestamp=None):
        self.index = index
        self.timestamp = timestamp if timestamp is not None else time.time()
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
        # Start-Hash (previous_hash='0') werden verwendet, um die Kette zu initialisieren.
        # Genesis-Block erstellen (Index 0, Vorgänger-Hash "0"
        # Der Proof wurde mit mine_genesis.py gemint, sodass der Hash mit 4 führenden Nullen beginnt.)
        genesis_block = Block(
            index=0,
            transactions=[],
            proof=30530,  # mit mine_genesis.py gemint, so dass auch der hash mit 4 führenden Nullen beginnt
            timestamp=0.0,
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
            print(f"[DISTRIBUTE BLOCK] wurde aufgerufen mit parameter block: {block.to_dict()}")

        if DEBUG:
            print(f"[DISTRIBUTE BLOCK] verfügbare Peers: {list(peer_manager.get_all_peers())}")
        if not peer_manager.get_all_peers():
            if DEBUG:
                print(f"[DISTRIBUTE BLOCK] keine Peers verfügbar.")
            return

        target_peers = peer_manager.get_random_peers(count=1)  # Wähle 1 zufällige Peers aus

        for target_peer in target_peers:
            url = f'http://{target_peer}/nodes/receive_block'
            if DEBUG:
                print(f"[DISTRIBUTE BLOCK] Sende an: {url}")
            payload = block.to_dict()
            p2p_client.request(target_peer, "POST", "/nodes/receive_block", json=payload, timeout=1.5)


    
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

            # Der *previous_hash* von Block 1 zeigt auf den Genesis-Block. 
            # Der *previous_hash* von Block 2 zeigt auf Block 1 usw.

            current_index += 1

        return True

    def check_and_sync_chain_with_peer(self, target_peer):
        """
        Fragt einen einzelnen Peer ab, validiert die Kette und ersetzt 
        die eigene bei Bedarf. Gibt True zurück, wenn ersetzt wurde, sonst False.
        """
        response = p2p_client.request(target_peer,"GET","/chain")
        if response and response.status_code  == 200:
            data = response.json()
            remote_length = data.get("length", 0)
            remote_chain_data = data.get("chain", [])
            
            # Wenn der Peer länger ist, prüfen und ggf. ersetzen
            if remote_length > len(self.chain):
                if self.valid_chain(remote_chain_data):
                    self.chain = [
                        Block(
                            index=b['index'],
                            transactions=b['transactions'],
                            proof=b['proof'],
                            previous_hash=b['previous_hash'],
                            timestamp=b['timestamp']
                        ) for b in remote_chain_data
                    ]
                    if DEBUG:
                        print(f"[CHAIN SYNC] Kette von Peer {target_peer} übernommen. Neue Länge: {len(self.chain)}")
                    return True

        return False

   

# Globale Blockchain-Instanz erzeugen
blockchain = Blockchain()

# Eine eindeutige ID für diesen Node (z.B. als Empfänger der Mining-Belohnung)
node_identifier = str(socket.gethostname())


def bootstrap():
    """
    Fragt beim Start den Bootstrap-Server ab und übergibt die Peers 
    direkt an den PeerManager (inkl. automatischer Eigen-IP-Filterung).
    """
    
    for BOOTSTRAP_URL in BOOTSTRAP_URLS:
        if DEBUG:
            print(f"[Bootstrap] Frage Bootstrap-Server an: {BOOTSTRAP_URL}")

        response = p2p_client.request(BOOTSTRAP_URL, "GET", "/peers")
        if response and response.status_code == 200:
            data = response.json()
            raw_peers = data.get("peers", [])
            
            # Der PeerManager filtert sich selbst und Penalty-Peers jetzt automatisch heraus!
            peer_manager.update_peers(raw_peers)
            
            if DEBUG:
                for peer in raw_peers:
                    print(f"[Bootstrap] Empfangener Peer verarbeitet: {peer}")
            break  # Wenn ein Bootstrap-Server erfolgreich war, müssen wir nicht weitere abfragen

    if DEBUG:
        print(f"[Bootstrap] Finale bekannte Peers: {list(peer_manager.get_all_peers())}")


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
        "known_peers": list(peer_manager.get_all_peers()) 
    }) + "\n", 200  # 200 OK

# Peers hinter NAT oder in Docker-Containern können ihre IP-Adresse nicht direkt veröffentlichen, 
# da sie möglicherweise nicht von außen erreichbar ist.
# => Daher pushen die Peers ihre bekannten Peers an andere Peers, die diese dann in ihrer Liste aufnehmen und
# die dann ihre anderen Peers zurückgeben. 
@app.route('/sync/peers', methods=['POST'])
def sync_peers():
    data = request.get_json() or {}
    incoming_peers = data.get("peers", [])
    
    # 1. Fremde Peers aufnehmen
    for p in incoming_peers:
        if p not in peer_manager.get_all_peers():
            peer_manager.add_peer(p)
            if DEBUG:
                print(f"[SYNC] Neuer Peer erhalten: {p}")
            if DEBUG:
                print(f"[SYNC] Aktuelle bekannte Peers: {list(peer_manager.get_all_peers())}")
            
    # 2. Nur das zurückgeben, was der Absender noch nicht hatte (Diff)
    diff_peers = [p for p in peer_manager.get_all_peers() if p not in incoming_peers]
    
    return json.dumps({
        "peer_ip": MY_ADDRESS,
        "diff_peers": diff_peers
    }) + "\n", 200


import random
import time

def background_sync_loop(interval=10):
    """
    Schickt in einem bestimmten Intervall einen Sync-Request an zufällige Peers (Gossip-Protokoll).
    Nutzt den zentralen P2PClient für robustes Fehler- und Quarantänemanagement.
    """
    MAX_JITTER = 3  # Sekunden, um gleichzeitige Syncs zu vermeiden
    jitter = random.uniform(0, MAX_JITTER)
    
    try:
        # Initiale Pause mit Jitter
        time.sleep(jitter)
        
        while True:
            time.sleep(interval)
            
            if not peer_manager.get_all_peers():
                continue

            target_peers = peer_manager.get_random_peers(count=1)
                
            for target_peer in list(target_peers):
                if DEBUG:
                    print(f"[BACKGROUND] Starte Sync mit {target_peer}...")
                
                payload = {"peers": [MY_ADDRESS] + list(peer_manager.get_all_peers())}
                
                # Der P2PClient übernimmt das Senden, Timeouts, 
                # Fehlerhandling und das automatische Quarantänemangement!
                response = p2p_client.request(
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
                        peer_manager.update_peers(remote_peers)
                        
                    if DEBUG:
                        print(f"[BACKGROUND] Sync erfolgreich. Aktuelle Peers: {list(peer_manager.get_all_peers())}")
                else:
                    if DEBUG and response:
                        print(f"[BACKGROUND] Fehler vom Peer {target_peer}: Status {response.status_code}")
                
            if DEBUG:
                print(f"[BACKGROUND] Sync-Durchgang abgeschlossen. Aktuelle Peers: {list(peer_manager.get_all_peers())}")
                
    except Exception as e:
        print(f"[BACKGROUND CRITICAL ERROR] {e}", flush=True)


def background_chain_sync_loop(interval=15):
    """
    Regelmäßiger Hintergrund-Loop, der zufällige Peers über die 
    Blockchain-Methode synchronisiert.
    """
    while True:
        try:
            time.sleep(interval)
            target_peers = list(peer_manager.get_random_peers(count=1))
            if not target_peers:
                continue
                
            for target_peer in target_peers:
                if DEBUG:
                    print(f"[CHAIN-SYNC] Prüfe Kette von Peer {target_peer}...")
                blockchain.check_and_sync_chain_with_peer(target_peer)
                
        except Exception as e:
            print(f"[CHAIN-SYNC CRITICAL ERROR] {e}", flush=True)


# --- FLASK ENDPOINTS: Blockchain ---


"""
Eingehenden Block entgegennehmen, validieren und anhängen, falls er gültig ist.
Rückgabe: JSON mit einer Bestätigungsmeldung
"""
@app.route('/nodes/receive_block', methods=['POST'])
def receive_block():
    if DEBUG:
        print(f"[RECEIVE BLOCK] Eingehender Block: {request.get_json()}")
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

    if DEBUG:
        print(f"[RECEIVE BLOCK] Block abgelehnt: Ungültig oder veraltet. Eingehender Block: {incoming_block.to_dict()}, Letzter Block: {last_block.to_dict()}")
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

    # Hintergrund-Threads für den periodischen Sync starten
    # p2p-Gossip-Mechanismus: Jeder Peer fragt in regelmäßigen Abständen zufällige Peers ab, um die Peer-Liste zu synchronisieren.
    sync_thread = threading.Thread(target=background_sync_loop, daemon=True)
    sync_thread.start()
    # blockchain-Sync-Mechanismus: Jeder Peer fragt in regelmäßigen Abständen zufällige Peers ab, um die Kette zu synchronisieren.
    sync_thread = threading.Thread(target=background_chain_sync_loop, daemon=True)
    sync_thread.start()
    
    # Flask-Server starten
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # has to run in docker containers    
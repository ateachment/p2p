import hashlib
import json
import threading
import time

from config import DEBUG

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
    def __init__(self, peer_manager, p2p_client):
        
        self.chain = []
        self.current_transactions = []
        self.peer_manager = peer_manager
        self.p2p_client = p2p_client
        
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
            print(f"[DISTRIBUTE BLOCK] verfügbare Peers: {list(self.peer_manager.get_all_peers())}")
        if not self.peer_manager.get_all_peers():
            if DEBUG:
                print(f"[DISTRIBUTE BLOCK] keine Peers verfügbar.")
            return

        target_peers = self.peer_manager.get_random_peers(count=1)  # Wähle 1 zufällige Peers aus

        for target_peer in target_peers:
            url = f'http://{target_peer}/nodes/receive_block'
            if DEBUG:
                print(f"[DISTRIBUTE BLOCK] Sende an: {url}")
            payload = block.to_dict()
            self.p2p_client.request(target_peer, "POST", "/nodes/receive_block", json=payload, timeout=1.5)


    
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


    def start_background_sync(self):
        """Startet alle Hintergrund-Sync-Loops asynchron als Daemon-Threads."""

        # Blockchain-Sync-Loop starten
        peers_thread = threading.Thread(target=self._check_and_sync_chain_with_peer_loop, daemon=True)
        peers_thread.start()
        
        if DEBUG:
            print("[Blockchain] Hintergrund-Sync-Threads gestartet.")


    def _check_and_sync_chain_with_peer(self, target_peer):
        """
        Fragt einen einzelnen Peer ab, validiert die Kette und ersetzt 
        die eigene bei Bedarf. Gibt True zurück, wenn ersetzt wurde, sonst False.
        """
        response = self.p2p_client.request(target_peer,"GET","/chain")
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


    def _check_and_sync_chain_with_peer_loop(self, interval=15):
        """
        Regelmäßiger Hintergrund-Loop, der zufällige Peers über die 
        Blockchain-Methode synchronisiert.
        """
        while True:
            try:
                time.sleep(interval)
                target_peers = list(self.peer_manager.get_random_peers(count=1))
                if not target_peers:
                    continue
                    
                for target_peer in target_peers:
                    if DEBUG:
                        print(f"[CHAIN-SYNC] Prüfe Kette von Peer {target_peer}...")
                    self._check_and_sync_chain_with_peer(target_peer)
                    
            except Exception as e:
                print(f"[CHAIN-SYNC CRITICAL ERROR] {e}", flush=True)


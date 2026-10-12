import hashlib
import json

def mine_genesis():
    previous_hash = "0"
    timestamp = 0.0
    transactions = []
    proof = 0
    
    while True:
        # Baue das Block-Dictionary exakt so wie in deiner Block-Klasse
        block_content = {
            'index': 0,
            'timestamp': timestamp,
            'transactions': transactions,
            'proof': proof,
            'previous_hash': previous_hash
        }
        block_string = json.dumps(block_content, sort_keys=True).encode()
        block_hash = hashlib.sha256(block_string).hexdigest()
        
        if block_hash.startswith("0000"):
            print("Genesis Block gefunden! Proof:", proof)
            print("Hash:", block_hash)
            break
        proof += 1

if __name__ == "__main__":
    mine_genesis()
from flask import Blueprint, current_app, request


from config import DEBUG
from p2p_network.util import json_response


blockchain_api = Blueprint('blockchain_api', __name__)


# --- FLASK ENDPOINTS: Blockchain ---


"""
Eingehenden Block entgegennehmen, validieren und anhängen, falls er gültig ist.
Rückgabe: JSON mit einer Bestätigungsmeldung
"""
@blockchain_api.route('/nodes/receive_block', methods=['POST'])
def receive_block():
    if DEBUG:
        print(f"[RECEIVE BLOCK] Eingehender Block: {request.get_json()}")
    values = request.get_json()
    
    required = ['index', 'timestamp', 'transactions', 'proof', 'previous_hash']
    if not all(k in values for k in required):
        return json_response({'message': 'Fehlende Block-Daten'}, status=400)

    # Erstelle ein Block-Objekt aus den empfangenen Daten
    incoming_block = current_app.Block(
        index=values['index'],
        transactions=values['transactions'],
        proof=values['proof'],
        previous_hash=values['previous_hash'],
        timestamp=values['timestamp']
    )

    last_block = current_app.blockchain.last_block

    # Prüffall 1: Der Block passt exakt auf unsere aktuelle Kette auf
    if incoming_block.previous_hash == last_block.hash() and incoming_block.index == last_block.index + 1:
        if incoming_block.hash()[:4] == "0000":
            current_app.blockchain.chain.append(incoming_block)
            # Transaktionen bereinigen, falls sie lokal noch im Pool lagen
            # ...
            return json_response({'message': 'Block akzeptiert und angehängt.'}), 201

    # Prüffall 2: Unser Node hat den Anschluss verpasst oder liegt zurück -> Konsens starten!
    if incoming_block.index > last_block.index + 1:
        replaced = current_app.blockchain.resolve_conflicts()
        if replaced:
            return json_response({'message': 'Kette durch Konfliktloesung aktualisiert.'}), 200

    if DEBUG:
        print(f"[RECEIVE BLOCK] Block abgelehnt: Ungültig oder veraltet. Eingehender Block: {incoming_block.to_dict()}, Letzter Block: {last_block.to_dict()}")
    return json_response({'message': 'Block abgelehnt (Ungueltig oder veraltet).'}), 400


"""
    Transaktion-Endpoint: Erstellt eine neue Transaktion und fügt sie der Liste hinzu.
    Rückgabe: JSON mit einer Bestätigungsmeldung
"""
@blockchain_api.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Prüfen, ob alle Pflichtfelder da sind
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return json_response({'message': 'Fehlende Werte'}, status=400)

    # Transaktion zur Liste hinzufügen
    index = current_app.blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    return json_response({'message': f'Transaktion wird zu Block {index} hinzugefügt'}), 201


"""
    Mining-Endpoint: Führt den Proof-of-Work aus, erstellt eine neue Transaktion für die Mining-Belohnung und fügt einen neuen Block hinzu.
    Rückgabe: JSON mit den Details des neuen Blocks
"""
@blockchain_api.route('/mine', methods=['GET'])
def mine():
    # 1. Den Proof-of-Work für den letzten Block berechnen
    last_block = current_app.blockchain.last_block

    proof, block_timestamp = current_app.blockchain.proof_of_work(last_block)

    # 2. Belohnung für den Miner gutschreiben (Absender "0" symbolisiert das System)
    current_app.blockchain.new_transaction(
        sender="0",
        recipient=current_app.node_identifier,
        amount=1,
    )

    # 3. JETZT den Proof-of-Work berechnen (auf Basis ALLER Transaktionen inkl. Belohnung)
    proof, block_timestamp = current_app.blockchain.proof_of_work(last_block)

    # 4. Neuen Block erstellen
    previous_hash = last_block.hash()
    block = current_app.blockchain.new_block(proof, previous_hash, timestamp=block_timestamp)

    # 5. Gezielte Weiterleitung an zufällige ausgewählte Peers (Unicast-Push-Loop)
    current_app.blockchain.distribute_block(block)

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
@blockchain_api.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': [block.to_dict() for block in current_app.blockchain.chain], # Wichtig: .to_dict() aufrufen!
        'length': len(current_app.blockchain.chain),
    }
    return json_response(response, 200)

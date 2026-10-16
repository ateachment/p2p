# app.py

import socket
import os

from flask import Flask

# Eigene Module importieren
from blockchain.core import Blockchain
from p2p_network.peer_manager import PeerManager
from p2p_network.p2p_client import P2PClient
from p2p_network.p2p_server import P2PServer

# Blueprints importieren
from api.blockchain_routes import blockchain_api
from api.p2p_routes import p2p_api

# Flask-App initialisieren
app = Flask(__name__)



def create_app(config_override=None):
    app = Flask(__name__)

    # Globale Instanzen bereitstellen (wichtig für Routen und Tests)

    node_identifier = str(socket.gethostname()) # Eindeutiger Node-Identifier (kann Hostname oder eine UUID sein)
    ip = socket.gethostbyname(socket.gethostname())  # Eigene Adresse ermitteln
    port = int(os.environ.get("PORT", 5000))
    own_address = f"{ip}:{port}"

    peer_manager = PeerManager(own_address, cooldown_seconds=60)
    p2p_client = P2PClient(own_address, peer_manager)
    p2p_server = P2PServer(own_address, peer_manager, p2p_client)

    blockchain = Blockchain(peer_manager, p2p_client)

    # Instanzen für Routen / App-Kontext bereitstellen

    app.node_identifier = node_identifier
    app.own_address = own_address
    app.blockchain = blockchain
    app.peer_manager = peer_manager
    app.p2p_client = p2p_client
    app.p2p_server = p2p_server

    # Blueprints registrieren
    app.register_blueprint(blockchain_api)
    app.register_blueprint(p2p_api)

    return app
    

if __name__ == '__main__':
    app = create_app()

    # Bootstrap beim Start ausführen
    app.p2p_client.bootstrap()

    # Hintergrund-Threads für den periodischen Sync starten
    
    # p2p-Gossip-Mechanismus: Jeder Peer fragt in regelmäßigen Abständen zufällige Peers ab, 
    # um die Peer-Liste zu synchronisieren.
    app.p2p_server.start_background_sync()

    # blockchain-Sync-Mechanismus: Jeder Peer fragt in regelmäßigen Abständen zufällige Peers ab, 
    # um die Kette zu synchronisieren.
    app.blockchain.start_background_sync()

    # Flask-Server starten
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # has to run in docker containers    
import json

from flask import Blueprint, current_app, request
from config import DEBUG


p2p_api = Blueprint('p2p_api', __name__)

# --- FLASK ENDPOINTS: P2P & GOSSIP ---

# Route zum Veröffentlichen bekannter Peer-IPs
@p2p_api.route('/peers', methods=['GET'])
def publish_some_peer_ips():
    return json.dumps({ 
        "peer_ip": current_app.p2p_server.own_address, 
        "known_peers": list(current_app.peer_manager.get_all_peers()) 
    }) + "\n", 200  # 200 OK

# Peers hinter NAT oder in Docker-Containern können ihre IP-Adresse nicht direkt veröffentlichen, 
# da sie möglicherweise nicht von außen erreichbar ist.
# => Daher pushen die Peers ihre bekannten Peers an andere Peers, die diese dann in ihrer Liste aufnehmen und
# die dann ihre anderen Peers zurückgeben. 
@p2p_api.route('/sync/peers', methods=['POST'])
def sync_peers():
    data = request.get_json() or {}
    incoming_peers = data.get("peers", [])
    
    # 1. Fremde Peers aufnehmen
    for p in incoming_peers:
        if p not in current_app.peer_manager.get_all_peers():
            current_app.peer_manager.add_peer(p)
            if DEBUG:
                print(f"[SYNC] Neuer Peer erhalten: {p}")
            if DEBUG:
                print(f"[SYNC] Aktuelle bekannte Peers: {list(current_app.peer_manager.get_all_peers())}")
            
    # 2. Nur das zurückgeben, was der Absender noch nicht hatte (Diff)
    diff_peers = [p for p in current_app.peer_manager.get_all_peers() if p not in incoming_peers]
    
    return json.dumps({
        "peer_ip": current_app.own_address,
        "diff_peers": diff_peers
    }) + "\n", 200


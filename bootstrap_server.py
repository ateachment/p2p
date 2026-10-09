from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# Zentrales Verzeichnis aller bekannten Peers
registered_peers = set(["172.18.0.2:5000","172.18.0.99:5000"])  # den 1. Peer sollte es geben, den 2. Peer nicht


@app.route("/peers", methods=["GET"])
def get_peers():
    return jsonify({"peers": list(registered_peers)}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
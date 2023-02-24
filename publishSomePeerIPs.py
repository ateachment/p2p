from flask import Flask
import json
import os
import socket

app = Flask(__name__)

@app.route('/', methods=['GET'])
def publishSomePeerIPs():
    ip = socket.gethostbyname(socket.gethostname())                 # get ip address of python running system
    return json.dumps({ "server ip": ip }), 200                     # 200 OK

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # has to run in docker containers    
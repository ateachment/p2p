import json
import socket
from publishSomePeerIPs import app

def test_logout():
    response = app.test_client().get('/')
    assert response.status_code == 200
    ip = socket.gethostbyname(socket.gethostname())                 # get ip address of python running system
    server_ip = json.loads(response.data.decode('utf-8')).get("server ip")
    assert server_ip == ip

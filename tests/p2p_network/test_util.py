from flask import current_app
import pytest
from app import create_app

from p2p_network.util import json_response

@pytest.fixture
def util_env():
    """Erstellt eine isolierte Testumgebung über die Application Factory."""
    # App im Test-Modus erzeugen
    app = create_app({
        "TESTING": True,
        "PROPAGATE_EXCEPTIONS": True  # <--- Das sorgt dafür, dass echte Exceptions direkt in Pytest landen!
        })
    return app.test_client() 

def test_json_response_helper(util_env):
    """Testet die Hilfsfunktion json_response auf korrekten Status, Mimetype und Newline."""
    test_client = util_env

    payload = {"status": "ok", "value": 42}
    

    with test_client.application.app_context():
        response = json_response(payload, status=201)
        # Prüfungen durchführen
        assert response.status_code == 201
        assert response.mimetype == 'application/json'
        assert response.get_json() == payload
        # Prüfen, ob das explizite Newline am Ende der Rohdaten hängt
        assert response.get_data().endswith(b'\n')
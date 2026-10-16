import json
from flask import current_app

# Hilfsfunktion
def json_response(data, status=200):
    return current_app.response_class(
        response=json.dumps(data) + '\n',
        status=status,
        mimetype='application/json'
    )



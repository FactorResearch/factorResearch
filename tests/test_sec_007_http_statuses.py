from flask import Flask, abort

from codes.app import server
from codes.error_pages import register_error_pages


def test_unsupported_methods_remain_client_errors():
    client = server.test_client()
    assert client.open("/", method="TRACE").status_code == 405
    assert client.open("/", method="CONNECT").status_code == 405


def test_untemplated_http_exception_preserves_status_and_hides_detail():
    app = Flask(__name__)
    app.secret_key = "test"
    register_error_pages(app)

    @app.get("/teapot")
    def teapot():
        abort(418, description="internal detail")

    response = app.test_client().get("/teapot")
    assert response.status_code == 418
    assert response.get_data(as_text=True) == "418 I'm a Teapot\n"
    assert "internal detail" not in response.get_data(as_text=True)

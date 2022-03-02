import requests


def test_home():
    url = "http://127.0.0.1:8040/"
    resp = requests.get(url)
    assert resp.history[0].status_code == 302


def test_login():
    url = "http://127.0.0.1:8040/login/"
    session = requests.Session()
    session.get(url)

    csrf_token = session.cookies['csrftoken']

    data = dict(
        username="test_superuser",
        password="test_superpass",
        csrfmiddlewaretoken=csrf_token,
        login="[]"
    )

    resp = session.post(url, data=data)

    assert resp.status_code == 200, resp.content.decode()
    assert 'name="api_token"' in resp.content.decode()

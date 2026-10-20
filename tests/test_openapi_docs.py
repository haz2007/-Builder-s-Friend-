from manage import OPENAPI_PATH, openapi_json


def test_openapi_file_is_up_to_date():
    """Если API поменялся — обнови документацию: python manage.py export-openapi."""
    assert OPENAPI_PATH.read_text(encoding="utf-8") == openapi_json()

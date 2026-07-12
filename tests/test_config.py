import pytest

from szurubooru_toolkit import config as config_module
from szurubooru_toolkit.config import Config


@pytest.fixture
def make_config(monkeypatch):
    """Builds Config instances that don't pick up config.toml files from the machine."""

    monkeypatch.setattr('os.path.isfile', lambda path: False)
    return Config


def test_defaults_not_shared_between_instances(make_config):
    first = make_config()
    first.upload_media['tags'] = ['changed']
    first.credentials['pixiv']['token'] = 'secret'

    second = make_config()

    assert second.upload_media['tags'] == ['tagme']
    assert second.credentials['pixiv']['token'] is None
    assert config_module.UPLOAD_MEDIA_DEFAULTS['tags'] == ['tagme']


def test_globals_have_no_hide_progress_default(make_config):
    # Scripts try config.globals['hide_progress'] and fall back to their own
    # section on KeyError; a global default would make that fallback dead code.
    assert 'hide_progress' not in make_config().globals


def test_override_import_section_tolerates_missing_upload_options(make_config):
    config = make_config()

    config.override_config(
        {
            'globals': {'url': 'http://szuru.local', 'username': 'user', 'api_token': 'token'},
            'import_from_booru': {'limit': 5},
        },
    )

    assert config.import_from_booru['limit'] == 5


def test_override_import_section_forwards_upload_options(make_config):
    config = make_config()

    config.override_config(
        {
            'globals': {'url': 'http://szuru.local', 'username': 'user', 'api_token': 'token'},
            'import_from_booru': {'max_similarity': 0.8},
        },
    )

    assert config.upload_media['max_similarity'] == 0.8

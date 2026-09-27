import importlib

import szurubooru_toolkit

# The CLI reads the *_DEFAULTS of the config module at import time, but other test modules
# replace the package attribute `szurubooru_toolkit.config` with a stand-in; restore it for the import
_stand_in = szurubooru_toolkit.__dict__.get('config')
szurubooru_toolkit.config = importlib.import_module('szurubooru_toolkit.config')
from szurubooru_toolkit.scripts import szuru_toolkit  # noqa: E402

szurubooru_toolkit.config = _stand_in


def test_no_command_defines_an_option_twice():
    # A second --limit on import-from-booru made click print warnings on every invocation
    for name, command in szuru_toolkit.cli.commands.items():
        options = [option for param in command.params for option in getattr(param, 'opts', [])]
        assert len(options) == len(set(options)), name

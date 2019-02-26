from pathlib import Path

import pytest
from click.testing import CliRunner


here = Path(__file__).parent
DATA_DIR = here / 'data'
CONFIG_FILEPATH = here / 'config.ini'


@pytest.fixture(autouse=True)
def monekypatch_config(monkeypatch):
    """Point at the testing configuration file"""
    monkeypatch.setenv('NEB_CONFIG', str(CONFIG_FILEPATH))


@pytest.fixture
def datadir():
    """Returns the path to the data directory"""
    return DATA_DIR


@pytest.fixture
def invoker():
    """Provides a callable for testing a click enabled function using
    the click.testing.CliRunner

    """
    runner = CliRunner()
    return runner.invoke


@pytest.fixture
def tmpcwd(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    return Path(str(tmpdir))


@pytest.fixture
def clear_files(request):
    import os

    def _get_files(directory, filename):
        for root, dirs, files in os.walk(str(directory)):
            if filename in files:
                yield os.path.join(root, filename)

    def _clear_files(directory, filename):
        def cleanup():
            for f in _get_files(directory, filename):
                os.unlink(f)

        # make sure files are removed before tests
        cleanup()

        # make sure files are removed after tests
        request.addfinalizer(cleanup)

    return _clear_files

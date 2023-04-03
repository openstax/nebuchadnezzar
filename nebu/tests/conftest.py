from pathlib import Path

import pytest
from aioresponses import aioresponses
from click.testing import CliRunner


here = Path(__file__).parent
DATA_DIR = here / 'data'
CONFIG_FILEPATH = here / 'config.ini'


@pytest.fixture
def git_collection_data(datadir):
    """This data reflects what is expected from git storage"""
    return datadir / 'collection_for_git_workflow'


@pytest.fixture
def parts_tuple(git_collection_data):
    from nebu.models.book_part import BookPart
    collection, docs_by_id, docs_by_uuid = BookPart.collection_from_file(
        git_collection_data / "collection.xml"
    )
    return (collection, docs_by_id, docs_by_uuid)


@pytest.fixture(autouse=True)
def monekypatch_config(monkeypatch):
    """Point at the testing configuration file"""
    monkeypatch.setenv('NEB_CONFIG', str(CONFIG_FILEPATH))


@pytest.fixture
def datadir():
    """Returns the path to the data directory"""
    return DATA_DIR


@pytest.fixture
def snapshot_dir():
    return here / "snapshots"


# You can override this in tests
@pytest.fixture
def current_snapshot_dir(snapshot_dir):
    return snapshot_dir


@pytest.fixture
def assert_match(snapshot, current_snapshot_dir):
    # emulate the way pytest_snapshot auto names snapshot directories
    # with increased control of the parent directory via current_snapshot_dir
    def _assert_match(value, name):
        import inspect
        frames = inspect.getouterframes(inspect.currentframe())
        func_name = frames[1].function
        snapshot.snapshot_dir = current_snapshot_dir / func_name
        snapshot.assert_match(value, name)
    return _assert_match


@pytest.fixture
def invoker():
    """Provides a callable for testing a click enabled function using
    the click.testing.CliRunner

    """
    runner = CliRunner()
    return runner.invoke


@pytest.fixture
def mock_aioresponses():
    with aioresponses() as m:
        yield m


@pytest.fixture
def tmpcwd(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    return Path(str(tmpdir))

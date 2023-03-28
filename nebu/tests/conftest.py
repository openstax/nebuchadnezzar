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
    collection, docs_by_id, docs_by_uuid = BookPart.from_collection_xml(
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

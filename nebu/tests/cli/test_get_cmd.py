# -*- coding: utf-8 -*-
from functools import partial
from pathlib import Path
from os import scandir

import pytest
import requests_mock


def pathlib_walk(dir):
    for e in scandir(str(dir)):
        yield Path(e.path)
        if e.is_dir():
            for ee in pathlib_walk(e.path):
                yield Path(ee)


@pytest.fixture
def requests_mocker(request):
    mocker = requests_mock.Mocker()
    mocker.start()
    request.addfinalizer(mocker.stop)
    return mocker


@pytest.fixture
def tmpcwd(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    return Path(str(tmpdir))


def test_get_cmd(datadir, tmpcwd, requests_mocker):
    col_id = 'col11405'
    url = 'http://legacy.cnx.org/content/{}/latest/complete'.format(col_id)

    complete_zip = datadir / 'complete.zip'
    content_size = complete_zip.stat().st_size
    with complete_zip.open('rb') as fb:
        headers = {'Content-Length': str(content_size)}
        requests_mocker.get(url, content=fb.read(), headers=headers)

    from nebu.cli.main import main
    args = ['get', col_id]
    return_code = main(args)

    assert return_code == 0

    dir = tmpcwd / col_id
    expected = datadir / 'collection'

    def _rel(p, b): return p.relative_to(b)

    relative_dir = map(partial(_rel, b=dir), pathlib_walk(dir))
    relative_expected = map(partial(_rel, b=expected), pathlib_walk(expected))
    assert sorted(relative_dir) == sorted(relative_expected)


def test_get_cmd_with_existing_output_dir(tmpcwd, capsys):
    col_id = 'col00000'

    (tmpcwd / col_id).mkdir()

    from nebu.cli.main import main
    args = ['get', col_id]
    return_code = main(args)

    assert return_code == 3

    out, err = capsys.readouterr()
    assert 'output directory cannot exist:' in out


def test_get_cmd_with_failed_request(requests_mocker, capsys):
    col_id = 'col00000'
    url = 'http://legacy.cnx.org/content/{}/latest/complete'.format(col_id)

    requests_mocker.register_uri('GET', url, status_code=404)

    from nebu.cli.main import main
    args = ['get', col_id]
    return_code = main(args)

    assert return_code == 4

    out, err = capsys.readouterr()
    assert "content unavailable for '{}'".format(col_id) in out

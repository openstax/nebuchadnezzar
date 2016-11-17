# -*- coding: utf-8 -*-
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path

import requests
from litezip import convert_completezip
from progressbar import Bar, FileTransferSpeed, Percentage, ProgressBar

from ..logger import logger
from .discovery import register_subcommand


def get_parser(parser):
    """Download and expansion arguments for the `get` command."""
    parser.add_argument('col_id', help="collection id")
    parser.add_argument('col_version', nargs='?',
                        default='latest',
                        help="collection version")
    parser.add_argument('-d', '--output-dir',
                        help="output directory name (can't previously exist)")


@contextmanager
def progress_bar(id, size):
    widgets = [id, ": ", Bar(marker="|", left="[", right="]"),
               Percentage(), " at ",  FileTransferSpeed(), " ",
               " of {0}MB".format(str(round(size / 1024 / 1024, 2))[:4])]
    pbar = ProgressBar(widgets=widgets, maxval=size).start()
    yield pbar
    pbar.finish()


@register_subcommand('get', get_parser)
def get_cmd(args_namespace):
    """download and expand the completezip to the current working directory"""
    col_id = args_namespace.col_id
    col_version = args_namespace.col_version
    url = 'http://legacy.cnx.org/content/{}/{}/complete'.format(
        col_id, col_version)

    tmp_dir = Path(tempfile.mkdtemp())
    zip_filepath = tmp_dir / 'complete.zip'
    output_dir = args_namespace.output_dir
    if output_dir is None:
        output_dir = Path.cwd() / col_id
    else:
        output_dir = Path(output_dir)

    if output_dir.exists():
        logger.error("output directory cannot exist:  {}".format(output_dir))
        return 3

    resp = requests.get(url, stream=True)

    if not resp:
        logger.error("content unavailable for '{}'".format(col_id))
        logger.debug("response code is {}".format(resp.status_code))
        return 4

    content_size = int(resp.headers['Content-Length'].strip())
    bytes_ = 0
    _progress_bar = progress_bar(col_id, content_size)
    with _progress_bar as pbar, zip_filepath.open('wb') as fb:
        for buffer_ in resp.iter_content(1024):
            if buffer_:
                fb.write(buffer_)
                bytes_ += len(buffer_)
                pbar.update(bytes_)

    with zipfile.ZipFile(str(zip_filepath), 'r') as zip:
        zip.extractall(str(tmp_dir))

    extracted_dir = Path([x for x in tmp_dir.glob('col*_complete')][0])

    convert_completezip(extracted_dir)

    shutil.copytree(str(extracted_dir), str(output_dir))
    shutil.rmtree(str(tmp_dir))

    return 0

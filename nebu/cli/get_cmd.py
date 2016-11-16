# -*- coding: utf-8 -*-
import shutil
import tempfile
import zipfile
from pathlib import Path

import requests
from litezip import convert_completezip

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

    # TODO check if the output dir exists already

    resp = requests.get(url)

    # TODO check for request failure

    with zip_filepath.open('wb') as f:
        f.write(resp.content)

    with zipfile.ZipFile(str(zip_filepath), 'r') as zip:
        zip.extractall(str(tmp_dir))

    extracted_dir = Path([x for x in tmp_dir.glob('col*_complete')][0])

    convert_completezip(extracted_dir)

    shutil.copytree(str(extracted_dir), str(output_dir))
    shutil.rmtree(str(tmp_dir))

    return 0

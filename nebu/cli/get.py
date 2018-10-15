import os

import click
import requests

from lxml import etree
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from ..logger import logger
from ._common import common_params, confirm, get_base_url
from .exceptions import *  # noqa: F403


@click.command()
@common_params
@click.option('-d', '--output-dir', type=click.Path(),
              help="output directory name (can't previously exist)")
@click.option('-t', '--book-tree', is_flag=True,
              help="create human-friendly book-tree")
@click.argument('env')
@click.argument('col_id')
@click.argument('col_version')
@click.pass_context
def get(ctx, env, col_id, col_version, output_dir, book_tree):
    """download and expand the completezip to the current working directory"""

    # Build the base url
    base_url = get_base_url(ctx, env)
    parsed_url = urlparse(base_url)
    sep = len(parsed_url.netloc.split('.')) > 2 and '-' or '.'
    url_parts = [
        parsed_url.scheme,
        'archive{}{}'.format(sep, parsed_url.netloc),
    ] + list(parsed_url[2:])
    base_url = urlunparse(url_parts)

    col_hash = '{}/{}'.format(col_id, col_version)
    # Fetch metadata
    url = '{}/content/{}'.format(base_url, col_hash)
    resp = requests.get(url)
    if resp.status_code >= 400:
        raise MissingContent(col_id, col_version)
    col_metadata = resp.json()
    uuid = col_metadata['id']
    version = col_metadata['version']

    # Generate full output dir as soon as we have the version
    if output_dir is None:
        output_dir = Path.cwd() / '{}_1.{}'.format(col_id, version)
    else:
        output_dir = Path(output_dir)
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir

    # ... and check if it's already been downloaded
    if output_dir.exists():
        raise ExistingOutputDir(output_dir)

    # Fetch extras (includes head and downloadable file info)
    url = '{}/extras/{}@{}'.format(base_url, uuid, version)
    resp = requests.get(url)

    # Latest defaults to successfully baked - we need headVersion
    if col_version == 'latest':
        version = resp.json()['headVersion']
        url = '{}/extras/{}@{}'.format(base_url, uuid, version)
        resp = requests.get(url)

    col_extras = resp.json()

    if version != col_extras['headVersion']:
        logger.warning("Fetching non-head version of {}."
                       "\n    Head: {},"
                       " requested {}".format(col_id,
                                              col_extras['headVersion'],
                                              version))
        if not(confirm("Fetch anyway? [y/n] ")):
            raise OldContent()

    # Write tree
    tree = col_metadata['tree']
    os.mkdir(str(output_dir))

    num_pages = _count_leaves(tree) + 1
    label = 'Downloading to {}'.format(output_dir.relative_to(Path.cwd()))
    with click.progressbar(length=num_pages,
                           label=label,
                           show_pos=True) as pbar:
        _write_node(tree, base_url, output_dir, pbar, book_tree)


def _count_leaves(node, count=0):
    if 'contents' in node:
        for child in node['contents']:
            count = _count_leaves(child, count)
        return count
    else:
        return count + 1


filename_by_type = {'application/vnd.org.cnx.collection': 'collection.xml',
                    'application/vnd.org.cnx.module': 'index.cnxml'}


def _safe_name(name):
    return name.replace('/', '∕').replace(':', '∶')


def _write_node(node, base_url, out_dir, pbar, book_tree=False, pos=0, lvl=0):
    """Write out a tree node"""
    if book_tree:
        #  HACK Prepending zero-filled numbers to folders to fix the sort order
        if lvl > 0:
            #  HACK - the silly don't number Preface logic - let's use 00
            if lvl == 1 and pos == 1 and 'Preface' in node['title']:
                pos = 0
            dirname = '{:02d} {}'.format(pos, _safe_name(node['title']))
        else:
            dirname = _safe_name(node['title'])

        out_dir = out_dir / dirname
        os.mkdir(str(out_dir))

    write_dir = out_dir  # Allows nesting only for book_tree case

    resp = requests.get('{}/contents/{}'.format(base_url, node['id']))
    if resp:  # Subcollections cannot (yet) be fetched directly
        metadata = resp.json()
        resources = {r['filename']: r for r in metadata['resources']}
        filename = filename_by_type[metadata['mediaType']]
        url = '{}/resources/{}'.format(base_url, resources[filename]['id'])
        file_resp = requests.get(url)
        if not(book_tree) and filename == 'index.cnxml':
            write_dir = write_dir / metadata['legacy_id']
            os.mkdir(str(write_dir))
        filepath = write_dir / filename
        # core files are XML - this parse/serialize removes numeric entities
        filepath.write_bytes(etree.tostring(etree.XML(file_resp.text),
                                            encoding='utf-8',
                                            xml_declaration=True))
        pbar.update(1)
        # TODO Future - fetch all resources, if requested

    if 'contents' in node:
        pos = 0
        for child in node['contents']:
            pos += 1
            _write_node(child, base_url, out_dir, pbar,
                        book_tree, pos, lvl + 1)

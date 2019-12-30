import os

import click
import requests

from lxml import etree
from pathlib import Path

from ..logger import logger
from ._common import common_params, confirm, build_archive_url, calculate_sha1
from .exceptions import (MissingContent,
                         ExistingOutputDir,
                         OldContent,
                         )

@click.command()
@common_params
@click.option('-d', '--output-dir', type=click.Path(),
              help="output directory name (can't previously exist)")
@click.option('-t', '--book-tree', is_flag=True,
              help="create human-friendly book-tree")
@click.option('-r', '--with-resources', is_flag=True, default=False,
              help="Also get all resources (images)")
@click.argument('env')
@click.argument('col_id')
@click.argument('col_version')
@click.pass_context
def get(ctx, env, col_id, col_version, output_dir, book_tree, with_resources):
    """download and expand the completezip to the current working directory"""
    base_url = build_archive_url(ctx, env)

    version = None
    req_version = col_version
    if col_version.count('.') > 1:
        full_version = col_version.split('.')
        col_version = '.'.join(full_version[:2])
        version = '.'.join(full_version[1:])

    col_hash = '{}/{}'.format(col_id, col_version)
    # Fetch metadata
    url = '{}/content/{}'.format(base_url, col_hash)

    # Create a request session with retries if there's failed DNS lookups,
    # socket connections and connection timeouts.
    # See https://stackoverflow.com/questions/33895739/
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=5)
    session.mount('https://', adapter)

    # Request the collection's metadata by requests the legacy url,
    # which is redirected to the metadata url.
    resp = session.get(url)
    if resp.status_code >= 400:
        raise MissingContent(col_id, req_version)
    col_metadata = resp.json()

    # If the response is a collated (aka baked) version of the book,
    # request the non-collated (aka raw) version instead.
    if col_metadata['collated']:
        url = resp.url + '?as_collated=False'
        resp = session.get(url)
        if resp.status_code >= 400:
            # This should never happen - indicates that only baked exists?
            raise MissingContent(col_id, req_version)
        col_metadata = resp.json()

    uuid = col_metadata['id']
    # metadata fetch used legacy IDs, so will only have
    # the latest minor version - if "version" is set, the
    # user requested an explicit minor (3 part version: 1.X.Y)
    # refetch metadata, using uuid and requested version
    if version and version != col_metadata['version']:
        url = '{}/contents/{}@{}'.format(base_url, uuid, version) + \
              '?as_collated=False'
        resp = session.get(url)
        if resp.status_code >= 400:  # Requested version doesn't exist
            raise MissingContent(col_id, req_version)
        col_metadata = resp.json()

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
    resp = session.get(url)

    # Latest defaults to successfully baked - we need headVersion
    if col_version == 'latest':
        version = resp.json()['headVersion']
        url = '{}/extras/{}@{}'.format(base_url, uuid, version)
        resp = session.get(url)

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

    num_pages = _count_nodes(tree) + 1  # Num. of xml files to fetch
    try:
        label = 'Getting {}'.format(output_dir.relative_to(Path.cwd()))
    except ValueError:
        # Raised ONLY when output_dir is not a childnode of cwd
        label = 'Getting {}'.format(output_dir)
    with click.progressbar(length=num_pages,
                           label=label,
                           width=0,
                           show_pos=True) as pbar:
        _write_node(tree, base_url, output_dir, book_tree, with_resources, pbar)

def _count_nodes(node):
    if 'contents' in node:
        return sum([_count_nodes(childnode) for childnode in node['contents']])
    else:
        return 1

def _get_depth(node):
    if 'contents' in node:
        depths = []
        for childnode in node['contents']:
            depths.append(_get_depth(childnode))
        return max(depths) + 1
    else:
        return 0

filename_by_type = {
    'application/vnd.org.cnx.collection': 'collection.xml',
    'application/vnd.org.cnx.module': 'index.cnxml'
    }

def _safe_name(name):
    return name.replace('/', '∕').replace(':', '∶')

def store_sha1(sha1, write_dir, filename):
    with (write_dir / '.sha1sum').open('a') as s:
        s.write('{}  {}\n'.format(sha1, filename))

def _get_resources(resources, filename, write_dir):
    print('\n++++++++++++ GETTING RESOURCES +++++++++++')
    for res in resources:  # Dict keyed by resource filename
        #  Exclude core file, already written out
        if res != filename:
            filepath = write_dir / res
            url = resources[res]['url']
            file_resp = requests.get(url)
            filepath.write_bytes(file_resp.content)
            store_sha1(resources[res]['id'], write_dir, res) # NOTE: the id is the sha1
            print('GETTING RESOURCE FOR: {}'.format(res))
        else:
            print('NOT GETTING RESOURCE FOR: {}'.format(res))

def _clean_resources(metadata, base_url):
    resources = {}
    file_to_skip = 'index.cnxml.html'
    """
    index.cnxml.html files should not be edited nor published.
    They are generated and regenerated in-place in the database.
    So they are excluded from resources to download.
    """
    for res in metadata['resources']:
        if res['filename'] != file_to_skip:
            res.update({'url': '{}/resources/{}'.format(base_url, res['id'])})
            resources.update({res['filename'] : res})

    return resources

def _cache_node_sha1(write_dir, filename):
    sha1 = calculate_sha1(write_dir / filename)
    store_sha1(sha1, write_dir, filename)

def _make_human_readable_directories(out_dir, book_level, position, node):
    #  HACK Prepending zero-filled numbers to folders to fix the sort order
    if book_level == 0:
        dirname = _safe_name(node['title'])
    else:
        dirname = '{:02d} {}'.format(position[book_level], _safe_name(node['title']))

    out_dir = out_dir / dirname
    os.mkdir(str(out_dir))
    return out_dir


def _write_node(node, base_url, out_dir, book_tree=False, with_resources=False,
                pbar=None, depth=None, position={0: 0}, book_level=0):
    print("\n")
    print("%%" * 300)
    print('\n')
    print('==== NEW NODE ON THE BLOCK ====')
    """ Recursively write out contents of a book"""
    print("node: {}".format(node))                        ## Root of the json tree
    print("base_url: {}".format(base_url))                ## Archive url to fetch from
    print("out_dir: {}".format(out_dir))                  ## Existing directory to write out to
    print("book_tree: {}".format(book_tree))              ## Format to write (book tree or flat) as well as a click progress bar, if desired
    print("with_resources: {}".format(with_resources))
    print("pbar: {}".format(pbar))
    print("depth: {}".format(depth))                      ## Depth is height of tree
    print("position: {}".format(position))                ## Used to reset the lowest book_level counter (pages) per chapter, i.e. position: {book: ##, chapter: ##, page: ##}
    print("book_level: {}".format(book_level))            ## Book Levels - 0: book, 1: unit , 2: chapter, 3: module/page, .... for A & P book col11496
    """ Remaining args are used for recursion """

    if depth is None:
        depth = _get_depth(node)
        position = {0: 0}
        book_level = 0

    if book_tree:
        out_dir = _make_human_readable_directories(out_dir, book_level, position, node)

    write_dir = out_dir  # Allows nesting only for book_tree case

    # Fetch and store the core file for each node
    resp = requests.get('{}/contents/{}'.format(base_url, node['id']))
    if resp:  # Subcollections cannot (yet) be fetched directly
        metadata = resp.json()
        resources = _clean_resources(metadata, base_url)

        # Deal with core XML file and output directory
        filename = filename_by_type[metadata['mediaType']] #returns collection.xml or index.cnxml
        url = resources[filename]['url']
        file_resp = requests.get(url)

        if not(book_tree) and filename == 'index.cnxml':
            write_dir = write_dir / metadata['legacy_id'] #write_dir changes if you're not a book tree and you have a filename index.cnxml
            os.mkdir(str(write_dir))

        filepath = write_dir / filename
        # core files are XML - this parse/serialize removes numeric entities
        filepath.write_bytes(etree.tostring(etree.XML(file_resp.content),
                                            encoding='utf-8'))

        _cache_node_sha1(write_dir, filename)

        if with_resources:
            _get_resources(resources, filename, write_dir)

        if pbar is not None:
            pbar.update(1)

    if 'contents' in node:  # Top-book_level or subcollection - recurse
        book_level += 1
        if book_level not in position:
            position[book_level] = 0
        if book_level == depth:  # Reset counter for bottom-most book_level: pages
            position[book_level] = 0
        for childnode in node['contents']:
            #  HACK - Silly don't number Preface/Introduction logic
            preface = (book_level == 1 and position[1] == 0 and 'Preface' in childnode['title'])
            introduction = (position[book_level] == 0 and childnode['title'] == 'Introduction')
            if preface or introduction:
                position[book_level] = 0
            else:
                position[book_level] += 1
            # if position.get(2) is None or position.get(2) < 2:
            #     _write_node(childnode, base_url, out_dir, book_tree, with_resources,
            #                 pbar, depth, position, book_level)
            _write_node(childnode, base_url, out_dir, book_tree, with_resources,
                        pbar, depth, position, book_level)

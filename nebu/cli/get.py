import os
import time

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

import concurrent.futures
import urllib.request

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

def _load_url(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as conn:
        return conn.read()

def get_resources(resources, filename, write_dir):
    print('\n++++++++++++ GETTING RESOURCES +++++++++++')
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures_to_url =  {}
        for resource in resources:
            url = resources[resource]['url']
            futures_to_url.update({executor.submit(_load_url, url, 60): resource})

        for future in concurrent.futures.as_completed(futures_to_url):
            resource = futures_to_url[future]
            if not resources[resource]['skip_download']:
                content = future.result()
                file_path = write_dir / resource
                file_path.write_bytes(content)
                # NOTE: 'id' is the sha1
                store_sha1(resources[resource]['id'], write_dir, resource)
                print('GETTING RESOURCE FOR: {}'.format(resource))

def _clean_resources(metadata, base_url):
    resources = {}
    file_to_skip = 'index.cnxml.html'
    """
    index.cnxml.html files should not be edited nor published.
    They are generated and regenerated in-place in the database.
    So they are excluded from resources to download.
    """
    for res in metadata['resources']:
        res.update({'url': '{}/resources/{}'.format(base_url, res['id'])})
        res.update({'skip_download': res['filename'] == file_to_skip})
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
            get_resources(resources, filename, write_dir)

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

def _get_versions(col_version):
    version = None
    req_version = col_version
    if col_version.count('.') > 1:
        full_version = col_version.split('.')
        col_version = '.'.join(full_version[:2])
        version = '.'.join(full_version[1:])
    return req_version, col_version, version

def fetch_metadata(session, base_url, legacy_url, col_id, req_version, version):
    # Legacy url redirects to the metadata url
    resp = session.get(legacy_url)
    if resp.status_code >= 400:
        raise MissingContent(col_id, req_version)
    collection_metadata = resp.json()

    baked_version = collection_metadata['collated']
    if baked_version:
        raw_url = resp.url + '?as_collated=False'
        raw_version = session.get(raw_url)
        if raw_version.status_code >= 400:
            # Should never happen: Indicates that only baked exists.
            raise MissingContent(col_id, req_version)
        collection_metadata = raw_version.json()

    uuid = collection_metadata['id']
    if version and version != collection_metadata['version']:
        # If "version" is set and explicit minor (3 part version: 1.X.Y) was requested
        # Refetch metadata, using uuid and requested version
        raw_query = 'as_collated=False'
        url = '{}/contents/{}@{}?{}'.format(base_url, uuid, version, raw_query)
        resp = session.get(url)
        if resp.status_code >= 400:
            raise MissingContent(col_id, req_version)
        collection_metadata = resp.json()
    return collection_metadata

def build_legacy_url(base_url, col_id, col_version):
    col_hash = '{}/{}'.format(col_id, col_version)
    legacy_url = '{}/content/{}'.format(base_url, col_hash)
    return legacy_url

def build_output_directory(output_dir, col_id, version):
    if output_dir is None:
        output_dir = Path.cwd() / '{}_1.{}'.format(col_id, version)
    else:
        output_dir = Path(output_dir)
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir
    if output_dir.exists():
        raise ExistingOutputDir(output_dir)
    return output_dir

def fetch_extras(session, base_url, uuid, version, col_id, latest=False):
    # Extras (includes head and downloadable file info)
    extras_url = '{}/extras/{}@{}'.format(base_url, uuid, version)
    resp = session.get(extras_url)

    # Latest defaults to successfully baked - we need headVersion
    if latest:
        version = resp.json()['headVersion']
        extras_url = '{}/extras/{}@{}'.format(base_url, uuid, version)
        resp = session.get(extras_url)

    col_extras = resp.json()
    if version != col_extras['headVersion']:
        logger.warning(
            """
            Fetching non-head version of {}.
            Head: {},
            Requested: {}
            """.format(col_id, col_extras['headVersion'], version))
        if not(confirm("Fetch anyway? [y/n] ")):
            raise OldContent()

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
    start_time = time.time()
    base_url = build_archive_url(ctx, env)
    req_version, col_version, version = _get_versions(col_version)

    # Create a request session with retries if there's failed DNS lookups,
    # socket connections and connection timeouts.
    # See https://stackoverflow.com/questions/33895739/
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=5)
    session.mount('https://', adapter)

    # Fetch Metadata
    legacy_url = build_legacy_url(base_url, col_id, col_version)
    metadata = fetch_metadata(session, base_url, legacy_url, col_id, req_version, version)

    # Build Output Directory
    version = metadata['version']
    output_dir = build_output_directory(output_dir, col_id, version)

    # Fetch Extras
    uuid = metadata['id']
    fetch_extras(session, base_url, uuid, version, col_id, col_version == 'latest')

    # Write tree ???
    tree = metadata['tree']
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

    duration = time.time() - start_time
    print("Fetch took {} seconds".format(duration))

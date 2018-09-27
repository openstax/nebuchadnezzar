import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import os
import imghdr

import click
import requests
from litezip import (
    convert_completezip,
)

from ..logger import logger
from ._common import common_params, confirm, get_base_url, gen_coll_dir_name
from .exceptions import *  # noqa: F403


@click.command()
@common_params
@click.option('-d', '--output-dir', type=click.Path(),
              help="output directory name (can't previously exist)")
@click.argument('env')
@click.argument('col_id')
@click.argument('col_version')
@click.pass_context
def get(ctx, env, col_id, col_version, output_dir):
    """download and expand the completezip to the current working directory"""
    # Determine the output directory
    tmp_dir = Path(tempfile.mkdtemp())
    zip_filepath = tmp_dir / 'complete.zip'

    def build_base_url(ctx, env):
        base_url = get_base_url(ctx, env)
        parsed_url = urlparse(base_url)
        sep = len(parsed_url.netloc.split('.')) > 2 and '-' or '.'
        url_parts = [
            parsed_url.scheme,
            'archive{}{}'.format(sep, parsed_url.netloc),
        ] + list(parsed_url[2:])
        return urlunparse(url_parts)

    def build_metadata_url(col_id, col_version):
        # col_hash = '{}/{}'.format(col_id, col_version)
        return '{}/content/{}/{}'.format(base_url, col_hash, col_version)

    def build_extras_url(base_url, uuid, version):
        return '{}/extras/{}@{}'.format(base_url, uuid, version)

    def build_zip_url(base_url, zip_path):
        url = '{}{}'.format(base_url, zip_path)

    def gen_coll_dir_name(col_id, version):
        # Gen. the directory name for the unzipped collection file
        return '{}_1.{}'.format(col_id, version)

    def fetch_metadata(metadata_url):
        # Fetch metadata
        resp = requests.get(metadata_url)
        if resp.status_code >= 400:
            raise MissingContent(col_id, col_version)
        col_metadata = resp.json()
        uuid = col_metadata['id']
        version = col_metadata['version']
        return (uuid, version)

    def fetch_extras(extras_url):
        # Fetch extras (includes head and downloadable file info)
        if col_version != 'latest':
            resp = requests.get(url)

        if col_version == 'latest':
            latest_version = resp.json()['headVersion']
            resp = requests.get(extras_url)
            return

            extras_json = resp.json()

        if version != latest_version:
            logger.warning("Fetching non-head version of {}."
                           "\n    Head: {},"
                           " requested {}".format(col_id,
                                                  col_extras['headVersion'],
                                                  version))
            if not(confirm("Fetch anyway? [y/n] ")):
                raise OldContent()

    def fetch_zip(zip_url):
        logger.debug('Request sent to {} ...'.format(zip_url))
        zip_resp = requests.get(zip_url, stream=True)
        return zip_resp

    def gen_output_dir_name(output_dir):
        if output_dir: # if provided a dir name
            # turn it into a Path
            output_dir = Path(dir_name)

            if output_dir.exists():
                raise ExistingOutputDir(output_dir)
        else:
            my_output_dir = Path(dir_name)

            if my_output_dir.exists():
                raise ExistingOutputDir(my_output_dir)
        return something

    def gen_output_dir_name_WIP(output_dir):
        if output_dir is None:
            # generate one from the collection name and version
            if col_version == 'latest':
                specific_version = version
            else:
                specific_version = col_version

            output_dir = Path.cwd() / gen_coll_dir_name(col_id, specific_version)

            if output_dir.exists():
                raise ExistingOutputDir(output_dir)
        return something

    ##########################################
    dir_name = gen_coll_dir_name(col_id, col_version)

    base_url = build_base_url(ctx, env)


    metadata_url = build_metadata_url(col_id, col_version)

    uuid, version = fetch_metadata(metadata_url)

    extras_url = build_extras_url(base_url, uuid, version)
    extras_resp = fetch_extras(extras_url)

    def get_zip_info():
        pass
        # Get zip url from downloads
        zipinfo = [d for d in col_extras['downloads']
                   if d['format'] == 'Offline ZIP'][0]

        if zipinfo['state'] != 'good':
            logger.info("The content exists,"
                        " but the completezip is {}".format(zipinfo['state']))
            raise MissingContent(col_id, col_version)

        zip_path = zipinfo['path']

        zip_url = build_zip_url(base_url, zip_path)

        zip_resp = fetch_zip(zip_url)

        if not zip_resp:
            logger.debug("Response code is {}".format(zip_resp.status_code))
            raise MissingContent(col_id, col_version)
        elif zip_resp.status_code == 204:
            logger.info("The content exists, but the completezip is missing")
            raise MissingContent(col_id, col_version)


    content_size = int(zip_resp.headers['Content-Length'].strip())
    label = 'Downloading {}'.format(col_id)
    progressbar = click.progressbar(label=label, length=content_size)
    with progressbar as pbar, zip_filepath.open('wb') as fb:
        for buffer_ in zip_resp.iter_content(1024):
            if buffer_:
                fb.write(buffer_)
                pbar.update(len(buffer_))

    label = 'Extracting {}'.format(col_id)
    with zipfile.ZipFile(str(zip_filepath), 'r') as zip:
        progressbar = click.progressbar(iterable=zip.infolist(),
                                        label=label,
                                        show_eta=False)
        with progressbar as pbar:
            for i in pbar:
                zip.extract(i, path=str(tmp_dir))

    extracted_dir = Path([x for x in tmp_dir.glob('col*_complete')][0])

    logger.debug(
        "Converting completezip at '{}' to litezip".format(extracted_dir))
    convert_completezip(extracted_dir)

    logger.debug(
        "Removing resource files in {}".format(extracted_dir))
    for dirpath, dirnames, filenames in os.walk(str(extracted_dir)):
        for name in filenames:
            full_path = os.path.join(dirpath, name)
            if imghdr.what(full_path):
                os.remove(full_path)

    logger.debug(
        "Cleaning up extraction data at '{}'".format(tmp_dir))
    shutil.copytree(str(extracted_dir), str(output_dir))
    shutil.rmtree(str(tmp_dir))

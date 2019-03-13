import io
from pathlib import Path
import shutil

import click
import docker

from ..logger import logger
from ._common import common_params


IMAGE_TAG = 'openstax/princexml'
INPUT_FILE = 'collection.baked.xhtml'
OUTPUT_FILE = 'collection.pdf'
MOUNT_POINT = '/out'


# This file will live somewhere else in the future
PRINCEXML_DOCKERFILE = r"""
FROM ubuntu:18.04
WORKDIR /
RUN apt-get update && apt-get install -y wget
RUN apt-get install -y libcurl4 \
        libfontconfig1 \
        libfreetype6 \
        libgif7 \
        libgomp1 \
        libjpeg8 \
        liblcms2-2 \
        libpixman-1-0 \
        libpng16-16 \
        libtiff5 \
        libxml2
ENV PRINCE_DEB=prince_11.4-1_ubuntu18.04_amd64.deb
RUN wget http://www.princexml.com/download/$PRINCE_DEB && \
    dpkg -i $PRINCE_DEB && \
    rm -f $PRINCE_DEB
RUN mkdir /out
WORKDIR /out
""".encode('utf-8')


@click.command()
@common_params
@click.option('--build', is_flag=True,
              help='Force build the princexml image even if the image exists')
@click.option('-s', '--style', type=click.Path(exists=True),
              help='The stylesheet to apply to the pdf')
@click.option('-i', '--input-file',
              type=click.Path(exists=True, file_okay=True),
              help='Location of the input file')
@click.argument('collection_path')
@click.pass_context
def pdf(ctx, collection_path, build, style, input_file):
    """Generate a pdf from the baked html in COLLECTION_PATH"""
    if input_file:
        input_file = Path(input_file)
    else:
        input_file = Path(collection_path) / INPUT_FILE
    if not input_file.is_file():
        raise ValueError('Input file {} not found or is not a file.'.format(
            input_file))
    output_file = Path(collection_path) / OUTPUT_FILE
    mounted_input_file = Path(MOUNT_POINT) / input_file.name
    mounted_output_file = Path(MOUNT_POINT) / OUTPUT_FILE
    if style:
        # copy style file into COLLECTION_PATH so it can be found in the
        # container
        dest = shutil.copy(style, collection_path)
        mounted_style_file = Path(MOUNT_POINT) / Path(dest).name

    client = docker.from_env()
    try:
        client.images.pull(IMAGE_TAG)
    except docker.errors.ImageNotFound:
        # the image might eventually be available on docker hub, but if it's
        # not available, we can build the image ourselves
        pass
    images = client.images.list(IMAGE_TAG)
    if not images or build:
        logger.info('Building the {} image...'.format(IMAGE_TAG))
        # docker build -t openstax/princexml
        image, build_logs = client.images.build(
            fileobj=io.BytesIO(PRINCEXML_DOCKERFILE), tag=IMAGE_TAG, rm=True)
        for log in build_logs:
            if 'stream' in log:
                logger.debug(log['stream'])

    # docker run --rm openstax/princexml
    #    --mount type=bind,source=col12345_1.23.45,target=/out
    #    prince -v --output=/out/collection.pdf --style=a.css \
    #        /out/collection.baked.xhtml
    command = ['prince', '-v', '--output="{}"'.format(mounted_output_file),
               str(mounted_input_file)]
    if style:
        command.insert(1, '--style="{}"'.format(mounted_style_file))
    command = ' '.join(command)
    logger.debug('command: {}'.format(command))
    run_logs = client.containers.run(
        IMAGE_TAG, command=command, remove=True,
        mounts=[docker.types.Mount(
            target=MOUNT_POINT, type='bind',
            source=str(Path(collection_path).absolute()))])
    logger.debug(run_logs.decode('utf-8'))
    logger.info('PDF generated {}'.format(output_file))

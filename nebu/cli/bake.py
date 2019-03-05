import os
from pathlib import Path

import click
import cnxeasybake
from lxml import etree

from ..logger import logger
from ._common import common_params


INPUT_FILE = 'collection.mathified.xhtml'
OUTPUT_FILE = 'collection.baked.xhtml'


def get_input_file_path(collection_path):
    for root, dirs, files in os.walk(collection_path):
        if INPUT_FILE in files:
            return Path(root, INPUT_FILE)


@click.command()
@common_params
@click.option('-r', '--recipe', type=click.Path(exists=True, file_okay=True),
              help='Path to a CSS3 ruleset stylesheet recipe')
@click.option('-s', '--style', type=click.Path(exists=True, file_okay=True),
              help='Path to a CSS file to include in the html')
@click.option('-i', '--input-file',
              type=click.Path(exists=True, file_okay=True),
              help='Location of the input file')
@click.argument('collection_path')
@click.pass_context
def bake(ctx, collection_path, recipe, style, input_file):
    """Use cnx-easybake to bake the collection html"""
    if input_file:
        input_file = Path(input_file)
    else:
        input_file = get_input_file_path(collection_path)
    if not input_file or not input_file.is_file():
        raise ValueError('Input file {} not found or is not a file.'.format(
            input_file))
    output_file = input_file.parent / OUTPUT_FILE

    oven = cnxeasybake.Oven(recipe)
    with input_file.open('r') as f:
        html_doc = etree.parse(f)
    oven.bake(html_doc)
    if style:
        head = html_doc.xpath('/x:html/x:head', namespaces={
            'x': 'http://www.w3.org/1999/xhtml'})
        if head:
            etree.SubElement(head[0], 'link', {
                'rel': 'stylesheet',
                'type': 'text/css',
                'href': str(Path(style).absolute()),
            })
    with output_file.open('wb') as f:
        f.write(etree.tostring(html_doc))
    logger.info('Baked HTML in {}'.format(output_file))

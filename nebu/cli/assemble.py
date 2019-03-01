import click


from nebu.assembler import assembler


from ._common import common_params


@click.command()
@common_params
@click.argument('collection_path',
                type=click.Path(exists=True, file_okay=False))
def assemble(collection_path):
    """Generate a single XHTML file of all the module HTML files located in
    source directory combined."""
    assembler(collection_path)

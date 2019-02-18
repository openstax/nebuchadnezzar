import click

from ._common import common_params, logger


@click.command(name='list')
@common_params
@click.pass_context
def list_settings(context):
    """List of valid environment names and numbering classes from config.

    Names are required for get and publish"""
    envs = context.obj['settings']['environs']
    lines = []
    for env, val in envs.items():
        lines.append('{}\t{url}'.format(env, **val))
    lines.sort()
    lines.insert(0, '----\t---')
    lines.insert(0, 'Name\tURL')
    lines.append('------')
    lines.append(
        'Unnumbered classes: {}'.format(
            context.obj['settings']['skip_number_classes']
        )
    )
    logger.info('\n'.join(lines))

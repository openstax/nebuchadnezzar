"""Commandline utility for publishing content"""
import click
import sys
import requests
import re

from nebu import __version__
from ..config import prepare

from .atom import config_atom
from .get import get
from .environment import list_environments
from .publish import publish
from .validate import validate


__all__ = ('cli',)


def _version_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    working_version = __version__
    click.echo('Nebuchadnezzar {}'.format(working_version))
    installed_semver_match = re.match(r"^\d\.*\d*\.*\d*(?=\+)",
                                      working_version)
    try:
        installed_semver = installed_semver_match.group(0)
    except AttributeError:
        click.echo("The semantic version of Neb could not be read.\n"
                   "Please submit a bug report.",
                   file=sys.stderr)
        ctx.exit()
    latest_version = get_latest_released_version()
    if installed_semver < latest_version:
        click.echo("Version {0} available for install.".format(latest_version),
                   file=sys.stderr)
    ctx.exit()


def get_pypi_releases():
    """Fetch Neb package releases available via pip, sorted from oldest to
    newest. If a network error occurs, returns an empty list.
    """
    try:
        url = "https://pypi.org/pypi/nebuchadnezzar/json"
        data = requests.get(url).json()
        try:
            releases_from_request = data["releases"]
        except KeyError:
            click.echo("The PyPi API schema seems to have changed.\n"
                       "Please submit a bug report.",
                       file=sys.stderr)
            return []
        sorted_releases = sorted(list(releases_from_request.keys()))
        return sorted_releases
    except requests.exceptions.RequestException:
        return []


def get_latest_released_version():
    """Get the latest released version of Neb. If no releases found,
    returns an empty string
    """
    try:
        return get_pypi_releases()[-1]
    except IndexError:
        return ""


@click.group()
@click.option('--version', callback=_version_callback, is_flag=True,
              expose_value=False, is_eager=True,
              help='Show the version and exit')
@click.pass_context
def cli(ctx):
    env = prepare()
    ctx.obj = env


cli.add_command(config_atom)
cli.add_command(get)
cli.add_command(list_environments)
cli.add_command(publish)
cli.add_command(validate)

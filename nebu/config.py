import configparser
import os
from pathlib import Path


CONFIG_FILE_LOC = Path.home() / '.config/nebuchadnezzar.ini'
CONFIG_SECTION_ENVIRON_PREFIX = 'environ-'

INITIAL_DEFAULT_CONFIG = """\
[settings]

# If set, this has the same effect as `neb get -t` and `neb get -f`
# respectively. If default is the opposite flag will override

# default_book_format = tree|flat

# This provides the classes used to supress numbering of first-pages
# in chapters and books, such as 'introduction' or 'preface'

# skip_number_classes = <class-1> <class-2> [...]

# [environ-<short-name>]
# url = <base-url-to-the-environment>

[environ-dev]
url = https://dev.cnx.org

[environ-qa]
url = https://qa.cnx.org

[environ-staging]
url = https://staging.cnx.org

[environ-prod]
url = https://cnx.org

[environ-content01]
url = https://content01.cnx.org

[environ-content02]
url = https://content02.cnx.org

[environ-content03]
url = https://content03.cnx.org

[environ-content04]
url = https://content04.cnx.org

[environ-content05]
url = https://content05.cnx.org

[environ-staged]
url = https://staged.cnx.org
"""


def _write_default_config_file():
    """Writes the default config file to the filesystem."""
    CONFIG_FILE_LOC.parent.mkdir(exist_ok=True)  # create ~/.config
    with CONFIG_FILE_LOC.open('w') as fb:
        fb.write(INITIAL_DEFAULT_CONFIG)


def discover_settings():
    """Discover settings from environment variables and config files

    TODO Document what env vars are actually looked at.
    TODO Document config file location lookup

    :param dict settings: An existing settings value
    :return: dictionary of settings
    :rtype: dict

    """
    # Lookup the location of the configuration file.
    # If NEB_CONFIG is defined the file specified is used.
    config_filepath = os.environ.get('NEB_CONFIG', None)
    if config_filepath:
        config_filepath = Path(config_filepath)
        assert config_filepath.exists()
    else:
        config_filepath = CONFIG_FILE_LOC
        if not config_filepath.exists():
            _write_default_config_file()

    config = configparser.ConfigParser()
    config.read(str(config_filepath))

    settings = {
        '_config_file': config_filepath.resolve(),
        'environs': {
            # short-name : settings
        },
    }
    for section in config.sections():
        if section.startswith(CONFIG_SECTION_ENVIRON_PREFIX):
            short_name = section[len(CONFIG_SECTION_ENVIRON_PREFIX):]
            settings['environs'][short_name] = dict(config[section])
        elif section == 'settings':
            settings.update(config[section])
        else:
            # Ignore other sections
            pass   # pragma: no cover
    return settings


def prepare():
    """This function prepares an application/script for use.

    :return: an environment dictionary containing the newly created
             ``settings`` and a ``closer`` function.
    :rtype: dict

    """
    # Get the settings
    settings = discover_settings()

    def closer():  # pragma: no cover
        pass

    return {'closer': closer, 'settings': settings}

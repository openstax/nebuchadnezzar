# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


setup_requires = (
    'pytest-runner',
    )
install_requires = (
    'cnx-litezip',
    # FIXME progressbar33 is a fork of progressbar. Let's see if we can't
    #       align the universe.
    'progressbar33',
    'requests',
    'venusian',
    )
tests_require = [
    'pytest',
    'requests-mock',
    ]
extras_require = {
    'test': tests_require,
    }
description = "Connexions Nebu publishing utility"
with open('README.rst', 'r') as readme:
    long_description = readme.read()

setup(
    name='nebuchadnezzar',
    version='0.0.0',
    author='Connexions team',
    author_email='info@cnx.org',
    url="https://github.com/connexions/nebuchadnezzar",
    license='AGPL, See also LICENSE.txt',
    description=description,
    long_description=long_description,
    setup_requires=setup_requires,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require=extras_require,
    test_suite='nebu.tests',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'nebu.tests': ['data/**/*.*'],
        },
    entry_points="""\
    [console_scripts]
    neb = nebu.cli.main:main
    """,
    )

import nebu.cli.main


def test_for_version(monkeypatch, invoker):
    version = 'X.Y.Z'

    monkeypatch.setattr(nebu.cli.main, '__version__', version)

    from nebu.cli.main import cli
    args = ['--version']
    result = invoker(cli, args)
    assert result.exit_code == 0

    expected_output = 'Nebuchadnezzar {}\n'.format(version)
    assert result.output == expected_output


def test_old_version(monkeypatch, invoker):
    version = '0.0.0'

    monkeypatch.setattr(nebu.cli.main, '__version__', version)

    from nebu.cli.main import cli
    args = ['--version']
    result = invoker(cli, args)
    assert result.exit_code == 0

    import re
    expected_output = 'Nebuchadnezzar {}\n'.format(version)
    expected_output += "Version available for install.\n"
    output_no_version = re.sub(r"Version \w+(\.\w+)* available",
                               "Version available",
                               result.output)
    assert output_no_version == expected_output

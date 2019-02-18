def test_for_list(monkeypatch, invoker):

    from nebu.cli.main import cli
    args = ['list']
    result = invoker(cli, args)
    assert result.exit_code == 0

    expected_output = (
        'Name\tURL\n'
        '----\t---\n'
        'test-env\thttps://cnx.org\n'
        '------\n'
        'Unnumbered classes: introduction\n'
    )

    assert result.output == expected_output

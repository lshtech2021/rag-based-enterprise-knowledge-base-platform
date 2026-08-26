from kb_ingestion.cli import build_parser, run


def test_cli_requires_user_agent(capsys, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    code = run(["--cik", "320193", "--backend", "memory"])
    assert code == 2
    err = capsys.readouterr().out
    assert "User-Agent" in err


def test_cli_requires_openai_key(capsys, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    code = run(
        [
            "--cik",
            "320193",
            "--backend",
            "memory",
            "--user-agent",
            "App test@example.com",
        ]
    )
    assert code == 2
    err = capsys.readouterr().out
    assert "OPENAI_API_KEY" in err


def test_cli_parser_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["--cik", "320193", "--user-agent", "App test@example.com", "--backend", "local"]
    )
    assert args.backend == "local"
    assert args.forms == "10-K,10-Q,8-K"


def test_cli_parser_accepts_compose_backend() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["--cik", "320193", "--user-agent", "App test@example.com", "--backend", "compose"]
    )
    assert args.backend == "compose"

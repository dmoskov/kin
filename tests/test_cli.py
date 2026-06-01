"""Tests for the CLI module — parser construction and command dispatch.

Commands that hit the database use a temporary SQLite DB.
"""

from unittest.mock import MagicMock, patch

import pytest

from cli import COMMANDS, build_parser, main
from database.connection import init_db
from database.repository import TreeRepository
from models.person import Gender, Person
from models.relationship import Relationship

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", path)
    init_db(path)
    return path


@pytest.fixture
def repo(db_path):
    return TreeRepository(db_path)


# ── Parser ────────────────────────────────────────────────────────────


class TestBuildParser:
    def test_all_commands_registered(self):
        parser = build_parser()
        assert parser is not None
        for cmd in COMMANDS:
            assert cmd in COMMANDS

    def test_parse_init(self):
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"

    def test_parse_add_person(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "add-person",
                "--id",
                "alice",
                "--given",
                "Alice",
                "--surname",
                "Smith",
                "--gender",
                "female",
                "--birth-date",
                "1990-01-01",
            ]
        )
        assert args.command == "add-person"
        assert args.id == "alice"
        assert args.given == "Alice"
        assert args.gender == "female"

    def test_parse_add_parent(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "add-parent",
                "--parent",
                "dad",
                "--child",
                "kid",
            ]
        )
        assert args.command == "add-parent"
        assert args.parent == "dad"
        assert args.child == "kid"

    def test_parse_add_union(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "add-union",
                "--partner1",
                "p1",
                "--partner2",
                "p2",
                "--date",
                "2020-06-01",
            ]
        )
        assert args.command == "add-union"
        assert args.partner1 == "p1"

    def test_parse_add_event(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "add-event",
                "--person",
                "alice",
                "--type",
                "career",
                "--date",
                "2015-01",
                "--description",
                "New job",
            ]
        )
        assert args.command == "add-event"
        assert args.person == "alice"
        assert args.type == "career"

    def test_parse_search(self):
        parser = build_parser()
        args = parser.parse_args(["search", "Smith"])
        assert args.query == "Smith"

    def test_parse_serve(self):
        parser = build_parser()
        args = parser.parse_args(["serve", "--port", "9000"])
        assert args.port == 9000

    def test_parse_serve_default_port(self):
        parser = build_parser()
        args = parser.parse_args(["serve"])
        assert args.port == 8000

    def test_parse_import_export(self):
        parser = build_parser()
        args = parser.parse_args(["import", "data.json"])
        assert args.file == "data.json"
        args = parser.parse_args(["export", "out.json"])
        assert args.file == "out.json"

    def test_parse_add_source(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "add-source",
                "--id",
                "src1",
                "--name",
                "Census",
            ]
        )
        assert args.command == "add-source"
        assert args.id == "src1"

    def test_parse_cite(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "cite",
                "--source",
                "src1",
                "--entity-type",
                "person",
                "--entity-id",
                "alice",
            ]
        )
        assert args.command == "cite"
        assert args.source == "src1"


# ── Command execution ─────────────────────────────────────────────────


class TestCommands:
    def test_cmd_init(self, db_path, capsys):
        main(["init"])
        out = capsys.readouterr().out
        assert "Database initialized" in out

    def test_cmd_add_person(self, db_path, capsys):
        main(
            [
                "add-person",
                "--id",
                "bob",
                "--given",
                "Bob",
                "--surname",
                "Jones",
            ]
        )
        out = capsys.readouterr().out
        assert "Added" in out

    def test_cmd_list_empty(self, db_path, capsys):
        main(["list"])
        out = capsys.readouterr().out
        assert "No people" in out

    def test_cmd_list_with_people(self, db_path, repo, capsys):
        repo.save_person(
            Person(
                id="alice",
                given_name="Alice",
                surname="Smith",
                gender=Gender.FEMALE,
                birth_date="1990-01-01",
            )
        )
        main(["list"])
        out = capsys.readouterr().out
        assert "Alice" in out
        assert "Total: 1" in out

    def test_cmd_search(self, db_path, repo, capsys):
        repo.save_person(
            Person(
                id="alice",
                given_name="Alice",
                surname="Smith",
            )
        )
        main(["search", "Alice"])
        out = capsys.readouterr().out
        assert "alice" in out

    def test_cmd_search_no_results(self, db_path, capsys):
        main(["search", "Nobody"])
        out = capsys.readouterr().out
        assert "No results" in out

    def test_cmd_stats(self, db_path, repo, capsys):
        repo.save_person(Person(id="a", given_name="A", surname="B"))
        main(["stats"])
        out = capsys.readouterr().out
        assert "People:" in out
        assert "1" in out

    def test_cmd_show(self, db_path, repo, capsys):
        repo.save_person(
            Person(
                id="alice",
                given_name="Alice",
                surname="Smith",
                birth_date="1990-05-15",
                birth_place="Portland",
            )
        )
        main(["show", "alice"])
        out = capsys.readouterr().out
        assert "Alice Smith" in out
        assert "1990-05-15" in out

    def test_cmd_show_not_found(self, db_path):
        with pytest.raises(SystemExit):
            main(["show", "nobody"])

    def test_cmd_add_parent(self, db_path, repo, capsys):
        repo.save_person(Person(id="dad", given_name="D", surname="S"))
        repo.save_person(Person(id="kid", given_name="K", surname="S"))
        main(["add-parent", "--parent", "dad", "--child", "kid"])
        out = capsys.readouterr().out
        assert "Added relationship" in out

    def test_cmd_add_union(self, db_path, repo, capsys):
        repo.save_person(Person(id="p1", given_name="A", surname="X"))
        repo.save_person(Person(id="p2", given_name="B", surname="Y"))
        main(["add-union", "--partner1", "p1", "--partner2", "p2"])
        out = capsys.readouterr().out
        assert "Added union" in out

    def test_cmd_add_event(self, db_path, repo, capsys):
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        main(
            [
                "add-event",
                "--person",
                "alice",
                "--type",
                "career",
                "--date",
                "2020-01",
                "--description",
                "Promoted",
            ]
        )
        out = capsys.readouterr().out
        assert "Added event" in out

    def test_cmd_export_import_roundtrip(self, db_path, repo, tmp_path, capsys):
        repo.save_person(
            Person(
                id="alice",
                given_name="Alice",
                surname="Smith",
            )
        )
        export_path = str(tmp_path / "export.json")
        main(["export", export_path])
        out = capsys.readouterr().out
        assert "Exported" in out

        main(["import", export_path])
        out = capsys.readouterr().out
        assert "Imported" in out

    def test_cmd_add_source(self, db_path, capsys):
        main(["add-source", "--id", "src1", "--name", "Census 1900"])
        out = capsys.readouterr().out
        assert "Added source" in out

    def test_cmd_sources_empty(self, db_path, capsys):
        main(["sources"])
        out = capsys.readouterr().out
        assert "No sources" in out

    def test_no_command_exits(self):
        with pytest.raises(SystemExit):
            main([])

    def test_cmd_relationship(self, db_path, repo, capsys):
        repo.save_person(Person(id="dad", given_name="Dad", surname="Smith"))
        repo.save_person(Person(id="kid", given_name="Kid", surname="Smith"))
        repo.save_relationship(Relationship(parent_id="dad", child_id="kid"))
        main(["relationship", "kid", "dad"])
        out = capsys.readouterr().out
        assert "Dad Smith" in out

    def test_cmd_relationship_not_found(self, db_path, repo):
        with pytest.raises(SystemExit):
            main(["relationship", "nobody", "nope"])

    def test_cmd_timeline_person(self, db_path, repo, capsys):
        repo.save_person(
            Person(
                id="alice",
                given_name="Alice",
                surname="S",
                birth_date="1990-01-01",
            )
        )
        main(["timeline", "alice"])
        out = capsys.readouterr().out
        assert "Timeline" in out

    def test_cmd_timeline_all(self, db_path, repo, capsys):
        repo.save_person(
            Person(
                id="alice",
                given_name="Alice",
                surname="S",
                birth_date="1990-01-01",
            )
        )
        main(["timeline", "--all"])
        out = capsys.readouterr().out
        assert "Family Timeline" in out

    def test_cmd_timeline_no_args(self, db_path):
        with pytest.raises(SystemExit):
            main(["timeline"])

    def test_cmd_serve(self, db_path):
        mock_serve = MagicMock()
        mock_web_server = MagicMock()
        mock_web_server.serve = mock_serve
        with patch.dict("sys.modules", {"web_server": mock_web_server}):
            import importlib

            import cli as cli_mod

            importlib.reload(cli_mod)
            cli_mod.main(["serve", "--port", "9999"])
            mock_serve.assert_called_once_with(port=9999)

    def test_cmd_cite(self, db_path, repo, capsys):
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        from models.source import Source, SourceType

        repo.save_source(Source(id="src1", name="Census", source_type=SourceType.OTHER))
        main(
            [
                "cite",
                "--source",
                "src1",
                "--entity-type",
                "person",
                "--entity-id",
                "alice",
            ]
        )
        out = capsys.readouterr().out
        assert "Cited" in out


class TestAudit:
    def test_clean_data_reports_no_issues(self, repo, capsys):
        repo.save_person(
            Person(id="p", given_name="Pat", surname="X", birth_date="1950", gender=Gender.MALE)
        )
        repo.save_person(
            Person(id="c", given_name="Chris", surname="X", birth_date="1980", gender=Gender.MALE)
        )
        repo.save_relationship(Relationship(parent_id="p", child_id="c"))
        main(["audit"])
        out = capsys.readouterr().out
        assert "No relationship issues found" in out

    def test_detects_reversed_edge(self, repo, capsys):
        repo.save_person(
            Person(
                id="young", given_name="Young", surname="P", birth_date="1984", gender=Gender.MALE
            )
        )
        repo.save_person(
            Person(id="old", given_name="Old", surname="C", birth_date="1950", gender=Gender.MALE)
        )
        repo.save_relationship(Relationship(parent_id="young", child_id="old"))  # reversed
        main(["audit"])
        out = capsys.readouterr().out
        assert "likely-reversed" in out
        assert "Young" in out and "Old" in out

    def test_fix_swaps_reversed_edge(self, repo, capsys):
        repo.save_person(
            Person(
                id="young", given_name="Young", surname="P", birth_date="1984", gender=Gender.MALE
            )
        )
        repo.save_person(
            Person(id="old", given_name="Old", surname="C", birth_date="1950", gender=Gender.MALE)
        )
        repo.save_relationship(Relationship(parent_id="young", child_id="old"))
        main(["audit", "--fix"])
        assert "Fixed" in capsys.readouterr().out
        tree = repo.load_tree()
        # edge should now be old -> young
        edge = tree.relationships[0]
        assert edge.parent_id == "old" and edge.child_id == "young"

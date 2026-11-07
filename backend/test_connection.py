

from app.database import connection as db_connection
from unittest.mock import MagicMock, call


def test_create_user_table(monkeypatch):
    mock_create_all = MagicMock()
    monkeypatch.setattr(
        db_connection.Base.metadata,
        "create_all",
        mock_create_all,
    )

    db_connection.create_user_table()

    mock_create_all.assert_called_once()
    kwargs = mock_create_all.call_args.kwargs

    assert kwargs["bind"] is db_connection.engine
    assert len(kwargs["tables"]) == 1
    assert kwargs["tables"][0].name == "users"


def test_ensure_pgvector_extension(monkeypatch):
    mock_connection = MagicMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_connection

    monkeypatch.setattr(db_connection, "engine", mock_engine)

    db_connection.ensure_pgvector_extension()

    mock_connection.execute.assert_called_once()
    sql = str(mock_connection.execute.call_args.args[0])
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    
def test_ensure_conversation_schema_executes_sql(monkeypatch):
    mock_connection = MagicMock()
    mock_connection.execute.return_value.scalars.return_value.all.return_value = []

    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_connection

    monkeypatch.setattr(db_connection, "engine", mock_engine)

    db_connection.ensure_conversation_schema()

    assert mock_connection.execute.call_count > 10
    mock_engine.begin.assert_called_once()
    
def test_ensure_conversation_schema_generates_missing_ids(monkeypatch):
    mock_connection = MagicMock()
    mock_connection.execute.return_value.scalars.return_value.all.return_value = [
        "(0,1)",
        "(0,2)",
    ]

    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_connection

    monkeypatch.setattr(db_connection, "engine", mock_engine)

    db_connection.ensure_conversation_schema()

    update_calls = [
        call for call in mock_connection.execute.call_args_list
        if "UPDATE conversations SET conversation_id" in str(call.args[0])
    ]

    assert len(update_calls) == 2

    for call in update_calls:
        params = call.args[1]
        assert params["row_ctid"] in ["(0,1)", "(0,2)"]
        assert len(params["conversation_id"]) == 36

def test_ensure_conversation_messages_schema(monkeypatch):
    mock_create_all = MagicMock()

    monkeypatch.setattr(
        db_connection.Base.metadata,
        "create_all",
        mock_create_all,
    )

    db_connection.ensure_conversation_messages_schema()

    mock_create_all.assert_called_once()
    kwargs = mock_create_all.call_args.kwargs

    assert kwargs["bind"] is db_connection.engine
    assert len(kwargs["tables"]) == 1
    assert kwargs["tables"][0].name == "conversation_messages"



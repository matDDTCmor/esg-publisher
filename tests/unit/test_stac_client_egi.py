import json
import os
from unittest.mock import patch

from esgcet.stac_client import EGITransactionClient


def _make_client(dry_run, save_stac):
    args = {
        "stac_api": "https://example.org/transaction",
        "dry_run": dry_run,
        "save_stac": save_stac,
        "verbose": False,
        "silent": True,
    }
    return EGITransactionClient(args)


def test_publish_dry_run_skips_network(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = _make_client(dry_run=True, save_stac=False)
    entry = {"id": "test-item-001", "collection": "CMIP7"}

    with patch("esgcet.stac_client.requests.post") as mock_post:
        result = client.publish(entry)

    mock_post.assert_not_called()
    assert result is True


def test_publish_dry_run_writes_local_stac_item(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = _make_client(dry_run=True, save_stac=True)
    entry = {"id": "test-item-002", "collection": "CMIP7"}

    with patch("esgcet.stac_client.requests.post") as mock_post:
        client.publish(entry)

    mock_post.assert_not_called()
    written = tmp_path / "test-item-002.json"
    assert written.exists()
    assert json.loads(written.read_text()) == entry


def test_publish_live_mode_calls_network(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = _make_client(dry_run=False, save_stac=False)
    entry = {"id": "test-item-003", "collection": "CMIP7"}

    with patch("esgcet.stac_client.requests.post") as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.raise_for_status.return_value = None
        client.publish(entry)

    mock_post.assert_called_once()


def test_json_patch_dry_run_skips_network(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = _make_client(dry_run=True, save_stac=False)
    entry = [{"op": "replace", "path": "/properties/foo", "value": "bar"}]

    with patch("esgcet.stac_client.requests.patch") as mock_patch:
        client.json_patch("CMIP7", "test-item-001", entry)

    mock_patch.assert_not_called()

import logging

import esgcet.logger as logger


def _reset_logging_state(monkeypatch):
    # add_file_handler() and return_logger() both cache/install once per
    # process; force a clean slate so tests don't see each other's state.
    monkeypatch.setattr(logger, "_file_handler_installed", False)
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    for name in ("Generic NetCDF Publisher", "STAC Client"):
        named = logging.getLogger(name)
        for h in list(named.handlers):
            named.removeHandler(h)


def test_add_file_handler_creates_parent_dir_and_file(tmp_path, monkeypatch):
    _reset_logging_state(monkeypatch)
    log_path = tmp_path / "maps-cmip7" / "logs" / "publish.log"

    logger.add_file_handler(log_path)

    assert log_path.parent.is_dir()
    logging.getLogger("Publisher-Main").warning("hello from root propagation")
    for h in logging.getLogger().handlers:
        h.flush()
    assert log_path.exists()
    assert "hello from root propagation" in log_path.read_text()


def test_add_file_handler_captures_records_from_other_named_loggers(tmp_path, monkeypatch):
    # This is the actual scenario: dozens of call sites each build their
    # own ESGPubLogger()-wrapped, differently-named logger. A single
    # add_file_handler() call must capture all of them via propagation,
    # without touching each of those call sites.
    _reset_logging_state(monkeypatch)
    log_path = tmp_path / "publish.log"
    logger.add_file_handler(log_path)

    esgpub1 = logger.ESGPubLogger()
    generic_netcdf_log = esgpub1.return_logger("Generic NetCDF Publisher", False, True)
    esgpub2 = logger.ESGPubLogger()
    stac_log = esgpub2.return_logger("STAC Client", False, False)

    generic_netcdf_log.info("Making dataset...")
    stac_log.info("Dry-run mode: Not publishing")

    for h in logging.getLogger().handlers:
        h.flush()
    contents = log_path.read_text()
    assert "Making dataset..." in contents
    assert "Dry-run mode: Not publishing" in contents


def test_add_file_handler_is_idempotent(tmp_path, monkeypatch):
    _reset_logging_state(monkeypatch)
    log_path = tmp_path / "publish.log"

    logger.add_file_handler(log_path)
    logger.add_file_handler(log_path)  # second call must be a no-op

    root_file_handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, logging.FileHandler)
    ]
    assert len(root_file_handlers) == 1

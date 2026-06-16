"""DataMind Studio -- AI-native data science research system."""

__version__ = "0.1.0"

# Initialize structured logging on module import.
# setup_logging is idempotent -- calling it again only reconfigures handlers.
import os as _os
if _os.environ.get("DATAMIND_LOG_DISABLE") != "1":
    from datamind.logging_setup import setup_logging as _setup_logging
    _setup_logging()

import json
import logging
from datetime import datetime


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        return json.dumps(log_data)


def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("sealens")
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = setup_logging()

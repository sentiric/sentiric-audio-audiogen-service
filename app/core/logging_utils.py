import logging, sys, os, structlog
from datetime import datetime
from app.core.config import settings

def setup_logging(service_name):
    def suts_v4(logger, log_method, event_dict):
        event_dict["schema_v"] = "1.0.0"
        event_dict["ts"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        event_dict["severity"] = event_dict.pop("level", "info").upper()
        event_dict["tenant_id"] = event_dict.get("tenant_id", "unknown")
        event_dict["resource"] = {"service.name": service_name, "service.version": settings.APP_VERSION, "service.env": settings.ENV}
        event_dict["trace_id"] = event_dict.get("trace_id", None)
        event_dict["span_id"] = event_dict.get("span_id", None)
        event_dict["message"] = event_dict.pop("event", "LOG_EVENT")
        event_dict["event"] = event_dict.pop("event_id", "LOG_EVENT")
        return event_dict

    structlog.configure(processors=[structlog.stdlib.add_log_level, suts_v4, structlog.processors.JSONRenderer()], logger_factory=structlog.stdlib.LoggerFactory())
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

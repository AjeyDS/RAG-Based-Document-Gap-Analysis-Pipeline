"""Logging Config module for Document Gap Analysis pipeline."""
import logging
import json
import os

class JsonFormatter(logging.Formatter):
    def format(self, record):
        std_keys = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
            'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName',
            'process', 'message', 'asctime', 'taskName'
        }
        
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        for key, value in record.__dict__.items():
            if key not in std_keys:
                log_data[key] = value
                
        if record.exc_info:
            log_data['exc_info'] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

class TextFormatter(logging.Formatter):
    def format(self, record):
        std_keys = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
            'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName',
            'process', 'message', 'asctime', 'taskName'
        }
        
        extras = {}
        for key, value in record.__dict__.items():
            if key not in std_keys:
                extras[key] = value
                
        extra_str = f" {extras}" if extras else ""
        record.extra_str = extra_str
        
        return super().format(record)

def setup_logging():
    log_format = os.environ.get("LOG_FORMAT", "text").lower()
    log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    if logger.hasHandlers():
        logger.handlers.clear()
        
    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s%(extra_str)s"))
        
    logger.addHandler(handler)

    for noisy_logger in ["httpx", "openai", "httpcore"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

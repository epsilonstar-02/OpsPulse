"""
Output Handlers - Write logs to various destinations
"""
import json
import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from .models import LogEntry


class OutputHandler(ABC):
    """Base class for output handlers"""
    
    @abstractmethod
    def write(self, log_entry: LogEntry, include_labels: bool = True) -> None:
        """Write a single log entry"""
        pass
    
    @abstractmethod
    def write_batch(self, log_entries: List[LogEntry], include_labels: bool = True) -> None:
        """Write multiple log entries"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the handler and release resources"""
        pass


class StdoutHandler(OutputHandler):
    """Write logs to standard output"""
    
    def __init__(self, format: str = "json"):
        self.format = format
    
    def write(self, log_entry: LogEntry, include_labels: bool = True) -> None:
        if self.format == "json":
            print(log_entry.to_json(include_labels))
        else:
            print(log_entry.to_text(include_labels))
    
    def write_batch(self, log_entries: List[LogEntry], include_labels: bool = True) -> None:
        for entry in log_entries:
            self.write(entry, include_labels)
    
    def close(self) -> None:
        sys.stdout.flush()


class FileHandler(OutputHandler):
    """Write logs to files with rotation support"""
    
    def __init__(
        self,
        path: str = "./output/logs",
        format: str = "json",
        rotation_size_mb: int = 10,
        max_files: int = 5
    ):
        self.base_path = Path(path)
        self.format = format
        self.rotation_size_bytes = rotation_size_mb * 1024 * 1024
        self.max_files = max_files
        
        self.current_file: Optional[Any] = None
        self.current_file_path: Optional[Path] = None
        self.current_file_size = 0
        self.file_counter = 0
        
        # Ensure output directory exists
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._open_new_file()
    
    def _get_file_extension(self) -> str:
        return ".json" if self.format == "json" else ".log"
    
    def _open_new_file(self) -> None:
        """Open a new log file"""
        if self.current_file:
            self.current_file.close()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.base_path.stem}_{timestamp}_{self.file_counter}{self._get_file_extension()}"
        self.current_file_path = self.base_path.parent / filename
        
        self.current_file = open(self.current_file_path, "w", encoding="utf-8")
        self.current_file_size = 0
        self.file_counter += 1
        
        self._cleanup_old_files()
    
    def _cleanup_old_files(self) -> None:
        """Remove old files if we exceed max_files"""
        pattern = f"{self.base_path.stem}_*{self._get_file_extension()}"
        files = sorted(self.base_path.parent.glob(pattern))
        
        while len(files) > self.max_files:
            oldest = files.pop(0)
            try:
                oldest.unlink()
            except OSError:
                pass
    
    def _check_rotation(self) -> None:
        """Check if file rotation is needed"""
        if self.current_file_size >= self.rotation_size_bytes:
            self._open_new_file()
    
    def write(self, log_entry: LogEntry, include_labels: bool = True) -> None:
        self._check_rotation()
        
        if self.format == "json":
            line = log_entry.to_json(include_labels) + "\n"
        else:
            line = log_entry.to_text(include_labels) + "\n"
        
        self.current_file.write(line)
        self.current_file_size += len(line.encode("utf-8"))
    
    def write_batch(self, log_entries: List[LogEntry], include_labels: bool = True) -> None:
        for entry in log_entries:
            self.write(entry, include_labels)
        self.current_file.flush()
    
    def close(self) -> None:
        if self.current_file:
            self.current_file.close()
            self.current_file = None


class JsonLinesHandler(OutputHandler):
    """Write logs as JSON Lines format for easy processing"""
    
    def __init__(self, path: str = "./output/logs.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.path, "w", encoding="utf-8")
    
    def write(self, log_entry: LogEntry, include_labels: bool = True) -> None:
        self.file.write(log_entry.to_json(include_labels) + "\n")
    
    def write_batch(self, log_entries: List[LogEntry], include_labels: bool = True) -> None:
        for entry in log_entries:
            self.write(entry, include_labels)
        self.file.flush()
    
    def close(self) -> None:
        self.file.close()


class MultiHandler(OutputHandler):
    """Combine multiple output handlers"""
    
    def __init__(self, handlers: List[OutputHandler]):
        self.handlers = handlers
    
    def write(self, log_entry: LogEntry, include_labels: bool = True) -> None:
        for handler in self.handlers:
            handler.write(log_entry, include_labels)
    
    def write_batch(self, log_entries: List[LogEntry], include_labels: bool = True) -> None:
        for handler in self.handlers:
            handler.write_batch(log_entries, include_labels)
    
    def close(self) -> None:
        for handler in self.handlers:
            handler.close()


def create_output_handler(config: Dict[str, Any]) -> OutputHandler:
    """Factory function to create output handler from config"""
    output_config = config.get("output", {})
    format_type = output_config.get("format", "json")
    destination = output_config.get("destination", "stdout")
    
    handlers = []
    
    if destination in ["stdout", "both"]:
        handlers.append(StdoutHandler(format=format_type))
    
    if destination in ["file", "both"]:
        file_config = output_config.get("file", {})
        handlers.append(FileHandler(
            path=file_config.get("path", "./output/logs"),
            format=format_type,
            rotation_size_mb=file_config.get("rotation_size_mb", 10),
            max_files=file_config.get("max_files", 5)
        ))
    
    if len(handlers) == 1:
        return handlers[0]
    elif len(handlers) > 1:
        return MultiHandler(handlers)
    else:
        return StdoutHandler(format=format_type)

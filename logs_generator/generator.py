"""
Log Generator - Main log generation engine
"""
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Generator, Optional
import numpy as np
from faker import Faker

from .models import LogEntry, LogLevel, AnomalyType
from .templates import MessageTemplates
from .anomalies import AnomalyGenerator
from .output import OutputHandler, create_output_handler

fake = Faker()


class LogGenerator:
    """Main log generation engine"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sources = config.get("sources", [])
        self.normal_config = config.get("normal_logs", {})
        self.generator_config = config.get("generator", {})
        self.timestamp_config = config.get("timestamps", {})
        
        self.anomaly_generator = AnomalyGenerator(config)
        
        # Initialize timestamp
        start = self.timestamp_config.get("start", "now")
        if start == "now":
            self.current_timestamp = datetime.now()
        else:
            self.current_timestamp = datetime.fromisoformat(start)
        
        # Build source weights
        self._build_source_weights()
        
        # Build log level weights
        self._build_level_weights()
    
    def _build_source_weights(self) -> None:
        """Build weighted source selection"""
        self.source_names = []
        self.source_weights = []
        self.source_services = {}
        
        for source in self.sources:
            name = source.get("name", "application")
            weight = source.get("weight", 0.25)
            services = source.get("services", ["default-service"])
            
            self.source_names.append(name)
            self.source_weights.append(weight)
            self.source_services[name] = services
    
    def _build_level_weights(self) -> None:
        """Build weighted log level selection"""
        levels_config = self.normal_config.get("log_levels", {})
        
        self.levels = []
        self.level_weights = []
        
        level_mapping = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
            "CRITICAL": LogLevel.CRITICAL,
        }
        
        for level_name, weight in levels_config.items():
            if level_name in level_mapping:
                self.levels.append(level_mapping[level_name])
                self.level_weights.append(weight)
        
        # Ensure we have default levels
        if not self.levels:
            self.levels = [LogLevel.INFO, LogLevel.DEBUG, LogLevel.WARNING, LogLevel.ERROR]
            self.level_weights = [0.7, 0.15, 0.1, 0.05]
    
    def _select_source(self) -> tuple:
        """Select a random source and service"""
        if not self.source_names:
            return "application", "default-service"
        
        source = random.choices(self.source_names, weights=self.source_weights, k=1)[0]
        service = random.choice(self.source_services.get(source, ["default-service"]))
        return source, service
    
    def _select_level(self) -> LogLevel:
        """Select a random log level based on weights"""
        return random.choices(self.levels, weights=self.level_weights, k=1)[0]
    
    def _generate_response_time(self, is_anomaly: bool = False) -> float:
        """Generate realistic response time"""
        rt_config = self.normal_config.get("response_time", {})
        
        if is_anomaly:
            # Anomalous response times are much higher
            return random.uniform(1000, 10000)
        
        mean = rt_config.get("mean", 150)
        std = rt_config.get("std", 50)
        min_rt = rt_config.get("min", 10)
        max_rt = rt_config.get("max", 500)
        
        # Generate from normal distribution
        response_time = np.random.normal(mean, std)
        return max(min_rt, min(max_rt, response_time))
    
    def _advance_timestamp(self) -> datetime:
        """Advance the current timestamp"""
        increment_config = self.timestamp_config.get("increment", {})
        min_inc = increment_config.get("min", 0.001)
        max_inc = increment_config.get("max", 2.0)
        
        increment = random.uniform(min_inc, max_inc)
        self.current_timestamp += timedelta(seconds=increment)
        return self.current_timestamp
    
    def generate_normal_log(self) -> LogEntry:
        """Generate a single normal log entry"""
        timestamp = self._advance_timestamp()
        source, service = self._select_source()
        level = self._select_level()
        
        message, context = MessageTemplates.get_message(source, level.value)
        
        # Determine status code based on level
        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            status_code = MessageTemplates.get_status_code("server_error")
            error_code = MessageTemplates.get_error_code()
        elif level == LogLevel.WARNING:
            status_code = MessageTemplates.get_status_code("client_error")
            error_code = None
        else:
            status_code = MessageTemplates.get_status_code("success")
            error_code = None
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            source=source,
            service=service,
            message=message,
            request_id=context.get("request_id"),
            user_id=context.get("user_id") if random.random() > 0.5 else None,
            ip_address=context.get("ip") if random.random() > 0.3 else None,
            response_time_ms=self._generate_response_time(),
            status_code=status_code if source == "web-server" else None,
            endpoint=MessageTemplates.get_endpoint() if source in ["web-server", "application"] else None,
            method=MessageTemplates.get_method() if source == "web-server" else None,
            error_code=error_code,
            is_anomaly=False,
            anomaly_type=AnomalyType.NONE,
            anomaly_score=0.0
        )
    
    def generate_log(self) -> LogEntry:
        """Generate a single log entry (normal or anomalous)"""
        # Check if we should start a new anomaly
        if self.anomaly_generator.should_start_anomaly():
            self.anomaly_generator.start_anomaly()
        
        # If an anomaly is active, generate anomalous log
        if self.anomaly_generator.is_active:
            timestamp = self._advance_timestamp()
            source, service = self._select_source()
            log = self.anomaly_generator.generate_anomalous_log(timestamp, source, service)
            # Safety check - should never be None now but handle gracefully
            if log is not None:
                return log
        
        # Otherwise generate normal log
        return self.generate_normal_log()
    
    def generate_batch(self, size: Optional[int] = None) -> List[LogEntry]:
        """Generate a batch of log entries"""
        if size is None:
            size = self.generator_config.get("batch_size", 100)
        
        return [self.generate_log() for _ in range(size)]
    
    def generate_stream(self, total: Optional[int] = None) -> Generator[LogEntry, None, None]:
        """Generate a stream of log entries"""
        if total is None:
            total = self.generator_config.get("total_logs", 0)
        
        count = 0
        while total == 0 or count < total:
            yield self.generate_log()
            count += 1
    
    def run(self, output_handler: OutputHandler) -> None:
        """Run the generator with the given output handler"""
        total_logs = self.generator_config.get("total_logs", 1000)
        batch_size = self.generator_config.get("batch_size", 100)
        interval = self.generator_config.get("interval", 1.0)
        include_labels = self.config.get("output", {}).get("include_labels", True)
        
        generated = 0
        
        try:
            while total_logs == 0 or generated < total_logs:
                remaining = total_logs - generated if total_logs > 0 else batch_size
                current_batch_size = min(batch_size, remaining)
                
                batch = self.generate_batch(current_batch_size)
                output_handler.write_batch(batch, include_labels)
                
                generated += len(batch)
                
                # Count anomalies for logging
                anomaly_count = sum(1 for log in batch if log.is_anomaly)
                print(f"\rGenerated {generated} logs ({anomaly_count} anomalies in last batch)", 
                      end="", flush=True)
                
                if total_logs == 0 or generated < total_logs:
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            print(f"\n\nGeneration interrupted. Total logs generated: {generated}")
        finally:
            output_handler.close()
        
        print(f"\n\nGeneration complete. Total logs generated: {generated}")


def create_generator(config: Dict[str, Any]) -> LogGenerator:
    """Factory function to create a log generator"""
    return LogGenerator(config)

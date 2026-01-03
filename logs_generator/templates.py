"""
Message Templates - Realistic log message generators
"""
import random
from typing import Dict, List, Tuple
from faker import Faker

fake = Faker()


class MessageTemplates:
    """Generate realistic log messages for different scenarios"""
    
    # Web server messages
    WEB_INFO = [
        'GET {endpoint} HTTP/1.1" {status} {bytes}',
        'POST {endpoint} HTTP/1.1" {status} {bytes}',
        "Request completed successfully for {endpoint}",
        "Served static file: {file}",
        "Connection established from {ip}",
        "SSL handshake completed for {domain}",
        "Cache hit for {endpoint}",
        "Upstream response received in {time}ms",
    ]
    
    WEB_WARNING = [
        "Slow response detected: {time}ms for {endpoint}",
        "Rate limit approaching for IP {ip}",
        "Connection pool nearing capacity: {percent}%",
        "Retry attempt {attempt} for upstream {service}",
        "Certificate expiring in {days} days for {domain}",
        "High memory usage detected: {percent}%",
    ]
    
    WEB_ERROR = [
        "Failed to connect to upstream {service}: Connection refused",
        "Request timeout after {time}ms for {endpoint}",
        "SSL certificate verification failed for {domain}",
        "502 Bad Gateway - upstream {service} unavailable",
        "Connection reset by peer for {ip}",
        "Max retries exceeded for {endpoint}",
    ]
    
    # Application messages
    APP_INFO = [
        "User {user_id} logged in successfully",
        "Processing request {request_id}",
        "Transaction {transaction_id} completed",
        "Cache updated for key {cache_key}",
        "Background job {job_id} started",
        "Webhook delivered to {endpoint}",
        "Email sent to {email}",
        "File uploaded: {filename} ({size} bytes)",
        "API call to {service} completed successfully",
        "Session created for user {user_id}",
    ]
    
    APP_WARNING = [
        "Deprecated API endpoint called: {endpoint}",
        "Slow database query: {time}ms",
        "Rate limit exceeded for user {user_id}",
        "Retry scheduled for failed job {job_id}",
        "Low disk space: {percent}% remaining",
        "Queue depth high: {count} messages pending",
        "Memory usage warning: {percent}%",
    ]
    
    APP_ERROR = [
        "Failed to process payment for order {order_id}: {error}",
        "Database connection lost: {error}",
        "Authentication failed for user {user_id}",
        "Service {service} returned error: {status_code}",
        "Failed to send notification: {error}",
        "Invalid request payload: {error}",
        "Transaction rollback for {transaction_id}: {error}",
    ]
    
    APP_CRITICAL = [
        "CRITICAL: Database connection pool exhausted",
        "CRITICAL: Out of memory - service degraded",
        "CRITICAL: Disk full - unable to write logs",
        "CRITICAL: Circuit breaker opened for {service}",
        "CRITICAL: Data corruption detected in {table}",
    ]
    
    # Database messages
    DB_INFO = [
        "Query executed in {time}ms: {query_type}",
        "Connection established from {client}",
        "Checkpoint completed in {time}ms",
        "Index rebuilt for {table}",
        "Backup completed successfully: {size}",
        "Replication lag: {lag}ms",
    ]
    
    DB_WARNING = [
        "Slow query detected: {time}ms",
        "Connection pool utilization: {percent}%",
        "Lock wait timeout for {table}",
        "High replication lag: {lag}ms",
        "Tablespace {name} at {percent}% capacity",
    ]
    
    DB_ERROR = [
        "Query failed: {error}",
        "Connection refused from {client}",
        "Deadlock detected on {table}",
        "Replication broken: {error}",
        "Constraint violation: {constraint}",
    ]
    
    # Infrastructure messages
    INFRA_INFO = [
        "Pod {pod} started successfully in namespace {namespace}",
        "Container {container} health check passed",
        "Node {node} joined cluster",
        "Deployment {deployment} rolled out successfully",
        "ConfigMap {name} updated",
        "Service {service} endpoint updated",
        "Metric scraped: {metric}={value}",
    ]
    
    INFRA_WARNING = [
        "Pod {pod} restarting: count={count}",
        "Node {node} memory pressure: {percent}%",
        "Container {container} OOMKilled",
        "Deployment {deployment} scaling: {replicas} replicas",
        "PVC {pvc} at {percent}% capacity",
        "Network latency spike: {latency}ms",
    ]
    
    INFRA_ERROR = [
        "Pod {pod} CrashLoopBackOff",
        "Node {node} NotReady",
        "Container {container} failed to start: {error}",
        "Service {service} endpoints not available",
        "PVC {pvc} provisioning failed",
        "Network policy violation: {policy}",
    ]
    
    # Security threat messages
    SECURITY_THREATS = {
        "brute_force": [
            "Multiple failed login attempts for user {user}: {count} attempts",
            "Account locked due to excessive failed logins: {user}",
            "Suspicious authentication pattern detected from {ip}",
            "Password spray attack detected from {ip}",
        ],
        "sql_injection": [
            "Potential SQL injection detected in parameter: {param}",
            "Blocked malicious query pattern: {pattern}",
            "WAF triggered: SQL injection attempt from {ip}",
            "Suspicious characters in request: {chars}",
        ],
        "xss_attempt": [
            "XSS attempt blocked in parameter: {param}",
            "Script injection detected from {ip}",
            "Encoded XSS payload blocked: {payload}",
            "Content-Security-Policy violation from {ip}",
        ],
        "unauthorized_access": [
            "Unauthorized access attempt to {resource} from {ip}",
            "Privilege escalation attempt by user {user}",
            "Access denied: insufficient permissions for {resource}",
            "Token validation failed for user {user}",
            "Suspicious API key usage pattern detected",
        ],
    }
    
    # Resource exhaustion messages
    RESOURCE_EXHAUSTION = {
        "memory": [
            "Memory usage critical: {percent}%",
            "OOM killer invoked for process {process}",
            "Memory allocation failed: {error}",
            "Heap size exceeded threshold: {size}MB",
        ],
        "cpu": [
            "CPU usage critical: {percent}%",
            "Process {process} consuming excessive CPU",
            "Thread pool exhausted",
            "CPU throttling active",
        ],
        "disk": [
            "Disk usage critical: {percent}%",
            "Write failed: No space left on device",
            "Disk I/O latency spike: {latency}ms",
            "Inode exhaustion warning",
        ],
        "connections": [
            "Connection pool exhausted",
            "Max connections reached: {count}",
            "Socket timeout: too many open connections",
            "File descriptor limit reached",
        ],
    }
    
    ENDPOINTS = [
        "/api/v1/users", "/api/v1/orders", "/api/v1/products",
        "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/refresh",
        "/api/v1/payments", "/api/v1/inventory", "/api/v1/notifications",
        "/api/v2/search", "/api/v2/recommendations", "/health", "/metrics",
        "/graphql", "/webhook/stripe", "/webhook/github",
    ]
    
    HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    
    STATUS_CODES = {
        "success": [200, 201, 204],
        "redirect": [301, 302, 304],
        "client_error": [400, 401, 403, 404, 422, 429],
        "server_error": [500, 502, 503, 504],
    }
    
    ERROR_CODES = [
        "ERR_TIMEOUT", "ERR_CONNECTION_REFUSED", "ERR_NOT_FOUND",
        "ERR_UNAUTHORIZED", "ERR_FORBIDDEN", "ERR_VALIDATION",
        "ERR_INTERNAL", "ERR_SERVICE_UNAVAILABLE", "ERR_RATE_LIMIT",
    ]
    
    @classmethod
    def get_message(cls, source: str, level: str) -> Tuple[str, Dict]:
        """Get a random message template and fill with fake data"""
        templates_map = {
            ("web-server", "INFO"): cls.WEB_INFO,
            ("web-server", "WARNING"): cls.WEB_WARNING,
            ("web-server", "ERROR"): cls.WEB_ERROR,
            ("web-server", "CRITICAL"): cls.WEB_ERROR,
            ("application", "INFO"): cls.APP_INFO,
            ("application", "WARNING"): cls.APP_WARNING,
            ("application", "ERROR"): cls.APP_ERROR,
            ("application", "CRITICAL"): cls.APP_CRITICAL,
            ("database", "INFO"): cls.DB_INFO,
            ("database", "WARNING"): cls.DB_WARNING,
            ("database", "ERROR"): cls.DB_ERROR,
            ("database", "CRITICAL"): cls.DB_ERROR,
            ("infrastructure", "INFO"): cls.INFRA_INFO,
            ("infrastructure", "WARNING"): cls.INFRA_WARNING,
            ("infrastructure", "ERROR"): cls.INFRA_ERROR,
            ("infrastructure", "CRITICAL"): cls.INFRA_ERROR,
        }
        
        templates = templates_map.get((source, level), cls.APP_INFO)
        template = random.choice(templates)
        
        # Generate context data
        context = cls._generate_context()
        
        try:
            message = template.format(**context)
        except KeyError:
            message = template
        
        return message, context
    
    @classmethod
    def get_security_message(cls, threat_type: str) -> Tuple[str, Dict]:
        """Get a security threat message"""
        templates = cls.SECURITY_THREATS.get(threat_type, cls.SECURITY_THREATS["unauthorized_access"])
        template = random.choice(templates)
        context = cls._generate_context()
        
        try:
            message = template.format(**context)
        except KeyError:
            message = template
        
        return message, context
    
    @classmethod
    def get_resource_message(cls, resource_type: str) -> Tuple[str, Dict]:
        """Get a resource exhaustion message"""
        templates = cls.RESOURCE_EXHAUSTION.get(resource_type, cls.RESOURCE_EXHAUSTION["memory"])
        template = random.choice(templates)
        context = cls._generate_context()
        
        try:
            message = template.format(**context)
        except KeyError:
            message = template
        
        return message, context
    
    @classmethod
    def _generate_context(cls) -> Dict:
        """Generate fake data for message templates"""
        return {
            "endpoint": random.choice(cls.ENDPOINTS),
            "ip": fake.ipv4(),
            "user": fake.user_name(),
            "user_id": fake.uuid4()[:8],
            "request_id": fake.uuid4(),
            "transaction_id": f"TXN-{fake.random_number(digits=8)}",
            "order_id": f"ORD-{fake.random_number(digits=6)}",
            "job_id": f"JOB-{fake.random_number(digits=5)}",
            "status": random.choice([200, 201, 400, 401, 403, 404, 500, 502, 503]),
            "status_code": random.choice([200, 201, 400, 401, 403, 404, 500, 502, 503]),
            "bytes": random.randint(100, 50000),
            "time": random.randint(10, 5000),
            "percent": random.randint(70, 99),
            "count": random.randint(1, 100),
            "attempt": random.randint(1, 5),
            "days": random.randint(1, 30),
            "service": random.choice(["auth-service", "payment-service", "user-service"]),
            "domain": fake.domain_name(),
            "email": fake.email(),
            "filename": fake.file_name(),
            "size": random.randint(1024, 10485760),
            "cache_key": f"cache:{fake.word()}:{fake.uuid4()[:8]}",
            "error": random.choice([
                "Connection refused", "Timeout exceeded", "Invalid response",
                "Network unreachable", "Service unavailable", "Rate limited"
            ]),
            "file": f"/static/{fake.file_name(extension='js')}",
            "query_type": random.choice(["SELECT", "INSERT", "UPDATE", "DELETE"]),
            "client": f"{fake.ipv4()}:{random.randint(30000, 65535)}",
            "table": random.choice(["users", "orders", "products", "sessions"]),
            "constraint": random.choice(["pk_users", "fk_orders_users", "uk_email"]),
            "lag": random.randint(10, 10000),
            "name": fake.word(),
            "pod": f"{fake.word()}-{fake.hexify('??????')}",
            "container": fake.word(),
            "node": f"node-{random.randint(1, 10)}",
            "namespace": random.choice(["default", "production", "staging"]),
            "deployment": f"{fake.word()}-deployment",
            "replicas": random.randint(1, 10),
            "pvc": f"pvc-{fake.word()}",
            "metric": random.choice(["cpu_usage", "memory_usage", "request_count"]),
            "value": round(random.uniform(0, 100), 2),
            "latency": random.randint(1, 1000),
            "policy": f"policy-{fake.word()}",
            "param": random.choice(["id", "name", "email", "query", "filter"]),
            "pattern": random.choice(["UNION SELECT", "OR 1=1", "DROP TABLE"]),
            "chars": random.choice(["<script>", "'; --", "1=1"]),
            "payload": "<script>alert(1)</script>",
            "resource": random.choice(["/admin", "/api/internal", "/config"]),
            "process": random.choice(["python", "java", "node", "nginx"]),
        }
    
    @classmethod
    def get_endpoint(cls) -> str:
        return random.choice(cls.ENDPOINTS)
    
    @classmethod
    def get_method(cls) -> str:
        return random.choice(cls.HTTP_METHODS)
    
    @classmethod
    def get_status_code(cls, category: str = "success") -> int:
        return random.choice(cls.STATUS_CODES.get(category, cls.STATUS_CODES["success"]))
    
    @classmethod
    def get_error_code(cls) -> str:
        return random.choice(cls.ERROR_CODES)

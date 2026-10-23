"""Bounded synchronous workers behind a buffering authenticated reverse proxy."""
bind = '0.0.0.0:8765'
workers = 2
worker_class = 'sync'
timeout = 30
graceful_timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 4096
# Do not trust client forwarding headers, even from loopback. The application
# emits relative URLs and the proxy strips the configured external path prefix.
forwarded_allow_ips = ''
forwarder_headers = ''
secure_scheme_headers = {}
accesslog = None
errorlog = '-'
loglevel = 'critical'
# No preload: database connections and mutable demo state belong to each worker.
preload_app = False

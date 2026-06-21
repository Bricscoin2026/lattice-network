# Common proxy settings shared by all /api/* locations.
# Included by nginx-frontend.conf (FASE 3 split routing).

proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;

# Failover: if the Rust gateway misbehaves (5xx, timeout, conn refused),
# nginx automatically retries on the next upstream — which for the
# location blocks that target `lattice_rust_gateway` falls back to a
# nginx-level proxy_next_upstream policy.
proxy_next_upstream error timeout http_502 http_503 http_504;
proxy_next_upstream_tries 2;

proxy_connect_timeout 2s;
proxy_send_timeout    10s;
proxy_read_timeout    30s;

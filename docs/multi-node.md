## Multi-Node API Gateway

A simple nginx configuration for multi-node API gateway.

`/etc/nginx/nginx.conf`
```nginx
user www-data;
worker_processes auto;
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
    worker_connections 768;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;


    gzip on;

    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
    upstream backend {
        server ip_addr_of_node_0:8000;
        server ip_addr_of_node_1:8000;
    }
}
```

`/etc/nginx/conf.d/default.conf`
```nginx
server {
    listen 9000;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## CPU-Node and GPU-Node communication

> [!NOTE]
> This is for RL training.

Otherwise, you need to find an available node that can ssh both CPU-Node and GPU-Node.

```bash
autossh -M 0 -fCN -L 9001:localhost:9000 user@cpu
autossh -M 0 -fCN -R 9002:localhost:9001 user@gpu
```

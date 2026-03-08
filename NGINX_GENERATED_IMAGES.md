# Nginx config for generated images

Add this location block to serve Gemini-generated images:

```nginx
location /generated/ {
    alias /home/exedev/wonderz-agentics/web_ui/frontend/dist/generated/;
}
```

Place it before the main `location /` block in `/etc/nginx/sites-enabled/default`.

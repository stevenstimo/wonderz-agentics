#!/bin/bash
set -e

LOG_DIR="/var/log/wonderz"
LOG_FILE="$LOG_DIR/monitor.log"

# Ensure log directory exists
sudo mkdir -p "$LOG_DIR"
sudo chown exedev:exedev "$LOG_DIR" 2>/dev/null || true

check_service() {
    SERVICE=$1
    
    if ! systemctl is-active --quiet $SERVICE; then
        echo "[$(date)] ERROR: $SERVICE is down!" | tee -a $LOG_FILE
        journalctl -u $SERVICE -n 20 --no-pager >> $LOG_FILE 2>&1
        return 1
    fi
    return 0
}

# Check alle services
SERVICES=("wonderz-backend" "wonderz-worker" "wonderz-frontend" "postgresql" "redis")
ALL_OK=true

for SERVICE in "${SERVICES[@]}"; do
    if ! check_service $SERVICE; then
        ALL_OK=false
    fi
done

# Check API health
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/api/health 2>/dev/null || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    echo "[$(date)] ERROR: API health check failed! HTTP $HTTP_CODE" | tee -a $LOG_FILE
    ALL_OK=false
fi

if $ALL_OK; then
    echo "[$(date)] All services OK" >> $LOG_FILE
fi

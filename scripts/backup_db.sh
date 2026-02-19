#!/bin/bash
set -e

# Config
DB_NAME="wonderz"
DB_USER="wonderz"
DB_PASSWORD="wonderz123"
BACKUP_DIR="/home/exedev/backups"
RETENTION_DAYS=7

# Maak backup directory
mkdir -p "$BACKUP_DIR"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/wonderz_${TIMESTAMP}.sql.gz"

# Voer backup uit
echo "[$(date)] Starting backup to $BACKUP_FILE"
PGPASSWORD="$DB_PASSWORD" pg_dump -h localhost -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

# Check of backup succesvol was
if [ $? -eq 0 ]; then
    echo "[$(date)] Backup successful: $(du -h $BACKUP_FILE | cut -f1)"
else
    echo "[$(date)] ERROR: Backup failed!"
    exit 1
fi

# Verwijder oude backups (ouder dan RETENTION_DAYS)
find "$BACKUP_DIR" -name "wonderz_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Cleaned up backups older than $RETENTION_DAYS days"

# Log backup size en aantal
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/wonderz_*.sql.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "[$(date)] Total: $BACKUP_COUNT backups, $TOTAL_SIZE disk usage"

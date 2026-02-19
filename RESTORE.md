# Database Restore Procedure

## In geval van data loss:

1. Stop alle services:
   ```bash
   sudo systemctl stop wonderz-backend wonderz-worker
   ```

2. Lijst beschikbare backups:
   ```bash
   ls -lh /home/exedev/backups/
   ```

3. Kies nieuwste backup en restore:
   ```bash
   BACKUP_FILE="/home/exedev/backups/wonderz_YYYYMMDD_HHMMSS.sql.gz"
   
   # Drop en recreate database
   sudo -u postgres psql -c "DROP DATABASE IF EXISTS wonderz;"
   sudo -u postgres psql -c "CREATE DATABASE wonderz OWNER wonderz;"
   
   # Restore
   gunzip -c $BACKUP_FILE | PGPASSWORD=wonderz123 psql -h localhost -U wonderz -d wonderz
   ```

4. Verifieer data:
   ```bash
   PGPASSWORD=wonderz123 psql -h localhost -U wonderz -d wonderz -c "SELECT COUNT(*) FROM jobs;"
   ```

5. Start services:
   ```bash
   sudo systemctl start wonderz-backend wonderz-worker
   ```

## Pre-migration backup:

Voor elke database migratie:
```bash
/home/exedev/wonderz-agentics/scripts/backup_db.sh
```

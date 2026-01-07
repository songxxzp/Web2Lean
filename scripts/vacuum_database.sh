#!/bin/bash
#
# Database Vacuum Script
#
# This script vacuums the SQLite database to reclaim space from deleted data.
# Run this periodically to keep the database size optimized.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Database path
DB_DIR="/datadisk/Web2Lean/data/databases"
DB_FILE="${DB_DIR}/web2lean.db"

echo "=========================================="
echo "  SQLite Database Vacuum Script"
echo "=========================================="
echo ""

# Check if database exists
if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}Error: Database file not found at $DB_FILE${NC}"
    exit 1
fi

# Show current database size
BEFORE_SIZE=$(ls -lh "$DB_FILE" | awk '{print $5}')
echo "Current database size: $BEFORE_SIZE"
echo ""

# Get record counts before vacuum
echo "Record counts before vacuum:"
sqlite3 "$DB_FILE" "
SELECT '  questions: ' || COUNT(*) FROM questions
UNION ALL
SELECT '  answers: ' || COUNT(*) FROM answers
UNION ALL
SELECT '  processing_status: ' || COUNT(*) FROM processing_status
UNION ALL
SELECT '  lean_conversion_results: ' || COUNT(*) FROM lean_conversion_results;
"
echo ""

# Check fragmentation
echo "Checking database fragmentation..."
FRAGMENTATION=$(sqlite3 "$DB_FILE" "SELECT CAST(freelist_count * page_size AS REAL) / 1024.0 / 1024.0 FROM pragma_page_count(), pragma_page_size(), pragma_freelist_count();")
FRAG_INT=$(printf "%.0f" "$FRAGMENTATION" 2>/dev/null || echo 0)

if [ "$FRAG_INT" -gt 10 ]; then
    echo -e "${YELLOW}Warning: ${FRAGMENTATION}MB of free space (fragmented) detected${NC}"
    echo "Vacuum is recommended to reclaim this space."
else
    echo -e "${GREEN}Database is not heavily fragmented (${FRAGMENTATION}MB free)${NC}"
    echo "Vacuum may not be necessary."
fi
echo ""

# Ask for confirmation
read -p "Do you want to continue with VACUUM? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Vacuum cancelled${NC}"
    exit 0
fi

echo ""
echo "Starting VACUUM... (this may take a few minutes)"

# Create backup before vacuum
BACKUP_FILE="${DB_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "Creating backup at $BACKUP_FILE..."
cp "$DB_FILE" "$BACKUP_FILE"

# Run vacuum
START_TIME=$(date +%s)
sqlite3 "$DB_FILE" "VACUUM;"
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Show results
AFTER_SIZE=$(ls -lh "$DB_FILE" | awk '{print $5}')
echo ""
echo -e "${GREEN}✓ Vacuum completed in ${DURATION}s${NC}"
echo "Database size: $BEFORE_SIZE → $AFTER_SIZE"
echo ""

# Verify data integrity
echo "Verifying data integrity..."
sqlite3 "$DB_FILE" "
PRAGMA integrity_check;
"

echo ""
echo "Record counts after vacuum:"
sqlite3 "$DB_FILE" "
SELECT '  questions: ' || COUNT(*) FROM questions
UNION ALL
SELECT '  answers: ' || COUNT(*) FROM answers
UNION ALL
SELECT '  processing_status: ' || COUNT(*) FROM processing_status
UNION ALL
SELECT '  lean_conversion_results: ' || COUNT(*) FROM lean_conversion_results;
"
echo ""

echo -e "${GREEN}✓ Database vacuum completed successfully!${NC}"
echo "Backup saved at: $BACKUP_FILE"
echo ""
echo "To remove old backups, you can run:"
echo "  rm ${DB_DIR}/web2lean.db.backup.*"

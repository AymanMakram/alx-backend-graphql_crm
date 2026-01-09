#!/bin/bash
set -euo pipefail

# Determine project root (assumes crm/cron_jobs is inside the project tree)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Run Django manage.py shell to delete customers with no orders since 1 year ago
# The Python command prints the number of deleted customers to stdout.
COUNT=$(python manage.py shell -c "from django.utils import timezone; from datetime import timedelta; from crm.models import Customer; from orders.models import Order; cutoff=timezone.now()-timedelta(days=365); active_ids=list(Order.objects.filter(created_at__gte=cutoff).values_list('customer_id', flat=True)); inactive=Customer.objects.exclude(id__in=active_ids); count=inactive.count(); inactive.delete(); print(count)" | tail -n 1)

# Log result with timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "$TIMESTAMP - Deleted ${COUNT} inactive customers" >> /tmp/customer_cleanup_log.txt

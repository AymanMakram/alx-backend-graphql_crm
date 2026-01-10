from celery import shared_task
from datetime import datetime

# Execute the project's GraphQL schema to fetch aggregates
from .schema import schema

@shared_task
def generatecrmreport():
    """
    Run a GraphQL query against the local schema to fetch:
      - totalCustomers
      - totalOrders
      - totalRevenue

    Append a single-line report to /tmp/crmreportlog.txt in the format:
      YYYY-MM-DD HH:MM:SS - Report: X customers, Y orders, Z revenue
    """
    query = '''
    query {
      crmReport {
        totalCustomers
        totalOrders
        totalRevenue
      }
    }
    '''

    result = schema.execute(query)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if result.errors:
        # Join errors into a single message and write as an "error" line
        error_text = "; ".join(str(e) for e in result.errors)
        line = f"{timestamp} - Report Error: {error_text}\n"
    else:
        data = (result.data or {}).get('crmReport') or {}
        total_customers = data.get('totalCustomers') or 0
        total_orders = data.get('totalOrders') or 0
        total_revenue = data.get('totalRevenue') or 0.0

        line = (
            f"{timestamp} - Report: "
            f"{total_customers} customers, {total_orders} orders, {total_revenue} revenue\n"
        )

    log_path = '/tmp/crmreportlog.txt'
    try:
        with open(log_path, 'a') as fh:
            fh.write(line)
    except Exception as e:
        # Ensure worker logs the failure to write
        print(f"Failed to write report to {log_path}: {e}")
        print("Report content:", line)

    # Return a small payload for task inspection/monitoring
    return {
        'timestamp': datetime.now().isoformat(),
        'customers': int(data.get('totalCustomers') or 0) if not result.errors else None,
        'orders': int(data.get('totalOrders') or 0) if not result.errors else None,
        'revenue': float(data.get('totalRevenue') or 0.0) if not result.errors else None,
        'errors': [str(e) for e in (result.errors or [])] if result.errors else []
    }

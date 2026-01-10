from celery import shared_task
from datetime import datetime
import os

# We'll execute the local GraphQL schema to fetch the summary
from .schema import schema

@shared_task
def generate_crm_report():
    """
    Execute a GraphQL query against the project's schema to fetch:
      - totalCustomers
      - totalOrders
      - totalRevenue
    Then append the report line to /tmp/crm_report_log.txt:
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

    # Default values if execution failed or values are missing
    total_customers = 0
    total_orders = 0
    total_revenue = 0.0

    if result.errors:
        # In case of errors, log them along with a notice in the report
        error_text = "; ".join(str(e) for e in result.errors)
        line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Report Error: {error_text}\n"
    else:
        data = result.data or {}
        crm_report = data.get('crmReport') or {}
        total_customers = crm_report.get('totalCustomers') or 0
        total_orders = crm_report.get('totalOrders') or 0
        total_revenue = crm_report.get('totalRevenue') or 0.0

        line = (
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Report: "
            f"{total_customers} customers, {total_orders} orders, {total_revenue} revenue\n"
        )

    # Ensure directory exists and append to the log file
    log_path = '/tmp/crm_report_log.txt'
    try:
        with open(log_path, 'a') as fh:
            fh.write(line)
    except Exception as e:
        # If writing fails, print to stdout so Celery worker logs it
        print(f"Failed to write report to {log_path}: {e}")
        print("Report content:", line)

    return {
        'timestamp': datetime.now().isoformat(),
        'customers': total_customers,
        'orders': total_orders,
        'revenue': float(total_revenue)
    }
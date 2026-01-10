from celery import shared_task
import requests
from datetime import datetime
import json

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def generate_crm_report():
    print("Generating CRM report...")

    graphql_url = "http://localhost:8000/graphql/"

    query = """
    query {
        crmReport {
            totalCustomers
            totalOrders
            totalRevenue
        }
    }
    """

    try:
        response = requests.post(
            graphql_url,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if "errors" in data:
            raise Exception(data["errors"])

        # ✅ Correct, case-sensitive key
        report_data = data["data"].get("crmReport", {})

        customer_count = report_data.get("totalCustomers", 0)
        order_count = report_data.get("totalOrders", 0)
        total_revenue = report_data.get("totalRevenue", 0)

        # ⬇️ Time bucket (idempotency)
        timestamp_key = datetime.now().strftime("%Y-%m-%d %H:%M")

        log_line = (
            f"[{timestamp_key}] "
            f"{customer_count} customers, "
            f"{order_count} orders, "
            f"${float(total_revenue):.2f} revenue\n"
        )

        log_path = "/tmp/crm_report_log.txt"

        # ✅ Idempotent file write (overwrite same minute)
        logs = {}

        try:
            with open(log_path, "r") as f:
                for line in f:
                    if line.startswith("["):
                        key = line.split("]")[0] + "]"
                        logs[key] = line
        except FileNotFoundError:
            pass

        logs[f"[{timestamp_key}]"] = log_line

        with open(log_path, "w") as f:
            f.writelines(logs.values())

        return "CRM report generated successfully."

    except Exception as e:
        print(f"Error generating CRM report: {e}")
        raise

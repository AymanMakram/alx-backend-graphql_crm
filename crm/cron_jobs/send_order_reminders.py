import logging
from datetime import datetime, timedelta
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

# 1. Setup Logging
LOG_FILE = "/tmp/order_reminders_log.txt"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 2. Setup GraphQL Client
transport = AIOHTTPTransport(url="http://localhost:8000/graphql")
client = Client(transport=transport, fetch_schema_from_transport=True)

# 3. Define the Query
query = gql(
    """
    query {
      allOrders {
        edges {
          node {
            id
            orderDate
            customer {
              email
            }
          }
        }
      }
    }
    """
)

def process_reminders():
    try:
        response = client.execute(query)
        orders = response['allOrders']['edges']
        
        one_week_ago = datetime.now() - timedelta(days=7)
        count = 0

        for edge in orders:
            node = edge['node']
            # Parse the ISO date string from GraphQL
            order_date = datetime.fromisoformat(node['orderDate'].replace('Z', '+00:00'))
            
            if order_date.replace(tzinfo=None) > one_week_ago.replace(tzinfo=None):
                email = node['customer']['email']
                order_id = node['id']
                logging.info(f"REMINDER: Order ID {order_id} for {email}")
                count += 1
        
        print("Order reminders processed!")
    except Exception as e:
        logging.error(f"Error processing reminders: {e}")

if __name__ == "__main__":
    process_reminders()

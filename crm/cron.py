import logging
from datetime import datetime
from graphene_django.utils.testing import graphql_query
from gql.transport.requests import RequestsHTTPTransport
from gql import gql, Client

def log_crm_heartbeat():
    log_file = "/tmp/crm_heartbeat_log.txt"
    timestamp = datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
    
    # Message to log
    log_message = f"{timestamp} CRM is alive\n"
    
    try:
        # Appending to the file
        with open(log_file, "a") as f:
            f.write(log_message)
            
        #Perform a simple GraphQL query to ensure the API is responsive
        from alx_backend_graphql.schema import schema
        result = schema.execute('{ hello }')
        
        if result.errors:
            with open(log_file, "a") as f:
                f.write(f"{timestamp} - GraphQL Error: {result.errors}\n")
                
    except Exception as e:
        with open(log_file, "a") as f:
            f.write(f"{timestamp} - System Error: {str(e)}\n")



def update_low_stock():
    log_file = "/tmp/low_stock_updates_log.txt"
    timestamp = datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
    
    try:
        from alx_backend_graphql.schema import schema
        
        # The mutation string
        mutation_query = """
        mutation {
          updateLowStockProducts {
            message
            updatedProducts {
              name
              stock
            }
          }
        }
        """
        
        result = schema.execute(mutation_query)
        
        if result.errors:
            with open(log_file, "a") as f:
                f.write(f"{timestamp} - Mutation Error: {result.errors}\n")
        else:
            data = result.data['updateLowStockProducts']
            message = data['message']
            products = data['updatedProducts']
            
            with open(log_file, "a") as f:
                f.write(f"{timestamp} - {message}\n")
                for p in products:
                    f.write(f"   Restocked: {p['name']} (New Stock: {p['stock']})\n")
                    
    except Exception as e:
        with open(log_file, "a") as f:
            f.write(f"{timestamp} - System Error: {str(e)}\n")

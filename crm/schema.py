import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from .filters import CustomerFilter, ProductFilter, OrderFilter
from .models import Customer, Order
from crm.models import Product
from django.db import transaction
from django.db.models import Sum

# --- Types ---
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        interfaces = (graphene.relay.Node, )
        fields = "__all__"
    

class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        interfaces = (graphene.relay.Node, )
        fields = "__all__"

    price = graphene.Float()

    def resolve_price(self, info):
        return float(self.price)

class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        interfaces = (graphene.relay.Node, )
        fields = "__all__"


# --- 1. CreateCustomer ---
class CreateCustomer(graphene.Mutation):
    class Arguments:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone_number = graphene.String()
        address = graphene.String()

    customer = graphene.Field(CustomerType)
    success = graphene.Boolean()

    def mutate(self, info, first_name, last_name, email, phone_number=None, address=None):
        # Email uniqueness check
        if Customer.objects.filter(email=email).exists():
            raise Exception("A customer with this email already exists.")

        customer = Customer.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            address=address
        )
        return CreateCustomer(customer=customer, success=True)

# --- Bulk Create Customers ---
class CustomerInput(graphene.InputObjectType):
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone_number = graphene.String()
    address = graphene.String()

class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        # We accept a LIST of our input template
        customers_data = graphene.List(CustomerInput, required=True)

    # What we return to the user
    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    def mutate(self, info, customers_data):
        success_list = []
        error_list = []

        for data in customers_data:
            try:
                # Use a 'sub-transaction' for each individual customer
                with transaction.atomic():
                    # Check uniqueness before saving
                    if Customer.objects.filter(email=data.email).exists():
                        raise Exception(f"Email {data.email} is already taken.")

                    new_customer = Customer.objects.create(
                        first_name=data.first_name,
                        last_name=data.last_name,
                        email=data.email,
                        phone_number=data.phone_number,
                        address=data.address
                    )
                    success_list.append(new_customer)
            
            except Exception as e:
                # If one fails, record the error and keep going with the next one
                error_list.append(str(e))

        return BulkCreateCustomers(customers=success_list, errors=error_list)
    
# --- 2. CreateProduct ---
class CreateProduct(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        description = graphene.String()
        price = graphene.Float(required=True) # graphene.Float maps well to DecimalField
        stock = graphene.Int(required=True)

    product = graphene.Field(ProductType)

    def mutate(self, info, name, price, stock, description=None):
        if price <= 0:
            raise Exception("Price must be greater than zero.")
        
        product = Product.objects.create(
            name=name, 
            description=description, 
            price=price, 
            stock=stock
        )
        return CreateProduct(product=product)

# --- 3. CreateOrder ---
class CreateOrder(graphene.Mutation):
    class Arguments:
        customer_id = graphene.ID(required=True)
        product_id = graphene.ID(required=True)
        quantity = graphene.Int(required=True)

    order = graphene.Field(OrderType)

    def mutate(self, info, customer_id, product_id, quantity):
        # 1. Validate Customer
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            raise Exception("Customer not found.")

        # 2. Validate Product
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise Exception("Product not found.")

        # 3. Check Stock
        if product.stock < quantity:
            raise Exception(f"Not enough stock. Only {product.stock} units available.")

        # 4. Create Order and Update Stock (using a transaction for safety)
        with transaction.atomic():
            order = Order.objects.create(
                customer=customer,
                product=product,
                quantity=quantity
            )
            
            # Decrease the product stock
            product.stock -= quantity
            product.save()

        return CreateOrder(order=order)

# 1. Define an Output Type for the list of updated products (avoid name collision with ProductType)
class RestockedProductType(graphene.ObjectType):
    name = graphene.String()
    stock = graphene.Int()

class UpdateLowStockProducts(graphene.Mutation):
    class Arguments:
        pass # No input arguments needed as it scans the DB

    message = graphene.String()
    updated_products = graphene.List(RestockedProductType)

    def mutate(self, info):
        # Find products with stock less than 10
        low_stock_items = Product.objects.filter(stock__lt=10)
        updated_list = []

        for product in low_stock_items:
            product.stock += 10
            product.save()
            updated_list.append(RestockedProductType(name=product.name, stock=product.stock))

        return UpdateLowStockProducts(
            message=f"Successfully restocked {len(updated_list)} products.",
            updated_products=updated_list
        )

# --- New: Report Type & resolver to expose aggregates to the GraphQL schema ---
class CRMReportType(graphene.ObjectType):
    totalCustomers = graphene.Int()
    totalOrders = graphene.Int()
    totalRevenue = graphene.Float()

# --- Queries ---
class Query(graphene.ObjectType):
    all_customers = DjangoFilterConnectionField(CustomerType, filterset_class=CustomerFilter)
    all_products = DjangoFilterConnectionField(ProductType, filterset_class=ProductFilter)
    all_orders = DjangoFilterConnectionField(OrderType, filterset_class=OrderFilter)

    # Aggregated report available to GraphQL clients (and tasks)
    crmReport = graphene.Field(CRMReportType)

    # These "resolver" functions tell Django how to actually get the data
    def resolve_all_customers(root, info):
        return Customer.objects.all()

    def resolve_all_products(root, info):
        return Product.objects.all()

    def resolve_all_orders(root, info):
        return Order.objects.select_related('customer', 'product').all()

    def resolve_crmReport(root, info):
        total_customers = Customer.objects.count()
        total_orders = Order.objects.count()
        # Assuming Order model has a `totalamount` field
        revenue_agg = Order.objects.aggregate(total=Sum('totalamount'))['total'] or 0.0
        return CRMReportType(
            totalCustomers=total_customers,
            totalOrders=total_orders,
            totalRevenue=float(revenue_agg)
        )

class CRMQuery(graphene.ObjectType):
    hello = graphene.String()

    def resolve_hello(root, info):
        return "Hello, GraphQL!"

# --- Mutations (single class with all mutations included) ---
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    update_low_stock_products = UpdateLowStockProducts.Field()

# Create schema after all types/mutations are defined
schema = graphene.Schema(query=Query, mutation=Mutation)
import re
import graphene
from django.db import transaction
from django.utils import timezone
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from decimal import Decimal
from . import models
from .filters import CustomerFilter, ProductFilter, OrderFilter

class CustomerType(DjangoObjectType):
    class Meta:
        model = models.Customer
        fields = ("id", "name", "email", "phone", "created_at")
        interfaces = (graphene.relay.Node,)

class ProductType(DjangoObjectType):
    class Meta:
        model = models.Product
        fields = ("id", "name", "price", "stock")
        interfaces = (graphene.relay.Node,)

class OrderType(DjangoObjectType):
    class Meta:
        model = models.Order
        fields = ("id", "customer", "order_date", "total_amount")  # exclude auto-generated products
        interfaces = (graphene.relay.Node,)

    # Convenience field to query a single product (first associated)
    product = graphene.Field(lambda: ProductType)

    # Plain list of products to allow querying { name, price } directly
    products = graphene.List(lambda: ProductType)

    # Keep a Relay connection for products, if needed elsewhere
    productsConnection = graphene.ConnectionField(ProductType._meta.connection)

    def resolve_product(self, info):
        return self.products.all().first() or None

    def resolve_products(self, info):
        return list(self.products.all())

    def resolve_productsConnection(self, info, **kwargs):
        return self.products.all()

# Simple phone validator: +1234567890 or 123-456-7890 or 1234567890
PHONE_REGEX = re.compile(r"^(\+\d{7,15}|\d{3}-\d{3}-\d{4}|\d{7,15})$")

class CreateCustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String(required=False)

class CreateCustomer(graphene.Mutation):
    class Arguments:
        input = CreateCustomerInput(required=True)

    customer = graphene.Field(CustomerType)
    ok = graphene.Boolean()
    message = graphene.String()

    @staticmethod
    def mutate(root, info, input):
        name = input.get("name")
        email = input.get("email")
        phone = input.get("phone")

        # Validate unique email
        if models.Customer.objects.filter(email__iexact=email).exists():
            return CreateCustomer(customer=None, ok=False, message="Email already exists")
        # Validate phone format if provided
        if phone and not PHONE_REGEX.match(phone):
            return CreateCustomer(customer=None, ok=False, message="Invalid phone format")
        customer = models.Customer.objects.create(name=name, email=email, phone=phone or "")
        return CreateCustomer(customer=customer, ok=True, message="Customer created successfully")

class BulkCustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String(required=False)

class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        input = graphene.List(BulkCustomerInput, required=True)

    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, input):
        created = []
        errors = []

        # Partial success: validate per record; in case you need all-or-nothing, wrap the whole loop in a single atomic transaction.
        for idx, c in enumerate(input):
            name = c.get("name")
            email = c.get("email")
            phone = c.get("phone")

            # Basic validations
            if not name or not email:
                errors.append(f"Row {idx}: name and email are required")
                continue
            if models.Customer.objects.filter(email__iexact=email).exists():
                errors.append(f"Row {idx}: Email already exists")
                continue
            if phone and not PHONE_REGEX.match(phone):
                errors.append(f"Row {idx}: Invalid phone format")
                continue

            # Create per-item to allow partial success
            try:
                with transaction.atomic():
                    customer = models.Customer.objects.create(name=name, email=email, phone=phone or "")
                    created.append(customer)
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")

        return BulkCreateCustomers(customers=created, errors=errors)

class CreateProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    price = graphene.Float(required=True)  # accept numeric input
    stock = graphene.Int(required=False, default_value=0)

class CreateProduct(graphene.Mutation):
    class Arguments:
        input = CreateProductInput(required=True)

    product = graphene.Field(ProductType)
    ok = graphene.Boolean()
    message = graphene.String()

    @staticmethod
    def mutate(root, info, input):
        name = input.get("name")
        price = input.get("price")
        stock = input.get("stock", 0)

        # Validations
        if price is None:
            return CreateProduct(product=None, ok=False, message="Price is required")
        try:
            if float(price) <= 0:
                return CreateProduct(product=None, ok=False, message="Price must be a positive number")
        except Exception:
            return CreateProduct(product=None, ok=False, message="Price must be a valid number")
        if stock is None or int(stock) < 0:
            return CreateProduct(product=None, ok=False, message="Stock cannot be negative")

        # Convert to Decimal for DB storage
        price_dec = Decimal(str(price))
        product = models.Product.objects.create(name=name, price=price_dec, stock=stock)
        return CreateProduct(product=product, ok=True, message="Product created successfully")

class CreateOrderInput(graphene.InputObjectType):
    customer_id = graphene.ID(required=True)
    product_ids = graphene.List(graphene.ID, required=True)
    order_date = graphene.DateTime(required=False)

class CreateOrder(graphene.Mutation):
    class Arguments:
        input = CreateOrderInput(required=True)

    order = graphene.Field(OrderType)
    ok = graphene.Boolean()
    message = graphene.String()

    @staticmethod
    def mutate(root, info, input):
        customer_id = input.get("customer_id")
        product_ids = input.get("product_ids") or []
        order_date = input.get("order_date")

        # Validate inputs
        try:
            customer = models.Customer.objects.get(pk=customer_id)
        except models.Customer.DoesNotExist:
            return CreateOrder(order=None, ok=False, message="Invalid customer ID")

        if not product_ids:
            return CreateOrder(order=None, ok=False, message="At least one product must be selected")

        products = []
        invalid_ids = []
        for pid in product_ids:
            try:
                products.append(models.Product.objects.get(pk=pid))
            except models.Product.DoesNotExist:
                invalid_ids.append(str(pid))

        if invalid_ids:
            return CreateOrder(order=None, ok=False, message=f"Invalid product ID(s): {', '.join(invalid_ids)}")

        with transaction.atomic():
            order = models.Order.objects.create(
                customer=customer,
                order_date=order_date or timezone.now(),
            )
            order.products.set(products)
            # Calculate total_amount as sum of product prices
            total = sum((p.price for p in products), Decimal("0"))
            order.total_amount = total
            order.save()

        return CreateOrder(order=order, ok=True, message="Order created successfully")

# Filter input types to support a single "filter" arg
class CustomerFilterInput(graphene.InputObjectType):
    nameIcontains = graphene.String(required=False)
    emailIcontains = graphene.String(required=False)
    createdAtGte = graphene.DateTime(required=False)
    createdAtLte = graphene.DateTime(required=False)
    phonePattern = graphene.String(required=False)

class ProductFilterInput(graphene.InputObjectType):
    nameIcontains = graphene.String(required=False)
    priceGte = graphene.Float(required=False)
    priceLte = graphene.Float(required=False)
    stockGte = graphene.Int(required=False)
    stockLte = graphene.Int(required=False)
    lowStock = graphene.Boolean(required=False)

class OrderFilterInput(graphene.InputObjectType):
    totalAmountGte = graphene.Float(required=False)
    totalAmountLte = graphene.Float(required=False)
    orderDateGte = graphene.DateTime(required=False)
    orderDateLte = graphene.DateTime(required=False)
    customerName = graphene.String(required=False)
    productName = graphene.String(required=False)
    productId = graphene.ID(required=False)

class Query(graphene.ObjectType):
    # Use ConnectionField to keep Relay edges, plus custom filter and order_by
    all_customers = graphene.ConnectionField(
        CustomerType._meta.connection,
        filter=CustomerFilterInput(required=False),
        order_by=graphene.String(required=False),  # changed to String
    )
    all_products = graphene.ConnectionField(
        ProductType._meta.connection,
        filter=ProductFilterInput(required=False),
        order_by=graphene.String(required=False),  # changed to String
    )
    all_orders = graphene.ConnectionField(
        OrderType._meta.connection,
        filter=OrderFilterInput(required=False),
        order_by=graphene.String(required=False),  # changed to String
    )

    def resolve_all_customers(self, info, filter=None, order_by=None, **kwargs):
        qs = models.Customer.objects.all()
        if filter:
            if filter.get("nameIcontains"):
                qs = qs.filter(name__icontains=filter["nameIcontains"])
            if filter.get("emailIcontains"):
                qs = qs.filter(email__icontains=filter["emailIcontains"])
            if filter.get("createdAtGte"):
                qs = qs.filter(created_at__gte=filter["createdAtGte"])
            if filter.get("createdAtLte"):
                qs = qs.filter(created_at__lte=filter["createdAtLte"])
            if filter.get("phonePattern"):
                qs = qs.filter(phone__istartswith=filter["phonePattern"])
        if order_by:
            qs = qs.order_by(order_by)
        return qs

    def resolve_all_products(self, info, filter=None, order_by=None, **kwargs):
        qs = models.Product.objects.all()
        if filter:
            if filter.get("nameIcontains"):
                qs = qs.filter(name__icontains=filter["nameIcontains"])
            if filter.get("priceGte") is not None:
                qs = qs.filter(price__gte=Decimal(str(filter["priceGte"])))
            if filter.get("priceLte") is not None:
                qs = qs.filter(price__lte=Decimal(str(filter["priceLte"])))
            if filter.get("stockGte") is not None:
                qs = qs.filter(stock__gte=filter["stockGte"])
            if filter.get("stockLte") is not None:
                qs = qs.filter(stock__lte=filter["stockLte"])
            if filter.get("lowStock"):
                qs = qs.filter(stock__lt=10)
        if order_by:
            qs = qs.order_by(order_by)
        return qs

    def resolve_all_orders(self, info, filter=None, order_by=None, **kwargs):
        qs = models.Order.objects.select_related("customer").prefetch_related("products")
        if filter:
            if filter.get("totalAmountGte") is not None:
                qs = qs.filter(total_amount__gte=Decimal(str(filter["totalAmountGte"])))
            if filter.get("totalAmountLte") is not None:
                qs = qs.filter(total_amount__lte=Decimal(str(filter["totalAmountLte"])))
            if filter.get("orderDateGte"):
                qs = qs.filter(order_date__gte=filter["orderDateGte"])
            if filter.get("orderDateLte"):
                qs = qs.filter(order_date__lte=filter["orderDateLte"])
            if filter.get("customerName"):
                qs = qs.filter(customer__name__icontains=filter["customerName"])
            if filter.get("productName"):
                qs = qs.filter(products__name__icontains=filter["productName"]).distinct()
            if filter.get("productId") is not None:
                qs = qs.filter(products__id=filter["productId"]).distinct()
        if order_by:
            qs = qs.order_by(order_by)
        return qs

class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()

import re
import graphene
from graphene_django import DjangoObjectType
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Customer, Product, Order

class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = "__all__"


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = "__all__"


class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        fields = "__all__"


class CRMQuery(graphene.ObjectType):
    customers = graphene.List(CustomerType)
    products = graphene.List(ProductType)
    orders = graphene.List(OrderType)

    def resolve_customers(self, info):
        return Customer.objects.all()

    def resolve_products(self, info):
        return Product.objects.all()

    def resolve_orders(self, info):
        return Order.objects.all()
    
 
class CreateCustomer(graphene.Mutation):
    customer = graphene.Field(CustomerType)
    message = graphene.String()

    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone = graphene.String()

    def mutate(self, info, name, email, phone=None):
        if Customer.objects.filter(email=email).exists():
            raise ValidationError("Email already exists")

        if phone and not re.match(r"^(\+\d{10,15}|\d{3}-\d{3}-\d{4})$", phone):
            raise ValidationError("Invalid phone format")

        customer = Customer(
            name=name,
            email=email,
            phone=phone
        )
        customer.save()

        return CreateCustomer(
            customer=customer,
            message="Customer created successfully"
        )
    

class BulkCustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String()


class BulkCreateCustomers(graphene.Mutation):
    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    class Arguments:
        input = graphene.List(BulkCustomerInput, required=True)

    def mutate(self, info, input):
        created_customers = []
        errors = []

        with transaction.atomic():
            for index, data in enumerate(input):
                try:
                    if Customer.objects.filter(email=data.email).exists():
                        raise ValidationError("Email already exists")

                    if data.phone and not re.match(
                        r"^(\+\d{10,15}|\d{3}-\d{3}-\d{4})$", data.phone
                    ):
                        raise ValidationError("Invalid phone format")

                    customer = Customer(
                        name=data.name,
                        email=data.email,
                        phone=data.phone
                    )
                    customer.save()
                    created_customers.append(customer)

                except Exception as e:
                    errors.append(f"Record {index + 1}: {str(e)}")

        return BulkCreateCustomers(
            customers=created_customers,
            errors=errors
        )

    

class CreateProduct(graphene.Mutation):
    product = graphene.Field(ProductType)

    class Arguments:
        name = graphene.String(required=True)
        price = graphene.Decimal(required=True)
        stock = graphene.Int()

    def mutate(self, info, name, price, stock=0):
        if price <= 0:
            raise ValidationError("Price must be positive")

        if stock < 0:
            raise ValidationError("Stock cannot be negative")

        product = Product(
            name=name,
            price=price,
            stock=stock
        )
        product.save()

        return CreateProduct(product=product)
    
    
class CreateOrder(graphene.Mutation):
    order = graphene.Field(OrderType)

    class Arguments:
        customer_id = graphene.ID(required=True)
        product_ids = graphene.List(graphene.ID, required=True)
        order_date = graphene.DateTime()

    def mutate(self, info, customer_id, product_ids, order_date=None):
        if not product_ids:
            raise ValidationError("At least one product is required")

        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            raise ValidationError("Invalid customer ID")

        products = Product.objects.filter(id__in=product_ids)
        if products.count() != len(product_ids):
            raise ValidationError("Invalid product ID")

        total_amount = sum(product.price for product in products)

        order = Order(
            customer=customer,
            total_amount=total_amount,
            order_date=order_date or timezone.now()
        )
        order.save()
        order.products.set(products)

        return CreateOrder(order=order)


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


class Query(graphene.ObjectType):
    all_customers = graphene.List(CustomerType)

    def resolve_all_customers(self, info):
        return Customer.objects.all()

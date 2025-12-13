from crm.models import Customer, Product

Customer.objects.get_or_create(
    name="Alice",
    email="alice@example.com",
    phone="+1234567890"
)

Product.objects.get_or_create(
    name="Laptop",
    price=999.99,
    stock=10
)
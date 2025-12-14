import django_filters
from django.db.models import Q
from .models import Customer, Product, Order

class CustomerFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    email = django_filters.CharFilter(field_name="email", lookup_expr="icontains")
    created_at__gte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_at__lte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    phone_pattern = django_filters.CharFilter(method="filter_phone_pattern")

    def filter_phone_pattern(self, queryset, name, value):
        # Example: starts with +1
        if value:
            return queryset.filter(phone__istartswith=value)
        return queryset

    class Meta:
        model = Customer  # changed from models.Customer
        fields = ["name", "email", "created_at__gte", "created_at__lte", "phone_pattern"]

class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    price__gte = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price__lte = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    stock__gte = django_filters.NumberFilter(field_name="stock", lookup_expr="gte")
    stock__lte = django_filters.NumberFilter(field_name="stock", lookup_expr="lte")
    low_stock = django_filters.BooleanFilter(method="filter_low_stock")

    def filter_low_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__lt=10)
        return queryset

    class Meta:
        model = Product  # changed from models.Product
        fields = ["name", "price__gte", "price__lte", "stock__gte", "stock__lte", "low_stock"]

class OrderFilter(django_filters.FilterSet):
    total_amount__gte = django_filters.NumberFilter(field_name="total_amount", lookup_expr="gte")
    total_amount__lte = django_filters.NumberFilter(field_name="total_amount", lookup_expr="lte")
    order_date__gte = django_filters.DateTimeFilter(field_name="order_date", lookup_expr="gte")
    order_date__lte = django_filters.DateTimeFilter(field_name="order_date", lookup_expr="lte")
    customer_name = django_filters.CharFilter(method="filter_customer_name")
    product_name = django_filters.CharFilter(method="filter_product_name")
    product_id = django_filters.NumberFilter(method="filter_product_id")

    def filter_customer_name(self, queryset, name, value):
        if value:
            return queryset.filter(customer__name__icontains=value)
        return queryset

    def filter_product_name(self, queryset, name, value):
        if value:
            return queryset.filter(products__name__icontains=value).distinct()
        return queryset

    def filter_product_id(self, queryset, name, value):
        if value is not None:
            return queryset.filter(products__id=value).distinct()
        return queryset

    class Meta:
        model = Order  # changed from models.Order
        fields = [
            "total_amount__gte",
            "total_amount__lte",
            "order_date__gte",
            "order_date__lte",
            "customer_name",
            "product_name",
            "product_id",
        ]

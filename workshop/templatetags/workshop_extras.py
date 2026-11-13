from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def rub(value):
    """12345.5 -> «12 345,50 ₽»."""
    try:
        number = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        return value
    formatted = f"{number:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} ₽"


@register.filter
def dict_get(mapping, key):
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None

# rdv/templatetags/history_extras.py

from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Retourne dictionary[key] si elle existe, sinon 0."""
    return dictionary.get(key, 0)

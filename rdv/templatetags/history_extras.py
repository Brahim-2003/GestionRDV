from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Filtre pour accéder aux valeurs d'un dictionnaire dans les templates.
    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return 0
    return dictionary.get(key, 0)
from django import template

register = template.Library()

@register.filter
def dict_get(dictionary, key):
    """Récupérer une valeur dans un dictionnaire"""
    return dictionary.get(key, [])
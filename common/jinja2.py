import os
import re
from functools import partial

from crispy_forms.utils import render_crispy_form
from django.conf import settings
from django.contrib import messages
from django.template.defaultfilters import pluralize
from django.templatetags.static import static
from django.urls import reverse
from django.utils.timezone import localtime
from govuk_frontend_jinja.templates import Environment
from govuk_frontend_jinja.templates import NunjucksExtension
from markupsafe import Markup
from webpack_loader.templatetags.webpack_loader import render_bundle
from webpack_loader.templatetags.webpack_loader import webpack_static


class GovukFrontendExtension(NunjucksExtension):
    """Builds on govuk_frontend_jinja.templates.NunjucksExtension to provide
    more template preprocessing, to fix issues translating Nunjucks templates to
    Jinja templates."""

    def preprocess(self, source, name, filename=None):
        if filename and filename.endswith(".njk"):
            source = super().preprocess(source, name, filename)

            # fix iterating objects
            # govuk_frontend_jinja only catches `params.attributes`
            iterated_objects = [
                r"item.attributes",
            ]
            source = re.sub(
                r"(for attribute, value in )(" + r"|".join(iterated_objects) + r")",
                r"\1(\2|default({}))",
                source,
            )

            # fix nested attribute access
            # NunjucksUndefined ought to catch these, but doesn't
            nested_attrs = [
                r"cell.attributes",
                r"item.conditional",
                r"item.hint",
                r"item.label",
                r"params.attributes",
                r"params.countMessage",
                r"params.formGroup",
                r"params.legend",
                r"params.prefix",
                r"params.suffix",
            ]
            source = re.sub(
                r"(" + r"|".join(nested_attrs) + r")\.",
                r"(\1|default({})).",
                source,
            )

            # fix concatenating str and int
            source = source.replace(
                "+ (params.maxlength or params.maxwords) +",
                "~ (params.maxlength or params.maxwords) ~",
            )

        return source


class GovukFrontendEnvironment(Environment):
    """Override the govuk_frontend_jinja Environment class to use our extra
    template preprocessing."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("extensions", [GovukFrontendExtension])
        super().__init__(*args, **kwargs)


def break_words(word):
    """
    Adds zero-width spaces around non-word characters to allow breaking lines
    when wrapping text.

    For example:

    >>> break_words("hello/goodbye")
    "hello&8203;/&8203;goodbye"
    """
    return Markup(re.sub(r"([^\w]+)", r"&#8203;\1&#8203;", word))


def query_transform(request, **kwargs):
    """Override query parameters in the current request string."""
    updated = request.GET.copy()
    for key, value in kwargs.items():
        updated[key] = value
    return updated.urlencode()


def environment(**kwargs):
    """
    Set up the Jinja template environment.

    Add global variables and functions.
    """
    env = GovukFrontendEnvironment(**kwargs)

    env.filters.update(
        {
            "localtime": localtime,
        },
    )
    env.globals.update(
        {
            "break_words": break_words,
            "query_transform": query_transform,
            "crispy": render_crispy_form,
            "env": os.environ.get("ENV", "dev"),
            "get_messages": messages.get_messages,
            "localtime": localtime,
            "pluralize": pluralize,
            "settings": settings,
            "static": static,
            "url": reverse,
            "webpack_static": webpack_static,
        },
    )
    env.globals["render_bundle"] = partial(render_bundle, env.globals)

    return env

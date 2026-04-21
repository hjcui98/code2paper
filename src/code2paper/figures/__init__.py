"""Figure generation backends for code2paper method drafts."""

from .backend_fallback import generate_fallback_figure
from .backend_paperbanana import generate_paperbanana_figure

__all__ = ["generate_fallback_figure", "generate_paperbanana_figure"]

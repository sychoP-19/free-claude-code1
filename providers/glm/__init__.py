"""GLM (ZhipuAI) provider exports."""

from providers.defaults import GLM_DEFAULT_BASE

from .client import GlmProvider

__all__ = [
    "GLM_DEFAULT_BASE",
    "GlmProvider",
]

"""Shared tag and impact-level vocabulary used by reports and Vim."""

DEFAULT_TAGS = (
    "delivery",
    "planning",
    "investigation",
    "implementation",
    "review",
    "documentation",
    "operations",
    "learning",
)

IMPACT_LEVELS = {
    "low": "Local improvement or small maintenance",
    "medium": "Meaningful delivery or team enablement",
    "high": "Customer, business, or cross-team impact",
}

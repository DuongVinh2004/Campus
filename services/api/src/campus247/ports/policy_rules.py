"""Port-level errors for the policy rule store."""


class Conflict(Exception):
    """Optimistic-lock or uniqueness conflict."""

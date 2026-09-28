from web import (  # noqa: F401
    account_routes,
    people_routes,
    real_estate_routes,
    reporting_routes,
    transaction_routes,
)
from web.model_blueprint import blueprint

__all__ = ["blueprint"]

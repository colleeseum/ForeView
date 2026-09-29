from .account_type_provider import AccountTypeProvider


def provider() -> AccountTypeProvider:
    return AccountTypeProvider("non_registered", "Non-registered", "taxable_growth", "liquid")

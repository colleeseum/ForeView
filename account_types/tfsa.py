from .account_type_provider import AccountTypeProvider


def provider() -> AccountTypeProvider:
    return AccountTypeProvider("tfsa", "TFSA", "tax_free", "liquid")

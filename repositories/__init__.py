"""Persistence adapters for domain objects."""

from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.person_repository import PersonRepository

__all__ = ["AccountOwnershipRepository", "AccountRepository", "PersonRepository"]

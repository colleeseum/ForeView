export function editableAccountValues(account) {
  return {
    institution: account.institution ?? '',
    name: account.name ?? '',
    account_number: account.account_number ?? '',
  };
}

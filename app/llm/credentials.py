from pydantic import SecretStr


def first_secret_value(*secrets: SecretStr | None) -> str:
    for secret in secrets:
        if secret is None:
            continue
        value = secret.get_secret_value().strip()
        if value:
            return value
    return ""

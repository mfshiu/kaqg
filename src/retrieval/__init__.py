def ensure_size(string: str, max_length: int = 300) -> str:
    if len(string) <= max_length:
        return string
    else:
        return string[:max_length - 2] + '..'

"""Pure deterministic layout; a new invocation always starts at LEFT."""


def rows(products, columns=3):
    result = []
    row = []
    for p in products:
        for _ in range(p.quantity):
            row.append(p)
            if len(row) == columns:
                result.append(row)
                row = []
    if row:
        result.append(row + [None] * (columns - len(row)))
    return result

from datetime import date

def get_current_year_quarter(d: date | None = None) -> str:
    d = d or date.today()
    y, m = d.year, d.month

    # Japanese FY year logic (April 1 start)
    fy_year = y if m >= 4 else y - 1

    # Quarter logic
    if m in (4, 5, 6):
        q = "Q1"
    elif m in (7, 8, 9):
        q = "Q2"
    elif m in (10, 11, 12):
        q = "Q3"
    else:
        q = "Q4"

    return f"{fy_year}-{q}"
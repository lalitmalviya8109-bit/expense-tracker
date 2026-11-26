import calendar
import csv
import os
from datetime import date

EXPENSE_FILE = "expenses.csv"
SUB_FILE = "subscriptions.csv"
EXPENSE_FIELDS = ["date", "description", "amount", "category"]
SUB_FIELDS = ["name", "cost", "cycle", "start_date"]

RULES = {
    "Food": ["pizza", "burger", "cafe", "grocery", "tea", "lunch", "dinner"],
    "Transport": ["uber", "ola", "bus", "metro", "fuel", "petrol", "auto"],
    "Entertainment": ["netflix", "movie", "game", "spotify", "prime"],
    "Education": ["book", "course", "fees", "stationery", "exam"],
    "Bills": ["recharge", "electricity", "wifi", "rent", "water"],
}


# ---------- storage ----------
def append_row(row, path, fields):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow(row)


def read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# ---------- categorization ----------
def categorize(description):
    text = description.lower()
    for category, words in RULES.items():
        if any(word in text for word in words):
            return category
    return "Other"


# ---------- subscription logic ----------
def add_months(d, n):
    m = d.month - 1 + n
    year = d.year + m // 12
    month = m % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_due_date(start_date, cycle):
    today = date.today()
    start = date.fromisoformat(start_date)
    step = 1 if cycle == "monthly" else 12
    n = 0
    due = start
    while due < today:
        n += step
        due = add_months(start, n)
    return due


def monthly_total(subs):
    total = 0
    for s in subs:
        cost = float(s["cost"])
        total += cost if s["cycle"] == "monthly" else cost / 12
    return round(total, 2)


# ---------- input helpers ----------
def ask_amount(prompt):
    while True:
        text = input(prompt).strip()
        try:
            value = float(text)
        except ValueError:
            print(f"'{text}' is not a number.")
            continue
        if value <= 0:
            print("Amount must be more than 0.")
            continue
        return value


# ---------- menu actions ----------
def add_expense():
    desc = input("Description: ").strip()
    amount = ask_amount("Amount: ")
    row = {"date": date.today().isoformat(), "description": desc,
           "amount": amount, "category": categorize(desc)}
    append_row(row, EXPENSE_FILE, EXPENSE_FIELDS)
    print("Saved:", row)


def view_expenses():
    rows = read_rows(EXPENSE_FILE)
    if not rows:
        print("No expenses yet.")
        return
    for r in rows:
        print(f"{r['date']} | {r['description']:<15} | "
              f"{float(r['amount']):>8.2f} | {r['category']}")
    print("Total:", round(sum(float(r["amount"]) for r in rows), 2))


def add_subscription():
    name = input("Subscription name: ").strip()
    cost = ask_amount("Cost: ")
    while True:
        cycle = input("Billing cycle (monthly/yearly): ").strip().lower()
        if cycle in ("monthly", "yearly"):
            break
        print("Type monthly or yearly.")
    while True:
        start = input("Start date (YYYY-MM-DD): ").strip()
        try:
            date.fromisoformat(start)
            break
        except ValueError:
            print("Use the format YYYY-MM-DD.")
    row = {"name": name, "cost": cost, "cycle": cycle, "start_date": start}
    append_row(row, SUB_FILE, SUB_FIELDS)
    print("Saved:", row)


def show_subscriptions():
    subs = read_rows(SUB_FILE)
    if not subs:
        print("No subscriptions yet.")
        return
    print("Monthly subscription cost:", monthly_total(subs))
    print("Upcoming payments:")
    for s in subs:
        due = next_due_date(s["start_date"], s["cycle"])
        days = (due - date.today()).days
        print(f"  {s['name']} - {s['cost']} on {due} ({days} days)")


def main():
    while True:
        print("\n1. Add expense")
        print("2. View expenses")
        print("3. Add subscription")
        print("4. Show subscriptions")
        print("5. Exit")
        choice = input("Choose: ").strip()
        if choice == "1":
            add_expense()
        elif choice == "2":
            view_expenses()
        elif choice == "3":
            add_subscription()
        elif choice == "4":
            show_subscriptions()
        elif choice == "5":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
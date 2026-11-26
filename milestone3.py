#!/usr/bin/env python3
"""Expense Tracker (Milestone 3).
Run:  python expense_tracker.py [--csv FILE | --db FILE]   (default: expenses.db)
      python expense_tracker.py --test | --evaluate
"""
import csv, os, re, sqlite3, statistics, sys, tempfile, unittest
from collections import defaultdict, namedtuple
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import random
from milestone2 import categorize
CATEGORIES = ["Food", "Transport", "Bills", "Entertainment", "Subscriptions", "Other"]
FIELDS = ["id", "amount", "category", "date", "merchant", "note"]
CREATE = ("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY, amount TEXT, "
          "category TEXT, date TEXT, merchant TEXT, note TEXT)")
Sub = namedtuple("Sub", "merchant period amount count confidence")


@dataclass
class Expense:
    amount: Decimal
    category: str
    when: date
    merchant: str = ""
    note: str = ""
    id: int = None


def money(text):
    try:
        v = Decimal(str(text).strip()).quantize(Decimal("0.01"), ROUND_HALF_UP)
    except Exception:
        raise ValueError(f"Invalid amount: {text!r}.")
    if not v.is_finite() or v <= 0:
        raise ValueError("Amount must be greater than zero.")
    return v


def day(text):
    try:
        return date.fromisoformat(str(text).strip())
    except ValueError:
        raise ValueError(f"Invalid date {text!r}; use YYYY-MM-DD.")


def _row(e):
    return [e.id, str(e.amount), e.category, e.when.isoformat(), e.merchant, e.note]


class Store:
    """Expense log with categories. Path ending in .csv uses CSV, otherwise SQLite. Saves are atomic."""

    def __init__(self, path=":memory:"):
        self.path = path
        self.db = None if path.endswith(".csv") else sqlite3.connect(path)
        if self.db:
            self.db.execute(CREATE)
        self.categories = list(CATEGORIES)
        self.rows = {}
        for e in self._load():
            self.rows[e.id] = e
            if e.category not in self.categories:
                self.categories.append(e.category)

    def _load(self):
        if self.db:
            return [Expense(Decimal(r[1]), r[2], day(r[3]), r[4] or "", r[5] or "", r[0])
                    for r in self.db.execute("SELECT * FROM expenses ORDER BY id")]
        if not os.path.exists(self.path):
            return []
        with open(self.path, newline="", encoding="utf-8") as f:
            return [Expense(money(r["amount"]), r["category"], day(r["date"]),
                            r["merchant"], r["note"], int(r["id"])) for r in csv.DictReader(f)]

    def save(self):
        if self.db:
            with self.db:  # one transaction
                self.db.execute("DELETE FROM expenses")
                self.db.executemany("INSERT INTO expenses VALUES (?,?,?,?,?,?)",
                                    [_row(e) for e in self.rows.values()])
            return
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(self.path)))
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(FIELDS)
            w.writerows(_row(e) for e in self.rows.values())
        os.replace(tmp, self.path)  # atomic swap

    def close(self):
        if self.db:
            self.db.close()

    def check(self, category):
        category = (category or "").strip()
        if category not in self.categories:
            raise ValueError(f"Unknown category '{category}'.")
        return category

    def add(self, amount, category, when, merchant="", note=""):
        new_id = max(self.rows, default=0) + 1
        self.rows[new_id] = Expense(money(amount), self.check(category), day(when),
                                    merchant.strip(), note.strip(), new_id)
        return self.rows[new_id]

    def update(self, eid, field, value):
        if eid not in self.rows:
            raise KeyError(f"No expense #{eid}.")
        if field not in ("amount", "category", "date", "merchant", "note"):
            raise ValueError(f"Unknown field '{field}'.")
        e = self.rows[eid]
        if field == "amount":
            e.amount = money(value)
        elif field == "category":
            e.category = self.check(value)
        elif field == "date":
            e.when = day(value)
        else:
            setattr(e, field, value.strip())
        return e

    def delete(self, eid):
        if eid not in self.rows:
            raise KeyError(f"No expense #{eid}.")
        del self.rows[eid]

    def all(self):
        return sorted(self.rows.values(), key=lambda e: (e.when, e.id))


def detect_subscriptions(expenses, min_count=3, threshold=0.7):
    """A merchant is a subscription if most gaps between charges match a
    weekly/monthly/yearly period and most amounts stay near the median."""
    groups = defaultdict(list)
    for e in expenses:
        key = re.sub(r"[^a-z0-9]+", " ", re.sub(r"\.(com|net|org)\b", "", (e.merchant or e.note).lower())).strip()
        if key:
            groups[key].append(e)
    found = []
    for items in groups.values():
        if len(items) < max(min_count, 2):
            continue
        items.sort(key=lambda e: e.when)
        gaps = [(b.when - a.when).days for a, b in zip(items, items[1:])]
        period, fit = max(((p, sum(abs(g - d) <= max(2, round(d * 0.15)) for g in gaps) / len(gaps))
                           for p, d in {"weekly": 7, "monthly": 30, "yearly": 365}.items()),
                          key=lambda x: x[1])
        median = Decimal(str(statistics.median(e.amount for e in items)))
        amount_fit = sum(abs(e.amount - median) <= median * Decimal("0.1") for e in items) / len(items)
        confidence = round(fit * (0.5 + 0.5 * amount_fit), 2)
        if fit >= 0.75 and confidence >= threshold:
            found.append(Sub(items[-1].merchant or items[-1].note, period, median, len(items), confidence))
    return sorted(found, key=lambda s: -s.confidence)


def evaluate(seed=7):
    """Labeled synthetic merchants. Returns (precision, recall, errors)."""
    rng = random.Random(seed)
    start = date(2025, 1, 5)
    month = lambda i: date(start.year + (start.month - 1 + i) // 12,
                           (start.month - 1 + i) % 12 + 1, min(start.day, 28))
    noisy = lambda base, var: (Decimal(str(base)) * Decimal(str(round(1 + rng.uniform(-var, var), 3)))).quantize(Decimal("0.01"))
    scattered = lambda n, lo, hi: [(start + timedelta(days=rng.randint(0, 360)), Decimal(str(round(rng.uniform(lo, hi), 2)))) for _ in range(n)]
    cases = [  # (merchant, is_subscription, [(date, amount)])
        ("Netflix", True, [(month(i), "15.49" if i < 6 else "17.99") for i in range(12)]),
        ("Gym", True, [(month(i), "39.00") for i in range(12)]),
        ("Phone Plan", True, [(month(i), "45.00" if i < 4 else "52.00") for i in range(12)]),
        ("Domain", True, [(date(2023 + i, 3, 12), "14.99") for i in range(3)]),
        ("Newspaper", True, [(start + timedelta(days=7 * i), "2.50") for i in range(20)]),
        ("Electric Utility", False, [(month(i), noisy(80, 0.35)) for i in range(12)]),
        ("Bank Fee", False, [(month(i), "5.00") for i in range(12)]),
        ("IKEA", False, scattered(2, 40, 300)),
        ("Auto Repair", False, scattered(4, 80, 400)),
        ("Coffee Shop", False, scattered(10, 3, 8)),
    ]
    tp = fp = fn = 0
    errors = []
    for name, label, rows in cases:
        expenses = [Expense(Decimal(str(a)), "Subscriptions", d, name) for d, a in rows]
        predicted = any(s.merchant == name for s in detect_subscriptions(expenses))
        tp += label and predicted
        fp += predicted and not label
        fn += label and not predicted
        if predicted != label:
            errors.append((name, label, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return precision, recall, errors


def run_evaluation():
    p, r, errors = evaluate()
    print(f"Precision {p:.2f}  Recall {r:.2f}  "
          f"targets (P>=0.85, R>=0.80): {'MET' if p >= 0.85 and r >= 0.80 else 'NOT MET'}")
    for name, label, predicted in errors:
        print(f"  error: {name} labeled {'subscription' if label else 'not subscription'}, "
              f"detector {'flagged' if predicted else 'did not flag'}")


def run_app(store, ask=input, out=print):
    menu = ["Add", "List", "Summary", "Edit", "Delete", "Subscriptions", "Save and exit"]
    while True:
        for i, item in enumerate(menu, 1):
            out(f"{i}. {item}")
        choice = ask("> ").strip()
        try:
            if choice == "1":
                desc = ask("Description: ").strip()
                e = store.add(ask("Amount: "), categorize(desc),
                          ask("Date (YYYY-MM-DD, blank = today): ") or date.today().isoformat(),
              desc)
                out(f"Added #{e.id}.")
            elif choice == "2":
                for e in store.all():
                    out(f"#{e.id} {e.when} {e.amount:>9} {e.category:<14} {e.merchant or e.note}")
            elif choice == "3":
                totals = defaultdict(Decimal)
                for e in store.all():
                    totals[e.category] += e.amount
                for cat, total in totals.items():
                    out(f"{cat:<16} {total}")
            elif choice == "4":
                eid = int(ask("Expense id: "))
                store.update(eid, ask("Field (amount/category/date/merchant/note): ").lower(), ask("New value: "))
                out(f"Updated #{eid}.")
            elif choice == "5":
                store.delete(int(ask("Expense id: ")))
                out("Deleted.")
            elif choice == "6":
                for s in detect_subscriptions(store.all()):
                    out(f"{s.merchant} ({s.period}, ~{s.amount}, {s.confidence:.0%})")
            elif choice == "7":
                store.save()
                out("Saved. Goodbye.")
                return
            else:
                out("Choose a number from the menu.")
        except (ValueError, KeyError) as exc:
            out(f"Error: {exc.args[0] if exc.args else exc}")


class Tests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(money("12.345"), Decimal("12.35"))
        for bad in ["abc", "0", "-5"]:
            with self.assertRaises(ValueError):
                money(bad)
        with self.assertRaises(ValueError):
            Store().add("5", "Gardening", "2025-01-01")

    def test_crud(self):
        s = Store()
        e = s.add("5", "Food", "2025-01-02", note="lunch")
        s.update(e.id, "amount", "7")
        self.assertEqual(s.rows[e.id].amount, Decimal("7.00"))
        with self.assertRaises(ValueError):
            s.update(e.id, "colour", "red")
        s.delete(e.id)
        with self.assertRaises(KeyError):
            s.delete(e.id)

    def test_sqlite_save_and_reload(self):
        path = os.path.join(tempfile.mkdtemp(), "t.db")
        s = Store(path)
        s.add("5", "Food", "2025-01-02", merchant="Bakery")
        s.save()
        s.close()
        self.assertEqual(Store(path).rows[1].merchant, "Bakery")

    def test_csv_save_and_reload(self):
        path = os.path.join(tempfile.mkdtemp(), "t.csv")
        s = Store(path)
        s.add("5.50", "Food", "2025-01-02", merchant="Bakery", note="bread")
        s.save()
        loaded = Store(path)
        self.assertEqual(loaded.rows[1].amount, Decimal("5.50"))
        self.assertEqual(loaded.rows[1].note, "bread")

    def test_detector(self):
        def charges(name, rows):
            return [Expense(Decimal(str(a)), "Subscriptions", d, name) for d, a in rows]
        netflix = [(date(2025, i + 1, 5), "15.49" if i < 6 else "17.99") for i in range(12)]
        self.assertEqual([s.period for s in detect_subscriptions(charges("Netflix", netflix))], ["monthly"])
        bill = [(date(2025, i + 1, 5), a) for i, a in enumerate([50, 90, 55, 100, 60, 95, 52, 88])]
        self.assertEqual(detect_subscriptions(charges("Electric", bill)), [])
        self.assertEqual(detect_subscriptions(charges("Two", netflix[:2])), [])

    def test_app(self):
        s = Store()
        inputs = iter(["1", "12.50", "Food", "", "", "lunch", "7"])
        run_app(s, ask=lambda p: next(inputs), out=lambda line: None)
        self.assertEqual(len(s.rows), 1)

    def test_evaluation_runs(self):
        p, r, _ = evaluate()
        self.assertTrue(0 <= p <= 1 and 0 <= r <= 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        unittest.main(argv=[sys.argv[0]], verbosity=2)
    elif "--evaluate" in sys.argv:
        run_evaluation()
    else:
        flag = "--csv" if "--csv" in sys.argv else "--db"
        path = sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else "expenses.db"
        store = Store(path)
        run_app(store)
        store.close()
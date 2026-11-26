#!/usr/bin/env python3
"""Milestone 4: integration tests, stress test, query optimisation, UI helper.
  python milestone4.py --test
  python milestone4.py --stress 20000
"""
import os, random, sqlite3, sys, tempfile, time, unittest
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal

from milestone2 import categorize
from milestone3 import Expense, Store, detect_subscriptions, run_app

INDEX = "CREATE INDEX IF NOT EXISTS idx_category_date ON expenses(category, date)"


def ensure_index(path):
    """Optimisation: lets SQLite find a category and date range without scanning every row."""
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(INDEX)


def query(path, category=None, start=None, end=None):
    """Reads only the rows that match the filters."""
    sql, args = "SELECT id, amount, category, date, merchant, note FROM expenses WHERE 1=1", []
    if category:
        sql += " AND category = ?"
        args.append(category)
    if start:
        sql += " AND date >= ?"
        args.append(start.isoformat())
    if end:
        sql += " AND date <= ?"
        args.append(end.isoformat())
    with closing(sqlite3.connect(path)) as db:
        return db.execute(sql + " ORDER BY date", args).fetchall()


def stress(n=20000):
    """Writes n expenses, then times the same query before and after adding an index."""
    path = os.path.join(tempfile.mkdtemp(), "stress.db")
    store = Store(path)
    cats, base = store.categories, date(2024, 1, 1)
    t0 = time.perf_counter()
    for i in range(1, n + 1):
        # Set rows directly: Store.add() scans every id on each call, which is slow at this size.
        store.rows[i] = Expense(Decimal(random.randint(100, 50000)) / 100, random.choice(cats),
                                base + timedelta(days=random.randint(0, 700)), f"shop{i % 200}", "", i)
    store.save()
    store.close()
    print(f"Wrote {n} expenses in {time.perf_counter() - t0:.2f}s")

    args = ("Food", date(2025, 1, 1), date(2025, 6, 30))
    t0 = time.perf_counter()
    rows = query(path, *args)
    slow = time.perf_counter() - t0
    ensure_index(path)
    t0 = time.perf_counter()
    query(path, *args)
    fast = time.perf_counter() - t0
    print(f"Query without index: {slow:.4f}s, with index: {fast:.4f}s, rows found: {len(rows)}")
    return rows


def confirm_delete(store, eid, ask):
    """Usability: ask before deleting and report the result in plain words."""
    if ask(f"Delete expense #{eid}? (y/n): ").strip().lower() != "y":
        return "Cancelled."
    try:
        store.delete(eid)
    except KeyError as exc:
        return f"Error: {exc.args[0]}"
    return f"Deleted #{eid}."


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "int.db")

    def run_menu(self, inputs):
        out = []
        run_app(Store(self.path), ask=lambda p: next(inputs), out=out.append)
        return out

    def test_menu_flow_persists_after_restart(self):
        self.run_menu(iter(["1", "pizza", "12.50", "", "1", "netflix", "15.49", "2025-01-05", "7"]))
        cats = sorted(e.category for e in Store(self.path).rows.values())
        self.assertEqual(cats, ["Entertainment", "Food"])

    def test_bad_input_is_rejected_cleanly(self):
        out = self.run_menu(iter(["1", "pizza", "-3", "", "7"]))
        self.assertEqual(len(Store(self.path).rows), 0)
        self.assertTrue(any(line.startswith("Error") for line in out))

    def test_subscription_found_after_three_charges(self):
        store = Store(self.path)
        for m in (1, 2, 3):
            store.add("15.49", "Entertainment", f"2025-0{m}-05", merchant="Netflix")
        self.assertEqual([s.merchant for s in detect_subscriptions(store.all())], ["Netflix"])

    def test_indexed_query_matches_store(self):
        store = Store(self.path)
        for i in range(30):
            store.add("5", "Food" if i % 2 else "Transport", f"2025-01-{i % 28 + 1:02d}")
        store.save()
        store.close()
        ensure_index(self.path)
        self.assertEqual(len(query(self.path, category="Food")), 15)

    def test_categorize_from_milestone2(self):
        self.assertEqual(categorize("Pizza at cafe"), "Food")
        self.assertEqual(categorize("Netflix"), "Entertainment")
        self.assertEqual(categorize("xyz"), "Other")

    def test_stress_small(self):
        self.assertGreater(len(stress(2000)), 0)


class UITests(unittest.TestCase):
    def test_confirm_delete(self):
        store = Store()
        store.add("5", "Food", "2025-01-01")
        self.assertEqual(confirm_delete(store, 1, lambda p: "n"), "Cancelled.")
        self.assertEqual(len(store.rows), 1)
        self.assertEqual(confirm_delete(store, 1, lambda p: "y"), "Deleted #1.")
        self.assertTrue(confirm_delete(store, 9, lambda p: "y").startswith("Error"))


if __name__ == "__main__":
    if "--test" in sys.argv:
        unittest.main(argv=[sys.argv[0]], verbosity=2)
    elif "--stress" in sys.argv:
        stress(int(sys.argv[sys.argv.index("--stress") + 1]))
    else:
        print(__doc__)
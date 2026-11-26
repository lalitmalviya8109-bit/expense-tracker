# expense-tracker

Command-line expense tracker in Python. Automatically categorizes spending from short descriptions, stores data in SQLite or CSV, detects recurring subscriptions, and includes integration tests and a stress test. Uses only the Python standard library.

## Features

- Automatic categorization from keywords (Food, Transport, Bills, Entertainment, Subscriptions, Other)
- Add, list, summarize, edit, and delete expenses (delete asks for confirmation)
- Subscription detection for weekly, monthly, and yearly charges, with a confidence score
- Saves to SQLite (`.db`) or CSV (`.csv`), depending on the file name you give

## Requirements

- Python 3.9 or newer
- No other packages needed
- Windows is recommended; the commands below are written for PowerShell

## Files

- `milestone2.py`: categorization rules and `categorize()`
- `milestone3.py`: expense storage, subscription detection, and the main menu
- `milestone4.py`: integration tests, stress test, query index, and delete confirmation

Keep all three `.py` files in the same folder.

## How to run

python milestone3.py                    # start the app, saves to expenses.db
python milestone3.py --csv expenses.csv # start the app, saves to CSV
python milestone4.py --test             # run the tests
python milestone4.py --stress 20000     # run the stress test

## Menu options

1. Add: enter a description, amount, date (or blank for today), merchant, and note
2. List: show all expenses with a total
3. Summary: total spending by category, optionally for one month (YYYY-MM)
4. Edit: change a field of an expense by ID
5. Delete: remove an expense by ID after confirmation
6. Subscriptions: list detected recurring charges
7. Save and exit

## Results

- All 7 integration and interface tests pass
- Writing 20,000 expenses takes about 0.16 seconds
- Subscription detector on a small labeled test set: precision 0.83, recall 1.00

## Known limitations

- Adding expenses slows as the data grows (planned fix: a counter for the next ID)
- One false positive in testing: a bank maintenance fee was flagged as a subscription
- Categorization uses keywords, so unusual descriptions are placed in Other
- Developed and tested on Windows only

## Author

Lalit Malviya (BTCS26O1072)
Anjali Rajawat(BTCS26O1020)

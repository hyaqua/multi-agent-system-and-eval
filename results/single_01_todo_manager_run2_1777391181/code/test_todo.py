"""Test harness for todo_manager — exercises every required feature."""

import os
import sys
import tempfile

# ---------------------------------------------------------------------------
# Switch to a writable temp directory before importing the module
# because todo_manager writes tasks.json to the current directory.
# ---------------------------------------------------------------------------
test_dir = tempfile.mkdtemp()
os.chdir(test_dir)
print(f"Running tests in: {test_dir}")

# Remove any leftover tasks.json
if os.path.exists("tasks.json"):
    os.remove("tasks.json")

# Now import the module
sys.path.insert(0, "/workspace")
import todo_manager

print("=" * 60)
print("TESTING TODO MANAGER")
print("=" * 60)

# Clean state
store = todo_manager.TaskStore()
assert len(store.tasks) == 0, "Should start empty"

# Test add
t1 = store.add("Buy groceries", "high")
print(f"Added: {t1}")
assert t1.title == "Buy groceries"
assert t1.priority == "high"
assert not t1.completed

t2 = store.add("Walk the dog", "low")
t3 = store.add("Write report")  # default medium
t4 = store.add("Review PR", "medium")
t5 = store.add("Call dentist", "high")

print(f"\nAll tasks ({len(store.tasks)}):")
for t in store.tasks:
    print(f"  [{t.id}] {t.title} | {t.priority} | {t.status_str}")

# Test list filtering
active = store.list_tasks(status_filter="active")
assert len(active) == 5
print(f"\nActive tasks: {len(active)}")

done_tasks = store.list_tasks(status_filter="done")
assert len(done_tasks) == 0
print(f"Done tasks: {len(done_tasks)}")

# Test mark done
assert store.mark_done(t1.id)
assert store.get(t1.id).completed
print(f"\nMarked '{t1.title}' as done.")

active = store.list_tasks(status_filter="active")
assert len(active) == 4
done_tasks = store.list_tasks(status_filter="done")
assert len(done_tasks) == 1
print(f"Active: {len(active)}, Done: {len(done_tasks)}")

# Test sorting by priority
by_priority = store.list_tasks(sort_by="priority")
print("\nSorted by priority:")
for t in by_priority:
    print(f"  [{t.id}] {t.title} | {t.priority}")
priorities = [t.priority for t in by_priority]
# high should come before medium, which should come before low
high_indices = [i for i, p in enumerate(priorities) if p == "high"]
medium_indices = [i for i, p in enumerate(priorities) if p == "medium"]
low_indices = [i for i, p in enumerate(priorities) if p == "low"]
if high_indices and medium_indices:
    assert all(
        hi < mi for hi in high_indices for mi in medium_indices
    ), "high should be before medium"
if medium_indices and low_indices:
    assert all(
        mi < li for mi in medium_indices for li in low_indices
    ), "medium should be before low"
print("  Sort order OK")

# Test sorting by date
by_date = store.list_tasks(sort_by="date")
print("\nSorted by date:")
for t in by_date:
    print(f"  [{t.id}] {t.title} | {t.created_at}")
dates = [t.created_datetime for t in by_date]
assert dates == sorted(dates), "Should be sorted by date ascending"
print("  Date sort OK")

# Test delete
assert store.delete(t3.id)
assert store.get(t3.id) is None
assert len(store.tasks) == 4
print(f"\nDeleted '{t3.title}'. Remaining: {len(store.tasks)}")

# Test search
results = store.search("groceries")
assert len(results) == 1
assert results[0].title == "Buy groceries"
print(f"\nSearch 'groceries': found {len(results)}")

results = store.search("nonexistent")
assert len(results) == 0
print(f"Search 'nonexistent': found {len(results)}")

results = store.search("dentist")
assert len(results) == 1
assert results[0].title == "Call dentist"
print(f"Search 'dentist': found {len(results)}")

# Test invalid operations
assert not store.mark_done("nonexistent-id")
assert not store.delete("nonexistent-id")
print("\nInvalid ID handling: OK")

# Test persistence
store2 = todo_manager.TaskStore()
assert len(store2.tasks) == len(store.tasks)
print(f"Persistence check: {len(store2.tasks)} tasks loaded from JSON")

# Clean up
os.remove("tasks.json")

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)

# Now test the REPL command parsing via subprocess
print("\n--- Testing REPL command parsing ---")

# Test parse_add_args
title, priority = todo_manager.parse_add_args(["Buy", "milk"])
assert title == "Buy milk"
assert priority == "medium"

title, priority = todo_manager.parse_add_args(["Buy", "milk", "--priority", "high"])
assert title == "Buy milk"
assert priority == "high"

title, priority = todo_manager.parse_add_args(["--priority=low", "Walk"])
assert title == "Walk"
assert priority == "low"

title, priority = todo_manager.parse_add_args([])
assert title is None  # error

print("parse_add_args: OK")

# Test parse_list_args
status, sort = todo_manager.parse_list_args([])
assert status is None and sort is None

status, sort = todo_manager.parse_list_args(["active"])
assert status == "active" and sort is None

status, sort = todo_manager.parse_list_args(["done"])
assert status == "done" and sort is None

status, sort = todo_manager.parse_list_args(["--sort", "priority"])
assert status is None and sort == "priority"

status, sort = todo_manager.parse_list_args(["--sort", "date"])
assert status is None and sort == "date"

status, sort = todo_manager.parse_list_args(["active", "--sort", "date"])
assert status == "active" and sort == "date"

status, sort = todo_manager.parse_list_args(["--sort", "invalid"])
assert status is None and sort is None  # error

print("parse_list_args: OK")

print("\nAll parsing tests passed!")
print(f"\nTests completed in: {test_dir}")

"""File I/O for saving and loading circuits as JSON."""

import json
import os
from circuit import Circuit


def save_circuit(circuit: Circuit, filepath: str):
    """Save circuit to JSON file."""
    data = circuit.to_dict()
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_circuit(circuit: Circuit, filepath: str):
    """Load circuit from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    circuit.from_dict(data)


def get_file_dialog_save() -> str | None:
    """Show save file dialog using tkinter."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.getcwd(),
        )
        root.destroy()
        return filepath if filepath else None
    except Exception:
        return None


def get_file_dialog_open() -> str | None:
    """Show open file dialog using tkinter."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.getcwd(),
        )
        root.destroy()
        return filepath if filepath else None
    except Exception:
        return None

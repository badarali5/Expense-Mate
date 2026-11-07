"""
ui.py — Presentation Layer
----------------------------
Tkinter desktop client. Talks ONLY to the Logic Layer (never to db.py
directly) so the UI can be swapped (e.g. for a web front-end) without
touching business rules — this is the low-coupling boundary the
architecture document describes.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from logic import ExpenseManager, ValidationError


class ExpenseMateApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ExpenseMate — Personal Expense Manager")
        self.geometry("880x600")
        self.manager = ExpenseManager()

        now = datetime.now()
        self.current_month = tk.IntVar(value=now.month)
        self.current_year = tk.IntVar(value=now.year)
        self.summary_var = tk.StringVar()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.tab_add = ttk.Frame(notebook)
        self.tab_list = ttk.Frame(notebook)
        self.tab_budget = ttk.Frame(notebook)
        self.tab_analytics = ttk.Frame(notebook)
        self.tab_io = ttk.Frame(notebook)

        notebook.add(self.tab_add, text="Add Transaction")
        notebook.add(self.tab_list, text="Transactions")
        notebook.add(self.tab_budget, text="Budgets & Alerts")
        notebook.add(self.tab_analytics, text="Analytics")
        notebook.add(self.tab_io, text="Import / Export")

        self._build_add_tab()
        self._build_list_tab()
        self._build_budget_tab()
        self._build_analytics_tab()
        self._build_io_tab()

    def _build_add_tab(self):
        f = self.tab_add
        labels = ["Type (income/expense)", "Amount", "Category", "Date (YYYY-MM-DD)", "Description"]
        self.add_vars = {k: tk.StringVar() for k in labels}
        for i, label in enumerate(labels):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=8)
            ttk.Entry(f, textvariable=self.add_vars[label], width=40).grid(row=i, column=1, padx=10, pady=8)
        ttk.Button(f, text="Add Transaction", command=self._on_add_transaction).grid(
            row=len(labels), column=0, columnspan=2, pady=15)

        recurring = ttk.LabelFrame(f, text="Recurring transaction")
        recurring.grid(row=len(labels) + 1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        recurring_labels = ["Type", "Amount", "Category", "Start date (YYYY-MM-DD)", "Description", "Months"]
        self.recurring_vars = {k: tk.StringVar() for k in recurring_labels}
        for i, label in enumerate(recurring_labels):
            ttk.Label(recurring, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=4)
            ttk.Entry(recurring, textvariable=self.recurring_vars[label], width=35).grid(
                row=i, column=1, padx=10, pady=4)
        ttk.Button(recurring, text="Add recurring transactions", command=self._on_add_recurring).grid(
            row=len(recurring_labels), column=0, columnspan=2, pady=8)

    def _on_add_transaction(self):
        v = self.add_vars
        try:
            self.manager.add_transaction(
                tx_type=v["Type (income/expense)"].get().strip().lower(),
                amount=float(v["Amount"].get()),
                category=v["Category"].get(),
                date_str=v["Date (YYYY-MM-DD)"].get().strip(),
                description=v["Description"].get(),
            )
            messagebox.showinfo("Success", "Transaction added.")
            for var in v.values():
                var.set("")
            self._refresh_list()
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Invalid input", str(e))

    def _on_add_recurring(self):
        v = self.recurring_vars
        try:
            count = len(self.manager.add_recurring_transaction(
                tx_type=v["Type"].get().strip().lower(),
                amount=float(v["Amount"].get()),
                category=v["Category"].get(),
                start_date=v["Start date (YYYY-MM-DD)"].get().strip(),
                description=v["Description"].get(),
                months=int(v["Months"].get()),
            ))
            messagebox.showinfo("Success", f"Created {count} recurring transactions.")
            for var in v.values():
                var.set("")
            self._refresh_list()
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Invalid input", str(e))

    def _build_list_tab(self):
        f = self.tab_list
        cols = ("id", "date", "type", "category", "amount", "description")
        self.tree = ttk.Treeview(f, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=120)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        actions = ttk.Frame(f)
        actions.pack(pady=5)
        ttk.Button(actions, text="Refresh", command=self._refresh_list).pack(side="left", padx=5)
        ttk.Button(actions, text="Delete selected", command=self._on_delete_transaction).pack(side="left", padx=5)
        ttk.Label(f, textvariable=self.summary_var).pack(pady=5)
        self._refresh_list()

    def _refresh_list(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for r in self.manager.get_transactions():
            self.tree.insert("", "end", values=(r["id"], r["date"], r["type"], r["category"],
                                                 r["amount"], r["description"]))
        summary = self.manager.monthly_summary(self.current_month.get(), self.current_year.get())
        self.summary_var.set(
            f"{self.current_year.get()}-{self.current_month.get():02d}: "
            f"income {summary['income']:.2f} | expenses {summary['expense']:.2f} | "
            f"net {summary['net']:.2f}"
        )

    def _on_delete_transaction(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Delete transaction", "Select a transaction first.")
            return
        tx_id = self.tree.item(selected[0], "values")[0]
        if messagebox.askyesno("Delete transaction", "Delete the selected transaction?"):
            self.manager.delete_transaction(int(tx_id))
            self._refresh_list()

    def _build_budget_tab(self):
        f = self.tab_budget
        ttk.Label(f, text="Category").grid(row=0, column=0, padx=10, pady=8)
        ttk.Label(f, text="Monthly Limit").grid(row=0, column=1, padx=10, pady=8)
        self.budget_cat = tk.StringVar()
        self.budget_limit = tk.StringVar()
        ttk.Entry(f, textvariable=self.budget_cat).grid(row=1, column=0, padx=10)
        ttk.Entry(f, textvariable=self.budget_limit).grid(row=1, column=1, padx=10)
        ttk.Button(f, text="Set Budget", command=self._on_set_budget).grid(row=1, column=2, padx=10)

        ttk.Label(f, text="Month").grid(row=0, column=3, padx=10, pady=8)
        ttk.Label(f, text="Year").grid(row=0, column=4, padx=10, pady=8)
        ttk.Spinbox(f, from_=1, to=12, textvariable=self.current_month, width=6).grid(
            row=1, column=3, padx=10)
        ttk.Spinbox(f, from_=2000, to=2100, textvariable=self.current_year, width=8).grid(
            row=1, column=4, padx=10)
        ttk.Button(f, text="Apply period", command=self._on_period_changed).grid(row=1, column=5, padx=10)

        self.alert_box = tk.Text(f, height=18, width=80)
        self.alert_box.grid(row=2, column=0, columnspan=3, padx=10, pady=15)
        ttk.Button(f, text="Check Alerts (current month)", command=self._refresh_alerts).grid(
            row=3, column=0, columnspan=3, pady=5)

    def _on_set_budget(self):
        try:
            self.manager.set_budget(self.budget_cat.get(), self.current_month.get(),
                                     self.current_year.get(), float(self.budget_limit.get()))
            messagebox.showinfo("Success", "Budget saved.")
            self._refresh_alerts()
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Invalid input", str(e))

    def _refresh_alerts(self):
        self.alert_box.delete("1.0", tk.END)
        alerts = self.manager.check_budget_alerts(self.current_month.get(), self.current_year.get())
        if not alerts:
            self.alert_box.insert(tk.END, "No budgets set for this month yet.\n")
        for a in alerts:
            icon = {"ok": "✅", "warning": "⚠️", "exceeded": "🚨"}[a["status"]]
            self.alert_box.insert(
                tk.END,
                f"{icon} {a['category']}: spent {a['spent']:.2f} / limit {a['limit']:.2f} "
                f"({a['status'].upper()})\n",
            )

    def _on_period_changed(self):
        self._refresh_list()
        self._refresh_alerts()
        self._refresh_chart()

    def _build_analytics_tab(self):
        f = self.tab_analytics
        ttk.Button(f, text="Refresh Chart", command=self._refresh_chart).pack(pady=5)
        self.chart_frame = ttk.Frame(f)
        self.chart_frame.pack(fill="both", expand=True)
        self._refresh_chart()

    def _refresh_chart(self):
        for w in self.chart_frame.winfo_children():
            w.destroy()
        data = self.manager.category_breakdown(self.current_month.get(), self.current_year.get())
        fig = Figure(figsize=(6, 4))
        ax = fig.add_subplot(111)
        if data:
            ax.pie(data.values(), labels=data.keys(), autopct="%1.1f%%")
            ax.set_title("Expenses by Category (this month)")
        else:
            ax.text(0.5, 0.5, "No expense data for this month", ha="center")
        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_io_tab(self):
        f = self.tab_io
        ttk.Button(f, text="Export to CSV", command=self._on_export).pack(pady=10)
        ttk.Button(f, text="Import from CSV", command=self._on_import).pack(pady=10)
        self.io_status = tk.Text(f, height=10, width=80)
        self.io_status.pack(pady=10)

    def _on_export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if not path:
            return
        n = self.manager.export_csv(path)
        self.io_status.insert(tk.END, f"Exported {n} transactions to {path}\n")

    def _on_import(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            result = self.manager.import_csv(path)
            self.io_status.insert(
                tk.END,
                f"Imported {result['imported']}, skipped {result['skipped']}\n",
            )
            for err in result["errors"]:
                self.io_status.insert(tk.END, f"  - {err}\n")
            self._refresh_list()
        except ValidationError as e:
            messagebox.showerror("Import failed", str(e))


if __name__ == "__main__":
    app = ExpenseMateApp()
    app.mainloop()

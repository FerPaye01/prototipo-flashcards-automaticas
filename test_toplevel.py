import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Main")

segments_container = ttk.Frame(root)
segments_container.columnconfigure(0, weight=1)
segments_container.rowconfigure(0, weight=1)

segments_canvas = tk.Canvas(segments_container, bg="red", highlightthickness=0, height=300)
segments_scrollbar = ttk.Scrollbar(segments_container, orient="vertical", command=segments_canvas.yview)

segments_inner_frame = ttk.Frame(segments_canvas)
segments_inner_frame.columnconfigure(0, weight=1)

segments_canvas.create_window((0, 0), window=segments_inner_frame, anchor="nw", tags="inner")
segments_canvas.configure(yscrollcommand=segments_scrollbar.set)

segments_canvas.grid(row=0, column=0, sticky="nsew")
segments_scrollbar.grid(row=0, column=1, sticky="ns")

# Populate segments
for i in range(5):
    f = ttk.Frame(segments_inner_frame, relief="groove", borderwidth=2)
    f.grid(row=i, column=0, sticky="ew", pady=5, padx=5)
    f.columnconfigure(0, weight=1)
    ttk.Label(f, text=f"Segment {i}").pack()

def on_configure(e):
    segments_canvas.configure(scrollregion=segments_canvas.bbox("all"))
segments_inner_frame.bind("<Configure>", on_configure)

def on_canvas_configure(e):
    segments_canvas.itemconfig("inner", width=e.width)
segments_canvas.bind("<Configure>", on_canvas_configure)

def show_window():
    top = tk.Toplevel(root)
    top.geometry("400x400")
    # Repack the segments_container into the Toplevel
    segments_container.pack(fill="both", expand=True, padx=10, pady=10)

ttk.Button(root, text="Show", command=show_window).pack()

root.mainloop()

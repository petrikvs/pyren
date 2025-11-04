#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta
import sys
import os
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
import re
from io import StringIO
import threading
import matplotlib.dates as mdates
import platform


class CSVHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_any_event(self, event):
        if Path(event.src_path) == Path(self.app.csv_file_path) and not event.is_directory:
            if hasattr(self, '_last_call'):
                if time.time() - self._last_call < 0.1:
                    return
            self._last_call = time.time()
            self.app.load_new_data()


class RealTimePlotApp:
    MAX_AXES = 8
    MAX_ROWS = 10000
    UPDATE_INTERVAL_MS = 100

    def __init__(self, root, csv_file_path, n_seconds=10):
        self.root = root
        self.csv_file_path = Path(csv_file_path)
        self.n_seconds = n_seconds
        self.data = pd.DataFrame()
        self.y_columns = []
        self.is_tracking = True
        self.saved_xlim = None
        self.last_file_size = 0
        self.partial_line_buffer = ""
        self.csv_separator = '\t'
        self.reading_lock = threading.Lock()
        self.reading_in_progress = False
        self.pending_plot_update = False
        self.status_var = tk.StringVar(value="Ready")
        self.colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k']
        self.numeric_columns = []

        self.setup_ui()
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.ax_twin = []
        self.lines = {}
        self.cursor_line = None
        self.annotation = None

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
        self.canvas.mpl_connect("axes_leave_event", self.on_mouse_leave)
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)

        observer_class = PollingObserver if platform.system() == "Darwin" else Observer
        self.observer = observer_class()
        self.event_handler = CSVHandler(self)
        self.observer.schedule(self.event_handler, path=self.csv_file_path.parent, recursive=False)
        self.observer.start()

        self.load_initial_data()

    def setup_ui(self):
        # Main window
        self.root.title("Multi-Axis Real-time CSV Plot")
        self.root.geometry("1400x800")

        # Control panel (top)
        control_frame = ttk.Frame(self.root)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Start/Stop buttons
        self.start_btn = ttk.Button(control_frame, text="Stop", command=self.toggle_tracking)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        # File selection
        ttk.Label(control_frame, text="CSV File:").pack(side=tk.LEFT, padx=5)
        self.file_var = tk.StringVar(value=str(self.csv_file_path)) # str() for Path
        ttk.Entry(control_frame, textvariable=self.file_var, width=40).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Browse", command=self.browse_file).pack(side=tk.LEFT, padx=5)

        # Interval
        ttk.Label(control_frame, text="Interval (seconds):").pack(side=tk.LEFT, padx=5)
        self.interval_var = tk.StringVar(value=str(self.n_seconds))
        ttk.Entry(control_frame, textvariable=self.interval_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Apply", command=self.update_interval).pack(side=tk.LEFT, padx=5)

        # Reset zoom button
        ttk.Button(control_frame, text="Reset Zoom", command=self.reset_zoom).pack(side=tk.LEFT, padx=5)

        # Export button (right)
        ttk.Button(control_frame, text="Export Plot", command=self.export_plot).pack(side=tk.RIGHT, padx=5)

        # Split into two parts: available columns and selected columns (between control panel and plot)
        selection_frame = ttk.Frame(self.root)
        selection_frame.pack(fill=tk.X, padx=5, pady=5)

        # Left part: list of available columns
        left_frame = ttk.Frame(selection_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        ttk.Label(left_frame, text="Available Columns:").pack(anchor=tk.W)
        self.available_listbox = tk.Listbox(left_frame, selectmode=tk.EXTENDED, height=6)
        self.available_listbox.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        # Event binding does not require a command
        self.available_listbox.bind('<<ListboxSelect>>', lambda e: None)

        # Add buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="→ Add Selected", command=self.add_selected_columns).pack(pady=2)
        ttk.Button(button_frame, text="→ Add All", command=self.add_all_columns).pack(pady=2)

        # Right part: selected columns
        right_frame = ttk.Frame(selection_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        ttk.Label(right_frame, text="Selected Y Columns:").pack(anchor=tk.W)
        self.selected_listbox = tk.Listbox(right_frame, selectmode=tk.EXTENDED, height=6)
        self.selected_listbox.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.selected_listbox.bind('<<ListboxSelect>>', lambda e: None)
        ttk.Button(right_frame, text="Remove Selected", command=self.remove_selected_columns).pack(pady=2)
        ttk.Button(right_frame, text="Remove All", command=self.remove_all_columns).pack(pady=2)

        # Status bar (always at the bottom)
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2) # side=tk.BOTTOM places it at the bottom
        # Use Label directly, as in the original code
        ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        # Plot frame (takes the main space)
        self.plot_frame = ttk.Frame(self.root)
        self.plot_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def toggle_tracking(self):
        if self.is_tracking:
            self.save_current_xlim()
            self.observer.stop()
            self.observer.join()
            self.is_tracking = False
            self.start_btn.config(text="Start")
            self.update_plot_static()
        else:
            # Fix 1: Hide and reset cursor and annotation when starting tracking
            if self.cursor_line:
                self.cursor_line.set_visible(False)
                self.cursor_line = None
            if self.annotation:
                self.annotation.set_visible(False)
                self.annotation = None
            self.canvas.draw()
            # End Fix 1

            observer_class = PollingObserver if platform.system() == "Darwin" else Observer
            self.observer = observer_class()
            self.observer.schedule(self.event_handler, path=self.csv_file_path.parent, recursive=False)
            self.observer.start()
            self.is_tracking = True
            self.start_btn.config(text="Stop")
            self.update_plot()

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.csv_file_path = Path(path)
            self.file_var.set(str(self.csv_file_path))
            self.load_initial_data()

    def update_interval(self):
        try:
            self.n_seconds = int(self.interval_var.get())
            if self.is_tracking:
                self.update_plot()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for interval.")

    def save_current_xlim(self):
        if self.ax.get_xlim()[0] != 0:
            self.saved_xlim = self.ax.get_xlim()

    def load_initial_data(self):
        self.status_var.set("Loading initial data...")
        for attempt in range(100):
            try:
                with open(self.csv_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.last_file_size = os.path.getsize(self.csv_file_path)
                self.partial_line_buffer = ""

                lines = content.splitlines(keepends=True)
                sep = '\t'
                if lines and lines[0].startswith('sep='):
                    sep_line = lines.pop(0).strip()
                    sep = sep_line[4:]
                    if sep == '\\t':
                        sep = '\t'
                    self.csv_separator = sep

                full_content = ''.join(lines)
                ends_with_newline = full_content.endswith(('\n', '\r', '\r\n'))
                all_lines = full_content.splitlines(keepends=True)

                if not ends_with_newline and all_lines:
                    self.partial_line_buffer = all_lines.pop()
                else:
                    self.partial_line_buffer = ""

                content_to_process = ''.join(all_lines)
                if not content_to_process.strip():
                    time.sleep(0.5)
                    continue

                if re.search(r'(?<=\d),(?=\d)', content_to_process):
                    content_to_process = re.sub(r'(?<=\d),(?=\d)', '.', content_to_process)

                df = pd.read_csv(StringIO(content_to_process), sep=sep, header=0)
                time_col = df.columns[0]
                df[time_col] = pd.to_datetime(df[time_col], format='%H:%M:%S.%f', errors='coerce')
                for col in df.columns[1:]:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

                df.rename(columns={time_col: 'timestamp'}, inplace=True)
                numeric_df = df.select_dtypes(include='number')
                self.numeric_columns = list(numeric_df.columns)

                self.available_listbox.delete(0, tk.END)
                for col in self.numeric_columns:
                    self.available_listbox.insert(tk.END, col)

                if self.numeric_columns:
                    self.data = pd.concat([df[['timestamp']], numeric_df], axis=1)
                    if len(self.data) > self.MAX_ROWS:
                        self.data = self.data.tail(self.MAX_ROWS).reset_index(drop=True)
                    self._update_plot()
                    self.status_var.set(f"Loaded {len(self.data)} rows from {self.csv_file_path}")
                    return
                else:
                    self.status_var.set(f"No numeric data found (attempt {attempt + 1}/100). Waiting...")
                    time.sleep(0.5)
            except Exception as e:
                self.status_var.set(f"Error loading CSV: {e}")
                time.sleep(0.5)
        messagebox.showwarning("No numeric data", "No numeric columns found after multiple attempts.")
        self.status_var.set("Still waiting for numeric data...")

    def load_new_data(self):
        with self.reading_lock:
            if self.reading_in_progress:
                return
            self.reading_in_progress = True

        def _read():
            try:
                current_size = os.path.getsize(self.csv_file_path)
                if current_size < self.last_file_size:
                    # File was truncated or rewritten
                    self.partial_line_buffer = ""
                    self.last_file_size = 0
                    self.root.after(0, self.load_initial_data)
                    return

                if current_size == self.last_file_size:
                    return  # No changes

                # Open file and read from last position
                with open(self.csv_file_path, 'rb') as f:
                    f.seek(self.last_file_size)
                    raw_new = f.read()

                if not raw_new:
                    return

                # Decode considering possible incomplete UTF-8 sequences
                try:
                    new_text = raw_new.decode('utf-8')
                except UnicodeDecodeError as e:
                    # If the last UTF-8 character is cut off, discard it
                    new_text = raw_new[:e.start].decode('utf-8')
                    # In this case, we cannot advance past e.start
                    bytes_to_advance = e.start
                    self.last_file_size += bytes_to_advance
                    return

                # Combine with buffer
                combined = self.partial_line_buffer + new_text
                lines = combined.splitlines(keepends=True)

                # Check if the last line is complete
                ends_with_newline = new_text.endswith(('\n', '\r\n', '\r'))

                if not ends_with_newline and lines:
                    self.partial_line_buffer = lines.pop()
                else:
                    self.partial_line_buffer = ""

                if not lines:
                    # No complete lines - but still advance by the length of raw_new
                    self.last_file_size += len(raw_new)
                    return

                # Collect complete lines
                full_text = ''.join(lines)

                # Process commas in numbers
                if re.search(r'(?<=\d),(?=\d)', full_text):
                    full_text = re.sub(r'(?<=\d),(?=\d)', '.', full_text)

                try:
                    df_new = pd.read_csv(StringIO(full_text), sep=self.csv_separator, header=None)
                except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
                    # Fix 2: Thread-safe status update
                    self.root.after(0, lambda msg=str(e): self.status_var.set(f"Parse error: {msg}"))
                    # End Fix 2
                    self.last_file_size += len(raw_new)
                    return

                if len(df_new.columns) != len(self.data.columns):
                    # Fix 2: Thread-safe status update
                    self.root.after(0, lambda: self.status_var.set(
                        f"Column mismatch: expected {len(self.data.columns)}, got {len(df_new.columns)}"
                    ))
                    # End Fix 2
                    self.last_file_size += len(raw_new)
                    return

                df_new.columns = self.data.columns
                time_col = 'timestamp'
                df_new[time_col] = pd.to_datetime(df_new[time_col], format='%H:%M:%S.%f', errors='coerce')
                for col in df_new.columns:
                    if col != time_col:
                        df_new[col] = pd.to_numeric(df_new[col], errors='coerce')

                df_new = df_new.dropna(subset=[time_col])
                if df_new.empty:
                    self.last_file_size += len(raw_new)
                    return

                with self.reading_lock:
                    self.data = pd.concat([self.data, df_new], ignore_index=True)
                    if len(self.data) > self.MAX_ROWS:
                        self.data = self.data.tail(self.MAX_ROWS).reset_index(drop=True)

                    numeric_df = self.data.select_dtypes(include='number')
                    new_numeric = list(numeric_df.columns)
                    if set(new_numeric) != set(getattr(self, 'numeric_columns', [])):
                        self.numeric_columns = new_numeric
                        self.available_listbox.delete(0, tk.END)
                        for col in self.numeric_columns:
                            self.available_listbox.insert(tk.END, col)
                        # Fix 2: Thread-safe status update
                        msg = f"Numeric columns updated: {', '.join(self.numeric_columns)}" if self.numeric_columns else "Still waiting for numeric data..."
                        self.root.after(0, lambda m=msg: self.status_var.set(m))
                        # End Fix 2

                    if self.is_tracking:
                        self.request_plot_update()

                self.last_file_size += len(raw_new)

            except Exception as e:
                # Fix 2: Thread-safe status update
                self.root.after(0, lambda msg=str(e): self.status_var.set(f"Error in load_new_data: {msg}"))
                print(f"Error in load_new_data: {str(e)}")
                # End Fix 2
            finally:
                with self.reading_lock:
                    self.reading_in_progress = False

        threading.Thread(target=_read, daemon=True).start()

    def request_plot_update(self):
        if not self.pending_plot_update:
            self.pending_plot_update = True
            self.root.after(self.UPDATE_INTERVAL_MS, self.perform_plot_update)

    def perform_plot_update(self):
        self.pending_plot_update = False
        self.update_plot()

    def _update_plot(self, full_range=False):
        if self.data.empty or not self.y_columns:
            self._clear_plot("Waiting for data...", "Waiting for numeric data to appear in file...")
            return

        plot_data = self.data if full_range else self.data[
            self.data['timestamp'] >= (self.data['timestamp'].iloc[-1] - timedelta(seconds=self.n_seconds))
        ]
        if plot_data.empty:
            return

        for ax in self.ax_twin:
            ax.remove()
        self.ax.clear()
        self.ax_twin = []
        self.lines = {}

        title = "Full Time Range" if full_range else f"Last {self.n_seconds} seconds (up to {plot_data['timestamp'].iloc[-1].strftime('%H:%M:%S.%f')})"
        self.ax.set_title(title)
        self.ax.set_xlabel("Time")

        num_axes = len(self.y_columns)
        for i, col in enumerate(self.y_columns):
            if col not in plot_data.columns:
                continue
            ax_current = self.ax if i == 0 else self.ax.twinx()
            if i > 0:
                self.ax_twin.append(ax_current)
                offset = min(150, (60 if num_axes <= 4 else 40 if num_axes <= 6 else 25) * (i - 1))
                ax_current.spines.right.set_position(("outward", offset))

            color = self.colors[i % len(self.colors)]
            line, = ax_current.plot(plot_data['timestamp'], plot_data[col], color=color, label=col)
            self.lines[col] = line
            ax_current.set_ylabel(col, color=color)
            ax_current.tick_params(axis='y', labelcolor=color)
            ax_current.autoscale(axis='y')

        try:
            self.fig.tight_layout()
        except:
            pass

        right_margin = max(0.05, min(0.98, 0.95 - (0.03 if num_axes <= 4 else 0.04 if num_axes <= 6 else 0.05) * max(0, num_axes - 1)))
        try:
            self.fig.subplots_adjust(right=right_margin)
        except:
            try:
                self.fig.subplots_adjust(right=0.8)
            except:
                pass

        if full_range:
            xlim = self.saved_xlim or (plot_data['timestamp'].min(), plot_data['timestamp'].max())
        else:
            xlim = (plot_data['timestamp'].min(), plot_data['timestamp'].max())
        self.ax.set_xlim(xlim)
        self.ax.grid(True)
        self.canvas.draw()

    def _clear_plot(self, title: str, message: str):
        for ax in self.ax_twin:
            ax.remove()
        self.ax.clear()
        self.ax_twin = []
        self.lines = {}
        self.ax.set_title(title)
        self.ax.set_xlabel("Time")
        self.ax.text(0.5, 0.5, message, horizontalalignment='center', verticalalignment='center',
                     transform=self.ax.transAxes, fontsize=14)
        self.ax.grid(True)
        self.canvas.draw()

    def update_plot(self):
        self._update_plot(full_range=False)

    def update_plot_static(self):
        self._update_plot(full_range=True)

    def add_selected_columns(self):
        selected = [self.available_listbox.get(i) for i in self.available_listbox.curselection()]
        self._add_columns(selected)

    def add_all_columns(self):
        available = [self.available_listbox.get(i) for i in range(self.available_listbox.size())]
        self._add_columns([c for c in available if c not in self.y_columns])

    def _add_columns(self, cols):
        free_slots = self.MAX_AXES - len(self.y_columns)
        if free_slots <= 0:
            messagebox.showwarning("Max Axes Reached", f"Maximum of {self.MAX_AXES} Y axes reached.")
            return
        if len(cols) > free_slots:
            messagebox.showwarning("Max Axes Warning",
                                   f"Only {free_slots} of {len(cols)} columns will be added.")
            cols = cols[:free_slots]

        for col in cols:
            if col not in self.y_columns:
                self.y_columns.append(col)
                self.selected_listbox.insert(tk.END, col)
        self._update_plot()

    def remove_selected_columns(self):
        for i in reversed(self.selected_listbox.curselection()):
            col = self.selected_listbox.get(i)
            if col in self.y_columns:
                self.y_columns.remove(col)
            self.selected_listbox.delete(i)
        self._update_plot()

    def remove_all_columns(self):
        self.y_columns.clear()
        self.selected_listbox.delete(0, tk.END)
        self._update_plot()

    def export_plot(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        if path:
            try:
                self.fig.savefig(path, dpi=150, bbox_inches='tight')
                messagebox.showinfo("Export Successful", f"Plot saved to:\n{path}")
            except Exception as e:
                messagebox.showerror("Export Failed", f"Could not save plot:\n{e}")

    def reset_zoom(self):
        if not self.data.empty and self.y_columns:
            times = self.data['timestamp'].dropna()
            if not times.empty:
                self.ax.set_xlim(times.min(), times.max())
                for ax in [self.ax] + self.ax_twin:
                    ax.autoscale(axis='y')
                self.saved_xlim = None
                self.canvas.draw()

    def on_mouse_move(self, event):
        if not self.is_tracking and event.inaxes in [self.ax] + self.ax_twin and event.xdata is not None:
            mouse_time = mdates.num2date(event.xdata).replace(tzinfo=None)
            times = self.data['timestamp'].dropna().dt.tz_localize(None)
            if times.empty:
                return

            idx = (times - mouse_time).abs().argmin()
            closest_time = times.iloc[idx]

            y_vals = {}
            for col in self.y_columns:
                row = self.data[self.data['timestamp'] == closest_time]
                if not row.empty and pd.notna(row[col].iloc[0]):
                    y_vals[col] = row[col].iloc[0]

            annotation_text = f"{closest_time.strftime('%H:%M:%S.%f')}\n"
            for col in self.y_columns:
                if col in y_vals:
                    annotation_text += f"{col}: {y_vals[col]:.2f}\n"

            # Fix 1: Recreate cursor and annotation on each call
            if self.cursor_line is None:
                self.cursor_line = self.ax.axvline(x=0, color='gray', linestyle='--', linewidth=1, visible=False)
            self.cursor_line.set_xdata([event.xdata])
            self.cursor_line.set_visible(True)

            if self.annotation is None:
                y0 = y_vals.get(self.y_columns[0], 0) if self.y_columns else 0
                self.annotation = self.ax.annotate(
                    annotation_text, xy=(closest_time, y0), xytext=(20, 20),
                    textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8),
                    fontsize=10, visible=False
                )
            else:
                y0 = y_vals.get(self.y_columns[0], 0) if self.y_columns else 0
                self.annotation.xy = (closest_time, y0)
                self.annotation.set_text(annotation_text)

            center_x = sum(self.ax.get_xlim()) / 2
            if mdates.date2num(closest_time) < center_x:
                self.annotation.set_position((10, 10))
                self.annotation.set_horizontalalignment('left')
            else:
                self.annotation.set_position((-10, 10))
                self.annotation.set_horizontalalignment('right')
            self.annotation.set_visible(True)
            # End Fix 1
            self.canvas.draw()
        else:
            needs_draw = False
            # Fix 1: Hide elements only if they were visible
            if self.cursor_line and self.cursor_line.get_visible():
                self.cursor_line.set_visible(False)
                needs_draw = True
            if self.annotation and self.annotation.get_visible():
                self.annotation.set_visible(False)
                needs_draw = True
            if needs_draw:
                self.canvas.draw()

    def on_mouse_leave(self, event):
        if self.cursor_line:
            self.cursor_line.set_visible(False)
        if self.annotation:
            self.annotation.set_visible(False)
        self.canvas.draw()

    def on_scroll(self, event):
        if not self.is_tracking and event.inaxes in [self.ax] + self.ax_twin and event.xdata is not None:
            xlim = self.ax.get_xlim()
            x_range = xlim[1] - xlim[0]
            scale = 1.2 if event.button == 'up' else 1 / 1.2
            new_range = x_range * scale
            rel = (event.xdata - xlim[0]) / x_range
            self.ax.set_xlim(event.xdata - rel * new_range, event.xdata + (1 - rel) * new_range)
            self.save_current_xlim()
            self.canvas.draw()

    def on_press(self, event):
        if not self.is_tracking and event.inaxes in [self.ax] + self.ax_twin and event.button == 1:
            self.press = (event.xdata, event.ydata)

    def on_release(self, event):
        if not self.is_tracking and self.press and event.inaxes in [self.ax] + self.ax_twin and event.button == 1:
            if event.xdata is None or self.press[0] is None:
                self.press = None
                return
            x1, x2 = self.press[0], event.xdata
            if x2 > x1:
                self.ax.set_xlim(mdates.num2date(x1).replace(tzinfo=None), mdates.num2date(x2).replace(tzinfo=None))
            else:
                times = self.data['timestamp'].dropna()
                if not times.empty:
                    self.ax.set_xlim(times.min(), times.max())
            self.save_current_xlim()
            self.canvas.draw()
            self.press = None

    def cleanup(self):
        self.observer.stop()
        self.observer.join()


def main():
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        root_tk = tk.Tk()
        root_tk.withdraw()
        csv_file = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        root_tk.destroy()
        if not csv_file:
            print("No file selected. Exiting.")
            return

    root = tk.Tk()
    app = RealTimePlotApp(root, csv_file_path=csv_file, n_seconds=10)

    def on_closing():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

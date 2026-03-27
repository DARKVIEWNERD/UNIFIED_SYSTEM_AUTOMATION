"""Automation control tab"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import threading
import os
import logging
from pathlib import Path
from datetime import datetime

from tabs.base import Base
from constants.ui import UIConstants, Colors
from config import COUNTRIES, WEB_PLATFORMS, APP_PLATFORMS, PLATFORM_CATEGORIES, TARGET_DIR
from logging_config import logger
from utils.get_Cur_FY import get_current_year_quarter

# Global stop flag — shared by both automation and scraper
STOP_AUTOMATION = False


class AutomationTab(Base):
    """Automation control tab"""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title = "▶️ Automation Control"

        # State variables
        self.is_running = False
        self.stop_flag = False
        self.start_time = None
        self.automation_thread = None
        self._driver = None

        # Configuration variables
        self.country_vars = {}
        self.web_vars = {}
        self.app_vars = {}
        self.category_vars = {}
        self.scrape_directory = tk.StringVar()

        # UI Elements
        self.start_button = None
        self.stop_button = None
        self.status_indicator = None
        self.status_label = None
        self.progress_bar = None
        self.progress_label = None
        self.log_text = None
        self.success_count = None
        self.fail_count = None
        self.files_count = None
        self.elapsed_time = None
        self.log_count_label = None
        self.filter_var = None
        self.level_var = None
        self.match_label = None
        self.selection_label = None
        self.selection_frame = None
        self.status_frame = None
        self._auto_config_status_frame = None
        self._auto_scrape_status_label = None

    def build(self):
        """Build the automation tab"""
        main_paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill='both', expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        self.build_config_panel(left_frame)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        self.build_log_panel(right_frame)

    def build_config_panel(self, parent):
        """Build the configuration panel"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=5)
        ttk.Label(header_frame, text="AUTOMATION CONFIGURATION",
                  style='Header.TLabel').pack()
        ttk.Label(header_frame, text="Configure and run multi-country automation",
                  style='SubHeader.TLabel').pack()

        self.build_control_panel(parent)

        canvas, scrollbar, scrollable = self.create_scrollable_frame(parent)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.build_country_section(scrollable)
        self.build_app_platforms_section(scrollable)
        self.build_categories_section(scrollable)
        self.build_config_status_section(scrollable)
        self.build_output_section(scrollable)
        self.build_scrape_status_section(scrollable)

    def build_control_panel(self, parent):
        """Build control buttons and status"""
        control_frame = ttk.LabelFrame(parent, text="🎮 Control Panel", padding=10)
        control_frame.pack(fill='x', pady=5)

        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill='x')

        self.start_button = ttk.Button(button_frame, text="▶ START AUTOMATION",
                                       command=self.start_automation,
                                       style='Success.TButton', width=20)
        self.start_button.pack(side='left', padx=5)

        self.stop_button = ttk.Button(button_frame, text="⏹ STOP",
                                      command=self.stop_automation,
                                      style='Danger.TButton', width=10, state='disabled')
        self.stop_button.pack(side='left', padx=5)

        self.scrape_button = ttk.Menubutton(button_frame, text="📂 SCRAPE FILES",
                                            width=18, style='Action.TButton')
        self.scrape_button.pack(side='left', padx=5)

        scrape_menu = tk.Menu(self.scrape_button, tearoff=0)
        scrape_menu.add_command(label="📁 Select Directory", command=self.select_directory)
        scrape_menu.add_separator()
        scrape_menu.add_command(label="▶ Start Directory Scraping",
                                command=self.start_directory_scraping)
        scrape_menu.add_command(label="🔄 Clear Selection", command=self.clear_selection)
        self.scrape_button.configure(menu=scrape_menu)

        self.status_frame = ttk.Frame(control_frame)
        self.status_frame.pack(fill='x', pady=10)

        self.status_indicator = ttk.Label(self.status_frame, text="●", foreground='gray',
                                          font=('Arial', 14))
        self.status_indicator.pack(side='left', padx=5)
        self.status_label = ttk.Label(self.status_frame, text="Ready to start",
                                      style='Status.TLabel')
        self.status_label.pack(side='left')

        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(fill='x', pady=5)
        ttk.Label(progress_frame, text="Overall Progress:").pack(anchor='w')
        self.progress_bar = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.progress_bar.pack(fill='x', pady=2)
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.pack(anchor='e')

        self.selection_frame = ttk.Frame(control_frame)
        self.selection_label = ttk.Label(self.selection_frame, text="", foreground='blue')
        self.selection_label.pack()

    def refresh_country_status(self):
        """Refresh countries display (2-column layout)"""
        if not self._country_status_frame:
            return
        for widget in self._country_status_frame.winfo_children():
            widget.destroy()
        for i, country in enumerate(COUNTRIES):
            row = i // 2
            col = i % 2
            ttk.Label(
                self._country_status_frame,
                text=f"• {country['name']} ({country['code']})",
                font=('Arial', 9)
            ).grid(row=row, column=col, sticky="w", padx=10, pady=2)
        self._country_status_frame.grid_columnconfigure(0, weight=1)
        self._country_status_frame.grid_columnconfigure(1, weight=1)

    def build_country_section(self, parent):
        frame = ttk.LabelFrame(parent, text="📍 Countries", padding=5)
        frame.pack(fill='x', pady=5)
        self._country_status_frame = ttk.Frame(frame)
        self._country_status_frame.pack(fill='x', padx=5, pady=2)
        self.refresh_country_status()

    def refresh_app_platforms(self):
        if not self._app_platform_frame:
            return
        for widget in self._app_platform_frame.winfo_children():
            widget.destroy()
        for platform in APP_PLATFORMS:
            row = ttk.Frame(self._app_platform_frame)
            row.pack(fill='x', pady=1)
            ttk.Label(row, text="•", foreground="gray").pack(side='left')
            ttk.Label(row, text=f" {platform.upper()}", font=('Arial', 9)).pack(side='left')

    def build_app_platforms_section(self, parent):
        frame = ttk.LabelFrame(parent, text="📱 App Platforms", padding=5)
        frame.pack(fill='x', pady=5)
        self._app_platform_frame = ttk.Frame(frame)
        self._app_platform_frame.pack(fill='x', padx=5, pady=2)
        self.refresh_app_platforms()

    def refresh_categories_status(self):
        if not self._category_status_frame:
            return
        for widget in self._category_status_frame.winfo_children():
            widget.destroy()
        for platform, categories in PLATFORM_CATEGORIES.items():
            ttk.Label(self._category_status_frame, text=f"{platform.upper()}:",
                      font=('Arial', 9, 'bold')).pack(anchor='w', pady=(4, 1))
            for category in categories[:5]:
                label = category[:40] + "..." if len(category) > 40 else category
                row = ttk.Frame(self._category_status_frame)
                row.pack(fill='x')
                ttk.Label(row, text="•", foreground="gray").pack(side='left')
                ttk.Label(row, text=f" {label}", font=('Arial', 9)).pack(side='left')
            if len(categories) > 5:
                ttk.Label(self._category_status_frame,
                          text=f"... and {len(categories) - 5} more",
                          foreground="gray", font=('Arial', 8)).pack(anchor='w', padx=10)

    def build_categories_section(self, parent):
        frame = ttk.LabelFrame(parent, text="🗂 Categories", padding=5)
        frame.pack(fill='x', pady=5)
        self._category_status_frame = ttk.Frame(frame)
        self._category_status_frame.pack(fill='x', padx=5, pady=2)
        self.refresh_categories_status()

    def build_output_section(self, parent):
        dir_frame = ttk.LabelFrame(parent, text="💾 Output Directory", padding=5)
        dir_frame.pack(fill='x', pady=5)
        ttk.Label(dir_frame, text=str(TARGET_DIR), foreground='blue').pack(anchor='w')

    def build_config_status_section(self, parent):
        status_frame = ttk.LabelFrame(parent, text="🔄 Custom Configs (live)", padding=5)
        status_frame.pack(fill='x', pady=5)
        self._auto_config_status_frame = ttk.Frame(status_frame)
        self._auto_config_status_frame.pack(fill='x', padx=5, pady=2)
        self.refresh_config_status()

    def build_scrape_status_section(self, parent):
        status_frame = ttk.LabelFrame(parent, text="🔄 Scrape Profiles (live)", padding=5)
        status_frame.pack(fill='x', pady=5)
        self._auto_scrape_status_label = ttk.Label(status_frame, text="", font=('Arial', 9))
        self._auto_scrape_status_label.pack(anchor='w', padx=5, pady=2)
        self.refresh_scrape_status()

    def build_log_panel(self, parent):
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=5)
        ttk.Label(header_frame, text="📊 LIVE AUTOMATION LOGS",
                  style='Header.TLabel') .pack()

        control_frame = ttk.Frame(parent)
        control_frame.pack(fill='x', pady=5)
        ttk.Button(control_frame, text="🧹 Clear Logs",
                   command=self.clear_logs).pack(side='left', padx=5)
        ttk.Button(control_frame, text="📋 Copy All",
                   command=self.copy_logs).pack(side='left', padx=5)
        self.log_count_label = ttk.Label(control_frame, text="Entries: 0")
        self.log_count_label.pack(side='right', padx=5)

        self.build_stats_panel(parent)

        log_frame = ttk.LabelFrame(parent, text="📝 Log Output", padding=5)
        log_frame.pack(fill='both', expand=True, pady=5)
        self.log_text = tk.scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, width=80, height=30,
            font=UIConstants.FONTS['log'], background='black', foreground=Colors.SUCCESS, state='disabled'
        )
        self.log_text.pack(fill='both', expand=True)
        self.app.log_manager.attach_log_widget(self.log_text)

        self.build_filter_panel(parent)
        self.update_logs()

    def build_stats_panel(self, parent):
        stats_frame = ttk.LabelFrame(parent, text="📈 Real-time Statistics", padding=5)
        stats_frame.pack(fill='x', pady=5)
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill='x')

        ttk.Label(stats_grid, text="✅ Successful:").grid(row=0, column=0, sticky='w', padx=5)
        self.success_count = ttk.Label(stats_grid, text="0", foreground='green')
        self.success_count.grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(stats_grid, text="❌ Failed:").grid(row=0, column=2, sticky='w', padx=20)
        self.fail_count = ttk.Label(stats_grid, text="0", foreground='red')
        self.fail_count.grid(row=0, column=3, sticky='w', padx=5)

        ttk.Label(stats_grid, text="📁 Files Created:").grid(row=1, column=0, sticky='w', padx=5)
        self.files_count = ttk.Label(stats_grid, text="0")
        self.files_count.grid(row=1, column=1, sticky='w', padx=5)

        ttk.Label(stats_grid, text="⏱️ Elapsed Time:").grid(row=1, column=2, sticky='w', padx=20)
        self.elapsed_time = ttk.Label(stats_grid, text="00:00:00")
        self.elapsed_time.grid(row=1, column=3, sticky='w', padx=5)

    def build_filter_panel(self, parent):
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', pady=5)

        ttk.Label(filter_frame, text="Filter:").pack(side='left', padx=5)

        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=20)
        filter_entry.pack(side='left', padx=5)
        filter_entry.bind('<KeyRelease>', self.filter_logs)

        ttk.Button(filter_frame, text="Clear Filter",
                   command=self.clear_filter).pack(side='left', padx=10)

        # Live match counter — updated by filter_logs on every keystroke or combo change
        self.match_label = ttk.Label(filter_frame, text="", foreground='gray')
        self.match_label.pack(side='left', padx=5)

        self.level_var = tk.StringVar(value="ALL")
        level_combo = ttk.Combobox(filter_frame, textvariable=self.level_var,
                                   values=['ALL', 'INFO', 'WARNING', 'ERROR'], width=10)
        level_combo.pack(side='right', padx=5)
        level_combo.bind('<<ComboboxSelected>>', self.filter_logs)

    # ========== Status Refresh Methods ==========

    def refresh_config_status(self):
        if not self._auto_config_status_frame:
            return
        for widget in self._auto_config_status_frame.winfo_children():
            widget.destroy()
        if not self.app.config_manager.configs:
            ttk.Label(self._auto_config_status_frame,
                      text="No configurations loaded.", foreground='gray').pack(anchor='w')
            return
        for config in self.app.config_manager.configs:
            status = "✅" if config.active else "❌"
            color = Colors.ACTIVE_GREEN if config.active else Colors.INACTIVE_RED
            row = ttk.Frame(self._auto_config_status_frame)
            row.pack(fill='x', pady=1)
            ttk.Label(row, text=status, foreground=color, font=('Arial', 10)).pack(side='left')
            ttk.Label(row, text=f" {config.name}", font=('Arial', 9, 'bold')).pack(side='left')
            ttk.Label(row, text=f" ({len(config.custom_selectors)} selectors)",
                      foreground='gray', font=('Arial', 8)).pack(side='left')

    def refresh_scrape_status(self):
        if not self._auto_scrape_status_label:
            return
        profiles = self.app.config_manager.load_scrape_configs()
        count = len(profiles)
        self._auto_scrape_status_label.config(
            text=f"Scrape profiles in config.json: {count}",
            foreground=Colors.ACTIVE_GREEN if count else 'gray'
        )

    # ========== Directory Scraping Methods ==========

    def select_directory(self):
        directory = filedialog.askdirectory(
            title="Select Directory with MHTML Files",
            initialdir=os.path.expanduser("~")
        )
        if directory:
            self.scrape_directory.set(directory)
            mhtml_files = [f for f in os.listdir(directory)
                           if f.lower().endswith(('.mhtml', '.mht'))]
            self.show_selection(f"📁 Selected: {directory} ({len(mhtml_files)} .mhtml files)")
            if mhtml_files:
                if messagebox.askyesno("Start Scraping",
                                       f"Found {len(mhtml_files)} MHTML files.\n\nStart directory scraping now?"):
                    self.start_directory_scraping()
            logging.info(f"Selected directory: {directory} ({len(mhtml_files)} MHTML files)")

    def show_selection(self, text):
        if hasattr(self, 'selection_label') and hasattr(self, 'selection_frame'):
            self.selection_label.config(text=text)
            self.selection_frame.pack(fill='x', pady=5, after=self.status_frame)
            self.app.root.after(10000, self.hide_selection)

    def hide_selection(self):
        if hasattr(self, 'selection_frame'):
            self.selection_frame.pack_forget()

    def clear_selection(self):
        self.scrape_directory.set("")
        self.hide_selection()
        logging.info("Cleared directory selection")

    def start_directory_scraping(self):
        if not self.scrape_directory.get():
            messagebox.showwarning("No Directory", "Please select a directory first")
            return
        if self.is_running:
            messagebox.showwarning("Already Running", "Another process is already running")
            return
        self.show_scraping_dialog()

    def show_scraping_dialog(self):
        dialog = tk.Toplevel(self.app.root)
        dialog.title("MHTML Scraping Configuration")
        dialog.geometry("500x350")
        dialog.transient(self.app.root)
        dialog.grab_set()

        ttk.Label(dialog, text="MHTML Directory Scraping",
                  font=('Arial', 12, 'bold')).pack(pady=10)
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Directory:", font=('Arial', 9, 'bold')).pack(anchor='w')
        ttk.Label(main_frame, text=self.scrape_directory.get(),
                  foreground='blue', wraplength=450).pack(anchor='w', pady=(0, 10))

        quarter_frame = ttk.Frame(main_frame)
        quarter_frame.pack(fill='x', pady=5)
        ttk.Label(quarter_frame, text="Quarter:", width=10).pack(side='left')
        quarter_var = tk.StringVar(value=get_current_year_quarter())
        ttk.Entry(quarter_frame, textvariable=quarter_var, width=20).pack(side='left', padx=5)

        rows_frame = ttk.Frame(main_frame)
        rows_frame.pack(fill='x', pady=5)
        ttk.Label(rows_frame, text="Max rows:", width=10).pack(side='left')
        max_rows_var = tk.IntVar(value=10)
        ttk.Spinbox(rows_frame, from_=1, to=50, textvariable=max_rows_var,
                    width=10).pack(side='left', padx=5)

        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill='x', pady=5)
        ttk.Label(output_frame, text="Output file:", width=10).pack(side='left')
        filename_var = tk.StringVar(value="All_platforms.xlsx")
        ttk.Entry(output_frame, textvariable=filename_var, width=30).pack(side='left', padx=5)

        ttk.Label(main_frame, text="Category sheets:").pack(anchor='w', pady=(10, 0))
        category_var = tk.StringVar(value="Music,Navigation,Messaging")
        ttk.Entry(main_frame, textvariable=category_var, state='disabled',
                  width=50).pack(anchor='w', pady=5)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill='x', pady=20)

        def start():
            dialog.destroy()
            self.execute_directory_scraping(
                directory=self.scrape_directory.get(),
                quarter=quarter_var.get().strip() or get_current_year_quarter(),
                max_rows=max_rows_var.get(),
                output_filename=filename_var.get().strip(),
                category_sheets=[c.strip() for c in category_var.get().split(',') if c.strip()]
            )

        ttk.Button(button_frame, text="Start Scraping",
                   command=start, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel",
                   command=dialog.destroy).pack(side='left', padx=5)

    def execute_directory_scraping(self, directory, quarter, max_rows,
                                   output_filename, category_sheets):
        global STOP_AUTOMATION
        STOP_AUTOMATION = False
        self.stop_flag = False
        self.is_running = True
        self.app.is_running = True

        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.status_indicator.config(foreground='green')
        self.status_label.config(text=f"Scraping: {os.path.basename(directory)}")

        self._reset_ui_state()

        self.scrape_params = {
            'directory': directory,
            'quarter': quarter,
            'max_rows': max_rows,
            'output_filename': output_filename,
            'category_sheets': category_sheets
        }

        self.automation_thread = threading.Thread(
            target=self.run_directory_scraping, daemon=True)
        self.automation_thread.start()
        self.update_timer()
        
    def run_directory_scraping(self):
            """Thin wrapper — UI wiring only.
            All business logic lives in automation_runner.run_directory_scraping_process().
            """
            try:
                from automation_runner import run_directory_scraping_process

                def _update_progress(pct):
                    self.app.root.after(0, lambda p=pct: (
                        self.progress_bar.configure(value=p),
                        self.progress_label.configure(text=f"{p:.1f}%")
                    ))

                def _set_counts(success, failed):
                    self.app.root.after(0, lambda s=success, f=failed: (
                        self.success_count.config(text=str(s)),
                        self.fail_count.config(text=str(f))
                    ))

                def _get_stop_flag():
                    global STOP_AUTOMATION
                    return STOP_AUTOMATION

                ui_callbacks = {
                    "update_progress": _update_progress,
                    "set_counts":      _set_counts, 
                    "get_stop_flag":   _get_stop_flag,
                }

                result = run_directory_scraping_process(self.scrape_params, ui_callbacks)

                total      = result["total"]
                successful = result["successful"]
                failed     = result["failed"]
                outfile    = result["outfile"]
                stopped    = result["stopped"]

                def _show_done():
                    if total == 0:
                        messagebox.showwarning("No Files", "No MHTML files found")
                        return
                    messagebox.showinfo(
                        "Scraping Complete",
                        f"Directory : {self.scrape_params['directory']}\n\n"
                        f"Output    : {os.path.basename(outfile)}\n"
                        f"Total     : {total}\n"
                        f"Successful: {successful}\n"
                        f"Failed    : {failed}\n"
                        f"{'⏹ Stopped by user' if stopped else '✅ Completed successfully'}\n\n"
                        f"Check logs for details."
                    )

                self.app.root.after(0, _show_done)

            except Exception as e:
                logging.error(f"Directory scraping error: {e}")
                self.app.root.after(0, lambda: messagebox.showerror(
                    "Error", f"Scraping failed: {str(e)}"))
            finally:
                self.app.root.after(0, self.automation_finished)
                
                
    # ========== Automation Methods ==========

    def _reset_ui_state(self):
        """Reset all UI elements to a clean state before every new run."""
        self.progress_bar['value'] = 0
        self.progress_label.config(text="0%")
        self.success_count.config(text="0")
        self.fail_count.config(text="0")
        self.files_count.config(text="0")
        self.elapsed_time.config(text="00:00:00")
        self.log_count_label.config(text="Entries: 0")
        self.log_text.delete(1.0, tk.END)
        self.app.log_manager.clear_logs()
        self.start_time = time.time()

    def start_automation(self):
        """Start the automation in a separate thread"""
        if self.is_running:
            return

        global STOP_AUTOMATION
        STOP_AUTOMATION = False
        self.stop_flag = False

        self.is_running = True
        self.app.is_running = True
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.status_indicator.config(foreground='green')
        self.status_label.config(text="Automation Running...")

        self._reset_ui_state()

        self.automation_thread = threading.Thread(target=self.run_automation, daemon=True)
        self.automation_thread.start()
        self.update_timer()

    def run_automation(self):
        """Thin wrapper — UI wiring only.
        All business logic lives in automation_runner.run_automation_process().
        """
        try:
            from automation_runner import run_automation_process

            def _update_status(text):
                self.app.root.after(0, lambda t=text: self.status_label.config(text=t))

            def _update_progress(pct):
                self.app.root.after(0, lambda p=pct: (
                    self.progress_bar.configure(value=p),
                    self.progress_label.configure(text=f"{p:.1f}%")
                ))

            def _increment_files():
                self.app.root.after(0, lambda: self.files_count.config(
                    text=str(int(self.files_count.cget("text") or 0) + 1)
                ))

            def _increment_files_by(n):
                self.app.root.after(0, lambda n=n: self.files_count.config(
                    text=str(int(self.files_count.cget("text") or 0) + n)
                ))

            def _set_counts(success, failed):
                self.app.root.after(0, lambda s=success, f=failed: (
                    self.success_count.config(text=str(s)),
                    self.fail_count.config(text=str(f))
                ))

            def _get_stop_flag():
                global STOP_AUTOMATION
                return STOP_AUTOMATION

            ui_callbacks = {
                "update_status":      _update_status,
                "update_progress":    _update_progress,
                "increment_files":    _increment_files,
                "increment_files_by": _increment_files_by,
                "set_counts":         _set_counts,
                "get_stop_flag":      _get_stop_flag,
            }

            result           = run_automation_process(ui_callbacks)
            all_successful   = result["all_successful"]
            all_failed       = result["all_failed"]
            mhtml_files      = result["mhtml_files"]
            execution_folder = result["execution_folder"]

            def _show_done():
                global STOP_AUTOMATION
                lines = [
                    f"Successful : {len(all_successful)}",
                    f"Failed     : {len(all_failed)}",
                    f"MHTML files: {len(mhtml_files)}",
                    "",
                    f"{'⏹ Stopped by user' if STOP_AUTOMATION else '✅ Completed successfully'}",
                    "",
                    f"Files saved to:\n{execution_folder}",
                    "",
                    "📊 All rows extracted to All_platforms.xlsx",
                ]
                messagebox.showinfo("Automation Complete", "\n".join(lines))

            self.app.root.after(0, _show_done)

        except Exception as e:
            logging.error(f"Automation error: {e}")
            self.app.root.after(0, lambda: messagebox.showerror(
                "Error", f"Automation failed: {str(e)}"))
        finally:
            self.app.root.after(0, self.automation_finished)

    def stop_automation(self):
        """Stop the automation gracefully"""
        if self.is_running:
            global STOP_AUTOMATION
            STOP_AUTOMATION = True
            self.stop_flag = True
            self.status_indicator.config(foreground='orange')
            self.status_label.config(text="Stopping Automation...")
            self.stop_button.config(state='disabled')
            logging.warning("⏹️ Stop signal sent...")
            if hasattr(self, '_driver') and self._driver:
                try:
                    self._driver.quit()
                    self._driver = None
                except Exception:
                    pass
            self.app.root.after(5000, self.force_stop_if_needed)

    def force_stop_if_needed(self):
        """Called 5s after stop is requested."""
        if self.stop_flag:
            logging.error("⛔ Force stop confirmed — waiting for thread to exit...")
            self.status_label.config(text="Force stopped — waiting for thread...")

    def automation_finished(self):
        """Called ONLY from the thread's finally block — safe to reset everything."""
        self.is_running = False
        self.app.is_running = False
        self.stop_flag = False
        self._driver = None
        global STOP_AUTOMATION
        STOP_AUTOMATION = False

        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.status_indicator.config(foreground='gray')
        self.status_label.config(text="Automation Finished")
        self.progress_bar['value'] = 100
        self.progress_label.config(text="100%")

    def update_timer(self):
        if self.is_running:
            elapsed = int(time.time() - self.start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self.elapsed_time.config(text=f"{h:02d}:{m:02d}:{s:02d}")
            self.app.root.after(1000, self.update_timer)

    # ========== Log Methods ==========

    def update_logs(self):
        if self.app.log_manager.update_display():
            stats = self.app.log_manager.stats
            self.log_count_label.config(text=f"Entries: {stats['entries']}")
        self.app.root.after(100, self.update_logs)

    def clear_logs(self):
        self.app.log_manager.clear_logs()
        self.success_count.config(text="0")
        self.fail_count.config(text="0")
        self.files_count.config(text="0")
        self.log_count_label.config(text="Entries: 0")

    def copy_logs(self):
        logs = self.app.log_manager.get_log_content()
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(logs)
        messagebox.showinfo("Copied", "Logs copied to clipboard!")

    def filter_logs(self, event=None):
        query    = self.filter_var.get().strip().lower()
        level    = self.level_var.get()
        log_text = self.log_text

        # ── Clear all existing tags ───────────────────────────────────
        log_text.tag_remove("match_line", "1.0", tk.END)
        log_text.tag_remove("dim_line",   "1.0", tk.END)
        log_text.tag_remove("highlight",  "1.0", tk.END)

        log_text.tag_config("match_line", background="#1a3a1a", foreground="#00ff00")
        log_text.tag_config("dim_line",   foreground="#444444")
        log_text.tag_config("highlight",  background="#ffff00", foreground="#000000")

        level_keywords = {
            "INFO":    "INFO",
            "WARNING": "WARNING",
            "ERROR":   "ERROR",
        }

        total_lines = int(log_text.index(tk.END).split(".")[0]) - 1
        match_count = 0

        for lineno in range(1, total_lines + 1):
            line_start = f"{lineno}.0"
            line_end   = f"{lineno}.end"
            line_text  = log_text.get(line_start, line_end)

            level_match   = level == "ALL" or level_keywords.get(level, "") in line_text
            keyword_match = not query or query in line_text.lower()

            if level_match and keyword_match:
                log_text.tag_add("match_line", line_start, line_end)
                match_count += 1

                # Highlight every occurrence of the keyword within the line
                if query:
                    search_start = line_start
                    while True:
                        pos = log_text.search(query, search_start,
                                              stopindex=line_end, nocase=True)
                        if not pos:
                            break
                        end_pos = f"{pos}+{len(query)}c"
                        log_text.tag_add("highlight", pos, end_pos)
                        search_start = end_pos
            else:
                log_text.tag_add("dim_line", line_start, line_end)

        # ── Update match counter ──────────────────────────────────────
        if query or level != "ALL":
            self.match_label.config(
                text=f"{match_count} match{'es' if match_count != 1 else ''}"
            )
        else:
            self.match_label.config(text="")

        # Keep log_manager in sync
        self.app.log_manager.filter_logs(query)

    def clear_filter(self):
        self.filter_var.set("")
        self.level_var.set("ALL")
        self.match_label.config(text="")

        self.log_text.tag_remove("match_line", "1.0", tk.END)
        self.log_text.tag_remove("dim_line",   "1.0", tk.END)
        self.log_text.tag_remove("highlight",  "1.0", tk.END)

        self.app.log_manager.filter_logs("")
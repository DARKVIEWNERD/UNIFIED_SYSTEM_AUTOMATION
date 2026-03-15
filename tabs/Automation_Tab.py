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
        self._driver = None          # holds the live Chrome driver so stop_automation() can kill it

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
        ttk.Label(header_frame, text="🤖 AUTOMATION CONFIGURATION",
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
        self.build_output_section(scrollable)
        self.build_config_status_section(scrollable)
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

        self.scrape_button = ttk.Menubutton(button_frame, text="📂 Scrape Files",
                                            width=15, style='Action.TButton')
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
                  style='Header.TLabel').pack()

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
            font=UIConstants.FONTS['log'], background='black', foreground=Colors.SUCCESS
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
                   command=self.clear_filter).pack(side='left', padx=5)
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
        self.progress_bar['value'] = 0
        self.progress_label.config(text="0%")

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

        self.start_time = time.time()
        self.update_timer()

    def run_directory_scraping(self):
        """Run the MHTML directory scraping process using filename-first approach"""
        try:
            params = self.scrape_params
            dir_path = params['directory']
            quarter = params['quarter']
            max_rows = params['max_rows']
            output_filename = params['output_filename']
            category_sheets = params.get('category_sheets', ['Music', 'Navigation', 'Messaging'])

            from scraper_helpers.console import iter_mhtml_files
            from scraper_helpers.io import html_from_mhtml_bytes, load_config
            from scraper_detectors.platform import detect_platform_from_filename
            from scraper_detectors.country import detect_country_from_filename
            from scraper_detectors.category import detect_category_from_filename
            from scraper_pipeline.dispatcher import extract_platform_rows, build_output_rows
            from scraper_helpers.excel import prepare_workbook_for_append, append_rows_to_category_sheets
            from scraper_helpers.console import post_trim_rows
            from scraper_models.constants import HEADERS
            from config import TARGET_DIR

            files = list(iter_mhtml_files(dir_path))
            files.sort(key=lambda p: os.path.basename(p).lower())

            if not files:
                logger.warning(f"No MHTML files found in: {dir_path}")
                self.app.root.after(0, lambda: messagebox.showwarning(
                    "No Files", "No MHTML files found"))
                return

            config = load_config()
            outfile = os.path.join(TARGET_DIR, output_filename)
            wb, ws_map = prepare_workbook_for_append(
                outfile, headers=HEADERS,
                category_sheets=tuple(category_sheets) if category_sheets
                else ("Music", "Navigation", "Messaging")
            )
            base_url = (config.get("source_base_url") or "").strip()

            logger.info(f"🔍 Found {len(files)} MHTML files to process")
            total = len(files)
            successful = 0
            failed = 0

            for idx, file_path in enumerate(files, 1):
                if STOP_AUTOMATION:
                    logger.warning("⏹️ Scraping stopped by user")
                    logger.info(f"   ✅ Completed: {successful} files successfully")
                    logger.info(f"   ⏸️ Stopped at: {os.path.basename(file_path)}")
                    break

                filename = os.path.basename(file_path)
                progress = (idx / total) * 100
                self.app.root.after(0, lambda p=progress: self.progress_bar.configure(value=p))
                self.app.root.after(0, lambda p=progress: self.progress_label.configure(
                    text=f"{p:.1f}%"))

                try:
                    platform_key = detect_platform_from_filename(file_path)
                    country_dict = detect_country_from_filename(file_path)
                    file_category = detect_category_from_filename(file_path)

                    if not platform_key:
                        logger.warning(f"⚠️ [{idx}/{total}] Skipping {filename}: No platform hint from filename")
                        failed += 1
                        continue

                    with open(file_path, "rb") as f:
                        data = f.read()
                    html, err = html_from_mhtml_bytes(data)

                    if err or not html:
                        logger.error(f"❌ [{idx}/{total}] Failed: {filename} - {err or 'Failed to parse MHTML'}")
                        failed += 1
                        continue

                    plat_name, rows, reason = extract_platform_rows(
                        platform_key, html, config,
                        max_rows=max_rows, source_path=file_path
                    )
                    rows = post_trim_rows(rows, max_rows)

                    if not rows:
                        logger.warning(f"⚠️ [{idx}/{total}] Skipping {filename}: 0 rows from {platform_key} ({reason})")
                        failed += 1
                        continue

                    final_rows = build_output_rows(plat_name, rows, country_dict, quarter, file_path)
                    append_rows_to_category_sheets(
                        ws_map, final_rows, file_category,
                        input_dir=dir_path, base_url=base_url
                    )

                    country_info = f" ({country_dict['code']})" if country_dict else ""
                    category_info = f" [{file_category}]" if file_category else ""
                    logger.info(
                        f"✅ [{idx}/{total}] Processed: {filename} → {len(final_rows)} rows "
                        f"from {plat_name}{country_info}{category_info}"
                    )
                    successful += 1

                except Exception as e:
                    logger.error(f"❌ [{idx}/{total}] Failed: {filename} - {str(e)}")
                    failed += 1

            try:
                wb.save(outfile)
                logger.info(f"📝 Saved workbook: {outfile}")
            except Exception as e:
                logger.error(f"❌ Failed to save workbook: {e}")

            logger.info(f"\n{'=' * 50}")
            logger.info(f"✅ SCRAPING COMPLETE")
            logger.info(f"   Directory: {dir_path}")
            logger.info(f"   Output: {outfile}")
            logger.info(f"   Total files: {total}")
            logger.info(f"   Successful: {successful}")
            logger.info(f"   Failed: {failed}")
            if STOP_AUTOMATION:
                logger.info(f"   ⏹️ Stopped by user")
            logger.info(f"{'=' * 50}")

            for cat in category_sheets:
                ws = ws_map.get(cat)
                if ws:
                    count = max(0, ws.max_row - 1)
                    logger.info(f"   - {cat}: {count} row(s)")

            self.app.root.after(0, lambda: messagebox.showinfo(
                "Scraping Complete",
                f"Directory: {dir_path}\n\n"
                f"Output: {os.path.basename(outfile)}\n"
                f"Total files: {total}\n"
                f"Successful: {successful}\n"
                f"Failed: {failed}\n"
                f"{'Stopped by user' if STOP_AUTOMATION else 'Completed successfully'}\n\n"
                f"Check logs for details."
            ))

        except Exception as e:
            logger.error(f"❌ Scraping error: {e}")
            self.app.root.after(0, lambda: messagebox.showerror(
                "Error", f"Scraping failed: {str(e)}"))
        finally:
            self.app.root.after(0, self.automation_finished)

    # ========== Automation Methods ==========

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
        self.log_text.delete(1.0, tk.END)

        self.automation_thread = threading.Thread(target=self.run_automation, daemon=True)
        self.automation_thread.start()

        self.start_time = time.time()
        self.update_timer()

    def run_automation(self):
        """Run execute_process() inline — same pattern as run_directory_scraping().
        Uses the tab's own STOP_AUTOMATION global and self.app.root.after() for UI sync.
        main.py is NOT modified — it is only imported for its helpers.
        """
        try:
            # ── Imports (same as main.py) ─────────────────────────────────
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from config import (
                COUNTRIES, PLATFORM_CATEGORIES, WEB_PLATFORMS, APP_PLATFORMS,
                TARGET_DIR, DELAYS, CHROME_OPTIONS, WEBDRIVER_WAIT, reload_web_platforms
            )
            from utils.utils import (
                slugify, get_country_slug, get_url_for_platform,
                print_progress, random_sleep, clean_category_name,
                get_next_sequence_number, calculate_totals
            )
            from Web_validators import (
                is_human_verification, is_page_unusable,
                wait_for_manual_verification, test_url_with_retry
            )
            from file_handlers import (
                ensure_directory_exists, save_mhtml_snapshot,
                create_base_filename, load_existing_snapshots,
                initialize_counters_from_files
            )

            try:
                from apptweak_integration import AppTweakIntegration
                APPTWEAK_AVAILABLE = True
            except ImportError:
                APPTWEAK_AVAILABLE = False
                class AppTweakIntegration:
                    def __init__(self, *a, **kw): pass
                    def execute_apptweak_flow(self, *a, **kw): return 0, 0

            try:
                from automation_engine_initial import execute_universal_flow
                UNIVERSAL_AVAILABLE = True
            except ImportError:
                UNIVERSAL_AVAILABLE = False

            # ── Setup ─────────────────────────────────────────────────────
            reload_web_platforms()
            total_countries, urls_per_country, total_tests = calculate_totals()

            logger.info("=" * 60)
            logger.info("AUTOMATED TESTING - MULTIPLE COUNTRIES & PLATFORMS")
            logger.info("=" * 60)
            logger.info(f"📍 Countries to test: {len(COUNTRIES)} countries")
            logger.info(f"Total URLs to test: {total_tests}")

            active_platforms = [wp for wp in WEB_PLATFORMS if wp.get("active", True)]
            logger.info(f"🌐 Web Platforms: {', '.join(wp['name'] for wp in active_platforms)}")
            logger.info("📱 App Platforms: Android & Apple (both automatically)")

            timestamp = datetime.now().strftime("%Y-%m-%d")
            existing_snapshots = load_existing_snapshots(
                TARGET_DIR / f"AUTOMATION_{timestamp}"
            )

            options = Options()
            for opt in CHROME_OPTIONS:
                options.add_argument(opt)
            driver = webdriver.Chrome(options=options)
            self._driver = driver                      # ← expose to stop_automation()
            driver.set_page_load_timeout(15)           # ← unblocks after 15s max
            wait = WebDriverWait(driver, WEBDRIVER_WAIT)

            ensure_directory_exists(TARGET_DIR)
            execution_folder = TARGET_DIR / f"AUTOMATION_{timestamp}"
            ensure_directory_exists(execution_folder)

            country_sequence_counters = initialize_counters_from_files(execution_folder, COUNTRIES)
            logger.info(f"🔢 Initialized counters for {len(COUNTRIES)} countries")

            if APPTWEAK_AVAILABLE:
                apptweak = AppTweakIntegration(
                    driver=driver,
                    execution_folder=execution_folder,
                    sequence_counters=country_sequence_counters,
                    existing_snapshots=existing_snapshots
                )
                logger.info("✅ AppTweakIntegration initialized")
            else:
                apptweak = None

            logger.info(f"📁 Saving to: {execution_folder}")

            all_successful = []
            all_failed = []

            # Progress denominator: one unit per (country × active platform)
            total_pairs = sum(
                1 for _ in COUNTRIES
                for wp in WEB_PLATFORMS if wp.get("active", True)
            )
            completed_pairs = 0

            try:
                for country_index, country in enumerate(COUNTRIES, 1):

                    # ── STOP CHECK ────────────────────────────────────────
                    if STOP_AUTOMATION:
                        logger.warning("⏹️ Stopped before next country.")
                        break

                    logger.info("=" * 60)
                    logger.info(f"COUNTRY {country_index}/{total_countries}: "
                                f"{country['name']} ({country['code']})")
                    logger.info("=" * 60)

                    # Update status label on UI thread
                    self.app.root.after(
                        0, lambda c=country['name']:
                        self.status_label.config(text=f"Running: {c}")
                    )

                    if country['number'] not in country_sequence_counters:
                        country_sequence_counters[country['number']] = 0

                    for web_platform in WEB_PLATFORMS:
                        if not web_platform.get("active", True):
                            continue

                        # ── STOP CHECK ────────────────────────────────────
                        if STOP_AUTOMATION:
                            logger.warning("⏹️ Stopped before next platform.")
                            break

                        logger.info(f"🌐 WEB PLATFORM: {web_platform['name']}")
                        self.app.root.after(
                            0, lambda p=web_platform['name']:
                            self.status_label.config(
                                text=f"Running: {country['name']} / {p}"
                            )
                        )

                        # ── AppTweak ──────────────────────────────────────
                        if web_platform["type"] == "apptweak":
                            if not APPTWEAK_AVAILABLE or apptweak is None:
                                logger.warning("⚠ AppTweak disabled")
                            else:
                                try:
                                    seq_before = country_sequence_counters.get(country['number'], 0)
                                    success_count, total_count = apptweak.execute_apptweak_flow(
                                        country, web_platform
                                    )
                                    seq_after = country_sequence_counters.get(country['number'], 0)
                                    files_made = seq_after - seq_before
                                    logger.info(f"      📊 AppTweak created {files_made} files")

                                    for _ in range(success_count):
                                        all_successful.append((
                                            country['name'], web_platform['name'],
                                            "apptweak", "apptweak_category",
                                            web_platform["base_url"]
                                        ))
                                    for _ in range(total_count - success_count):
                                        all_failed.append((
                                            country['name'], web_platform['name'],
                                            "apptweak", "apptweak_category",
                                            web_platform["base_url"],
                                            "AppTweak automation failed"
                                        ))

                                    # ── Sync UI ───────────────────────────
                                    s, f, fi = len(all_successful), len(all_failed), files_made
                                    self.app.root.after(0, lambda s=s, f=f: (
                                        self.success_count.config(text=str(s)),
                                        self.fail_count.config(text=str(f))
                                    ))
                                    self.app.root.after(
                                        0, lambda fi=fi: self.files_count.config(
                                            text=str(int(self.files_count.cget("text") or 0) + fi)
                                        )
                                    )

                                    time.sleep(DELAYS.get("apptweak_country_delay", 5))

                                except Exception as e:
                                    logger.error(f"❌ AppTweak failed: {str(e)[:120]}")
                                    all_failed.append((
                                        country['name'], web_platform['name'],
                                        "apptweak", "apptweak", web_platform["base_url"],
                                        f"AppTweak error: {str(e)[:100]}"
                                    ))

                            completed_pairs += 1
                            pct = (completed_pairs / total_pairs * 100)
                            self.app.root.after(0, lambda p=pct: (
                                self.progress_bar.configure(value=p),
                                self.progress_label.configure(text=f"{p:.1f}%")
                            ))
                            continue

                        # ── Universal engine ──────────────────────────────
                        if web_platform["type"] == "universal":
                            if not UNIVERSAL_AVAILABLE:
                                logger.warning("⚠ Universal engine disabled")
                            else:
                                try:
                                    seq_before = country_sequence_counters.get(country['number'], 0)
                                    success_count, total_count = execute_universal_flow(
                                        driver=driver,
                                        country_data=country,
                                        platform_config=web_platform,
                                        execution_folder=execution_folder,
                                        sequence_counters=country_sequence_counters,
                                        existing_snapshots=existing_snapshots
                                    )
                                    seq_after = country_sequence_counters.get(country['number'], 0)
                                    files_made = seq_after - seq_before
                                    logger.info(f"      📊 Universal created {files_made} files")

                                    for _ in range(success_count):
                                        all_successful.append((
                                            country['name'], web_platform['name'],
                                            "universal", "universal_category",
                                            web_platform["base_url"]
                                        ))
                                    for _ in range(total_count - success_count):
                                        all_failed.append((
                                            country['name'], web_platform['name'],
                                            "universal", "universal_category",
                                            web_platform["base_url"],
                                            "Universal automation failed"
                                        ))

                                    s, f, fi = len(all_successful), len(all_failed), files_made
                                    self.app.root.after(0, lambda s=s, f=f: (
                                        self.success_count.config(text=str(s)),
                                        self.fail_count.config(text=str(f))
                                    ))
                                    self.app.root.after(
                                        0, lambda fi=fi: self.files_count.config(
                                            text=str(int(self.files_count.cget("text") or 0) + fi)
                                        )
                                    )

                                except Exception as e:
                                    logger.error(f"❌ Universal failed: {str(e)[:120]}")
                                    all_failed.append((
                                        country['name'], web_platform['name'],
                                        "universal", "universal_category",
                                        web_platform["base_url"],
                                        f"Universal error: {str(e)[:100]}"
                                    ))

                            completed_pairs += 1
                            pct = (completed_pairs / total_pairs * 100)
                            self.app.root.after(0, lambda p=pct: (
                                self.progress_bar.configure(value=p),
                                self.progress_label.configure(text=f"{p:.1f}%")
                            ))
                            continue

                        # ── Normal URL processing ─────────────────────────
                        urls = []
                        for app_platform in APP_PLATFORMS:
                            for category in PLATFORM_CATEGORIES[app_platform]:
                                country_slug = get_country_slug(country, web_platform["type"])
                                category_slug = slugify(category, web_platform["type"])
                                url = get_url_for_platform(
                                    web_platform["base_url"], web_platform["type"],
                                    app_platform, country_slug, category_slug
                                )
                                urls.append((app_platform, category, url))

                        logger.info(f"   ✅ URLs generated: {len(urls)}")
                        successful_urls = []
                        failed_urls = []

                        for i, (app_platform, category, url) in enumerate(urls):

                            # ── STOP CHECK ────────────────────────────────
                            if STOP_AUTOMATION:
                                logger.warning("⏹️ Stopped mid-URL loop.")
                                break

                            safe_category = clean_category_name(category).lower()
                            task_key = (
                                country["code"],
                                web_platform["name"].lower(),
                                app_platform.lower(),
                                safe_category
                            )

                            if task_key in existing_snapshots:
                                logger.info(f"      ⏭️ Already saved: {task_key}")
                                continue

                            print_progress(i + 1, len(urls), f"   Testing {web_platform['name']}")
                            logger.info(f"   [{i+1}/{len(urls)}] {app_platform.upper()} - {category}")
                            logger.info(f"      URL: {url}")

                            try:
                                test_url_with_retry(driver, url)

                                if is_human_verification(driver):
                                    if not wait_for_manual_verification(driver):
                                        logger.warning("      ⏭️ Verification timeout")
                                        failed_urls.append((
                                            country['name'], web_platform['name'],
                                            app_platform, category, url, "Verification timeout"
                                        ))
                                        continue

                                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                                time.sleep(2)

                                is_bad, reason = is_page_unusable(driver, web_platform["type"])
                                if is_bad:
                                    logger.warning(f"      ⏭️ Skipped: {reason}")
                                    failed_urls.append((
                                        country['name'], web_platform['name'],
                                        app_platform, category, url, reason
                                    ))
                                    continue

                            except Exception as e:
                                logger.error(f"      ❌ Load error: {str(e)[:120]}")
                                failed_urls.append((
                                    country['name'], web_platform['name'],
                                    app_platform, category, url,
                                    f"Load error: {str(e)[:120]}"
                                ))
                                random_sleep(*DELAYS["between_tests"])
                                continue

                            logger.info("      ✅ Page validated")

                            date_stamp = datetime.now().strftime("%Y%m%d")
                            sequence_number = get_next_sequence_number(
                                country, country_sequence_counters
                            )
                            base_filename = create_base_filename(
                                country=country,
                                sequence=sequence_number,
                                web_platform=web_platform,
                                app_platform=app_platform,
                                category=clean_category_name(category),
                                date_stamp=date_stamp
                            )

                            try:
                                success, result = save_mhtml_snapshot(
                                    driver=driver,
                                    base_filename=base_filename,
                                    folder_path=execution_folder
                                )
                                if success:
                                    logger.info(f"      💾 Saved: {result}")
                                    existing_snapshots.add(task_key)
                                    successful_urls.append((
                                        country['name'], web_platform['name'],
                                        app_platform, category, url
                                    ))
                                    # ── Sync files count to UI ─────────────
                                    self.app.root.after(
                                        0, lambda: self.files_count.config(
                                            text=str(
                                                int(self.files_count.cget("text") or 0) + 1
                                            )
                                        )
                                    )
                                    # ── Extract saved MHTML immediately ────
                                    # Uses the keys already known at save time —
                                    # no need for callable.py or folder scanning.
                                    try:
                                        from scraper_helpers.io import html_from_mhtml_bytes, load_config
                                        from scraper_pipeline.dispatcher import extract_platform_rows, build_output_rows
                                        from scraper_helpers.excel import prepare_workbook_for_append, append_rows_to_category_sheets
                                        from scraper_helpers.console import effective_cap, post_trim_rows
                                        from scraper_models.constants import HEADERS
                                        from config import TARGET_DIR

                                        _config     = load_config()
                                        _cap        = effective_cap(_config.get("max_rows", 10))
                                        _outfile    = str(TARGET_DIR / "All_platforms.xlsx")
                                        _base_url   = (_config.get("source_base_url") or "").strip()
                                        _quarter    = get_current_year_quarter()
                                        _saved_path = str(execution_folder / f"{base_filename}.mhtml")

                                        # Build country dict matching scraper schema
                                        _country_dict = {
                                            "name": country["name"],
                                            "code": country["code"],
                                        }

                                        # platform key = web_platform type
                                        # (same key detect_platform_from_filename uses)
                                        _platform_key = web_platform["type"]

                                        with open(_saved_path, "rb") as _f:
                                            _html, _err = html_from_mhtml_bytes(_f.read())

                                        if _html and not _err:
                                            _plat_name, _rows, _reason = extract_platform_rows(
                                                _platform_key, _html, _config,
                                                max_rows=_cap, source_path=_saved_path
                                            )
                                            _rows = post_trim_rows(_rows, _cap)

                                            if _rows:
                                                _final_rows = build_output_rows(
                                                    _plat_name, _rows,
                                                    _country_dict, _quarter,
                                                    _saved_path
                                                )
                                                _wb, _ws_map = prepare_workbook_for_append(
                                                    _outfile,
                                                    headers=HEADERS,
                                                    category_sheets=("Music", "Navigation", "Messaging")
                                                )
                                                append_rows_to_category_sheets(
                                                    _ws_map, _final_rows,
                                                    safe_category,
                                                    input_dir=str(execution_folder),
                                                    base_url=_base_url
                                                )
                                                _wb.save(_outfile)
                                                logger.info(
                                                    f"      📊 Extracted: {len(_final_rows)} rows"
                                                    f" → {_plat_name} [{safe_category}]"
                                                )
                                            else:
                                                logger.warning(
                                                    f"      ⚠️ Extract: 0 rows from"
                                                    f" {_platform_key} ({_reason})"
                                                )
                                        else:
                                            logger.warning(
                                                f"      ⚠️ Extract: could not parse MHTML"
                                                f" ({_err})"
                                            )
                                    except Exception as _ex:
                                        logger.error(f"      ❌ Extract failed: {_ex}")
                                else:
                                    logger.error(f"      ⚠️ Snapshot error: {result}")
                                    failed_urls.append((
                                        country['name'], web_platform['name'],
                                        app_platform, category, url,
                                        f"MHTML save error: {result}"
                                    ))
                            except Exception as e:
                                failed_urls.append((
                                    country['name'], web_platform['name'],
                                    app_platform, category, url,
                                    f"MHTML save error: {str(e)[:120]}"
                                ))

                            # ── Sync success/failed to UI after every URL ──
                            all_successful.extend(successful_urls[-1:])
                            all_failed.extend(failed_urls[-1:])
                            s, f = len(all_successful), len(all_failed)
                            self.app.root.after(0, lambda s=s, f=f: (
                                self.success_count.config(text=str(s)),
                                self.fail_count.config(text=str(f))
                            ))

                            random_sleep(*DELAYS["between_tests"])

                        completed_pairs += 1
                        pct = (completed_pairs / total_pairs * 100)
                        self.app.root.after(0, lambda p=pct: (
                            self.progress_bar.configure(value=p),
                            self.progress_label.configure(text=f"{p:.1f}%")
                        ))

                        logger.info(f"\n   📊 {web_platform['name']} - {country['name']}:")
                        logger.info(f"      Successful: {len(successful_urls)} / Failed: {len(failed_urls)}")

                    if STOP_AUTOMATION:
                        break

                    if country_index < total_countries:
                        logger.info("\n⏳ Next country...")
                        random_sleep(*DELAYS["between_countries"])

            finally:
                driver.quit()

            # ── Final summary ─────────────────────────────────────────────
            logger.info("=" * 60)
            logger.info("AUTOMATED TESTING COMPLETE" if not STOP_AUTOMATION
                        else "AUTOMATED TESTING STOPPED BY USER")
            logger.info("=" * 60)

            total_actual = len(all_successful) + len(all_failed)
            logger.info(f"Successful: {len(all_successful)} / Failed: {len(all_failed)}")
            if total_actual:
                logger.info(f"Overall success rate: {len(all_successful)/total_actual*100:.1f}%")

            mhtml_files = list(execution_folder.glob("*.mhtml"))
            logger.info(f"💾 Total MHTML files: {len(mhtml_files)} → {execution_folder}")

            # ── ✅ AUTO-SCRAPE: process all saved MHTMLs immediately ──────
            # Only runs if there are files to process and stop was not requested
            scrape_result = None
            if mhtml_files and not STOP_AUTOMATION:
                logger.info("=" * 60)
                logger.info("🔄 AUTO-SCRAPE: Processing saved MHTML files...")
                logger.info("=" * 60)
                try:
                    from callable import run_batch_directory
                    scrape_result = run_batch_directory(
                        directory=str(execution_folder),
                        quarter=get_current_year_quarter(),
                        output_dir=str(TARGET_DIR),
                        output_filename="All_platforms.xlsx",
                    )
                    logger.info(f"✅ Auto-scrape complete:")
                    logger.info(f"   Processed : {scrape_result['processed']} files")
                    logger.info(f"   Failures  : {scrape_result['failures']}")
                    logger.info(f"   Output    : {scrape_result['output_path']}")
                    for cat, count in scrape_result["by_category"].items():
                        logger.info(f"   {cat}: {count} row(s)")
                except Exception as e:
                    logger.error(f"❌ Auto-scrape failed: {e}")
                    scrape_result = None

            # ── Completion dialog ─────────────────────────────────────────
            def _show_done():
                lines = [
                    f"Successful: {len(all_successful)}",
                    f"Failed    : {len(all_failed)}",
                    f"MHTML files: {len(mhtml_files)}",
                    "",
                    f"{'⏹ Stopped by user' if STOP_AUTOMATION else '✅ Completed successfully'}",
                    "",
                    f"Files saved to:\n{execution_folder}",
                ]
                if scrape_result:
                    lines += [
                        "",
                        "─── Auto-Scrape Results ───",
                        f"Processed : {scrape_result['processed']} files",
                        f"Failures  : {scrape_result['failures']}",
                        f"Output    : {os.path.basename(scrape_result['output_path'])}",
                    ]
                    for cat, count in scrape_result["by_category"].items():
                        lines.append(f"  {cat}: {count} row(s)")
                elif mhtml_files and not STOP_AUTOMATION:
                    lines += ["", "⚠ Auto-scrape failed — check logs."]
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
            # Kill the driver immediately so any blocking Selenium call
            # (page load, wait.until, save_mhtml) raises an exception
            # right away instead of waiting to time out
            if hasattr(self, '_driver') and self._driver:
                try:
                    self._driver.quit()
                    self._driver = None
                except Exception:
                    pass
            self.app.root.after(5000, self.force_stop_if_needed)

    def force_stop_if_needed(self):
        """Called 5s after stop is requested. The thread may still be alive —
        do NOT reset STOP_AUTOMATION here or the loop will keep running.
        Just update the UI; the thread's finally block calls automation_finished()."""
        if self.stop_flag:
            logging.error("⛔ Force stop confirmed — waiting for thread to exit...")
            # Keep STOP_AUTOMATION = True so the loop keeps seeing it.
            self.status_label.config(text="Force stopped — waiting for thread...")

    def automation_finished(self):
        """Called ONLY from the thread's finally block — safe to reset everything."""
        self.is_running = False
        self.app.is_running = False
        self.stop_flag = False
        self._driver = None
        global STOP_AUTOMATION
        STOP_AUTOMATION = False      # safe here — thread has fully exited

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
        self.filter_var_text = self.filter_var.get().lower()
        self.app.log_manager.filter_logs(self.filter_var_text)

    def clear_filter(self):
        self.filter_var.set("")
        self.app.log_manager.filter_logs("")
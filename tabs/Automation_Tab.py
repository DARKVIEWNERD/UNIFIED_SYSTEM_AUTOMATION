"""Automation control tab"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import threading
import os
import logging
from pathlib import Path

from tabs.base import Base
from constants.ui import UIConstants, Colors
from config import COUNTRIES, WEB_PLATFORMS, APP_PLATFORMS, PLATFORM_CATEGORIES, TARGET_DIR
from logging_config import logger
from utils.get_Cur_FY import get_current_year_quarter

# Global stop flag
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
        # Create main paned window
        main_paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Left panel - Configuration
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        self.build_config_panel(left_frame)
        
        # Right panel - Logs
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        self.build_log_panel(right_frame)
        
    def build_config_panel(self, parent):
        """Build the configuration panel"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=5)
        ttk.Label(header_frame, text="🤖 AUTOMATION CONFIGURATION",
                  style='Header.TLabel').pack()
        ttk.Label(header_frame, text="Configure and run multi-country automation",
                  style='SubHeader.TLabel').pack()
        
        # Control buttons
        self.build_control_panel(parent)
        
        # Configuration details with scroll
        canvas, scrollbar, scrollable = self.create_scrollable_frame(parent)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add configuration sections
        self.build_country_section(scrollable)
        self.build_web_platforms_section(scrollable)
        self.build_app_platforms_section(scrollable)
        self.build_categories_section(scrollable)
        self.build_output_section(scrollable)
        self.build_config_status_section(scrollable)
        self.build_scrape_status_section(scrollable)
        
    def build_control_panel(self, parent):
        """Build control buttons and status"""
        control_frame = ttk.LabelFrame(parent, text="🎮 Control Panel", padding=10)
        control_frame.pack(fill='x', pady=5)
        
        # Buttons
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
        
        # Scrape button with menu
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
        
        # Status indicator
        self.status_frame = ttk.Frame(control_frame)
        self.status_frame.pack(fill='x', pady=10)
        
        self.status_indicator = ttk.Label(self.status_frame, text="●", foreground='gray',
                                          font=('Arial', 14))
        self.status_indicator.pack(side='left', padx=5)
        self.status_label = ttk.Label(self.status_frame, text="Ready to start",
                                      style='Status.TLabel')
        self.status_label.pack(side='left')
        
        # Progress bar
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(fill='x', pady=5)
        ttk.Label(progress_frame, text="Overall Progress:").pack(anchor='w')
        self.progress_bar = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.progress_bar.pack(fill='x', pady=2)
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.pack(anchor='e')
        
        # Selection frame (hidden initially)
        self.selection_frame = ttk.Frame(control_frame)
        self.selection_label = ttk.Label(self.selection_frame, text="", foreground='blue')
        self.selection_label.pack()
        
    def build_country_section(self, parent):
        """Build country selection section"""
        country_frame = ttk.LabelFrame(parent, text="📍 Countries", padding=5)
        country_frame.pack(fill='x', pady=5)
        
        for country in COUNTRIES:
            var = tk.BooleanVar(value=True)
            self.country_vars[country['code']] = var
            ttk.Checkbutton(country_frame,
                          text=f"{country['name']} ({country['code']})",
                          variable=var).pack(anchor='w', pady=2)
                          
    def build_web_platforms_section(self, parent):
        """Build web platforms section"""
        web_frame = ttk.LabelFrame(parent, text="🌐 Web Platforms", padding=5)
        web_frame.pack(fill='x', pady=5)
        
        for platform in WEB_PLATFORMS:
            var = tk.BooleanVar(value=True)
            self.web_vars[platform['name']] = var
            ttk.Checkbutton(web_frame,
                          text=f"{platform['name']} - {platform['type']}",
                          variable=var).pack(anchor='w', pady=2)
                          
    def build_app_platforms_section(self, parent):
        """Build app platforms section"""
        app_frame = ttk.LabelFrame(parent, text="📱 App Platforms", padding=5)
        app_frame.pack(fill='x', pady=5)
        
        for platform in APP_PLATFORMS:
            var = tk.BooleanVar(value=True)
            self.app_vars[platform] = var
            ttk.Checkbutton(app_frame, text=platform.upper(),
                          variable=var).pack(anchor='w', pady=2)
                          
    def build_categories_section(self, parent):
        """Build categories section"""
        cat_frame = ttk.LabelFrame(parent, text="🗂 Categories", padding=5)
        cat_frame.pack(fill='x', pady=5)
        
        for app_platform, categories in PLATFORM_CATEGORIES.items():
            ttk.Label(cat_frame, text=f"{app_platform.upper()}:",
                     font=('Arial', 9, 'bold')).pack(anchor='w', pady=(5, 2))
            
            for category in categories[:5]:
                var = tk.BooleanVar(value=True)
                self.category_vars[f"{app_platform}_{category}"] = var
                label = category[:40] + "..." if len(category) > 40 else category
                ttk.Checkbutton(cat_frame, text=label, variable=var).pack(anchor='w', padx=10)
                
            if len(categories) > 5:
                ttk.Label(cat_frame,
                         text=f"... and {len(categories) - 5} more",
                         foreground='gray').pack(anchor='w', padx=10)
                         
    def build_output_section(self, parent):
        """Build output directory section"""
        dir_frame = ttk.LabelFrame(parent, text="💾 Output Directory", padding=5)
        dir_frame.pack(fill='x', pady=5)
        ttk.Label(dir_frame, text=str(TARGET_DIR), foreground='blue').pack(anchor='w')
        
    def build_config_status_section(self, parent):
        """Build custom configs status section"""
        status_frame = ttk.LabelFrame(parent, text="🔄 Custom Configs (live)", padding=5)
        status_frame.pack(fill='x', pady=5)
        self._auto_config_status_frame = ttk.Frame(status_frame)
        self._auto_config_status_frame.pack(fill='x', padx=5, pady=2)
        self.refresh_config_status()
        
    def build_scrape_status_section(self, parent):
        """Build scrape profiles status section"""
        status_frame = ttk.LabelFrame(parent, text="🔄 Scrape Profiles (live)", padding=5)
        status_frame.pack(fill='x', pady=5)
        self._auto_scrape_status_label = ttk.Label(status_frame, text="", font=('Arial', 9))
        self._auto_scrape_status_label.pack(anchor='w', padx=5, pady=2)
        self.refresh_scrape_status()
        
    def build_log_panel(self, parent):
        """Build the logging panel"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=5)
        ttk.Label(header_frame, text="📊 LIVE AUTOMATION LOGS",
                  style='Header.TLabel').pack()
        
        # Controls
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill='x', pady=5)
        
        ttk.Button(control_frame, text="🧹 Clear Logs",
                  command=self.clear_logs).pack(side='left', padx=5)
        ttk.Button(control_frame, text="📋 Copy All",
                  command=self.copy_logs).pack(side='left', padx=5)
        
        self.log_count_label = ttk.Label(control_frame, text="Entries: 0")
        self.log_count_label.pack(side='right', padx=5)
        
        # Statistics
        self.build_stats_panel(parent)
        
        # Log display
        log_frame = ttk.LabelFrame(parent, text="📝 Log Output", padding=5)
        log_frame.pack(fill='both', expand=True, pady=5)
        
        self.log_text = tk.scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, width=80, height=30,
            font=UIConstants.FONTS['log'], background='black', foreground=Colors.SUCCESS
        )
        self.log_text.pack(fill='both', expand=True)
        
        # Attach log widget to log manager
        self.app.log_manager.attach_log_widget(self.log_text)
        
        # Filter
        self.build_filter_panel(parent)
        
        # Start log updates
        self.update_logs()
        
    def build_stats_panel(self, parent):
        """Build statistics panel"""
        stats_frame = ttk.LabelFrame(parent, text="📈 Real-time Statistics", padding=5)
        stats_frame.pack(fill='x', pady=5)
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill='x')
        
        # Success
        ttk.Label(stats_grid, text="✅ Successful:").grid(row=0, column=0, sticky='w', padx=5)
        self.success_count = ttk.Label(stats_grid, text="0", foreground='green')
        self.success_count.grid(row=0, column=1, sticky='w', padx=5)
        
        # Failed
        ttk.Label(stats_grid, text="❌ Failed:").grid(row=0, column=2, sticky='w', padx=20)
        self.fail_count = ttk.Label(stats_grid, text="0", foreground='red')
        self.fail_count.grid(row=0, column=3, sticky='w', padx=5)
        
        # Files
        ttk.Label(stats_grid, text="📁 Files Created:").grid(row=1, column=0, sticky='w', padx=5)
        self.files_count = ttk.Label(stats_grid, text="0")
        self.files_count.grid(row=1, column=1, sticky='w', padx=5)
        
        # Elapsed time
        ttk.Label(stats_grid, text="⏱️ Elapsed Time:").grid(row=1, column=2, sticky='w', padx=20)
        self.elapsed_time = ttk.Label(stats_grid, text="00:00:00")
        self.elapsed_time.grid(row=1, column=3, sticky='w', padx=5)
        
    def build_filter_panel(self, parent):
        """Build filter panel"""
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
        """Refresh custom configs status display"""
        if not self._auto_config_status_frame:
            return
            
        # Clear existing
        for widget in self._auto_config_status_frame.winfo_children():
            widget.destroy()
            
        if not self.app.config_manager.configs:
            ttk.Label(self._auto_config_status_frame, 
                     text="No configurations loaded.",
                     foreground='gray').pack(anchor='w')
            return
            
        for config in self.app.config_manager.configs:
            status = "✅" if config.active else "❌"
            color = Colors.ACTIVE_GREEN if config.active else Colors.INACTIVE_RED
            row = ttk.Frame(self._auto_config_status_frame)
            row.pack(fill='x', pady=1)
            ttk.Label(row, text=status, foreground=color,
                     font=('Arial', 10)).pack(side='left')
            ttk.Label(row, text=f" {config.name}",
                     font=('Arial', 9, 'bold')).pack(side='left')
            ttk.Label(row, text=f" ({len(config.custom_selectors)} selectors)",
                     foreground='gray', font=('Arial', 8)).pack(side='left')
                     
    def refresh_scrape_status(self):
        """Refresh scrape profiles status"""
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
        """Open directory selection dialog for MHTML files"""
        directory = filedialog.askdirectory(
            title="Select Directory with MHTML Files",
            initialdir=os.path.expanduser("~")
        )
        
        if directory:
            self.scrape_directory.set(directory)
            
            mhtml_files = []
            for file in os.listdir(directory):
                if file.lower().endswith(('.mhtml', '.mht')):
                    mhtml_files.append(file)
                    
            self.show_selection(f"📁 Selected: {directory} ({len(mhtml_files)} .mhtml files)")
            
            if mhtml_files:
                if messagebox.askyesno("Start Scraping",
                                    f"Found {len(mhtml_files)} MHTML files.\n\nStart directory scraping now?"):
                    self.start_directory_scraping()
                    
            logging.info(f"Selected directory: {directory} ({len(mhtml_files)} MHTML files)")
            
    def show_selection(self, text):
        """Show the selection label"""
        if hasattr(self, 'selection_label') and hasattr(self, 'selection_frame'):
            self.selection_label.config(text=text)
            self.selection_frame.pack(fill='x', pady=5, after=self.status_frame)
            self.app.root.after(10000, self.hide_selection)
            
    def hide_selection(self):
        """Hide the selection label"""
        if hasattr(self, 'selection_frame'):
            self.selection_frame.pack_forget()
            
    def clear_selection(self):
        """Clear directory selection"""
        self.scrape_directory.set("")
        self.hide_selection()
        logging.info("Cleared directory selection")
        
    def start_directory_scraping(self):
        """Start the MHTML directory scraping process"""
        if not self.scrape_directory.get():
            messagebox.showwarning("No Directory", "Please select a directory first")
            return
            
        if self.is_running:
            messagebox.showwarning("Already Running", "Another process is already running")
            return
            
        self.show_scraping_dialog()
        
    def show_scraping_dialog(self):
        """Show scraping configuration dialog"""
        dialog = tk.Toplevel(self.app.root)
        dialog.title("MHTML Scraping Configuration")
        dialog.geometry("500x350")
        dialog.transient(self.app.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="MHTML Directory Scraping",
                font=('Arial', 12, 'bold')).pack(pady=10)
                
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Directory display
        ttk.Label(main_frame, text="Directory:", font=('Arial', 9, 'bold')).pack(anchor='w')
        ttk.Label(main_frame, text=self.scrape_directory.get(),
                foreground='blue', wraplength=450).pack(anchor='w', pady=(0, 10))
                
        # Quarter
        quarter_frame = ttk.Frame(main_frame)
        quarter_frame.pack(fill='x', pady=5)
        ttk.Label(quarter_frame, text="Quarter:", width=10).pack(side='left')
        quarter_var = tk.StringVar(value=get_current_year_quarter())
        ttk.Entry(quarter_frame, textvariable=quarter_var, width=20).pack(side='left', padx=5)
        
        # Max rows
        rows_frame = ttk.Frame(main_frame)
        rows_frame.pack(fill='x', pady=5)
        ttk.Label(rows_frame, text="Max rows:", width=10).pack(side='left')
        max_rows_var = tk.IntVar(value=10)
        ttk.Spinbox(rows_frame, from_=1, to=50, textvariable=max_rows_var,
                width=10).pack(side='left', padx=5)
                
        # Output file
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill='x', pady=5)
        ttk.Label(output_frame, text="Output file:", width=10).pack(side='left')
        filename_var = tk.StringVar(value="All_platforms.xlsx")
        ttk.Entry(output_frame, textvariable=filename_var, width=30).pack(side='left', padx=5)
        
        # Category sheets
        ttk.Label(main_frame, text="Category sheets:").pack(
            anchor='w', pady=(10, 0))
        category_var = tk.StringVar(value="Music,Navigation,Messaging")
        ttk.Entry(main_frame, textvariable=category_var,state='disabled', width=50).pack(anchor='w', pady=5)
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill='x', pady=20)
        
        def start():
            dialog.destroy()
            self.execute_directory_scraping(
                directory=self.scrape_directory.get(),
                quarter= quarter_var.get().strip() or get_current_year_quarter(),
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
        """Execute directory scraping in separate thread"""
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
            target=self.run_directory_scraping,
            daemon=True
        )
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

            # Import your scraper engine with correct paths
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

            # Get all MHTML files
            files = list(iter_mhtml_files(dir_path))
            files.sort(key=lambda p: os.path.basename(p).lower())

            if not files:
                logger.warning(f"No MHTML files found in: {dir_path}")
                self.app.root.after(0, lambda: messagebox.showwarning(  # Changed: self.root -> self.app.root
                    "No Files", "No MHTML files found"))
                return

            # Load config
            config = load_config()
            
            # Prepare output file path
            outfile = os.path.join(TARGET_DIR, output_filename)
            
            # Prepare workbook once
            wb, ws_map = prepare_workbook_for_append(
                outfile, 
                headers=HEADERS, 
                category_sheets=tuple(category_sheets) if category_sheets else ("Music", "Navigation", "Messaging")
            )
            
            base_url = (config.get("source_base_url") or "").strip()

            logger.info(f"🔍 Found {len(files)} MHTML files to process")
            total = len(files)
            successful = 0
            failed = 0

            for idx, file_path in enumerate(files, 1):
                # Check stop flag
                if STOP_AUTOMATION:
                    logger.warning("⏹️ Scraping stopped by user")
                    logger.info(f"   ✅ Completed: {successful} files successfully")
                    logger.info(f"   ⏸️ Stopped at: {os.path.basename(file_path)}")
                    break

                filename = os.path.basename(file_path)
                progress = (idx / total) * 100
                
                # Fixed: self.root -> self.app.root
                self.app.root.after(0, lambda p=progress: self.progress_bar.configure(value=p))
                self.app.root.after(0, lambda p=progress: self.progress_label.configure(
                    text=f"{p:.1f}%"))

                try:
                    # ---- 1) Filename-only detection ----
                    platform_key = detect_platform_from_filename(file_path)
                    country_dict = detect_country_from_filename(file_path)
                    file_category = detect_category_from_filename(file_path)

                    if not platform_key:
                        logger.warning(f"⚠️ [{idx}/{total}] Skipping {filename}: No platform hint from filename")
                        failed += 1
                        continue

                    # ---- 2) Load MHTML -> HTML ----
                    with open(file_path, "rb") as f:
                        data = f.read()
                    html, err = html_from_mhtml_bytes(data)
                    
                    if err or not html:
                        logger.error(f"❌ [{idx}/{total}] Failed: {filename} - {err or 'Failed to parse MHTML'}")
                        failed += 1
                        continue

                    # ---- 3) Extract by platform ----
                    plat_name, rows, reason = extract_platform_rows(
                        platform_key, html, config, 
                        max_rows=max_rows, 
                        source_path=file_path
                    )
                    
                    rows = post_trim_rows(rows, max_rows)

                    if not rows:
                        logger.warning(f"⚠️ [{idx}/{total}] Skipping {filename}: 0 rows from {platform_key} ({reason})")
                        failed += 1
                        continue

                    # ---- 4) Build rows in your fixed schema ----
                    final_rows = build_output_rows(
                        plat_name, rows, country_dict, quarter, file_path
                    )

                    # ---- 5) Append to workbook ----
                    append_rows_to_category_sheets(
                        ws_map, final_rows, file_category, 
                        input_dir=dir_path, base_url=base_url
                    )

                    # Log success with details
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

            # Save workbook at the end
            try:
                wb.save(outfile)
                logger.info(f"📝 Saved workbook: {outfile}")
            except Exception as e:
                logger.error(f"❌ Failed to save workbook: {e}")

            # Final summary
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

            # Show sheet statistics
            for cat in category_sheets:
                ws = ws_map.get(cat)
                if ws:
                    count = max(0, ws.max_row - 1)  # Subtract header row
                    logger.info(f"   - {cat}: {count} row(s)")

            # Fixed: self.root -> self.app.root
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
            # Fixed: self.root -> self.app.root
            self.app.root.after(0, lambda: messagebox.showerror(
                "Error", f"Scraping failed: {str(e)}"))
        finally:
            # Fixed: self.root -> self.app.root
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
        """Run the automation process"""
        try:
            from main import execute_process
            execute_process()
        except Exception as e:
            logging.error(f"Automation error: {e}")
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
            self.app.root.after(5000, self.force_stop_if_needed)
            
    def force_stop_if_needed(self):
        """Force stop if automation didn't respond"""
        if self.is_running and self.stop_flag:
            logging.error("⛔ Automation forcefully stopped!")
            self.automation_finished()
            
    def automation_finished(self):
        """Handle automation completion"""
        self.is_running = False
        self.app.is_running = False
        self.stop_flag = False
        global STOP_AUTOMATION
        STOP_AUTOMATION = False
        
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.status_indicator.config(foreground='gray')
        self.status_label.config(text="Automation Finished")
        self.progress_bar['value'] = 100
        self.progress_label.config(text="100%")
        
    def update_timer(self):
        """Update elapsed time"""
        if self.is_running:
            elapsed = int(time.time() - self.start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self.elapsed_time.config(text=f"{h:02d}:{m:02d}:{s:02d}")
            self.app.root.after(1000, self.update_timer)
            
    # ========== Log Methods ==========
    
    def update_logs(self):
        """Update log display from queue"""
        if self.app.log_manager.update_display():
            # Update statistics
            stats = self.app.log_manager.stats
            self.success_count.config(text=str(stats['success']))
            self.fail_count.config(text=str(stats['fail']))
            self.files_count.config(text=str(stats['files']))
            self.log_count_label.config(text=f"Entries: {stats['entries']}")
            
        self.app.root.after(100, self.update_logs)
        
    def clear_logs(self):
        """Clear the log display"""
        self.app.log_manager.clear_logs()
        self.success_count.config(text="0")
        self.fail_count.config(text="0")
        self.files_count.config(text="0")
        self.log_count_label.config(text="Entries: 0")
        
    def copy_logs(self):
        """Copy all logs to clipboard"""
        logs = self.app.log_manager.get_log_content()
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(logs)
        messagebox.showinfo("Copied", "Logs copied to clipboard!")
        
    def filter_logs(self, event=None):
        """Filter logs"""
        filter_text = self.filter_var.get().lower()
        self.app.log_manager.filter_logs(filter_text)
        
    def clear_filter(self):
        """Clear the filter"""
        self.filter_var.set("")
        self.app.log_manager.filter_logs("")
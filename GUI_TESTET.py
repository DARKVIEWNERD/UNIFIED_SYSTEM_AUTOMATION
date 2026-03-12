import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import sys
from io import StringIO
import time
from datetime import datetime
import os
from pathlib import Path
import signal
import json
import webbrowser
import logging

# Import your existing modules
from config import COUNTRIES, WEB_PLATFORMS, APP_PLATFORMS, PLATFORM_CATEGORIES, TARGET_DIR
from logging_config import logger

# Global stop flag
STOP_AUTOMATION = False


class QueueHandler(logging.Handler):
    """Custom logging handler to put records into a queue"""

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class AutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 Multi-Platform Automation Controller")
        self.root.geometry("1100x740")
        self.root.minsize(1000, 600)

        # Apply modern style
        self.setup_styles()

        # Variables
        self.is_running = False
        self.stop_flag = False
        self.start_time = None
        self.automation_thread = None

        # Queues for logging
        self.log_queue = queue.Queue()
        self.stdout_queue = queue.Queue()

        # Custom Website configuration
        self.existing_configs = []
        self.existing_selectors = {
            'roles': [],
            'selectors': [],
            'tags': ['div', 'button', 'input', 'a', 'span', 'select']
        }
        self.selectors = []
        self.scraper_selectors = []
        self.view_mode = 'custom'
        self.current_config = None
        self.summary_var = tk.StringVar(value="📊 No configurations loaded")

        # Track editing state
        self.editing_index = -1
        self.editing_view_mode = 'custom'

        # main_container_index — always persisted independently of view_mode
        self.main_container_index = []

        # Load existing configs
        self.load_existing_configs()
        self.extract_all_selectors()

        # Setup logging
        self.setup_logging()

        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Create tabs
        self.create_automation_tab()
        self.create_config_tab()
        self.create_view_tab()

        # Start log updates
        self.update_logs()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ==================== STYLES ====================

    def setup_styles(self):
        """Configure ttk styles for modern look"""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
        style.configure('SubHeader.TLabel', font=('Arial', 10), foreground='gray')
        style.configure('Status.TLabel', font=('Arial', 10))
        style.configure('Success.TButton', font=('Arial', 10, 'bold'))
        style.configure('Danger.TButton', font=('Arial', 10, 'bold'))
        style.configure('Action.TButton', font=('Arial', 10))
        style.configure('Card.TLabelframe', background='#f8f9fa')

    # ==================== CONFIGURATION MANAGEMENT ====================

    def load_existing_configs(self):
        """Load configurations from custom_patterns.json"""
        filepath = Path(__file__).parent / "custom_patterns.json"
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self.existing_configs = data if isinstance(data, list) else [data]
            else:
                self.existing_configs = []
        except Exception as e:
            print(f"Error loading configs: {e}")
            self.existing_configs = []
        return self.existing_configs

    def extract_all_selectors(self):
        """Extract all unique selector roles and values from existing configs"""
        roles = set()
        selectors = set()
        tags = set(['div', 'button', 'input', 'a', 'span', 'select',
                    'form', 'img', 'li', 'h1', 'h2', 'p'])
        for config in self.existing_configs:
            for selector in config.get('custom_selectors', []):
                if selector.get('role'):
                    roles.add(selector['role'])
                if selector.get('value'):
                    selectors.add(selector['value'])
                if selector.get('tag'):
                    tags.add(selector['tag'])
        self.existing_selectors = {
            'roles': sorted(list(roles)),
            'selectors': sorted(list(selectors)),
            'tags': sorted(list(tags))
        }

    def save_all_configs(self):
        """Save all configs to file"""
        filepath = Path(__file__).parent / "custom_patterns.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.existing_configs, f, indent=2, ensure_ascii=False)

    # ==================== AUTOMATION TAB ====================

    def create_automation_tab(self):
        """Create the main automation control tab"""
        auto_frame = ttk.Frame(self.notebook)
        self.notebook.add(auto_frame, text="▶️ Automation Control")

        main_paned = ttk.PanedWindow(auto_frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill='both', expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)

        self.build_config_panel(left_frame)
        self.build_log_panel(right_frame)

    def build_config_panel(self, parent):
        """Build the configuration panel for automation"""
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill='x', pady=5)
        ttk.Label(title_frame, text="🤖 AUTOMATION CONFIGURATION",
                  style='Header.TLabel').pack()
        ttk.Label(title_frame, text="Configure and run multi-country automation",
                  style='SubHeader.TLabel').pack()

        # Control buttons
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

        # Status indicator
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill='x', pady=10)

        self.status_indicator = ttk.Label(status_frame, text="●", foreground='gray',
                                          font=('Arial', 14))
        self.status_indicator.pack(side='left', padx=5)
        self.status_label = ttk.Label(status_frame, text="Ready to start",
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

        # Configuration details
        config_frame = ttk.LabelFrame(parent, text="📋 Configuration Details", padding=10)
        config_frame.pack(fill='both', expand=True, pady=5)

        config_canvas = tk.Canvas(config_frame, borderwidth=0, highlightthickness=0)
        config_scrollbar = ttk.Scrollbar(config_frame, orient="vertical",
                                         command=config_canvas.yview)
        config_scrollable = ttk.Frame(config_canvas)

        config_scrollable.bind(
            "<Configure>",
            lambda e: config_canvas.configure(scrollregion=config_canvas.bbox("all"))
        )
        config_canvas.create_window((0, 0), window=config_scrollable, anchor="nw")
        config_canvas.configure(yscrollcommand=config_scrollbar.set)

        # Countries
        country_frame = ttk.LabelFrame(config_scrollable, text="📍 Countries", padding=5)
        country_frame.pack(fill='x', pady=5)
        self.country_vars = {}
        for country in COUNTRIES:
            var = tk.BooleanVar(value=True)
            self.country_vars[country['code']] = var
            ttk.Checkbutton(country_frame,
                            text=f"{country['name']} ({country['code']})",
                            variable=var).pack(anchor='w', pady=2)

        # Web platforms
        web_frame = ttk.LabelFrame(config_scrollable, text="🌐 Web Platforms", padding=5)
        web_frame.pack(fill='x', pady=5)
        self.web_vars = {}
        for platform in WEB_PLATFORMS:
            var = tk.BooleanVar(value=True)
            self.web_vars[platform['name']] = var
            ttk.Checkbutton(web_frame,
                            text=f"{platform['name']} - {platform['type']}",
                            variable=var).pack(anchor='w', pady=2)

        # App platforms
        app_frame = ttk.LabelFrame(config_scrollable, text="📱 App Platforms", padding=5)
        app_frame.pack(fill='x', pady=5)
        self.app_vars = {}
        for platform in APP_PLATFORMS:
            var = tk.BooleanVar(value=True)
            self.app_vars[platform] = var
            ttk.Checkbutton(app_frame, text=platform.upper(),
                            variable=var).pack(anchor='w', pady=2)

        # Categories
        cat_frame = ttk.LabelFrame(config_scrollable, text="🗂 Categories", padding=5)
        cat_frame.pack(fill='x', pady=5)
        self.category_vars = {}
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

        # Target directory
        dir_frame = ttk.LabelFrame(config_scrollable, text="💾 Output Directory", padding=5)
        dir_frame.pack(fill='x', pady=5)
        ttk.Label(dir_frame, text=str(TARGET_DIR), foreground='blue').pack(anchor='w')

        config_canvas.pack(side="left", fill="both", expand=True)
        config_scrollbar.pack(side="right", fill="y")

    def build_log_panel(self, parent):
        """Build the logging panel"""
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill='x', pady=5)
        ttk.Label(title_frame, text="📊 LIVE AUTOMATION LOGS",
                  style='Header.TLabel').pack()

        # Log controls
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill='x', pady=5)
        ttk.Button(control_frame, text="🧹 Clear Logs",
                   command=self.clear_logs).pack(side='left', padx=5)
        ttk.Button(control_frame, text="📋 Copy All",
                   command=self.copy_logs).pack(side='left', padx=5)
        self.log_count_label = ttk.Label(control_frame, text="Entries: 0")
        self.log_count_label.pack(side='right', padx=5)

        # Statistics
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

        # Log display
        log_frame = ttk.LabelFrame(parent, text="📝 Log Output", padding=5)
        log_frame.pack(fill='both', expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, width=80, height=30,
            font=('Consolas', 9), background='black', foreground='#00ff00'
        )
        self.log_text.pack(fill='both', expand=True)

        self.log_text.tag_config('ERROR', foreground='#ff5555')
        self.log_text.tag_config('WARNING', foreground='#ffaa00')
        self.log_text.tag_config('INFO', foreground='#00ff00')
        self.log_text.tag_config('DEBUG', foreground='#888888')
        self.log_text.tag_config('SUCCESS', foreground='#55ff55')

        # Filter
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

    # ==================== CONFIGURATION TAB ====================

    def create_config_tab(self):
        """Create the configuration builder tab"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="⚙️ Create Configuration")

        config_frame.grid_rowconfigure(0, weight=1)
        config_frame.grid_rowconfigure(1, weight=0)
        config_frame.grid_rowconfigure(2, weight=0)
        config_frame.grid_columnconfigure(0, weight=1)
        config_frame.grid_columnconfigure(1, weight=0)

        canvas = tk.Canvas(config_frame, borderwidth=0, highlightthickness=0, bg='#f0f0f0')
        scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw",
                             width=canvas.winfo_width())

        def configure_canvas(event):
            canvas.itemconfig(1, width=event.width)

        canvas.bind('<Configure>', configure_canvas)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

        # Main container
        main_container = ttk.Frame(scrollable_frame)
        main_container.pack(fill='both', expand=True, padx=10, pady=5)
        main_container.columnconfigure(0, weight=1)

        # Header
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(header_frame, text="CUSTOM AUTOMATION CONFIGURATION BUILDER",
                  font=('Arial', 14, 'bold')).pack()
        ttk.Label(header_frame,
                  text="Create reusable selectors for web automation. These will be saved to use in your automation scripts.",
                  font=('Arial', 9), foreground='gray', wraplength=1000).pack()

        # Configuration Details
        config_details = ttk.LabelFrame(main_container, text="📋 Configuration Details", padding=12)
        config_details.pack(fill='x', pady=3)
        config_details.columnconfigure(1, weight=1)

        ttk.Label(config_details, text="Configuration Name:",
                  font=('Arial', 9)).grid(row=0, column=0, sticky='w', padx=3, pady=3)
        self.name_var = tk.StringVar()
        name_combo = ttk.Combobox(config_details, textvariable=self.name_var, height=5)
        existing_names = [c.get('name', '') for c in self.existing_configs if c.get('name')]
        name_combo['values'] = existing_names
        name_combo.grid(row=0, column=1, columnspan=2, sticky='ew', padx=3, pady=3)
        name_combo.bind('<<ComboboxSelected>>', self.load_existing_config)

        ttk.Label(config_details, text="Website URL:",
                  font=('Arial', 9)).grid(row=1, column=0, sticky='w', padx=3, pady=3)
        self.url_var = tk.StringVar()
        url_combo = ttk.Combobox(config_details, textvariable=self.url_var, height=5)
        existing_urls = [c.get('base_url', '') for c in self.existing_configs if c.get('base_url')]
        url_combo['values'] = list(set(existing_urls))
        url_combo.grid(row=1, column=1, sticky='ew', padx=3, pady=3)
        ttk.Button(config_details, text="🔍 Test URL", command=self.test_url,
                   style='Action.TButton', width=12).grid(row=1, column=2, padx=3, pady=3, sticky='w')

        ttk.Label(config_details, text="Description:",
                  font=('Arial', 9)).grid(row=2, column=0, sticky='w', padx=3, pady=3)
        self.desc_var = tk.StringVar()
        ttk.Entry(config_details, textvariable=self.desc_var).grid(
            row=2, column=1, columnspan=2, sticky='ew', padx=3, pady=3)

        # Status
        status_frame = ttk.LabelFrame(main_container, text="⚡ Configuration Status", padding=10)
        status_frame.pack(fill='x', pady=3)
        status_frame.columnconfigure(1, weight=1)

        ttk.Label(status_frame, text="Active Status:",
                  font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky='w', padx=3, pady=3)
        radio_frame = ttk.Frame(status_frame)
        radio_frame.grid(row=0, column=1, sticky='w', padx=3, pady=3)
        self.status_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(radio_frame, text="✅ Active", variable=self.status_var,
                        value=True, command=self.update_status_display).pack(side='left', padx=5)
        ttk.Radiobutton(radio_frame, text="❌ Inactive", variable=self.status_var,
                        value=False, command=self.update_status_display).pack(side='left', padx=5)

        indicator_frame = ttk.Frame(status_frame)
        indicator_frame.grid(row=1, column=0, columnspan=2, sticky='w', padx=3, pady=3)
        self.status_indicator_config = ttk.Label(indicator_frame, text="●", font=('Arial', 14))
        self.status_indicator_config.pack(side='left', padx=5)
        self.status_text = ttk.Label(indicator_frame,
                                     text="Configuration is active and will be used in automation",
                                     font=('Arial', 9))
        self.status_text.pack(side='left', padx=5)

        version_frame = ttk.Frame(status_frame)
        version_frame.grid(row=1, column=1, sticky='e', padx=3, pady=3)
        ttk.Label(version_frame, text="Version:", font=('Arial', 9)).pack(side='left', padx=5)
        self.version_var = tk.StringVar(value="1.0")
        ttk.Entry(version_frame, textvariable=self.version_var, width=6).pack(side='left')

        # ── Main Container Index (always visible, view-independent) ──────────────
        index_frame = ttk.LabelFrame(main_container,
                                     text="🗂 Main Container Index  (comma-separated, e.g. 0, 1, 2)",
                                     padding=10)
        index_frame.pack(fill='x', pady=3)
        index_frame.columnconfigure(1, weight=1)

        ttk.Label(index_frame,
                  text="Index values:",
                  font=('Arial', 9)).grid(row=0, column=0, sticky='w', padx=3, pady=3)

        self.ConIndex_var = tk.StringVar()
        container_index_entry = ttk.Entry(index_frame, textvariable=self.ConIndex_var)
        container_index_entry.grid(row=0, column=1, sticky='ew', padx=3, pady=3)
        container_index_entry.bind('<KeyRelease>', self.update_container_index)
        container_index_entry.bind('<FocusOut>', self.update_container_index)

        ttk.Label(index_frame,
                  text="Leave empty to omit from saved JSON.",
                  foreground='#7f8c8d', font=('Arial', 8)).grid(
            row=1, column=0, columnspan=2, sticky='w', padx=3)

        # Selector Configuration
        selector_frame = ttk.LabelFrame(main_container, text="🎯 Selector Configuration",
                                        padding=12)
        selector_frame.pack(fill='both', expand=True, pady=3)
        selector_frame.columnconfigure(1, weight=1)
        selector_frame.columnconfigure(3, weight=2)
        selector_frame.rowconfigure(6, weight=1)

        # View toggle bar
        help_frame = ttk.Frame(selector_frame)
        help_frame.grid(row=0, column=0, columnspan=4, sticky='ew', pady=(0, 8))

        view_control_frame = ttk.Frame(help_frame)
        view_control_frame.pack(fill='x', pady=(0, 5))

        self.view_badge = ttk.Label(view_control_frame, text="Viewing: Custom Selectors",
                                    font=('Arial', 9, 'bold'), foreground='#27ae60')
        self.view_badge.pack(side='left', padx=5)

        self.toggle_view_button = ttk.Button(view_control_frame,
                                             text="Switch to Scrape Selectors",
                                             command=self.toggle_selector_view,
                                             style='Action.TButton')
        self.toggle_view_button.pack(side='left', padx=5)

        ttk.Label(help_frame,
                  text="Define elements you want to interact with on the website.",
                  font=('Arial', 9, 'bold')).pack(anchor='w')
        ttk.Label(help_frame,
                  text="Available types: text, button, link, dropdown, checkbox, input, multiple, container",
                  foreground='#7f8c8d', font=('Arial', 8)).pack(anchor='w')

        # Row 1: Role + Tag
        ttk.Label(selector_frame, text="Role:",
                  font=('Arial', 9)).grid(row=1, column=0, sticky='w', padx=3, pady=3)
        self.role_var = tk.StringVar()
        role_combo = ttk.Combobox(selector_frame, textvariable=self.role_var)
        role_combo['values'] = self.existing_selectors['roles']
        role_combo.grid(row=1, column=1, sticky='ew', padx=3, pady=3)

        ttk.Label(selector_frame, text="HTML Tag:",
                  font=('Arial', 9)).grid(row=1, column=2, sticky='w', padx=8, pady=3)
        self.tag_var = tk.StringVar(value="div")
        tag_combo = ttk.Combobox(selector_frame, textvariable=self.tag_var)
        tag_combo['values'] = self.existing_selectors['tags']
        tag_combo.grid(row=1, column=3, sticky='ew', padx=3, pady=3)

        # Row 2: Element Type + Selector
        ttk.Label(selector_frame, text="Element Type:",
                  font=('Arial', 9)).grid(row=2, column=0, sticky='w', padx=3, pady=3)
        self.type_var = tk.StringVar()
        ttk.Combobox(selector_frame, textvariable=self.type_var,
                     values=('text', 'button', 'link', 'dropdown',
                             'checkbox', 'input', 'multiple', 'container')
                     ).grid(row=2, column=1, sticky='ew', padx=3, pady=3)

        ttk.Label(selector_frame, text="Selector:",
                  font=('Arial', 9)).grid(row=2, column=2, sticky='w', padx=8, pady=3)
        self.selector_var = tk.StringVar()
        selector_combo = ttk.Combobox(selector_frame, textvariable=self.selector_var)
        selector_combo['values'] = self.existing_selectors['selectors']
        selector_combo.grid(row=2, column=3, sticky='ew', padx=3, pady=3)

        # Row 3: Notes
        ttk.Label(selector_frame, text="Notes:",
                  font=('Arial', 9)).grid(row=3, column=0, sticky='w', padx=3, pady=3)
        self.notes_var = tk.StringVar()
        ttk.Entry(selector_frame, textvariable=self.notes_var).grid(
            row=3, column=1, columnspan=3, sticky='ew', padx=3, pady=3)

        # Row 4: Action Buttons
        action_row = ttk.Frame(selector_frame)
        action_row.grid(row=4, column=0, columnspan=4, sticky='ew', pady=8)

        self.add_button = ttk.Button(action_row, text="➕ Add to Custom",
                                     command=self.add_selector,
                                     style='Action.TButton', width=16)
        self.add_button.pack(side='left', padx=3)

        ttk.Button(action_row, text="🗑️ Remove Selected", command=self.remove_selector,
                   style='Danger.TButton', width=16).pack(side='left', padx=3)

        ttk.Button(action_row, text="👁️ Preview Selected", command=self.preview_selector,
                   style='Action.TButton', width=16).pack(side='left', padx=3)

        ttk.Button(action_row, text="✏️ Clear Fields", command=self.clear_selector_inputs,
                   style='Action.TButton', width=12).pack(side='left', padx=3)

        # Row 5: Treeview
        tree_container = ttk.Frame(selector_frame)
        tree_container.grid(row=5, column=0, columnspan=4, sticky='nsew', pady=5)
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        columns = ('role', 'tag', 'type', 'selector', 'notes')
        self.tree = ttk.Treeview(tree_container, columns=columns, show='headings', height=8)

        column_configs = [
            ('role', 'Role', 120),
            ('tag', 'Tag', 80),
            ('type', 'Type', 100),
            ('selector', 'Selector', 400),
            ('notes', 'Notes', 300)
        ]
        for col, heading, width in column_configs:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, minwidth=50)

        vsb = ttk.Scrollbar(tree_container, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        self.tree.bind('<Double-Button-1>', self.load_selector_to_fields)

        # Bottom Buttons
        action_frame = ttk.Frame(config_frame)
        action_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=8)

        button_container = ttk.Frame(action_frame)
        button_container.pack(anchor='center')

        self.save_button = ttk.Button(button_container, text="💾 Save Configuration",
                                      command=self.save_configuration,
                                      style='Success.TButton', width=18)
        self.save_button.pack(side='left', padx=5)

        self.update_button = ttk.Button(button_container, text="🔄 Update Existing",
                                        command=self.update_configuration,
                                        style='Action.TButton', width=18)
        self.update_button.pack(side='left', padx=5)

        ttk.Button(button_container, text="🗑️ Clear Form", command=self.clear_form,
                   style='Danger.TButton', width=15).pack(side='left', padx=5)

        # Status Bar
        status_bar = ttk.Frame(config_frame, relief='sunken', padding=3)
        status_bar.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(2, 0))

        self.status_label_var = tk.StringVar(value="✅ Ready to create new configuration")
        ttk.Label(status_bar, textvariable=self.status_label_var,
                  foreground='#27ae60', font=('Arial', 9)).pack(side='left')

        self.update_status_display()

    def update_status_display(self):
        """Update the status indicator based on selection"""
        if self.status_var.get():
            self.status_indicator_config.config(foreground='#27ae60')
            self.status_text.config(
                text="Configuration is active and will be used in automation")
        else:
            self.status_indicator_config.config(foreground='#e74c3c')
            self.status_text.config(
                text="Configuration is inactive and will be skipped in automation")

    # ==================== VIEW CONFIGURATIONS TAB ====================

    def create_view_tab(self):
        """Create tab for viewing existing configurations"""
        view_frame = ttk.Frame(self.notebook)
        self.notebook.add(view_frame, text="👁️ View Configurations")

        header_frame = ttk.Frame(view_frame)
        header_frame.pack(fill='x', pady=5)
        ttk.Label(header_frame, text="📋 Existing Configurations",
                  style='Header.TLabel').pack()
        ttk.Label(header_frame, text="Double-click any configuration to edit",
                  style='SubHeader.TLabel').pack()

        tree_frame = ttk.Frame(view_frame)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)

        columns = ('name', 'url', 'status', 'selectors', 'scraper_selectors',
                   'container_index', 'created')
        self.config_tree = ttk.Treeview(tree_frame, columns=columns,
                                         show='headings', height=12)

        column_configs = [
            ('name', 'Configuration Name', 180),
            ('url', 'URL', 220),
            ('status', 'Status', 80),
            ('selectors', 'Custom Sel.', 85),
            ('scraper_selectors', 'Scraper Sel.', 90),
            ('container_index', 'Container Idx', 110),
            ('created', 'Created', 130)
        ]
        for col, heading, width in column_configs:
            self.config_tree.heading(col, text=heading)
            self.config_tree.column(col, width=width, minwidth=50)

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.config_tree.yview)
        self.config_tree.configure(yscrollcommand=vsb.set)
        self.config_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.config_tree.bind('<Double-Button-1>', self.load_for_editing)

        btn_frame = ttk.Frame(view_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        button_container = ttk.Frame(btn_frame)
        button_container.pack(anchor='center')

        ttk.Button(button_container, text="✏️ Edit Selected",
                   command=self.edit_selected_config,
                   style='Action.TButton', width=15).pack(side='left', padx=3)
        ttk.Button(button_container, text="🔄 Toggle Status",
                   command=self.toggle_config_status,
                   style='Action.TButton', width=15).pack(side='left', padx=3)
        ttk.Button(button_container, text="🗑️ Delete Selected",
                   command=self.delete_configuration,
                   style='Danger.TButton', width=15).pack(side='left', padx=3)
        ttk.Button(button_container, text="🔄 Refresh",
                   command=self.refresh_view,
                   style='Action.TButton', width=10).pack(side='left', padx=3)

        summary_frame = ttk.Frame(view_frame, relief='sunken', padding=3)
        summary_frame.pack(fill='x', side='bottom', pady=3)
        ttk.Label(summary_frame, textvariable=self.summary_var,
                  font=('Arial', 8)).pack(side='left')

        self.load_configs_into_tree()

    def edit_selected_config(self):
        """Edit selected configuration from view tab"""
        selected = self.config_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a configuration to edit")
            return
        self.load_for_editing()

    def load_selector_to_fields(self, event=None):
        """Load selected selector into input fields for editing"""
        selected = self.tree.selection()
        if not selected:
            return

        item = self.tree.item(selected[0])
        values = item['values']

        if values[0] == "No selectors to display.":
            return

        data_source = self.selectors if self.view_mode == 'custom' else self.scraper_selectors

        for i, selector in enumerate(data_source):
            if (selector.get('role') == values[0] and
                    selector.get('value') == values[3]):
                self.editing_index = i
                self.editing_view_mode = self.view_mode

                self.role_var.set(selector.get('role', ''))
                self.tag_var.set(selector.get('tag', ''))
                self.type_var.set(selector.get('type', ''))
                self.selector_var.set(selector.get('value', ''))
                self.notes_var.set(selector.get('notes', ''))

                view_type = "scraper" if self.view_mode == 'scrape' else "custom"
                self.status_label_var.set(
                    f"✏️ Editing {view_type} selector: {values[0]}")
                break

    def load_configs_into_tree(self):
        """Load configurations into the view tree"""
        for item in self.config_tree.get_children():
            self.config_tree.delete(item)

        for config in self.existing_configs:
            status = "✅ Active" if config.get('active', True) else "❌ Inactive"
            idx = config.get('main_container_index', [])
            idx_display = ', '.join(str(i) for i in idx) if idx else '—'
            self.config_tree.insert('', 'end', values=(
                config.get('name', 'Unnamed'),
                config.get('base_url', 'N/A'),
                status,
                len(config.get('custom_selectors', [])),
                len(config.get('scraper_selectors', [])),
                idx_display,
                config.get('metadata', {}).get('created_at', 'Unknown')
            ))

        total_configs = len(self.existing_configs)
        active_configs = sum(1 for c in self.existing_configs if c.get('active', True))
        self.summary_var.set(
            f"📊 Total: {total_configs} configurations | "
            f"✅ Active: {active_configs} | "
            f"❌ Inactive: {total_configs - active_configs}"
        )

    # ==================== CONFIGURATION METHODS ====================

    def test_url(self):
        """Test URL in browser"""
        url = self.url_var.get().strip()
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            webbrowser.open(url)
        else:
            messagebox.showwarning("No URL", "Please enter a URL first")

    def update_container_index(self, event=None):
        """
        Parse the ConIndex_var entry into self.main_container_index.
        Accepts comma-separated integers, e.g. "0, 1, 2"  →  [0, 1, 2]
        Silently ignores non-integer tokens.
        """
        value_str = self.ConIndex_var.get().strip()
        if not value_str:
            self.main_container_index = []
            return

        indices = []
        for part in value_str.split(','):
            part = part.strip()
            if part:
                try:
                    indices.append(int(part))
                except ValueError:
                    pass  # ignore non-integer tokens

        self.main_container_index = indices

    def _apply_container_index_to_config(self, config: dict):
        """
        Helper: always call update_container_index first, then either
        write or remove 'main_container_index' in *config* dict.
        """
        self.update_container_index()
        if self.main_container_index:
            config["main_container_index"] = self.main_container_index
        else:
            config.pop("main_container_index", None)

    def add_selector(self):
        """Add or update selector in the current view's list"""
        role = self.role_var.get().strip()
        tag = self.tag_var.get().strip()
        sel_type = self.type_var.get().strip()
        selector = self.selector_var.get().strip()
        notes = self.notes_var.get().strip()

        if not all([role, tag, sel_type, selector]):
            messagebox.showwarning(
                "Missing Information",
                "Role, HTML Tag, Element Type, and Selector are required!")
            return

        selector_data = {
            "role": role,
            "tag": tag,
            "type": sel_type,
            "value": selector
        }
        if notes:
            selector_data["notes"] = notes

        target_list = self.selectors if self.view_mode == 'custom' else self.scraper_selectors
        list_name = "custom" if self.view_mode == 'custom' else "scraper"

        if (self.editing_index != -1 and
                self.editing_view_mode == self.view_mode and
                0 <= self.editing_index < len(target_list)):
            target_list[self.editing_index] = selector_data
            self.status_label_var.set(f"✅ Updated {list_name} selector: {role}")
        else:
            target_list.append(selector_data)
            self.status_label_var.set(f"✅ Added {list_name} selector: {role}")
            self.editing_index = -1

        self.update_selector_list()
        self.clear_selector_inputs()

    def update_selector_list(self):
        """Update the treeview with current selectors based on view mode"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        data_source = self.selectors if self.view_mode == 'custom' else self.scraper_selectors

        if not data_source:
            self.tree.insert('', 'end', values=("No selectors to display.", "", "", "", ""))
            return

        for selector in data_source:
            self.tree.insert('', 'end', values=(
                selector.get('role', ''),
                selector.get('tag', ''),
                selector.get('type', ''),
                selector.get('value', ''),
                selector.get('notes', '')
            ))

    def remove_selector(self):
        """Remove selected selector from current view"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a selector to remove")
            return

        item = self.tree.item(selected[0])
        values = item['values']
        if values[0] == "No selectors to display.":
            return

        role = values[0]
        selector_value = values[3]
        target_list = self.selectors if self.view_mode == 'custom' else self.scraper_selectors
        list_name = "custom" if self.view_mode == 'custom' else "scraper"

        for i, selector in enumerate(target_list):
            if (selector.get('role') == role and
                    selector.get('value') == selector_value):
                target_list.pop(i)
                if (self.editing_index == i and
                        self.editing_view_mode == self.view_mode):
                    self.editing_index = -1
                break

        self.update_selector_list()
        self.status_label_var.set(f"🗑️ Removed {list_name} selector: {role}")

    def preview_selector(self):
        """Preview selected selector"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a selector to preview")
            return

        item = self.tree.item(selected[0])
        values = item['values']
        if values[0] == "No selectors to display.":
            return

        role, tag, sel_type, selector, notes = values
        preview_text = (
            f"Role:     {role}\n\n"
            f"Tag:      {tag}\n\n"
            f"Type:     {sel_type}\n\n"
            f"Selector: {selector}\n\n"
            f"Notes:    {notes or '—'}"
        )
        messagebox.showinfo(f"🔍 Selector Preview — {role}", preview_text)

    def clear_selector_inputs(self):
        """Clear selector input fields and reset edit mode"""
        self.role_var.set('')
        self.tag_var.set('div')
        self.type_var.set('')
        self.selector_var.set('')
        self.notes_var.set('')
        self.editing_index = -1

    def _populate_form_from_config(self, config: dict):
        """Helper: fill all form fields from a config dict"""
        self.current_config = config
        self.name_var.set(config.get('name', ''))
        self.url_var.set(config.get('base_url', ''))
        self.desc_var.set(config.get('description', ''))
        self.status_var.set(config.get('active', True))
        self.version_var.set(config.get('version', '1.0'))

        self.selectors = config.get('custom_selectors', []).copy()
        self.scraper_selectors = config.get('scraper_selectors', []).copy()

        # Always load main_container_index regardless of view mode
        idx = config.get('main_container_index', [])
        self.main_container_index = list(idx)
        self.ConIndex_var.set(', '.join(str(i) for i in idx) if idx else '')

        self.view_mode = 'custom'
        self.editing_index = -1

        if hasattr(self, 'toggle_view_button') and hasattr(self, 'view_badge'):
            self.toggle_view_button.config(text="Switch to Scrape Selectors")
            self.view_badge.config(text="Viewing: Custom Selectors", foreground='#27ae60')
            self.add_button.config(text="➕ Add to Custom")

        self.update_selector_list()
        self.update_status_display()

    def load_existing_config(self, event=None):
        """Load selected existing config for editing (from name combobox)"""
        selected_name = self.name_var.get()
        for config in self.existing_configs:
            if config.get('name') == selected_name:
                self._populate_form_from_config(config)
                # Keep Save enabled in case user wants to clone under a new name,
                # but Update is the primary action here
                self.save_button.config(state='normal')
                self.update_button.config(state='normal')
                self.status_label_var.set(
                    f"✏️ Loaded '{selected_name}' — edit freely, then Save or Update.")
                break

    def load_for_editing(self, event=None):
        """Load selected config from view tab for editing"""
        selected = self.config_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a configuration to edit")
            return

        item = self.config_tree.item(selected[0])
        config_name = item['values'][0]

        for config in self.existing_configs:
            if config.get('name') == config_name:
                self._populate_form_from_config(config)
                self.save_button.config(state='normal')
                self.update_button.config(state='normal')
                self.status_label_var.set(f"✏️ Editing: {config_name}")
                self.notebook.select(1)
                break

    def load_existing_config_by_name(self, name: str):
        """Load existing config by name (called when user confirms overwrite)"""
        for config in self.existing_configs:
            if config.get('name') == name:
                self._populate_form_from_config(config)
                self.save_button.config(state='normal')
                self.update_button.config(state='normal')
                self.status_label_var.set(
                    f"✏️ Loaded '{name}' — edit and click Update Existing to save changes.")
                break

    def clear_form(self):
        """Clear all form data"""
        if messagebox.askyesno("Clear Form", "Are you sure you want to clear all form data?"):
            self.name_var.set('')
            self.url_var.set('')
            self.desc_var.set('')
            self.status_var.set(True)
            self.version_var.set('1.0')
            self.selectors = []
            self.scraper_selectors = []
            self.main_container_index = []
            self.ConIndex_var.set('')
            self.current_config = None
            self.view_mode = 'custom'
            self.editing_index = -1

            if hasattr(self, 'toggle_view_button') and hasattr(self, 'view_badge'):
                self.toggle_view_button.config(text="Switch to Scrape Selectors",
                                               state='normal')
                self.view_badge.config(text="Viewing: Custom Selectors",
                                       foreground='#27ae60')
                self.add_button.config(text="➕ Add to Custom")

            self.update_selector_list()
            self.clear_selector_inputs()
            self.update_status_display()
            self.save_button.config(state='normal')
            self.update_button.config(state='normal')
            self.status_label_var.set("✅ Ready to create new configuration")

    def _auto_assign_param(self, selector_list: list):
        """Auto-assign 'param' key for selectors that don't have one yet"""
        for s in selector_list:
            if not s.get("param"):
                text = (f"{s.get('role', '')} "
                        f"{s.get('notes', '')} "
                        f"{s.get('value', '')}").lower()
                if "country" in text or "countries" in text:
                    s["param"] = "country"
                elif "category" in text or "categories" in text:
                    s["param"] = "category"
                elif "platform" in text or "store" in text:
                    s["param"] = "platform"

    def save_configuration(self):
        """Save new configuration to file"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing Information",
                                   "Configuration name is required!")
            return

        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing Information", "Website URL is required!")
            return

        if not self.selectors and not self.scraper_selectors:
            messagebox.showwarning("No Selectors",
                                   "Please add at least one selector!")
            return

        # Auto-assign params
        self._auto_assign_param(self.selectors)

        # Check for duplicate name — offer to switch to update mode
        for config in self.existing_configs:
            if config.get('name') == name:
                if not messagebox.askyesno(
                        "Name Exists",
                        f"Configuration '{name}' already exists.\n"
                        "Do you want to update it instead?"):
                    return
                else:
                    self.load_existing_config_by_name(name)
                    return

        config = {
            "name": name,
            "base_url": url,
            "active": self.status_var.get(),
            "version": self.version_var.get(),
            "description": self.desc_var.get().strip(),
            "custom_selectors": self.selectors,
            "scraper_selectors": self.scraper_selectors,
            "metadata": {
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_selectors": len(self.selectors),
                "total_scraper_selectors": len(self.scraper_selectors)
            }
        }

        # Always apply container index (view-mode independent)
        self._apply_container_index_to_config(config)

        # Write — write_config_to_file will re-point self.current_config automatically
        self.write_config_to_file(config, is_update=False)

    def update_configuration(self):
        """Update existing configuration — works any number of times after initial save."""
        name = self.name_var.get().strip()
        url = self.url_var.get().strip()

        if not name:
            messagebox.showwarning("Missing Information",
                                   "Configuration name is required!")
            return
        if not url:
            messagebox.showwarning("Missing Information", "Website URL is required!")
            return

        # If current_config is None (e.g. user typed a name but never loaded a config),
        # try to find it in existing_configs by name before failing.
        if not self.current_config:
            matched = next(
                (c for c in self.existing_configs if c.get('name') == name), None
            )
            if matched:
                self.current_config = matched
            else:
                messagebox.showwarning(
                    "No Configuration",
                    f"No saved configuration named '{name}' found.\n"
                    "Use 'Save Configuration' to create it first, or load an existing one."
                )
                return

        self._auto_assign_param(self.selectors)

        self.current_config["name"] = name
        self.current_config["base_url"] = url
        self.current_config["description"] = self.desc_var.get().strip()
        self.current_config["active"] = self.status_var.get()
        self.current_config["version"] = self.version_var.get()
        self.current_config["custom_selectors"] = self.selectors
        self.current_config["scraper_selectors"] = self.scraper_selectors

        # Always apply container index (view-mode independent)
        self._apply_container_index_to_config(self.current_config)

        if "metadata" not in self.current_config:
            self.current_config["metadata"] = {}
        self.current_config["metadata"]["total_selectors"] = len(self.selectors)
        self.current_config["metadata"]["total_scraper_selectors"] = len(
            self.scraper_selectors)
        self.current_config["metadata"]["updated_at"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")

        self.write_config_to_file(self.current_config, is_update=True)

    def write_config_to_file(self, config: dict, is_update: bool = False):
        """Write configuration to file, then keep the form live for further edits."""
        filepath = Path(__file__).parent / "custom_patterns.json"

        existing_data = []
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        existing_data = json.loads(content)
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
            except Exception:
                existing_data = []

        config_name = config.get('name', '')

        if is_update:
            replaced = False
            for i, c in enumerate(existing_data):
                if c.get('name') == config_name:
                    existing_data[i] = config
                    replaced = True
                    break
            if not replaced:
                # Name was changed — remove old entry by matching current_config's original name
                orig_name = (self.current_config or {}).get('name', '')
                existing_data = [c for c in existing_data if c.get('name') != orig_name]
                existing_data.append(config)
            action = "updated"
        else:
            existing_data.append(config)
            action = "saved"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

        # Reload file into memory and refresh the view tree
        self.existing_configs = self.load_existing_configs()
        self.extract_all_selectors()
        self.load_configs_into_tree()

        # --- KEY FIX: re-point current_config to the freshly saved object ---
        # This means Update Existing will keep working after any number of saves.
        self.current_config = next(
            (c for c in self.existing_configs if c.get('name') == config_name),
            None
        )

        # Both buttons always enabled after a write — user can keep editing
        self.save_button.config(state='normal')
        self.update_button.config(state='normal' if self.current_config else 'disabled')

        status_text = "✅ Active" if config.get('active') else "❌ Inactive"
        idx = config.get('main_container_index', [])
        idx_info = (f"\nMain container index: [{', '.join(str(i) for i in idx)}]"
                    if idx else "")

        self.status_label_var.set(
            f"✅ '{config_name}' {action} — you can keep editing or add more selectors."
        )

        messagebox.showinfo(
            "Success",
            f"Configuration '{config_name}' has been {action}!\n"
            f"Status: {status_text}\n"
            f"Custom selectors: {len(config.get('custom_selectors', []))}\n"
            f"Scraper selectors: {len(config.get('scraper_selectors', []))}"
            f"{idx_info}\n\n"
            f"You can continue editing and click\n"
            f"'Update Existing' again at any time."
        )
        self.notebook.select(1)

    def toggle_selector_view(self):
        """Toggle between custom and scrape selector views"""
        if self.view_mode == 'custom':
            self.view_mode = 'scrape'
            self.toggle_view_button.config(text="Switch to Custom Selectors")
            self.view_badge.config(text="Viewing: Scrape Selectors", foreground='#e67e22')
            self.add_button.config(text="➕ Add to Scrape")
        else:
            self.view_mode = 'custom'
            self.toggle_view_button.config(text="Switch to Scrape Selectors")
            self.view_badge.config(text="Viewing: Custom Selectors", foreground='#27ae60')
            self.add_button.config(text="➕ Add to Custom")

        # Reset edit mode when switching views
        self.editing_index = -1
        self.clear_selector_inputs()
        self.update_selector_list()

    def toggle_config_status(self):
        """Toggle the active status of selected configuration"""
        selected = self.config_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a configuration")
            return

        item = self.config_tree.item(selected[0])
        config_name = item['values'][0]

        for config in self.existing_configs:
            if config.get('name') == config_name:
                config['active'] = not config.get('active', True)
                if 'metadata' not in config:
                    config['metadata'] = {}
                config['metadata']['status_updated_at'] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S")
                self.save_all_configs()
                self.load_configs_into_tree()
                new_status = "activated" if config['active'] else "deactivated"
                messagebox.showinfo("Success",
                                    f"Configuration '{config_name}' has been {new_status}!")
                break

    def delete_configuration(self):
        """Delete selected configuration"""
        selected = self.config_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection",
                                   "Please select a configuration to delete")
            return

        item = self.config_tree.item(selected[0])
        config_name = item['values'][0]

        if not messagebox.askyesno("Confirm Delete",
                                    f"Are you sure you want to delete '{config_name}'?"):
            return

        self.existing_configs = [
            c for c in self.existing_configs if c.get('name') != config_name
        ]
        self.save_all_configs()
        self.load_configs_into_tree()
        self.extract_all_selectors()
        messagebox.showinfo("Success",
                            f"Configuration '{config_name}' deleted successfully!")

    def refresh_view(self):
        """Refresh the view tab"""
        self.existing_configs = self.load_existing_configs()
        self.extract_all_selectors()
        self.load_configs_into_tree()
        messagebox.showinfo("Refreshed", "View updated with latest data!")

    # ==================== LOGGING METHODS ====================

    def setup_logging(self):
        """Redirect logs to GUI"""
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        queue_handler.setFormatter(formatter)
        logging.getLogger().addHandler(queue_handler)
        self.stdout_queue = queue.Queue()
        sys.stdout = self.GUITextIO(self.stdout_queue)

    # ==================== AUTOMATION METHODS ====================

    def start_automation(self):
        """Start the automation in a separate thread"""
        if self.is_running:
            return

        global STOP_AUTOMATION
        STOP_AUTOMATION = False
        self.stop_flag = False

        self.is_running = True
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
            logger.error(f"Automation error: {e}")
        finally:
            self.root.after(0, self.automation_finished)

    def stop_automation(self):
        """Stop the automation gracefully"""
        if self.is_running:
            global STOP_AUTOMATION
            STOP_AUTOMATION = True
            self.stop_flag = True
            self.status_indicator.config(foreground='orange')
            self.status_label.config(text="Stopping Automation...")
            self.stop_button.config(state='disabled')
            logger.warning("⏹️ Stop signal sent — waiting for current operation to complete...")
            self.root.after(5000, self.force_stop_if_needed)

    def force_stop_if_needed(self):
        """Force stop if automation didn't respond to graceful stop"""
        if self.is_running and self.stop_flag:
            logger.error("⛔ Automation forcefully stopped!")
            self.automation_finished()

    def automation_finished(self):
        """Handle automation completion"""
        self.is_running = False
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
            self.root.after(1000, self.update_timer)

    def update_logs(self):
        """Update log display from queue"""
        try:
            while True:
                record = self.log_queue.get_nowait()
                if 'ERROR' in record:
                    tag = 'ERROR'
                elif 'WARNING' in record:
                    tag = 'WARNING'
                elif 'SUCCESS' in record or '✅' in record:
                    tag = 'SUCCESS'
                elif 'INFO' in record:
                    tag = 'INFO'
                else:
                    tag = 'DEBUG'

                self.log_text.insert(tk.END, record + '\n', tag)
                self.log_text.see(tk.END)
                self.update_statistics(record)
        except queue.Empty:
            pass
        self.root.after(100, self.update_logs)

    def update_statistics(self, log_entry):
        """Update statistics based on log entries"""
        if '✅' in log_entry or 'Success' in log_entry or 'saved' in log_entry.lower():
            current = int(self.success_count.cget('text'))
            self.success_count.config(text=str(current + 1))
        if '❌' in log_entry or 'Failed' in log_entry or 'Error' in log_entry:
            current = int(self.fail_count.cget('text'))
            self.fail_count.config(text=str(current + 1))
        if 'MHTML' in log_entry and ('saved' in log_entry.lower() or 'created' in log_entry.lower()):
            current = int(self.files_count.cget('text'))
            self.files_count.config(text=str(current + 1))
        log_content = self.log_text.get(1.0, tk.END)
        self.log_count_label.config(text=f"Entries: {len(log_content.split(chr(10)))}")

    def clear_logs(self):
        """Clear the log display"""
        self.log_text.delete(1.0, tk.END)
        self.success_count.config(text="0")
        self.fail_count.config(text="0")
        self.files_count.config(text="0")
        self.log_count_label.config(text="Entries: 0")

    def copy_logs(self):
        """Copy all logs to clipboard"""
        logs = self.log_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(logs)
        messagebox.showinfo("Copied", "Logs copied to clipboard!")

    def filter_logs(self, event=None):
        """Highlight matching log lines"""
        filter_text = self.filter_var.get().lower()
        self.log_text.tag_remove('highlight', 1.0, tk.END)
        if filter_text:
            start = 1.0
            while True:
                pos = self.log_text.search(filter_text, start, tk.END)
                if not pos:
                    break
                end = f"{pos}+{len(filter_text)}c"
                self.log_text.tag_add('highlight', pos, end)
                start = end
            self.log_text.tag_config('highlight', background='yellow', foreground='black')

    def clear_filter(self):
        """Clear the filter"""
        self.filter_var.set("")
        self.log_text.tag_remove('highlight', 1.0, tk.END)

    def on_closing(self):
        """Handle window close event"""
        if self.is_running:
            if messagebox.askyesno("Exit", "Automation is still running. Stop and exit?"):
                self.stop_automation()
                self.root.destroy()
        else:
            self.root.destroy()

    # ==================== UTILITY CLASSES ====================

    class GUITextIO(StringIO):
        """Custom StringIO to redirect stdout to GUI"""

        def __init__(self, q):
            super().__init__()
            self.queue = q

        def write(self, s):
            if s.strip():
                self.queue.put(s)
            super().write(s)


# ==================== MAIN EXECUTION ====================

def main():
    root = tk.Tk()
    app = AutomationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
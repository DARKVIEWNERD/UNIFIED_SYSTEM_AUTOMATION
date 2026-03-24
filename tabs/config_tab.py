"""Configuration builder tab"""
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from datetime import datetime

from tabs.base import Base
from models.data_models import Configuration, Selector
from constants.selectors import SelectorTypes


class ConfigTab(Base):
    """Configuration builder tab"""
    
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title = "⚙️ Create Configuration"
        
        # Form variables
        self.name_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        self.version_var = tk.StringVar(value="1.0")
        self.status_var = tk.BooleanVar(value=True)
        self.ConIndex_var = tk.StringVar()
        self.scrape_profile_var = tk.StringVar()
        
        # Selector variables
        self.role_var = tk.StringVar()
        self.tag_var = tk.StringVar(value="div")
        self.type_var = tk.StringVar()
        self.selector_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        
        # State variables
        self.current_config = None
        self.view_mode = 'custom'  # 'custom' or 'scrape'
        self.editing_index = -1
        self.editing_view_mode = 'custom'
        self.main_container_index = None
        self.selectors = []  # Custom selectors
        self.scraper_selectors = []  # Scrape selectors
        
        # UI Elements (will be set in build)
        self.tree = None
        self.add_button = None
        self.toggle_view_button = None
        self.view_badge = None
        self.save_button = None
        self.update_button = None
        self.status_label_var = tk.StringVar(value="✅ Ready to create new configuration")
        self.status_indicator_config = None
        self.status_text = None
        self.config_details_frame = None
        self.status_config_frame = None
        self.index_frame = None
        self._selector_frame_ref = None
        
        # Custom-only widgets
        self._lbl_name = None
        self._widget_name = None
        self._lbl_url = None
        self._widget_url = None
        self._btn_test_url = None
        self._lbl_desc = None
        self._widget_desc = None
        
        # Scrape-only widgets
        self._lbl_profile = None
        self._profile_combo = None
        self._lbl_profile_hint = None
        
    def build(self):
        """Build the configuration tab"""
        # Create scrollable frame
        canvas, scrollbar, scrollable = self.create_scrollable_frame(self.frame)
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Configure canvas width
        def configure_canvas(event):
            canvas.itemconfig(1, width=event.width)
        canvas.bind('<Configure>', configure_canvas)
        
        # Main container
        main_container = ttk.Frame(scrollable)
        main_container.pack(fill='both', expand=True, padx=10, pady=5)
        main_container.columnconfigure(0, weight=1)
        
        # Header
        self.build_header(main_container)
        
        # Configuration Details
        self.build_config_details(main_container)
        
        # Status
        self.build_status_section(main_container)
        
        # Main Container Index
        self.build_container_index_section(main_container)
        
        # Selector Configuration
        self.build_selector_section(main_container)
        
        # Bottom Buttons
        self.build_action_buttons()
        
        # Status Bar
        self.build_status_bar()
        
        # Initial visibility
        self.update_status_display()
        self._refresh_fields_visibility()
        
    def build_header(self, parent):
        """Build header section"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(header_frame, text="CUSTOM AUTOMATION CONFIGURATION BUILDER",
                  font=('Arial', 14, 'bold')).pack()
        ttk.Label(header_frame,
                  text="Create reusable selectors for web automation. These will be saved to use in your automation scripts.",
                  font=('Arial', 9), foreground='gray', wraplength=1000).pack()
        
    def build_config_details(self, parent):
        """Build configuration details section"""
        self.config_details_frame = ttk.LabelFrame(parent, text="📋 Configuration Details", padding=12)
        self.config_details_frame.pack(fill='x', pady=3)
        self.config_details_frame.columnconfigure(1, weight=1)
        config_details = self.config_details_frame
        
        # Custom-only rows (rows 0-2)
        self._lbl_name = ttk.Label(config_details, text="Configuration Name:", font=('Arial', 9))
        self._lbl_name.grid(row=0, column=0, sticky='w', padx=3, pady=3)
        # ✅ BUG FIX: Do NOT reassign self.name_var here. The StringVar created in __init__
        # is what the rest of the code reads/writes. Reassigning it creates a new orphaned
        # var bound to the widget while all other methods still point to the old one.
        name_combo = ttk.Combobox(config_details, textvariable=self.name_var, height=5)
        existing_names = [c.name for c in self.app.config_manager.configs if c.name]
        name_combo['values'] = existing_names
        name_combo.grid(row=0, column=1, columnspan=2, sticky='ew', padx=3, pady=3)
        name_combo.bind('<<ComboboxSelected>>', self.load_existing_config)
        self._widget_name = name_combo
        
        self._lbl_url = ttk.Label(config_details, text="Website URL:", font=('Arial', 9))
        self._lbl_url.grid(row=1, column=0, sticky='w', padx=3, pady=3)
        # ✅ BUG FIX: Same — do NOT reassign self.url_var.
        url_combo = ttk.Combobox(config_details, textvariable=self.url_var, height=5)
        existing_urls = list(set(c.base_url for c in self.app.config_manager.configs if c.base_url))
        url_combo['values'] = existing_urls
        url_combo.grid(row=1, column=1, sticky='ew', padx=3, pady=3)
        self._widget_url = url_combo
        self._btn_test_url = ttk.Button(config_details, text="🔍 Test URL", command=self.test_url,
                                        style='Action.TButton', width=12)
        self._btn_test_url.grid(row=1, column=2, padx=3, pady=3, sticky='w')
        
        self._lbl_desc = ttk.Label(config_details, text="Description:", font=('Arial', 9))
        self._lbl_desc.grid(row=2, column=0, sticky='w', padx=3, pady=3)
        # ✅ BUG FIX: Do NOT reassign self.desc_var.
        self._widget_desc = ttk.Entry(config_details, textvariable=self.desc_var)
        self._widget_desc.grid(row=2, column=1, columnspan=2, sticky='ew', padx=3, pady=3)
        
        # Scrape-only row (row 3)
        self._lbl_profile = ttk.Label(config_details, text="Scrape Profile Key:", font=('Arial', 9))
        self._lbl_profile.grid(row=3, column=0, sticky='w', padx=3, pady=3)
        existing_profiles = list(self.load_scrape_configs().keys())
        self._profile_combo = ttk.Combobox(config_details,
                                           textvariable=self.scrape_profile_var, height=5)
        self._profile_combo['values'] = existing_profiles
        self._profile_combo.grid(row=3, column=1, sticky='ew', padx=3, pady=3)
        self._lbl_profile_hint = ttk.Label(config_details,
                                           text="Key in config.json",
                                           foreground='#7f8c8d', font=('Arial', 8))
        self._lbl_profile_hint.grid(row=3, column=2, sticky='w', padx=3, pady=3)
        self._profile_combo.bind('<<ComboboxSelected>>', self._on_profile_selected)
        
    def build_status_section(self, parent):
        """Build status section"""
        self.status_config_frame = ttk.LabelFrame(parent, text="⚡ Configuration Status", padding=10)
        self.status_config_frame.pack(fill='x', pady=3)
        self.status_config_frame.columnconfigure(1, weight=1)
        status_frame = self.status_config_frame
        
        ttk.Label(status_frame, text="Active Status:",
                  font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky='w', padx=3, pady=3)
        radio_frame = ttk.Frame(status_frame)
        radio_frame.grid(row=0, column=1, sticky='w', padx=3, pady=3)
        # ✅ BUG FIX: Do NOT reassign self.status_var — reuse the one from __init__.
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
        ttk.Entry(version_frame, textvariable=self.version_var, width=6).pack(side='left')
        
    def build_container_index_section(self, parent):
        """Build main container index section"""
        self.index_frame = ttk.LabelFrame(parent,
                                        text="🗂 Main Container Index  (comma-separated, e.g. 0, 1, 2)",
                                        padding=10)
        self.index_frame.pack(fill='x', pady=3)
        self.index_frame.columnconfigure(1, weight=1)
        
        ttk.Label(self.index_frame, text="Index values:",
                  font=('Arial', 9)).grid(row=0, column=0, sticky='w', padx=3, pady=3)
        
        container_index_entry = ttk.Entry(self.index_frame, textvariable=self.ConIndex_var)
        container_index_entry.grid(row=0, column=1, sticky='ew', padx=3, pady=3)
        container_index_entry.bind('<KeyRelease>', self.update_container_index)
        container_index_entry.bind('<FocusOut>', self.update_container_index)
        
        ttk.Label(self.index_frame,
                  text="Leave empty to omit from saved JSON.",
                  foreground='#7f8c8d', font=('Arial', 8)).grid(
            row=1, column=0, columnspan=2, sticky='w', padx=3)
            
    def build_selector_section(self, parent):
        """Build selector configuration section"""
        selector_frame = ttk.LabelFrame(parent, text="🎯 Selector Configuration",
                                        padding=12)
        selector_frame.pack(fill='both', expand=True, pady=3)
        self._selector_frame_ref = selector_frame
        selector_frame.columnconfigure(1, weight=1)
        selector_frame.columnconfigure(3, weight=2)
        selector_frame.rowconfigure(6, weight=1)
        
        # View toggle bar
        self.build_view_toggle(selector_frame)
        
        # Row 1: Role + Tag
        ttk.Label(selector_frame, text="Role:",
                  font=('Arial', 9)).grid(row=1, column=0, sticky='w', padx=3, pady=3)


        role_combo = ttk.Combobox(selector_frame, textvariable=self.role_var)
        role_combo['values'] = self.app.config_manager.selectors_pool['roles']
        role_combo.grid(row=1, column=1, sticky='ew', padx=3, pady=3)
        self._role_combo = role_combo
        
        ttk.Label(selector_frame, text="HTML Tag:",
                  font=('Arial', 9)).grid(row=1, column=2, sticky='w', padx=8, pady=3)
        tag_combo = ttk.Combobox(selector_frame, textvariable=self.tag_var)
        tag_combo['values'] = self.app.config_manager.selectors_pool['tags']
        tag_combo.grid(row=1, column=3, sticky='ew', padx=3, pady=3)
        
        # Row 2: Element Type + Selector
        ttk.Label(selector_frame, text="Element Type:",
                  font=('Arial', 9)).grid(row=2, column=0, sticky='w', padx=3, pady=3)
        ttk.Combobox(selector_frame, textvariable=self.type_var,
                     values=SelectorTypes.ALL).grid(row=2, column=1, sticky='ew', padx=3, pady=3)
        
        ttk.Label(selector_frame, text="Selector:",
                  font=('Arial', 9)).grid(row=2, column=2, sticky='w', padx=8, pady=3)
        selector_combo = ttk.Combobox(selector_frame, textvariable=self.selector_var)
        selector_combo['values'] = self.app.config_manager.selectors_pool['selectors']
        selector_combo.grid(row=2, column=3, sticky='ew', padx=3, pady=3)
        
        # Row 3: Notes
        ttk.Label(selector_frame, text="Notes:",
                  font=('Arial', 9)).grid(row=3, column=0, sticky='w', padx=3, pady=3)
        ttk.Entry(selector_frame, textvariable=self.notes_var).grid(
            row=3, column=1, columnspan=3, sticky='ew', padx=3, pady=3)
        
        # Row 4: Action Buttons
        self.build_selector_actions(selector_frame)
        
        # Row 5: Treeview
        self.build_selector_tree(selector_frame)
        
    def build_view_toggle(self, parent):
        """Build view toggle controls"""
        help_frame = ttk.Frame(parent)
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
        
    def build_selector_actions(self, parent):
        """Build selector action buttons"""
        action_row = ttk.Frame(parent)
        action_row.grid(row=4, column=0, columnspan=4, sticky='ew', pady=8)
        
        self.add_button = ttk.Button(action_row, text="➕ Add to Custom",
                                     command=self.add_selector,
                                     style='Action.TButton', width=16)
        self.add_button.pack(side='left', padx=3)
        
        ttk.Button(action_row, text="🗑️ Delete ", command=self.remove_selector,
                   style='Danger.TButton', width=16).pack(side='left')
        
        ttk.Button(action_row, text="👁️ View ", command=self.preview_selector,
                   style='Action.TButton', width=16).pack(side='left')
        
        ttk.Button(action_row, text="✏️ Clear Fields", command=self.clear_selector_inputs,
                   style='Action.TButton', width=16).pack(side='left')
        
    def build_selector_tree(self, parent):
        """Build selector treeview"""
        tree_container = ttk.Frame(parent)
        tree_container.grid(row=5, column=0, columnspan=4, sticky='nsew')
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
        
    def build_action_buttons(self):
        """Build main action buttons"""
        action_frame = ttk.Frame(self.frame)
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
        
    def build_status_bar(self):
        """Build status bar"""
        status_bar = ttk.Frame(self.frame, relief='sunken', padding=3)
        status_bar.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(2, 0))
        
        self.status_label_var = tk.StringVar(value="✅ Ready to create new configuration")
        ttk.Label(status_bar, textvariable=self.status_label_var,
                  foreground='#27ae60', font=('Arial', 9)).pack(side='left')
        
    # ==================== ACTION METHODS ====================
    
    def load_scrape_configs(self):
        """Load scrape configs from app's config manager"""
        return self.app.config_manager.load_scrape_configs()
        
    def test_url(self):
        """Test URL in browser"""
        url = self.url_var.get().strip()
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            webbrowser.open(url)
        else:
            messagebox.showwarning("No URL", "Please enter a URL first")
            
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
                
    def update_container_index(self, event=None):
        """Parse the ConIndex_var entry into self.main_container_index as a single integer."""
        value_str = self.ConIndex_var.get().strip()
        if not value_str:
            self.main_container_index = None
            return
            
        try:
            self.main_container_index = int(value_str)
        except ValueError:
            self.main_container_index = None
            self.ConIndex_var.set('')
            messagebox.showwarning("Invalid Input", "Please enter a single valid integer")
    
    def _get_scrape_roles(self) -> list:
        """Get roles only from config.json scraper selectors"""
        return [
        "Main Container",
        "Row Container",
        "App Name",
        "Publisher",
        "App Link",
    ]

    def _get_custom_roles(self) -> list:
        """Get roles only from custom_patterns.json custom selectors"""
        roles = set()
        for config in self.app.config_manager.configs:
            if hasattr(config, 'custom_selectors') and config.custom_selectors:
                for s in config.custom_selectors:
                    role = getattr(s, 'role', None)
                    if role:
                        roles.add(role)
        return sorted(list(roles))
            
    def toggle_selector_view(self):
        """Toggle between custom and scrape selector views"""
        if self.view_mode == 'custom':
            self.view_mode = 'scrape'
            self.toggle_view_button.config(text="Switch to Custom Selectors")
            self.view_badge.config(text="Viewing: Scrape Selectors", foreground='#e67e22')
            self.add_button.config(text="➕ Add to Scrape")

            # ← Show only SCRAPE roles in dropdown
            scrape_roles = self._get_scrape_roles()
            self._role_combo.config(values=scrape_roles)
            # Refresh profile dropdown
            existing_profiles = list(self.load_scrape_configs().keys())
            self._profile_combo['values'] = existing_profiles
            
            # Load if profile selected
            selected_key = self.scrape_profile_var.get().strip()
            if selected_key:
                self._load_scrape_profile(selected_key)
        else:
            self.view_mode = 'custom'
            self.toggle_view_button.config(text="Switch to Scrape Selectors")
            self.view_badge.config(text="Viewing: Custom Selectors", foreground='#27ae60')
            self.add_button.config(text="➕ Add to Custom")

                    # ← Show only CUSTOM roles in dropdown
            custom_roles = self._get_custom_roles()
            self._role_combo.config(values=custom_roles)
            
        self._refresh_fields_visibility()
        self.editing_index = -1
        self.clear_selector_inputs()
        self.update_selector_list()
        
    def _refresh_fields_visibility(self):
        """Show/hide fields based on view_mode"""
        custom_widgets = [
            self._lbl_name, self._widget_name,
            self._lbl_url, self._widget_url, self._btn_test_url,
            self._lbl_desc, self._widget_desc,
        ]
        scrape_widgets = [
            self._lbl_profile, self._profile_combo, self._lbl_profile_hint,
        ]
        
        if self.view_mode == 'custom':
            for w in custom_widgets:
                w.grid()
            for w in scrape_widgets:
                w.grid_remove()
            self.status_config_frame.pack(fill='x', pady=3, after=self.config_details_frame)
            self.index_frame.pack_forget()
        else:
            for w in custom_widgets:
                w.grid_remove()
            for w in scrape_widgets:
                w.grid()
            self.status_config_frame.pack_forget()
            self.index_frame.pack(fill='x', pady=3, after=self.config_details_frame)
            
    def _on_profile_selected(self, event=None):
        """Handle profile selection from dropdown"""
        key = self.scrape_profile_var.get().strip()
        if key:
            self._load_scrape_profile(key)
            
    def _load_scrape_profile(self, profile_key: str):
        """Load scrape profile from config.json"""
        selectors, idx = self.app.config_manager.load_scrape_profile(profile_key)
        # Convert Selector objects to dictionaries
        self.scraper_selectors = [s.to_dict() if hasattr(s, 'to_dict') else s for s in selectors]
        self.main_container_index = idx
        self.ConIndex_var.set(str(idx) if idx is not None else '')
        self.update_selector_list()
        self.status_label_var.set(f"✅ Loaded profile '{profile_key}'")
        
    def add_selector(self):
        """Add or update selector"""
        role = self.role_var.get().strip()
        tag = self.tag_var.get().strip()
        sel_type = self.type_var.get().strip()
        selector = self.selector_var.get().strip()
        notes = self.notes_var.get().strip()
        
        if not all([role, tag, sel_type, selector]):
            messagebox.showwarning("Missing Information",
                                  "Role, Tag, Type, and Selector are required!")
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
        """Update treeview with current selectors"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get the correct data source based on view mode
        data_source = self.selectors if self.view_mode == 'custom' else self.scraper_selectors
        
        if not data_source:
            # Show empty state but don't insert a placeholder row that can be selected
            # Just leave the tree empty
            return
            
        # Insert all selectors
        for selector in data_source:
            self.tree.insert('', 'end', values=(
                selector.get('role', ''),
                selector.get('tag', ''),
                selector.get('type', ''),
                selector.get('value', ''),
                selector.get('notes', '')
            ))
                
    def remove_selector(self):
        """Remove selected selector"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a selector")
            return
            
        item = self.tree.item(selected[0])
        values = item['values']
        if values[0] == "No selectors to display.":
            return
            
        role = values[0]
        selector_value = values[3]
        target_list = self.selectors if self.view_mode == 'custom' else self.scraper_selectors
        
        for i, selector in enumerate(target_list):
            if selector.get('role') == role and selector.get('value') == selector_value:
                target_list.pop(i)
                if self.editing_index == i and self.editing_view_mode == self.view_mode:
                    self.editing_index = -1
                break
                
        self.update_selector_list()
        self.status_label_var.set(f"🗑️ Removed selector: {role}")
        
    def preview_selector(self):
        """Preview selected selector"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a selector")
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
        
    def load_selector_to_fields(self, event=None):
        """Load selected selector into fields"""
        selected = self.tree.selection()
        if not selected:
            return
            
        item = self.tree.item(selected[0])
        values = item['values']
        
        if values[0] == "No selectors to display.":
            return
            
        data_source = self.selectors if self.view_mode == 'custom' else self.scraper_selectors
        
        for i, selector in enumerate(data_source):
            if selector.get('role') == values[0] and selector.get('value') == values[3]:
                self.editing_index = i
                self.editing_view_mode = self.view_mode
                
                self.role_var.set(selector.get('role', ''))
                self.tag_var.set(selector.get('tag', ''))
                self.type_var.set(selector.get('type', ''))
                self.selector_var.set(selector.get('value', ''))
                self.notes_var.set(selector.get('notes', ''))
                break
                
    def clear_selector_inputs(self):
        """Clear selector input fields"""
        self.role_var.set('')
        self.tag_var.set('div')
        self.type_var.set('')
        self.selector_var.set('')
        self.notes_var.set('')
        self.editing_index = -1
        
    def load_existing_config(self, event=None):
        """Load existing config from dropdown"""
        selected_name = self.name_var.get()
        config = self.app.config_manager.find_config(selected_name)
        if config:
            self._populate_form_from_config(config)
            self.status_label_var.set(f"✏️ Loaded '{selected_name}'")
            
    def _populate_form_from_config(self, config: Configuration):
        """Fill form from config object"""
        self.current_config = config
        self.name_var.set(config.name)
        self.url_var.set(config.base_url)
        self.desc_var.set(config.description or '')
        self.status_var.set(config.active)
        self.version_var.set(config.version)
        
        # Load custom selectors - convert to dict if needed
        self.selectors = []
        for s in config.custom_selectors:
            if hasattr(s, 'to_dict'):
                self.selectors.append(s.to_dict())
            elif isinstance(s, dict):
                self.selectors.append(s)
        
        # Load scraper selectors - convert to dict if needed
        self.scraper_selectors = []
        # Check if the config has the attribute and it's not empty
        if hasattr(config, 'custom_Scraper_selectors') and config.custom_Scraper_selectors:
            for s in config.custom_Scraper_selectors:  # Use the same attribute name
                if hasattr(s, 'to_dict'):
                    self.scraper_selectors.append(s.to_dict())
                elif isinstance(s, dict):
                    self.scraper_selectors.append(s)
        self.main_container_index = config.main_container_index
        self.ConIndex_var.set(str(config.main_container_index) if config.main_container_index is not None else '')
        
 
        self.view_mode = 'custom'
        if hasattr(self, 'toggle_view_button') and self.toggle_view_button:
            self.toggle_view_button.config(text="Switch to Scrape Selectors")
        if hasattr(self, 'view_badge') and self.view_badge:
            self.view_badge.config(text="Viewing: Custom Selectors", foreground='#27ae60')
        if hasattr(self, 'add_button') and self.add_button:
            self.add_button.config(text="➕ Add to Custom")
        
        self.editing_index = -1
        self.update_selector_list()
        self.update_status_display()
        self._refresh_fields_visibility()

        
    def load_config_for_editing(self, config: Configuration):
        """Load config for editing (called from view tab)"""
        self._populate_form_from_config(config)
        self.save_button.config(state='normal')
        self.update_button.config(state='normal')
        
    def clear_form(self):
        """Clear all form data"""
        if messagebox.askyesno("Clear Form", "Clear all form data?"):
            self.name_var.set('')
            self.url_var.set('')
            self.desc_var.set('')
            self.status_var.set(True)
            self.version_var.set('1.0')
            self.selectors = []
            self.scraper_selectors = []
            self.main_container_index = None
            self.ConIndex_var.set('')
            self.scrape_profile_var.set('')
            self.current_config = None
            self.view_mode = 'custom'
            self.editing_index = -1
            self.update_selector_list()
            self.clear_selector_inputs()
            self.update_status_display()
            self._refresh_fields_visibility()
            self.status_label_var.set("✅ Ready to create new configuration")
            
    def save_configuration(self):
        """Save configuration based on view mode"""
        if self.view_mode == 'custom':
            self._save_custom_configuration()
        else:
            self._save_scrape_configuration(is_update=False)
            
    def update_configuration(self):
        """Update configuration based on view mode"""
        if self.view_mode == 'custom':
            self._update_custom_configuration()
        else:
            self._save_scrape_configuration(is_update=True)
            
    def _save_custom_configuration(self):
        """Save custom configuration"""
        name = self.name_var.get().strip()
        url = self.url_var.get().strip()
        
        if not name or not url:
            messagebox.showwarning("Missing Info", "Name and URL are required!")
            return
        if not self.selectors:
            messagebox.showwarning("No Selectors", "Add at least one selector!")
            return
            
        # Check for existing
        existing = self.app.config_manager.find_config(name)
        if existing:
            if not messagebox.askyesno("Name Exists", f"'{name}' exists. Update?"):
                return
            self._populate_form_from_config(existing)
            return
            
        # Create and save
        config = Configuration(
            name=name,
            base_url=url,
            active=self.status_var.get(),
            version=self.version_var.get(),
            description=self.desc_var.get().strip(),
            custom_selectors=[Selector.from_dict(s) for s in self.selectors],
            main_container_index=self.main_container_index
        )
        
        if self.app.config_manager.save_config(config):
            self.current_config = config
            self.status_label_var.set(f"✅ '{name}' saved")
            messagebox.showinfo("Success", f"Configuration '{name}' saved!")
            self.refresh_combos()
            
    def _update_custom_configuration(self):
        """Update existing custom configuration"""
        name = self.name_var.get().strip()
        
        if not self.current_config:
            self.current_config = self.app.config_manager.find_config(name)
            if not self.current_config:
                messagebox.showwarning("Not Found", f"No config named '{name}'")
                return
                
        # Update config
        self.current_config.name = name
        self.current_config.base_url = self.url_var.get().strip()
        self.current_config.description = self.desc_var.get().strip()
        self.current_config.active = self.status_var.get()
        self.current_config.version = self.version_var.get()
        self.current_config.custom_selectors = [Selector.from_dict(s) for s in self.selectors]
        self.current_config.main_container_index = self.main_container_index
        self.current_config.update_metadata()
        
        if self.app.config_manager.save_config(self.current_config, is_update=True):
            self.status_label_var.set(f"✅ '{name}' updated")
            messagebox.showinfo("Success", f"Configuration '{name}' updated!")
            self.refresh_combos()
            
    def _save_scrape_configuration(self, is_update: bool):
        """Save scrape configuration to config.json"""
        if not self.scraper_selectors:
            messagebox.showwarning("No Selectors", "Add at least one scrape selector!")
            return
            
        profile_key = self.scrape_profile_var.get().strip()
        if not profile_key:
            profile_key = f"scrape_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.scrape_profile_var.set(profile_key)
            
        selectors = [Selector.from_dict(s) for s in self.scraper_selectors]
        
        if self.app.config_manager.save_scrape_config(profile_key, selectors, self.main_container_index):
            self.status_label_var.set(f"✅ Profile '{profile_key}' saved")
            messagebox.showinfo("Success", f"Scrape profile '{profile_key}' saved!")
            self.refresh_profile_combo()
            
    def refresh_combos(self):
        """Refresh combobox values"""
        if self._widget_name:
            self._widget_name['values'] = [c.name for c in self.app.config_manager.configs if c.name]
        if self._widget_url:
            self._widget_url['values'] = list(set(c.base_url for c in self.app.config_manager.configs if c.base_url))
        self.refresh_profile_combo()
        
    def refresh_profile_combo(self):
        """Refresh profile combobox"""
        if self._profile_combo:
            self._profile_combo['values'] = list(self.load_scrape_configs().keys())
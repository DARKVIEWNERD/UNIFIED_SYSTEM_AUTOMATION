"""View configurations tab"""
import tkinter as tk
from tkinter import ttk, messagebox

from tabs.base import Base


class ViewTab(Base):
    """View configurations tab"""
    
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title = "👁️ View Configurations"
        self.config_tree = None
        self.summary_var = tk.StringVar(value="📊 No configurations loaded")
        
    def build(self):
        """Build the view tab"""
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill='x', pady=5)
        ttk.Label(header_frame, text="📋 Existing Configurations",
                 style='Header.TLabel').pack()
        ttk.Label(header_frame, text="Double-click any configuration to edit",
                 style='SubHeader.TLabel').pack()
        
        # Tree frame
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create treeview
        self.build_treeview(tree_frame)
        
        # Button frame
        self.build_button_frame()
        
        # Summary
        summary_frame = ttk.Frame(self.frame, relief='sunken', padding=3)
        summary_frame.pack(fill='x', side='bottom', pady=3)
        ttk.Label(summary_frame, textvariable=self.summary_var,
                 font=('Arial', 8)).pack(side='left')
        
        # Load data
        self.load_configs_into_tree()
        
    def build_treeview(self, parent):
        """Build the treeview"""
        columns = ('name', 'url', 'status', 'selectors', 'created')
        self.config_tree = ttk.Treeview(parent, columns=columns,
                                        show='headings', height=12)
        
        column_configs = [
            ('name', 'Configuration Name', 180),
            ('url', 'URL', 220),
            ('status', 'Status', 80),
            ('selectors', 'Custom Sel.', 85),
            ('created', 'Created', 130)
        ]
        
        for col, heading, width in column_configs:
            self.config_tree.heading(col, text=heading)
            self.config_tree.column(col, width=width, minwidth=50)
            
        # Scrollbar
        vsb = ttk.Scrollbar(parent, orient='vertical', command=self.config_tree.yview)
        self.config_tree.configure(yscrollcommand=vsb.set)
        self.config_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        # Bind double-click
        self.config_tree.bind('<Double-Button-1>', self.load_for_editing)
        
    def build_button_frame(self):
        """Build action buttons"""
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        button_container = ttk.Frame(btn_frame)
        button_container.pack(anchor='center')
        
        ttk.Button(button_container, text="✏️ Edit Selected",
                  command=self.edit_selected_config,
                  style='Action.TButton', width=18).pack(side='left', padx=3)
        ttk.Button(button_container, text="🔄 Toggle Status",
                  command=self.toggle_config_status,
                  style='Action.TButton', width=18).pack(side='left', padx=3)
        ttk.Button(button_container, text="🗑️ Delete Selected",
                  command=self.delete_configuration,
                  style='Danger.TButton', width=18).pack(side='left', padx=3)
        ttk.Button(button_container, text="🔄 Refresh",
                  command=self.refresh_view,
                  style='Action.TButton', width=18).pack(side='left', padx=3)
                  
    def load_configs_into_tree(self):
        """Load configurations into the tree"""
        # Clear existing
        for item in self.config_tree.get_children():
            self.config_tree.delete(item)
            
        # Add configs
        for config in self.app.config_manager.configs:
            status = "✅ Active" if config.active else "❌ Inactive"
            
            self.config_tree.insert('', 'end', values=(
                config.name,
                config.base_url,
                status,
                len(config.custom_selectors),
                config.metadata.get('created_at', 'Unknown')
            ))
            
        # Update summary
        total = len(self.app.config_manager.configs)
        active = sum(1 for c in self.app.config_manager.configs if c.active)
        self.summary_var.set(
            f"📊 Total: {total} configurations | "
            f"✅ Active: {active} | "
            f"❌ Inactive: {total - active}"
        )
        
    def edit_selected_config(self):
        """Edit selected configuration"""
        selected = self.config_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a configuration")
            return
        self.load_for_editing()
        
    def load_for_editing(self, event=None):
        """Load selected config for editing"""
        selected = self.config_tree.selection()
        if not selected:
            return
            
        item = self.config_tree.item(selected[0])
        config_name = item['values'][0]
        
        config = self.app.config_manager.find_config(config_name)
        if config:
            # Switch to config tab and load
            config_tab = self.app.tabs['config']
            config_tab.load_config_for_editing(config)
            self.app.notebook.select(1)
            
    def toggle_config_status(self):
        """Toggle active status of selected configuration"""
        selected = self.config_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a configuration")
            return
            
        item = self.config_tree.item(selected[0])
        config_name = item['values'][0]
        
        new_status = self.app.config_manager.toggle_config_status(config_name)
        if new_status is not None:
            self.load_configs_into_tree()
            status_text = "activated" if new_status else "deactivated"
            messagebox.showinfo("Success", f"Configuration '{config_name}' {status_text}!")
            
    def delete_configuration(self):
        """Delete selected configuration"""
        selected = self.config_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a configuration")
            return
            
        item = self.config_tree.item(selected[0])
        config_name = item['values'][0]
        
        if not messagebox.askyesno("Confirm Delete",
                                  f"Delete '{config_name}'?"):
            return
            
        if self.app.config_manager.delete_config(config_name):
            self.load_configs_into_tree()
            messagebox.showinfo("Success", f"Configuration '{config_name}' deleted!")
            
    def refresh_view(self):
        """Refresh the view"""
        self.app.config_manager.load_configs()
        self.load_configs_into_tree()
        messagebox.showinfo("Refreshed", "View updated with latest data!")
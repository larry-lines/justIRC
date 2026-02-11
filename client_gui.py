"""
JustIRC GUI Client - Secure IRC Client with GUI
Uses Tkinter for cross-platform GUI
"""

import asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import json
import os
import time
from datetime import datetime
from typing import Optional
from protocol import Protocol, MessageType
from crypto_layer import CryptoLayer
from image_transfer import ImageTransfer
from config_manager import ConfigManager


class IRCClientGUI:
    """GUI IRC Client with E2E encryption"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🛡️ JustIRC - Secure Encrypted IRC")
        self.root.geometry("1100x700")
        
        # Load configuration
        self.config = ConfigManager()
        
        # Client state
        self.connected = False
        self.user_id: Optional[str] = None
        self.nickname: Optional[str] = None
        self.crypto = CryptoLayer()
        self.image_transfer = ImageTransfer(self.crypto)
        
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
        self.users = {}  # All users: user_id -> {nickname, public_key}
        self.channel_users = {}  # Users in current channel: channel -> set(user_ids)
        self.channel_operators = {}  # Channel operators: channel -> set(operator_user_ids)
        self.channel_mods = {}  # Channel mods: channel -> set(mod_user_ids)
        self.channel_owners = {}  # Channel owners: channel -> owner_user_id
        self.protected_channels = set()  # Channels that are password-protected
        self.current_channel: Optional[str] = None
        self.current_recipient: Optional[str] = None  # For private messages
        self.joined_channels = set()
        
        # Pending image transfers waiting for user acceptance
        self.pending_images = {}  # image_id -> {from_id, metadata, chunks_data}
        
        # Event loop
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
        
        self.setup_window_icon()
        self.setup_ui()
        self.apply_theme()
    
    def setup_window_icon(self):
        """Set window icon from PNG file"""
        try:
            import os
            import sys
            
            # Get base path - different for frozen (PyInstaller) vs development
            if getattr(sys, 'frozen', False):
                # Running from PyInstaller bundle
                base_path = sys._MEIPASS
            else:
                # Running in development
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            # Try multiple paths to find the logo
            possible_paths = [
                os.path.join(base_path, "JUSTIRC-logo.png"),  # Bundled location
                "JUSTIRC-logo.png",  # Current directory
                os.path.join(os.getcwd(), "JUSTIRC-logo.png")  # Working directory
            ]
            
            logo_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    logo_path = path
                    break
            
            if logo_path:
                # Use native Tkinter PhotoImage (supports PNG directly)
                photo = tk.PhotoImage(file=logo_path)
                self.root.iconphoto(True, photo)
                # Keep reference to prevent garbage collection
                self._icon_photo = photo
            else:
                print("Warning: JUSTIRC-logo.png not found in any expected location")
        except Exception as e:
            print(f"Warning: Could not load window icon: {e}")
            pass
    
    def setup_ui(self):
        """Setup the user interface with modern design"""
        # Configure styles
        style = ttk.Style()
        style.theme_use('clam')  # Base theme for better customization
        
        # Menu bar (Keep as native menu)
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Settings", command=self.show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Help menu  
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Commands", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Main Container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Top Bar (Header & Connection)
        top_bar = ttk.Frame(main_container, style='Header.TFrame')
        top_bar.pack(fill=tk.X, padx=0, pady=0)
        
        # Logo/Title area
        title_frame = ttk.Frame(top_bar, style='Header.TFrame')
        title_frame.pack(side=tk.LEFT, padx=15, pady=10)
        ttk.Label(title_frame, text="🛡️ JustIRC", font=('Segoe UI', 14, 'bold'), style='Header.TLabel').pack(side=tk.LEFT)
        
        # Connection Controls - Modernized (Right aligned)
        conn_frame = ttk.Frame(top_bar, style='Header.TFrame')
        conn_frame.pack(side=tk.RIGHT, padx=15, pady=10)
        
        # Load saved server settings
        last_server = self.config.get("server", "last_server", default="localhost")
        last_port = self.config.get("server", "last_port", default=6667)
        last_nick = self.config.get("server", "last_nickname", default="")

        # Inputs with labels
        for label, val, width in [("Server:", last_server, 15), ("Port:", last_port, 6), ("Nick:", last_nick, 12)]:
            f = ttk.Frame(conn_frame, style='Header.TFrame')
            f.pack(side=tk.LEFT, padx=5)
            ttk.Label(f, text=label, font=('Segoe UI', 8), style='Header.TLabel').pack(anchor=tk.W)
            entry = ttk.Entry(f, width=width)
            entry.insert(0, str(val))
            entry.pack()
            if label == "Server:": self.server_entry = entry
            elif label == "Port:": self.port_entry = entry
            elif label == "Nick:": self.nick_entry = entry

        # Connect Button
        btn_frame = ttk.Frame(conn_frame, style='Header.TFrame', padding=(5, 12, 0, 0))
        btn_frame.pack(side=tk.LEFT)
        self.connect_btn = ttk.Button(btn_frame, text="Connect", command=self.connect, width=10, style='Action.TButton')
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect", command=self.disconnect, state=tk.DISABLED, width=10)
        self.disconnect_btn.pack(side=tk.LEFT)

        # Main Content Area
        self.content_frame = ttk.Frame(main_container)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        main_paned = ttk.PanedWindow(self.content_frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # LEFT PANEL: Channels
        left_panel = ttk.Frame(main_paned, width=200)
        main_paned.add(left_panel, weight=0)
        
        # Section Header
        ttk.Label(left_panel, text="CHANNELS", font=('Segoe UI', 9, 'bold'), foreground='#888888').pack(anchor=tk.W, pady=(0, 5))
        
        channel_list_frame = ttk.Frame(left_panel)
        channel_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.channel_scrollbar = ttk.Scrollbar(channel_list_frame, orient="vertical", style="Vertical.TScrollbar")
        self.channel_list = tk.Listbox(
            channel_list_frame, 
            height=10, 
            bd=0, 
            highlightthickness=0, # Modern flat look
            activestyle='none',
            font=('Segoe UI', 10),
            yscrollcommand=self.channel_scrollbar.set
        )
        self.channel_scrollbar.config(command=self.channel_list.yview)
        
        self.channel_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.channel_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.channel_list.bind('<<ListboxSelect>>', self.on_channel_select)
        
        # Channel Controls
        c_btn_frame = ttk.Frame(left_panel)
        c_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(c_btn_frame, text="+ Join", command=self.join_channel_dialog, width=8).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(c_btn_frame, text="- Leave", command=self.leave_channel, width=8).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # CENTER PANEL: Chat
        center_panel = ttk.Frame(main_paned)
        main_paned.add(center_panel, weight=3)
        
        # Context Header
        self.context_label = ttk.Label(
            center_panel,
            text="Welcome to JustIRC",
            font=('Segoe UI', 12, 'bold')
        )
        self.context_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Chat Display
        font_family = self.config.get("font", "family", default="Consolas")
        font_size = self.config.get("font", "chat_size", default=10)
        
        frame_chat_border = ttk.Frame(center_panel, style='Border.TFrame') # Manual border if needed
        frame_chat_border.pack(fill=tk.BOTH, expand=True)
        
        chat_frame = ttk.Frame(frame_chat_border)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        self.chat_scrollbar = ttk.Scrollbar(chat_frame, orient="vertical", style="Vertical.TScrollbar")
        self.chat_display = tk.Text(
            chat_frame, 
            wrap=tk.WORD, 
            state=tk.DISABLED, 
            font=(font_family, font_size),
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            yscrollcommand=self.chat_scrollbar.set
        )
        self.chat_scrollbar.config(command=self.chat_display.yview)
        
        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Message Input Area
        input_container = ttk.Frame(center_panel)
        input_container.pack(fill=tk.X, pady=(10, 0))
        
        self.message_entry = ttk.Entry(input_container, font=('Segoe UI', 11))
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10), ipady=5)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        self.message_entry.bind('<Tab>', self.autocomplete_nickname)
        
        send_btn = ttk.Button(input_container, text="SEND", command=self.send_message, style='Action.TButton')
        send_btn.pack(side=tk.LEFT)
        img_btn = ttk.Button(input_container, text="📎", command=self.send_image_dialog, width=3)
        img_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # RIGHT PANEL: Users
        right_panel = ttk.Frame(main_paned, width=200)
        main_paned.add(right_panel, weight=0)
        
        # Channel Users
        ttk.Label(right_panel, text="MEMBERS", font=('Segoe UI', 9, 'bold'), foreground='#888888').pack(anchor=tk.W, pady=(0, 5))
        
        channel_user_frame = ttk.Frame(right_panel)
        channel_user_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.channel_user_scrollbar = ttk.Scrollbar(channel_user_frame, orient="vertical", style="Vertical.TScrollbar")
        self.channel_user_list = tk.Listbox(
            channel_user_frame,
            height=15,
            bd=0,
            highlightthickness=0,
            activestyle='none',
            font=('Segoe UI', 10),
            yscrollcommand=self.channel_user_scrollbar.set
        )
        self.channel_user_scrollbar.config(command=self.channel_user_list.yview)
        
        self.channel_user_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.channel_user_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.channel_user_list.bind('<Double-Button-1>', self.on_user_double_click)
        self.channel_user_list.bind('<Button-3>', self.show_user_context_menu)
        
        # All Users
        ttk.Label(right_panel, text="ALL USERS", font=('Segoe UI', 9, 'bold'), foreground='#888888').pack(anchor=tk.W, pady=(0, 5))
        
        user_list_frame = ttk.Frame(right_panel)
        user_list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.user_scrollbar = ttk.Scrollbar(user_list_frame, orient="vertical", style="Vertical.TScrollbar")
        self.user_list = tk.Listbox(
            user_list_frame,
            height=8,
            bd=0,
            highlightthickness=0,
            activestyle='none',
            font=('Segoe UI', 10),
            yscrollcommand=self.user_scrollbar.set
        )
        self.user_scrollbar.config(command=self.user_list.yview)
        
        self.user_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.user_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.user_list.bind('<Double-Button-1>', self.on_user_double_click)

        # Status Bar
        self.status_var = tk.StringVar(value="Disconnected")
        status_bar = ttk.Label(
            self.root, 
            textvariable=self.status_var, 
            relief=tk.FLAT, 
            anchor=tk.W,
            font=('Segoe UI', 9),
            padding=(10, 5)
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def apply_theme(self):
        """Apply color theme to widgets"""
        colors = self.config.get_theme_colors()
        
        # Configure root and main styles
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass # Fallback if clam not available
        
        # Colors
        bg = colors["bg"]
        fg = colors["fg"]
        accent = colors["accent"]
        input_bg = colors["input_bg"]
        input_fg = colors["input_fg"]
        border = colors.get("border", "#444")
        
        self.root.config(bg=bg)

        # --------------------------------------------------------------------
        # MENU BAR STYLING
        # --------------------------------------------------------------------
        # For new menus (dialogs etc)
        self.root.option_add('*Menu.background', bg)
        self.root.option_add('*Menu.foreground', fg)
        self.root.option_add('*Menu.activeBackground', accent)
        self.root.option_add('*Menu.activeForeground', '#ffffff')
        self.root.option_add('*Menu.selectColor', accent)
        
        # Update existing main menu if it exists
        if hasattr(self, 'menubar'):
            try:
                # Top-level bar
                self.menubar.config(bg=bg, fg=fg, activebackground=accent, activeforeground='#ffffff')
                # Children menus (File, Edit, etc.)
                for child in self.menubar.winfo_children():
                    if isinstance(child, tk.Menu):
                        child.config(bg=bg, fg=fg, activebackground=accent, activeforeground='#ffffff')
            except Exception as e:
                print(f"Menu styling error: {e}")
        
        # Configure standard widgets
        for widget in [self.channel_list, self.user_list, self.channel_user_list]:
            widget.config(
                bg=input_bg,
                fg=input_fg,
                selectbackground=accent,
                selectforeground='#ffffff'
            )
            
        self.chat_display.config(
            bg=colors["chat_bg"],
            fg=colors["chat_fg"],
            insertbackground=fg
        )
        
        # Configure text tags
        self.chat_display.tag_config("timestamp", foreground=colors["system"], font=('Consolas', 9))
        self.chat_display.tag_config("info", foreground=colors["info"])
        self.chat_display.tag_config("error", foreground=colors["error"])
        self.chat_display.tag_config("success", foreground=colors["success"])
        self.chat_display.tag_config("pm", foreground=colors["pm"])
        self.chat_display.tag_config("channel", foreground=colors["channel"]) # Default channel text
        self.chat_display.tag_config("system", foreground=colors["system"])
        self.chat_display.tag_config("action", foreground=colors["action"], font=('Consolas', 10, 'italic'))
        self.chat_display.tag_config("highlight", background=colors["highlight"])
        self.chat_display.tag_config("self_msg", foreground=fg) # Regular msg color
        
        # Configure dynamic tags for name colors
        # (This is done dynamically in log method, but base config here)

        # TTK Styles
        style.configure('.', background=bg, foreground=fg, font=('Segoe UI', 10))
        style.configure('TFrame', background=bg)
        style.configure('TLabel', background=bg, foreground=fg)
        style.configure('TButton', background=input_bg, foreground=fg, borderwidth=1, relief="flat")
        style.map('TButton',
                 background=[('active', accent), ('pressed', accent)],
                 foreground=[('active', '#ffffff'), ('pressed', '#ffffff')])
        
        # Configure Scrollbar
        scrollbar_bg = colors.get("scrollbar_bg", input_bg)
        scrollbar_fg = colors.get("scrollbar_fg", accent)
        
        try:
            style.configure("Vertical.TScrollbar",
                gripcount=0,
                background=scrollbar_bg,
                darkcolor=bg,
                lightcolor=bg,
                troughcolor=bg,
                bordercolor=bg,
                arrowcolor=fg
            )
            style.map("Vertical.TScrollbar",
                background=[("active", scrollbar_fg), ("!disabled", scrollbar_bg)],
                arrowcolor=[("active", accent)]
            )
        except:
            pass
        
        style.configure('TEntry', fieldbackground=input_bg, foreground=input_fg, bordercolor=border, relief="flat", padding=5)

        # Configure Notebook
        style.configure('TNotebook', background=bg, borderwidth=0)
        style.configure('TNotebook.Tab', 
            background=colors["chat_bg"], 
            foreground=fg, 
            padding=[10, 5],
            borderwidth=0
        )
        style.map('TNotebook.Tab',
            background=[('selected', accent), ('active', colors['highlight'])],
            foreground=[('selected', '#ffffff'), ('active', fg)]
        )
        
        # Custom styles
        style.configure('Header.TFrame', background=colors.get("chat_bg", bg))
        style.configure('Header.TLabel', background=colors.get("chat_bg", bg), foreground=fg)
        
        style.configure('Action.TButton', background=accent, foreground='#ffffff', font=('Segoe UI', 10, 'bold'))
        style.map('Action.TButton', background=[('active', colors['highlight'])])
        
        style.configure('Border.TFrame', background=border, borderwidth=1)
        
        style.configure('TPanedwindow', background=bg)
    
    def show_settings(self):
        """Show settings dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Theme tab
        theme_frame = ttk.Frame(notebook, padding=20)
        notebook.add(theme_frame, text="Theme")
        
        ttk.Label(theme_frame, text="Select Theme:", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        current_theme = self.config.get("theme", default="dark")
        theme_var = tk.StringVar(value=current_theme)
        
        theme_descriptions = {
            "dark": "Dark - Classic dark mode",
            "light": "Light - Bright clean interface",
            "classic": "Classic - Traditional IRC look",
            "cyber": "🛡️ Cyber - Security-themed",
            "custom": "🎨 Custom - User defined colors"
        }
        
        for theme_name in ["dark", "light", "classic", "cyber", "custom"]:
            ttk.Radiobutton(
                theme_frame,
                text=theme_descriptions[theme_name],
                variable=theme_var,
                value=theme_name
            ).pack(anchor=tk.W, pady=5)
            
        # Custom Colors Button (Only shown/enabled if custom selected)
        def convert_color(prompt_title, initial_color):
            try:
                from tkinter.colorchooser import askcolor
                color = askcolor(color=initial_color, title=prompt_title)
                return color[1] if color[1] else initial_color
            except:
                return initial_color

        def open_custom_theme_editor():
            if theme_var.get() != 'custom':
                messagebox.showinfo("Info", "Select 'Custom' theme first to edit colors.")
                return
                
            editor = tk.Toplevel(dialog)
            editor.title("Custom Theme Editor")
            editor.geometry("400x500")
            editor.config(bg=colors['bg'])
            
            # Load current custom colors
            current_custom = self.config.get("colors", "custom")
            if not current_custom:
                current_custom = self.config.get("colors", "dark").copy() # fallback
            
            # Helper to create color picker row
            def create_picker(parent, name, key):
                f = ttk.Frame(parent)
                f.pack(fill=tk.X, pady=2)
                ttk.Label(f, text=name, width=20).pack(side=tk.LEFT)
                
                # Color preview/button
                btn = tk.Button(f, bg=current_custom.get(key, '#000000'), width=10)
                
                def pick():
                    new_c = convert_color(f"Pick {name}", current_custom.get(key, '#000000'))
                    current_custom[key] = new_c
                    btn.config(bg=new_c)
                    
                btn.config(command=pick)
                btn.pack(side=tk.RIGHT)
                
            scroll_frame = ttk.Frame(editor)
            scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            keys_to_edit = [
                ("Background", "bg"), ("Foreground", "fg"),
                ("Chat BG", "chat_bg"), ("Chat FG", "chat_fg"),
                ("Accent", "accent"), ("Input BG", "input_bg"),
                ("Info Text", "info"), ("Error Text", "error"),
                ("Success Text", "success")
            ]
            
            for label, key in keys_to_edit:
                create_picker(scroll_frame, label, key)
                
            def save_custom():
                self.config.set("colors", "custom", value=current_custom)
                messagebox.showinfo("Saved", "Custom colors saved. Apply theme to see changes.")
                editor.destroy()
                
            ttk.Button(editor, text="Save Custom Colors", command=save_custom).pack(pady=10)

        editor_btn = ttk.Button(theme_frame, text="Customize Colors...", command=open_custom_theme_editor)
        editor_btn.pack(anchor=tk.W, pady=10)
        
        # Font tab
        font_frame = ttk.Frame(notebook, padding=20)
        notebook.add(font_frame, text="Font")
        
        ttk.Label(font_frame, text="Font Family:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        font_family_var = tk.StringVar(value=self.config.get("font", "family", default="Consolas"))
        font_entry = ttk.Entry(font_frame, textvariable=font_family_var, width=30)
        font_entry.pack(anchor=tk.W, pady=(0, 15))
        
        ttk.Label(font_frame, text="Chat Font Size:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        font_size_var = tk.IntVar(value=self.config.get("font", "chat_size", default=10))
        ttk.Scale(
            font_frame,
            from_=8,
            to=16,
            variable=font_size_var,
            orient=tk.HORIZONTAL,
            length=200
        ).pack(anchor=tk.W)
        
        # UI Options tab
        ui_frame = ttk.Frame(notebook, padding=20)
        notebook.add(ui_frame, text="UI Options")
        
        timestamps_var = tk.BooleanVar(value=self.config.get("ui", "show_timestamps", default=True))
        join_leave_var = tk.BooleanVar(value=self.config.get("ui", "show_join_leave", default=True))
        
        ttk.Checkbutton(ui_frame, text="Show timestamps", variable=timestamps_var).pack(anchor=tk.W, pady=5)
        ttk.Checkbutton(ui_frame, text="Show join/leave messages", variable=join_leave_var).pack(anchor=tk.W, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_settings():
            self.config.set("theme", value=theme_var.get())
            self.config.set("font", "family", value=font_family_var.get())
            self.config.set("font", "chat_size", value=font_size_var.get())
            self.config.set("ui", "show_timestamps", value=timestamps_var.get())
            self.config.set("ui", "show_join_leave", value=join_leave_var.get())
            self.apply_theme()
            
            # Update font
            font_family = font_family_var.get()
            font_size = font_size_var.get()
            self.chat_display.config(font=(font_family, font_size))
            
            dialog.destroy()
            dialog.destroy()
            messagebox.showinfo("Settings", "Settings saved! Some changes may require restart.")
        
        ttk.Button(btn_frame, text="Save", command=save_settings, width=12).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.RIGHT)
    
    def show_help(self):
        """Show help dialog with command list"""
        help_text = """IRC Commands:
        
🔹 Basic Commands:
  /join #channel [join_pwd] [creator_pwd]  - Join/create channel
    • For new channels: creator_pwd required (4+ chars) to regain operator later
    • For existing: use creator_pwd to regain operator status  
    • If only one password: used for both join and creator access
    • Channel names automatically converted to lowercase
    • Spaces in names replaced with hyphens
  /leave [#channel]          - Leave current or specified channel
  /msg user message          - Send private message
  /nick newnick              - Change nickname (future)
  /quit                      - Disconnect and quit
  
🔹 Actions & Formatting:
  /me action                 - Send action (*user does something*)
  
🔹 Channel Management:
  Mods - Can kick users
  Operators - Can kick, ban, give mod status
  Owners - All operator powers + give operator status + transfer ownership
  
  /op user                   - Grant operator (owner only, requires setting op password)
  /unop user                 - Remove operator status (owner only)
  /mod user                  - Grant mod status (operators+)
  /unmod user                - Remove mod status (operators+)
  /kick user [reason]        - Kick user from channel (mods+)
  /ban user [reason]         - Ban user from channel (operators+)
  /unban user                - Unban user from channel (operators+)
  /kickban user [reason]     - Kick and ban user (operators+)
  /transfer user             - Transfer channel ownership (owner only, target must be op)
  /topic new topic           - Set channel topic (operators+)
  
🔹 Information:
  /users                     - List all online users
  /whois user                - Get user information and channels
  /list                      - List all available channels (🔒 = password-protected)
  
🔹 File Transfer:
  /image user path           - Send encrypted image
  
💡 Tip: Double-click a user to start private chat
💡 Tip: Right-click a channel user for quick actions
💡 Tip: Press Tab to autocomplete nicknames
💡 Tip: Channel messages are filtered - switch channels to see different conversations
💡 Tip: Operators need a password - set it when granted op, provide it when rejoining
"""
        
        dialog = tk.Toplevel(self.root)
        dialog.title("IRC Commands Help")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Consolas', 10),
                                         bg=colors['chat_bg'], fg=colors['chat_fg'])
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert('1.0', help_text)
        text.config(state=tk.DISABLED)
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def show_about(self):
        """Show about dialog with logo"""
        dialog = tk.Toplevel(self.root)
        dialog.title("About JustIRC")
        dialog.geometry("450x550")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Get theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Create logo area
        logo_frame = tk.Frame(dialog, bg=colors['bg'], height=120)
        logo_frame.pack(fill=tk.X, pady=20)
        
        # Create a simple shield logo
        try:
            canvas = tk.Canvas(logo_frame, width=100, height=100, 
                             bg=colors['bg'], highlightthickness=0)
            canvas.pack()
            
            # Draw cyber shield logo
            # Hexagon/shield shape
            points = [
                50, 10,   # Top
                80, 30,   # Top right
                80, 70,   # Bottom right
                50, 90,   # Bottom
                20, 70,   # Bottom left
                20, 30    # Top left
            ]
            
            # Gradient effect with multiple polygons
            canvas.create_polygon(points, fill='#2196F3', outline='#66BB6A', width=3)
            
            # Inner design - circuit-like
            canvas.create_oval(30, 30, 70, 70, outline='#4CAF50', width=2)
            canvas.create_line(50, 20, 50, 40, fill='#76FF03', width=2)
            canvas.create_line(50, 60, 50, 80, fill='#76FF03', width=2)
            canvas.create_line(30, 50, 40, 50, fill='#76FF03', width=2)
            canvas.create_line(60, 50, 70, 50, fill='#76FF03', width=2)
            
            # Center "C"
            canvas.create_arc(40, 40, 60, 60, start=45, extent=270,
                            outline='#66BB6A', width=3, style=tk.ARC)
        except:
            pass
        
        # App title
        title_label = tk.Label(
            dialog,
            text="🛡️ JustIRC",
            font=('Arial', 24, 'bold'),
            bg=colors['bg'],
            fg=colors['accent']
        )
        title_label.pack(pady=(0, 10))
        
        subtitle_label = tk.Label(
            dialog,
            text="Secure Encrypted IRC",
            font=('Arial', 12),
            bg=colors['bg'],
            fg=colors['fg']
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Info frame
        info_frame = tk.Frame(dialog, bg=colors['chat_bg'], relief=tk.RIDGE, borderwidth=2)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        info_text = (
            "Version 1.0.1\n\n"
            "🔐 End-to-End Encrypted IRC Client\n\n"
            "Features:\n"
            "  • X25519 ECDH key exchange\n"
            "  • ChaCha20-Poly1305 AEAD encryption\n"
            "  • Zero-knowledge routing server\n"
            "  • Secure image transfer\n"
            "  • Password-protected channels\n"
            "  • Channel operators\n"
            "  • Modern themeable UI\n\n"
            "🔒 Your messages are encrypted end-to-end.\n"
            "The server cannot decrypt your communications!"
        )
        
        info_label = tk.Label(
            info_frame,
            text=info_text,
            justify=tk.LEFT,
            font=('Consolas', 10),
            bg=colors['chat_bg'],
            fg=colors['chat_fg'],
            padx=20,
            pady=20
        )
        info_label.pack()
        
        # Close button
        close_btn = tk.Button(
            dialog,
            text="Close",
            command=dialog.destroy,
            font=('Arial', 10),
            bg=colors['accent'],
            fg='white',
            padx=30,
            pady=5
        )
        close_btn.pack(pady=20)
    
    def autocomplete_nickname(self, event):
        """Autocomplete nickname with Tab key"""
        text = self.message_entry.get()
        if not text:
            return "break"
        
        # Get last word
        words = text.split()
        if not words:
            return "break"
        
        partial = words[-1].lstrip('@')
        
        # Find matching nicknames
        matches = [
            info['nickname'] for uid, info in self.users.items()
            if info['nickname'].lower().startswith(partial.lower())
        ]
        
        if matches:
            # Replace last word with match
            words[-1] = matches[0]
            self.message_entry.delete(0, tk.END)
            self.message_entry.insert(0, ' '.join(words))
        
        return "break"
    
    def show_user_context_menu(self, event):
        """Show context menu when right-clicking a channel user"""
        if not self.current_channel:
            return
        
        # Get selected user
        selection = self.channel_user_list.curselection()
        if not selection:
            return
            
        # Identify user from list (strip symbol)
        display_name = self.channel_user_list.get(selection[0])
        # Simple split by first space to remove symbol
        parts = display_name.split(' ', 1)
        nickname = parts[1] if len(parts) > 1 else display_name
        
        # Create context menu
        menu = tk.Menu(self.root, tearoff=0)
        
        # Don't allow PM to self
        if nickname != self.nickname:
            menu.add_command(label=f"Private Message to {nickname}", command=lambda: self.start_pm(nickname))
            menu.add_command(label=f"Send Image to {nickname}", command=lambda: self.send_image_to_user(nickname))
            menu.add_separator()
        
        menu.add_command(label=f"Grant Operator to {nickname}", command=lambda: self.quick_op_user(nickname))
        
        # Add kick option for operators only (check if current user is op)
        if self.current_channel and self.user_id in self.channel_operators.get(self.current_channel, set()):
            if nickname != self.nickname:
                menu.add_command(label=f"Kick {nickname}", command=lambda: self.kick_user_dialog(nickname))
        
        # Show menu
        menu.post(event.x_root, event.y_root)
    
    def start_pm(self, nickname):
        """Start private message with user"""
        self.current_recipient = nickname
        self.current_channel = None
        self.update_context_label()
        self.message_entry.focus()
    
    def send_image_to_user(self, nickname):
        """Open image dialog for specific user"""
        filename = filedialog.askopenfilename(
            title=f"Send image to {nickname}",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")]
        )
        if filename:
            asyncio.run_coroutine_threadsafe(
                self._send_image(nickname, filename),
                self.loop
            )
    
    def quick_op_user(self, nickname):
        """Quick op user with saved password"""
        # For now, just open the op dialog
        # In future, could save password securely
        self.op_user_dialog_for_user(nickname)
    
    def op_user_dialog_for_user(self, target_nickname):
        """Show op dialog for specific user - requires operator password"""
        if not self.connected or not self.current_channel:
            return
        
        # Create dialog to get operator password for the new operator
        dialog = tk.Toplevel(self.root)
        dialog.title("Grant Operator")
        dialog.geometry("400x180")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        ttk.Label(dialog, text=f"Grant operator status to {target_nickname}", font=('Arial', 10, 'bold')).pack(pady=15)
        
        ttk.Label(dialog, text="Set operator password for user (4+ chars):").pack(anchor=tk.W, padx=20)
        password_entry = ttk.Entry(dialog, width=40, show='*')
        password_entry.pack(padx=20, fill=tk.X, pady=5)
        password_entry.focus()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)
        
        def grant():
            password = password_entry.get().strip()
            if len(password) < 4:
                messagebox.showerror("Error", "Operator password must be at least 4 characters")
                return
            dialog.destroy()
            asyncio.run_coroutine_threadsafe(
                self._op_user(target_nickname, password),
                self.loop
            )
        
        ttk.Button(btn_frame, text="Grant", command=grant, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT)
        
        # Bind enter key
        password_entry.bind('<Return>', lambda e: grant())
    
    def _prompt_op_password(self, channel: str, is_new: bool):
        """Prompt user for operator password"""
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Operator Password Required")
        dialog.geometry("400x180")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        if is_new:
            prompt_text = f"Set your operator password for {channel} (4+ chars):"
        else:
            prompt_text = f"Enter your operator password for {channel}:"
        
        ttk.Label(dialog, text=prompt_text, font=('Arial', 10, 'bold')).pack(pady=15)
        
        password_entry = ttk.Entry(dialog, width=40, show='*')
        password_entry.pack(padx=20, fill=tk.X, pady=5)
        password_entry.focus()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)
        
        def submit():
            password = password_entry.get().strip()
            if not password:
                messagebox.showerror("Error", "Password cannot be empty")
                return
            if is_new and len(password) < 4:
                messagebox.showerror("Error", "Password must be at least 4 characters")
                return
            dialog.destroy()
            # Send password response to server
            msg = Protocol.build_message(
                MessageType.OP_PASSWORD_RESPONSE,
                channel=channel,
                password=password
            )
            asyncio.run_coroutine_threadsafe(
                self.send_to_server(msg),
                self.loop
            )
        
        def cancel():
            dialog.destroy()
            # User refused to provide password - will be disconnected by server
            self.log("Operator authentication cancelled - you will be disconnected", "error")
        
        ttk.Button(btn_frame, text="Submit", command=submit, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side=tk.LEFT)
        
        password_entry.bind('<Return>', lambda e: submit())
    
    def kick_user_dialog(self, target_nickname):
        """Show kick user dialog"""
        if not self.connected or not self.current_channel:
            return
        
        # Create kick dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Kick User")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        ttk.Label(dialog, text=f"Kick {target_nickname} from {self.current_channel}?", font=('Arial', 10, 'bold')).pack(pady=15)
        
        ttk.Label(dialog, text="Reason (optional):").pack(anchor=tk.W, padx=20)
        reason_entry = ttk.Entry(dialog, width=40)
        reason_entry.pack(padx=20, fill=tk.X, pady=5)
        reason_entry.focus()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)
        
        def kick():
            reason = reason_entry.get().strip() or "No reason given"
            dialog.destroy()
            asyncio.run_coroutine_threadsafe(
                self._kick_user(target_nickname, reason),
                self.loop
            )
        
        ttk.Button(btn_frame, text="Kick", command=kick, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT)
        
        reason_entry.bind('<Return>', lambda e: kick())
    
    def log_chat(self, sender: str, message: str, channel: str = None, msg_type: str = "msg"):
        """Add structured chat message with colored nickname"""
        from datetime import datetime
        
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp
        if self.config.get("ui", "show_timestamps", default=True):
            timestamp = datetime.now().strftime("[%H:%M:%S] ")
            self.chat_display.insert(tk.END, timestamp, "timestamp")
        
        # Add channel prefix if needed (e.g. strict format)
        if channel:
            self.chat_display.insert(tk.END, f"[{channel}] ", "channel")
        
        # Determine sender color and tag
        nick_color = self.config.get_nick_color(sender)
        nick_tag = f"nick_{sender}"
        try:
            self.chat_display.tag_config(nick_tag, foreground=nick_color, font=('Consolas', 10, 'bold'))
        except:
            pass
            
        # Insert Nickname
        if msg_type == "action":
            self.chat_display.insert(tk.END, "* ", "action")
            self.chat_display.insert(tk.END, sender, nick_tag)
            self.chat_display.insert(tk.END, f" {message}\n", "action")
        else:
            self.chat_display.insert(tk.END, f"<{sender}> ", nick_tag)
            self.chat_display.insert(tk.END, f"{message}\n", "self_msg")
            
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def log(self, message: str, tag: str = None):
        """Add message to chat display"""
        from datetime import datetime
        
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp if enabled
        show_timestamps = self.config.get("ui", "show_timestamps", default=True)
        if show_timestamps:
            timestamp = datetime.now().strftime("[%H:%M:%S] ")
            self.chat_display.insert(tk.END, timestamp, "timestamp")
        
        if tag:
            self.chat_display.insert(tk.END, message + "\n", tag)
        else:
            self.chat_display.insert(tk.END, message + "\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    def set_status(self, status: str):
        """Update status bar"""
        self.status_var.set(status)
    
    def connect(self):
        """Connect to server"""
        server = self.server_entry.get().strip()
        port = self.port_entry.get().strip()
        nickname = self.nick_entry.get().strip()
        
        if not nickname:
            messagebox.showerror("Error", "Please enter a nickname")
            return
        
        try:
            port = int(port)
        except ValueError:
            messagebox.showerror("Error", "Invalid port number")
            return
        
        self.nickname = nickname
        
        # Disable connection controls
        self.connect_btn.config(state=tk.DISABLED)
        self.server_entry.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.DISABLED)
        self.nick_entry.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.NORMAL)
        
        # Start event loop in thread
        self.running = True
        thread = threading.Thread(target=self._run_async_loop, args=(server, port), daemon=True)
        thread.start()
        
        self.log(f"Connecting to {server}:{port}...", "info")
    
    def _run_async_loop(self, server: str, port: int):
        """Run asyncio event loop in thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._connect_and_run(server, port))
        except Exception as e:
            self.log(f"Connection error: {e}", "error")
        finally:
            self.loop.close()
            self.running = False
    
    async def _connect_and_run(self, server: str, port: int):
        """Connect to server and run"""
        try:
            # Try to connect with 10 second timeout
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(server, port),
                timeout=10.0
            )
            self.connected = True
            
            # Save last server to config
            self.config.set("server", "last_server", value=server)
            self.config.set("server", "last_port", value=str(port))
            
            self.root.after(0, lambda: self.set_status(f"Connected to {server}:{port}"))
            self.root.after(0, lambda: self.log(f"Connected to {server}:{port}", "success"))
            self.root.after(0, self.update_context_label)
            
            # Register
            public_key = self.crypto.get_public_key_b64()
            msg = Protocol.register(self.nickname, public_key)
            await self.send_to_server(msg)
            
            # Receive loop
            while self.running and self.connected:
                data = await self.reader.readline()
                if not data:
                    break
                
                message_str = data.decode('utf-8').strip()
                if message_str:
                    try:
                        message = json.loads(message_str)
                        await self.handle_message(message)
                    except json.JSONDecodeError:
                        pass
        
        except asyncio.TimeoutError:
            self.root.after(0, lambda: self.log(f"Connection timeout: Server unavailable after 10 seconds", "error"))
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.log(f"Connection lost: {error_msg}", "error"))
        finally:
            self.connected = False
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            self.root.after(0, self._on_disconnected)
    
    async def send_to_server(self, message: str):
        """Send message to server"""
        if self.writer and self.connected:
            self.writer.write(message.encode('utf-8') + b'\n')
            await self.writer.drain()
    
    async def handle_message(self, message: dict):
        """Handle incoming message"""
        msg_type = message.get('type')
        
        if msg_type == MessageType.ACK.value:
            if 'user_id' in message:
                self.user_id = message['user_id']
                welcome_msg = message.get('message', 'Registered')
                self.root.after(0, lambda: self.log(welcome_msg, "success"))
                
                # Display server description if provided
                if 'description' in message and message['description']:
                    description = message['description']
                    self.root.after(0, lambda: self.log("\n" + description + "\n", "info"))
            
            elif 'channel' in message:
                channel = message['channel']
                self.joined_channels.add(channel)
                self.current_channel = channel
                
                # Track if channel is password-protected
                if message.get('is_protected', False):
                    self.protected_channels.add(channel)
                
                # Initialize channel users set
                if channel not in self.channel_users:
                    self.channel_users[channel] = set()
                
                # Initialize channel operators and mods sets
                if channel not in self.channel_operators:
                    self.channel_operators[channel] = set()
                if channel not in self.channel_mods:
                    self.channel_mods[channel] = set()
                
                # Load member keys and track them
                members = message.get('members', [])
                for member in members:
                    member_id = member['user_id']
                    self.channel_users[channel].add(member_id)
                    
                    # Track operator status
                    if member.get('is_operator', False):
                        self.channel_operators[channel].add(member_id)
                    
                    # Track mod status
                    if member.get('is_mod', False):
                        self.channel_mods[channel].add(member_id)
                    
                    # Track owner
                    if member.get('is_owner', False):
                        self.channel_owners[channel] = member_id
                    
                    if member_id != self.user_id:
                        self.users[member_id] = {
                            'nickname': member['nickname'],
                            'public_key': member['public_key']
                        }
                        self.crypto.load_peer_public_key(member_id, member['public_key'])
                    else:
                        # Add ourselves to users dict if not there
                        if member_id not in self.users:
                            self.users[member_id] = {
                                'nickname': member['nickname'],
                                'public_key': member['public_key']
                            }
                
                self.root.after(0, self._update_channel_list)
                self.root.after(0, self._update_channel_user_list)
                self.root.after(0, self.update_context_label)
                self.root.after(0, lambda: self.log(f"Joined {channel} ({len(members)} members)", "success"))
        
        elif msg_type == MessageType.USER_LIST.value:
            users = message.get('users', [])
            for user in users:
                self.users[user['user_id']] = {
                    'nickname': user['nickname'],
                    'public_key': user['public_key']
                }
                self.crypto.load_peer_public_key(user['user_id'], user['public_key'])
            
            self.root.after(0, self._update_user_list)
            self.root.after(0, lambda: self.log(f"{len(users)} users online", "info"))
        
        elif msg_type == MessageType.PRIVATE_MESSAGE.value:
            from_id = message['from_id']
            try:
                plaintext = self.crypto.decrypt(from_id, message['encrypted_data'], message['nonce'])
                sender = self.users.get(from_id, {}).get('nickname', from_id)
                
                # Check if it's an action message
                prefix = f"* {sender} "
                if plaintext.startswith(prefix):
                    content = plaintext[len(prefix):]
                    self.root.after(0, lambda: self.log_chat(sender, content, channel="PM", msg_type="action"))
                elif plaintext.startswith('* '):
                     # Fallback for weird action format
                     self.root.after(0, lambda: self.log(f"[PM from {sender}] {plaintext}", "action")) 
                else:
                    self.root.after(0, lambda: self.log_chat(sender, plaintext, channel="PM", msg_type="msg"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.log(f"Failed to decrypt PM: {error_msg}", "error"))
        
        elif msg_type == MessageType.CHANNEL_MESSAGE.value:
            from_id = message.get('from_id')
            channel = message.get('to_id') or message.get('channel')
            sender = message.get('sender')
            
            # Handle server announcements (no encryption)
            if sender == "SERVER":
                text = message.get('text', '')
                if channel == self.current_channel:
                    self.root.after(0, lambda c=channel, t=text: self.log(f"[{c}] {t}", "system"))
            elif from_id:
                # Handle encrypted user messages
                try:
                    plaintext = self.crypto.decrypt(from_id, message['encrypted_data'], message['nonce'])
                    sender_nick = self.users.get(from_id, {}).get('nickname', from_id)
                    
                    # Only display if this is the current channel
                    if channel == self.current_channel:
                        # Check if it's an action message
                        prefix = f"* {sender_nick} "
                        if plaintext.startswith(prefix):
                            content = plaintext[len(prefix):]
                            self.root.after(0, lambda c=channel, s=sender_nick, m=content: self.log_chat(s, m, c, msg_type="action"))
                        elif plaintext.startswith('* '):
                            # Display action with special formatting (fallback)
                            self.root.after(0, lambda c=channel, p=plaintext: self.log(f"[{c}] {p}", "action"))
                        else:
                            # Normal channel message
                            self.root.after(0, lambda c=channel, s=sender_nick, p=plaintext: self.log_chat(s, p, c))
                except Exception:
                    pass
        
        elif msg_type == MessageType.JOIN_CHANNEL.value:
            user_id = message['user_id']
            nickname = message['nickname']
            channel = message['channel']
            public_key = message.get('public_key')
            is_operator = message.get('is_operator', False)
            is_mod = message.get('is_mod', False)
            is_owner = message.get('is_owner', False)
            
            # Add user to channel tracking
            if channel not in self.channel_users:
                self.channel_users[channel] = set()
            self.channel_users[channel].add(user_id)
            
            # Initialize channel role tracking if needed
            if channel not in self.channel_operators:
                self.channel_operators[channel] = set()
            if channel not in self.channel_mods:
                self.channel_mods[channel] = set()
            
            # Track their roles
            if is_operator:
                self.channel_operators[channel].add(user_id)
            if is_mod:
                self.channel_mods[channel].add(user_id)
            if is_owner:
                self.channel_owners[channel] = user_id
            
            if user_id != self.user_id:
                self.users[user_id] = {'nickname': nickname, 'public_key': public_key}
                if public_key:
                    self.crypto.load_peer_public_key(user_id, public_key)
                
                self.root.after(0, self._update_user_list)
                self.root.after(0, lambda: self.log(f"{nickname} joined {channel}", "system"))
                
                # Update channel user list if viewing this channel
                if self.current_channel == channel:
                    self.root.after(0, self._update_channel_user_list)
        
        elif msg_type == MessageType.LEAVE_CHANNEL.value:
            user_id = message.get('user_id')
            nickname = message['nickname']
            channel = message['channel']
            
            # Remove user from channel tracking
            if channel in self.channel_users and user_id:
                self.channel_users[channel].discard(user_id)
            
            self.root.after(0, lambda: self.log(f"{nickname} left {channel}", "system"))
            
            # Update channel user list if viewing this channel
            if self.current_channel == channel:
                self.root.after(0, self._update_channel_user_list)
        
        elif msg_type == MessageType.DISCONNECT.value:
            user_id = message.get('user_id')
            nickname = message.get('nickname')
            
            # Remove user from global user list
            if user_id and user_id in self.users:
                del self.users[user_id]
            
            # Remove from all channel tracking
            for channel in self.channel_users.values():
                channel.discard(user_id)
            
            # Update both user lists
            self.root.after(0, self._update_user_list)
            if self.current_channel:
                self.root.after(0, self._update_channel_user_list)
            
            self.root.after(0, lambda n=nickname: self.log(f"{n} disconnected", "system"))
        
        elif msg_type == MessageType.IMAGE_START.value:
            await self.handle_image_start(message)
        
        elif msg_type == MessageType.IMAGE_CHUNK.value:
            await self.handle_image_chunk(message)
        
        elif msg_type == MessageType.IMAGE_END.value:
            await self.handle_image_end(message)
        
        elif msg_type == MessageType.WHOIS_RESPONSE.value:
            nickname = message.get('nickname')
            channels = message.get('channels', [])
            channel_list = ', '.join(channels) if channels else 'No channels'
            whois_info = f"Whois {nickname}:\n  Channels: {channel_list}\n  Status: Online"
            self.root.after(0, lambda: self.log(whois_info, "info"))
        
        elif msg_type == MessageType.CHANNEL_LIST_RESPONSE.value:
            channels = message.get('channels', [])
            if channels:
                list_text = "Available channels:\n"
                for ch in channels:
                    lock = "🔒 " if ch.get('protected') else ""
                    list_text += f"  {lock}{ch['name']} ({ch['users']} users)\n"
                self.root.after(0, lambda: self.log(list_text, "info"))
            else:
                self.root.after(0, lambda: self.log("No channels available", "info"))
        
        elif msg_type == MessageType.OP_USER.value:
            # Someone was granted operator status
            channel = message.get('channel')
            user_id = message.get('user_id')
            nickname = message.get('nickname')
            granted_by = message.get('granted_by')
            
            if channel in self.channel_operators:
                self.channel_operators[channel].add(user_id)
            else:
                self.channel_operators[channel] = {user_id}
            
            self.root.after(0, lambda: self.log(f"{nickname} was granted operator status by {granted_by} in {channel}", "system"))
            if self.current_channel == channel:
                self.root.after(0, self._update_channel_user_list)
        
        elif msg_type == MessageType.UNOP_USER.value:
            # Someone had operator status removed
            channel = message.get('channel')
            user_id = message.get('user_id')
            nickname = message.get('nickname')
            removed_by = message.get('removed_by')
            
            if channel in self.channel_operators:
                self.channel_operators[channel].discard(user_id)
            
            self.root.after(0, lambda: self.log(f"{nickname} had operator status removed by {removed_by} in {channel}", "system"))
            if self.current_channel == channel:
                self.root.after(0, self._update_channel_user_list)
        
        elif msg_type == MessageType.MOD_USER.value:
            # Someone was granted mod status
            channel = message.get('channel')
            user_id = message.get('user_id')
            nickname = message.get('nickname')
            granted_by = message.get('granted_by')
            
            if channel in self.channel_mods:
                self.channel_mods[channel].add(user_id)
            else:
                self.channel_mods[channel] = {user_id}
            
            self.root.after(0, lambda: self.log(f"{nickname} was granted mod status by {granted_by} in {channel}", "system"))
            if self.current_channel == channel:
                self.root.after(0, self._update_channel_user_list)
        
        elif msg_type == MessageType.UNMOD_USER.value:
            # Someone had mod status removed
            channel = message.get('channel')
            user_id = message.get('user_id')
            nickname = message.get('nickname')
            removed_by = message.get('removed_by')
            
            if channel in self.channel_mods:
                self.channel_mods[channel].discard(user_id)
            
            self.root.after(0, lambda: self.log(f"{nickname} had mod status removed by {removed_by} in {channel}", "system"))
            if self.current_channel == channel:
                self.root.after(0, self._update_channel_user_list)
        
        elif msg_type == MessageType.KICK_USER.value:
            # You were kicked from a channel
            channel = message.get('channel')
            kicked_by = message.get('kicked_by')
            reason = message.get('reason', 'No reason given')
            
            # Remove from joined channels
            if channel in self.joined_channels:
                self.joined_channels.remove(channel)
            
            # Clear channel data
            if channel in self.channel_users:
                del self.channel_users[channel]
            if channel in self.channel_operators:
                del self.channel_operators[channel]
            if channel in self.channel_mods:
                del self.channel_mods[channel]
            
            # If viewing this channel, clear it
            if self.current_channel == channel:
                self.current_channel = None
                self.root.after(0, self.update_context_label)
            
            self.root.after(0, lambda: self.log(f"You were kicked from {channel} by {kicked_by}: {reason}", "error"))
            self.root.after(0, self._update_channel_list)
        
        elif msg_type == MessageType.BAN_USER.value:
            # You were banned from a channel
            channel = message.get('channel')
            banned_by = message.get('banned_by')
            reason = message.get('reason', 'No reason given')
            
            # Remove from joined channels
            if channel in self.joined_channels:
                self.joined_channels.remove(channel)
            
            # Clear channel data
            if channel in self.channel_users:
                del self.channel_users[channel]
            if channel in self.channel_operators:
                del self.channel_operators[channel]
            if channel in self.channel_mods:
                del self.channel_mods[channel]
            
            # If viewing this channel, clear it
            if self.current_channel == channel:
                self.current_channel = None
                self.root.after(0, self.update_context_label)
            
            self.root.after(0, lambda: self.log(f"You were BANNED from {channel} by {banned_by}: {reason}", "error"))
            self.root.after(0, self._update_channel_list)
        
        elif msg_type == MessageType.UNBAN_USER.value:
            # You were unbanned from a channel
            channel = message.get('channel')
            unbanned_by = message.get('unbanned_by')
            
            self.root.after(0, lambda: self.log(f"You were unbanned from {channel} by {unbanned_by}", "success"))
        
        elif msg_type == MessageType.OP_PASSWORD_REQUEST.value:
            channel = message.get('channel')
            action = message.get('action')
            
            # Request password from user
            if action == 'set':
                self.root.after(0, lambda: self._prompt_op_password(channel, is_new=True))
            else:  # verify
                self.root.after(0, lambda: self._prompt_op_password(channel, is_new=False))
        
        elif msg_type == MessageType.ERROR.value:
            error = message.get('error')
            self.root.after(0, lambda: self.log(f"Error: {error}", "error"))
    
    def _update_channel_list(self):
        """Update channel list box"""
        self.channel_list.delete(0, tk.END)
        for channel in sorted(self.joined_channels):
            # Add padlock symbol for protected channels
            display_name = f"🔒 {channel}" if channel in self.protected_channels else channel
            self.channel_list.insert(tk.END, display_name)
    
    def _update_user_list(self):
        """Update user list box"""
        self.user_list.delete(0, tk.END)
        for user_id, info in self.users.items():
            self.user_list.insert(tk.END, info['nickname'])
    
    def _update_channel_user_list(self):
        """Update channel user list for current channel with symbols and colors"""
        self.channel_user_list.delete(0, tk.END)
        
        if not self.current_channel:
            return
        
        # Get users in current channel
        channel_members = self.channel_users.get(self.current_channel, set())
        channel_ops = self.channel_operators.get(self.current_channel, set())
        channel_mods = self.channel_mods.get(self.current_channel, set())
        channel_owner = self.channel_owners.get(self.current_channel)
        
        # Sort: owner first, then operators, then mods, then alphabetically
        members_with_info = []
        for user_id in channel_members:
            info = self.users.get(user_id)
            if info:
                nickname = info['nickname']
                is_owner = (user_id == channel_owner)
                is_op = user_id in channel_ops
                is_mod = user_id in channel_mods
                # Sort key: (not owner, not op, not mod, nickname)
                members_with_info.append((nickname, user_id, is_owner, is_op, is_mod))
        
        # Sort: owner first, then ops, then mods, then alphabetically by nickname
        members_with_info.sort(key=lambda x: (not x[2], not x[3], not x[4], x[0].lower()))
        
        # Add to listbox with symbols
        for i, (nickname, user_id, is_owner, is_op, is_mod) in enumerate(members_with_info):
            symbol = self.config.get_role_symbol(is_owner=is_owner, is_op=is_op, is_mod=is_mod)
            display_name = f"{symbol} {nickname}"
            
            self.channel_user_list.insert(tk.END, display_name)
            
            # Colorize the item
            fg_color = self.config.get_nick_color(nickname)
            # Make sure it's readable against the background
            try:
                self.channel_user_list.itemconfig(i, foreground=fg_color)
                if is_op:
                     pass # self.channel_user_list.itemconfig(i, selectbackground=fg_color)
            except:
                pass
    
    def on_channel_select(self, event):
        """Handle channel selection"""
        selection = self.channel_list.curselection()
        if selection:
            idx = selection[0]
            display_name = self.channel_list.get(idx)
            # Strip padlock emoji if present
            channel = display_name.replace('🔒 ', '')
            self.current_channel = channel
            self.current_recipient = None  # Clear PM mode
            self.set_status(f"Channel: {self.current_channel}")
            self.update_context_label()
            self._update_channel_user_list()  # Update channel users display
    
    def on_user_double_click(self, event):
        """Handle double-click on user (start PM)"""
        selection = self.user_list.curselection()
        if selection:
            nickname = self.user_list.get(selection[0])
            self.current_channel = None  # Switch to PM mode
            self.current_recipient = nickname
            self.set_status(f"PM to: {nickname}")
            self.update_context_label()
            self.message_entry.focus()
    
    def send_message(self):
        """Send message or execute command"""
        text = self.message_entry.get().strip()
        if not text or not self.connected:
            return
        
        # Handle IRC commands
        if text.startswith('/'):
            self.message_entry.delete(0, tk.END)
            asyncio.run_coroutine_threadsafe(
                self.handle_slash_command(text),
                self.loop
            )
            return
        
        # Normal message
        target = self.current_channel if self.current_channel else self.current_recipient
        if not target:
            self.log("Select a channel or user first", "error")
            return
        
        # Send message
        if self.current_channel:
            asyncio.run_coroutine_threadsafe(
                self._send_channel_message(self.current_channel, text),
                self.loop
            )
        elif self.current_recipient:
            asyncio.run_coroutine_threadsafe(
                self._send_private_message(self.current_recipient, text),
                self.loop
            )
        
        self.message_entry.delete(0, tk.END)
    
    async def handle_slash_command(self, text: str):
        """Handle IRC slash commands"""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == '/me':
            # Action message
            if not args:
                self.root.after(0, lambda: self.log("Usage: /me <action>", "error"))
                return
            
            action_text = f"* {self.nickname} {args}"
            
            if self.current_channel:
                # Send to channel
                for user_id, info in self.users.items():
                    if user_id != self.user_id:
                        try:
                            encrypted_data, nonce = self.crypto.encrypt(user_id, action_text)
                            msg = Protocol.encrypted_message(
                                self.user_id, self.current_channel, encrypted_data, nonce, is_channel=True
                            )
                            await self.send_to_server(msg)
                        except Exception:
                            pass
                # Echo
                self.root.after(0, lambda: self.log(f"[{self.current_channel}] {action_text}", "action"))
            
            elif self.current_recipient:
                # Send as PM
                target_id = None
                for uid, info in self.users.items():
                    if info['nickname'] == self.current_recipient:
                        target_id = uid
                        break
                if target_id:
                    encrypted_data, nonce = self.crypto.encrypt(target_id, action_text)
                    msg = Protocol.encrypted_message(
                        self.user_id, target_id, encrypted_data, nonce, is_channel=False
                    )
                    await self.send_to_server(msg)
                    self.root.after(0, lambda: self.log(f"[PM to {self.current_recipient}] {action_text}", "action"))
        
        elif cmd == '/op':
            # Grant operator status (requires password)
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel", "error"))
                return
            if not args:
                self.root.after(0, lambda: self.log("Usage: /op <user>", "error"))
                return
            
            target_nickname = args.strip()
            # Will need password - show dialog
            self.root.after(0, lambda: self.op_user_dialog_for_user(target_nickname))
        
        elif cmd == '/mod':
            # Grant mod status (no password needed)
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel", "error"))
                return
            if not args:
                self.root.after(0, lambda: self.log("Usage: /mod <user>", "error"))
                return
            
            target_nickname = args.strip()
            msg = Protocol.build_message(MessageType.MOD_USER, channel=self.current_channel, target_nickname=target_nickname)
            asyncio.run_coroutine_threadsafe(
                self.send_to_server(msg),
                self.loop
            )
        
        elif cmd == '/join':
            if not args:
                self.root.after(0, lambda: self.log(
                    "Usage: /join #channel [join_password] [creator_password]\n"
                    "  - For new channels: creator_password required (4+ chars)\n"
                    "  - For existing channels: use creator_password to regain operator status",
                    "error"
                ))
                return
            parts = args.split(maxsplit=2)
            channel = parts[0]
            join_password = parts[1] if len(parts) > 1 else None
            creator_password = parts[2] if len(parts) > 2 else join_password  # If only one password, use for both
            await self._join_channel(channel, join_password, creator_password)
        
        elif cmd == '/leave' or cmd == '/part':
            channel = args.strip() if args else self.current_channel
            if channel:
                await self._leave_channel(channel)
            else:
                self.root.after(0, lambda: self.log("Usage: /leave [channel]", "error"))
        
        elif cmd == '/msg' or cmd == '/query':
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                self.root.after(0, lambda: self.log("Usage: /msg <user> <message>", "error"))
                return
            await self._send_private_message(parts[0], parts[1])
        
        elif cmd == '/image':
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                self.root.after(0, lambda: self.log("Usage: /image <user> <filepath>", "error"))
                return
            await self._send_image(parts[0], parts[1])
        
        elif cmd == '/users':
            if self.users:
                user_list = "Online users:\n" + "\n".join(f"  • {info['nickname']}" for uid, info in self.users.items())
                self.root.after(0, lambda: self.log(user_list, "info"))
            else:
                self.root.after(0, lambda: self.log("No users online", "info"))
        
        elif cmd == '/whois':
            if not args:
                self.root.after(0, lambda: self.log("Usage: /whois <nickname>", "error"))
                return
            nickname = args.strip()
            msg = Protocol.whois(nickname)
            await self.send_to_server(msg)
        
        elif cmd == '/list':
            msg = Protocol.list_channels()
            await self.send_to_server(msg)
        
        elif cmd == '/kick':
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel to use /kick", "error"))
                return
            parts = args.split(maxsplit=1)
            if not parts:
                self.root.after(0, lambda: self.log("Usage: /kick <user> [reason]", "error"))
                return
            target_nickname = parts[0]
            reason = parts[1] if len(parts) > 1 else "No reason given"
            msg = Protocol.kick_user(self.current_channel, target_nickname, reason)
            await self.send_to_server(msg)
        
        elif cmd == '/topic':
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel to use /topic", "error"))
                return
            if not args:
                self.root.after(0, lambda: self.log("Usage: /topic <new topic>", "error"))
                return
            topic = args.strip()
            msg = Protocol.set_topic(self.current_channel, topic)
            await self.send_to_server(msg)
        
        elif cmd == '/unop':
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel", "error"))
                return
            if not args:
                self.root.after(0, lambda: self.log("Usage: /unop <user>", "error"))
                return
            target_nickname = args.strip()
            msg = Protocol.build_message(MessageType.UNOP_USER, channel=self.current_channel, target_nickname=target_nickname)
            await self.send_to_server(msg)
        
        elif cmd == '/unmod':
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel", "error"))
                return
            if not args:
                self.root.after(0, lambda: self.log("Usage: /unmod <user>", "error"))
                return
            target_nickname = args.strip()
            msg = Protocol.build_message(MessageType.UNMOD_USER, channel=self.current_channel, target_nickname=target_nickname)
            await self.send_to_server(msg)
        
        elif cmd == '/ban':
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel", "error"))
                return
            parts = args.split(maxsplit=1)
            if not parts:
                self.root.after(0, lambda: self.log("Usage: /ban <user> [reason]", "error"))
                return
            target_nickname = parts[0]
            reason = parts[1] if len(parts) > 1 else "No reason given"
            msg = Protocol.build_message(MessageType.BAN_USER, channel=self.current_channel, target_nickname=target_nickname, reason=reason)
            await self.send_to_server(msg)
        
        elif cmd == '/kickban':
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel", "error"))
                return
            parts = args.split(maxsplit=1)
            if not parts:
                self.root.after(0, lambda: self.log("Usage: /kickban <user> [reason]", "error"))
                return
            target_nickname = parts[0]
            reason = parts[1] if len(parts) > 1 else "No reason given"
            msg = Protocol.build_message(MessageType.KICKBAN_USER, channel=self.current_channel, target_nickname=target_nickname, reason=reason)
            await self.send_to_server(msg)
        
        elif cmd == '/unban':
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel", "error"))
                return
            if not args:
                self.root.after(0, lambda: self.log("Usage: /unban <user>", "error"))
                return
            target_nickname = args.strip()
            msg = Protocol.build_message(MessageType.UNBAN_USER, channel=self.current_channel, target_nickname=target_nickname)
            await self.send_to_server(msg)
        
        elif cmd == '/transfer':
            if not self.current_channel:
                self.root.after(0, lambda: self.log("You must be in a channel", "error"))
                return
            if not args:
                self.root.after(0, lambda: self.log("Usage: /transfer <operator_nickname>", "error"))
                return
            target_nickname = args.strip()
            msg = Protocol.build_message(MessageType.TRANSFER_OWNERSHIP, channel=self.current_channel, target_nickname=target_nickname)
            await self.send_to_server(msg)
        
        elif cmd == '/quit':
            self.running = False
            self.disconnect()
        
        elif cmd == '/help':
            self.root.after(0, self.show_help)
        
        else:
            self.root.after(0, lambda: self.log(f"Unknown command: {cmd}. Type /help for available commands", "error"))
    
    async def _send_channel_message(self, channel: str, text: str):
        """Send message to channel"""
        if channel not in self.joined_channels:
            return
        
        for user_id, info in self.users.items():
            if user_id != self.user_id:
                try:
                    encrypted_data, nonce = self.crypto.encrypt(user_id, text)
                    msg = Protocol.encrypted_message(
                        self.user_id, channel, encrypted_data, nonce, is_channel=True
                    )
                    await self.send_to_server(msg)
                except Exception:
                    pass
        
        # Echo own message
        self.root.after(0, lambda: self.log_chat(self.nickname, text, channel))
    
    def op_user_dialog(self):
        """Show op user dialog"""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to server")
            return
        
        if not self.current_channel:
            messagebox.showwarning("Warning", "You must be in a channel to grant operator status")
            return
        
        # Select user
        selection = self.user_list.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a user first")
            return
        
        target_nickname = self.user_list.get(selection[0])
        
        # Create simple confirmation dialog (no password needed for verified operators)
        dialog = tk.Toplevel(self.root)
        dialog.title("Grant Operator Status")
        dialog.geometry("350x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Message
        msg_frame = ttk.Frame(dialog, padding=20)
        msg_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            msg_frame,
            text=f"Grant operator status to {target_nickname}?",
            font=('Arial', 10, 'bold')
        ).pack(pady=(0, 10))
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def on_op():
            dialog.destroy()
            # Send op command (no password needed)
            asyncio.run_coroutine_threadsafe(
                self._op_user(target_nickname, ""),
                self.loop
            )
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(btn_frame, text="Grant Op", command=on_op, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=12).pack(side=tk.LEFT, padx=5)
    
    async def _op_user(self, target_nickname: str, password: str):
        """Grant operator status to a user"""
        msg = Protocol.op_user(self.current_channel, target_nickname, password)
        await self.send_to_server(msg)
        self.root.after(0, lambda: self.log(f"Requesting operator status for {target_nickname}", "info"))
    
    async def _kick_user(self, target_nickname: str, reason: str):
        """Kick a user from the current channel"""
        msg = Protocol.kick_user(self.current_channel, target_nickname, reason)
        await self.send_to_server(msg)
        self.root.after(0, lambda: self.log(f"Kicking {target_nickname} from {self.current_channel}...", "info"))
    
    async def _send_private_message(self, target_nickname: str, text: str):
        """Send private message to user"""
        # Find user ID
        target_id = None
        for uid, info in self.users.items():
            if info['nickname'] == target_nickname:
                target_id = uid
                break
        
        if not target_id:
            self.root.after(0, lambda: self.log(f"User {target_nickname} not found", "error"))
            return
        
        # Ensure we have their public key
        if not self.crypto.has_peer_key(target_id):
            self.root.after(0, lambda: self.log(f"No encryption key for {target_nickname}", "error"))
            return
        
        try:
            # Encrypt message
            encrypted_data, nonce = self.crypto.encrypt(target_id, text)
            
            # Send
            msg = Protocol.encrypted_message(
                self.user_id, target_id, encrypted_data, nonce, is_channel=False
            )
            await self.send_to_server(msg)
            
            # Echo own message
            self.root.after(0, lambda: self.log_chat(f"To {target_nickname}", text, channel="PM", msg_type="msg"))
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.log(f"Failed to send PM: {error_msg}", "error"))
    
    def join_channel_dialog(self):
        """Show join channel dialog"""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to server")
            return
        
        # Create custom dialog for channel and passwords
        dialog = tk.Toplevel(self.root)
        dialog.title("Join Channel")
        dialog.geometry("450x220")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        ttk.Label(dialog, text="Channel name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        channel_entry = ttk.Entry(dialog, width=30)
        channel_entry.grid(row=0, column=1, padx=10, pady=10)
        channel_entry.focus()
        
        ttk.Label(dialog, text="Join password (optional):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        join_password_entry = ttk.Entry(dialog, width=30, show="*")
        join_password_entry.grid(row=1, column=1, padx=10, pady=5)
        
        ttk.Label(dialog, text="Creator password (for operator):").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        creator_password_entry = ttk.Entry(dialog, width=30, show="*")
        creator_password_entry.grid(row=2, column=1, padx=10, pady=5)
        
        hint_label = ttk.Label(
            dialog, 
            text="For new channels: creator password required (4+ chars)\nFor existing: use creator password to regain operator",
            font=('Arial', 8)
        )
        hint_label.grid(row=3, column=0, columnspan=2, padx=10, pady=5)
        
        result = {'channel': None, 'join_password': None, 'creator_password': None}
        
        def on_join():
            channel = channel_entry.get().strip()
            join_pwd = join_password_entry.get().strip() or None
            creator_pwd = creator_password_entry.get().strip() or None
            
            # If no creator password but has join password, use join password for both
            if not creator_pwd and join_pwd:
                creator_pwd = join_pwd
            
            result['channel'] = channel
            result['join_password'] = join_pwd
            result['creator_password'] = creator_pwd
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Join", command=on_join).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        channel_entry.bind('<Return>', lambda e: on_join())
        join_password_entry.bind('<Return>', lambda e: on_join())
        creator_password_entry.bind('<Return>', lambda e: on_join())
        
        dialog.wait_window()
        
        if result['channel']:
            asyncio.run_coroutine_threadsafe(
                self._join_channel(result['channel'], result['join_password'], result['creator_password']),
                self.loop
            )
    
    async def _join_channel(self, channel: str, password: str = None, creator_password: str = None):
        """Join a channel"""
        msg = Protocol.join_channel(self.user_id, channel, password, creator_password)
        await self.send_to_server(msg)
    
    def leave_channel(self):
        """Leave current channel"""
        if not self.current_channel:
            messagebox.showwarning("Warning", "No channel selected")
            return
        
        asyncio.run_coroutine_threadsafe(
            self._leave_channel(self.current_channel),
            self.loop
        )
    
    async def _leave_channel(self, channel: str):
        """Leave a channel"""
        msg = Protocol.leave_channel(self.user_id, channel)
        await self.send_to_server(msg)
        
        self.joined_channels.discard(channel)
        if channel in self.channel_users:
            del self.channel_users[channel]
        
        if self.current_channel == channel:
            self.current_channel = None
        
        self.root.after(0, self._update_channel_list)
        self.root.after(0, self._update_channel_user_list)
    
    def send_image_dialog(self):
        """Show send image dialog"""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to server")
            return
        
        # Select recipient
        selection = self.user_list.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a user first")
            return
        
        nickname = self.user_list.get(selection[0])
        
        # Select file
        filename = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")]
        )
        
        if filename:
            self.log(f"Sending image to {nickname}...", "info")
            asyncio.run_coroutine_threadsafe(
                self._send_image(nickname, filename),
                self.loop
            )
    
    async def _send_image(self, target_nickname: str, image_path: str):
        """Send encrypted image to user"""
        # Find user ID
        target_id = None
        for uid, info in self.users.items():
            if info['nickname'] == target_nickname:
                target_id = uid
                break
        
        if not target_id:
            self.root.after(0, lambda: self.log(f"User {target_nickname} not found", "error"))
            return
        
        if not os.path.exists(image_path):
            self.root.after(0, lambda: self.log(f"File not found: {image_path}", "error"))
            return
        
        try:
            import uuid
            import base64
            
            # Prepare image
            chunks, filename, total_size = self.image_transfer.prepare_image(image_path)
            image_id = str(uuid.uuid4())
            
            # Encrypt metadata
            metadata = {'filename': filename, 'size': total_size}
            encrypted_metadata, nonce = self.crypto.encrypt(target_id, json.dumps(metadata))
            
            # Send start message
            msg = Protocol.image_start(
                self.user_id, target_id, image_id,
                len(chunks), encrypted_metadata, nonce
            )
            await self.send_to_server(msg)
            
            self.root.after(0, lambda: self.log(f"Sending image: {filename} ({len(chunks)} chunks)", "info"))
            
            # Send chunks
            for i, chunk in enumerate(chunks):
                encrypted_chunk, chunk_nonce = self.crypto.encrypt_image(target_id, chunk)
                msg = Protocol.image_chunk(
                    self.user_id, target_id, image_id, i,
                    base64.b64encode(encrypted_chunk).decode('utf-8'),
                    chunk_nonce
                )
                await self.send_to_server(msg)
            
            # Send end message
            msg = Protocol.image_end(self.user_id, target_id, image_id)
            await self.send_to_server(msg)
            
            self.root.after(0, lambda: self.log(f"Image sent: {filename}", "success"))
        
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.log(f"Failed to send image: {error_msg}", "error"))
    
    async def handle_image_start(self, message: dict):
        """Handle start of image transfer - prompt user to accept"""
        from_id = message['from_id']
        image_id = message['image_id']
        total_chunks = message['total_chunks']
        encrypted_metadata = message['encrypted_metadata']
        nonce = message['nonce']
        
        try:
            # Decrypt metadata
            metadata_json = self.crypto.decrypt(from_id, encrypted_metadata, nonce)
            metadata = json.loads(metadata_json)
            
            sender = self.users.get(from_id, {}).get('nickname', from_id)
            filename = metadata['filename']
            size_mb = metadata['size'] / (1024 * 1024)
            
            # Store pending transfer
            self.pending_images[image_id] = {
                'from_id': from_id,
                'sender': sender,
                'metadata': metadata,
                'total_chunks': total_chunks,
                'chunks': [None] * total_chunks,
                'received': 0,
                'accepted': None  # Will be True/False after user response
            }
            
            # Prompt user on main thread
            self.root.after(0, lambda: self._prompt_image_accept(image_id, sender, filename, size_mb))
        
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.log(f"Failed to process image request: {error_msg}", "error"))
    
    async def handle_image_chunk(self, message: dict):
        """Handle image chunk - only process if accepted"""
        from_id = message['from_id']
        image_id = message['image_id']
        chunk_number = message['chunk_number']
        encrypted_data = message['encrypted_data']
        nonce = message['nonce']
        
        # Check if this is a pending/accepted transfer
        if image_id not in self.pending_images:
            return  # Unknown transfer, ignore
        
        pending = self.pending_images[image_id]
        
        # If user hasn't decided yet, queue the chunk
        if pending['accepted'] is None:
            # Store encrypted chunk for later processing
            if 'queued_chunks' not in pending:
                pending['queued_chunks'] = {}
            pending['queued_chunks'][chunk_number] = (encrypted_data, nonce)
            return
        
        # If user declined, ignore chunks
        if not pending['accepted']:
            return
        
        # User accepted, decrypt and store chunk
        try:
            import base64
            chunk_data = self.crypto.decrypt_image(
                from_id,
                base64.b64decode(encrypted_data),
                nonce
            )
            
            pending['chunks'][chunk_number] = chunk_data
            pending['received'] += 1
        
        except Exception as e:
            import logging
            logging.error(f"Failed to decrypt image chunk: {e}")
    
    async def handle_image_end(self, message: dict):
        """Handle end of image transfer"""
        image_id = message['image_id']
        
        if image_id not in self.pending_images:
            return
        
        pending = self.pending_images[image_id]
        
        # If user declined, clean up and done
        if pending['accepted'] is False:
            del self.pending_images[image_id]
            return
        
        # If user accepted, save the image
        if pending['accepted'] is True:
            # Reassemble image
            image_data = b''.join(pending['chunks'])
            metadata = pending['metadata']
            filename = pending.get('save_path', f"received_{metadata['filename']}")
            
            try:
                with open(filename, 'wb') as f:
                    f.write(image_data)
                
                sender = pending['sender']
                self.root.after(0, lambda: self.log(f"Image saved: {filename} (from {sender})", "success"))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.log(f"Failed to save image: {error_msg}", "error"))
            
            # Clean up
            del self.pending_images[image_id]
    
    def _prompt_image_accept(self, image_id: str, sender: str, filename: str, size_mb: float):
        """Prompt user to accept or decline image transfer"""
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Incoming Image")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Message
        msg_frame = ttk.Frame(dialog, padding=20)
        msg_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            msg_frame,
            text=f"{sender} wants to send you an image:",
            font=('Arial', 10, 'bold')
        ).pack(pady=(0, 10))
        
        ttk.Label(msg_frame, text=f"Filename: {filename}").pack(anchor=tk.W)
        ttk.Label(msg_frame, text=f"Size: {size_mb:.2f} MB").pack(anchor=tk.W)
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def on_accept():
            dialog.destroy()
            # Ask where to save
            save_path = filedialog.asksaveasfilename(
                title="Save image as",
                initialfile=filename,
                defaultextension=os.path.splitext(filename)[1]
            )
            
            if save_path:
                self._accept_image_transfer(image_id, save_path)
            else:
                # User cancelled save dialog
                self._decline_image_transfer(image_id)
        
        def on_decline():
            dialog.destroy()
            self._decline_image_transfer(image_id)
        
        ttk.Button(btn_frame, text="Accept", command=on_accept, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Decline", command=on_decline, width=12).pack(side=tk.LEFT, padx=5)
        
        self.log(f"{sender} wants to send you: {filename}", "info")
    
    def _accept_image_transfer(self, image_id: str, save_path: str):
        """Accept an image transfer and process queued chunks"""
        if image_id not in self.pending_images:
            return
        
        pending = self.pending_images[image_id]
        pending['accepted'] = True
        pending['save_path'] = save_path
        
        self.log(f"Accepting image from {pending['sender']}", "success")
        
        # Process any queued chunks that arrived while user was deciding
        if 'queued_chunks' in pending:
            import base64
            for chunk_num, (encrypted_data, nonce) in pending['queued_chunks'].items():
                try:
                    chunk_data = self.crypto.decrypt_image(
                        pending['from_id'],
                        base64.b64decode(encrypted_data),
                        nonce
                    )
                    pending['chunks'][chunk_num] = chunk_data
                    pending['received'] += 1
                except Exception as e:
                    import logging
                    logging.error(f"Failed to decrypt queued chunk: {e}")
            
            del pending['queued_chunks']
    
    def _decline_image_transfer(self, image_id: str):
        """Decline an image transfer"""
        if image_id not in self.pending_images:
            return
        
        pending = self.pending_images[image_id]
        pending['accepted'] = False
        
        self.log(f"Declined image from {pending['sender']}", "info")
    
    def update_context_label(self):
        """Update the context label showing where messages will be sent"""
        if not self.connected:
            self.context_label.config(text="Not connected", foreground='gray')
        elif self.current_channel:
            self.context_label.config(text=f"Channel: {self.current_channel}", foreground='orange')
        elif self.current_recipient:
            self.context_label.config(text=f"PM to {self.current_recipient}", foreground='magenta')
        else:
            self.context_label.config(text="Select a channel or user", foreground='gray')
    
    def disconnect(self):
        """Disconnect from server"""
        self.running = False
        self.connected = False
        
        if self.loop and self.writer:
            asyncio.run_coroutine_threadsafe(self._close_connection(), self.loop)
    
    async def _close_connection(self):
        """Close connection"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
    
    def _on_disconnected(self):
        """Handle disconnection"""
        self.connect_btn.config(state=tk.NORMAL)
        self.server_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
        self.nick_entry.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        
        self.channel_list.delete(0, tk.END)
        self.user_list.delete(0, tk.END)
        
        self.set_status("Disconnected")
        self.log("Disconnected from server", "info")
        self.update_context_label()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = IRCClientGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

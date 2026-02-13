"""
JustIRC GUI Client - Secure IRC Client with GUI (MVP Architecture)
Uses Tkinter for cross-platform GUI
Refactored to use Model-View-Presenter pattern with dependency injection
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

# Protocol and crypto
from protocol import Protocol, MessageType
from crypto_layer import CryptoLayer
from image_transfer import ImageTransfer

# Configuration and utilities
from config_manager import ConfigManager
from message_history import MessageHistory
from message_formatter import MessageFormatter
from system_tray_manager import SystemTrayManager
from ui_dialogs import UIDialogs
from command_handler import CommandHandler
from settings_dialogs import SettingsDialogs

# MVP Architecture (v1.2.0)
from dependency_container import create_default_container
from presenter import ClientPresenter
from models import User, Channel, Message, ClientState, UserStatus, MessageType as ModelMessageType
from services import NetworkService


class IRCClientGUI:
    """GUI IRC Client with E2E encryption (MVP Architecture)"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🛡️ JustIRC - Secure Encrypted IRC")
        self.root.geometry("1100x700")
        
        # Load configuration
        self.config = ConfigManager()
        
        # Initialize MVP architecture with dependency injection
        self.container = create_default_container(self.config)
        self.presenter: ClientPresenter = self.container.resolve(ClientPresenter)
        
        # Connect presenter callbacks to UI update methods
        self._setup_presenter_callbacks()
        
        # Legacy support - these will be phased out as we use presenter
        self.crypto = self.container.resolve(CryptoLayer)
        self.image_transfer = self.container.resolve(ImageTransfer)
        self.formatter = MessageFormatter()
        
        # LEGACY STATE: Still used by handle_message() - TODO: migrate to presenter/state_manager
        self.connected = False
        self.user_id: Optional[str] = None
        self.nickname: Optional[str] = None
        self.users = {}  # All users: user_id -> {nickname, public_key, status, status_message}
        self.channel_users = {}  # Users in current channel: channel -> set(user_ids)
        self.channel_operators = {}  # Channel operators: channel -> set(operator_user_ids)
        self.channel_mods = {}  # Channel mods: channel -> set(mod_user_ids)
        self.channel_owners = {}  # Channel owners: channel -> owner_user_id
        self.protected_channels = set()  # Channels that are password-protected
        self.current_channel: Optional[str] = None
        self.current_recipient: Optional[str] = None  # For private messages
        self.joined_channels = set()
        self.blocked_users = set()  # Set of blocked user_ids
        self.current_status = "online"  # online, away, busy, dnd
        self.current_status_message = ""
        
        # UI state (not business state - that's in presenter/state_manager)
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
        # Legacy state properties - now backed by presenter's state
        # These provide backward compatibility during refactoring
        self._legacy_compat_setup()
        
        # Pending image transfers (still handled at UI level for now)
        self.pending_images = {}
        
        # Message history (optional)
        self.history = None
        if self.config.get("history", "enabled", default=False):
            history_encrypted = self.config.get("history", "encrypted", default=False)
            history_password = self.config.get("history", "password", default=None) if history_encrypted else None
            try:
                self.history = MessageHistory(password=history_password)
            except Exception as e:
                print(f"Failed to initialize message history: {e}")
        
        # Event loop
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
        
        self.setup_window_icon()
        self.setup_ui()
        self.apply_theme()
        
        # System tray setup
        self.tray_manager = SystemTrayManager(
            self.root, 
            self.show_window, 
            self.hide_window, 
            self.quit_app
        )
        if self.tray_manager.is_available() and self.config.get("ui", "enable_system_tray", default=True):
            self.tray_manager.setup()
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Command handler
        self.command_handler = CommandHandler(self)
    
    def _setup_presenter_callbacks(self):
        """Connect presenter callbacks to UI update methods"""
        self.presenter.on_connection_changed = self._on_connection_changed
        self.presenter.on_message_received = self._on_message_received
        self.presenter.on_user_list_updated = self._on_user_list_updated
        self.presenter.on_channel_joined = self._on_channel_joined
        self.presenter.on_channel_left = self._on_channel_left
        self.presenter.on_error = self._on_error
        self.presenter.on_state_changed = self._on_state_changed
        
        # Register handle_message as a message handler with NetworkService
        # This allows the existing comprehensive message handling to continue working
        # TODO: Gradually migrate individual message types to service-level handling
        self.presenter.network.add_message_handler(self.handle_message)
    
    def _legacy_compat_setup(self):
        """Set up legacy compatibility properties that delegate to presenter state"""
        # NOTE: Most legacy state is kept as instance variables for now (see __init__)
        # because handle_message() still modifies them directly
        # As we migrate handle_message(), we can remove these and use properties instead
        pass
    
    # COMMENTED OUT: These properties conflict with instance variables
    # Uncomment and use these once handle_message() is fully refactored
    
    # @property
    # def connected(self) -> bool:
    #     """Legacy property - delegates to presenter state"""
    #     return self.presenter.get_state().connected
    # 
    # @connected.setter
    # def connected(self, value: bool):
    #     """Legacy property setter - updates through presenter"""
    #     pass  # State is managed by presenter now
    # 
    # @property
    # def user_id(self) -> Optional[str]:
    #     """Legacy property - delegates to presenter state"""
    #     return self.presenter.get_state().user_id
    # 
    # @property
    # def nickname(self) -> Optional[str]:
    #     """Legacy property - delegates to presenter state"""
    #     return self.presenter.get_state().nickname
    # 
    # @property
    # def users(self) -> dict:
    #     """Legacy property - delegates to presenter state"""
    #     return {user.user_id: {
    #         'nickname': user.nickname,
    #         'public_key': user.public_key,
    #         'status': user.status.value,
    #         'status_message': user.status_message
    #     } for user in self.presenter.get_users()}
    # 
    # @property
    # def current_channel(self) -> Optional[str]:
    #     """Legacy property - delegates to presenter state"""
    #     return self.presenter.get_state().current_channel
    # 
    # @property
    # def joined_channels(self) -> set:
    #     """Legacy property - delegates to presenter state"""
    #     return self.presenter.get_state().joined_channels
    # 
    # @property
    # def blocked_users(self) -> set:
    #     """Legacy property - delegates to presenter state"""
    #     return self.presenter.get_state().blocked_users
    
    # Presenter callback implementations (UI updates)
    def _on_connection_changed(self, success: bool, error: str):
        """Called when connection state changes"""
        if success:
            self.root.after(0, lambda: self._update_connection_status(True))
        else:
            self.root.after(0, lambda: self.log(f"Connection failed: {error}", "error"))
            self.root.after(0, self._on_disconnected)
    
    def _on_message_received(self, message: Message):
        """Called when a message is received"""
        self.root.after(0, lambda: self._display_message(message))
    
    def _on_user_list_updated(self, users: list[User]):
        """Called when user list changes"""
        self.root.after(0, lambda: self._update_user_list())
    
    def _on_channel_joined(self, channel: Channel):
        """Called when successfully joined a channel"""
        self.root.after(0, lambda: self._handle_channel_joined(channel))
    
    def _on_channel_left(self, channel_name: str):
        """Called when successfully left a channel"""
        self.root.after(0, lambda: self._handle_channel_left(channel_name))
    
    def _on_error(self, error_message: str):
        """Called when an error occurs"""
        # Check for special creator password error
        if error_message.startswith("CREATOR_PASSWORD_REQUIRED:"):
            actual_error = error_message.split(":", 1)[1]
            self.root.after(0, lambda: self._show_creator_password_dialog(actual_error))
        else:
            # Check if user is banned from a channel - remove from saved channels
            if "You are banned from" in error_message:
                # Extract channel name from "You are banned from {channel}"
                parts = error_message.split("You are banned from")
                if len(parts) > 1:
                    channel = parts[1].strip()
                    self._remove_channel_from_config(channel)
                    self.root.after(0, lambda: self.log(f"Removed {channel} from saved channels (banned)", "info"))
            
            self.root.after(0, lambda: self.log(f"Error: {error_message}", "error"))
    
    def _on_state_changed(self, state: ClientState):
        """Called when application state changes"""
        self.root.after(0, lambda: self.update_context_label())
    
    # UI update helper methods
    def _update_connection_status(self, connected: bool):
        """Update UI based on connection status"""
        # Update legacy state for backward compatibility
        self.connected = connected
        
        if connected:
            self.connect_btn.config(text="Disconnect", command=self.disconnect, state=tk.NORMAL)
            self.set_status("Connected")
            self.log("✓ Connected to server", "success")
            # Update channel list to show saved channels
            self._update_channel_list()
        else:
            self.connect_btn.config(text="Connect", command=self.connect, state=tk.NORMAL)
            self.set_status("Disconnected")
            # Don't log here - let _cleanup_after_disconnect handle it
    
    def _display_message(self, message: Message):
        """Display a received message in the UI"""
        # Extract sender_id from metadata if available
        sender_id = message.metadata.get('from_id') if message.metadata else None
        
        # Use existing log_chat method for consistent formatting
        if message.message_type == ModelMessageType.PRIVATE:
            self.log_chat(message.sender, message.content, msg_type="privmsg", sender_id=sender_id)
        elif message.message_type == ModelMessageType.CHANNEL:
            self.log_chat(message.sender, message.content, 
                         channel=message.recipient, msg_type="msg", sender_id=sender_id)
        else:
            self.log(f"{message.sender}: {message.content}")
    
    def _handle_channel_joined(self, channel: Channel):
        """Handle successful channel join"""
        # Update legacy current_channel for backward compatibility
        self.current_channel = channel.name
        
        # Update legacy joined_channels set
        self.joined_channels.add(channel.name)
        
        # Track if channel is password-protected
        if channel.password_protected:
            self.protected_channels.add(channel.name)
        
        # Initialize channel data structures
        if channel.name not in self.channel_users:
            self.channel_users[channel.name] = set()
        if channel.name not in self.channel_operators:
            self.channel_operators[channel.name] = set()
        if channel.name not in self.channel_mods:
            self.channel_mods[channel.name] = set()
        
        # Populate member data from channel object and sync users dict
        for member_id in channel.members:
            self.channel_users[channel.name].add(member_id)
            
            # Sync user info from state manager to legacy users dict
            user = self.presenter.state.get_user(member_id)
            if user and member_id not in self.users:
                self.users[member_id] = {
                    'nickname': user.nickname,
                    'public_key': user.public_key,
                    'status': user.status.value if hasattr(user.status, 'value') else str(user.status),
                    'status_message': user.status_message
                }
        
        # Populate operator/mod data
        for op_id in channel.operators:
            self.channel_operators[channel.name].add(op_id)
        for mod_id in channel.mods:
            self.channel_mods[channel.name].add(mod_id)
        
        # Track owner
        if channel.owner:
            self.channel_owners[channel.name] = channel.owner
        
        # Also update state manager to ensure consistency
        self.presenter.state.update_state(current_channel=channel.name)
        
        # Save channel to config for persistent rejoining
        self._save_channel_to_config(channel.name)
        
        self.log(f"✓ Joined {channel.name} ({len(channel.members)} members)", "success")
        self._update_channel_list()
        self._update_channel_user_list()
        self.update_context_label()
    
    def _handle_channel_left(self, channel_name: str):
        """Handle leaving a channel"""
        # Remove from legacy joined_channels set
        self.joined_channels.discard(channel_name)
        
        # Clear channel data structures
        if channel_name in self.channel_users:
            del self.channel_users[channel_name]
        if channel_name in self.channel_operators:
            del self.channel_operators[channel_name]
        if channel_name in self.channel_mods:
            del self.channel_mods[channel_name]
        if channel_name in self.channel_owners:
            del self.channel_owners[channel_name]
        if channel_name in self.protected_channels:
            self.protected_channels.discard(channel_name)
        
        # If this was the current channel, clear it
        if self.current_channel == channel_name:
            self.current_channel = None
            self._update_channel_user_list()  # Clear the user list
        
        # Remove channel from saved config
        self._remove_channel_from_config(channel_name)
        
        # Update UI
        self._update_channel_list()
        self.update_context_label()
        self.log(f"Left {channel_name}", "info")
    
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
    
    def show_notification(self, title, message):
        """Show desktop notification - cross-platform implementation"""
        # Check if notifications are enabled
        if not self.config.get("notifications", "enabled", default=True):
            return
        
        # Check if only notify when inactive
        if self.config.get("notifications", "only_when_inactive", default=True):
            # Check if window is focused
            try:
                if self.root.focus_displayof() is not None:
                    return  # Window has focus, don't notify
            except:
                pass  # If check fails, show notification anyway
        
        import platform
        import subprocess
        
        system = platform.system()
        
        try:
            if system == "Linux":
                # Use notify-send on Linux
                subprocess.run([
                    'notify-send',
                    '-a', 'JustIRC',
                    '-i', 'dialog-information',
                    title,
                    message
                ], check=False)
            elif system == "Darwin":  # macOS
                # Use osascript for macOS notifications
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(['osascript', '-e', script], check=False)
            elif system == "Windows":
                # Use PowerShell for Windows 10+ toast notifications
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                
                $template = @"
                <toast>
                    <visual>
                        <binding template="ToastText02">
                            <text id="1">{title}</text>
                            <text id="2">{message}</text>
                        </binding>
                    </visual>
                </toast>
"@
                
                $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                $xml.LoadXml($template)
                $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JustIRC").Show($toast)
                '''
                subprocess.run(['powershell', '-Command', ps_script], check=False, capture_output=True)
        except Exception as e:
            # Fallback: flash window and make sound
            try:
                self.root.bell()
                # Flash the window title
                original_title = self.root.title()
                self.root.title(f"💬 {title}")
                self.root.after(2000, lambda: self.root.title(original_title))
            except:
                pass
    
    def block_user(self, user_id: str):
        """Block a user (client-side filter) - Uses presenter"""
        asyncio.run_coroutine_threadsafe(
            self.presenter.block_user(user_id),
            self.loop
        )
        
        # Get nickname for logging
        users_dict = self.users
        nickname = users_dict.get(user_id, {}).get('nickname', user_id)
        self.log(f"Blocked user: {nickname}", "info")
    
    def unblock_user(self, user_id: str):
        """Unblock a user - Uses presenter"""
        asyncio.run_coroutine_threadsafe(
            self.presenter.unblock_user(user_id),
            self.loop
        )
        
        # Get nickname for logging
        users_dict = self.users
        nickname = users_dict.get(user_id, {}).get('nickname', user_id)
        self.log(f"Unblocked user: {nickname}", "info")
    
    def is_user_blocked(self, user_id: str) -> bool:
        """Check if a user is blocked - Uses presenter state"""
        return user_id in self.blocked_users
    
    def _handle_profile_response(self, message: dict):
        """Handle profile response from server"""
        nickname = message.get('nickname', 'Unknown')
        bio = message.get('bio')
        status_message = message.get('status_message')
        registered = message.get('registered', False)
        registration_date = message.get('registration_date')
        
        # Build profile display text
        profile_text = f"\n{'='*50}\n"
        profile_text += f"  Profile: {nickname}\n"
        profile_text += f"{'='*50}\n"
        
        if registered:
            profile_text += f"  ✓ Registered nickname\n"
            if registration_date:
                try:
                    # Format the date nicely
                    from datetime import datetime
                    reg_dt = datetime.fromisoformat(registration_date.replace('Z', '+00:00'))
                    profile_text += f"  Registered: {reg_dt.strftime('%Y-%m-%d')}\n"
                except Exception:
                    pass
        else:
            profile_text += f"  Unregistered nickname\n"
        
        if status_message:
            profile_text += f"  Status: {status_message}\n"
        
        if bio:
            profile_text += f"\n  Bio:\n"
            # Indent the bio text
            for line in bio.split('\n'):
                profile_text += f"    {line}\n"
        else:
            profile_text += f"  No bio set\n"
        
        profile_text += f"{'='*50}\n"
        
        self.root.after(0, lambda: self.log(profile_text, "info"))

    
    
    def show_window(self, icon=None, item=None):
        """Show the main window from system tray"""
        self.root.after(0, self._show_window_impl)
    
    def _show_window_impl(self):
        """Implementation of show_window on main thread"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def hide_window(self, icon=None, item=None):
        """Hide the main window to system tray"""
        self.root.after(0, self.root.withdraw)
    
    def on_closing(self):
        """Handle window close event - minimize to tray or quit"""
        if self.tray_manager.is_available() and self.config.get("ui", "minimize_to_tray_on_close", default=True):
            # Minimize to tray
            self.hide_window()
        else:
            # Actually quit
            self.quit_app()
    
    def quit_app(self, icon=None, item=None):
        """Quit the application completely"""
        self.running = False
        if self.tray_manager:
            self.tray_manager.stop()
        self.root.after(0, self.root.quit)
    
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
        file_menu.add_command(label="Set Status...", command=lambda: UIDialogs.show_status_dialog(self.root, self.config, self.send_status))
        file_menu.add_separator()
        file_menu.add_command(label="Settings", command=self.show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Help menu  
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Commands", command=self.show_help)
        help_menu.add_command(label="About", command=lambda: UIDialogs.show_about(self.root, self.config))
        
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
        self.channel_list.bind('<Double-Button-1>', self.on_channel_double_click)
        self.channel_list.bind('<Button-3>', self.on_channel_right_click)
        
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
        emoji_btn = ttk.Button(input_container, text="😊", command=lambda: UIDialogs.show_emoji_picker(self.root, self.config, self.message_entry), width=3)
        emoji_btn.pack(side=tk.LEFT, padx=(5, 0))
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
        self.chat_display.tag_config("mention", foreground=colors["accent"], font=('Consolas', 10, 'bold'))  # @mentions
        self.chat_display.tag_config("mention_self", foreground=colors["error"], background=colors["highlight"], font=('Consolas', 10, 'bold'))  # @you mentions
        
        # Message formatting tags
        self.chat_display.tag_config("format_bold", font=('Consolas', 10, 'bold'))
        self.chat_display.tag_config("format_italic", font=('Consolas', 10, 'italic'))
        self.chat_display.tag_config("format_code", foreground=colors["info"], background=colors["highlight"], font=('Consolas', 9))
        self.chat_display.tag_config("format_strike", overstrike=True)
        
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
        SettingsDialogs.show_settings(self.root, self.config, self.history, self.chat_display, self.apply_theme)
    
    def show_help(self):
        """Show help dialog with command list"""
        help_text = """Available Commands:

Channel Management:
  /join <channel> [password] [creator_password]
  /leave or /part - Leave current channel
  /topic <text> - Set channel topic
  /list - List all channels

Messaging:
  /msg <nickname> <message> - Send private message
  /me <action> - Send action message
  /image - Send image to user or channel

User Management:
  /users - List online users
  /whois <nickname> - Get user info
  /block <nickname> - Block a user
  /unblock <nickname> - Unblock a user
  /blocked - List blocked users

Operator Commands:
  /op <nickname> - Grant operator status
  /unop <nickname> - Remove operator status
  /mod <nickname> - Grant moderator status
  /unmod <nickname> - Remove moderator status
  /kick <nickname> [reason] - Kick user from channel
  /ban <nickname> [duration] [reason] - Ban user
  /kickban <nickname> [reason] - Kick and ban user
  /unban <nickname> - Unban user
  /mode <mode> [args] - Set channel mode
  /invite <nickname> - Invite user to channel
  /transfer <nickname> - Transfer ownership

Message History:
  /history [count] - Show message history
  /search <query> - Search message history
  /export <filename> - Export chat history

Other:
  /register <password> - Register account
  /profile <nickname> - View user profile
  /help - Show this help
  /quit - Disconnect from server
"""
        
        # Create help dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("IRC Commands Help")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        
        # Apply theme
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Create text widget with scrollbar
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(
            frame,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            bg=colors['chat_bg'],
            fg=colors['fg'],
            font=('Courier', 10),
            padx=10,
            pady=10
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        text_widget.insert('1.0', help_text)
        text_widget.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy, width=15).pack(pady=10)
    
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
            
        # Identify user from list - format is "symbol status_icon nickname"
        display_name = self.channel_user_list.get(selection[0])
        # Split and take last part (nickname) after removing role symbol and status icon
        parts = display_name.split()
        # The nickname is everything after the emojis (last part or parts joined if space in nickname)
        # Since nicknames can't have spaces in IRC, it's the last part
        nickname = parts[-1] if parts else display_name
        
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
        
        # Add block/unblock option
        if nickname != self.nickname:
            menu.add_separator()
            # Find user_id for this nickname
            user_id = None
            for uid, info in self.users.items():
                if info.get('nickname') == nickname:
                    user_id = uid
                    break
            
            if user_id:
                if self.is_user_blocked(user_id):
                    menu.add_command(label=f"❌ Unblock {nickname}", command=lambda: self.unblock_user(user_id))
                else:
                    menu.add_command(label=f"🚫 Block {nickname}", command=lambda: self.block_user(user_id))
        
        # Show menu
        menu.post(event.x_root, event.y_root)
        
        # Bind to destroy menu when clicking elsewhere
        def close_menu(e=None):
            menu.unpost()
            self.root.unbind('<Button-1>')
        
        self.root.bind('<Button-1>', close_menu)
        menu.bind('<FocusOut>', close_menu)
    
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
        """Grant operator status to user - server will prompt target for password"""
        if not self.connected or not self.current_channel:
            return
        
        # Send OP_USER message directly - server will prompt target user for password
        msg = Protocol.build_message(
            MessageType.OP_USER,
            channel=self.current_channel,
            target_nickname=nickname
        )
        asyncio.run_coroutine_threadsafe(
            self.send_to_server(msg),
            self.loop
        )
        self.log(f"Requesting to grant operator status to {nickname}...", "info")
    
    
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
    
    def _prompt_op_password(self, channel: str, is_new: bool, granted_by: str = None, is_mod: bool = False):
        """Prompt user for operator/mod password"""
        # Create dialog
        dialog = tk.Toplevel(self.root)
        
        # Set title based on context
        if granted_by:
            role_name = "Moderator" if is_mod else "Operator"
            dialog.title(f"{role_name} Role Granted")
        else:
            dialog.title("Operator Password Required")
        
        dialog.geometry("450x200")
        dialog.transient(self.root)
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Set prompt text based on context
        if granted_by:
            role_name = "moderator" if is_mod else "operator"
            if is_new:
                prompt_text = f"{granted_by} has granted you {role_name} status in {channel}"
                sub_text = f"Set your {role_name} password (4+ chars):"
            else:
                prompt_text = f"{granted_by} is granting you {role_name} status in {channel}"
                sub_text = f"Enter your {role_name} password:"
        else:
            if is_new:
                prompt_text = f"Set your operator password for {channel} (4+ chars):"
                sub_text = ""
            else:
                prompt_text = f"Enter your operator password for {channel}:"
                sub_text = ""
        
        ttk.Label(dialog, text=prompt_text, font=('Arial', 10, 'bold')).pack(pady=15)
        if sub_text:
            ttk.Label(dialog, text=sub_text, font=('Arial', 9)).pack(pady=(0, 10))
        
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
            # User refused to provide password
            if granted_by:
                self.log(f"You declined the {'moderator' if is_mod else 'operator'} role in {channel}", "error")
            else:
                self.log("Operator authentication cancelled - you will be disconnected", "error")
        
        ttk.Button(btn_frame, text="Submit", command=submit, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side=tk.LEFT)
        
        password_entry.bind('<Return>', lambda e: submit())
        
        # Ensure dialog is rendered before grabbing focus
        dialog.update_idletasks()
        dialog.grab_set()
    
    
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
    
    def log_chat(self, sender: str, message: str, channel: str = None, msg_type: str = "msg", sender_id: str = None):
        """Add structured chat message with colored nickname"""
        from datetime import datetime
        
        # If sender_id not provided, try to look it up
        if sender_id is None:
            for uid, info in self.users.items():
                if info.get('nickname') == sender:
                    sender_id = uid
                    break
        
        # Check if sender is blocked (client-side filter)
        if sender_id and self.is_user_blocked(sender_id):
            return  # Silently ignore messages from blocked users
        
        # Save to history if enabled
        if self.history:
            try:
                self.history.add_message(
                    sender=sender, 
                    content=message, 
                    channel=channel, 
                    message_type=msg_type
                )
            except Exception as e:
                print(f"Failed to save message to history: {e}")
        
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp
        if self.config.get("ui", "show_timestamps", default=True):
            timestamp = datetime.now().strftime("[%H:%M:%S] ")
            self.chat_display.insert(tk.END, timestamp, "timestamp")
        
        # Add channel prefix if needed (e.g. strict format)
        if channel:
            self.chat_display.insert(tk.END, f"[{channel}] ", "channel")
        
        # Determine sender role and get appropriate symbol
        role_symbol = ""
        if sender_id and channel:
            # Check if user has a role in this channel
            is_owner = self.channel_owners.get(channel) == sender_id
            is_op = sender_id in self.channel_operators.get(channel, set())
            is_mod = sender_id in self.channel_mods.get(channel, set())
            role_symbol = self.config.get_role_symbol(is_owner=is_owner, is_op=is_op, is_mod=is_mod)
        
        # Determine sender color and tag
        nick_color = self.config.get_nick_color(sender)
        nick_tag = f"nick_{sender}"
        try:
            self.chat_display.tag_config(nick_tag, foreground=nick_color, font=('Consolas', 10, 'bold'))
        except:
            pass
            
        # Insert Nickname with role symbol
        if msg_type == "action":
            self.chat_display.insert(tk.END, "* ", "action")
            if role_symbol:
                self.chat_display.insert(tk.END, f"{role_symbol} ", "role_icon")
            self.chat_display.insert(tk.END, sender, nick_tag)
            self.chat_display.insert(tk.END, f" {message}\n", "action")
        else:
            if role_symbol:
                self.chat_display.insert(tk.END, f"{role_symbol} ", "role_icon")
            self.chat_display.insert(tk.END, f"<{sender}> ", nick_tag)
            # Process message for @mentions
            mentioned_me = self._insert_message_with_mentions(message)
            
            # Show notification if user was mentioned
            if mentioned_me and self.config.get("notifications", "on_mention", default=True):
                self.show_notification(
                    f"Mentioned in {channel or 'chat'}",
                    f"{sender}: {message[:100]}{'...' if len(message) > 100 else ''}"
                )
            
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    def _insert_message_with_mentions(self, message: str):
        """Insert message text with formatting and highlighted @mentions. Returns True if current user was mentioned."""
        import re
        
        mentioned_me = False
        
        # First, split by @mentions
        mention_pattern = r'(@\w+)'
        parts = re.split(mention_pattern, message)
        
        for part in parts:
            if part.startswith('@'):
                # This is a mention
                username = part[1:]
                
                # Check if it's mentioning the current user
                if self.nickname and username.lower() == self.nickname.lower():
                    self.chat_display.insert(tk.END, part, "mention_self")
                    mentioned_me = True
                else:
                    self.chat_display.insert(tk.END, part, "mention")
            else:
                # Regular text - apply formatting
                formatted_parts = self.formatter.parse_message(part)
                
                for text, fmt in formatted_parts:
                    if fmt == 'normal':
                        self.chat_display.insert(tk.END, text, "self_msg")
                    elif fmt == 'bold':
                        self.chat_display.insert(tk.END, text, "format_bold")
                    elif fmt == 'italic':
                        self.chat_display.insert(tk.END, text, "format_italic")
                    elif fmt == 'code':
                        self.chat_display.insert(tk.END, text, "format_code")
                    elif fmt == 'strikethrough':
                        self.chat_display.insert(tk.END, text, "format_strike")
        
        self.chat_display.insert(tk.END, "\n")
        
        # Play sound and show notification if user was mentioned
        if mentioned_me:
            # Play sound if enabled
            if self.config.get("notifications", "sound_enabled", default=True):
                try:
                    self.root.bell()
                except:
                    pass
        
        return mentioned_me

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
        """Connect to server - Uses presenter"""
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
        
        # Disable connection controls
        self.connect_btn.config(state=tk.DISABLED)
        self.server_entry.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.DISABLED)
        self.nick_entry.config(state=tk.DISABLED)
        
        # Setup event loop if needed
        if self.loop is None:
            self.running = True
            thread = threading.Thread(target=self._run_async_loop, args=(server, port, nickname), daemon=True)
            thread.start()
        else:
            # Use existing loop - create ConnectionConfig for presenter
            from models import ConnectionConfig
            config = ConnectionConfig(
                host=server,
                port=port,
                nickname=nickname
            )
            asyncio.run_coroutine_threadsafe(
                self.presenter.connect(config),
                self.loop
            )
        
        # Save last server to config
        self.config.set("server", "last_server", value=server)
        self.config.set("server", "last_port", value=str(port))
        self.config.set("server", "last_nickname", value=nickname)
        
        self.log(f"Connecting to {server}:{port}...", "info")
    
    def _run_async_loop(self, server: str, port: int, nickname: str):
        """Run asyncio event loop in thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._connect_via_presenter(server, port, nickname))
            # Keep loop running for async operations
            self.loop.run_forever()
        except Exception as e:
            self.log(f"Connection error: {e}", "error")
        finally:
            self.loop.close()
            self.running = False
    
    async def _connect_via_presenter(self, server: str, port: int, nickname: str):
        """Connect to server via presenter"""
        from models import ConnectionConfig
        try:
            config = ConnectionConfig(
                host=server,
                port=port,
                nickname=nickname
            )
            await self.presenter.connect(config)
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Connection failed: {e}", "error"))
            self.root.after(0, self._on_disconnected)
    
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
        """Send message to server - Uses NetworkService"""
        try:
            network = self.container.resolve(NetworkService)
            if network.connected:
                await network.send(message)
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Failed to send: {e}", "error"))
    
    async def handle_message(self, message: dict):
        """Handle incoming message"""
        msg_type = message.get('type')
        
        if msg_type == MessageType.ACK.value:
            if 'user_id' in message:
                self.user_id = message['user_id']
                
                # Set nickname from state manager (set by presenter during connection)
                state = self.presenter.state.get_state()
                if state.nickname:
                    self.nickname = state.nickname
                
                # Add self to users dict for proper role display
                if self.user_id and self.nickname:
                    self.users[self.user_id] = {
                        'nickname': self.nickname,
                        'public_key': self.crypto.get_public_key_b64(),
                        'status': 'online',
                        'status_message': ''
                    }
                
                welcome_msg = message.get('message', 'Registered')
                self.root.after(0, lambda: self.log(welcome_msg, "success"))
                
                # Display server description if provided
                if 'description' in message and message['description']:
                    description = message['description']
                    self.root.after(0, lambda: self.log("\n" + description + "\n", "info"))
            
            elif 'channel' in message:
                # Legacy ACK for channel join - skip as presenter handles JOIN_CHANNEL
                # Just log for debugging
                pass
        
        elif msg_type == MessageType.USER_LIST.value:
            users = message.get('users', [])
            for user in users:
                self.users[user['user_id']] = {
                    'nickname': user['nickname'],
                    'public_key': user['public_key'],
                    'status': user.get('status', 'online'),
                    'status_message': user.get('status_message', '')
                }
                self.crypto.load_peer_public_key(user['user_id'], user['public_key'])
            
            self.root.after(0, self._update_user_list)
            self.root.after(0, lambda: self.log(f"{len(users)} users online", "info"))
        
        elif msg_type == MessageType.STATUS_UPDATE.value:
            # User status changed
            user_id = message.get('user_id')
            nickname = message.get('nickname')
            status = message.get('status', 'online')
            status_message = message.get('custom_message', '')
            
            if user_id and user_id in self.users:
                self.users[user_id]['status'] = status
                self.users[user_id]['status_message'] = status_message
                
                # Update UI
                self.root.after(0, self._update_user_list)
                self.root.after(0, self._update_channel_user_list)
                
                # Log status change
                status_icons = {'online': '🟢', 'away': '🟡', 'busy': '🔴', 'dnd': '⛔'}
                icon = status_icons.get(status, '🟢')
                msg_text = f"{icon} {nickname} is now {status}"
                if status_message:
                    msg_text += f": {status_message}"
                self.root.after(0, lambda: self.log(msg_text, "info"))
        
        elif msg_type == MessageType.PRIVATE_MESSAGE.value:
            from_id = message['from_id']
            try:
                plaintext = self.crypto.decrypt(from_id, message['encrypted_data'], message['nonce'])
                sender = self.users.get(from_id, {}).get('nickname', from_id)
                
                # Show notification for private message
                if self.config.get("notifications", "on_pm", default=True):
                    self.show_notification(
                        f"Private message from {sender}",
                        plaintext[:100] + ('...' if len(plaintext) > 100 else '')
                    )
                
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
            
            # Remove from operator/mod lists
            if channel in self.channel_operators:
                self.channel_operators[channel].discard(user_id)
            if channel in self.channel_mods:
                self.channel_mods[channel].discard(user_id)
            
            # If we left the channel, update our state
            if user_id == self.user_id:
                self.joined_channels.discard(channel)
                if self.current_channel == channel:
                    self.current_channel = None
                self.root.after(0, self._update_channel_list)  # Update UI
                self.root.after(0, self.update_context_label)
                self.root.after(0, lambda: self.log(f"Left {channel}", "info"))
            else:
                # Someone else left
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
            
            # Remove from all channel tracking (iterate over channel names, not values)
            for channel_name in list(self.channel_users.keys()):
                self.channel_users[channel_name].discard(user_id)
            
            # Remove from operator and mod tracking
            for channel_name in list(self.channel_operators.keys()):
                self.channel_operators[channel_name].discard(user_id)
            for channel_name in list(self.channel_mods.keys()):
                self.channel_mods[channel_name].discard(user_id)
            
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
        
        elif msg_type == MessageType.PROFILE_RESPONSE.value:
            self._handle_profile_response(message)
        
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
            
            # If this is us, update our saved channel config
            if user_id == self.user_id:
                self._save_channel_to_config(channel)
            
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
            
            # If this is us, update our saved channel config
            if user_id == self.user_id:
                self._save_channel_to_config(channel)
            
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
            
            # If this is us, update our saved channel config
            if user_id == self.user_id:
                self._save_channel_to_config(channel)
            
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
            
            # If this is us, update our saved channel config
            if user_id == self.user_id:
                self._save_channel_to_config(channel)
            
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
        
        elif msg_type == MessageType.SET_TOPIC.value:
            # Topic was changed
            channel = message.get('channel')
            topic = message.get('topic', '')
            set_by = message.get('set_by', 'someone')
            
            if topic:
                self.root.after(0, lambda c=channel, t=topic, s=set_by: 
                              self.log(f"[{c}] Topic changed by {s}: {t}", "info"))
            else:
                self.root.after(0, lambda c=channel, s=set_by:
                              self.log(f"[{c}] Topic cleared by {s}", "info"))
        
        elif msg_type == MessageType.MODE_CHANGE.value:
            channel = message.get('channel')
            mode = message.get('mode')
            enabled = message.get('enabled')
            set_by = message.get('set_by', 'unknown')
            
            mode_names = {
                'm': 'moderated',
                's': 'secret',
                'i': 'invite-only',
                'n': 'no external messages',
                'p': 'private'
            }
            mode_name = mode_names.get(mode, mode)
            action = "enabled" if enabled else "disabled"
            prefix = '+' if enabled else '-'
            
            self.root.after(0, lambda c=channel, m=mode, n=mode_name, a=action, s=set_by, p=prefix: 
                          self.log(f"[{c}] {s} {a} mode {p}{m} ({n})", "system"))
        
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
        
        elif msg_type == MessageType.INVITE_USER.value:
            # You were invited to a channel
            channel = message.get('channel')
            inviter_nickname = message.get('inviter_nickname')
            inviter_id = message.get('inviter_id')
            
            # Show invite dialog
            self.root.after(0, lambda: UIDialogs.show_invite_dialog(self.root, channel, inviter_nickname, inviter_id, self.send_invite_response))
        
        elif msg_type == MessageType.OP_PASSWORD_REQUEST.value:
            channel = message.get('channel')
            action = message.get('action')
            granted_by = message.get('granted_by')  # Who is granting the role
            is_mod = message.get('is_mod', False)  # Is this for mod role?
            
            # Request password from user
            if action == 'set':
                self.root.after(0, lambda: self._prompt_op_password(channel, is_new=True, granted_by=granted_by, is_mod=is_mod))
            else:  # verify
                self.root.after(0, lambda: self._prompt_op_password(channel, is_new=False, granted_by=granted_by, is_mod=is_mod))
        
        # Note: ERROR messages are handled by presenter._handle_error()
        # which calls _on_error() callback to log the error
    
    def _update_channel_list(self):
        """Update channel list box"""
        self.channel_list.delete(0, tk.END)
        
        # First, add joined channels (only when connected)
        if self.connected:
            for channel in sorted(self.joined_channels):
                # Add padlock symbol for protected channels
                display_name = f"🔒 {channel}" if channel in self.protected_channels else channel
                self.channel_list.insert(tk.END, display_name)
        
        # Then, add saved channels we're not currently in (show always for easy access)
        saved_channels = self.config.get("saved_channels", default={})
        for channel in sorted(saved_channels.keys()):
            if channel not in self.joined_channels:
                # Show with a different indicator (dim/italics not available, use prefix)
                display_name = f"💾 {channel}"
                self.channel_list.insert(tk.END, display_name)
    
    def _update_user_list(self):
        """Update user list box with status icons"""
        self.user_list.delete(0, tk.END)
        
        status_icons = {
            'online': '🟢',
            'away': '🟡',
            'busy': '🔴',
            'dnd': '⛔'
        }
        
        for user_id, info in self.users.items():
            status = info.get('status', 'online')
            icon = status_icons.get(status, '🟢')
            display_name = f"{icon} {info['nickname']}"
            self.user_list.insert(tk.END, display_name)
    
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
        
        # Add to listbox with symbols and status icons
        status_icons = {
            'online': '🟢',
            'away': '🟡',
            'busy': '🔴',
            'dnd': '⛔'
        }
        
        for i, (nickname, user_id, is_owner, is_op, is_mod) in enumerate(members_with_info):
            symbol = self.config.get_role_symbol(is_owner=is_owner, is_op=is_op, is_mod=is_mod)
            
            # Get status icon
            user_info = self.users.get(user_id, {})
            status = user_info.get('status', 'online')
            status_icon = status_icons.get(status, '🟢')
            
            display_name = f"{symbol} {status_icon} {nickname}"
            
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
            # Strip any emoji prefixes (🔒 for protected, 💾 for saved)
            channel = display_name.replace('🔒 ', '').replace('💾 ', '')
            self.current_channel = channel
            self.current_recipient = None  # Clear PM mode
            self.set_status(f"Channel: {self.current_channel}")
            self.update_context_label()
            self._update_channel_user_list()  # Update channel users display
    
    def on_channel_double_click(self, event):
        """Handle double-click on channel to rejoin if not currently in it"""
        selection = self.channel_list.curselection()
        if not selection:
            return
        
        idx = selection[0]
        display_name = self.channel_list.get(idx)
        # Strip any emoji prefixes (🔒 for protected, 💾 for saved)
        channel = display_name.replace('🔒 ', '').replace('💾 ', '')
        
        # If we're already in this channel, switch to it
        if channel in self.joined_channels:
            self.current_channel = channel
            self.current_recipient = None
            self.set_status(f"Channel: {self.current_channel}")
            self.update_context_label()
            self._update_channel_user_list()
        else:
            # Not in channel yet - check if connected first
            if not self.connected:
                messagebox.showinfo("Not Connected", 
                                   f"Please connect to the server before joining {channel}")
                return
            
            # Try to rejoin - server will handle authentication
            # Server will prompt for operator_password if user has operator/mod status
            asyncio.run_coroutine_threadsafe(
                self._join_channel(channel, password=None),
                self.loop
            )
    
    def on_channel_right_click(self, event):
        """Handle right-click on channel to show context menu"""
        # Select the item under cursor
        idx = self.channel_list.nearest(event.y)
        if idx >= 0:
            self.channel_list.selection_clear(0, tk.END)
            self.channel_list.selection_set(idx)
            
            display_name = self.channel_list.get(idx)
            # Strip any emoji prefixes (🔒 for protected, 💾 for saved)
            channel = display_name.replace('🔒 ', '').replace('💾 ', '')
            
            # Show context menu
            menu = tk.Menu(self.root, tearoff=0)
            
            if channel in self.joined_channels:
                menu.add_command(label=f"Leave {channel}", command=lambda: self._leave_channel_from_menu(channel))
            else:
                menu.add_command(label=f"Rejoin {channel}", command=lambda: self._rejoin_channel_from_menu(channel))
                menu.add_command(label=f"Join as Owner (creator password)", command=lambda: self._prompt_operator_password_for_rejoin(channel, is_owner=True))
                menu.add_separator()
                menu.add_command(label=f"Remove from saved", command=lambda: self._remove_channel_from_config(channel))
            
            menu.post(event.x_root, event.y_root)
    
    def _leave_channel_from_menu(self, channel: str):
        """Leave a channel from right-click menu"""
        asyncio.run_coroutine_threadsafe(
            self.presenter.leave_channel(channel),
            self.loop
        )
    
    def _rejoin_channel_from_menu(self, channel: str):
        """Rejoin a channel from right-click menu"""
        # Check if connected first
        if not self.connected:
            messagebox.showinfo("Not Connected", 
                               f"Please connect to the server before joining {channel}")
            return
        
        # Check if user had a role that requires operator password
        # Try to rejoin - server will handle authentication
        # Server will prompt for operator_password if user has operator/mod status
        asyncio.run_coroutine_threadsafe(
            self._join_channel(channel, password=None),
            self.loop
        )
    
    def _prompt_operator_password_for_rejoin(self, channel: str, is_owner: bool = False):
        """Prompt for creator password when rejoining a channel as owner"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Rejoin {channel}")
        dialog.geometry("450x220")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        ttk.Label(dialog, text=f"Enter creator password for {channel}:", 
                 font=('Segoe UI', 10, 'bold')).pack(pady=15)
        ttk.Label(dialog, text="(Required because you are the channel owner)", 
                 font=('Segoe UI', 8)).pack(pady=(0, 10))
        
        password_entry = ttk.Entry(dialog, show="*", width=40)
        password_entry.pack(pady=15, padx=20)
        
        def on_submit():
            password = password_entry.get()
            if password:
                dialog.destroy()
                # Pass password as creator_password to regain owner status
                asyncio.run_coroutine_threadsafe(
                    self._join_channel(channel, password=None, creator_password=password),
                    self.loop
                )
            else:
                messagebox.showwarning("Warning", "Password required", parent=dialog)
        
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Rejoin", command=on_submit, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        password_entry.bind('<Return>', lambda e: on_submit())
        password_entry.bind('<Escape>', lambda e: on_cancel())
        
        # Make dialog modal and set focus after all widgets are created
        dialog.update_idletasks()  # Ensure window is rendered
        dialog.grab_set()
        password_entry.focus()
    
    def on_user_double_click(self, event):
        """Handle double-click on user (start PM)"""
        selection = self.user_list.curselection()
        if selection:
            display_name = self.user_list.get(selection[0])
            # Extract nickname from "status_icon nickname" format
            parts = display_name.split()
            nickname = parts[-1] if parts else display_name
            self.current_channel = None  # Switch to PM mode
            self.current_recipient = nickname
            self.set_status(f"PM to: {nickname}")
            self.update_context_label()
            self.message_entry.focus()
    
    def send_message(self):
        """Send message or execute command - Uses presenter"""
        text = self.message_entry.get().strip()
        if not text or not self.connected:
            return
        
        # Handle IRC commands
        if text.startswith('/'):
            self.message_entry.delete(0, tk.END)
            asyncio.run_coroutine_threadsafe(
                self.command_handler.handle_command(text),
                self.loop
            )
            return
        
        # Normal message via presenter
        if not self.loop:
            self.log("Not connected", "error")
            return
        
        # Send via presenter
        asyncio.run_coroutine_threadsafe(
            self.presenter.send_message(text),
            self.loop
        )
        
        self.message_entry.delete(0, tk.END)
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string like '30m', '1h', '2h30m' into seconds.
        Returns None if parsing fails."""
        import re
        
        try:
            # Match patterns like: 1h, 30m, 1h30m, 2h15m
            pattern = r'^(?:(\d+)h)?(?:(\d+)m)?$'
            match = re.match(pattern, duration_str.lower())
            
            if not match:
                return None
            
            hours, minutes = match.groups()
            total_seconds = 0
            
            if hours:
                total_seconds += int(hours) * 3600
            if minutes:
                total_seconds += int(minutes) * 60
            
            # Must have at least some duration
            return total_seconds if total_seconds > 0 else None
            
        except:
            return None
    
    async def _send_channel_message(self, channel: str, text: str):
        """Send message to channel - DEPRECATED: Use presenter"""
        # This method is kept for backward compatibility with command handler
        # New code should use presenter.send_message() directly
        await self.presenter.send_message(text)
    
    async def _send_status_update(self, status: str, custom_message: str = ""):
        """Send status update to server"""
        try:
            msg = Protocol.set_status(status, custom_message)
            await self.send_to_server(msg)
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.log(f"Failed to update status: {error_msg}", "error"))
    
    def send_status(self, status: str, custom_message: str = ""):
        """Callback for status dialog - updates local state and sends to server"""
        # Update local state
        self.current_status = status
        self.current_status_message = custom_message
        
        # Send to server
        if self.loop and self.running:
            asyncio.run_coroutine_threadsafe(
                self._send_status_update(status, custom_message),
                self.loop
            )
        
        # Show confirmation
        status_names = {
            "online": "🟢 Online",
            "away": "🟡 Away", 
            "busy": "🔴 Busy",
            "dnd": "⛔ Do Not Disturb"
        }
        self.log(f"Status set to: {status_names.get(status, status)}", "success")
    
    def send_invite_response(self, channel: str, inviter_nickname: str, accepted: bool):
        """Callback for invite dialog - sends response to server"""
        msg = Protocol.invite_response(channel, inviter_nickname, accepted)
        asyncio.run_coroutine_threadsafe(
            self.send_to_server(msg),
            self.loop
        )
        if accepted:
            self.log(f"Joined {channel}", "success")
        else:
            self.log(f"Declined invite to {channel}", "system")
    
    def insert_emoji(self, emoji: str):
        """Callback for emoji picker - inserts emoji at cursor position"""
        cursor_pos = self.message_entry.index(tk.INSERT)
        self.message_entry.insert(cursor_pos, emoji)
        self.message_entry.focus()

    
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
        
        # Get display name and strip status emoji
        display_name = self.user_list.get(selection[0])
        # Extract nickname from "status_icon nickname" format
        parts = display_name.split()
        target_nickname = parts[-1] if parts else display_name
        
        # Create dialog to get operator password for the new operator
        dialog = tk.Toplevel(self.root)
        dialog.title("Grant Operator Status")
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
        """Send private message to user -  DEPRECATED: Use presenter"""
        # This method is kept for backward compatibility with command handler
        # New code should use presenter.send_private_message_to() directly
        await self.presenter.send_private_message_to(target_nickname, text)
    

    
    def _show_creator_password_dialog(self, error_msg: str):
        """Show creator password dialog when creating a new channel"""
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("New Channel - Set Creator Password")
        dialog.geometry("450x220")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        # Info frame
        info_frame = ttk.Frame(dialog, padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            info_frame,
            text="Creating a new channel requires a creator password.",
            font=('Arial', 10, 'bold')
        ).pack(pady=(0, 5))
        
        ttk.Label(
            info_frame,
            text="This password lets you regain operator status if you rejoin later.",
            font=('Arial', 9),
            wraplength=400
        ).pack(pady=(0, 15))
        
        # Password entry
        ttk.Label(info_frame, text="Creator Password (4+ characters):").pack(anchor=tk.W)
        password_entry = ttk.Entry(info_frame, width=40, show='*')
        password_entry.pack(fill=tk.X, pady=5)
        password_entry.focus()
        
        # Store the last attempted channel
        last_channel = getattr(self, '_last_join_attempt', None)
        
        result = {'password': None, 'cancelled': False}
        
        def on_create():
            password = password_entry.get().strip()
            if len(password) < 4:
                messagebox.showerror("Error", "Password must be at least 4 characters")
                return
            result['password'] = password
            dialog.destroy()
        
        def on_cancel():
            result['cancelled'] = True
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Create Channel", command=on_create, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=15).pack(side=tk.LEFT, padx=5)
        
        password_entry.bind('<Return>', lambda e: on_create())
        
        dialog.wait_window()
        
        # If user provided password and didn't cancel, retry the join with creator_password
        if result['password'] and not result['cancelled'] and last_channel:
            asyncio.run_coroutine_threadsafe(
                self._join_channel(last_channel, password=None, creator_password=result['password']),
                self.loop
            )
    
    def join_channel_dialog(self):
        """Show join channel dialog"""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to server")
            return
        
        # Create simple dialog for channel name and optional password
        dialog = tk.Toplevel(self.root)
        dialog.title("Join Channel")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply theme colors
        colors = self.config.get_theme_colors()
        dialog.config(bg=colors['bg'])
        
        ttk.Label(dialog, text="Channel name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        channel_entry = ttk.Entry(dialog, width=30)
        channel_entry.grid(row=0, column=1, padx=10, pady=10)
        channel_entry.focus()
        
        ttk.Label(dialog, text="Password (if protected):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.grid(row=1, column=1, padx=10, pady=5)
        
        result = {'channel': None, 'password': None}
        
        def on_join():
            channel = channel_entry.get().strip()
            # Prepend '#' if not already present
            if channel and not channel.startswith('#'):
                channel = '#' + channel
            password = password_entry.get().strip() or None
            
            result['channel'] = channel
            result['password'] = password
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Join", command=on_join).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        channel_entry.bind('<Return>', lambda e: on_join())
        password_entry.bind('<Return>', lambda e: on_join())
        
        dialog.wait_window()
        
        if result['channel']:
            asyncio.run_coroutine_threadsafe(
                self._join_channel(result['channel'], result['password']),
                self.loop
            )
    
    async def _join_channel(self, channel: str, password: str = None, creator_password: str = None):
        """Join a channel - Uses presenter"""
        # Store the last join attempt for potential creator password retry
        self._last_join_attempt = channel
        await self.presenter.join_channel(channel, password, creator_password)
    
    def leave_channel(self):
        """Leave current channel - Uses presenter"""
        if not self.current_channel:
            messagebox.showwarning("Warning", "No channel selected")
            return
        
        asyncio.run_coroutine_threadsafe(
            self.presenter.leave_channel(self.current_channel),
            self.loop
        )
    
    async def _leave_channel(self, channel: str):
        """Leave a channel - DEPRECATED: Use presenter"""
        await self.presenter.leave_channel(channel)
    
    def _save_channel_to_config(self, channel_name: str):
        """Save a channel to config for persistent rejoining
        
        Note: Only saves timestamp. Server determines ALL roles on rejoin.
        """
        saved_channels = self.config.get("saved_channels", default={})
        
        # Only save timestamp - server is the source of truth for all roles
        saved_channels[channel_name] = {
            "joined_at": str(int(time.time()))
        }
        self.config.set("saved_channels", value=saved_channels)
    
    def _remove_channel_from_config(self, channel_name: str):
        """Remove a channel from saved config"""
        saved_channels = self.config.get("saved_channels", default={})
        if channel_name in saved_channels:
            del saved_channels[channel_name]
            self.config.set("saved_channels", value=saved_channels)
            # Update UI to remove the channel from list
            self._update_channel_list()
    
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
        
        display_name = self.user_list.get(selection[0])
        # Extract nickname from "status_icon nickname" format
        parts = display_name.split()
        nickname = parts[-1] if parts else display_name
        
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
        """Disconnect from server - Uses presenter"""
        if not self.connected:
            return
            
        self.running = False
        self.connected = False
        
        # Disable button during disconnection
        self.connect_btn.config(state=tk.DISABLED)
        self.server_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
        self.nick_entry.config(state=tk.NORMAL)
        self.set_status("Disconnecting...")
        
        # Disconnect via presenter which will close the connection
        # This will cause the receive loop to exit naturally
        if self.loop and not self.loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(
                    self.presenter.disconnect(),
                    self.loop
                )
            except Exception as e:
                print(f"Disconnect error: {e}")
        
        # Clean up UI and re-enable connect button
        self.root.after(100, self._cleanup_after_disconnect)
    
    def _stop_event_loop(self):
        """Stop the event loop if it exists"""
        if self.loop and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self.loop.stop)
            except:
                pass
    
    def _cleanup_after_disconnect(self):
        """Clean up UI after disconnect"""
        # Update button back to Connect mode
        self.connect_btn.config(text="Connect", command=self.connect, state=tk.NORMAL)
        
        # Clear user lists but keep channel list with saved channels
        self._update_channel_list()  # Show saved channels
        self.user_list.delete(0, tk.END)
        self.channel_user_list.delete(0, tk.END)
        self.set_status("Disconnected")
        self.log("Disconnected from server", "info")
        self.update_context_label()
    
    def _on_disconnected(self):
        """Handle disconnection event"""
        # Just update connection status, don't duplicate cleanup
        self._update_connection_status(False)
        self.connect_btn.config(state=tk.NORMAL)
        self.server_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
        self.nick_entry.config(state=tk.NORMAL)


def main():
    """Main entry point"""
    root = tk.Tk()
    app = IRCClientGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

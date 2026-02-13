"""
System Tray Manager for JustIRC
Handles system tray icon and menu
"""

import threading

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


class SystemTrayManager:
    """Manages system tray icon and interactions"""
    
    def __init__(self, root, show_window_callback, hide_window_callback, quit_callback):
        """
        Initialize system tray manager
        
        Args:
            root: Main tkinter window
            show_window_callback: Function to show the main window
            hide_window_callback: Function to hide the main window
            quit_callback: Function to quit the application
        """
        self.root = root
        self.show_window_callback = show_window_callback
        self.hide_window_callback = hide_window_callback
        self.quit_callback = quit_callback
        self.tray_icon = None
    
    def is_available(self):
        """Check if system tray is available"""
        return TRAY_AVAILABLE
    
    def setup(self):
        """Setup system tray icon"""
        if not TRAY_AVAILABLE:
            return False
        
        try:
            # Create and start tray icon in separate thread
            icon_image = self._create_icon_image()
            self.tray_icon = pystray.Icon("JustIRC", icon_image, "JustIRC", self._create_menu())
            
            # Run tray in background thread
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            return True
        except Exception as e:
            print(f"Failed to setup system tray: {e}")
            return False
    
    def _create_icon_image(self):
        """Create the system tray icon image"""
        # Create a 64x64 image with a shield icon
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color=(43, 43, 43))
        draw = ImageDraw.Draw(image)
        
        # Draw a simple shield
        draw.polygon([
            (32, 10),  # Top
            (50, 20),  # Top right
            (50, 45),  # Bottom right
            (32, 54),  # Bottom
            (14, 45),  # Bottom left
            (14, 20)   # Top left
        ], fill=(0, 120, 212), outline=(255, 255, 255))
        
        return image
    
    def _create_menu(self):
        """Create the system tray menu"""
        return pystray.Menu(
            pystray.MenuItem("Show", self.show_window_callback),
            pystray.MenuItem("Hide", self.hide_window_callback),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit_callback)
        )
    
    def stop(self):
        """Stop the system tray icon"""
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass

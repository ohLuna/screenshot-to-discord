#!/usr/bin/env python3
"""
Application Screenshot Discord Bot
Takes screenshots of a specific application and sends them to Discord webhook
Interactive configuration menu with GUI option
"""

import os
import time
import requests
from datetime import datetime
import sys
import threading

# Platform-specific imports
try:
    import pyautogui
    import psutil
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install pyautogui psutil")
    sys.exit(1)

# GUI imports (optional)
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# Windows-specific imports
if sys.platform == "win32":
    try:
        import pygetwindow as gw
        import win32gui
        import win32ui
        import win32con
        from PIL import Image
    except ImportError as e:
        print(f"Missing Windows-specific package: {e}")
        print("Install with: pip install pygetwindow pywin32 Pillow")
        sys.exit(1)

# macOS-specific imports
elif sys.platform == "darwin":
    try:
        from AppKit import NSWorkspace, NSApplicationActivationPolicyRegular
        import Quartz
        from PIL import Image
    except ImportError as e:
        print(f"Missing macOS-specific package: {e}")
        print("Install with: pip install pyobjc Pillow")
        sys.exit(1)

# Linux-specific imports
else:
    try:
        import subprocess
        from PIL import Image
    except ImportError as e:
        print(f"Missing Linux-specific package: {e}")
        print("Install with: pip install Pillow")
        sys.exit(1)


class ApplicationScreenshotter:
    def __init__(self):
        self.webhook_url = ""
        self.app_name = ""
        self.interval = 60
        self.delete_after_send = True
        self.running = False
        self.monitor_thread = None
        
    def find_application_window(self):
        """Find the application window based on platform"""
        if sys.platform == "win32":
            return self._find_window_windows()
        elif sys.platform == "darwin":
            return self._find_window_macos()
        else:
            return self._find_window_linux()
    
    def _find_window_windows(self):
        """Find application window on Windows"""
        try:
            # First try to find by window title
            windows = gw.getAllWindows()
            matching_windows = []
            
            for window in windows:
                if (window.title and 
                    self.app_name in window.title.lower() and 
                    window.visible and 
                    window.width > 0 and window.height > 0):
                    matching_windows.append(window)
            
            if matching_windows:
                # Prefer non-minimized windows
                for window in matching_windows:
                    if not window.isMinimized:
                        return window
                return matching_windows[0]  # Return first match if all are minimized
            
            # If no window title match, try by process name
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    proc_name = proc.info['name'].lower()
                    if self.app_name in proc_name or proc_name.replace('.exe', '') == self.app_name:
                        # Find window associated with this process
                        def enum_windows_callback(hwnd, pid):
                            if win32gui.GetWindowThreadProcessId(hwnd)[1] == pid:
                                window_title = win32gui.GetWindowText(hwnd)
                                if window_title and win32gui.IsWindowVisible(hwnd):
                                    # Create a window-like object
                                    rect = win32gui.GetWindowRect(hwnd)
                                    class WindowObj:
                                        def __init__(self, hwnd, title, rect):
                                            self.hwnd = hwnd
                                            self.title = title
                                            self.left = rect[0]
                                            self.top = rect[1] 
                                            self.width = rect[2] - rect[0]
                                            self.height = rect[3] - rect[1]
                                            self.visible = True
                                            
                                        @property
                                        def isMinimized(self):
                                            return win32gui.IsIconic(self.hwnd)
                                            
                                        def restore(self):
                                            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                                            
                                        def activate(self):
                                            win32gui.SetForegroundWindow(self.hwnd)
                                    
                                    return WindowObj(hwnd, window_title, rect)
                            return None
                        
                        # Try to find window for this process
                        def callback(hwnd, pid):
                            result = enum_windows_callback(hwnd, pid)
                            if result:
                                callback.result = result
                                return False
                            return True
                        
                        callback.result = None
                        win32gui.EnumWindows(lambda hwnd, param: callback(hwnd, proc.info['pid']), None)
                        
                        if hasattr(callback, 'result') and callback.result:
                            return callback.result
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            print(f"Error finding window on Windows: {e}")
        return None
    
    def _find_window_macos(self):
        """Find application window on macOS"""
        try:
            workspace = NSWorkspace.sharedWorkspace()
            apps = workspace.runningApplications()
            for app in apps:
                if self.app_name in app.localizedName().lower():
                    return app
        except Exception as e:
            print(f"Error finding window on macOS: {e}")
        return None
    
    def _find_window_linux(self):
        """Find application window on Linux"""
        try:
            result = subprocess.run(['xdotool', 'search', '--name', self.app_name], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except Exception as e:
            print(f"Error finding window on Linux: {e}")
        return None
    
    def list_running_applications(self):
        """List running applications to help user choose"""
        apps = set()
        
        if sys.platform == "win32":
            try:
                windows = gw.getAllWindows()
                for window in windows:
                    if window.title.strip():
                        apps.add(window.title.strip())
            except:
                pass
            
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name']
                    if name and not name.endswith('.exe'):
                        apps.add(name)
                    elif name and name.endswith('.exe'):
                        apps.add(name[:-4])  # Remove .exe extension
                except:
                    pass
                    
        elif sys.platform == "darwin":
            try:
                workspace = NSWorkspace.sharedWorkspace()
                running_apps = workspace.runningApplications()
                for app in running_apps:
                    apps.add(app.localizedName())
            except:
                pass
                
        else:  # Linux
            for proc in psutil.process_iter(['name']):
                try:
                    apps.add(proc.info['name'])
                except:
                    pass
        
        return sorted([app for app in apps if app and len(app) > 1])
    
    def take_screenshot(self):
        """Take screenshot of the application"""
        window = self.find_application_window()
        if not window:
            return None, f"Application '{self.app_name}' not found or not running"
        
        # Create screenshots folder if it doesn't exist
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(screenshots_dir, f"screenshot_{self.app_name}_{timestamp}.png")
        
        try:
            if sys.platform == "win32":
                return self._screenshot_windows(window, filename)
            elif sys.platform == "darwin":
                return self._screenshot_macos(window, filename)
            else:
                return self._screenshot_linux(window, filename)
        except Exception as e:
            return None, f"Error taking screenshot: {e}"
    
    def _screenshot_windows(self, window, filename):
        """Take screenshot on Windows"""
        try:
            # Method 1: Try to use window handle for direct capture
            try:
                hwnd = win32gui.FindWindow(None, window.title)
                if hwnd:
                    # Get window dimensions
                    rect = win32gui.GetWindowRect(hwnd)
                    left, top, right, bottom = rect
                    width = right - left
                    height = bottom - top
                    
                    # Bring window to front
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(1)  # Wait longer for window to come to front
                    
                    # Create device context
                    hwndDC = win32gui.GetWindowDC(hwnd)
                    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                    saveDC = mfcDC.CreateCompatibleDC()
                    
                    # Create bitmap
                    saveBitMap = win32ui.CreateBitmap()
                    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
                    saveDC.SelectObject(saveBitMap)
                    
                    # Copy window content
                    result = saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
                    
                    if result:
                        # Convert to PIL Image
                        bmpinfo = saveBitMap.GetInfo()
                        bmpstr = saveBitMap.GetBitmapBits(True)
                        
                        img = Image.frombuffer(
                            'RGB',
                            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                            bmpstr, 'raw', 'BGRX', 0, 1)
                        
                        # Clean up
                        win32gui.DeleteObject(saveBitMap.GetHandle())
                        saveDC.DeleteDC()
                        mfcDC.DeleteDC()
                        win32gui.ReleaseDC(hwnd, hwndDC)
                        
                        # Save image
                        img.save(filename)
                        return filename, "✓ Used direct window capture method"
                    
                    # Clean up if failed
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                    saveDC.DeleteDC()
                    mfcDC.DeleteDC()
                    win32gui.ReleaseDC(hwnd, hwndDC)
                    
            except Exception as e:
                pass
            
            # Method 2: Fallback to screen region capture
            if window.isMinimized:
                window.restore()
            window.activate()
            time.sleep(1.5)  # Longer wait
            
            # Ensure window is visible and get updated position
            left, top, width, height = window.left, window.top, window.width, window.height
            
            # Check if coordinates make sense
            if width <= 0 or height <= 0:
                screenshot = pyautogui.screenshot()
            else:
                # Add small margin to avoid window borders
                margin = 8
                left += margin
                top += margin + 30  # Account for title bar
                width -= margin * 2
                height -= margin * 2 + 30
                
                if width > 0 and height > 0:
                    screenshot = pyautogui.screenshot(region=(left, top, width, height))
                else:
                    screenshot = pyautogui.screenshot()
            
            screenshot.save(filename)
            return filename, "✓ Used screen region capture method"
            
        except Exception as e:
            return None, f"Error in Windows screenshot: {e}"
    
    def _screenshot_macos(self, app, filename):
        """Take screenshot on macOS"""
        try:
            # Activate the application and wait
            app.activateWithOptions_(NSApplicationActivationPolicyRegular)
            time.sleep(1.5)
            
            # Method 1: Try to get specific window bounds
            try:
                # Get all windows for this app
                options = Quartz.kCGWindowListOptionOnScreenOnly
                window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
                
                app_name = app.localizedName().lower()
                for window in window_list:
                    window_owner = window.get('kCGWindowOwnerName', '').lower()
                    if app_name in window_owner:
                        bounds = window.get('kCGWindowBounds', {})
                        if bounds:
                            x = int(bounds['X'])
                            y = int(bounds['Y'])
                            width = int(bounds['Width'])
                            height = int(bounds['Height'])
                            
                            if width > 0 and height > 0:
                                screenshot = pyautogui.screenshot(region=(x, y, width, height))
                                screenshot.save(filename)
                                return filename, "✓ Used window bounds capture method"
            except Exception as e:
                pass
            
            # Method 2: Fallback to full screen
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            return filename, "✓ Used full screen capture method"
            
        except Exception as e:
            return None, f"Error in macOS screenshot: {e}"
    
    def _screenshot_linux(self, window_id, filename):
        """Take screenshot on Linux"""
        try:
            # Method 1: Try using import with window ID
            try:
                subprocess.run(['xdotool', 'windowactivate', window_id], check=True)
                time.sleep(1)
                result = subprocess.run(['import', '-window', window_id, filename], 
                                      check=True, capture_output=True, text=True)
                if os.path.exists(filename):
                    return filename, "✓ Used window ID capture method"
            except subprocess.CalledProcessError:
                pass
            
            # Method 2: Try using scrot with window focus
            try:
                subprocess.run(['xdotool', 'windowactivate', window_id], check=True)
                time.sleep(1)
                result = subprocess.run(['scrot', '-s', filename], check=True)
                if os.path.exists(filename):
                    return filename, "✓ Used scrot selection method"
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            # Method 3: Fallback to gnome-screenshot or full screen
            try:
                subprocess.run(['gnome-screenshot', '-w', '-f', filename], check=True)
                if os.path.exists(filename):
                    return filename, "✓ Used gnome-screenshot method"
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            # Method 4: Final fallback - take full screenshot with pyautogui
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            return filename, "✓ Used full screen capture method"
            
        except Exception as e:
            return None, f"Error in Linux screenshot: {e}"
    
    def send_to_discord(self, filename):
        """Send screenshot to Discord webhook"""
        try:
            with open(filename, 'rb') as file:
                files = {'file': (filename, file, 'image/png')}
                data = {
                    'content': f'Screenshot of {self.app_name} - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                }
                
                response = requests.post(self.webhook_url, data=data, files=files)
                
                if response.status_code == 200:
                    return True, "✓ Screenshot sent successfully"
                else:
                    return False, f"✗ Failed to send screenshot. Status code: {response.status_code}"
                    
        except Exception as e:
            return False, f"✗ Error sending to Discord: {e}"
    
    def cleanup_screenshot(self, filename):
        """Delete screenshot file if delete_after_send is True"""
        if self.delete_after_send:
            try:
                os.remove(filename)
                return True, f"✓ Deleted screenshot: {filename}"
            except Exception as e:
                return False, f"✗ Error deleting file {filename}: {e}"
        return True, "Screenshot kept"
    
    def take_single_screenshot(self):
        """Take and send one screenshot"""
        if not self.webhook_url or not self.app_name:
            return False, "Please configure webhook URL and application name first!"
            
        filename, message = self.take_screenshot()
        
        if filename and os.path.exists(filename):
            success, send_message = self.send_to_discord(filename)
            if success:
                cleanup_success, cleanup_message = self.cleanup_screenshot(filename)
                return True, f"{message}\n{send_message}\n{cleanup_message}"
            else:
                return False, f"{message}\n{send_message}\nScreenshot kept due to send failure"
        else:
            return False, f"Failed to take screenshot: {message}"
    
    def start_monitoring(self):
        """Start continuous monitoring in a separate thread"""
        if not self.webhook_url or not self.app_name:
            return False, "Please configure webhook URL and application name first!"
            
        if self.running:
            return False, "Monitoring is already running!"
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        return True, f"Started monitoring '{self.app_name}' every {self.interval} seconds"
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            self.take_single_screenshot()
            
            # Sleep in small increments so we can stop quickly
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        if not self.running:
            return False, "Monitoring is not running!"
            
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        return True, "Stopped monitoring"


class ScreenshotBotGUI:
    def __init__(self):
        self.bot = ApplicationScreenshotter()
        self.root = tk.Tk()
        self.root.title("Screenshot Discord Bot")
        self.root.geometry("800x900")
        self.root.resizable(True, True)
        self.root.configure(bg='#1e1e1e')
        
        # Animation variables
        self.fade_alpha = 0.0
        self.pulse_scale = 1.0
        self.pulse_direction = 1
        self.status_colors = {
            'success': '#4ade80',
            'error': '#ef4444',
            'warning': '#f59e0b',
            'info': '#3b82f6'
        }
        
        # Configure ttk styles for dark theme
        self.setup_styles()
        
        # Create animated header
        self.create_animated_header()
        
        self.create_widgets()
        self.update_status()
        
        # Start animation loops
        self.root.after(50, self.animate_pulse)
        self.root.after(100, self.update_status_loop)
        self.animate_fade_in()
    
    def setup_styles(self):
        """Setup dark theme styles with modern look"""
        style = ttk.Style()
        
        # Configure dark theme
        style.theme_use('clam')
        
        # Main colors
        bg_color = '#1e1e1e'
        card_color = '#2d2d2d'
        accent_color = '#3b82f6'
        text_color = '#ffffff'
        secondary_text = '#a1a1aa'
        
        # Configure styles
        style.configure('Title.TLabel', 
                       background=bg_color, 
                       foreground=text_color,
                       font=('Segoe UI', 24, 'bold'))
        
        style.configure('Card.TFrame', 
                       background=card_color,
                       relief='flat',
                       borderwidth=1)
        
        style.configure('Modern.TLabel',
                       background=card_color,
                       foreground=text_color,
                       font=('Segoe UI', 10))
        
        style.configure('Secondary.TLabel',
                       background=card_color,
                       foreground=secondary_text,
                       font=('Segoe UI', 9))
        
        style.configure('Modern.TEntry',
                       borderwidth=1,
                       relief='flat',
                       font=('Segoe UI', 10),
                       fieldbackground='#374151',
                       foreground=text_color,
                       bordercolor=accent_color,
                       lightcolor=accent_color,
                       darkcolor=accent_color)
        
        style.configure('Action.TButton',
                       font=('Segoe UI', 10, 'bold'),
                       borderwidth=0,
                       focuscolor='none')
        
        style.map('Action.TButton',
                 background=[('active', '#2563eb'), ('!active', accent_color)],
                 foreground=[('active', 'white'), ('!active', 'white')])
        
        style.configure('Success.TButton',
                       font=('Segoe UI', 10, 'bold'),
                       borderwidth=0,
                       focuscolor='none')
        
        style.map('Success.TButton',
                 background=[('active', '#16a34a'), ('!active', '#22c55e')],
                 foreground=[('active', 'white'), ('!active', 'white')])
        
        style.configure('Danger.TButton',
                       font=('Segoe UI', 10, 'bold'),
                       borderwidth=0,
                       focuscolor='none')
        
        style.map('Danger.TButton',
                 background=[('active', '#dc2626'), ('!active', '#ef4444')],
                 foreground=[('active', 'white'), ('!active', 'white')])
    
    def create_animated_header(self):
        """Create animated header with gradient effect"""
        self.header_frame = tk.Frame(self.root, bg='#1e1e1e', height=100)
        self.header_frame.pack(fill=tk.X, pady=(0, 20))
        self.header_frame.pack_propagate(False)
        
        # Animated title
        self.title_label = tk.Label(
            self.header_frame,
            text="📸 Screenshot Discord Bot",
            font=('Segoe UI', 28, 'bold'),
            fg='#3b82f6',
            bg='#1e1e1e'
        )
        self.title_label.pack(expand=True)
        
        # Subtitle with typewriter effect
        self.subtitle_label = tk.Label(
            self.header_frame,
            text="",
            font=('Segoe UI', 12),
            fg='#a1a1aa',
            bg='#1e1e1e'
        )
        self.subtitle_label.pack()
        
        # Start typewriter animation
        self.typewriter_text = "wraith stinks btw"
        self.typewriter_index = 0
        self.root.after(2000, self.animate_typewriter)
    
    def animate_typewriter(self):
        """Animate typewriter effect for subtitle"""
        if self.typewriter_index <= len(self.typewriter_text):
            self.subtitle_label.config(text=self.typewriter_text[:self.typewriter_index])
            self.typewriter_index += 1
            self.root.after(50, self.animate_typewriter)
    
    def animate_fade_in(self):
        """Animate window fade in effect"""
        if self.fade_alpha < 1.0:
            self.fade_alpha += 0.05
            # Simulate fade by adjusting widget states
            self.root.after(30, self.animate_fade_in)
    
    def animate_pulse(self):
        """Animate pulsing effect for monitoring status"""
        if hasattr(self, 'status_indicator') and self.bot.running:
            self.pulse_scale += 0.02 * self.pulse_direction
            if self.pulse_scale >= 1.1:
                self.pulse_direction = -1
            elif self.pulse_scale <= 0.9:
                self.pulse_direction = 1
            
            # Update status indicator with pulse effect
            pulse_size = int(12 * self.pulse_scale)
            self.status_indicator.config(font=('Segoe UI', pulse_size, 'bold'))
        
        self.root.after(50, self.animate_pulse)
    
    def create_widgets(self):
        # Main container with padding
        main_container = tk.Frame(self.root, bg='#1e1e1e')
        main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        # Configuration Card
        config_card = self.create_card(main_container, "⚙️ Configuration")
        config_card.pack(fill=tk.X, pady=(0, 20))
        
        # Webhook URL section
        webhook_section = tk.Frame(config_card, bg='#2d2d2d')
        webhook_section.pack(fill=tk.X, padx=20, pady=10)
        
        webhook_label = tk.Label(webhook_section, text="Discord Webhook URL",
                                font=('Segoe UI', 11, 'bold'), fg='#ffffff', bg='#2d2d2d')
        webhook_label.pack(anchor=tk.W)
        
        webhook_desc = tk.Label(webhook_section, text="Enter your Discord webhook URL to send screenshots",
                               font=('Segoe UI', 9), fg='#a1a1aa', bg='#2d2d2d')
        webhook_desc.pack(anchor=tk.W, pady=(0, 5))
        
        self.webhook_var = tk.StringVar()
        self.webhook_entry = tk.Entry(webhook_section, textvariable=self.webhook_var,
                                     font=('Segoe UI', 10), bg='#374151', fg='#ffffff',
                                     bd=0, highlightthickness=1, highlightcolor='#3b82f6',
                                     insertbackground='#ffffff')
        self.webhook_entry.pack(fill=tk.X, ipady=8)
        self.webhook_entry.bind('<FocusIn>', lambda e: self.animate_entry_focus(e.widget, True))
        self.webhook_entry.bind('<FocusOut>', lambda e: self.animate_entry_focus(e.widget, False))
        
        # Application section
        app_section = tk.Frame(config_card, bg='#2d2d2d')
        app_section.pack(fill=tk.X, padx=20, pady=10)
        
        app_label = tk.Label(app_section, text="Target Application",
                            font=('Segoe UI', 11, 'bold'), fg='#ffffff', bg='#2d2d2d')
        app_label.pack(anchor=tk.W)
        
        app_desc = tk.Label(app_section, text="Choose which application to screenshot",
                           font=('Segoe UI', 9), fg='#a1a1aa', bg='#2d2d2d')
        app_desc.pack(anchor=tk.W, pady=(0, 5))
        
        app_input_frame = tk.Frame(app_section, bg='#2d2d2d')
        app_input_frame.pack(fill=tk.X)
        
        self.app_var = tk.StringVar()
        self.app_entry = tk.Entry(app_input_frame, textvariable=self.app_var,
                                 font=('Segoe UI', 10), bg='#374151', fg='#ffffff',
                                 bd=0, highlightthickness=1, highlightcolor='#3b82f6',
                                 insertbackground='#ffffff')
        self.app_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        self.app_entry.bind('<FocusIn>', lambda e: self.animate_entry_focus(e.widget, True))
        self.app_entry.bind('<FocusOut>', lambda e: self.animate_entry_focus(e.widget, False))
        
        self.browse_btn = tk.Button(app_input_frame, text="🔍 Browse",
                                   font=('Segoe UI', 9, 'bold'), bg='#6366f1', fg='white',
                                   bd=0, padx=15, pady=8, cursor='hand2',
                                   command=self.show_applications)
        self.browse_btn.pack(side=tk.RIGHT, padx=(10, 0))
        self.browse_btn.bind('<Enter>', lambda e: self.animate_button_hover(e.widget, True))
        self.browse_btn.bind('<Leave>', lambda e: self.animate_button_hover(e.widget, False))
        
        # Settings section
        settings_section = tk.Frame(config_card, bg='#2d2d2d')
        settings_section.pack(fill=tk.X, padx=20, pady=10)
        
        settings_row = tk.Frame(settings_section, bg='#2d2d2d')
        settings_row.pack(fill=tk.X)
        
        # Interval setting
        interval_frame = tk.Frame(settings_row, bg='#2d2d2d')
        interval_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        interval_label = tk.Label(interval_frame, text="Interval (seconds)",
                                 font=('Segoe UI', 11, 'bold'), fg='#ffffff', bg='#2d2d2d')
        interval_label.pack(anchor=tk.W)
        
        self.interval_var = tk.StringVar(value="60")
        self.interval_entry = tk.Entry(interval_frame, textvariable=self.interval_var,
                                      font=('Segoe UI', 10), bg='#374151', fg='#ffffff',
                                      bd=0, highlightthickness=1, highlightcolor='#3b82f6',
                                      insertbackground='#ffffff', width=10)
        self.interval_entry.pack(anchor=tk.W, ipady=8, pady=(5, 0))
        self.interval_entry.bind('<FocusIn>', lambda e: self.animate_entry_focus(e.widget, True))
        self.interval_entry.bind('<FocusOut>', lambda e: self.animate_entry_focus(e.widget, False))
        
        # Delete checkbox with modern styling
        delete_frame = tk.Frame(settings_row, bg='#2d2d2d')
        delete_frame.pack(side=tk.RIGHT, padx=(20, 0))
        
        self.delete_var = tk.BooleanVar(value=True)
        delete_check_frame = tk.Frame(delete_frame, bg='#2d2d2d')
        delete_check_frame.pack(pady=(25, 0))
        
        self.delete_checkbox = tk.Checkbutton(delete_check_frame, text="🗑️ Auto-delete screenshots",
                                             variable=self.delete_var, font=('Segoe UI', 10),
                                             fg='#ffffff', bg='#2d2d2d', selectcolor='#3b82f6',
                                             activebackground='#2d2d2d', activeforeground='#ffffff',
                                             bd=0, highlightthickness=0)
        self.delete_checkbox.pack()
        
        # Action Card
        action_card = self.create_card(main_container, "🚀 Actions")
        action_card.pack(fill=tk.X, pady=(0, 20))
        
        action_buttons_frame = tk.Frame(action_card, bg='#2d2d2d')
        action_buttons_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Modern gradient buttons
        btn_style = {
            'font': ('Segoe UI', 11, 'bold'),
            'bd': 0,
            'padx': 25,
            'pady': 12,
            'cursor': 'hand2'
        }
        
        self.screenshot_btn = tk.Button(action_buttons_frame, text="📸 Take Screenshot",
                                       bg='#3b82f6', fg='white', **btn_style,
                                       command=self.take_screenshot_animated)
        self.screenshot_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.screenshot_btn.bind('<Enter>', lambda e: self.animate_button_hover(e.widget, True))
        self.screenshot_btn.bind('<Leave>', lambda e: self.animate_button_hover(e.widget, False))
        
        self.start_btn = tk.Button(action_buttons_frame, text="▶️ Start Monitoring",
                                  bg='#22c55e', fg='white', **btn_style,
                                  command=self.start_monitoring_animated)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.start_btn.bind('<Enter>', lambda e: self.animate_button_hover(e.widget, True))
        self.start_btn.bind('<Leave>', lambda e: self.animate_button_hover(e.widget, False))
        
        self.stop_btn = tk.Button(action_buttons_frame, text="⏹️ Stop Monitoring",
                                 bg='#ef4444', fg='white', **btn_style,
                                 command=self.stop_monitoring_animated)
        self.stop_btn.pack(side=tk.LEFT)
        self.stop_btn.bind('<Enter>', lambda e: self.animate_button_hover(e.widget, True))
        self.stop_btn.bind('<Leave>', lambda e: self.animate_button_hover(e.widget, False))
        
        # Status Card with animated indicator
        status_card = self.create_card(main_container, "📊 Status & Activity")
        status_card.pack(fill=tk.BOTH, expand=True)
        
        # Status header with animated indicator
        status_header = tk.Frame(status_card, bg='#2d2d2d')
        status_header.pack(fill=tk.X, padx=20, pady=(10, 0))
        
        self.status_indicator = tk.Label(status_header, text="●", font=('Segoe UI', 12, 'bold'),
                                        fg='#ef4444', bg='#2d2d2d')
        self.status_indicator.pack(side=tk.LEFT)
        
        self.status_text_label = tk.Label(status_header, text="Stopped", font=('Segoe UI', 11, 'bold'),
                                         fg='#ffffff', bg='#2d2d2d')
        self.status_text_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Activity log with modern styling
        log_frame = tk.Frame(status_card, bg='#2d2d2d')
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))
        
        # Custom styled text widget
        self.status_text = tk.Text(log_frame, font=('Consolas', 9), bg='#1a1a1a',
                                  fg='#e5e5e5', bd=0, padx=15, pady=10,
                                  insertbackground='#3b82f6', selectbackground='#374151')
        
        # Scrollbar with modern styling
        scrollbar = tk.Scrollbar(log_frame, bg='#374151', troughcolor='#2d2d2d',
                                borderwidth=0, highlightthickness=0)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.status_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.status_text.yview)
        
        # Configure text tags for colored output
        self.status_text.tag_configure("success", foreground="#4ade80")
        self.status_text.tag_configure("error", foreground="#ef4444")
        self.status_text.tag_configure("warning", foreground="#f59e0b")
        self.status_text.tag_configure("info", foreground="#3b82f6")
        self.status_text.tag_configure("timestamp", foreground="#6b7280")
    
    def create_card(self, parent, title):
        """Create a modern card with title"""
        card_frame = tk.Frame(parent, bg='#2d2d2d', relief='flat', bd=1)
        
        # Card header
        header = tk.Frame(card_frame, bg='#374151', height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title_label = tk.Label(header, text=title, font=('Segoe UI', 14, 'bold'),
                              fg='#ffffff', bg='#374151')
        title_label.pack(expand=True)
        
        return card_frame
    
    def animate_entry_focus(self, widget, focused):
        """Animate entry field focus"""
        if focused:
            widget.config(highlightcolor='#3b82f6', highlightbackground='#3b82f6', highlightthickness=2)
        else:
            widget.config(highlightthickness=1)
    
    def animate_button_hover(self, widget, hovering):
        """Animate button hover effect"""
        if hovering:
            current_bg = widget.cget('bg')
            if current_bg == '#3b82f6':
                widget.config(bg='#2563eb')
            elif current_bg == '#22c55e':
                widget.config(bg='#16a34a')
            elif current_bg == '#ef4444':
                widget.config(bg='#dc2626')
            elif current_bg == '#6366f1':
                widget.config(bg='#4f46e5')
        else:
            current_bg = widget.cget('bg')
            if current_bg == '#2563eb':
                widget.config(bg='#3b82f6')
            elif current_bg == '#16a34a':
                widget.config(bg='#22c55e')
            elif current_bg == '#dc2626':
                widget.config(bg='#ef4444')
            elif current_bg == '#4f46e5':
                widget.config(bg='#6366f1')
    
    def show_applications(self):
        """Show running applications in a modern popup"""
        apps = self.bot.list_running_applications()
        
        app_window = tk.Toplevel(self.root)
        app_window.title("Select Application")
        app_window.geometry("500x600")
        app_window.configure(bg='#1e1e1e')
        app_window.resizable(False, False)
        
        # Center the window
        app_window.transient(self.root)
        app_window.grab_set()
        
        # Header
        header = tk.Frame(app_window, bg='#374151', height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(header, text="🔍 Select Target Application",
                        font=('Segoe UI', 16, 'bold'), fg='#ffffff', bg='#374151')
        title.pack(expand=True)
        
        # Search frame
        search_frame = tk.Frame(app_window, bg='#1e1e1e')
        search_frame.pack(fill=tk.X, padx=20, pady=20)
        
        search_label = tk.Label(search_frame, text="Search:", font=('Segoe UI', 10),
                               fg='#ffffff', bg='#1e1e1e')
        search_label.pack(anchor=tk.W)
        
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var,
                               font=('Segoe UI', 10), bg='#374151', fg='#ffffff',
                               bd=0, highlightthickness=1, highlightcolor='#3b82f6',
                               insertbackground='#ffffff')
        search_entry.pack(fill=tk.X, ipady=8, pady=(5, 0))
        
        # Apps list frame
        list_frame = tk.Frame(app_window, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Custom listbox with modern styling
        listbox_frame = tk.Frame(list_frame, bg='#2d2d2d')
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(listbox_frame, bg='#374151', troughcolor='#2d2d2d')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set,
                            font=('Segoe UI', 10), bg='#2d2d2d', fg='#ffffff',
                            selectbackground='#3b82f6', selectforeground='#ffffff',
                            bd=0, highlightthickness=0, activestyle='none')
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate list
        all_apps = apps[:]
        for app in all_apps:
            listbox.insert(tk.END, f"📱 {app}")
        
        def filter_apps():
            """Filter applications based on search"""
            query = search_var.get().lower()
            listbox.delete(0, tk.END)
            for app in all_apps:
                if query in app.lower():
                    listbox.insert(tk.END, f"📱 {app}")
        
        search_var.trace('w', lambda *args: filter_apps())
        
        def select_app():
            """Select application with animation"""
            selection = listbox.curselection()
            if selection:
                selected_app = listbox.get(selection[0]).replace("📱 ", "")
                self.app_var.set(selected_app.lower())
                
                # Animate selection
                for i in range(3):
                    listbox.config(selectbackground='#22c55e')
                    app_window.update()
                    self.root.after(100)
                    listbox.config(selectbackground='#3b82f6')
                    app_window.update()
                    self.root.after(100)
                
                app_window.destroy()
        
        # Button frame
        btn_frame = tk.Frame(app_window, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        select_btn = tk.Button(btn_frame, text="✅ Select Application",
                              font=('Segoe UI', 11, 'bold'), bg='#22c55e', fg='white',
                              bd=0, padx=30, pady=10, cursor='hand2',
                              command=select_app)
        select_btn.pack()
        
        # Double click to select
        listbox.bind('<Double-Button-1>', lambda e: select_app())
    
    def take_screenshot_animated(self):
        """Take screenshot with button animation"""
        self.animate_button_click(self.screenshot_btn)
        self.update_config()
        success, message = self.bot.take_single_screenshot()
        self.log_message_colored(message, 'success' if success else 'error')
        if not success:
            self.show_notification("Error", message, 'error')
    
    def start_monitoring_animated(self):
        """Start monitoring with button animation"""
        self.animate_button_click(self.start_btn)
        self.update_config()
        success, message = self.bot.start_monitoring()
        self.log_message_colored(message, 'success' if success else 'error')
        if not success:
            self.show_notification("Error", message, 'error')
        else:
            self.show_notification("Success", "Monitoring started!", 'success')
    
    def stop_monitoring_animated(self):
        """Stop monitoring with button animation"""
        self.animate_button_click(self.stop_btn)
        success, message = self.bot.stop_monitoring()
        self.log_message_colored(message, 'success' if success else 'warning')
    
    def animate_button_click(self, button):
        """Animate button click effect"""
        original_relief = button.cget('relief')
        button.config(relief='sunken')
        self.root.after(100, lambda: button.config(relief=original_relief))
    
    def show_notification(self, title, message, type_='info'):
        """Show animated notification"""
        notification = tk.Toplevel(self.root)
        notification.title(title)
        notification.geometry("400x120")
        notification.configure(bg=self.status_colors.get(type_, '#3b82f6'))
        notification.resizable(False, False)
        
        # Position in top-right corner
        notification.geometry("+{}+{}".format(
            self.root.winfo_x() + self.root.winfo_width() - 420,
            self.root.winfo_y() + 50
        ))
        
        # Remove window decorations
        notification.overrideredirect(True)
        
        # Content
        content_frame = tk.Frame(notification, bg=self.status_colors.get(type_, '#3b82f6'))
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        title_label = tk.Label(content_frame, text=title, font=('Segoe UI', 12, 'bold'),
                              fg='white', bg=self.status_colors.get(type_, '#3b82f6'))
        title_label.pack(anchor=tk.W)
        
        msg_label = tk.Label(content_frame, text=message, font=('Segoe UI', 10),
                            fg='white', bg=self.status_colors.get(type_, '#3b82f6'),
                            wraplength=350)
        msg_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Auto-close after 3 seconds
        self.root.after(3000, notification.destroy)
    
    def update_config(self):
        """Update bot configuration from GUI"""
        self.bot.webhook_url = self.webhook_var.get().strip()
        self.bot.app_name = self.app_var.get().strip().lower()
        try:
            self.bot.interval = int(self.interval_var.get())
        except ValueError:
            self.bot.interval = 60
        self.bot.delete_after_send = self.delete_var.get()
    
    def log_message_colored(self, message, type_='info'):
        """Add colored message to status log with animation"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Insert with colors
        self.status_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        
        if type_ == 'success':
            self.status_text.insert(tk.END, "✅ ", "success")
        elif type_ == 'error':
            self.status_text.insert(tk.END, "❌ ", "error")
        elif type_ == 'warning':
            self.status_text.insert(tk.END, "⚠️ ", "warning")
        else:
            self.status_text.insert(tk.END, "ℹ️ ", "info")
        
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        
        # Animate scroll to bottom
        self.animate_scroll_to_bottom()
    
    def animate_scroll_to_bottom(self):
        """Smooth scroll animation to bottom"""
        def scroll_step(step=0):
            if step < 5:
                self.status_text.see(tk.END)
                self.root.after(20, lambda: scroll_step(step + 1))
        scroll_step()
    
    def update_status(self):
        """Update status display with animations"""
        webhook_status = "✅" if self.bot.webhook_url else "❌"
        app_status = "✅" if self.bot.app_name else "❌"
        
        if self.bot.running:
            self.status_indicator.config(fg='#22c55e', text="●")
            self.status_text_label.config(text="🔄 Monitoring Active", fg='#22c55e')
            self.start_btn.config(state='disabled', text="▶️ Running...")
            self.stop_btn.config(state='normal')
        else:
            self.status_indicator.config(fg='#ef4444', text="●")
            self.status_text_label.config(text="⏸️ Stopped", fg='#ef4444')
            self.start_btn.config(state='normal', text="▶️ Start Monitoring")
            self.stop_btn.config(state='disabled')
        
        # Update window title with status
        status = f"Webhook: {webhook_status} | App: {app_status} | Interval: {self.bot.interval}s"
        self.root.title(f"Screenshot Discord Bot - {status}")
    
    def update_status_loop(self):
        """Continuous status update with smooth transitions"""
        self.update_status()
        self.root.after(1000, self.update_status_loop)
    
    def run(self):
        """Start the GUI with fade-in animation"""
        # Start with window slightly transparent effect simulation
        self.root.update_idletasks()
        
        # Welcome message
        self.root.after(1000, lambda: self.log_message_colored("Welcome to Screenshot Discord Bot! 🎉", 'info'))
        self.root.after(2000, lambda: self.log_message_colored("Configure your settings and start monitoring", 'info'))
        
        self.root.mainloop()


def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """Print the application banner"""
    print("=" * 60)
    print("      APPLICATION SCREENSHOT DISCORD BOT")
    print("=" * 60)


def print_current_config(bot):
    """Print current configuration"""
    print(f"\n--- Current Configuration ---")
    print(f"Webhook URL: {'✓ Set' if bot.webhook_url else '✗ Not set'}")
    print(f"Application: {bot.app_name if bot.app_name else '✗ Not set'}")
    print(f"Interval: {bot.interval} seconds")
    print(f"Delete after send: {'Yes' if bot.delete_after_send else 'No'}")
    print(f"Status: {'🟢 Running' if bot.running else '🔴 Stopped'}")


def console_menu():
    """Display the console menu and handle user input"""
    bot = ApplicationScreenshotter()
    
    while True:
        clear_screen()
        print_banner()
        print_current_config(bot)
        
        print("\n--- Menu ---")
        print("1. Set Discord Webhook URL")
        print("2. Set Application Name")
        print("3. List Running Applications")
        print("4. Set Screenshot Interval")
        print("5. Toggle Delete After Send")
        print("6. Take Single Screenshot")
        print("7. Start Continuous Monitoring")
        print("8. Stop Monitoring")
        print("9. Exit")
        
        try:
            choice = input("\nEnter your choice (1-9): ").strip()
            
            if choice == "1":
                url = input("Enter Discord webhook URL: ").strip()
                if url:
                    bot.webhook_url = url
                    print("✓ Webhook URL set successfully!")
                else:
                    print("✗ Invalid URL!")
                input("\nPress Enter to continue...")
                
            elif choice == "2":
                app = input("Enter application name (partial name is OK): ").strip()
                if app:
                    bot.app_name = app.lower()
                    print(f"✓ Application name set to: {bot.app_name}")
                else:
                    print("✗ Invalid application name!")
                input("\nPress Enter to continue...")
                
            elif choice == "3":
                print("\n--- Running Applications ---")
                apps = bot.list_running_applications()
                for i, app in enumerate(apps[:20], 1):
                    print(f"{i:2d}. {app}")
                if len(apps) > 20:
                    print(f"... and {len(apps) - 20} more applications")
                input("\nPress Enter to continue...")
                
            elif choice == "4":
                try:
                    interval = int(input(f"Enter interval in seconds (current: {bot.interval}): ").strip())
                    if interval > 0:
                        bot.interval = interval
                        print(f"✓ Interval set to {interval} seconds")
                    else:
                        print("✗ Interval must be greater than 0!")
                except ValueError:
                    print("✗ Please enter a valid number!")
                input("\nPress Enter to continue...")
                
            elif choice == "5":
                bot.delete_after_send = not bot.delete_after_send
                status = "enabled" if bot.delete_after_send else "disabled"
                print(f"✓ Delete after send {status}")
                input("\nPress Enter to continue...")
                
            elif choice == "6":
                success, message = bot.take_single_screenshot()
                print(message)
                input("\nPress Enter to continue...")
                
            elif choice == "7":
                success, message = bot.start_monitoring()
                print(message)
                input("\nPress Enter to continue...")
                
            elif choice == "8":
                success, message = bot.stop_monitoring()
                print(message)
                input("\nPress Enter to continue...")
                
            elif choice == "9":
                if bot.running:
                    print("Stopping monitoring...")
                    bot.stop_monitoring()
                print("Goodbye!")
                break
                
            else:
                print("✗ Invalid choice! Please enter 1-9.")
                input("\nPress Enter to continue...")
                
        except KeyboardInterrupt:
            if bot.running:
                print("\n\nStopping monitoring...")
                bot.stop_monitoring()
            print("Goodbye!")
            break
        except Exception as e:
            print(f"✗ An error occurred: {e}")
            input("\nPress Enter to continue...")


def main():
    """Main function to choose between GUI and console"""
    print("=" * 60)
    print("      APPLICATION SCREENSHOT DISCORD BOT")
    print("=" * 60)
    
    if GUI_AVAILABLE:
        print("\nChoose interface:")
        print("1. GUI (Graphical User Interface)")
        print("2. Console (Command Line Interface)")
        print("3. Exit")
        while True:
            try:
                choice = input("\nEnter your choice (1-3): ").strip()
                
                if choice == "1":
                    print("Starting GUI...")
                    gui = ScreenshotBotGUI()
                    gui.run()
                    break
                elif choice == "2":
                    console_menu()
                    break
                elif choice == "3":
                    print("Goodbye!")
                    break
                else:
                    print("✗ Invalid choice! Please enter 1-3.")
                    
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
    else:
        print("\nGUI not available (tkinter not installed)")
        print("Starting console interface...")
        time.sleep(2)
        console_menu()


if __name__ == "__main__":

    main()

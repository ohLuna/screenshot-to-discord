#!/usr/bin/env python3
"""
Application Screenshot Discord Bot
Takes screenshots of a specific application and sends them to Discord webhook
Interactive configuration menu with GUI option
Enhanced with customizable messages and persistent configuration
"""

import os
import time
import requests
from datetime import datetime
import sys
import threading
import json


try:
    import pyautogui
    import psutil
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install pyautogui psutil")
    sys.exit(1)


try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


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


elif sys.platform == "darwin":
    try:
        from AppKit import NSWorkspace, NSApplicationActivationPolicyRegular
        import Quartz
        from PIL import Image
    except ImportError as e:
        print(f"Missing macOS-specific package: {e}")
        print("Install with: pip install pyobjc Pillow")
        sys.exit(1)


else:
    try:
        import subprocess
        from PIL import Image
    except ImportError as e:
        print(f"Missing Linux-specific package: {e}")
        print("Install with: pip install Pillow")
        sys.exit(1)

class ToggleSwitch(tk.Canvas):
    """
    A custom tkinter widget that acts as a sliding toggle switch with rounded edges.
    """
    def __init__(self, master, on_command=None, off_command=None, **kwargs):
        super().__init__(master, width=50, height=26, highlightthickness=0, **kwargs)
        self.on_color = '#22c55e'
        self.off_color = '#6b7280'
        self.toggle_color = '#ffffff'
        self.state = False
        self.on_command = on_command
        self.off_command = off_command
        
        self.bind('<Button-1>', self.toggle)
        self.draw_toggle()

    def draw_toggle(self):
        """Draws the toggle switch based on its current state."""
        self.delete('all')
        bg_color = self.on_color if self.state else self.off_color
        
        # Draw the rounded rectangle background
        self.create_oval(2, 2, 24, 24, fill=bg_color, outline=bg_color)
        self.create_oval(26, 2, 48, 24, fill=bg_color, outline=bg_color)
        self.create_rectangle(12, 2, 38, 24, fill=bg_color, outline=bg_color)
        
        # Draw the knob as a perfect circle
        if self.state:
            self.create_oval(28, 2, 48, 24, fill=self.toggle_color, outline=self.toggle_color)
        else:
            self.create_oval(2, 2, 22, 24, fill=self.toggle_color, outline=self.toggle_color)

    def toggle(self, event=None):
        """Toggles the state of the switch and executes the corresponding command."""
        self.state = not self.state
        self.draw_toggle()
        if self.state and self.on_command:
            self.on_command()
        elif not self.state and self.off_command:
            self.off_command()


class ApplicationScreenshotter:
    def __init__(self):
        self.config_file = "cfg.json"
        self.webhook_url = ""
        self.app_name = ""
        self.interval = 60
        self.delete_after_send = True
        self.custom_message = "Screenshot of {app_name} - {timestamp}"
        self.running = False
        self.monitor_thread = None
        
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.webhook_url = config.get('webhook_url', '')
                    self.app_name = config.get('app_name', '')
                    self.interval = config.get('interval', 60)
                    self.delete_after_send = config.get('delete_after_send', True)
                    self.custom_message = config.get('custom_message', 'Screenshot of {app_name} - {timestamp}')
                return True # Config loaded
            else:
                self.create_default_config()
                return False # Config file not found
        except Exception as e:
            print(f"Error loading config: {e}")
            self.create_default_config()
            return False # Error, so created default config
            
    def create_default_config(self):
        """Create a default configuration file"""
        try:
            config = {
                'webhook_url': self.webhook_url,
                'app_name': self.app_name,
                'interval': self.interval,
                'delete_after_send': self.delete_after_send,
                'custom_message': self.custom_message
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error creating default config: {e}")
            
    def save_config(self):
        """Save configuration to JSON file"""
        try:
            config = {
                'webhook_url': self.webhook_url,
                'app_name': self.app_name,
                'interval': self.interval,
                'delete_after_send': self.delete_after_send,
                'custom_message': self.custom_message
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def format_message(self):
        """Format the custom message with available variables"""
        variables = {
            'app_name': self.app_name,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'date': datetime.now().strftime("%Y-%m-%d"),
            'time': datetime.now().strftime("%H:%M:%S"),
            'day': datetime.now().strftime("%A"),
            'month': datetime.now().strftime("%B"),
            'year': datetime.now().strftime("%Y")
        }
        
        try:
            return self.custom_message.format(**variables)
        except KeyError as e:
            return f"Error in message format: Unknown variable {e}"
        except Exception as e:
            return f"Error formatting message: {e}"
    
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
            
            windows = gw.getAllWindows()
            matching_windows = []
            
            for window in windows:
                if (window.title and 
                    self.app_name in window.title.lower() and 
                    window.visible and 
                    window.width > 0 and window.height > 0):
                    matching_windows.append(window)
            
            if matching_windows:
                
                for window in matching_windows:
                    if not window.isMinimized:
                        return window
                return matching_windows[0]  
            
            
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    proc_name = proc.info['name'].lower()
                    if self.app_name in proc_name or proc_name.replace('.exe', '') == self.app_name:
                        
                        def enum_windows_callback(hwnd, pid):
                            if win32gui.GetWindowThreadProcessId(hwnd)[1] == pid:
                                window_title = win32gui.GetWindowText(hwnd)
                                if window_title and win32gui.IsWindowVisible(hwnd):
                                    
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
                        apps.add(name[:-4])  
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
                
        else:  
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
            
            try:
                hwnd = win32gui.FindWindow(None, window.title)
                if hwnd:
                    
                    rect = win32gui.GetWindowRect(hwnd)
                    left, top, right, bottom = rect
                    width = right - left
                    height = bottom - top
                    
                    
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(1)  
                    
                    
                    hwndDC = win32gui.GetWindowDC(hwnd)
                    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                    saveDC = mfcDC.CreateCompatibleDC()
                    
                    
                    saveBitMap = win32ui.CreateBitmap()
                    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
                    saveDC.SelectObject(saveBitMap)
                    
                    
                    result = saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
                    
                    if result:
                        
                        bmpinfo = saveBitMap.GetInfo()
                        bmpstr = saveBitMap.GetBitmapBits(True)
                        
                        img = Image.frombuffer(
                            'RGB',
                            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                            bmpstr, 'raw', 'BGRX', 0, 1)
                        
                        
                        win32gui.DeleteObject(saveBitMap.GetHandle())
                        saveDC.DeleteDC()
                        mfcDC.DeleteDC()
                        win32gui.ReleaseDC(hwnd, hwndDC)
                        
                        
                        img.save(filename)
                        return filename, "✓ Used direct window capture method"
                    
                    
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                    saveDC.DeleteDC()
                    mfcDC.DeleteDC()
                    win32gui.ReleaseDC(hwnd, hwndDC)
                    
            except Exception as e:
                pass
            
            
            if window.isMinimized:
                window.restore()
            window.activate()
            time.sleep(1.5)  
            
            
            left, top, width, height = window.left, window.top, window.width, window.height
            
            
            if width <= 0 or height <= 0:
                screenshot = pyautogui.screenshot()
            else:
                
                margin = 8
                left += margin
                top += margin + 30  
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
            
            app.activateWithOptions_(NSApplicationActivationPolicyRegular)
            time.sleep(1.5)
            
            
            try:
                
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
            
            
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            return filename, "✓ Used full screen capture method"
            
        except Exception as e:
            return None, f"Error in macOS screenshot: {e}"
    
    def _screenshot_linux(self, window_id, filename):
        """Take screenshot on Linux"""
        try:
            
            try:
                subprocess.run(['xdotool', 'windowactivate', window_id], check=True)
                time.sleep(1)
                result = subprocess.run(['import', '-window', window_id, filename], 
                                      check=True, capture_output=True, text=True)
                if os.path.exists(filename):
                    return filename, "✓ Used window ID capture method"
            except subprocess.CalledProcessError:
                pass
            
            
            try:
                subprocess.run(['xdotool', 'windowactivate', window_id], check=True)
                time.sleep(1)
                result = subprocess.run(['scrot', '-s', filename], check=True)
                if os.path.exists(filename):
                    return filename, "✓ Used scrot selection method"
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            
            try:
                subprocess.run(['gnome-screenshot', '-w', '-f', filename], check=True)
                if os.path.exists(filename):
                    return filename, "✓ Used gnome-screenshot method"
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            return filename, "✓ Used full screen capture method"
            
        except Exception as e:
            return None, f"Error in Linux screenshot: {e}"
    
    def send_to_discord(self, filename):
        """Send screenshot to Discord webhook with custom message"""
        try:
            with open(filename, 'rb') as file:
                files = {'file': (filename, file, 'image/png')}
                
                
                content = self.format_message() if self.custom_message.strip() else None
                
                data = {}
                if content:
                    data['content'] = content
                
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
        self.config_found = self.bot.load_config()
        self.root = tk.Tk()
        self.root.title("Screenshot Discord Bot")
        self.root.geometry("1300x900")
        self.root.resizable(True, True)
        self.root.configure(bg='#1e1e1e')
        
        
        self.fade_alpha = 0.0
        self.pulse_scale = 1.0
        self.pulse_direction = 1
        self.status_colors = {
            'success': '#4ade80',
            'error': '#ef4444',
            'warning': '#f59e0b',
            'info': '#3b82f6'
        }
        
        
        self.setup_styles()
        
        
        self.create_animated_header()
        
        self.create_widgets()
        self.update_status()
        
        
        self.root.after(50, self.animate_pulse)
        self.root.after(100, self.update_status_loop)
        self.animate_fade_in()
        
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_closing(self):
        """Handle window closing - save config and stop monitoring"""
        if self.bot.running:
            self.bot.stop_monitoring()
        self.root.destroy()
    
    def setup_styles(self):
        """Setup dark theme styles with modern look"""
        style = ttk.Style()
        
        
        style.theme_use('clam')
        
        
        bg_color = '#1e1e1e'
        card_color = '#2d2d2d'
        accent_color = '#3b82f6'
        text_color = '#ffffff'
        secondary_text = '#a1a1aa'
        
        
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
        
        
        self.title_label = tk.Label(
            self.header_frame,
            text="Screenshot Discord Bot",
            font=('Segoe UI', 28, 'bold'),
            fg='#3b82f6',
            bg='#1e1e1e'
        )
        self.title_label.pack(expand=True)
        
        
        self.subtitle_label = tk.Label(
            self.header_frame,
            text="",
            font=('Segoe UI', 12),
            fg='#a1a1aa',
            bg='#1e1e1e'
        )
        self.subtitle_label.pack()
        
        
        self.typewriter_text = "Automated screenshot capture and Discord integration"
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
            
            self.root.after(30, self.animate_fade_in)
    
    def animate_pulse(self):
        """Animate pulsing effect for monitoring status"""
        if hasattr(self, 'status_indicator') and self.bot.running:
            self.pulse_scale += 0.02 * self.pulse_direction
            if self.pulse_scale >= 1.1:
                self.pulse_direction = -1
            elif self.pulse_scale <= 0.9:
                self.pulse_direction = 1
            
            
            pulse_size = int(12 * self.pulse_scale)
            self.status_indicator.config(font=('Segoe UI', pulse_size, 'bold'))
        
        self.root.after(50, self.animate_pulse)
    
    def create_widgets(self):
        """Create all GUI widgets including scrollable content area."""
        
        self.canvas = tk.Canvas(self.root, bg='#1e1e1e', highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg='#1e1e1e')
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(30, 0), pady=(20, 20))
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 30), pady=(20, 20))
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.scrollable_frame.bind("<Configure>", 
                                   lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Left and Right split
        left_frame = tk.Frame(self.scrollable_frame, bg='#1e1e1e')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))

        self.right_frame = tk.Frame(self.scrollable_frame, bg='#1e1e1e', width=350)
        # Note: self.right_frame is not expanded vertically to prevent stretching
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Left side cards
        config_card = self.create_card(left_frame, "Configuration")
        config_card.pack(fill=tk.X, pady=(0, 20))
        
        # Webhook URL
        webhook_frame = tk.Frame(config_card, bg='#2d2d2d')
        webhook_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        webhook_label = tk.Label(webhook_frame, text="Discord Webhook URL", 
                                font=('Segoe UI', 10, 'bold'), fg='#ffffff', bg='#2d2d2d')
        webhook_label.pack(anchor=tk.W)
        webhook_desc = tk.Label(webhook_frame, text="Enter your Discord webhook URL to send screenshots",
                                font=('Segoe UI', 8), fg='#a1a1aa', bg='#2d2d2d')
        webhook_desc.pack(anchor=tk.W)
        self.webhook_var = tk.StringVar(value=self.bot.webhook_url)
        webhook_entry = ttk.Entry(webhook_frame, textvariable=self.webhook_var, style='Modern.TEntry')
        webhook_entry.pack(fill=tk.X, ipady=5, pady=(5, 0))

        # Application Name
        app_frame = tk.Frame(config_card, bg='#2d2d2d')
        app_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        app_label = tk.Label(app_frame, text="Application Name", 
                            font=('Segoe UI', 10, 'bold'), fg='#ffffff', bg='#2d2d2d')
        app_label.pack(anchor=tk.W)
        app_desc = tk.Label(app_frame, text="Choose which application to screenshot",
                            font=('Segoe UI', 8), fg='#a1a1aa', bg='#2d2d2d')
        app_desc.pack(anchor=tk.W)
        self.app_var = tk.StringVar(value=self.bot.app_name)
        
        app_entry_frame = tk.Frame(app_frame, bg='#2d2d2d')
        app_entry_frame.pack(fill=tk.X, pady=(5,0))
        
        app_entry = ttk.Entry(app_entry_frame, textvariable=self.app_var, style='Modern.TEntry')
        app_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        app_btn = tk.Button(app_entry_frame, text="Browse", font=('Segoe UI', 9, 'bold'),
                            bg='#6b7280', fg='white', bd=0, padx=10, pady=5,
                            cursor='hand2', command=self.show_applications)
        app_btn.pack(side=tk.LEFT, padx=(5, 0))


        # Custom Message
        message_frame = tk.Frame(config_card, bg='#2d2d2d')
        message_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        message_label = tk.Label(message_frame, text="Custom Message", 
                                font=('Segoe UI', 10, 'bold'), fg='#ffffff', bg='#2d2d2d')
        message_label.pack(anchor=tk.W)
        
        message_desc = tk.Label(message_frame, text="customize the message sent with screenshots. Leave empty for only image",
                                font=('Segoe UI', 8), fg='#a1a1aa', bg='#2d2d2d')
        message_desc.pack(anchor=tk.W)
        
        # Frame to hold entry and help button together
        entry_help_frame = tk.Frame(message_frame, bg='#2d2d2d')
        entry_help_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.message_var = tk.StringVar(value=self.bot.custom_message)
        message_entry = ttk.Entry(entry_help_frame, textvariable=self.message_var, style='Modern.TEntry')
        message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        
        message_help_btn = tk.Button(entry_help_frame, text="?", font=('Segoe UI', 8, 'bold'),
                                     bg='#374151', fg='#ffffff', bd=0, width=2,
                                     cursor='hand2', command=self.show_message_help)
        message_help_btn.pack(side=tk.LEFT, padx=(5, 0))

        self.message_preview = tk.Label(message_frame, text="", 
                                       font=('Segoe UI', 8, 'italic'), fg='#4ade80', bg='#2d2d2d')
        self.message_preview.pack(anchor=tk.W, pady=(5, 0))
        self.message_var.trace('w', self.update_message_preview)
        self.update_message_preview()
        
        # Interval & Delete after send
        options_frame = tk.Frame(config_card, bg='#2d2d2d')
        options_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        interval_frame = tk.Frame(options_frame, bg='#2d2d2d')
        interval_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        interval_label = tk.Label(interval_frame, text="Interval (seconds):", 
                                font=('Segoe UI', 10), fg='#ffffff', bg='#2d2d2d')
        interval_label.pack(anchor=tk.W)
        self.interval_var = tk.StringVar(value=str(self.bot.interval))
        interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_var, style='Modern.TEntry')
        interval_entry.pack(fill=tk.X, ipady=5, pady=(5, 0))
        
        # New Toggle Switch for Delete After Send
        toggle_frame = tk.Frame(options_frame, bg='#2d2d2d')
        toggle_frame.pack(side=tk.RIGHT, padx=(10, 0), pady=(15, 0))
        toggle_label = tk.Label(toggle_frame, text="Delete after send:",
                                font=('Segoe UI', 10), fg='#ffffff', bg='#2d2d2d')
        toggle_label.pack(side=tk.LEFT, padx=(0, 5))
        self.delete_var = tk.BooleanVar(value=self.bot.delete_after_send)
        self.delete_toggle = ToggleSwitch(
            toggle_frame, 
            bg='#2d2d2d', 
            on_command=lambda: self.delete_var.set(True), 
            off_command=lambda: self.delete_var.set(False)
        )
        self.delete_toggle.pack(side=tk.LEFT)
        if self.bot.delete_after_send:
            self.delete_toggle.state = True
            self.delete_toggle.draw_toggle()
            
        # Save Configuration Button
        save_frame = tk.Frame(config_card, bg='#2d2d2d')
        save_frame.pack(fill=tk.X, padx=20, pady=(10, 20))
        
        self.save_btn = tk.Button(save_frame, text="Save Configuration",
                                  font=('Segoe UI', 11, 'bold'), bg='#6366f1', fg='white',
                                  bd=0, padx=20, pady=10, cursor='hand2',
                                  command=self.save_config_animated)
        self.save_btn.pack(expand=True)


        # Actions Card
        action_card = self.create_card(left_frame, "Actions")
        action_card.pack(fill=tk.X, pady=(0, 20))
        
        btn_frame = tk.Frame(action_card, bg='#2d2d2d', padx=20, pady=20)
        btn_frame.pack(fill=tk.X)
        
        self.screenshot_btn = tk.Button(btn_frame, text="Take Screenshot",
                                        font=('Segoe UI', 11, 'bold'), bg='#3b82f6', fg='white',
                                        bd=0, padx=20, pady=10, cursor='hand2',
                                        command=self.take_screenshot_animated)
        self.screenshot_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.start_btn = tk.Button(btn_frame, text="Start Monitoring",
                                    font=('Segoe UI', 11, 'bold'), bg='#22c55e', fg='white',
                                    bd=0, padx=20, pady=10, cursor='hand2',
                                    command=self.start_monitoring_animated)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        
        self.stop_btn = tk.Button(btn_frame, text="Stop Monitoring",
                                   font=('Segoe UI', 11, 'bold'), bg='#ef4444', fg='white',
                                   bd=0, padx=20, pady=10, cursor='hand2', state='disabled',
                                   command=self.stop_monitoring_animated)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Show Console Toggle
        console_toggle_frame = tk.Frame(action_card, bg='#2d2d2d')
        console_toggle_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        console_label = tk.Label(console_toggle_frame, text="Show Status Log:",
                                font=('Segoe UI', 10), fg='#ffffff', bg='#2d2d2d')
        console_label.pack(side=tk.LEFT, padx=(0, 5))
        self.show_console_var = tk.BooleanVar(value=True)
        self.show_console_toggle = ToggleSwitch(
            console_toggle_frame,
            bg='#2d2d2d',
            on_command=self.show_console,
            off_command=self.hide_console
        )
        self.show_console_toggle.pack(side=tk.LEFT)
        self.show_console_toggle.state = True
        self.show_console_toggle.draw_toggle()

        # Right side: Status & Activity
        self.status_card = self.create_card(self.right_frame, "Status & Activity")
        self.status_card.pack(fill=tk.BOTH, expand=True)

        status_header = tk.Frame(self.status_card, bg='#2d2d2d')
        status_header.pack(fill=tk.X, padx=20, pady=(10, 0))

        self.status_indicator = tk.Label(status_header, text="●", font=('Segoe UI', 12, 'bold'),
                                        fg='#ef4444', bg='#2d2d2d')
        self.status_indicator.pack(side=tk.LEFT)

        self.status_text_label = tk.Label(status_header, text="Stopped", font=('Segoe UI', 11, 'bold'),
                                         fg='#ffffff', bg='#2d2d2d')
        self.status_text_label.pack(side=tk.LEFT, padx=(5, 0))

        log_frame = tk.Frame(self.status_card, bg='#2d2d2d')
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))

        self.status_text = tk.Text(log_frame, font=('Consolas', 9), bg='#1a1a1a',
                                  fg='#e5e5e5', bd=0, padx=15, pady=10,
                                  insertbackground='#3b82f6', selectbackground='#374151')

        scrollbar = tk.Scrollbar(log_frame, bg='#374151', troughcolor='#2d2d2d',
                                borderwidth=0, highlightthickness=0)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.status_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.status_text.yview)

        self.status_text.tag_configure("success", foreground="#4ade80")
        self.status_text.tag_configure("error", foreground="#ef4444")
        self.status_text.tag_configure("warning", foreground="#f59e0b")
        self.status_text.tag_configure("info", foreground="#3b82f6")
        self.status_text.tag_configure("timestamp", foreground="#6b7280")
    
    def _on_mousewheel(self, event):
        """Handles mousewheel scrolling for the canvas."""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def show_console(self):
        """Show the status and activity log frame and resize the window."""
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))
        current_height = self.root.winfo_height()
        self.root.geometry(f"1100x{current_height}")
    
    def hide_console(self):
        """Hide the status and activity log frame and resize the window."""
        self.right_frame.pack_forget()
        current_height = self.root.winfo_height()
        self.root.geometry(f"700x{current_height}")
    
    def show_message_help(self):
        """Show help dialog for message variables"""
        help_window = tk.Toplevel(self.root)
        help_window.title("Message Variables Help")
        help_window.geometry("600x500")
        help_window.configure(bg='#1e1e1e')
        help_window.resizable(False, False)
        help_window.transient(self.root)
        help_window.grab_set()
        
        
        header = tk.Frame(help_window, bg='#374151', height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(header, text="Available Message Variables",
                        font=('Segoe UI', 16, 'bold'), fg='#ffffff', bg='#374151')
        title.pack(expand=True)
        
        
        content_frame = tk.Frame(help_window, bg='#1e1e1e')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        help_text = tk.Text(content_frame, font=('Consolas', 10), bg='#2d2d2d',
                           fg='#ffffff', bd=0, padx=15, pady=15, wrap=tk.WORD)
        help_text.pack(fill=tk.BOTH, expand=True)
        
        help_content = """Available Variables (use with curly braces):

{app_name}     - Name of the target application
{timestamp}    - Full date and time (YYYY-MM-DD HH:MM:SS)
{date}         - Date only (YYYY-MM-DD)  
{time}         - Time only (HH:MM:SS)
{day}          - Day of the week (Monday, Tuesday, etc.)
{month}        - Month name (January, February, etc.)
{year}         - Year (YYYY)

Examples:

"Screenshot of {app_name} taken at {time}"
→ "Screenshot of notepad taken at 14:30:25"

"{app_name} capture on {day}"
→ "notepad capture on Monday"

"Daily {app_name} screenshot - {date}"
→ "Daily notepad screenshot - 2024-01-15"

"Custom message without variables"
→ "Custom message without variables"

Leave empty for no message (image only).
"""
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
        
        
        close_btn = tk.Button(content_frame, text="Close", font=('Segoe UI', 11, 'bold'),
                             bg='#3b82f6', fg='white', bd=0, padx=30, pady=10,
                             cursor='hand2', command=help_window.destroy)
        close_btn.pack(pady=(10, 0))
    
    def update_message_preview(self, *args):
        """Update the message preview"""
        try:
            
            old_message = self.bot.custom_message
            self.bot.custom_message = self.message_var.get()
            preview = self.bot.format_message()
            self.bot.custom_message = old_message
            
            if preview and len(preview) > 80:
                preview = preview[:77] + "..."
            
            self.message_preview.config(text=f"Preview: {preview}" if preview else "Preview: (no message)")
        except Exception:
            self.message_preview.config(text="Preview: (invalid format)")
    
    def save_config_animated(self):
        """Save configuration with button animation"""
        self.animate_button_click(self.save_btn)
        self.update_config()
        self.bot.save_config()
        self.log_message_colored("Configuration saved successfully!", 'success')
        self.show_notification("Success", "Configuration saved!", 'success')
    
    def create_card(self, parent, title):
        """Create a modern card with title"""
        card_frame = tk.Frame(parent, bg='#2d2d2d', relief='flat', bd=1)
        
        
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
            elif current_bg == '#6b7280':
                widget.config(bg='#4b5563')
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
            elif current_bg == '#4b5563':
                widget.config(bg='#6b7280')
    
    def show_applications(self):
        """Show running applications in a modern popup"""
        apps = self.bot.list_running_applications()
        
        app_window = tk.Toplevel(self.root)
        app_window.title("Select Application")
        app_window.geometry("500x600")
        app_window.configure(bg='#1e1e1e')
        app_window.resizable(False, False)
        
        
        app_window.transient(self.root)
        app_window.grab_set()
        
        
        header = tk.Frame(app_window, bg='#374151', height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(header, text="Select Target Application",
                        font=('Segoe UI', 16, 'bold'), fg='#ffffff', bg='#374151')
        title.pack(expand=True)
        
        
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
        
        
        list_frame = tk.Frame(app_window, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        
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
        
        
        all_apps = apps[:]
        for app in all_apps:
            listbox.insert(tk.END, app)
        
        def filter_apps():
            """Filter applications based on search"""
            query = search_var.get().lower()
            listbox.delete(0, tk.END)
            for app in all_apps:
                if query in app.lower():
                    listbox.insert(tk.END, app)
        
        search_var.trace('w', lambda *args: filter_apps())
        
        def select_app():
            """Select application with animation"""
            selection = listbox.curselection()
            if selection:
                selected_app = listbox.get(selection[0])
                self.app_var.set(selected_app.lower())
                
                
                for i in range(3):
                    listbox.config(selectbackground='#22c55e')
                    app_window.update()
                    self.root.after(100)
                    listbox.config(selectbackground='#3b82f6')
                    app_window.update()
                    self.root.after(100)
                
                app_window.destroy()
        
        
        btn_frame = tk.Frame(app_window, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        select_btn = tk.Button(btn_frame, text="Select Application",
                              font=('Segoe UI', 11, 'bold'), bg='#22c55e', fg='white',
                              bd=0, padx=30, pady=10, cursor='hand2',
                              command=select_app)
        select_btn.pack()
        
        
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
        
        
        notification.geometry("+{}+{}".format(
            self.root.winfo_x() + self.root.winfo_width() - 420,
            self.root.winfo_y() + 50
        ))
        
        
        notification.overrideredirect(True)
        
        
        content_frame = tk.Frame(notification, bg=self.status_colors.get(type_, '#3b82f6'))
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        title_label = tk.Label(content_frame, text=title, font=('Segoe UI', 12, 'bold'),
                              fg='white', bg=self.status_colors.get(type_, '#3b82f6'))
        title_label.pack(anchor=tk.W)
        
        msg_label = tk.Label(content_frame, text=message, font=('Segoe UI', 10),
                            fg='white', bg=self.status_colors.get(type_, '#3b82f6'),
                            wraplength=350)
        msg_label.pack(anchor=tk.W, pady=(5, 0))
        
        
        self.root.after(3000, notification.destroy)
    
    def update_config(self):
        """Update bot configuration from GUI"""
        self.bot.webhook_url = self.webhook_var.get().strip()
        self.bot.app_name = self.app_var.get().strip().lower()
        self.bot.custom_message = self.message_var.get().strip()
        try:
            self.bot.interval = int(self.interval_var.get())
        except ValueError:
            self.bot.interval = 60
            self.interval_var.set("60")
        self.bot.delete_after_send = self.delete_var.get()
    
    def log_message_colored(self, message, type_='info'):
        """Add colored message to status log with animation"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        
        self.status_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        
        if type_ == 'success':
            self.status_text.insert(tk.END, "✅ ", "success")
        elif type_ == 'error':
            self.status_text.insert(tk.END, "❌ ", "error")
        elif type_ == 'warning':
            self.status_text.insert(tk.END, "⚠ ", "warning")
        else:
            self.status_text.insert(tk.END, "ℹ ", "info")
        
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        
        
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
        webhook_status = "✓" if self.bot.webhook_url else "✗"
        app_status = "✓" if self.bot.app_name else "✗"
        
        if self.bot.running:
            self.status_indicator.config(fg='#22c55e', text="●")
            self.status_text_label.config(text="Monitoring Active", fg='#22c55e')
            self.start_btn.config(state='disabled', text="Running...")
            self.stop_btn.config(state='normal')
        else:
            self.status_indicator.config(fg='#ef4444', text="●")
            self.status_text_label.config(text="Stopped", fg='#ef4444')
            self.start_btn.config(state='normal', text="Start Monitoring")
            self.stop_btn.config(state='disabled')
        
        
        status = f"Webhook: {webhook_status} | App: {app_status} | Interval: {self.bot.interval}s"
        self.root.title(f"Screenshot Discord Bot - {status}")
    
    def update_status_loop(self):
        """Continuous status update with smooth transitions"""
        self.update_status()
        self.root.after(1000, self.update_status_loop)
    
    def run(self):
        """Start the GUI with fade-in animation"""
        
        self.root.update_idletasks()
        
        
        self.root.after(1000, lambda: self.log_message_colored("Welcome to Screenshot Discord Bot!", 'info'))
        if self.config_found:
            self.root.after(2000, lambda: self.log_message_colored("Config found, successfully loaded", 'success'))
        else:
            self.root.after(2000, lambda: self.log_message_colored("No previous configuration found. creating cfg.json", 'error'))
            self.root.after(3000, lambda: self.log_message_colored("successfully created cfg file", 'success'))
        
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
    print(f"Custom Message: {bot.custom_message if bot.custom_message else '✗ No message'}")
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
        print("4. Set Custom Message")
        print("5. Set Screenshot Interval")
        print("6. Toggle Delete After Send")
        print("7. Take Single Screenshot")
        print("8. Start Continuous Monitoring")
        print("9. Stop Monitoring")
        print("10. Save Configuration")
        print("11. Exit")
        
        try:
            choice = input("\nEnter your choice (1-11): ").strip()
            
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
                print("\n--- Custom Message Setup ---")
                print("Available variables: {app_name}, {timestamp}, {date}, {time}, {day}, {month}, {year}")
                print("Leave empty for no message (image only)")
                print(f"Current: {bot.custom_message}")
                message = input("Enter custom message: ").strip()
                bot.custom_message = message
                if message:
                    print(f"✓ Custom message set!")
                    print(f"Preview: {bot.format_message()}")
                else:
                    print("✓ Message cleared - will send image only")
                input("\nPress Enter to continue...")
                
            elif choice == "5":
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
                
            elif choice == "6":
                bot.delete_after_send = not bot.delete_after_send
                status = "enabled" if bot.delete_after_send else "disabled"
                print(f"✓ Delete after send {status}")
                input("\nPress Enter to continue...")
                
            elif choice == "7":
                success, message = bot.take_single_screenshot()
                print(message)
                input("\nPress Enter to continue...")
                
            elif choice == "8":
                success, message = bot.start_monitoring()
                print(message)
                input("\nPress Enter to continue...")
                
            elif choice == "9":
                success, message = bot.stop_monitoring()
                print(message)
                input("\nPress Enter to continue...")
                
            elif choice == "10":
                bot.save_config()
                print("✓ Configuration saved successfully!")
                input("\nPress Enter to continue...")
                
            elif choice == "11":
                if bot.running:
                    print("Stopping monitoring...")
                    bot.stop_monitoring()
                print("Saving configuration...")
                bot.save_config()
                print("Goodbye!")
                break
                
            else:
                print("✗ Invalid choice! Please enter 1-11.")
                input("\nPress Enter to continue...")
                
        except KeyboardInterrupt:
            if bot.running:
                print("\n\nStopping monitoring...")
                bot.stop_monitoring()
            print("Saving configuration...")
            bot.save_config()
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

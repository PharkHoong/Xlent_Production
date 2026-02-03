import os
import random
import threading
import socket
import time
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QWidget,
    QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QInputDialog,
    QMessageBox, QProgressDialog, QLabel,
    QLineEdit, QSpinBox, QStackedWidget,
    QGroupBox, QScrollArea, QTextEdit,
)
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QPixmap, QTextCursor
from PySide6.QtCore import Signal, QObject, QTimer, Qt, QRectF, QPointF
from annotator import AnnotationWidget

from PIL import Image
import cv2
import numpy as np

# Import camera capture function
try:
    from camera import AutoCaptureFlow
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False
    print("Warning: camera_capture module not found. Camera button will be disabled.")


class CameraSignals(QObject):
    """Signals for camera thread communication"""
    finished = Signal(bool, str, object)  # success, message, image_path


class TrainingSignals(QObject):
    """Signals for training thread communication"""
    progress = Signal(int, str, str)  # progress_percentage, status_message, time_remaining
    finished = Signal(bool, str)  # success, message


class PredictionSignals(QObject):
    """Signals for prediction thread communication"""
    progress = Signal(int, str)  # progress_percentage, status_message
    finished = Signal(bool, str, list)  # success, message, predictions
    image_ready = Signal(str)  # path to predicted image


class TCPClientSignals(QObject):
    """Signals for TCP client communication"""
    connection_status = Signal(str, bool)  # message, is_connected
    message_received = Signal(str)  # received message
    message_sent = Signal(str)  # sent message


class LabelingPage(QWidget):
    """Labeling page with full annotation capabilities + TCP functionality"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.capture_folder = None
        self.image_files = []
        self.current_index = -1
        self.image_path = None

        # TCP related
        self.tcp_socket = None
        self.tcp_connected = False
        self.tcp_thread = None
        self.listening_thread = None
        self.scan_data_received = ""

        # Add these attributes for automatic cropping
        self.last_bounding_box = None  # Store the last drawn bounding box
        self.last_box_label = None  # Store the label of the last box
        self.cropped_save_folder = "C:\\Users\\SiP-PHChin\\OneDrive - SIP Technology (M) Sdn Bhd\\Desktop\\Picture"
        self.tcp_received_text = ""  # Store the latest TCP received text

        # TCP related
        self.tcp_socket = None
        self.tcp_connected = False
        self.tcp_thread = None
        self.listening_thread = None
        self.scan_data_received = ""

        # Initialize signals
        self.camera_signals = CameraSignals()
        self.camera_signals.finished.connect(self.on_camera_finished)

        self.tcp_signals = TCPClientSignals()
        self.tcp_signals.connection_status.connect(self.on_tcp_connection_status)
        self.tcp_signals.message_received.connect(self.on_tcp_message_received)
        self.tcp_signals.message_sent.connect(self.on_tcp_message_sent)

        self.init_ui()

    def init_ui(self):
        # Create the Picture folder if it doesn't exist
        os.makedirs(self.cropped_save_folder, exist_ok=True)

        # Use the same layout structure as MainWindow
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # ---------- Toolbar (same as annotation page but without Open Folder) ----------
        top_bar = QHBoxLayout()
        top_bar.setSpacing(5)

        # Add a timer to track bounding box changes
        self.box_tracker_timer = QTimer()
        self.box_tracker_timer.timeout.connect(self.track_bounding_box_changes)
        self.box_tracker_timer.start(300)  # Check every 300ms

        # Track previous box count
        self.previous_box_count = 0

        # Capture from Camera button
        self.capture_btn = QPushButton("Capture from Camera")
        self.capture_btn.clicked.connect(self.capture_from_camera)
        if not CAMERA_AVAILABLE:
            self.capture_btn.setEnabled(False)
            self.capture_btn.setToolTip("Camera module not available")
        top_bar.addWidget(self.capture_btn)

        # Navigation buttons
        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.clicked.connect(self.prev_image)
        self.prev_btn.setEnabled(False)
        top_bar.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_image)
        self.next_btn.setEnabled(False)
        top_bar.addWidget(self.next_btn)

        # Annotation tools
        self.undo_btn = QPushButton("↶ Undo")
        self.undo_btn.clicked.connect(self.undo)
        self.undo_btn.setEnabled(False)
        top_bar.addWidget(self.undo_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setEnabled(False)
        top_bar.addWidget(self.delete_btn)

        # TCP Connection button
        self.tcp_connect_btn = QPushButton("🔌 Connect TCP")
        self.tcp_connect_btn.clicked.connect(self.toggle_tcp_connection)
        self.tcp_connect_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        top_bar.addWidget(self.tcp_connect_btn)

        # Scan_ID button
        self.scan_id_btn = QPushButton("📡 Scan_ID")
        self.scan_id_btn.clicked.connect(self.scan_id)
        self.scan_id_btn.setStyleSheet("background-color: #795548; color: white;")
        self.scan_id_btn.setEnabled(False)
        top_bar.addWidget(self.scan_id_btn)

        # Back to main button
        back_btn = QPushButton("⬅ Back to Annotation")
        back_btn.clicked.connect(self.go_back)
        back_btn.setStyleSheet("background-color: #607D8B; color: white;")
        top_bar.addWidget(back_btn)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # ---------- Labels Section (same as annotation page) ----------
        label_bar = QHBoxLayout()
        label_bar.setSpacing(5)

        # Label combo box
        self.labels = ["object0"]
        self.label_colors = {"object0": QColor(255, 0, 0)}
        self.label_counter = 0

        self.label_combo = QComboBox()
        self.label_combo.addItems(self.labels)
        label_bar.addWidget(self.label_combo)

        # Add label button
        self.add_label_btn = QPushButton("+")
        self.add_label_btn.setFixedWidth(40)
        self.add_label_btn.clicked.connect(self.auto_add_label)
        self.add_label_btn.setToolTip("Add new label (object1, object2, ...)")
        label_bar.addWidget(self.add_label_btn)

        label_bar.addStretch()
        main_layout.addLayout(label_bar)

        # ---------- Main Content Area ----------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # ---------- Left Column: Annotation Viewer (70%) ----------
        left_column = QVBoxLayout()

        # Use the same AnnotationWidget as main page
        self.viewer = AnnotationWidget(
            self.get_current_label,
            self.get_label_color
        )
        left_column.addWidget(self.viewer, 1)

        # Image info label
        self.image_info_label = QLabel("No image loaded")
        self.image_info_label.setStyleSheet("color: #666; font-size: 12px; padding: 2px;")
        left_column.addWidget(self.image_info_label)

        content_layout.addLayout(left_column, 70)

        # ---------- Right Column: TCP Controls (30%) ----------
        right_column = QVBoxLayout()
        right_column.setSpacing(10)

        # TCP Connection Settings Group
        tcp_group = QGroupBox("TCP/IP Connection Settings")
        tcp_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #795548;
                border-radius: 5px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #795548;
            }
        """)

        tcp_layout = QVBoxLayout()

        # Host and Port inputs
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Host:"))
        self.host_edit = QLineEdit("127.0.0.1")
        self.host_edit.setPlaceholderText("Server IP")
        form_layout.addWidget(self.host_edit)

        form_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(1220)
        form_layout.addWidget(self.port_spin)

        tcp_layout.addLayout(form_layout)

        # Connection status
        self.connection_status_label = QLabel("Status: Disconnected")
        self.connection_status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px 0;")
        tcp_layout.addWidget(self.connection_status_label)

        tcp_group.setLayout(tcp_layout)
        right_column.addWidget(tcp_group)

        # Scan_ID Instructions Group
        instructions_group = QGroupBox("Scan_ID Instructions")
        instructions_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #2196F3;
                border-radius: 5px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2196F3;
            }
        """)

        instructions_layout = QVBoxLayout()

        instructions = QLabel(
            "📋 How to use Scan_ID:\n\n"
            "1. Capture or navigate to an image\n"
            "2. Draw bounding box(es) on objects\n"
            "3. Connect to TCP server\n"
            "4. Click Scan_ID to send coordinates\n\n"
            "The latest bounding box will be sent\n"
            "to the server for processing."
        )
        instructions.setStyleSheet("font-size: 12px; color: #555; padding: 8px;")
        instructions.setWordWrap(True)
        instructions_layout.addWidget(instructions)

        instructions_group.setLayout(instructions_layout)
        right_column.addWidget(instructions_group)

        # Received Data Group
        data_group = QGroupBox("TCP Messages")
        data_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #9C27B0;
                border-radius: 5px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #9C27B0;
            }
        """)

        data_layout = QVBoxLayout()

        # Create scrollable text area for messages
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(150)
        scroll_area.setMaximumHeight(250)

        self.tcp_messages_display = QTextEdit()
        self.tcp_messages_display.setReadOnly(True)
        self.tcp_messages_display.setLineWrapMode(QTextEdit.NoWrap)
        self.tcp_messages_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: none;
                font-family: monospace;
                font-size: 11px;
                color: #495057;
                padding: 5px;
            }
        """)

        scroll_area.setWidget(self.tcp_messages_display)
        data_layout.addWidget(scroll_area)

        # Clear messages button
        clear_messages_btn = QPushButton("🗑️ Clear Messages")
        clear_messages_btn.clicked.connect(self.clear_tcp_messages)
        clear_messages_btn.setMaximumWidth(120)
        data_layout.addWidget(clear_messages_btn, 0, Qt.AlignRight)

        data_group.setLayout(data_layout)
        right_column.addWidget(data_group)

        content_layout.addLayout(right_column, 30)

        main_layout.addLayout(content_layout)

        # ---------- Status Bar ----------
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

        # ---------- Shortcuts ----------
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_selected)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.scan_id)
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self.auto_add_label)

    def track_bounding_box_changes(self):
        """Track when new bounding boxes are drawn"""
        if hasattr(self.viewer, 'boxes'):
            current_count = len(self.viewer.boxes)

            # If new boxes were added
            if current_count > self.previous_box_count:
                # Get the latest box
                latest_box, latest_label = self.viewer.boxes[-1]

                # Store for auto-cropping
                self.last_bounding_box = (latest_box, latest_label)
                self.last_box_label = latest_label

                # Update TCP messages
                timestamp = time.strftime("%H:%M:%S")
                self.update_tcp_messages(f"[{timestamp}] 📦 New bounding box drawn: {latest_label}")

                # Update the Scan_ID button state
                self.update_scan_id_button_state()

            self.previous_box_count = current_count

    # ---------- Camera Capture Methods ----------
    def capture_from_camera(self):
        """Start camera capture in a separate thread"""
        # Use same folder as main window if available
        if self.capture_folder is None:
            self.capture_folder = "C:\\Users\\SiP-PHChin\\OneDrive - SIP Technology (M) Sdn Bhd\\Desktop\\Capture Image"

        # Create directory if it doesn't exist
        os.makedirs(self.capture_folder, exist_ok=True)

        self.capture_btn.setEnabled(False)
        self.capture_btn.setText("Capturing...")
        self.status_label.setText("Capturing image...")

        def run_capture():
            def callback(success, message, image_path):
                if success and image_path:
                    # Move/rename captured image to chosen folder
                    base_name = os.path.basename(image_path)
                    save_path = os.path.join(self.capture_folder, base_name)

                    # Ensure unique filename
                    count = 1
                    name, ext = os.path.splitext(base_name)
                    while os.path.exists(save_path):
                        save_path = os.path.join(self.capture_folder, f"{name}_{count}{ext}")
                        count += 1

                    os.rename(image_path, save_path)
                    image_path = save_path

                # Emit signal to update GUI
                self.camera_signals.finished.emit(success, message, image_path)

            # Call the camera capture function
            AutoCaptureFlow(callback=callback)

        thread = threading.Thread(target=run_capture, daemon=True)
        thread.start()

    def on_camera_finished(self, success, message, image_path):
        """Handle camera capture completion"""
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("Capture from Camera")

        if success and image_path:
            # Load the captured image
            if os.path.exists(image_path):
                # Add to image list if not already there
                if image_path not in self.image_files:
                    self.image_files.append(image_path)
                    self.image_files.sort()

                # Find index and load
                self.current_index = self.image_files.index(image_path)
                self.load_current_image()

                # Update TCP messages
                timestamp = time.strftime("%H:%M:%S")
                self.update_tcp_messages(f"[{timestamp}] 📸 Captured image: {os.path.basename(image_path)}")
        else:
            QMessageBox.critical(self, "Capture Failed",
                                 f"Camera capture failed!\n{message}")
            self.status_label.setText("Capture failed")

    # ---------- Image Navigation Methods ----------
    def load_current_image(self):
        """Load the current image into the viewer"""
        if self.current_index < 0 or self.current_index >= len(self.image_files):
            return

        path = self.image_files[self.current_index]

        # Load image using viewer's method
        self.viewer.load_image(path)
        self.image_path = path

        # Reset bounding box tracking
        self.last_bounding_box = None
        self.last_box_label = None
        self.previous_box_count = 0

        # Update image info
        self.image_info_label.setText(f"{os.path.basename(path)} ({self.current_index + 1}/{len(self.image_files)})")
        self.status_label.setText(f"Loaded: {os.path.basename(path)}")

        # Enable navigation buttons
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)
        self.undo_btn.setEnabled(True)

        # Update Scan_ID button state
        self.update_scan_id_button_state()

    def view_saved_cropped_images(self):
        """Open the folder containing saved cropped images"""
        try:
            if os.path.exists(self.cropped_save_folder):
                os.startfile(self.cropped_save_folder)  # Opens folder in Windows Explorer
                self.update_tcp_messages(f"[System] Opened save folder: {self.cropped_save_folder}")
            else:
                QMessageBox.information(self, "Folder Not Found",
                                        f"Save folder does not exist:\n{self.cropped_save_folder}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot open folder:\n{str(e)}")

    def next_image(self):
        """Navigate to next image"""
        if self.current_index < 0:
            return
        self.save_current()
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_current_image()

    def prev_image(self):
        """Navigate to previous image"""
        if self.current_index < 0:
            return
        self.save_current()
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()

    def save_current(self):
        """Save annotations for current image"""
        if hasattr(self, "image_path") and self.image_path:
            # Use viewer's save method
            if hasattr(self.viewer, 'save_annotations'):
                self.viewer.save_annotations(self.image_path)

    # ---------- Annotation Methods ----------
    def get_current_label(self):
        """Get currently selected label"""
        return self.label_combo.currentText()

    def get_label_color(self, label):
        """Get color for a label"""
        return self.label_colors.get(label, QColor(255, 255, 255))

    def auto_add_label(self):
        """Automatically add a sequentially numbered label"""
        self.label_counter += 1
        new_label = f"object{self.label_counter}"

        if new_label not in self.labels:
            self.labels.append(new_label)
            self.label_colors[new_label] = self.generate_color()
            self.label_combo.addItem(new_label)
            self.label_combo.setCurrentText(new_label)

            self.status_label.setText(f"Added label: {new_label}")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

    def generate_color(self):
        """Generate a random color for new labels"""
        hue = random.randint(0, 359)
        saturation = random.randint(150, 255)
        value = random.randint(150, 255)
        return QColor.fromHsv(hue, saturation, value)

    def undo(self):
        """Undo last annotation"""
        if hasattr(self.viewer, 'undo_last'):
            self.viewer.undo_last()

    def delete_selected(self):
        """Delete selected annotation"""
        if hasattr(self.viewer, 'delete_selected'):
            self.viewer.delete_selected()

    # ---------- TCP/IP Methods ----------
    def toggle_tcp_connection(self):
        """Toggle TCP connection on/off"""
        if self.tcp_connected:
            self.disconnect_tcp()
        else:
            self.connect_tcp()

    def connect_tcp(self):
        """Establish TCP connection"""
        host = self.host_edit.text().strip()
        port = self.port_spin.value()

        if not host:
            QMessageBox.warning(self, "Invalid Input", "Please enter a host address")
            return

        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.settimeout(2)

            self.tcp_connect_btn.setEnabled(False)
            self.tcp_connect_btn.setText("Connecting...")
            self.connection_status_label.setText(f"Status: Connecting to {host}:{port}...")

            def connect_thread():
                try:
                    self.tcp_socket.connect((host, port))
                    self.tcp_connected = True
                    self.tcp_signals.connection_status.emit(f"Connected to {host}:{port}", True)
                    self.start_listening()
                except socket.error as e:
                    self.tcp_signals.connection_status.emit(f"Connection failed: {str(e)}", False)
                    self.tcp_socket = None

            self.tcp_thread = threading.Thread(target=connect_thread, daemon=True)
            self.tcp_thread.start()

        except Exception as e:
            self.on_tcp_connection_status(f"Connection error: {str(e)}", False)

    def disconnect_tcp(self):
        """Close TCP connection"""
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except:
                pass

        self.tcp_connected = False
        self.tcp_socket = None
        self.tcp_connect_btn.setText("🔌 Connect TCP")
        self.tcp_connect_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.tcp_connect_btn.setEnabled(True)
        self.scan_id_btn.setEnabled(False)
        self.connection_status_label.setText("Status: Disconnected")
        self.update_tcp_messages("[System] Disconnected from server")

    def start_listening(self):
        """Start listening for incoming messages"""

        def listen_thread():
            while self.tcp_connected and self.tcp_socket:
                try:
                    data = self.tcp_socket.recv(1024)
                    if data:
                        message = data.decode('utf-8').strip()
                        self.tcp_signals.message_received.emit(message)
                    else:
                        if self.tcp_connected:
                            self.tcp_signals.connection_status.emit("Server disconnected", False)
                        break
                except socket.timeout:
                    continue
                except socket.error:
                    if self.tcp_connected:
                        self.tcp_signals.connection_status.emit("Connection lost", False)
                    break

        self.listening_thread = threading.Thread(target=listen_thread, daemon=True)
        self.listening_thread.start()

    def scan_id(self):
        """Send bounding box coordinates via TCP"""
        if not self.tcp_connected or not self.tcp_socket:
            QMessageBox.warning(self, "Not Connected", "Please connect to TCP server first")
            return

        if not hasattr(self.viewer, 'boxes') or not self.viewer.boxes:
            QMessageBox.warning(self, "No Bounding Boxes", "Please draw at least one bounding box first")
            return

        # Get the latest bounding box
        if self.viewer.boxes:
            latest_box, latest_label = self.viewer.boxes[-1]

            # Store for auto-cropping
            self.last_bounding_box = (latest_box, latest_label)
            self.last_box_label = latest_label

            # Get image dimensions from viewer
            if hasattr(self.viewer, 'pixmap') and self.viewer.pixmap:
                img_width = self.viewer.pixmap.width()
                img_height = self.viewer.pixmap.height()

                if img_width > 0 and img_height > 0:
                    # Calculate normalized coordinates (YOLO format)
                    x_center = (latest_box.x() + latest_box.width() / 2) / img_width
                    y_center = (latest_box.y() + latest_box.height() / 2) / img_height
                    width = latest_box.width() / img_width
                    height = latest_box.height() / img_height

                    # Create message in YOLO format
                    # Get label ID from combo box
                    label_text = self.label_combo.currentText()
                    label_id = 0  # Default
                    if label_text.startswith("object"):
                        try:
                            label_id = int(label_text.replace("object", ""))
                        except:
                            label_id = 0

                    message = f"{label_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"

                    try:
                        self.tcp_socket.sendall(message.encode('utf-8'))
                        self.tcp_signals.message_sent.emit(message)

                        timestamp = time.strftime("%H:%M:%S")
                        self.update_tcp_messages(f"[{timestamp}] 📡 Sent bounding box coordinates")
                        self.update_tcp_messages(f"  Label: {label_text} (ID: {label_id})")
                        self.update_tcp_messages(f"  Coordinates: {message}")

                        self.status_label.setText("Bounding box coordinates sent to server")

                        # Show confirmation
                        QMessageBox.information(
                            self,
                            "Coordinates Sent",
                            f"✅ Bounding box coordinates sent!\n\n"
                            f"Server: {self.host_edit.text()}:{self.port_spin.value()}\n"
                            f"Label: {label_text}\n"
                            f"Coordinates: {message}"
                        )

                    except socket.error as e:
                        self.update_tcp_messages(f"[Error] Failed to send: {str(e)}")
                        QMessageBox.critical(self, "Send Failed", f"Failed to send coordinates:\n{str(e)}")
                else:
                    QMessageBox.warning(self, "Invalid Image", "Cannot get image dimensions")
            else:
                QMessageBox.warning(self, "No Image", "Please load an image first")
        else:
            QMessageBox.warning(self, "No Boxes", "Please draw a bounding box first")

    def update_scan_id_button_state(self):
        """Update Scan_ID button enabled state"""
        has_image = hasattr(self, 'image_path') and self.image_path
        has_boxes = hasattr(self.viewer, 'boxes') and len(self.viewer.boxes) > 0
        is_connected = self.tcp_connected

        self.scan_id_btn.setEnabled(has_image and has_boxes and is_connected)
        self.delete_btn.setEnabled(has_boxes)

    # ---------- TCP Signal Handlers ----------
    def on_tcp_connection_status(self, message, is_connected):
        """Handle TCP connection status changes"""
        self.tcp_connected = is_connected
        self.tcp_connect_btn.setEnabled(True)

        if is_connected:
            self.tcp_connect_btn.setText("🔌 Disconnect TCP")
            self.tcp_connect_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
            self.connection_status_label.setText(
                f"Status: Connected to {self.host_edit.text()}:{self.port_spin.value()}")
            self.update_tcp_messages("[System] Connected to server")
        else:
            self.tcp_connect_btn.setText("🔌 Connect TCP")
            self.tcp_connect_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            self.connection_status_label.setText(f"Status: {message}")
            self.update_tcp_messages(f"[System] {message}")

        self.update_scan_id_button_state()

    def on_tcp_message_received(self, message):
        """Handle received TCP messages"""
        timestamp = time.strftime("%H:%M:%S")
        self.update_tcp_messages(f"[{timestamp}] 📥 Received: {message}")
        self.status_label.setText(f"TCP: {message[:50]}..." if len(message) > 50 else f"TCP: {message}")

        # Store received data
        self.scan_data_received = message
        self.tcp_received_text = message.strip()  # Store the received text for filename

        # NEW: Automatically crop and save image when TCP receives text
        self.auto_crop_and_save_on_tcp_message(message)

    def on_tcp_message_sent(self, message):
        """Handle sent TCP messages"""
        timestamp = time.strftime("%H:%M:%S")
        self.update_tcp_messages(f"[{timestamp}] 📤 Sent: {message}")

    def update_tcp_messages(self, message):
        """Update TCP messages display"""
        # Get current text
        current_text = self.tcp_messages_display.toPlainText()

        # Add new message at the beginning (newest first)
        if current_text:
            new_text = f"{message}\n{current_text}"
        else:
            new_text = message

        # Update the text edit
        self.tcp_messages_display.setPlainText(new_text)

        # Keep cursor at the beginning to show newest messages
        cursor = self.tcp_messages_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)  # FIXED: Use QTextCursor.MoveOperation.Start
        self.tcp_messages_display.setTextCursor(cursor)

    def clear_tcp_messages(self):
        """Clear all TCP messages"""
        self.tcp_messages_display.clear()
        self.status_label.setText("Messages cleared")

    def auto_crop_and_save_on_tcp_message(self, tcp_message):
        """Automatically crop and save image when TCP receives message"""
        # Check if we have the necessary components
        if not self.is_ready_for_auto_crop():
            self.update_tcp_messages(f"[AutoCrop] ⚠️ Not ready for auto-crop")
            return False

        # Sanitize the TCP message for filename (remove invalid characters)
        sanitized_text = self.sanitize_filename(tcp_message)
        if not sanitized_text:
            sanitized_text = "unknown"
            self.update_tcp_messages(f"[AutoCrop] ⚠️ Using 'unknown' as TCP text was empty")

        try:
            # Read the original image
            image = Image.open(self.image_path)
            img_width, img_height = image.size

            # Get the last drawn bounding box coordinates
            box, label = self.last_bounding_box

            # Convert QRectF coordinates to pixel integers
            x1 = max(0, int(box.x()))
            y1 = max(0, int(box.y()))
            x2 = min(img_width, int(box.x() + box.width()))
            y2 = min(img_height, int(box.y() + box.height()))

            # Validate box dimensions
            if x1 >= x2 or y1 >= y2:
                self.update_tcp_messages(f"[AutoCrop] ❌ Invalid bounding box dimensions")
                return False

            # Crop the image
            cropped_image = image.crop((x1, y1, x2, y2))

            # Generate filename in format: labelName_tcpipreceivedtext.bmp
            label_name = label.split()[0] if ' ' in label else label  # Take only first word if label has spaces
            filename = f"{label_name}_{sanitized_text}.bmp"
            save_path = os.path.join(self.cropped_save_folder, filename)

            # Ensure unique filename (add number if file exists)
            counter = 1
            while os.path.exists(save_path):
                filename = f"{label_name}_{sanitized_text}_{counter}.bmp"
                save_path = os.path.join(self.cropped_save_folder, filename)
                counter += 1

            # Save as BMP format
            cropped_image.save(save_path, "BMP")

            # Get crop dimensions
            crop_width = x2 - x1
            crop_height = y2 - y1

            # Update TCP messages
            self.update_tcp_messages(f"[AutoCrop] ✅ Auto-saved cropped image!")
            self.update_tcp_messages(f"[AutoCrop]   Filename: {filename}")
            self.update_tcp_messages(f"[AutoCrop]   Label: {label_name}")
            self.update_tcp_messages(f"[AutoCrop]   TCP Text: {sanitized_text}")
            self.update_tcp_messages(f"[AutoCrop]   Dimensions: {crop_width}x{crop_height} pixels")
            self.update_tcp_messages(f"[AutoCrop]   Saved to: {self.cropped_save_folder}")

            # Update status label
            self.status_label.setText(f"Auto-saved: {filename}")

            # Send confirmation back via TCP
            if self.tcp_connected and self.tcp_socket:
                try:
                    response = f"AUTO_CROP_SAVED: {filename}"
                    self.tcp_socket.sendall(response.encode('utf-8'))
                    self.tcp_signals.message_sent.emit(response)
                except socket.error as e:
                    self.update_tcp_messages(f"[Error] Failed to send confirmation: {str(e)}")

            # Show brief notification (optional, can be removed)
            QTimer.singleShot(100, lambda: self.show_auto_crop_notification(filename, label_name, sanitized_text))

            return True

        except Exception as e:
            error_msg = f"Auto-crop failed: {str(e)}"
            self.update_tcp_messages(f"[AutoCrop] ❌ {error_msg}")
            print(f"Auto-crop error: {e}")
            return False

    def is_ready_for_auto_crop(self):
        """Check if all conditions are met for auto-cropping"""
        # Check if image is loaded
        if not hasattr(self, 'image_path') or not self.image_path or not os.path.exists(self.image_path):
            return False

        # Check if bounding box exists
        if not self.last_bounding_box:
            self.update_tcp_messages(f"[AutoCrop] ❌ No bounding box drawn")
            return False

        # Check if label exists
        if not self.last_box_label:
            self.update_tcp_messages(f"[AutoCrop] ❌ No label for bounding box")
            return False

        # Check if save folder exists
        if not os.path.exists(self.cropped_save_folder):
            try:
                os.makedirs(self.cropped_save_folder, exist_ok=True)
            except:
                self.update_tcp_messages(f"[AutoCrop] ❌ Cannot create save folder")
                return False

        return True

    def sanitize_filename(self, text):
        """Sanitize TCP text for use in filename"""
        if not text:
            return "unknown"

        # Remove any non-alphanumeric characters (except underscore and dash)
        import re
        sanitized = re.sub(r'[^\w\-_]', '', text)

        # Trim length to reasonable size
        if len(sanitized) > 50:
            sanitized = sanitized[:50]

        # If empty after sanitization, use default
        if not sanitized:
            sanitized = "tcp_text"

        return sanitized

    def show_auto_crop_notification(self, filename, label_name, tcp_text):
        """Show a brief notification about auto-crop (non-modal)"""
        # Create a temporary message box that auto-closes
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Auto Crop & Save")
        msg_box.setText(f"✅ Auto-saved cropped image!\n\n"
                        f"📄 {filename}\n"
                        f"🏷️ Label: {label_name}\n"
                        f"📡 TCP Text: {tcp_text}")
        msg_box.setIcon(QMessageBox.Information)

        # Auto-close after 2 seconds
        QTimer.singleShot(2000, msg_box.close)
        msg_box.show()

    # ---------- Navigation ----------
    def go_back(self):
        """Return to main annotation page"""
        self.main_window.stacked_widget.setCurrentIndex(0)


class MainWindow(QMainWindow):
    def __init__(self):
        self.capture_folder = None
        super().__init__()
        self.setWindowTitle("BMP Annotation Tool with Camera, Training & Labeling")
        self.resize(1400, 900)

        # MODIFIED: Start with object0 as the first label
        self.labels = ["object0"]
        self.label_counter = 0
        self.label_colors = {"object0": QColor(255, 0, 0)}

        self.image_files = []
        self.current_index = -1
        self.camera_signals = CameraSignals()
        self.camera_signals.finished.connect(self.on_camera_finished)

        # Training related
        self.training_signals = TrainingSignals()
        self.training_signals.progress.connect(self.on_training_progress)
        self.training_signals.finished.connect(self.on_training_finished)

        # Prediction related
        self.prediction_signals = PredictionSignals()
        self.prediction_signals.progress.connect(self.on_prediction_progress)
        self.prediction_signals.finished.connect(self.on_prediction_finished)
        self.prediction_signals.image_ready.connect(self.on_prediction_image_ready)

        self.is_training = False
        self.is_predicting = False
        self.training_start_time = None
        self.progress_dialog = None
        self.prediction_progress_dialog = None
        self.current_model_path = None

        # Create stacked widget for multiple pages
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Create main annotation page
        self.main_page = QWidget()
        self.init_main_page()
        self.stacked_widget.addWidget(self.main_page)

        # Create labeling page
        self.labeling_page = LabelingPage(self)
        self.stacked_widget.addWidget(self.labeling_page)

    def init_main_page(self):
        """Initialize the main annotation page"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # ---------- Toolbar ----------
        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self.open_folder)

        self.capture_btn = QPushButton("Capture from Camera")
        self.capture_btn.clicked.connect(self.capture_from_camera)
        if not CAMERA_AVAILABLE:
            self.capture_btn.setEnabled(False)
            self.capture_btn.setToolTip("Camera module not available")

        prev_btn = QPushButton("◀ Prev")
        prev_btn.clicked.connect(self.prev_image)

        next_btn = QPushButton("Next ▶")
        next_btn.clicked.connect(self.next_image)

        undo_btn = QPushButton("↶ Undo")
        undo_btn.clicked.connect(self.undo)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected)

        auto_split_btn = QPushButton("Auto Split + data.yaml")
        auto_split_btn.clicked.connect(self.auto_split_dataset)
        auto_split_btn.setStyleSheet("background-color: #FF5722; color: white;")

        train_model_btn = QPushButton("Train Model")
        train_model_btn.clicked.connect(self.train_model)
        train_model_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")

        load_model_btn = QPushButton("Load Model")
        load_model_btn.clicked.connect(self.load_model)
        load_model_btn.setStyleSheet("background-color: #2196F3; color: white;")

        self.predict_btn = QPushButton("Predict")
        self.predict_btn.clicked.connect(self.predict_current_image)
        self.predict_btn.setStyleSheet("background-color: #FF9800; color: white;")
        self.predict_btn.setEnabled(False)

        self.predict_batch_btn = QPushButton("Predict Batch")
        self.predict_batch_btn.clicked.connect(self.predict_batch)
        self.predict_batch_btn.setStyleSheet("background-color: #9C27B0; color: white;")
        self.predict_batch_btn.setEnabled(False)

        # NEW: Labeling button to go to Labeling page
        labeling_btn = QPushButton("🔍 Labeling")
        labeling_btn.clicked.connect(self.go_to_labeling_page)
        labeling_btn.setStyleSheet("background-color: #795548; color: white; font-weight: bold;")

        top_bar = QHBoxLayout()
        top_bar.addWidget(open_folder_btn)
        top_bar.addWidget(self.capture_btn)
        top_bar.addWidget(prev_btn)
        top_bar.addWidget(next_btn)
        top_bar.addWidget(undo_btn)
        top_bar.addWidget(delete_btn)
        top_bar.addWidget(auto_split_btn)
        top_bar.addWidget(train_model_btn)
        top_bar.addWidget(load_model_btn)
        top_bar.addWidget(self.predict_btn)
        top_bar.addWidget(self.predict_batch_btn)
        top_bar.addWidget(labeling_btn)
        top_bar.addStretch()

        # ---------- Labels ----------
        self.label_combo = QComboBox()
        self.label_combo.addItems(self.labels)

        self.add_label_btn = QPushButton("+")
        self.add_label_btn.setFixedWidth(40)
        self.add_label_btn.clicked.connect(self.auto_add_label)
        self.add_label_btn.setToolTip("Add new label (object1, object2, ...)")

        label_bar = QHBoxLayout()
        label_bar.addWidget(self.label_combo)
        label_bar.addWidget(self.add_label_btn)
        label_bar.addStretch()

        # ---------- Viewer ----------
        self.viewer = AnnotationWidget(
            self.get_current_label,
            self.get_label_color
        )

        # ---------- Status Bar ----------
        self.status_label = QLabel("Ready")

        # Model info label
        self.model_info_label = QLabel("No model loaded")
        self.model_info_label.setStyleSheet("color: #666; font-style: italic;")

        layout.addLayout(top_bar)
        layout.addLayout(label_bar)
        layout.addWidget(self.viewer)

        container = QWidget()
        container.setLayout(layout)
        self.main_page.setLayout(layout)

        # ---------- Shortcuts ----------
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_selected)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.auto_split_dataset)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self.train_model)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.load_model)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.predict_current_image)
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self.auto_add_label)

    def go_to_labeling_page(self):
        """Switch to labeling page"""
        self.stacked_widget.setCurrentIndex(1)

    def auto_add_label(self):
        """Automatically add a sequentially numbered label (object1, object2, etc.)"""
        self.label_counter += 1
        new_label = f"object{self.label_counter}"

        # Check if label already exists (shouldn't happen with sequential numbering)
        if new_label not in self.labels:
            self.labels.append(new_label)
            self.label_colors[new_label] = self.generate_color()
            self.label_combo.addItem(new_label)
            self.label_combo.setCurrentText(new_label)

            # Show brief confirmation in status bar
            self.status_label.setText(f"Added label: {new_label}")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

    # Delete selected box
    def delete_selected(self):
        self.viewer.delete_selected()

    # Auto split dataset into train/val (simplified)
    def auto_split_dataset(self):
        """Automatically split dataset into train (80%) and validation (20%) sets and generate data.yaml"""
        try:
            # Get folder path
            if hasattr(self, "image_path") and self.image_path:
                folder_path = os.path.dirname(self.image_path)
            else:
                # Ask user to select a folder
                folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Auto Split")
                if not folder_path:
                    return

            # Count BMP files in the folder
            bmp_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.bmp')]

            if not bmp_files:
                QMessageBox.warning(self, "No BMP Files",
                                    f"No .bmp images found in:\n{folder_path}")
                return

            # Confirm with user
            reply = QMessageBox.question(
                self, "Auto Split & Generate data.yaml",
                f"This will:\n\n"
                f"1. 📊 Split dataset (80% train, 20% val)\n"
                f"2. 📁 Move files to organized folders\n"
                f"3. 📄 Generate data.yaml automatically\n\n"
                f"📈 Dataset stats:\n"
                f"• Total images: {len(bmp_files)}\n"
                f"• Training: {int(len(bmp_files) * 0.8)} images\n"
                f"• Validation: {int(len(bmp_files) * 0.2)} images\n"
                f"• Random seed: 42 (reproducible)\n\n"
                f"⚠ Files will be MOVED (not copied)\n\n"
                f"Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Create progress dialog
            self.progress_dialog = QProgressDialog("Starting auto split...", "Cancel", 0, 100, self)
            self.progress_dialog.setWindowTitle("Auto Split & Generate data.yaml")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.canceled.connect(self.cancel_auto_split)

            # Show progress in a simple way
            self.progress_dialog.setValue(10)
            QTimer.singleShot(100, lambda: self.run_auto_split_with_progress(folder_path))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start auto split:\n{str(e)}")

    def run_auto_split_with_progress(self, folder_path):
        """Run auto split with progress updates"""
        try:
            self.progress_dialog.setValue(20)
            self.progress_dialog.setLabelText("Splitting dataset...")

            # Perform the split
            success = self.viewer.auto_split_dataset(folder_path)

            if success:
                self.progress_dialog.setValue(100)
                self.progress_dialog.setLabelText("Complete!")

                QMessageBox.information(
                    self, "Auto Split Complete",
                    f"✅ Dataset successfully prepared!\n\n"
                    f"✓ Files organized into train/val folders\n"
                    f"✓ data.yaml generated\n"
                    f"✓ classes.txt updated\n\n"
                    f"Dataset is now ready for training! 🚀"
                )
            else:
                QMessageBox.warning(self, "Auto Split Failed",
                                    "Failed to split dataset. Check console for details.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed during auto split:\n{str(e)}")
        finally:
            self.progress_dialog.close()

    def cancel_auto_split(self):
        """Cancel the auto split process"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        QMessageBox.information(self, "Complete", "Auto split has done.")

    # Train Model functionality
    def train_model(self):
        """Start training a YOLOv11 model"""
        if self.is_training:
            QMessageBox.warning(self, "Training in Progress",
                                "A training session is already in progress.")
            return

        try:
            # Get folder path
            if hasattr(self, "image_path") and self.image_path:
                folder_path = os.path.dirname(self.image_path)
            else:
                # Ask user to select a folder
                folder_path = QFileDialog.getExistingDirectory(self, "Select Folder with data.yaml")
                if not folder_path:
                    return

            # Check if data.yaml exists
            yaml_path = os.path.join(folder_path, "data.yaml")
            if not os.path.exists(yaml_path):
                reply = QMessageBox.question(
                    self, "No data.yaml Found",
                    f"data.yaml not found in:\n{folder_path}\n\n"
                    f"Do you want to generate it now?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.viewer.generate_data_yaml(folder_path)
                    # Check again after generation
                    if not os.path.exists(yaml_path):
                        QMessageBox.warning(self, "data.yaml not created",
                                            "Failed to create data.yaml. Please check the folder structure.")
                        return
                else:
                    return

            # Check if train/val folders exist and have images
            images_train_dir = os.path.join(folder_path, "images", "train")
            images_val_dir = os.path.join(folder_path, "images", "val")

            if not os.path.exists(images_train_dir):
                reply = QMessageBox.question(
                    self, "No Training Folder",
                    f"Training folder not found: {images_train_dir}\n\n"
                    f"Do you want to run Auto Split (80/20) to create train/val folders?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    if not self.viewer.auto_split_dataset(folder_path):
                        QMessageBox.warning(self, "Auto Split Failed",
                                            "Failed to create train/val split.")
                        return
                else:
                    return

            # Count training images
            train_images = [f for f in os.listdir(images_train_dir) if
                            f.lower().endswith(('.bmp', '.jpg', '.jpeg', '.png'))]
            if len(train_images) == 0:
                QMessageBox.warning(self, "No Training Images",
                                    f"No images found in training folder: {images_train_dir}")
                return

            # Check for label files
            labels_train_dir = os.path.join(folder_path, "labels", "train")
            if os.path.exists(labels_train_dir):
                label_files = [f for f in os.listdir(labels_train_dir) if f.lower().endswith('.txt')]
                if len(label_files) < len(train_images):
                    QMessageBox.warning(self, "Missing Labels",
                                        f"Found {len(train_images)} images but only {len(label_files)} label files.\n"
                                        f"Some images may not have annotations.")

            # Ask for training parameters
            epochs, ok = QInputDialog.getInt(
                self, "Training Epochs",
                f"Enter number of training epochs (recommended: 50-300):\n"
                f"Dataset size: {len(train_images)} images",
                100, 10, 1000, 1
            )
            if not ok:
                return

            batch_size, ok = QInputDialog.getInt(
                self, "Batch Size",
                "Enter batch size:\n"
                "• 4-8 for low GPU memory\n"
                "• 16-32 for sufficient GPU memory\n"
                "• 1-4 for CPU training",
                16, 1, 64, 1
            )
            if not ok:
                return

            model_size, ok = QInputDialog.getItem(
                self, "Model Size",
                "Select YOLOv11 model size:\n"
                "• nano: Fastest, less accurate\n"
                "• small: Good balance\n"
                "• medium: Better accuracy\n"
                "• large: High accuracy\n"
                "• xlarge: Best accuracy, slowest",
                ["nano (yolo11n)", "small (yolo11s)", "medium (yolo11m)", "large (yolo11l)", "xlarge (yolo11x)"],
                1, False  # Default to small
            )
            if not ok:
                return

            # Map model size to actual model names
            model_map = {
                "nano (yolo11n)": "yolo11n.pt",
                "small (yolo11s)": "yolo11s.pt",
                "medium (yolo11m)": "yolo11m.pt",
                "large (yolo11l)": "yolo11l.pt",
                "xlarge (yolo11x)": "yolo11x.pt"
            }
            model_name = model_map[model_size]

            # Ask for save location
            default_save_dir = os.path.join(folder_path, "runs")
            save_dir = QFileDialog.getExistingDirectory(self, "Select Folder to Save Trained Model", default_save_dir)
            if not save_dir:
                return

            # Check CUDA availability
            import torch
            has_cuda = torch.cuda.is_available()
            device_info = "GPU (CUDA)" if has_cuda else "CPU"

            # Estimate training time
            time_per_epoch = 30 if not has_cuda else 5
            estimated_minutes = int((epochs * time_per_epoch) / 60)

            # Confirm training
            reply = QMessageBox.question(
                self, "Confirm Training",
                f"🚀 Training Configuration:\n\n"
                f"📁 Dataset: {os.path.basename(folder_path)}\n"
                f"📊 Training images: {len(train_images)}\n"
                f"🔄 Epochs: {epochs}\n"
                f"📦 Batch Size: {batch_size}\n"
                f"🤖 Model: {model_name}\n"
                f"⚡ Device: {device_info}\n"
                f"💾 Save to: {save_dir}\n\n"
                f"⏱ Estimated time: {estimated_minutes} minutes\n"
                f"📈 Progress will be shown during training.\n\n"
                f"Start training?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Create progress dialog
            self.progress_dialog = QProgressDialog("Initializing training...", "Cancel Training", 0, 100, self)
            self.progress_dialog.setWindowTitle(f"Training YOLOv11 - {os.path.basename(folder_path)}")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.canceled.connect(self.cancel_training)

            # Start training in a separate thread
            self.is_training = True
            self.training_start_time = datetime.now()

            thread = threading.Thread(
                target=self.run_training,
                args=(yaml_path, epochs, batch_size, model_name, save_dir),
                daemon=True
            )
            thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start training:\n{str(e)}")
            self.is_training = False

    def run_training(self, yaml_path, epochs, batch_size, model_name, save_dir):
        """Run YOLOv11 training in a separate thread - simplified without callbacks"""
        try:
            # Import ultralytics here to avoid import issues in main thread
            from ultralytics import YOLO
            import torch

            # Check if GPU is available
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
            self.training_signals.progress.emit(5,
                                                f"Initializing training on {device} ({gpu_count} GPU(s) available)...",
                                                "Estimating...")

            # Load model
            model = YOLO(model_name)

            # Calculate estimated time (very rough estimate)
            time_per_epoch = 30 if device == 'cpu' else 5
            estimated_total_seconds = epochs * time_per_epoch
            estimated_time = str(timedelta(seconds=estimated_total_seconds))

            self.training_signals.progress.emit(10, f"Starting training ({epochs} epochs, batch size: {batch_size})...",
                                                estimated_time)

            # Start training WITHOUT callbacks
            results = model.train(
                data=yaml_path,
                epochs=epochs,
                batch=batch_size,
                device=device,
                project=save_dir,
                name=f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                exist_ok=True,
                verbose=True,  # Let YOLO show its own progress
                save=True,
                save_period=10,
                plots=True
            )

            # Training completed successfully
            if results:
                # Find the training directory
                train_dirs = [d for d in os.listdir(save_dir)
                              if d.startswith("train_") and os.path.isdir(os.path.join(save_dir, d))]

                if train_dirs:
                    latest_train_dir = sorted(train_dirs)[-1]
                    best_model_path = os.path.join(save_dir, latest_train_dir, "weights", "best.pt")

                    success_message = (
                        f"✅ Training completed successfully!\n\n"
                        f"Model saved to:\n{best_model_path}\n\n"
                        f"Training time: {str(timedelta(seconds=int((datetime.now() - self.training_start_time).total_seconds())))}"
                    )
                else:
                    success_message = "✅ Training completed successfully!"

                self.training_signals.finished.emit(True, success_message)
            else:
                self.training_signals.finished.emit(False, "Training completed but no results returned.")

        except ImportError as e:
            error_msg = (
                f"Failed to import required libraries:\n{str(e)}\n\n"
                f"Please install required packages:\n"
                f"pip install ultralytics torch torchvision\n\n"
                f"For GPU support:\n"
                f"pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118"
            )
            self.training_signals.finished.emit(False, error_msg)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"Training failed:\n{str(e)}\n\nDetails:\n{error_details}"
            print(error_msg)
            self.training_signals.finished.emit(False, error_msg)
        finally:
            self.is_training = False

    # NEW: Load trained model
    def load_model(self):
        """Load a trained YOLOv11 model for inference"""
        if self.is_training:
            QMessageBox.warning(self, "Training in Progress",
                                "Please wait for training to complete before loading a model.")
            return

        try:
            # Ask user to select a model file
            model_path, _ = QFileDialog.getOpenFileName(
                self, "Select Trained Model",
                "",
                "PyTorch Models (*.pt);;All Files (*.*)"
            )

            if not model_path or not os.path.exists(model_path):
                return

            # Validate it's a YOLO model
            if not model_path.lower().endswith('.pt'):
                QMessageBox.warning(self, "Invalid File",
                                    "Please select a .pt PyTorch model file.")
                return

            # Show loading dialog
            loading_dialog = QProgressDialog("Loading model...", None, 0, 0, self)
            loading_dialog.setWindowTitle("Loading Model")
            loading_dialog.setWindowModality(Qt.WindowModal)
            loading_dialog.show()

            try:
                from ultralytics import YOLO
                import torch

                # Check device
                device = 'cuda' if torch.cuda.is_available() else 'cpu'

                # Load the model
                self.current_model = YOLO(model_path)
                self.current_model_path = model_path

                # Get model info
                model_name = os.path.basename(model_path)
                model_size = os.path.getsize(model_path) / (1024 * 1024)  # MB

                # Enable prediction buttons
                self.predict_btn.setEnabled(True)  # Use self.
                self.predict_batch_btn.setEnabled(True)  # Use self.

                # Update status
                self.model_info_label.setText(f"Model: {model_name} ({model_size:.1f} MB) on {device}")
                self.model_info_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

                loading_dialog.close()

                QMessageBox.information(
                    self, "Model Loaded",
                    f"✅ Model loaded successfully!\n\n"
                    f"• Model: {model_name}\n"
                    f"• Size: {model_size:.1f} MB\n"
                    f"• Device: {device}\n\n"
                    f"Prediction buttons are now enabled."
                )

            except Exception as e:
                loading_dialog.close()
                QMessageBox.critical(self, "Load Failed", f"Failed to load model:\n{str(e)}")
                self.current_model = None
                self.current_model_path = None
                self.predict_btn.setEnabled(False)  # Use self.
                self.predict_batch_btn.setEnabled(False)  # Use self.
                self.model_info_label.setText("No model loaded")
                self.model_info_label.setStyleSheet("color: #666; font-style: italic;")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model:\n{str(e)}")

    # NEW: Predict current image
    def predict_current_image(self):
        """Run inference on the current image"""
        if not hasattr(self, 'current_model') or self.current_model is None:
            QMessageBox.warning(self, "No Model Loaded",
                                "Please load a trained model first.")
            return

        if not hasattr(self, 'image_path') or not self.image_path:
            QMessageBox.warning(self, "No Image",
                                "Please open an image first.")
            return

        try:
            # Create progress dialog
            self.prediction_progress_dialog = QProgressDialog(
                "Running inference...", "Cancel", 0, 100, self
            )
            self.prediction_progress_dialog.setWindowTitle("Running Prediction")
            self.prediction_progress_dialog.setWindowModality(Qt.WindowModal)
            self.prediction_progress_dialog.setMinimumDuration(0)
            self.prediction_progress_dialog.canceled.connect(self.cancel_prediction)

            self.is_predicting = True

            # Run prediction in a separate thread
            thread = threading.Thread(
                target=self.run_prediction,
                args=(self.image_path,),
                daemon=True
            )
            thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start prediction:\n{str(e)}")
            self.is_predicting = False

    # NEW: Run prediction
    def run_prediction(self, image_path):
        """Run prediction on a single image"""
        try:
            from ultralytics import YOLO
            import torch

            self.prediction_signals.progress.emit(10, "Loading model...")

            # Load model if not already loaded
            if not hasattr(self, 'current_model') or self.current_model is None:
                if hasattr(self, 'current_model_path') and self.current_model_path:
                    self.current_model = YOLO(self.current_model_path)
                else:
                    self.prediction_signals.finished.emit(False, "No model loaded", [])
                    return

            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            self.prediction_signals.progress.emit(30, f"Running inference on {device}...")

            # Run prediction
            results = self.current_model.predict(
                source=image_path,
                conf=0.25,  # Confidence threshold
                iou=0.45,  # IOU threshold
                device=device,
                save=False,  # Don't save automatically
                save_txt=False,  # Don't save labels
                save_conf=True,  # Save confidence scores
                show=False,  # Don't show plot
                verbose=False  # Don't print details
            )

            self.prediction_signals.progress.emit(70, "Processing results...")

            # Extract predictions
            predictions = []
            if results and len(results) > 0:
                result = results[0]

                if hasattr(result, 'boxes') and result.boxes is not None:
                    boxes = result.boxes

                    # Get number of detections
                    if hasattr(boxes, 'xyxy') and boxes.xyxy is not None:
                        num_detections = len(boxes.xyxy)
                    else:
                        num_detections = 0

                    for i in range(num_detections):
                        try:
                            # Get box coordinates (xyxy format)
                            box = boxes.xyxy[i].cpu().numpy()

                            # Get confidence
                            conf = float(boxes.conf[i].cpu().numpy()) if boxes.conf is not None else 0.0

                            # Get class ID
                            cls = int(boxes.cls[i].cpu().numpy()) if boxes.cls is not None else 0

                            # Get class name if available
                            class_name = f"class_{cls}"  # Default
                            if hasattr(result, 'names') and result.names:
                                class_name = result.names.get(cls, f"class_{cls}")

                            # Store the prediction
                            predictions.append({
                                'bbox': box.tolist(),  # [x1, y1, x2, y2]
                                'confidence': conf,
                                'class_id': cls,
                                'class_name': class_name
                            })
                        except Exception as e:
                            print(f"Error processing detection {i}: {e}")
                            continue

            # Save annotated image
            output_dir = os.path.join(os.path.dirname(image_path), "predictions")
            os.makedirs(output_dir, exist_ok=True)

            output_filename = f"pred_{os.path.basename(image_path)}"
            output_path = os.path.join(output_dir, output_filename)

            # Save the result with boxes
            if results and len(results) > 0:
                result.save(filename=output_path)

            self.prediction_signals.progress.emit(90, "Saving results...")

            # Update the viewer with predictions immediately
            # This will display boxes in the current viewer
            self.viewer.display_predictions(predictions)

            self.prediction_signals.progress.emit(100, "Done!")
            self.prediction_signals.finished.emit(True, f"Found {len(predictions)} objects", predictions)
            self.prediction_signals.image_ready.emit(output_path)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"Prediction failed:\n{str(e)}"
            print(error_details)
            self.prediction_signals.finished.emit(False, error_msg, [])
        finally:
            self.is_predicting = False

    # NEW: Update viewer with predictions
    def update_viewer_with_predictions(self, predictions):
        """Update the annotation viewer with prediction results"""
        try:
            # Clear existing boxes
            self.viewer.boxes.clear()

            # Convert predictions to viewer format
            for pred in predictions:
                bbox = pred['bbox']  # [x1, y1, x2, y2]
                class_name = pred['class_name']
                confidence = pred['confidence']

                # Ensure bbox has 4 values
                if len(bbox) >= 4:
                    # Create QRectF
                    rect = QRectF(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])

                    # Add to viewer with confidence in label
                    label = f"{class_name} ({confidence:.2f})"
                    self.viewer.boxes.append((rect, label))

            # Update the display
            self.viewer.update()

        except Exception as e:
            print(f"Error updating viewer with predictions: {e}")
    # NEW: Predict batch of images
    def predict_batch(self):
        """Run inference on a batch of images"""
        if not hasattr(self, 'current_model') or self.current_model is None:
            QMessageBox.warning(self, "No Model Loaded",
                                "Please load a trained model first.")
            return

        try:
            # Ask user to select a folder
            folder_path = QFileDialog.getExistingDirectory(self, "Select Folder with Images")
            if not folder_path:
                return

            # Get image files
            image_extensions = ['.bmp', '.jpg', '.jpeg', '.png', '.tiff']
            image_files = []
            for ext in image_extensions:
                image_files.extend([f for f in os.listdir(folder_path) if f.lower().endswith(ext)])

            if not image_files:
                QMessageBox.warning(self, "No Images",
                                    "No images found in the selected folder.")
                return

            # Confirm batch prediction
            reply = QMessageBox.question(
                self, "Batch Prediction",
                f"Run prediction on {len(image_files)} images?\n\n"
                f"Results will be saved in:\n{folder_path}/predictions/\n\n"
                f"Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Create progress dialog
            self.prediction_progress_dialog = QProgressDialog(
                f"Processing 0/{len(image_files)}...", "Cancel", 0, len(image_files), self
            )
            self.prediction_progress_dialog.setWindowTitle("Batch Prediction")
            self.prediction_progress_dialog.setWindowModality(Qt.WindowModal)
            self.prediction_progress_dialog.setMinimumDuration(0)
            self.prediction_progress_dialog.canceled.connect(self.cancel_prediction)

            self.is_predicting = True

            # Run batch prediction in a separate thread
            thread = threading.Thread(
                target=self.run_batch_prediction,
                args=(folder_path, image_files),
                daemon=True
            )
            thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start batch prediction:\n{str(e)}")
            self.is_predicting = False

    # NEW: Run batch prediction
    def run_batch_prediction(self, folder_path, image_files):
        """Run prediction on a batch of images"""
        try:
            from ultralytics import YOLO
            import torch

            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            # Create output directory
            output_dir = os.path.join(folder_path, "predictions")
            os.makedirs(output_dir, exist_ok=True)

            total_images = len(image_files)
            processed = 0

            for i, image_file in enumerate(image_files):
                if not self.is_predicting:
                    break

                image_path = os.path.join(folder_path, image_file)

                # Update progress
                self.prediction_signals.progress.emit(
                    int((i / total_images) * 100),
                    f"Processing {i + 1}/{total_images}: {image_file}"
                )

                # Run prediction
                results = self.current_model.predict(
                    source=image_path,
                    conf=0.25,
                    iou=0.45,
                    device=device,
                    save=True,
                    project=output_dir,
                    name="",
                    exist_ok=True,
                    save_txt=True,
                    save_conf=True,
                    verbose=False
                )

                processed += 1

            if self.is_predicting:
                self.prediction_signals.finished.emit(
                    True,
                    f"Batch prediction completed!\n\n"
                    f"Processed: {processed}/{total_images} images\n"
                    f"Saved to: {output_dir}",
                    []
                )
            else:
                self.prediction_signals.finished.emit(
                    False,
                    f"Batch prediction cancelled.\n\n"
                    f"Processed: {processed}/{total_images} images",
                    []
                )

        except Exception as e:
            self.prediction_signals.finished.emit(False, f"Batch prediction failed:\n{str(e)}", [])
        finally:
            self.is_predicting = False

    # NEW: Prediction signal handlers
    def on_prediction_progress(self, progress, status):
        """Update prediction progress dialog"""
        if self.prediction_progress_dialog:
            self.prediction_progress_dialog.setValue(progress)
            self.prediction_progress_dialog.setLabelText(status)
            self.status_label.setText(f"Prediction: {status}")

    def on_prediction_finished(self, success, message, predictions):
        """Handle prediction completion"""
        self.is_predicting = False

        if self.prediction_progress_dialog:
            self.prediction_progress_dialog.close()
            self.prediction_progress_dialog = None

        if success:
            self.status_label.setText(f"Prediction complete: {message}")

            # Ask if user wants to save predictions as annotations
            if predictions:
                # Create format selection dialog
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QDialogButtonBox

                dialog = QDialog(self)
                dialog.setWindowTitle("Save Predictions")
                dialog.setModal(True)

                layout = QVBoxLayout()

                layout.addWidget(QLabel(f"Found {len(predictions)} objects.\nSelect format to save:"))

                # Radio buttons for format selection
                radio_yolo = QRadioButton("YOLO format (normalized: class x_center y_center width height)")
                radio_pixel = QRadioButton("Pixel coordinates (class confidence x1 y1 x2 y2)")
                radio_both = QRadioButton("Both formats")

                # Set default
                radio_yolo.setChecked(True)

                layout.addWidget(radio_yolo)
                layout.addWidget(radio_pixel)
                layout.addWidget(radio_both)

                # Dialog buttons
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(dialog.accept)
                buttons.rejected.connect(dialog.reject)
                layout.addWidget(buttons)

                dialog.setLayout(layout)

                if dialog.exec() == QDialog.Accepted:
                    # Determine selected format
                    if radio_yolo.isChecked():
                        format_type = "yolo"
                    elif radio_pixel.isChecked():
                        format_type = "pixel"
                    elif radio_both.isChecked():
                        format_type = "both"

                    # Save predictions as annotations
                    self.viewer.save_predictions_as_annotations(self.image_path, predictions, format_type)

                    # Show confirmation
                    format_names = {
                        "yolo": "YOLO format (.txt)",
                        "pixel": "Pixel coordinates (.txt)",
                        "both": "Both formats"
                    }

                    QMessageBox.information(self, "Saved",
                                            f"Predictions saved in {format_names[format_type]} format\n"
                                            f"Saved to: labels/ folder")
            else:
                QMessageBox.information(self, "Prediction Complete",
                                        "No objects detected in the image.")

        else:
            self.status_label.setText("Prediction failed")
            QMessageBox.critical(self, "Prediction Failed", message)

        # Reset status after 3 seconds
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

    def on_prediction_image_ready(self, image_path):
        """Load and display the predicted image"""
        try:
            if os.path.exists(image_path):
                # Load the predicted image
                self.viewer.load_image(image_path)
                self.viewer.update()

                # Update window title
                self.setWindowTitle(
                    f"BMP Annotation Tool – {os.path.basename(image_path)} (Predicted)"
                )
        except Exception as e:
            print(f"Error loading predicted image: {e}")

    def cancel_prediction(self):
        """Cancel the prediction process"""
        if self.is_predicting:
            self.is_predicting = False
            self.status_label.setText("Prediction cancelled")
            QMessageBox.information(self, "Prediction Cancelled", "Prediction has been cancelled.")

    # Training signal handlers
    def on_training_progress(self, progress, status, time_remaining):
        """Update progress dialog"""
        if self.progress_dialog:
            self.progress_dialog.setValue(progress)
            self.progress_dialog.setLabelText(f"{status}\nTime remaining: {time_remaining}")
            self.status_label.setText(f"Training: {status}")

    def on_training_finished(self, success, message):
        """Handle training completion"""
        self.is_training = False

        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        if success:
            QMessageBox.information(self, "Training Complete", message)
            self.status_label.setText("Training completed successfully!")
        else:
            QMessageBox.critical(self, "Training Failed", message)
            self.status_label.setText("Training failed")

        # Reset training info after 5 seconds
        QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))

    def cancel_training(self):
        """Cancel the training process"""
        if self.is_training:
            self.is_training = False
            self.status_label.setText("Training cancelled")
            QMessageBox.information(self, "Training Cancelled", "Training has been cancelled.")

    # ---------------- Camera Capture ----------------
    def capture_from_camera(self):
        """Start camera capture in a separate thread, save to chosen folder"""
        # MODIFIED: Hardcoded folder path
        if self.capture_folder is None:
            self.capture_folder = "C:\\Users\\SiP-PHChin\\OneDrive - SIP Technology (M) Sdn Bhd\\Desktop\\Capture Image"

        # Create directory if it doesn't exist
        os.makedirs(self.capture_folder, exist_ok=True)

        self.capture_btn.setEnabled(False)
        self.capture_btn.setText("Capturing...")

        def run_capture():
            def callback(success, message, image_path):
                if success and image_path:
                    # Move/rename captured image to chosen folder
                    base_name = os.path.basename(image_path)
                    save_path = os.path.join(self.capture_folder, base_name)

                    # Ensure unique filename
                    count = 1
                    name, ext = os.path.splitext(base_name)
                    while os.path.exists(save_path):
                        save_path = os.path.join(self.capture_folder, f"{name}_{count}{ext}")
                        count += 1

                    os.rename(image_path, save_path)
                    image_path = save_path

                # Emit signal to update GUI
                self.camera_signals.finished.emit(success, message, image_path)

            # Call the camera capture function
            AutoCaptureFlow(callback=callback)

        thread = threading.Thread(target=run_capture, daemon=True)
        thread.start()

    def on_camera_finished(self, success, message, image_path):
        """Handle camera capture completion"""
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("Capture from Camera")

        if success and image_path:
            # Load the captured image
            if os.path.exists(image_path):
                # Add to image list if not already there
                if image_path not in self.image_files:
                    self.image_files.append(image_path)
                    self.image_files.sort()

                # Find index and load
                self.current_index = self.image_files.index(image_path)
                self.load_current_image()
        else:
            QMessageBox.critical(self, "Capture Failed",
                                 f"Camera capture failed!\n{message}")

    # ---------------- Color logic ----------------
    def get_label_color(self, label):
        return self.label_colors.get(label, QColor(255, 255, 255))

    def generate_color(self):
        """Generate a random but distinct color for new labels"""
        # Try to generate colors that are visually distinct
        # You can customize this to your preference
        hue = random.randint(0, 359)
        saturation = random.randint(150, 255)
        value = random.randint(150, 255)

        color = QColor.fromHsv(hue, saturation, value)
        return color

    # ---------------- Folder ----------------
    def open_folder(self):
        # MODIFIED: Hardcoded folder path
        folder = "C:\\Users\\SiP-PHChin\\OneDrive - SIP Technology (M) Sdn Bhd\\Desktop\\Open Folder"

        # Create directory if it doesn't exist
        os.makedirs(folder, exist_ok=True)

        # MODIFIED: Removed QFileDialog and directly use the hardcoded folder
        self.image_files = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".bmp")
        ])

        if not self.image_files:
            QMessageBox.warning(self, "No BMP", "No .bmp images found in the default folder.")
            return

        self.current_index = 0
        self.load_current_image()

    # ---------------- Navigation ----------------
    def load_current_image(self):
        path = self.image_files[self.current_index]
        self.viewer.boxes.clear()
        self.viewer.load_image(path)
        self.image_path = path

        self.setWindowTitle(
            f"BMP Annotation Tool – {os.path.basename(path)} "
            f"({self.current_index + 1}/{len(self.image_files)})"
        )

    def next_image(self):
        if self.current_index < 0:
            return
        self.save_current()
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_current_image()

    def prev_image(self):
        if self.current_index < 0:
            return
        self.save_current()
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()

    # ---------------- Labels ----------------
    def get_current_label(self):
        return self.label_combo.currentText()

    def add_label(self):
        text, ok = QInputDialog.getText(self, "Add Label", "Label name:")
        if ok and text and text not in self.labels:
            self.labels.append(text)
            self.label_colors[text] = self.generate_color()
            self.label_combo.addItem(text)

    # ---------------- Undo ----------------
    def undo(self):
        self.viewer.undo_last()

    # ---------------- Save ----------------
    def save_current(self):
        """Save annotations for current image in YOLO format"""
        if hasattr(self, "image_path") and self.image_path:
            # This saves ONLY in YOLO format (.txt file)
            self.viewer.save_annotations(self.image_path)

    def closeEvent(self, event):
        # Ask if user wants to stop training/prediction
        if self.is_training or self.is_predicting:
            reply = QMessageBox.question(
                self, "Operation in Progress",
                "Training or prediction is currently in progress. Do you want to stop and exit?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            else:
                self.is_training = False
                self.is_predicting = False

        self.save_current()
        event.accept()

    def show_prediction_details(self):
        """Show details of current predictions"""
        if not hasattr(self.viewer, 'boxes') or not self.viewer.boxes:
            QMessageBox.information(self, "No Predictions",
                                    "No predictions to display. Run prediction first.")
            return

        # Collect prediction details
        details = []
        for i, (rect, label) in enumerate(self.viewer.boxes):
            # Get original image dimensions
            if hasattr(self.viewer, 'pixmap') and self.viewer.pixmap:
                img_width = self.viewer.pixmap.width()
                img_height = self.viewer.pixmap.height()

                # Convert to pixel coordinates
                x1 = rect.x()
                y1 = rect.y()
                x2 = rect.x() + rect.width()
                y2 = rect.y() + rect.height()

                details.append(f"Box {i + 1}: {label}\n"
                               f"  Coordinates: ({x1:.1f}, {y1:.1f}) to ({x2:.1f}, {y2:.1f})\n"
                               f"  Size: {rect.width():.1f} x {rect.height():.1f} pixels\n")

        # Show details dialog
        QMessageBox.information(self, "Prediction Details",
                                f"Found {len(details)} objects:\n\n" + "\n".join(details))

    def show_prediction_formats(self):
        """Show prediction in both YOLO and pixel formats directly"""
        if not hasattr(self, 'image_path') or not self.image_path:
            QMessageBox.warning(self, "No Image", "Please load an image first.")
            return

        if not hasattr(self.viewer, 'current_predictions') or not self.viewer.current_predictions:
            QMessageBox.information(self, "No Predictions",
                                    "No predictions available. Run prediction first.")
            return

        predictions = self.viewer.current_predictions

        # Get image dimensions
        if hasattr(self.viewer, 'pixmap') and self.viewer.pixmap:
            img_width = self.viewer.pixmap.width()
            img_height = self.viewer.pixmap.height()
        else:
            img_width = 1
            img_height = 1

        # Build comparison string
        comparison = f"📊 Prediction Coordinates\n"
        comparison += f"Image size: {img_width} x {img_height} pixels\n"
        comparison += f"Found {len(predictions)} objects:\n\n"

        for i, pred in enumerate(predictions):
            bbox = pred['bbox']
            class_name = pred['class_name']
            confidence = pred['confidence']
            class_id = pred['class_id']

            # Pixel format (original display format)
            pixel_str = f"[{bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}]"

            # Calculate width and height
            box_width = bbox[2] - bbox[0]
            box_height = bbox[3] - bbox[1]

            # YOLO format (normalized)
            x_center = ((bbox[0] + bbox[2]) / 2) / img_width
            y_center = ((bbox[1] + bbox[3]) / 2) / img_height
            width = box_width / img_width
            height = box_height / img_height

            yolo_str = f"[{x_center:.6f}, {y_center:.6f}, {width:.6f}, {height:.6f}]"

            # Format the display
            comparison += f"🔹 Box {i}:\n"
            comparison += f"   Class: {class_name} (ID: {class_id})\n"
            comparison += f"   Confidence: {confidence:.2%}\n"
            comparison += f"   Pixel coordinates (x1, y1, x2, y2):\n"
            comparison += f"      {pixel_str}\n"
            comparison += f"   Box size: {box_width:.1f} x {box_height:.1f} pixels\n"
            comparison += f"   YOLO format (class x_center y_center width height):\n"
            comparison += f"      {class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n\n"

        # Show in a scrollable text area for better viewing
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("Prediction Coordinates")
        dialog.setMinimumSize(700, 500)

        layout = QVBoxLayout()

        # Create scrollable text area
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(comparison)
        text_edit.setStyleSheet("font-family: monospace; font-size: 10pt;")

        layout.addWidget(text_edit)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()
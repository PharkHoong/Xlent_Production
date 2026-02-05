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


class MainWindow(QMainWindow):
    def __init__(self):
        self.capture_folder = None
        super().__init__()
        self.setWindowTitle("BMP Annotation Tool with Camera, Training & Auto TCP Scan")
        self.resize(1400, 900)

        # Define base paths
        self.base_path = "C:\\Users\\SiP-PHChin\\OneDrive - SIP Technology (M) Sdn Bhd\\Desktop"
        self.capture_image_path = f"{self.base_path}\\Capture Image"
        self.capture_image_prediction_path = f"{self.base_path}\\Capture Prediction"
        self.model_path = f"{self.base_path}\\Model"
        self.labeling_path = f"{self.base_path}\\Labeling"

        # Start with 0 as the first label
        self.labels = ["0"]
        self.label_counter = 0
        self.label_colors = {"0": QColor(255, 0, 0)}

        self.image_files = []
        self.current_index = -1

        # TCP related attributes
        self.tcp_socket = None
        self.tcp_connected = False
        self.tcp_thread = None
        self.listening_thread = None
        self.scan_data_received = ""
        self.last_bounding_box = None  # Store the last drawn bounding box
        self.last_box_label = None  # Store the label of the last box
        self.tcp_received_text = ""  # Store the latest TCP received text

        # Create necessary folders if they don't exist
        self.create_required_folders()

        # Initialize signals
        self.camera_signals = CameraSignals()
        self.camera_signals.finished.connect(self.on_camera_finished)

        self.camera_signals_2 = CameraSignals()
        self.camera_signals_2.finished.connect(self.on_camera_finished_predict)

        # Training related
        self.training_signals = TrainingSignals()
        self.training_signals.progress.connect(self.on_training_progress)
        self.training_signals.finished.connect(self.on_training_finished)

        # Prediction related
        self.prediction_signals = PredictionSignals()
        self.prediction_signals.progress.connect(self.on_prediction_progress)
        self.prediction_signals.finished.connect(self.on_prediction_finished)
        self.prediction_signals.image_ready.connect(self.on_prediction_image_ready)

        # TCP signals
        self.tcp_signals = TCPClientSignals()
        self.tcp_signals.connection_status.connect(self.on_tcp_connection_status)
        self.tcp_signals.message_received.connect(self.on_tcp_message_received)
        self.tcp_signals.message_sent.connect(self.on_tcp_message_sent)

        self.is_training = False
        self.is_predicting = False
        self.training_start_time = None
        self.progress_dialog = None
        self.prediction_progress_dialog = None
        self.current_model_path = None

        # Add a timer to track bounding box changes
        self.box_tracker_timer = QTimer()
        self.box_tracker_timer.timeout.connect(self.track_bounding_box_changes)
        self.box_tracker_timer.start(300)  # Check every 300ms

        # Track previous box count
        self.previous_box_count = 0

        self.init_ui()

    def init_ui(self):
        """Initialize the main annotation page with TCP functionality"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # ---------- Top Toolbar ----------
        top_bar = QHBoxLayout()

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self.open_folder)

        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.clicked.connect(self.capture_from_camera)
        if not CAMERA_AVAILABLE:
            self.capture_btn.setEnabled(False)
            self.capture_btn.setToolTip("Camera module not available")

        # Add duplicate button with different function
        self.capture2_btn = QPushButton("Capture & Predict")
        self.capture2_btn.clicked.connect(self.capture_predict)
        if not CAMERA_AVAILABLE:
            self.capture2_btn.setEnabled(False)
            self.capture2_btn.setToolTip("Camera module not available")

        prev_btn = QPushButton("◀ Prev")
        prev_btn.clicked.connect(self.prev_image)

        next_btn = QPushButton("Next ▶")
        next_btn.clicked.connect(self.next_image)

        undo_btn = QPushButton("↶ Undo")
        undo_btn.clicked.connect(self.undo)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected)

        # COMBINED: Single "Train Model" button that includes auto split functionality
        self.train_model_btn = QPushButton("Train Model")
        self.train_model_btn.clicked.connect(self.train_model)
        self.train_model_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.train_model_btn.setToolTip("Auto split dataset + Generate data.yaml + Train model")

        load_model_btn = QPushButton("Load Model")
        load_model_btn.clicked.connect(self.load_model)
        load_model_btn.setStyleSheet("background-color: #2196F3; color: white;")

        # Auto TCP Scan button
        self.labeling_btn = QPushButton("Image Labeling")
        self.labeling_btn.clicked.connect(self.auto_tcp_scan)
        self.labeling_btn.setStyleSheet("background-color: #795548; color: white; font-weight: bold;")
        self.labeling_btn.setToolTip("Auto connect TCP and send bounding box coordinates")

        top_bar.addWidget(open_folder_btn)
        top_bar.addWidget(self.capture_btn)
        top_bar.addWidget(self.capture2_btn)
        top_bar.addWidget(prev_btn)
        top_bar.addWidget(next_btn)
        top_bar.addWidget(undo_btn)
        top_bar.addWidget(delete_btn)
        top_bar.addWidget(self.train_model_btn)
        top_bar.addWidget(load_model_btn)
        top_bar.addWidget(self.labeling_btn)
        top_bar.addStretch()

        # ---------- Labels Section ----------
        self.label_combo = QComboBox()
        self.label_combo.addItems(self.labels)

        self.add_label_btn = QPushButton("+")
        self.add_label_btn.setFixedWidth(40)
        self.add_label_btn.clicked.connect(self.auto_add_label)
        self.add_label_btn.setToolTip("Add new label (1, 2, 3, ...)")  # Updated tooltip

        label_bar = QHBoxLayout()
        label_bar.addWidget(self.label_combo)
        label_bar.addWidget(self.add_label_btn)
        label_bar.addStretch()

        # ---------- Main Content Area ----------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # ---------- Left Column: Annotation Viewer (70%) ----------
        left_column = QVBoxLayout()

        # Annotation widget
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

        # ---------- Right Column: TCP Controls & Messages (30%) ----------
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

        # Instructions Group
        instructions_group = QGroupBox("Auto TCP Scan Instructions")
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
            "📋 Auto TCP Scan Process:\n\n"
            "1. Draw bounding box on object\n"
            "2. Click 'Auto TCP Scan' button\n"
            "3. Auto connect to TCP server\n"
            "4. Send bounding box coordinates\n"
            "5. Auto crop image on response\n\n"
            "Note: Requires at least one bounding box"
        )
        instructions.setStyleSheet("font-size: 12px; color: #555; padding: 8px;")
        instructions.setWordWrap(True)
        instructions_layout.addWidget(instructions)

        instructions_group.setLayout(instructions_layout)
        right_column.addWidget(instructions_group)

        # TCP Messages Group
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

        layout.addLayout(top_bar)
        layout.addLayout(label_bar)
        layout.addLayout(content_layout)

        # ---------- Status Bar ----------
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # Model info label
        self.model_info_label = QLabel("No model loaded")
        self.model_info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.model_info_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # ---------- Shortcuts ----------
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_selected)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self.train_model)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.load_model)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.predict_current_image)
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self.auto_add_label)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self.auto_tcp_scan)

    def create_required_folders(self):
        """Create all required folders if they don't exist"""
        folders_to_create = [
            self.capture_image_path,
            self.capture_image_prediction_path,
            self.model_path,
            self.labeling_path,
        ]

        for folder in folders_to_create:
            try:
                os.makedirs(folder, exist_ok=True)
                print(f"Created/Verified folder: {folder}")
            except Exception as e:
                print(f"Error creating folder {folder}: {e}")

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

            self.previous_box_count = current_count

    def auto_tcp_scan(self):
        """Auto connect TCP and perform Scan_ID"""
        # Check if bounding box exists
        if not hasattr(self.viewer, 'boxes') or not self.viewer.boxes:
            QMessageBox.warning(self, "No Bounding Box",
                                "Please draw at least one bounding box first!")
            return

        # Check if image is loaded
        if not hasattr(self, 'image_path') or not self.image_path:
            QMessageBox.warning(self, "No Image",
                                "Please load an image first!")
            return

        # Auto connect to TCP if not connected
        if not self.tcp_connected:
            self.status_label.setText("Auto connecting to TCP...")
            self.connect_tcp()

            # Wait a bit for connection
            QTimer.singleShot(1000, self.perform_scan_id_after_connect)
        else:
            # Already connected, perform scan immediately
            self.perform_scan_id()

    def perform_scan_id_after_connect(self):
        """Perform Scan_ID after TCP connection is established"""
        if self.tcp_connected:
            self.perform_scan_id()
        else:
            QMessageBox.warning(self, "Connection Failed",
                                "Failed to connect to TCP server. Please check settings.")

    def perform_scan_id(self):
        """Send OK message via TCP"""
        if not self.tcp_connected or not self.tcp_socket:
            QMessageBox.warning(self, "Not Connected",
                                "TCP connection failed. Please check settings.")
            return

        if not hasattr(self.viewer, 'boxes') or not self.viewer.boxes:
            QMessageBox.warning(self, "No Bounding Boxes",
                                "Please draw at least one bounding box first")
            return

        try:
            # Just send "OK" instead of coordinates
            message = "OK"

            self.tcp_socket.sendall(message.encode('utf-8'))
            self.tcp_signals.message_sent.emit(message)

            timestamp = time.strftime("%H:%M:%S")
            self.update_tcp_messages(f"[{timestamp}] 📡 Sent: {message}")

            self.status_label.setText("Message 'OK' sent to server")

            # Show brief notification
            self.show_scan_success_notification(message)

        except socket.error as e:
            self.update_tcp_messages(f"[Error] Failed to send: {str(e)}")
            QMessageBox.critical(self, "Send Failed",
                                 f"Failed to send message:\n{str(e)}")

    def show_scan_success_notification(self, message):
        """Show a brief success notification"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("TCP Message Sent")
        msg_box.setText(f"✅ Message sent!\n\n"
                        f"Message: {message}\n"
                        f"Server: {self.host_edit.text()}:{self.port_spin.value()}")
        msg_box.setIcon(QMessageBox.Information)

        # Auto-close after 2 seconds
        QTimer.singleShot(2000, msg_box.close)
        msg_box.show()

    # ---------- TCP/IP Methods ----------
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

            self.labeling_btn.setEnabled(False)
            self.labeling_btn.setText("Connecting...")
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
        self.labeling_btn.setText("Image Labeling")
        self.labeling_btn.setStyleSheet("background-color: #795548; color: white; font-weight: bold;")
        self.labeling_btn.setEnabled(True)
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

    # ---------- TCP Signal Handlers ----------
    def on_tcp_connection_status(self, message, is_connected):
        """Handle TCP connection status changes"""
        self.tcp_connected = is_connected
        self.labeling_btn.setEnabled(True)

        if is_connected:
            self.labeling_btn.setText("ID Scan")
            self.labeling_btn.setStyleSheet("background-color: #795548; color: white; font-weight: bold;")
            self.connection_status_label.setText(
                f"Status: Connected to {self.host_edit.text()}:{self.port_spin.value()}")
            self.update_tcp_messages("[System] Connected to server")
        else:
            self.labeling_btn.setText("Image Labeling")
            self.labeling_btn.setStyleSheet("background-color: #795548; color: white; font-weight: bold;")
            self.connection_status_label.setText(f"Status: {message}")
            self.update_tcp_messages(f"[System] {message}")

    def on_tcp_message_received(self, message):
        """Handle received TCP messages"""
        timestamp = time.strftime("%H:%M:%S")
        self.update_tcp_messages(f"[{timestamp}] 📥 Received: {message}")
        self.status_label.setText(f"TCP: {message[:50]}..." if len(message) > 50 else f"TCP: {message}")

        # Store received data
        self.scan_data_received = message
        self.tcp_received_text = message.strip()  # Store the received text for filename

        # Automatically crop and save image when TCP receives text
        self.auto_crop_and_save_on_tcp_message(message)

    def on_tcp_message_sent(self, message):
        """Handle sent TCP messages"""
        timestamp = time.strftime("%H:%M:%S")
        self.update_tcp_messages(f"[{timestamp}] 📤 Sent: {message}")

    def update_tcp_messages(self, message):
        """Update TCP messages display"""
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
        cursor.movePosition(QTextCursor.Start)
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

        # Sanitize the TCP message for filename
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
            label_name = label.split()[0] if ' ' in label else label
            filename = f"{label_name}_{sanitized_text}.bmp"
            save_path = os.path.join(self.labeling_path, filename)

            # Ensure unique filename
            counter = 1
            while os.path.exists(save_path):
                filename = f"{label_name}_{sanitized_text}_{counter}.bmp"
                save_path = os.path.join(self.labeling_path, filename)
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
            self.update_tcp_messages(f"[AutoCrop]   Saved to: {self.labeling_path}")

            # Update status label
            self.status_label.setText(f"Auto-saved: {filename}")

            # Send confirmation back via TCP
            # if self.tcp_connected and self.tcp_socket:
            #     try:
            #         response = f"AUTO_CROP_SAVED: {filename}"
            #         self.tcp_socket.sendall(response.encode('utf-8'))
            #         self.tcp_signals.message_sent.emit(response)
            #     except socket.error as e:
            #         self.update_tcp_messages(f"[Error] Failed to send confirmation: {str(e)}")

            # Show brief notification
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
        if not os.path.exists(self.labeling_path):
            try:
                os.makedirs(self.labeling_path, exist_ok=True)
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
        """Show a brief notification about auto-crop"""
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

    # ---------- COMBINED TRAIN MODEL FUNCTION ----------
    def train_model(self):
        """Combined function: Auto split + Generate data.yaml + Train model"""
        if self.is_training:
            QMessageBox.warning(self, "Training in Progress",
                                "A training session is already in progress.")
            return

        try:
            # Use the specific path for dataset
            folder_path = self.capture_image_path

            # Check if folder exists
            if not os.path.exists(folder_path):
                QMessageBox.warning(self, "Folder Not Found",
                                    f"Dataset folder not found:\n{folder_path}\n\n"
                                    f"Please make sure the Capture Image folder exists.")
                return

            # Check if we need to run auto split
            images_train_dir = os.path.join(folder_path, "images", "train")
            yaml_path = os.path.join(folder_path, "data.yaml")

            need_auto_split = False
            if not os.path.exists(images_train_dir):
                need_auto_split = True

            if not os.path.exists(yaml_path):
                need_auto_split = True

            if need_auto_split:
                # Ask user if they want to auto split
                reply = QMessageBox.question(
                    self, "Auto Split Required",
                    f"Dataset structure not found in:\n{folder_path}\n\n"
                    f"Do you want to automatically:\n"
                    f"1. 📊 Split dataset (80% train, 20% val)\n"
                    f"2. 📁 Create organized folders\n"
                    f"3. 📄 Generate data.yaml\n\n"
                    f"This will organize your dataset for YOLO training.",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )

                if reply != QMessageBox.Yes:
                    return

                # Run auto split
                self.status_label.setText("Running auto split...")

                success = self.viewer.auto_split_dataset(folder_path)

                if not success:
                    QMessageBox.warning(self, "Auto Split Failed",
                                        "Failed to prepare dataset. Please check your files.")
                    return

                self.status_label.setText("Auto split completed!")
                QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

            # Now check if we have training data
            if os.path.exists(images_train_dir):
                train_images = [f for f in os.listdir(images_train_dir)
                                if f.lower().endswith(('.bmp', '.jpg', '.jpeg', '.png'))]

                if len(train_images) == 0:
                    QMessageBox.warning(self, "No Training Images",
                                        f"No images found in training folder: {images_train_dir}")
                    return

            # Ask for training parameters
            epochs, ok = QInputDialog.getInt(
                self, "Training Epochs",
                f"Enter number of training epochs (recommended: 50-300):\n"
                f"Dataset: {os.path.basename(folder_path)}",
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
                1, False
            )
            if not ok:
                return

            model_map = {
                "nano (yolo11n)": "yolo11n.pt",
                "small (yolo11s)": "yolo11s.pt",
                "medium (yolo11m)": "yolo11m.pt",
                "large (yolo11l)": "yolo11l.pt",
                "xlarge (yolo11x)": "yolo11x.pt"
            }
            model_name = model_map[model_size]

            # Use the specific path for saving models
            save_dir = self.model_path

            # Create the Model folder if it doesn't exist
            os.makedirs(save_dir, exist_ok=True)

            import torch
            has_cuda = torch.cuda.is_available()
            device_info = "GPU (CUDA)" if has_cuda else "CPU"

            if has_cuda:
                gpu_name = torch.cuda.get_device_name(0)
                device_info = f"GPU: {gpu_name}"
            else:
                device_info = "CPU"


            time_per_epoch = 30 if not has_cuda else 5
            estimated_minutes = int((epochs * time_per_epoch) / 60)

            # Show training summary
            summary = (
                f"🚀 Training Configuration:\n\n"
                f"📁 Dataset: {os.path.basename(folder_path)}\n"
                f"📊 data.yaml: {yaml_path}\n"
                f"🔄 Epochs: {epochs}\n"
                f"📦 Batch Size: {batch_size}\n"
                f"🤖 Model: {model_name}\n"
                f"⚡ Device: {device_info}\n"
                f"💾 Save to: {save_dir}\n\n"
                f"⏱ Estimated time: {estimated_minutes} minutes\n"
            )

            reply = QMessageBox.question(
                self, "Confirm Training",
                f"{summary}Start training?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Create progress dialog with better labels
            self.progress_dialog = QProgressDialog("Initializing training...", "Cancel Training", 0, epochs * 2, self)
            self.progress_dialog.setWindowTitle(f"Training YOLOv11 - {os.path.basename(folder_path)}")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.canceled.connect(self.cancel_training)

            # Set initial values
            self.progress_dialog.setValue(0)
            self.progress_dialog.setLabelText(f"Initializing training...")

            self.is_training = True
            self.training_start_time = datetime.now()
            self.current_epoch = 0
            self.total_epochs = epochs

            # Start training in a separate thread
            thread = threading.Thread(
                target=self.run_training_with_monitoring,
                args=(yaml_path, epochs, batch_size, model_name, save_dir),
                daemon=True
            )
            thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start training:\n{str(e)}")
            self.is_training = False

    def run_training_with_monitoring(self, yaml_path, epochs, batch_size, model_name, save_dir):
        """Run YOLOv11 training with progress monitoring"""
        try:
            from ultralytics import YOLO
            import torch
            import time
            import json
            import os
            from pathlib import Path

            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0

            # Update progress - Initialization
            self.training_signals.progress.emit(0, f"Initializing training on {device}...", "Starting...")

            # Create unique run name
            run_name = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            run_dir = os.path.join(save_dir, run_name)

            # Load model
            model = YOLO(model_name)

            # Update progress - Model loaded
            self.training_signals.progress.emit(5, f"Model {model_name} loaded", "Preparing dataset...")

            # Start training with callback for monitoring
            # We'll use a custom callback approach
            self.training_signals.progress.emit(10, "Starting training...", f"Processing {epochs} epochs")

            # Store start time for ETA calculation
            start_time = datetime.now()

            # Function to update progress based on log file monitoring
            def monitor_training_progress(run_dir, total_epochs):
                """Monitor training progress by checking results.csv"""
                results_csv_path = os.path.join(run_dir, "results.csv")
                last_epoch = 0

                while self.is_training:
                    try:
                        if os.path.exists(results_csv_path):
                            with open(results_csv_path, 'r') as f:
                                lines = f.readlines()
                                if len(lines) > 1:  # Skip header
                                    # Count completed epochs
                                    completed_epochs = len(lines) - 1
                                    last_epoch = completed_epochs

                                    # Calculate progress percentage
                                    progress_percent = min(99, int((completed_epochs / total_epochs) * 100))

                                    # Calculate ETA
                                    if completed_epochs > 0:
                                        elapsed_time = (datetime.now() - start_time).total_seconds()
                                        time_per_epoch = elapsed_time / completed_epochs
                                        remaining_epochs = total_epochs - completed_epochs
                                        eta_seconds = remaining_epochs * time_per_epoch

                                        # Format ETA
                                        if eta_seconds < 60:
                                            eta_str = f"{int(eta_seconds)} seconds"
                                        elif eta_seconds < 3600:
                                            eta_str = f"{int(eta_seconds / 60)} minutes"
                                        else:
                                            hours = int(eta_seconds / 3600)
                                            minutes = int((eta_seconds % 3600) / 60)
                                            eta_str = f"{hours}h {minutes}m"

                                        # Get latest metrics if available
                                        latest_line = lines[-1]
                                        metrics = latest_line.strip().split(',')
                                        if len(metrics) > 6:
                                            try:
                                                loss = float(metrics[3])
                                                precision = float(metrics[4])
                                                recall = float(metrics[5])
                                                mAP50 = float(metrics[6])
                                                status = f"Epoch {completed_epochs}/{total_epochs} | Loss: {loss:.3f} | mAP50: {mAP50:.3f}"
                                            except:
                                                status = f"Epoch {completed_epochs}/{total_epochs} | Processing..."
                                        else:
                                            status = f"Epoch {completed_epochs}/{total_epochs} | Training..."

                                        # Update progress
                                        self.training_signals.progress.emit(
                                            progress_percent,
                                            status,
                                            eta_str
                                        )

                        # Check for plots.png to see if training is making progress
                        plots_path = os.path.join(run_dir, "results.png")
                        if os.path.exists(plots_path):
                            # Training is producing visual results
                            pass

                    except Exception as e:
                        print(f"Progress monitoring error: {e}")

                    # Wait before checking again
                    time.sleep(2)  # Check every 2 seconds

            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=monitor_training_progress,
                args=(run_dir, epochs),
                daemon=True
            )
            monitor_thread.start()

            # Start training
            try:
                results = model.train(
                    data=yaml_path,
                    epochs=epochs,
                    batch=batch_size,
                    device=device,
                    project=save_dir,
                    name=run_name,
                    exist_ok=True,
                    verbose=True,  # Show detailed output
                    save=True,
                    save_period=min(10, epochs // 10),  # Save checkpoints periodically
                    plots=True,
                    workers=0,
                    patience=50,  # Early stopping patience
                    seed=42
                )
            except KeyboardInterrupt:
                print("Training interrupted by user")
                results = None

            # Update to 100% when done
            if self.is_training and results:
                self.training_signals.progress.emit(100, "Training completed!", "Processing final results...")

                # Find the best model
                best_model_path = os.path.join(run_dir, "weights", "best.pt")
                if os.path.exists(best_model_path):
                    success_message = (
                        f"✅ Training completed successfully!\n\n"
                        f"📁 Run directory: {run_dir}\n"
                        f"📊 Best model: {best_model_path}\n"
                        f"⏱ Training time: {str(datetime.now() - start_time).split('.')[0]}\n\n"
                        f"🎯 Results saved in:\n"
                        f"• results.png - Training metrics plot\n"
                        f"• results.csv - Detailed metrics\n"
                        f"• confusion_matrix.png - Confusion matrix\n"
                        f"• labels.jpg - Label distribution\n"
                    )
                else:
                    success_message = f"✅ Training completed!\nRun directory: {run_dir}"

                self.training_signals.finished.emit(True, success_message)

            elif not self.is_training:
                self.training_signals.finished.emit(False, "Training was cancelled by user.")
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
            self.training_signals.progress.emit(0, "Import error", "Failed")
            self.training_signals.finished.emit(False, error_msg)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"Training failed:\n{str(e)}"
            print(f"Training error details:\n{error_details}")

            # Try to get more details
            try:
                # Check if run directory was created
                run_dirs = [d for d in os.listdir(save_dir) if d.startswith("train_")]
                if run_dirs:
                    latest_run = sorted(run_dirs)[-1]
                    log_path = os.path.join(save_dir, latest_run, "train.log")
                    if os.path.exists(log_path):
                        with open(log_path, 'r') as f:
                            log_content = f.read()[-1000:]  # Last 1000 chars
                        error_msg += f"\n\nLast log entries:\n{log_content}"
            except:
                pass

            self.training_signals.progress.emit(0, "Training failed", "Error")
            self.training_signals.finished.emit(False, error_msg)

        finally:
            self.is_training = False

    def on_training_progress(self, progress, status, time_remaining):
        """Update training progress dialog with live updates"""
        if not self.is_training:
            return

        if self.progress_dialog:
            try:
                # Update progress value
                self.progress_dialog.setValue(progress)

                # Create detailed status text
                elapsed_time = datetime.now() - self.training_start_time
                elapsed_str = str(elapsed_time).split('.')[0]  # Remove microseconds

                status_text = f"{status}\n"
                status_text += f"Elapsed: {elapsed_str}\n"
                status_text += f"ETA: {time_remaining}"

                self.progress_dialog.setLabelText(status_text)
                self.status_label.setText(f"Training: {status.split('|')[0] if '|' in status else status}")

                # Update window title with progress
                self.setWindowTitle(f"BMP Annotation Tool - Training {progress}%")

            except Exception as e:
                print(f"Error updating progress: {e}")

    def on_training_finished(self, success, message):
        """Handle training completion"""
        self.is_training = False

        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        # Reset window title
        if hasattr(self, 'image_path') and self.image_path:
            self.setWindowTitle(
                f"BMP Annotation Tool – {os.path.basename(self.image_path)} "
                f"({self.current_index + 1}/{len(self.image_files)})"
            )
        else:
            self.setWindowTitle("BMP Annotation Tool")

        if success:
            # Play success sound if available (optional)
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except:
                pass

            # Show detailed success message
            success_dialog = QMessageBox(self)
            success_dialog.setWindowTitle("🎉 Training Complete!")
            success_dialog.setText(message)
            success_dialog.setIcon(QMessageBox.Information)

            # Add buttons
            success_dialog.setStandardButtons(
                QMessageBox.Ok |
                QMessageBox.Open
            )

            # Customize button texts
            success_dialog.button(QMessageBox.Ok).setText("OK")
            success_dialog.button(QMessageBox.Open).setText("Open Results Folder")

            # Connect the Open button
            if success_dialog.exec() == QMessageBox.Open:
                # Extract run directory from message
                import re
                match = re.search(r"Run directory: (.*?)\n", message)
                if match:
                    run_dir = match.group(1)
                    if os.path.exists(run_dir):
                        os.startfile(run_dir)

            self.status_label.setText("Training completed successfully!")
        else:
            QMessageBox.critical(self, "Training Failed", message)
            self.status_label.setText("Training failed")

        # Reset status after 5 seconds
        QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))

    def cancel_training(self):
        """Cancel the training process"""
        if self.is_training:
            self.is_training = False
            self.status_label.setText("Training cancelled")

            # Try to interrupt the training process
            try:
                import signal
                import os
                # This is a best-effort attempt to stop training
                print("Attempting to cancel training...")
            except:
                pass

            QMessageBox.information(self, "Training Cancelled",
                                    "Training cancellation requested.\nIt may take a moment to stop.")

    # ---------- Other Methods (unchanged) ----------
    def auto_add_label(self):
        """Automatically add a sequentially numbered label (object1, object2, etc.)"""
        self.label_counter += 1
        new_label = str(self.label_counter)

        if new_label not in self.labels:
            self.labels.append(new_label)
            self.label_colors[new_label] = self.generate_color()
            self.label_combo.addItem(new_label)
            self.label_combo.setCurrentText(new_label)

            self.status_label.setText(f"Added label: {new_label}")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

    def delete_selected(self):
        self.viewer.delete_selected()

    def load_model(self):
        """Load a trained YOLOv11 model for inference - auto find latest model"""
        if self.is_training:
            QMessageBox.warning(self, "Training in Progress",
                                "Please wait for training to complete before loading a model.")
            return

        try:
            # Default to Model folder
            model_folder = self.model_path

            # Create folder if it doesn't exist
            os.makedirs(model_folder, exist_ok=True)

            # Find all train_* directories
            train_dirs = [d for d in os.listdir(model_folder)
                          if d.startswith("train_") and os.path.isdir(os.path.join(model_folder, d))]

            if not train_dirs:
                # No trained models found, show message
                QMessageBox.warning(self, "No Models Found",
                                    f"No trained models found in:\n{model_folder}\n\n"
                                    "Please train a model first.")
                return

            # Find the latest training run (by timestamp in folder name)
            latest_dir = None
            latest_time = None

            for dir_name in train_dirs:
                try:
                    # Extract timestamp from folder name: train_YYYYMMDD_HHMMSS
                    if dir_name.startswith("train_"):
                        timestamp_str = dir_name[6:]  # Remove "train_"
                        # Convert to datetime object
                        dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                        if latest_time is None or dt > latest_time:
                            latest_time = dt
                            latest_dir = dir_name
                except:
                    continue  # Skip folders with invalid format

            if not latest_dir:
                QMessageBox.warning(self, "Error", "Could not find a valid trained model.")
                return

            # Build path to best.pt in the latest folder
            best_model_path = os.path.join(model_folder, latest_dir, "weights", "best.pt")

            if not os.path.exists(best_model_path):
                # Check if weights folder exists but best.pt is missing
                weights_folder = os.path.join(model_folder, latest_dir, "weights")
                if os.path.exists(weights_folder):
                    # Try to find any .pt file
                    pt_files = [f for f in os.listdir(weights_folder) if f.lower().endswith('.pt')]
                    if pt_files:
                        # Try to find best.pt, last.pt, or any other .pt file
                        preferred_files = ["best.pt", "last.pt"]
                        for pref_file in preferred_files:
                            if pref_file in pt_files:
                                best_model_path = os.path.join(weights_folder, pref_file)
                                break
                        else:
                            # Use the first .pt file found
                            best_model_path = os.path.join(weights_folder, pt_files[0])
                    else:
                        QMessageBox.warning(self, "No Model Files",
                                            f"No .pt model files found in:\n{weights_folder}")
                        return
                else:
                    QMessageBox.warning(self, "Weights Folder Not Found",
                                        f"Weights folder not found in:\n{os.path.join(model_folder, latest_dir)}")
                    return

            # Validate the model file
            if not best_model_path.lower().endswith('.pt'):
                QMessageBox.warning(self, "Invalid File",
                                    "Selected file is not a .pt PyTorch model file.")
                return

            # Load the model
            loading_dialog = QProgressDialog(f"Loading latest model: {latest_dir}", None, 0, 0, self)
            loading_dialog.setWindowTitle(f"Loading {os.path.basename(best_model_path)}")
            loading_dialog.setWindowModality(Qt.WindowModal)
            loading_dialog.show()

            try:
                from ultralytics import YOLO
                import torch

                device = 'cuda' if torch.cuda.is_available() else 'cpu'

                self.current_model = YOLO(best_model_path)
                self.current_model_path = best_model_path

                # Get model info
                model_name = os.path.basename(best_model_path)
                model_size = os.path.getsize(best_model_path) / (1024 * 1024)
                model_type = "best.pt" if "best.pt" in best_model_path else "model"

                # Get training info
                training_time = latest_time.strftime('%Y-%m-%d %H:%M:%S')
                training_folder = latest_dir

                # Update model info label
                self.model_info_label.setText(
                    f"Model: {model_name} ({model_size:.1f} MB) | "
                    f"Trained: {training_time} | "
                    f"Device: {device}"
                )
                self.model_info_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

                loading_dialog.close()

                # Show success message
                QMessageBox.information(
                    self, "✅ Latest Model Loaded",
                    f"Successfully loaded latest trained model!\n\n"
                    f"📁 Training run: {training_folder}\n"
                    f"⏰ Trained on: {training_time}\n"
                    f"🤖 Model file: {model_name}\n"
                    f"📦 Size: {model_size:.1f} MB\n"
                    f"⚡ Device: {device}\n"
                    f"📁 Path: {best_model_path}"
                )

            except Exception as e:
                loading_dialog.close()
                QMessageBox.critical(self, "Load Failed", f"Failed to load model:\n{str(e)}")
                self.current_model = None
                self.current_model_path = None
                self.model_info_label.setText("No model loaded")
                self.model_info_label.setStyleSheet("color: #666; font-style: italic;")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model:\n{str(e)}")

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
            self.prediction_progress_dialog = QProgressDialog(
                "Running inference...", "Cancel", 0, 100, self
            )
            self.prediction_progress_dialog.setWindowTitle("Running Prediction")
            self.prediction_progress_dialog.setWindowModality(Qt.WindowModal)
            self.prediction_progress_dialog.setMinimumDuration(0)
            self.prediction_progress_dialog.canceled.connect(self.cancel_prediction)

            self.is_predicting = True

            thread = threading.Thread(
                target=self.run_prediction,
                args=(self.image_path,),
                daemon=True
            )
            thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start prediction:\n{str(e)}")
            self.is_predicting = False

    def run_prediction(self, image_path):
        """Run prediction on a single image"""
        try:
            from ultralytics import YOLO
            import torch

            self.prediction_signals.progress.emit(10, "Loading model...")

            if not hasattr(self, 'current_model') or self.current_model is None:
                if hasattr(self, 'current_model_path') and self.current_model_path:
                    self.current_model = YOLO(self.current_model_path)
                else:
                    self.prediction_signals.finished.emit(False, "No model loaded", [])
                    return

            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            self.prediction_signals.progress.emit(30, f"Running inference on {device}...")

            results = self.current_model.predict(
                source=image_path,
                conf=0.25,
                iou=0.45,
                device=device,
                save=False,
                save_txt=False,
                save_conf=True,
                show=False,
                verbose=False
            )

            self.prediction_signals.progress.emit(70, "Processing results...")

            predictions = []
            if results and len(results) > 0:
                result = results[0]

                if hasattr(result, 'boxes') and result.boxes is not None:
                    boxes = result.boxes

                    if hasattr(boxes, 'xyxy') and boxes.xyxy is not None:
                        num_detections = len(boxes.xyxy)
                    else:
                        num_detections = 0

                    for i in range(num_detections):
                        try:
                            box = boxes.xyxy[i].cpu().numpy()
                            conf = float(boxes.conf[i].cpu().numpy()) if boxes.conf is not None else 0.0
                            cls = int(boxes.cls[i].cpu().numpy()) if boxes.cls is not None else 0
                            class_name = f"class_{cls}"
                            if hasattr(result, 'names') and result.names:
                                class_name = result.names.get(cls, f"class_{cls}")

                            predictions.append({
                                'bbox': box.tolist(),
                                'confidence': conf,
                                'class_id': cls,
                                'class_name': class_name
                            })
                        except Exception as e:
                            print(f"Error processing detection {i}: {e}")
                            continue

            output_dir = os.path.join(os.path.dirname(image_path), "predictions")
            os.makedirs(output_dir, exist_ok=True)

            output_filename = f"pred_{os.path.basename(image_path)}"
            output_path = os.path.join(output_dir, output_filename)

            if results and len(results) > 0:
                result.save(filename=output_path)

            self.prediction_signals.progress.emit(90, "Saving results...")

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

    def run_batch_prediction(self, folder_path, image_files):
        """Run prediction on a batch of images"""
        try:
            from ultralytics import YOLO
            import torch

            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            output_dir = os.path.join(folder_path, "predictions")
            os.makedirs(output_dir, exist_ok=True)

            total_images = len(image_files)
            processed = 0

            for i, image_file in enumerate(image_files):
                if not self.is_predicting:
                    break

                image_path = os.path.join(folder_path, image_file)

                self.prediction_signals.progress.emit(
                    int((i / total_images) * 100),
                    f"Processing {i + 1}/{total_images}: {image_file}"
                )

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

            if predictions:
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QDialogButtonBox

                dialog = QDialog(self)
                dialog.setWindowTitle("Save Predictions")
                dialog.setModal(True)

                layout = QVBoxLayout()

                layout.addWidget(QLabel(f"Found {len(predictions)} objects.\nSelect format to save:"))

                radio_yolo = QRadioButton("YOLO format (normalized: class x_center y_center width height)")
                radio_pixel = QRadioButton("Pixel coordinates (class confidence x1 y1 x2 y2)")
                radio_both = QRadioButton("Both formats")

                radio_yolo.setChecked(True)

                layout.addWidget(radio_yolo)
                layout.addWidget(radio_pixel)
                layout.addWidget(radio_both)

                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(dialog.accept)
                buttons.rejected.connect(dialog.reject)
                layout.addWidget(buttons)

                dialog.setLayout(layout)

                # if dialog.exec() == QDialog.Accepted:
                #     if radio_yolo.isChecked():
                #         format_type = "yolo"
                #     elif radio_pixel.isChecked():
                #         format_type = "pixel"
                #     elif radio_both.isChecked():
                #         format_type = "both"
                #
                #     self.viewer.save_predictions_as_annotations(self.image_path, predictions, format_type)
                #
                #     format_names = {
                #         "yolo": "YOLO format (.txt)",
                #         "pixel": "Pixel coordinates (.txt)",
                #         "both": "Both formats"
                #     }
                #
                #     QMessageBox.information(self, "Saved",
                #                             f"Predictions saved in {format_names[format_type]} format\n"
                #                             f"Saved to: labels/ folder")
            else:
                QMessageBox.information(self, "Prediction Complete",
                                        "No objects detected in the image.")

        else:
            self.status_label.setText("Prediction failed")
            QMessageBox.critical(self, "Prediction Failed", message)

        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

    def on_prediction_image_ready(self, image_path):
        """Load and display the predicted image"""
        try:
            if os.path.exists(image_path):
                self.viewer.load_image(image_path)
                self.viewer.update()

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

        QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))

    def cancel_training(self):
        """Cancel the training process"""
        if self.is_training:
            self.is_training = False
            self.status_label.setText("Training cancelled")
            QMessageBox.information(self, "Training Cancelled", "Training has been cancelled.")

    def capture_from_camera(self):
        """Capture from camera and save to Capture Image folder"""
        # Always use this specific path
        self.capture_folder = self.capture_image_path

        os.makedirs(self.capture_folder, exist_ok=True)

        self.capture_btn.setEnabled(False)
        self.capture_btn.setText("Capturing...")

        def run_capture():
            def callback(success, message, image_path):
                if success and image_path:
                    base_name = os.path.basename(image_path)
                    save_path = os.path.join(self.capture_folder, base_name)

                    count = 1
                    name, ext = os.path.splitext(base_name)
                    while os.path.exists(save_path):
                        save_path = os.path.join(self.capture_folder, f"{name}_{count}{ext}")
                        count += 1

                    os.rename(image_path, save_path)
                    image_path = save_path

                self.camera_signals.finished.emit(success, message, image_path)

            AutoCaptureFlow(callback=callback)

        thread = threading.Thread(target=run_capture, daemon=True)
        thread.start()

    def capture_predict(self):
        """Second camera capture - also runs auto-prediction"""
        # Use the SAME path for both cameras
        self.capture_folder_2 = self.capture_image_prediction_path

        os.makedirs(self.capture_folder_2, exist_ok=True)

        self.capture2_btn.setEnabled(False)
        self.capture2_btn.setText("Capturing...")

        def run_capture():
            def callback(success, message, image_path):
                if success and image_path:
                    base_name = os.path.basename(image_path)
                    save_path = os.path.join(self.capture_folder_2, base_name)

                    count = 1
                    name, ext = os.path.splitext(base_name)
                    while os.path.exists(save_path):
                        save_path = os.path.join(self.capture_folder_2, f"{name}_{count}{ext}")
                        count += 1

                    os.rename(image_path, save_path)
                    image_path = save_path

                # Use the SECOND camera signal
                self.camera_signals_2.finished.emit(success, message, image_path)

            AutoCaptureFlow(callback=callback)

        thread = threading.Thread(target=run_capture, daemon=True)
        thread.start()

    def on_camera_finished(self, success, message, image_path):
        """Handle camera capture completion"""
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("Capture Image")

        if success and image_path:
            if os.path.exists(image_path):
                if image_path not in self.image_files:
                    self.image_files.append(image_path)
                    self.image_files.sort()

                self.current_index = self.image_files.index(image_path)
                self.load_current_image()
        else:
            QMessageBox.critical(self, "Capture Failed",
                                 f"Camera capture failed!\n{message}")

    def on_camera_finished_predict(self, success, message, image_path):
        """Handle camera capture completion for button 2"""
        self.capture2_btn.setEnabled(True)
        self.capture2_btn.setText("Capture & Predict")

        if success and image_path:
            if os.path.exists(image_path):
                if image_path not in self.image_files:
                    self.image_files.append(image_path)
                    self.image_files.sort()

                self.current_index = self.image_files.index(image_path)
                self.load_current_image()

                # Auto-run prediction after capture
                if hasattr(self, 'current_model') and self.current_model is not None:
                    QTimer.singleShot(500, self.predict_current_image)
                else:
                    # Model not loaded - show warning
                    self.status_label.setText("Model not loaded - skipping auto-prediction")
        else:
            QMessageBox.critical(self, "Capture Failed",
                                 f"Camera capture failed!\n{message}")

    def get_label_color(self, label):
        return self.label_colors.get(label, QColor(255, 255, 255))

    def generate_color(self):
        """Generate a random but distinct color for new labels"""
        hue = random.randint(0, 359)
        saturation = random.randint(150, 255)
        value = random.randint(150, 255)

        color = QColor.fromHsv(hue, saturation, value)
        return color

    def open_folder(self):
        """Open the hardcoded folder from specific path"""
        # Use the specific path you mentioned
        folder = self.capture_image_path

        # Check if the folder exists
        if not os.path.exists(folder):
            # Try to create the folder if it doesn't exist
            try:
                os.makedirs(folder, exist_ok=True)
                print(f"Created folder: {folder}")
            except Exception as e:
                QMessageBox.warning(self, "Folder Error",
                                    f"Cannot access or create folder:\n{folder}\nError: {str(e)}")
                return

        # Scan for images
        image_extensions = ('.bmp', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.gif')
        self.image_files = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(image_extensions)
        ])

        if not self.image_files:
            QMessageBox.information(self, "No Images Found",
                                    f"No image files found in:\n{folder}\n\n"
                                    f"Supported formats: BMP, JPG, JPEG, PNG, TIFF, GIF")
            return

        self.current_index = 0
        self.load_current_image()

        # Update status
        self.status_label.setText(f"Loaded {len(self.image_files)} images from Capture Image folder")

    def load_current_image(self):
        """Load the current image into the viewer"""
        path = self.image_files[self.current_index]
        self.viewer.boxes.clear()
        self.viewer.load_image(path)
        self.image_path = path

        self.setWindowTitle(
            f"BMP Annotation Tool – {os.path.basename(path)} "
            f"({self.current_index + 1}/{len(self.image_files)})"
        )

        # Update image info label
        self.image_info_label.setText(f"{os.path.basename(path)} ({self.current_index + 1}/{len(self.image_files)})")

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

    def get_current_label(self):
        return self.label_combo.currentText()

    def undo(self):
        self.viewer.undo_last()

    def save_current(self):
        """Save annotations for current image in YOLO format"""
        if hasattr(self, "image_path") and self.image_path:
            self.viewer.save_annotations(self.image_path)

    def closeEvent(self, event):
        """Handle window close event"""
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

        # Disconnect TCP if connected
        if self.tcp_connected:
            self.disconnect_tcp()

        event.accept()
import os
import random
import threading
import socket
import time
import json
import numpy as np
import cv2
from datetime import datetime, timedelta
from PIL import Image
from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QWidget,
    QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QInputDialog,
    QMessageBox, QProgressDialog, QLabel,
    QLineEdit, QSpinBox, QStackedWidget,
    QGroupBox, QScrollArea, QTextEdit, QCheckBox, QProgressBar
)
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QPixmap, QTextCursor
from PySide6.QtCore import Signal, QObject, QTimer, Qt, QRectF, QPointF
from annotator import AnnotationWidget

# Import camera capture function
try:
    from camera import AutoCaptureFlow

    CAMERA_AVAILABLE = True
except ImportError as e:
    CAMERA_AVAILABLE = False
    print(f"Warning: camera module not found. Camera button will be disabled. Error: {e}")


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
        self.setWindowTitle("BMP Annotation Tool with Camera, Training & Label ID Scan")
        self.resize(1400, 900)

        # Define base paths
        self.base_path = "C:\\Users\\SiP-PHChin\\OneDrive - SIP Technology (M) Sdn Bhd\\Desktop"
        self.capture_image_path = f"{self.base_path}\\Capture Image"
        self.capture_image_prediction_path = f"{self.base_path}\\Capture Prediction"
        self.model_path = f"{self.base_path}\\Model"
        self.labeling_path = f"{self.base_path}\\Labeling"
        self.image_boxes = {}

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
        self.listening_active = False
        self.scan_data_received = ""
        self.last_bounding_box = None  # Store the last drawn bounding box
        self.last_box_label = None  # Store the label of the last box
        self.tcp_received_text = ""  # Store the latest TCP received text
        self.selected_class_for_prediction = None  # Add this line

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

        # Add calibration object
        self.calibration = Calibration()

        # Add calibration UI elements
        self.calibration_progress = QProgressBar()
        self.calibration_progress.setRange(0, 10)
        self.calibration_progress.setVisible(False)

        self.calibration_status = QLabel("No calibration loaded")
        self.calibration_status.setStyleSheet("color: #666; font-style: italic;")

        self.save_calibration_btn = QPushButton("💾 Save Calibration")
        self.save_calibration_btn.clicked.connect(self.save_calibration)
        self.save_calibration_btn.setEnabled(False)
        self.save_calibration_btn.setStyleSheet("background-color: #4CAF50; color: white;")

        # Create the load button
        self.load_calibration_btn = QPushButton("📂 Load Calibration")
        self.load_calibration_btn.clicked.connect(self.load_calibration)
        self.load_calibration_btn.setStyleSheet("background-color: #2196F3; color: white;")

        self.is_training = False
        self.is_predicting = False
        self.training_start_time = None
        self.progress_dialog = None
        self.prediction_progress_dialog = None
        self.current_model_path = None
        self.current_model = None

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

        # Add OBB toggle button to top bar
        self.obb_mode_btn = QPushButton("OBB Mode OFF")
        self.obb_mode_btn.setCheckable(True)
        self.obb_mode_btn.clicked.connect(self.toggle_obb_mode)
        self.obb_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:checked {
                background-color: #FF9800;
            }
        """)

        # --- ADD CALIBRATION BUTTONS HERE, WITH THE OTHER BUTTONS ---
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
        top_bar.addWidget(self.obb_mode_btn)

        # ADD THE CALIBRATION BUTTONS HERE:
        top_bar.addWidget(self.load_calibration_btn)
        top_bar.addWidget(self.save_calibration_btn)

        top_bar.addStretch()
        # --- END OF CALIBRATION BUTTON ADDITION ---

        # ---------- Labels Section ----------
        self.label_combo = QComboBox()
        self.label_combo.addItems(self.labels)

        self.add_label_btn = QPushButton("+")
        self.add_label_btn.setFixedWidth(40)
        self.add_label_btn.clicked.connect(self.auto_add_label)
        self.add_label_btn.setToolTip("Add new label (1, 2, 3, ...)")

        label_bar = QHBoxLayout()
        label_bar.addWidget(self.label_combo)
        label_bar.addWidget(self.add_label_btn)
        label_bar.addStretch()

        # ---------- Main Content Area ----------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # ---------- Left Column: Annotation Viewer (70%) ----------
        left_column = QVBoxLayout()

        # FIX: Create AnnotationWidget FIRST before connecting signals
        self.viewer = AnnotationWidget(
            self.get_current_label,
            self.get_label_color
        )

        # FIX: Connect signals AFTER creating the viewer
        self.viewer.status_message.connect(self.on_annotation_status)

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
        self.host_edit = QLineEdit("192.168.1.100")
        self.host_edit.setPlaceholderText("Server IP")
        form_layout.addWidget(self.host_edit)

        form_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(8888)
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

        # ---------- CREATE FILTER WIDGETS HERE (BEFORE USING THEM) ----------
        self.class_filter_checkbox = QCheckBox("Filter by Class")
        self.class_filter_combo = QComboBox()
        self.class_filter_combo.setEnabled(False)

        self.class_filter_checkbox.stateChanged.connect(
            lambda state: self.class_filter_combo.setEnabled(state == Qt.Checked)
        )

        # Add filter layout
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.class_filter_checkbox)
        filter_layout.addWidget(self.class_filter_combo)
        filter_layout.addStretch()

        # Add filter layout to main layout
        layout.addLayout(filter_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # ---------- Shortcuts ----------
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_selected)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self.train_model)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.load_model)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.predict_current_image_with_filter)
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self.auto_add_label)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self.auto_tcp_scan)

    def on_annotation_status(self, message):
        """Handle status messages from annotation widget"""
        self.status_label.setText(message)
        # Also update TCP messages display if needed
        if "OBB" in message or "corner" in message:
            timestamp = time.strftime("%H:%M:%S")
            self.update_tcp_messages(f"[{timestamp}] 🎯 {message}")

    def toggle_obb_mode(self, checked):
        """Toggle Oriented Bounding Box mode"""
        # Call the viewer's toggle_obb_mode method
        self.viewer.toggle_obb_mode(checked)

        # Set/remove OBB mode flag file
        self.viewer.set_obb_mode_flag(self.labeling_path, checked)

        if checked:
            self.obb_mode_btn.setText("OBB Mode ON")
            self.obb_mode_btn.setStyleSheet("""
                QPushButton:checked {
                    background-color: #FF9800;
                    color: white;
                    font-weight: bold;
                    padding: 5px;
                }
            """)
            self.status_label.setText("OBB Mode: Click 4 corners to define rotated box")
        else:
            self.obb_mode_btn.setText("OBB Mode OFF")
            self.obb_mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #9C27B0;
                    color: white;
                    font-weight: bold;
                    padding: 5px;
                }
            """)
            self.status_label.setText("Ready")

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

        # Close existing connection if any
        self.disconnect_tcp()

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
                finally:
                    # Re-enable button in main thread
                    QTimer.singleShot(0, lambda: self.labeling_btn.setEnabled(True))

            self.tcp_thread = threading.Thread(target=connect_thread, daemon=True)
            self.tcp_thread.start()

        except Exception as e:
            self.on_tcp_connection_status(f"Connection error: {str(e)}", False)
            self.labeling_btn.setEnabled(True)

    def disconnect_tcp(self):
        """Close TCP connection"""
        self.listening_active = False
        self.tcp_connected = False

        if self.tcp_socket:
            try:
                self.tcp_socket.shutdown(socket.SHUT_RDWR)
                self.tcp_socket.close()
            except:
                pass
            finally:
                self.tcp_socket = None

        self.labeling_btn.setText("Image Labeling")
        self.labeling_btn.setStyleSheet("background-color: #795548; color: white; font-weight: bold;")
        self.labeling_btn.setEnabled(True)
        self.connection_status_label.setText("Status: Disconnected")
        self.update_tcp_messages("[System] Disconnected from server")

    def start_listening(self):
        """Start listening for incoming messages"""
        self.listening_active = True

        def listen_thread():
            while self.tcp_connected and self.tcp_socket and self.listening_active:
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
        """Combined function: Auto prepare dataset + Train YOLOv11 model"""
        if self.is_training:
            QMessageBox.warning(self, "Training in Progress",
                                "A training session is already in progress.")
            return

        try:
            # ---------------- Step 1: Prepare dataset ----------------
            folder_path = self.capture_image_path  # where train/val images live
            if not os.path.exists(folder_path):
                QMessageBox.warning(self, "Folder Not Found",
                                    f"Dataset folder not found:\n{folder_path}")
                return

            # Auto-split and generate data.yaml using labeled files
            self.status_label.setText("Preparing dataset...")
            success = self.viewer.auto_split_and_generate_yaml(
                self.capture_image_path,
                self.labeling_path
            )

            if not success:
                QMessageBox.warning(self, "Dataset Preparation Failed",
                                    "No valid labeled files found or no images in capture path.")
                return
            self.status_label.setText("Dataset ready!")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

            # Check that we have training images
            images_train_dir = os.path.join(folder_path, "images", "train")
            train_images = [f for f in os.listdir(images_train_dir)
                            if f.lower().endswith(('.bmp', '.jpg', '.jpeg', '.png'))]
            if len(train_images) == 0:
                QMessageBox.warning(self, "No Training Images",
                                    f"No images found in training folder: {images_train_dir}")
                return

            # ---------------- Step 2: Ask for training parameters ----------------
            epochs, ok = QInputDialog.getInt(
                self, "Training Epochs",
                "Enter number of training epochs (recommended: 50-300):",
                100, 10, 1000, 1
            )
            if not ok:
                return

            batch_size, ok = QInputDialog.getInt(
                self, "Batch Size",
                "Enter batch size:\n• 4-8 for low GPU memory\n• 16-32 for sufficient GPU\n• 1-4 for CPU",
                16, 1, 64, 1
            )
            if not ok:
                return

            model_size, ok = QInputDialog.getItem(
                self, "Model Size",
                "Select YOLOv11 model size:",
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

            # Ensure model save folder exists
            save_dir = self.model_path
            os.makedirs(save_dir, exist_ok=True)

            # ---------------- Step 3: Show training summary ----------------
            import torch
            device_info = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
            summary = (
                f"🚀 Training Configuration:\n\n"
                f"📁 Dataset: {os.path.basename(folder_path)}\n"
                f"📊 data.yaml: {os.path.join(folder_path, 'data.yaml')}\n"
                f"🔄 Epochs: {epochs}\n"
                f"📦 Batch Size: {batch_size}\n"
                f"🤖 Model: {model_name}\n"
                f"⚡ Device: {device_info}\n"
                f"💾 Save to: {save_dir}\n"
            )
            reply = QMessageBox.question(
                self, "Confirm Training", f"{summary}\nStart training?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            # ---------------- Step 4: Start training ----------------
            self.progress_dialog = QProgressDialog("Initializing training...", "Cancel Training", 0, epochs * 2, self)
            self.progress_dialog.setWindowTitle(f"Training YOLOv11 - {os.path.basename(folder_path)}")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.canceled.connect(self.cancel_training)
            self.progress_dialog.setValue(0)

            self.is_training = True
            self.training_start_time = datetime.now()
            self.current_epoch = 0
            self.total_epochs = epochs

            # Start training thread
            thread = threading.Thread(
                target=self.run_training_with_monitoring,
                args=(os.path.join(folder_path, "data.yaml"), epochs, batch_size, model_name, save_dir),
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
            if device == 'cuda':
                gpu_index = torch.cuda.current_device()
                gpu_name = torch.cuda.get_device_name(gpu_index)
                gpu_info = f"GPU {gpu_index}: {gpu_name}"
            else:
                gpu_info = "CPU"
            gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0

            # Check if this is OBB dataset
            is_obb = False
            try:
                import yaml
                with open(yaml_path, 'r') as f:
                    data = yaml.safe_load(f)
                    # OBB datasets have task='obb'
                    is_obb = data.get('task') == 'obb'
            except:
                pass

            # Use appropriate model for OBB
            if is_obb:
                # Determine model size from model_name
                original_model_name = model_name

                if "nano" in original_model_name or "n" in original_model_name:
                    model_size_key = "nano (yolo11n)"
                elif "small" in original_model_name or "s" in original_model_name:
                    model_size_key = "small (yolo11s)"
                elif "medium" in original_model_name or "m" in original_model_name:
                    model_size_key = "medium (yolo11m)"
                elif "large" in original_model_name or "l" in original_model_name:
                    model_size_key = "large (yolo11l)"
                elif "xlarge" in original_model_name or "x" in original_model_name:
                    model_size_key = "xlarge (yolo11x)"
                else:
                    model_size_key = "nano (yolo11n)"

                obb_model_map = {
                    "nano (yolo11n)": "yolo11n-obb.pt",
                    "small (yolo11s)": "yolo11s-obb.pt",
                    "medium (yolo11m)": "yolo11m-obb.pt",
                    "large (yolo11l)": "yolo11l-obb.pt",
                    "xlarge (yolo11x)": "yolo11x-obb.pt"
                }
                model_name = obb_model_map.get(model_size_key, "yolo11n-obb.pt")

            model = YOLO(model_name)

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
                    seed=42,

                    # --- NEW PARAMETERS ADDED HERE ---
                    hsv_h=0.0,  # Set Hue to 0.0: Stops the AI from "recoloring" your red box to green/blue
                    hsv_s=0.0,  # Set Saturation to 0.0: Keeps colors from becoming gray or neon
                    hsv_v=0.2,  # (Optional) Value 0.2: Allows slight brightness changes for light/shadow
                    degrees=0.0,  # Set to 0.0: No rotation (since your orientation is fixed)
                    fliplr=0.0,  # Set to 0.0: No horizontal flipping
                    flipud=0.0,  # Set to 0.0: No vertical flipping
                    translate=0.05  # 0.05: Allows for that 5cm "offset" or movement you mentioned
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

    def predict_current_image_with_filter(self):
        """Run inference with class filter"""
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
                f"Running inference for class {self.selected_class_for_prediction}..."
                if self.selected_class_for_prediction is not None
                else "Running inference for all classes...",
                "Cancel", 0, 100, self
            )
            self.prediction_progress_dialog.setWindowTitle("Running Prediction")
            self.prediction_progress_dialog.setWindowModality(Qt.WindowModal)
            self.prediction_progress_dialog.setMinimumDuration(0)
            self.prediction_progress_dialog.canceled.connect(self.cancel_prediction)

            self.is_predicting = True

            thread = threading.Thread(
                target=self.run_prediction_with_filter,
                args=(self.image_path, self.selected_class_for_prediction),
                daemon=True
            )
            thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start prediction:\n{str(e)}")
            self.is_predicting = False

    def run_prediction_with_filter(self, image_path, class_filter):
        """Run prediction with class filter - supports both regular and OBB"""
        try:
            from ultralytics import YOLO
            import torch
            import math
            import numpy as np
            import socket
            import json

            self.prediction_signals.progress.emit(10, "Loading model...")

            if not hasattr(self, 'current_model') or self.current_model is None:
                if hasattr(self, 'current_model_path') and self.current_model_path:
                    self.current_model = YOLO(self.current_model_path)
                else:
                    self.prediction_signals.finished.emit(False, "No model loaded", [])
                    return

            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            # Show which class we're detecting
            if class_filter is not None:
                class_names = self.current_model.names if hasattr(self.current_model, 'names') else {}
                class_name = class_names.get(class_filter, f"class_{class_filter}")
                self.prediction_signals.progress.emit(30,
                                                      f"Detecting class {class_filter} ({class_name}) on {device}...")
            else:
                self.prediction_signals.progress.emit(30, f"Detecting all classes on {device}...")

            # Check if model is OBB
            is_obb = hasattr(self.current_model, 'task') and self.current_model.task == 'obb'

            # Run prediction
            results = self.current_model.predict(
                source=image_path,
                conf=0.25,
                iou=0.45,
                device=device,
                save=False,
                save_txt=False,
                save_conf=True,
                show=False,
                verbose=False,
                classes=[class_filter] if class_filter is not None else None
            )

            self.prediction_signals.progress.emit(70, "Processing results...")

            predictions = []
            coordinate_strings = []  # Store coordinate strings for TCP sending
            world_coordinate_strings = []  # Store world coordinate strings for TCP sending

            if results and len(results) > 0:
                result = results[0]

                # Print image information
                print(f"\n{'=' * 60}")
                print(f"PREDICTION RESULTS FOR: {os.path.basename(image_path)}")
                print(f"{'=' * 60}")

                # Handle OBB results
                if is_obb and hasattr(result, 'obb') and result.obb is not None:
                    # Process OBB detections
                    obb = result.obb
                    print(f"\n📦 OBB DETECTIONS FOUND: {len(obb.xyxyxyxy)}")
                    print(f"{'-' * 60}")

                    for i in range(len(obb.xyxyxyxy)):
                        try:
                            # Get 4 corner points
                            corners = obb.xyxyxyxy[i].cpu().numpy()
                            conf = float(obb.conf[i].cpu().numpy()) if obb.conf is not None else 0.0
                            cls = int(obb.cls[i].cpu().numpy()) if obb.cls is not None else 0
                            class_name = f"class_{cls}"
                            if hasattr(result, 'names') and result.names:
                                class_name = result.names.get(cls, f"class_{cls}")

                            # Convert corners to bbox format (x1, y1, x2, y2) for display
                            x_coords = corners[:, 0]
                            y_coords = corners[:, 1]
                            x1 = float(np.min(x_coords))
                            y1 = float(np.min(y_coords))
                            x2 = float(np.max(x_coords))
                            y2 = float(np.max(y_coords))

                            # Convert pixel coordinates to world coordinates for all 4 corners
                            world_corners = []
                            if hasattr(self, 'calibration') and self.calibration.is_calibrated:
                                for corner in corners:
                                    world_point = self.calibration.pixel_to_world((corner[0], corner[1]))
                                    if world_point:
                                        world_corners.append(world_point)
                                    else:
                                        world_corners.append((corner[0], corner[1]))  # Fallback to pixel
                            else:
                                # If not calibrated, use pixel coordinates
                                world_corners = [(corner[0], corner[1]) for corner in corners]

                            predictions.append({
                                'bbox': [x1, y1, x2, y2],
                                'corners': corners.tolist(),  # Store corners for OBB
                                'world_corners': world_corners,  # Store world coordinates
                                'confidence': conf,
                                'class_id': cls,
                                'class_name': class_name,
                                'is_obb': True
                            })

                            # Format pixel coordinates for TCP sending: x1_y1,x2_y2,x3_y3,x4_y4
                            coord_string = (f"{corners[0][0]:.2f}_{corners[0][1]:.2f},"
                                            f"{corners[1][0]:.2f}_{corners[1][1]:.2f},"
                                            f"{corners[2][0]:.2f}_{corners[2][1]:.2f},"
                                            f"{corners[3][0]:.2f}_{corners[3][1]:.2f}")

                            # Format world coordinates for TCP sending
                            world_coord_string = (f"{world_corners[0][0]:.2f}_{world_corners[0][1]:.2f},"
                                                  f"{world_corners[1][0]:.2f}_{world_corners[1][1]:.2f},"
                                                  f"{world_corners[2][0]:.2f}_{world_corners[2][1]:.2f},"
                                                  f"{world_corners[3][0]:.2f}_{world_corners[3][1]:.2f}")

                            coordinate_strings.append(coord_string)
                            world_coordinate_strings.append(world_coord_string)

                            print(f"\n🔹 OBB Detection #{i + 1}:")
                            print(f"   Class: {class_name} (ID: {cls})")
                            print(f"   Confidence: {conf:.3f}")
                            print(f"   Pixel Coordinates: {coord_string}")
                            print(f"   World Coordinates: {world_coord_string}")

                        except Exception as e:
                            print(f"Error processing OBB detection {i}: {e}")
                            continue

                # Handle regular box results
                elif hasattr(result, 'boxes') and result.boxes is not None:
                    boxes = result.boxes
                    print(f"\n📦 REGULAR DETECTIONS FOUND: {len(boxes.xyxy)}")
                    print(f"{'-' * 60}")

                    for i in range(len(boxes.xyxy)):
                        try:
                            box = boxes.xyxy[i].cpu().numpy()
                            conf = float(boxes.conf[i].cpu().numpy()) if boxes.conf is not None else 0.0
                            cls = int(boxes.cls[i].cpu().numpy()) if boxes.cls is not None else 0
                            class_name = f"class_{cls}"
                            if hasattr(result, 'names') and result.names:
                                class_name = result.names.get(cls, f"class_{cls}")

                            # Get bounding box coordinates
                            x1, y1, x2, y2 = box

                            # Convert corner points to world coordinates
                            # For regular boxes, convert all 4 corners
                            corners_pixel = [
                                (x1, y1),  # top-left
                                (x2, y1),  # top-right
                                (x2, y2),  # bottom-right
                                (x1, y2)  # bottom-left
                            ]

                            world_corners = []
                            if hasattr(self, 'calibration') and self.calibration.is_calibrated:
                                for corner in corners_pixel:
                                    world_point = self.calibration.pixel_to_world((corner[0], corner[1]))
                                    if world_point:
                                        world_corners.append(world_point)
                                    else:
                                        world_corners.append((corner[0], corner[1]))  # Fallback to pixel
                            else:
                                # If not calibrated, use pixel coordinates
                                world_corners = corners_pixel

                            predictions.append({
                                'bbox': box.tolist(),
                                'world_bbox': [world_corners[0][0], world_corners[0][1],
                                               world_corners[2][0], world_corners[2][1]],  # x1,y1,x2,y2 in world
                                'confidence': conf,
                                'class_id': cls,
                                'class_name': class_name,
                                'is_obb': False,
                                'world_corners': world_corners  # Store all 4 corners in world coordinates
                            })

                            # For regular boxes, convert to 4-corner format (top-left, top-right, bottom-right, bottom-left)
                            # Pixel coordinates
                            coord_string = (f"{x1:.2f}_{y1:.2f},"
                                            f"{x2:.2f}_{y1:.2f},"
                                            f"{x2:.2f}_{y2:.2f},"
                                            f"{x1:.2f}_{y2:.2f}")

                            # World coordinates
                            world_coord_string = (f"{world_corners[0][0]:.2f}_{world_corners[0][1]:.2f},"
                                                  f"{world_corners[1][0]:.2f}_{world_corners[1][1]:.2f},"
                                                  f"{world_corners[2][0]:.2f}_{world_corners[2][1]:.2f},"
                                                  f"{world_corners[3][0]:.2f}_{world_corners[3][1]:.2f}")

                            coordinate_strings.append(coord_string)
                            world_coordinate_strings.append(world_coord_string)

                            print(f"\n🔹 Regular Detection #{i + 1}:")
                            print(f"   Class: {class_name} (ID: {cls})")
                            print(f"   Confidence: {conf:.3f}")
                            print(f"   Pixel Coordinates: {coord_string}")
                            print(f"   World Coordinates: {world_coord_string}")

                        except Exception as e:
                            print(f"Error processing detection {i}: {e}")
                            continue

                    # Print summary
                    print(f"\n{'=' * 60}")
                    print(f"✅ TOTAL DETECTIONS: {len(predictions)}")
                    if class_filter is not None:
                        class_names = self.current_model.names if hasattr(self.current_model, 'names') else {}
                        class_name = class_names.get(class_filter, f"class_{class_filter}")
                        print(f"🎯 FILTERED CLASS: {class_filter} ({class_name})")

                    # Show calibration status
                    if hasattr(self, 'calibration') and self.calibration.is_calibrated:
                        print(f"📐 Calibration: Active - Using world coordinates")
                    else:
                        print(f"📐 Calibration: Inactive - Using pixel coordinates")
                    print(f"{'=' * 60}\n")

                # Send coordinates to server via TCP/IP
                if world_coordinate_strings:  # Prefer sending world coordinates if available
                    server_ip = self.host_edit.text().strip()
                    server_port = self.port_spin.value()

                    # Validate inputs
                    if not server_ip:
                        print("❌ No server IP address specified")
                        return

                    try:
                        # Create socket connection
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(5)  # 5 second timeout

                        print(f"\n📡 Connecting to server {server_ip}:{server_port}...")
                        sock.connect((server_ip, server_port))

                        message = "\n".join(world_coordinate_strings) + "\n"

                        # Send data
                        sock.sendall(message.encode('utf-8'))
                        print(
                            f"✅ Sent {len(world_coordinate_strings)} coordinate sets to server")

                        # Optionally receive response
                        try:
                            response = sock.recv(1024)
                            print(f"📨 Server response: {response.decode('utf-8').strip()}")
                        except:
                            print("⚠️ No response from server")

                        sock.close()

                    except socket.timeout:
                        print(f"❌ Connection timeout to {server_ip}:{server_port}")
                    except socket.error as e:
                        print(f"❌ Socket error: {e}")
                    except Exception as e:
                        print(f"❌ Error sending to server: {e}")
                else:
                    print("\n⚠️ No coordinates to send to server")

                # Save results
                output_dir = os.path.join(os.path.dirname(image_path), "predictions")
                os.makedirs(output_dir, exist_ok=True)

                output_filename = f"pred_{os.path.basename(image_path)}"
                output_path = os.path.join(output_dir, output_filename)

                if results and len(results) > 0:
                    result.save(filename=output_path)
                    print(f"📁 Results saved to: {output_path}")

                    # Also save a JSON file with world coordinates
                    json_output_path = os.path.join(output_dir,
                                                    f"pred_{os.path.splitext(os.path.basename(image_path))[0]}.json")
                    with open(json_output_path, 'w') as f:
                        json.dump({
                            "image": image_path,
                            "predictions": predictions,
                            "calibration_active": hasattr(self, 'calibration') and self.calibration.is_calibrated
                        }, f, indent=2)
                    print(f"📁 JSON results saved to: {json_output_path}")

                self.prediction_signals.progress.emit(90, "Saving results...")

                # Display predictions in viewer
                self.viewer.display_predictions(predictions)

                # Show summary message
                if class_filter is not None:
                    class_names = self.current_model.names if hasattr(self.current_model, 'names') else {}
                    class_name = class_names.get(class_filter, f"class_{class_filter}")
                    message = f"Found {len(predictions)} objects of class {class_filter} ({class_name})"
                else:
                    message = f"Found {len(predictions)} objects"

                # Add calibration info to message
                if hasattr(self, 'calibration') and self.calibration.is_calibrated:
                    message += " (world coordinates sent)"

                self.prediction_signals.progress.emit(100, "Done!")
                self.prediction_signals.finished.emit(True, message, predictions)
                self.prediction_signals.image_ready.emit(output_path)

            else:
                print("\n⚠️ No detections found")
                self.prediction_signals.finished.emit(True, "No objects detected", [])

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"Prediction failed:\n{str(e)}"
            print(f"\n❌ ERROR: {error_msg}")
            print(error_details)
            self.prediction_signals.finished.emit(False, error_msg, [])
        finally:
            self.is_predicting = False

    # def predict_current_image(self):
    #     """Run inference on the current image"""
    #     if not hasattr(self, 'current_model') or self.current_model is None:
    #         QMessageBox.warning(self, "No Model Loaded",
    #                             "Please load a trained model first.")
    #         return
    #
    #     if not hasattr(self, 'image_path') or not self.image_path:
    #         QMessageBox.warning(self, "No Image",
    #                             "Please open an image first.")
    #         return
    #
    #     # Check if class filter is enabled
    #     class_filter = None
    #     if self.class_filter_checkbox.isChecked():
    #         class_filter = self.class_filter_combo.currentData()  # Store class ID as data
    #
    #     try:
    #         self.prediction_progress_dialog = QProgressDialog(
    #             "Running inference...", "Cancel", 0, 100, self
    #         )
    #         self.prediction_progress_dialog.setWindowTitle("Running Prediction")
    #         self.prediction_progress_dialog.setWindowModality(Qt.WindowModal)
    #         self.prediction_progress_dialog.setMinimumDuration(0)
    #         self.prediction_progress_dialog.canceled.connect(self.cancel_prediction)
    #
    #         self.is_predicting = True
    #
    #         thread = threading.Thread(
    #             target=self.run_prediction,
    #             args=(self.image_path,),
    #             daemon=True
    #         )
    #         thread.start()
    #
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", f"Failed to start prediction:\n{str(e)}")
    #         self.is_predicting = False
    #
    # def run_prediction(self, image_path, class_filter=None):
    #     """Run prediction on a single image with optional class filter"""
    #     try:
    #         from ultralytics import YOLO
    #         import torch
    #
    #         self.prediction_signals.progress.emit(10, "Loading model...")
    #
    #         if not hasattr(self, 'current_model') or self.current_model is None:
    #             if hasattr(self, 'current_model_path') and self.current_model_path:
    #                 self.current_model = YOLO(self.current_model_path)
    #             else:
    #                 self.prediction_signals.finished.emit(False, "No model loaded", [])
    #                 return
    #
    #         device = 'cuda' if torch.cuda.is_available() else 'cpu'
    #
    #         # Filter by class if specified
    #         if class_filter is not None:
    #             self.prediction_signals.progress.emit(30, f"Detecting class {class_filter} on {device}...")
    #         else:
    #             self.prediction_signals.progress.emit(30, f"Detecting all classes on {device}...")
    #
    #         # Add class filter to prediction parameters
    #         results = self.current_model.predict(
    #             source=image_path,
    #             conf=0.25,
    #             iou=0.45,
    #             device=device,
    #             save=False,
    #             save_txt=False,
    #             save_conf=True,
    #             show=False,
    #             verbose=False,
    #             classes=[class_filter] if class_filter is not None else None  # Add class filter
    #         )
    #
    #         self.prediction_signals.progress.emit(70, "Processing results...")
    #
    #         predictions = []
    #         if results and len(results) > 0:
    #             result = results[0]
    #
    #             if hasattr(result, 'boxes') and result.boxes is not None:
    #                 boxes = result.boxes
    #
    #                 if hasattr(boxes, 'xyxy') and boxes.xyxy is not None:
    #                     num_detections = len(boxes.xyxy)
    #                 else:
    #                     num_detections = 0
    #
    #                 for i in range(num_detections):
    #                     try:
    #                         box = boxes.xyxy[i].cpu().numpy()
    #                         conf = float(boxes.conf[i].cpu().numpy()) if boxes.conf is not None else 0.0
    #                         cls = int(boxes.cls[i].cpu().numpy()) if boxes.cls is not None else 0
    #
    #                         # Get actual class name from model
    #                         actual_class_name = ""
    #                         if hasattr(result, 'names') and result.names:
    #                             actual_class_name = result.names.get(cls, f"class_{cls}")
    #                         else:
    #                             actual_class_name = f"class_{cls}"
    #
    #                         print(f"DEBUG [run_prediction]: Class ID {cls} → '{actual_class_name}'")  # ADD THIS LINE
    #
    #                         predictions.append({
    #                             'bbox': box.tolist(),
    #                             'confidence': conf,
    #                             'class_id': cls,
    #                             'class_name': actual_class_name,  # Use actual name
    #                             'class_name_original': actual_class_name  # Add this for clarity
    #                         })
    #                     except Exception as e:
    #                         print(f"Error processing detection {i}: {e}")
    #                         continue
    #
    #         output_dir = os.path.join(os.path.dirname(image_path), "predictions")
    #         os.makedirs(output_dir, exist_ok=True)
    #
    #         output_filename = f"pred_{os.path.basename(image_path)}"
    #         output_path = os.path.join(output_dir, output_filename)
    #
    #         if results and len(results) > 0:
    #             result.save(filename=output_path)
    #
    #         self.prediction_signals.progress.emit(90, "Saving results...")
    #
    #         self.viewer.display_predictions(predictions)
    #
    #         self.prediction_signals.progress.emit(100, "Done!")
    #         self.prediction_signals.finished.emit(True, f"Found {len(predictions)} objects", predictions)
    #         self.prediction_signals.image_ready.emit(output_path)
    #
    #     except Exception as e:
    #         import traceback
    #         error_details = traceback.format_exc()
    #         error_msg = f"Prediction failed:\n{str(e)}"
    #         print(error_details)
    #         self.prediction_signals.finished.emit(False, error_msg, [])
    #     finally:
    #         self.is_predicting = False

    def on_prediction_progress(self, progress, status):
        """Update prediction progress dialog"""
        dialog = self.prediction_progress_dialog
        if dialog is None:
            return  # dialog already closed

        try:
            dialog.setValue(progress)
            dialog.setLabelText(status)
            self.status_label.setText(f"Prediction: {status}")
        except RuntimeError:
            # Dialog was deleted by Qt
            pass

    def on_prediction_finished(self, success, message, predictions):
        """Handle prediction completion"""
        self.is_predicting = False

        dialog = self.prediction_progress_dialog
        if dialog:
            try:
                dialog.close()
            except RuntimeError:
                pass
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

    def capture_from_camera(self):
        """Capture from camera and save to Capture Image folder"""
        # Always use this specific path
        self.capture_folder = self.capture_image_path

        self.save_current()

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
        # 🚨 Check model FIRST
        if not hasattr(self, 'current_model') or self.current_model is None:
            QMessageBox.warning(
                self,
                "No Model Loaded",
                "No model is loaded.\n\n"
                "Please load a trained YOLO model before using Capture & Predict."
            )
            return

        self.save_current()

        # Ask which class to detect
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QPushButton, QButtonGroup

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Detection Mode")
        dialog.setModal(True)

        layout = QVBoxLayout()

        # Get class names from model
        class_names = {}
        if hasattr(self.current_model, 'names'):
            class_names = self.current_model.names

        layout.addWidget(QLabel("Select detection mode:"))

        # Create radio buttons
        all_classes_radio = QRadioButton("Detect All Classes")
        all_classes_radio.setChecked(True)
        layout.addWidget(all_classes_radio)

        # Add radio buttons for each class
        class_radios = {}
        button_group = QButtonGroup()

        if class_names:
            layout.addWidget(QLabel("\nOr detect specific class:"))
            for class_id, class_name in sorted(class_names.items()):
                radio = QRadioButton(f"Class {class_id}: {class_name}")
                class_radios[class_id] = radio
                button_group.addButton(radio)
                layout.addWidget(radio)

        # Buttons
        button_box = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")

        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)

        button_box.addWidget(ok_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)

        dialog.setLayout(layout)

        if dialog.exec() != QDialog.Accepted:
            return

        # Determine which class to detect
        self.selected_class_for_prediction = None  # Reset
        if not all_classes_radio.isChecked():
            for class_id, radio in class_radios.items():
                if radio.isChecked():
                    self.selected_class_for_prediction = class_id
                    break

        print(f"DEBUG: Will detect class: {self.selected_class_for_prediction}")

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

        if success and image_path and os.path.exists(image_path):
            if image_path not in self.image_files:
                self.image_files.append(image_path)
                self.image_files.sort()

            self.current_index = self.image_files.index(image_path)
            self.load_current_image()

            # Auto-run prediction with selected class
            # You'll need to store the selected_class somewhere
            # Or pass it through the signal
            # Auto-run prediction with class filter
            QTimer.singleShot(500, self.predict_current_image_with_filter)

        else:
            QMessageBox.critical(
                self,
                "Capture Failed",
                f"Camera capture failed!\n{message}"
            )

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

        # Load existing annotations for all images
        self.load_all_existing_annotations()

        # Update status
        self.status_label.setText(f"Loaded {len(self.image_files)} images from Capture Image folder")

    def load_all_existing_annotations(self):
        """Load all existing YOLO annotations into memory"""
        print("Loading existing annotations...")
        for image_path in self.image_files:
            # Check if YOLO annotation file exists
            yolo_path = os.path.splitext(image_path)[0] + ".txt"
            if os.path.exists(yolo_path):
                try:
                    # Load image to get dimensions
                    from PIL import Image
                    img = Image.open(image_path)
                    img_width, img_height = img.size

                    boxes = []
                    with open(yolo_path, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                class_id = int(parts[0])
                                x_center = float(parts[1])
                                y_center = float(parts[2])
                                width = float(parts[3])
                                height = float(parts[4])

                                # Convert YOLO format to pixel coordinates
                                x1 = (x_center - width / 2) * img_width
                                y1 = (y_center - height / 2) * img_height
                                x2 = (x_center + width / 2) * img_width
                                y2 = (y_center + height / 2) * img_height

                                # Create QRectF
                                rect = QRectF(x1, y1, x2 - x1, y2 - y1)

                                # Store label (use class_id as label)
                                label = str(class_id)

                                boxes.append((rect, label))

                    if boxes:
                        self.image_boxes[image_path] = boxes
                        print(f"  Loaded {len(boxes)} boxes from {os.path.basename(yolo_path)}")

                except Exception as e:
                    print(f"Error loading annotation for {image_path}: {e}")

        print(f"✓ Total images with annotations: {len(self.image_boxes)}")

    def load_current_image(self):
        """Load the current image into the viewer"""
        path = self.image_files[self.current_index]
        self.viewer.boxes.clear()
        self.viewer.load_image(path)
        self.image_path = path

        if path in self.image_boxes:
            self.viewer.boxes = self.image_boxes[path].copy()

        self.setWindowTitle(
            f"BMP Annotation Tool – {os.path.basename(path)} "
            f"({self.current_index + 1}/{len(self.image_files)})"
        )

        # Update image info label
        self.image_info_label.setText(f"{os.path.basename(path)} ({self.current_index + 1}/{len(self.image_files)})")

        self.image_info_label.setText(f"{os.path.basename(path)} ({self.current_index + 1}/{len(self.image_files)})")

        # Force update
        self.viewer.update()

    def next_image(self):
        """Navigate to next image"""
        if self.current_index < 0:
            return
        self.save_current()  # This saves boxes
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_current_image()

    def prev_image(self):
        """Navigate to previous image"""
        if self.current_index < 0:
            return
        self.save_current()  # This saves boxes
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
            if hasattr(self.viewer, 'boxes'):
                self.image_boxes[self.image_path] = self.viewer.boxes.copy()

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

    def load_calibration(self):
        """Load calibration from file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Calibration File",
            "", "JSON Files (*.json)"
        )

        if filepath:
            success, message = self.calibration.load_calibration(filepath)
            if success:
                # Update UI
                if hasattr(self, 'calibration_progress'):
                    self.calibration_progress.setValue(len(self.calibration.pixel_points))
                    self.calibration_progress.setVisible(True)

                if hasattr(self, 'calibration_status'):
                    self.calibration_status.setText(f"Calibration loaded - {len(self.calibration.pixel_points)} points")

                if hasattr(self, 'save_calibration_btn'):
                    self.save_calibration_btn.setEnabled(True)

                # Clear and re-add points to image (assuming viewer has these methods)
                if hasattr(self.viewer, 'clear_calibration_points'):
                    self.viewer.clear_calibration_points()

                for i, (pixel, world) in enumerate(zip(self.calibration.pixel_points, self.calibration.world_points)):
                    if hasattr(self.viewer, 'add_calibration_point'):
                        self.viewer.add_calibration_point(
                            pixel[0], pixel[1], world[0], world[1]
                        )

                self.update_tcp_messages(f"[Calibration] 📂 Loaded: {filepath}")
                QMessageBox.information(self, "Calibration Loaded", message)
            else:
                QMessageBox.warning(self, "Load Failed", message)

    def save_calibration(self):
        """Save calibration to file"""
        if not hasattr(self.viewer, 'calibration_points') or not self.viewer.calibration_points:
            QMessageBox.warning(self, "No Calibration Points",
                                "No calibration points to save.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration File",
            "", "JSON Files (*.json)"
        )

        if filepath:
            try:
                # Collect points from viewer
                pixel_points = []
                world_points = []

                for point in self.viewer.calibration_points:
                    pixel_points.append([point.pixel_x, point.pixel_y])
                    world_points.append([point.world_x, point.world_y])

                data = {
                    'pixel_points': pixel_points,
                    'world_points': world_points,
                    'timestamp': datetime.now().isoformat()
                }

                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)

                self.update_tcp_messages(f"[Calibration] 💾 Saved: {filepath}")
                QMessageBox.information(self, "Calibration Saved",
                                        f"Saved {len(pixel_points)} calibration points")

            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Error saving calibration: {str(e)}")
class Calibration:
    """Handles camera calibration data and transformations"""

    def __init__(self):
        self.pixel_points = []  # List of (x, y) pixel coordinates
        self.world_points = []  # List of (x, y) world coordinates
        self.calibration_matrix = None
        self.is_calibrated = False
        self.calibration_file = None

    def add_point_pair(self, pixel_point, world_point):
        """Add a pixel-world coordinate pair"""
        self.pixel_points.append(pixel_point)
        self.world_points.append(world_point)

    def perform_calibration(self):
        """Perform perspective transformation calibration"""
        if len(self.pixel_points) < 4:
            return False, "Need at least 4 points for calibration"

        try:
            # Convert to numpy arrays
            src = np.array(self.pixel_points, dtype=np.float32)
            dst = np.array(self.world_points, dtype=np.float32)

            # Calculate homography matrix (perspective transformation)
            self.calibration_matrix, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)

            if self.calibration_matrix is not None:
                self.is_calibrated = True
                return True, "Calibration successful"
            else:
                return False, "Failed to calculate calibration matrix"

        except Exception as e:
            return False, f"Calibration error: {str(e)}"

    def pixel_to_world(self, pixel_point):
        """Convert pixel coordinates to world coordinates"""
        if not self.is_calibrated or self.calibration_matrix is None:
            return None

        try:
            # Convert single point
            pixel_array = np.array([[pixel_point[0], pixel_point[1]]], dtype=np.float32)
            world_array = cv2.perspectiveTransform(pixel_array.reshape(-1, 1, 2),
                                                   self.calibration_matrix)
            world_point = world_array[0][0]
            return (float(world_point[0]), float(world_point[1]))
        except Exception as e:
            print(f"Conversion error: {e}")
            return None

    def save_calibration(self, filepath):
        """Save calibration data to JSON file"""
        if not self.is_calibrated:
            return False, "Not calibrated"

        try:
            calibration_data = {
                'calibration_matrix': self.calibration_matrix.tolist(),
                'pixel_points': self.pixel_points,
                'world_points': self.world_points,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }

            with open(filepath, 'w') as f:
                json.dump(calibration_data, f, indent=2)

            self.calibration_file = filepath
            return True, f"Calibration saved to {filepath}"

        except Exception as e:
            return False, f"Failed to save calibration: {str(e)}"

    def load_calibration(self, filepath):
        """Load calibration data from JSON file"""
        try:
            with open(filepath, 'r') as f:
                calibration_data = json.load(f)

            self.calibration_matrix = np.array(calibration_data['calibration_matrix'])
            self.pixel_points = calibration_data['pixel_points']
            self.world_points = calibration_data['world_points']
            self.is_calibrated = True
            self.calibration_file = filepath

            return True, f"Calibration loaded from {filepath}"

        except Exception as e:
            return False, f"Failed to load calibration: {str(e)}"

    def get_calibration_status(self):
        """Get calibration status information"""
        return {
            'is_calibrated': self.is_calibrated,
            'num_points': len(self.pixel_points),
            'calibration_file': self.calibration_file
        }


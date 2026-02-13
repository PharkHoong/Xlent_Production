import os
import threading
import socket
import time
import json
import numpy as np
from scipy.spatial.transform import Rotation
import cv2

from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QWidget,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox, QLabel,
    QLineEdit, QSpinBox, QFormLayout, QGroupBox,
    QTextEdit, QScrollArea, QProgressBar
)
from PySide6.QtCore import Signal, QObject, Qt, QTimer, QPoint
from PySide6.QtGui import QPixmap, QFont, QMouseEvent, QPainter, QPen, QColor, QTextCursor

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


class TCPClientSignals(QObject):
    """Signals for TCP client communication"""
    connection_status = Signal(str, bool)  # message, is_connected
    message_received = Signal(str)  # received message
    message_sent = Signal(str)  # sent message


class ClickableImageLabel(QLabel):
    """Custom QLabel that emits click events with pixel coordinates"""
    clicked = Signal(QPoint, float)  # image_point, scale_factor

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.scaled_pixmap = None
        self.scale_factor = 1.0
        self.click_points = []  # Store click points for drawing
        self.world_points = []  # Store corresponding world coordinates
        self.show_click_points = True
        self.click_radius = 5

    def setPixmap(self, pixmap):
        """Override setPixmap to store original image"""
        self.original_pixmap = pixmap
        self.update_scaled_pixmap()

    def update_scaled_pixmap(self):
        """Update the scaled pixmap based on current label size"""
        if self.original_pixmap and not self.original_pixmap.isNull():
            # Scale the image to fit the label while maintaining aspect ratio
            self.scaled_pixmap = self.original_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # Calculate scale factor
            if self.original_pixmap.width() > 0:
                self.scale_factor = self.scaled_pixmap.width() / self.original_pixmap.width()

            super().setPixmap(self.scaled_pixmap)

    def resizeEvent(self, event):
        """Handle resize events"""
        self.update_scaled_pixmap()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse click events"""
        if event.button() == Qt.LeftButton:
            # Get click position relative to the label
            label_point = event.position().toPoint()

            # Calculate image dimensions and position within label
            if self.scaled_pixmap and not self.scaled_pixmap.isNull():
                # Calculate image position within label (centered)
                img_width = self.scaled_pixmap.width()
                img_height = self.scaled_pixmap.height()
                img_x = (self.width() - img_width) // 2
                img_y = (self.height() - img_height) // 2

                # Check if click is within the image area
                if (img_x <= label_point.x() <= img_x + img_width and
                        img_y <= label_point.y() <= img_y + img_height):

                    # Calculate position relative to the scaled image
                    scaled_x = label_point.x() - img_x
                    scaled_y = label_point.y() - img_y

                    # Calculate original image coordinates
                    if self.scale_factor > 0:
                        original_x = int(scaled_x / self.scale_factor)
                        original_y = int(scaled_y / self.scale_factor)

                        # Emit signal with coordinates
                        self.clicked.emit(
                            QPoint(original_x, original_y),  # Original image coordinates
                            self.scale_factor  # Scale factor
                        )

        super().mousePressEvent(event)

    def paintEvent(self, event):
        """Override paint event to draw click points"""
        super().paintEvent(event)

        if self.show_click_points and self.click_points:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            # Calculate image position within label (centered)
            if self.scaled_pixmap and not self.scaled_pixmap.isNull():
                img_width = self.scaled_pixmap.width()
                img_height = self.scaled_pixmap.height()
                img_x = (self.width() - img_width) // 2
                img_y = (self.height() - img_height) // 2

                # Draw each click point
                for i, (point, world_point) in enumerate(zip(self.click_points, self.world_points)):
                    scaled_x, scaled_y, original_x, original_y = point

                    # Draw crosshair
                    color = QColor(0, 255, 0) if i < len(self.click_points) - 1 else QColor(255, 0, 0)
                    painter.setPen(QPen(color, 2))
                    # Horizontal line
                    painter.drawLine(
                        int(img_x + scaled_x - self.click_radius),
                        int(img_y + scaled_y),
                        int(img_x + scaled_x + self.click_radius),
                        int(img_y + scaled_y)
                    )
                    # Vertical line
                    painter.drawLine(
                        int(img_x + scaled_x),
                        int(img_y + scaled_y - self.click_radius),
                        int(img_x + scaled_x),
                        int(img_y + scaled_y + self.click_radius)
                    )

                    # Draw point
                    painter.setPen(QPen(QColor(0, 0, 255), 3))
                    painter.drawPoint(int(img_x + scaled_x), int(img_y + scaled_y))

                    # Draw coordinate text with index
                    painter.setPen(QPen(QColor(0, 0, 0), 1))
                    painter.setFont(QFont("Arial", 9, QFont.Bold))
                    coord_text = f"{i + 1}:({original_x},{original_y})"
                    if world_point:
                        world_x, world_y = world_point
                        coord_text += f"\n({world_x:.1f},{world_y:.1f})"

                    text_width = painter.fontMetrics().horizontalAdvance(f"{i + 1}:({original_x},{original_y})")
                    painter.drawText(
                        int(img_x + scaled_x - text_width // 2),
                        int(img_y + scaled_y - self.click_radius - 15),
                        coord_text
                    )

    def add_calibration_point(self, scaled_x, scaled_y, original_x, original_y, world_x=None, world_y=None):
        """Add a calibration point with optional world coordinates"""
        self.click_points.append((scaled_x, scaled_y, original_x, original_y))
        self.world_points.append((world_x, world_y) if world_x is not None else (None, None))
        self.update()

    def clear_points(self):
        """Clear all click points"""
        self.click_points.clear()
        self.world_points.clear()
        self.update()


class CalibrationData:
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.capture_folder = None  # Will store the folder chosen by the user
        self.current_image_path = None  # Store current image path

        self.setWindowTitle("Camera Capture Tool with TCP/IP & Calibration")
        self.resize(1100, 850)

        # Initialize signals
        self.camera_signals = CameraSignals()
        self.camera_signals.finished.connect(self.on_camera_finished)

        self.tcp_signals = TCPClientSignals()
        self.tcp_signals.connection_status.connect(self.on_tcp_connection_status)
        self.tcp_signals.message_received.connect(self.on_tcp_message_received)
        self.tcp_signals.message_sent.connect(self.on_tcp_message_sent)

        # TCP Connection variables
        self.tcp_socket = None
        self.is_connected = False
        self.tcp_thread = None
        self.listening_thread = None

        # Calibration variables
        self.calibration = CalibrationData()
        self.calibration_points_needed = 9
        self.current_calibration_point = 0
        self.pending_world_coords = None
        self.stored_coordinates = []  # Store all received coordinates with their point indices
        self.calibration_active = False  # Flag to indicate calibration is in progress

        # Camera capture variables
        self.camera_capturing = False
        self.auto_capture_enabled = True  # Auto capture when receiving coordinates

        # ---------- Calibration Controls ----------
        self.calibration_group = QGroupBox("Calibration Settings")

        self.calibration_progress = QProgressBar()
        self.calibration_progress.setRange(0, self.calibration_points_needed)
        self.calibration_progress.setValue(0)
        self.calibration_progress.setTextVisible(True)
        self.calibration_progress.setFormat("Calibration points: %v/%m")

        self.calibration_status = QLabel("Not calibrated - 0/9 points")
        self.calibration_status.setStyleSheet("color: #666; font-weight: bold;")

        calibration_buttons = QHBoxLayout()

        self.save_calibration_btn = QPushButton("💾 Save Calibration")
        self.save_calibration_btn.clicked.connect(self.save_calibration)
        self.save_calibration_btn.setEnabled(False)
        self.save_calibration_btn.setStyleSheet("background-color: #4CAF50; color: white;")

        self.load_calibration_btn = QPushButton("📂 Load Calibration")
        self.load_calibration_btn.clicked.connect(self.load_calibration)
        self.load_calibration_btn.setStyleSheet("background-color: #2196F3; color: white;")

        self.clear_calibration_btn = QPushButton("🗑️ Clear Calibration")
        self.clear_calibration_btn.clicked.connect(self.clear_calibration)
        self.clear_calibration_btn.setStyleSheet("background-color: #f44336; color: white;")

        calibration_buttons.addWidget(self.save_calibration_btn)
        calibration_buttons.addWidget(self.load_calibration_btn)
        calibration_buttons.addWidget(self.clear_calibration_btn)
        calibration_buttons.addStretch()

        calibration_layout = QVBoxLayout()
        calibration_layout.addWidget(self.calibration_progress)
        calibration_layout.addWidget(self.calibration_status)
        calibration_layout.addLayout(calibration_buttons)
        self.calibration_group.setLayout(calibration_layout)

        # ---------- Coordinate Display ----------
        self.coord_group = QGroupBox("Coordinates")
        self.coord_group.setMaximumHeight(100)

        self.pixel_coord_label = QLabel("Pixel: (?, ?)")
        self.pixel_coord_label.setStyleSheet("color: #2196F3; font-weight: bold;")

        self.world_coord_label = QLabel("World: (?, ?)")
        self.world_coord_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

        self.calibration_point_label = QLabel("Calibration point: 0/9")
        self.calibration_point_label.setStyleSheet("color: #FF9800; font-style: italic;")

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(self.pixel_coord_label)
        coord_layout.addWidget(self.world_coord_label)
        coord_layout.addStretch()
        coord_layout.addWidget(self.calibration_point_label)

        self.coord_group.setLayout(coord_layout)

        # ---------- TCP Connection Settings ----------
        self.tcp_group = QGroupBox("TCP/IP Connection Settings")

        self.host_edit = QLineEdit("192.168.1.100")
        self.host_edit.setPlaceholderText("Enter host IP address")

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(8888)

        self.connect_btn = QPushButton("🔌 Connect")
        self.connect_btn.clicked.connect(self.toggle_tcp_connection)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        # Connection status label
        self.connection_status_label = QLabel("Status: Disconnected")
        self.connection_status_label.setStyleSheet("color: #666; font-style: italic;")

        # TCP settings layout
        tcp_form = QFormLayout()
        tcp_form.addRow("Host:", self.host_edit)
        tcp_form.addRow("Port:", self.port_spin)

        tcp_buttons = QHBoxLayout()
        tcp_buttons.addWidget(self.connect_btn)
        tcp_buttons.addStretch()

        tcp_layout = QVBoxLayout()
        tcp_layout.addLayout(tcp_form)
        tcp_layout.addLayout(tcp_buttons)
        tcp_layout.addWidget(self.connection_status_label)
        self.tcp_group.setLayout(tcp_layout)

        # ---------- Image Display Label ----------
        self.image_label = ClickableImageLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("Waiting for coordinates to capture image...")
        self.image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 5px;
                background-color: #f5f5f5;
                min-height: 400px;
            }
        """)
        self.image_label.clicked.connect(self.on_image_clicked)

        # ---------- Image Info Label ----------
        self.image_info_label = QLabel("")
        self.image_info_label.setAlignment(Qt.AlignCenter)
        self.image_info_label.setStyleSheet("color: #666; font-size: 12px;")

        # ---------- Status Bar ----------
        self.status_label = QLabel("Ready - Connect to server to start")
        self.statusBar().addWidget(self.status_label)

        # ---------- TCP Messages Display (Scrollable) ----------
        self.tcp_messages_group = QGroupBox("TCP Messages & Calibration Log")

        # Create scroll area for messages
        self.tcp_messages_scroll = QScrollArea()
        self.tcp_messages_scroll.setWidgetResizable(True)
        self.tcp_messages_scroll.setMinimumHeight(150)
        self.tcp_messages_scroll.setMaximumHeight(250)

        # Create text edit for messages with scrollbars
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

        # Set the text edit as the scroll area's widget
        self.tcp_messages_scroll.setWidget(self.tcp_messages_display)

        # Clear messages button
        self.clear_messages_btn = QPushButton("🗑️ Clear Messages")
        self.clear_messages_btn.clicked.connect(self.clear_tcp_messages)
        self.clear_messages_btn.setMaximumWidth(150)

        tcp_messages_layout = QVBoxLayout()
        tcp_messages_layout.addWidget(self.tcp_messages_scroll)

        messages_footer = QHBoxLayout()
        messages_footer.addStretch()
        messages_footer.addWidget(self.clear_messages_btn)

        tcp_messages_layout.addLayout(messages_footer)
        self.tcp_messages_group.setLayout(tcp_messages_layout)

        # ---------- Layout ----------
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tcp_group)
        main_layout.addWidget(self.calibration_group)
        main_layout.addWidget(self.coord_group)
        main_layout.addWidget(self.image_label, 1)  # Expand image area
        main_layout.addWidget(self.image_info_label)
        main_layout.addWidget(self.tcp_messages_group)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Ask for capture folder at startup
        self.select_capture_folder()

    def select_capture_folder(self):
        """Select folder to save captured images"""
        if self.capture_folder is None:
            folder = QFileDialog.getExistingDirectory(
                self,
                "Select Folder to Save Captured Images"
            )
            if folder:
                self.capture_folder = folder
                self.status_label.setText(f"Images will be saved to: {os.path.basename(folder)}")
                self.update_tcp_messages(f"[System] 📁 Capture folder selected: {folder}")
            else:
                # If no folder selected, try again or use default
                self.capture_folder = os.path.join(os.path.expanduser("~"), "Pictures", "CameraCaptures")
                os.makedirs(self.capture_folder, exist_ok=True)
                self.status_label.setText(f"Using default folder: {os.path.basename(self.capture_folder)}")
                self.update_tcp_messages(f"[System] 📁 Using default capture folder: {self.capture_folder}")

    # ---------- Camera Capture Methods ----------
    def capture_from_camera(self):
        """Start camera capture in a separate thread"""
        if self.camera_capturing:
            return

        if self.capture_folder is None:
            self.select_capture_folder()
            if self.capture_folder is None:
                return

        self.camera_capturing = True
        self.status_label.setText("Capturing image...")
        self.image_label.setText("Capturing image...\nPlease wait")
        self.image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 5px;
                background-color: #f5f5f5;
                min-height: 400px;
                font-size: 16px;
                color: #666;
            }
        """)
        self.image_info_label.setText("")

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
                self.camera_capturing = False

            # Call the camera capture function
            if CAMERA_AVAILABLE:
                AutoCaptureFlow(callback=callback)
            else:
                self.camera_signals.finished.emit(False, "Camera module not available", None)
                self.camera_capturing = False

        thread = threading.Thread(target=run_capture, daemon=True)
        thread.start()

    def display_image(self, image_path):
        """Display the captured image in the GUI"""
        self.current_image_path = image_path

        if not os.path.exists(image_path):
            self.image_label.setText("Error: Image file not found")
            self.image_label.setStyleSheet("""
                QLabel {
                    border: 2px dashed #f00;
                    border-radius: 5px;
                    background-color: #ffe6e6;
                    min-height: 400px;
                    font-size: 16px;
                    color: #c00;
                }
            """)
            self.image_info_label.setText("")
            return

        # Load and display the image
        pixmap = QPixmap(image_path)

        if pixmap.isNull():
            self.image_label.setText("Error: Cannot load image")
            self.image_label.setStyleSheet("""
                QLabel {
                    border: 2px dashed #f00;
                    border-radius: 5px;
                    background-color: #ffe6e6;
                    min-height: 400px;
                    font-size: 16px;
                    color: #c00;
                }
            """)
            self.image_info_label.setText("")
            return

        # Set the pixmap on our custom label
        self.image_label.setPixmap(pixmap)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 2px solid #4CAF50;
                border-radius: 5px;
                background-color: #f0f0f0;
                min-height: 400px;
            }
        """)

        # Update image info
        file_size = os.path.getsize(image_path) / 1024  # Convert to KB
        dimensions = f"{pixmap.width()} x {pixmap.height()}"

        if self.calibration.is_calibrated:
            info_text = f"{os.path.basename(image_path)} | {dimensions} | Calibrated | Click to convert pixel→world"
        else:
            info_text = f"{os.path.basename(image_path)} | {dimensions} | Not calibrated | Click points to calibrate"

        self.image_info_label.setText(info_text)

        # Log image load
        timestamp = time.strftime("%H:%M:%S")
        self.update_tcp_messages(f"[{timestamp}] 📸 Captured image: {os.path.basename(image_path)}")

    def on_camera_finished(self, success, message, image_path):
        """Handle camera capture completion"""
        if success and image_path:
            # Display the captured image
            self.display_image(image_path)
            self.status_label.setText(f"Image saved: {os.path.basename(image_path)}")

            # Log success
            timestamp = time.strftime("%H:%M:%S")
            self.update_tcp_messages(f"[{timestamp}] ✅ Image captured successfully")
        else:
            # Show error state
            self.image_label.setText("Capture Failed")
            self.image_label.setStyleSheet("""
                QLabel {
                    border: 2px dashed #f00;
                    border-radius: 5px;
                    background-color: #ffe6e6;
                    min-height: 400px;
                    font-size: 16px;
                    color: #c00;
                }
            """)
            self.image_info_label.setText("")
            self.status_label.setText("Capture failed")

            # Log error
            timestamp = time.strftime("%H:%M:%S")
            self.update_tcp_messages(f"[{timestamp}] ❌ Capture failed: {message}")

    # ---------- Calibration Methods ----------
    def start_calibration(self):
        """Start calibration process automatically"""
        self.calibration_active = True
        self.calibration_status.setText("Calibration in progress - Click 9 points")
        self.update_tcp_messages("[Calibration] 🎯 Calibration started - Click 9 points on the image")

        # Check if we already have stored coordinates for point 1
        next_point = self.current_calibration_point + 1
        coordinate_found = False

        for stored in self.stored_coordinates:
            if stored['index'] == next_point:
                self.pending_world_coords = stored['coords']
                self.update_tcp_messages(
                    f"[Calibration] 📦 Using stored coordinate for point {next_point}: "
                    f"({stored['coords'][0]}, {stored['coords'][1]}) - Click on image to bind")
                coordinate_found = True
                break

        # If no stored coordinate found, send C1_START
        if not coordinate_found:
            try:
                self.tcp_socket.sendall("C1_START".encode('utf-8'))
                self.tcp_signals.message_sent.emit("C1_START")
                self.update_tcp_messages("[Calibration] 🔵 Sent 'C1_START' - Waiting for world coordinate...")
            except socket.error as e:
                self.update_tcp_messages(f"Error sending C1_START: {str(e)}")

    def add_calibration_point(self, pixel_point, world_point):
        """Add a calibration point pair"""
        # Convert QPoint to tuple
        pixel_tuple = (pixel_point.x(), pixel_point.y())
        world_tuple = world_point

        # Add to calibration data
        self.calibration.add_point_pair(pixel_tuple, world_tuple)

        # Update progress
        self.current_calibration_point += 1
        self.calibration_progress.setValue(self.current_calibration_point)
        self.calibration_point_label.setText(f"Calibration point: {self.current_calibration_point}/9")

        # Update status
        if self.current_calibration_point >= self.calibration_points_needed:
            self.calibration_status.setText("Calibration complete - Performing calibration...")
            self.perform_calibration_calculation()
        else:
            self.calibration_status.setText(f"Calibration - {self.current_calibration_point}/9 points")

        # Add point to image display
        self.image_label.add_calibration_point(
            pixel_point.x() * self.image_label.scale_factor,
            pixel_point.y() * self.image_label.scale_factor,
            pixel_point.x(),
            pixel_point.y(),
            world_tuple[0],
            world_tuple[1]
        )

        return self.current_calibration_point

    def perform_calibration_calculation(self):
        """Perform the actual calibration calculation"""
        success, message = self.calibration.perform_calibration()

        if success:
            self.calibration_status.setText("Calibration successful! Save calibration file.")
            self.save_calibration_btn.setEnabled(True)
            self.calibration_active = False

            # Test calibration with first point
            test_pixel = self.calibration.pixel_points[0]
            test_world = self.calibration.pixel_to_world(test_pixel)

            self.update_tcp_messages(f"[Calibration] ✅ Calibration successful!")
            self.update_tcp_messages(f"[Calibration] Test: Pixel {test_pixel} → World {test_world}")

            QMessageBox.information(self, "Calibration Successful",
                                    f"Calibration completed successfully!\n\n"
                                    f"Click 'Save Calibration' to save the calibration file.")
        else:
            self.calibration_status.setText(f"Calibration failed: {message}")
            self.calibration_active = False

            self.update_tcp_messages(f"[Calibration] ❌ Calibration failed: {message}")
            QMessageBox.warning(self, "Calibration Failed", message)

    def save_calibration(self):
        """Save calibration to file"""
        if not self.calibration.is_calibrated:
            QMessageBox.warning(self, "Not Calibrated", "Please perform calibration first")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration File",
            "calibration.json",
            "JSON Files (*.json)"
        )

        if filepath:
            success, message = self.calibration.save_calibration(filepath)
            if success:
                self.update_tcp_messages(f"[Calibration] 💾 Saved: {filepath}")
                QMessageBox.information(self, "Calibration Saved", message)
            else:
                QMessageBox.warning(self, "Save Failed", message)

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
                self.calibration_progress.setValue(len(self.calibration.pixel_points))
                self.calibration_status.setText(f"Calibration loaded - {len(self.calibration.pixel_points)} points")
                self.save_calibration_btn.setEnabled(True)

                # Clear and re-add points to image
                self.image_label.clear_points()
                for i, (pixel, world) in enumerate(zip(self.calibration.pixel_points, self.calibration.world_points)):
                    self.image_label.add_calibration_point(
                        pixel[0] * self.image_label.scale_factor,
                        pixel[1] * self.image_label.scale_factor,
                        pixel[0],
                        pixel[1],
                        world[0],
                        world[1]
                    )

                self.update_tcp_messages(f"[Calibration] 📂 Loaded: {filepath}")
                QMessageBox.information(self, "Calibration Loaded", message)
            else:
                QMessageBox.warning(self, "Load Failed", message)

    def clear_calibration(self):
        """Clear all calibration data"""
        reply = QMessageBox.question(
            self, "Clear Calibration",
            "Are you sure you want to clear all calibration data?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Send C1_CANCEL to server to abort calibration
            if self.is_connected and self.tcp_socket:
                try:
                    self.tcp_socket.sendall("C1_CANCEL".encode('utf-8'))
                    self.tcp_signals.message_sent.emit("C1_CANCEL")
                    self.update_tcp_messages("[Calibration] 🛑 Sent 'C1_CANCEL' to abort calibration on server")
                except socket.error as e:
                    self.update_tcp_messages(f"Error sending C1_CANCEL: {str(e)}")

            self.calibration = CalibrationData()
            self.image_label.clear_points()
            self.calibration_progress.setValue(0)
            self.calibration_status.setText("Not calibrated - 0/9 points")
            self.calibration_point_label.setText("Calibration point: 0/9")
            self.save_calibration_btn.setEnabled(False)
            self.current_calibration_point = 0
            self.pending_world_coords = None
            self.stored_coordinates = []
            self.calibration_active = False

            self.update_tcp_messages("[Calibration] 🧹 Cleared all calibration data")

    # ---------- Pixel Coordinate Methods ----------
    def on_image_clicked(self, pixel_point, scale_factor):
        """Handle image click events"""
        # Update pixel coordinates display
        self.pixel_coord_label.setText(f"Pixel: ({pixel_point.x()}, {pixel_point.y()})")

        # If calibrated, convert to world coordinates
        if self.calibration.is_calibrated:
            world_point = self.calibration.pixel_to_world((pixel_point.x(), pixel_point.y()))
            if world_point:
                self.world_coord_label.setText(f"World: ({world_point[0]:.2f}, {world_point[1]:.2f})")
                self.update_tcp_messages(
                    f"📍 Pixel ({pixel_point.x()}, {pixel_point.y()}) → World ({world_point[0]:.2f}, {world_point[1]:.2f})")
            else:
                self.world_coord_label.setText("World: Conversion failed")
        else:
            # If calibration is active and we have pending world coordinates
            if self.calibration_active and self.pending_world_coords is not None:
                # Use the pending world coordinates
                world_coords = self.pending_world_coords
                self.pending_world_coords = None

                # Add calibration point
                point_num = self.add_calibration_point(pixel_point, world_coords)
                self.update_tcp_messages(
                    f"[Calibration] Point {point_num}: Pixel ({pixel_point.x()}, {pixel_point.y()}) ↔ World ({world_coords[0]}, {world_coords[1]})")

                # Send C1_NEXT for next point if calibration not complete
                if point_num < self.calibration_points_needed:
                    # Check if we already have the next point stored
                    next_point = point_num + 1
                    next_coord_found = False

                    for stored in self.stored_coordinates:
                        if stored['index'] == next_point:
                            self.pending_world_coords = stored['coords']
                            self.update_tcp_messages(
                                f"[Calibration] 📦 Using stored coordinate for point {next_point}: "
                                f"({stored['coords'][0]}, {stored['coords'][1]}) - Click on image to bind")
                            next_coord_found = True
                            break

                    # If no stored coordinate found, send C1_NEXT
                    if not next_coord_found:
                        try:
                            self.tcp_socket.sendall("C1_NEXT".encode('utf-8'))
                            self.tcp_signals.message_sent.emit("C1_NEXT")
                            self.update_tcp_messages(
                                f"[Calibration] 🔵 Sent 'C1_NEXT', waiting for next world coordinate...")
                        except socket.error as e:
                            self.update_tcp_messages(f"Error sending C1_NEXT: {str(e)}")
                else:
                    self.update_tcp_messages("[Calibration] ✅ All 9 points collected - Performing calibration...")

            # If calibration is active but no pending coordinates
            elif self.calibration_active:
                self.update_tcp_messages(
                    f"[Calibration] Clicked at ({pixel_point.x()}, {pixel_point.y()}) but no world coordinate available")
                self.update_tcp_messages(f"[Calibration] Waiting for server to send coordinates...")
            else:
                self.world_coord_label.setText("World: Not calibrated")
                self.update_tcp_messages(f"📍 Pixel click: ({pixel_point.x()}, {pixel_point.y()})")

        self.status_label.setText(f"Clicked at pixel: ({pixel_point.x()}, {pixel_point.y()})")

    # ---------- TCP Message Processing ----------
    def process_world_coordinates(self, message):
        """Parse world coordinates from TCP message"""
        try:
            # Parse C_POINT_X_Y format
            if message.startswith('C1_POINT_'):
                parts = message.split('_')
                if len(parts) >= 5:  # C, POINT, index, X, Y
                    point_index = int(parts[2])  # Get the point number (1, 2, 3...)
                    world_x = float(parts[-2])  # Second last is X
                    world_y = float(parts[-1])  # Last is Y

                    self.update_tcp_messages(
                        f"📥 World coordinates received: ({world_x}, {world_y}) for point {point_index}")
                    return (world_x, world_y, point_index)

            # Fallback: Try to parse as "x,y" format
            elif ',' in message:
                parts = message.split(',')
                if len(parts) >= 2:
                    world_x = float(parts[0].strip())
                    world_y = float(parts[1].strip())
                    self.update_tcp_messages(f"📥 World coordinates received: ({world_x}, {world_y})")
                    return (world_x, world_y, None)

            # Fallback: Try to parse as JSON
            try:
                data = json.loads(message)
                if 'x' in data and 'y' in data:
                    world_x = float(data['x'])
                    world_y = float(data['y'])
                    self.update_tcp_messages(f"📥 World coordinates received: ({world_x}, {world_y})")
                    return (world_x, world_y, None)
            except:
                pass

            return None

        except Exception as e:
            self.update_tcp_messages(f"Error parsing world coordinates: {str(e)}")
            return None

    # ---------- TCP/IP Connection Methods ----------
    def on_tcp_message_received(self, message):
        """Handle received TCP messages"""
        timestamp = time.strftime("%H:%M:%S")

        # Check if this is a coordinate message
        result = self.process_world_coordinates(message)

        if result:
            if len(result) == 3:  # C_POINT format with index
                world_x, world_y, point_index = result
                world_coords = (world_x, world_y)

                # Store ALL coordinates with their point numbers
                self.stored_coordinates.append({
                    'index': point_index,
                    'coords': world_coords,
                    'timestamp': timestamp
                })

                # Sort stored coordinates by index
                self.stored_coordinates.sort(key=lambda x: x['index'])

                # AUTO CAPTURE CAMERA when coordinate is received
                if self.auto_capture_enabled and not self.camera_capturing and CAMERA_AVAILABLE:
                    self.capture_from_camera()

                # If calibration is active, use as pending if it's the next expected point
                if self.calibration_active:
                    next_expected_point = self.current_calibration_point + 1
                    if point_index == next_expected_point:
                        self.pending_world_coords = world_coords
                        self.update_tcp_messages(
                            f"[Calibration] 📦 Stored world coordinates ({world_coords[0]}, {world_coords[1]}) for point {point_index} - Click on image to bind")
                    else:
                        self.update_tcp_messages(
                            f"[Calibration] 📦 Received point {point_index} ({world_coords[0]}, {world_coords[1]}) - Waiting for point {next_expected_point}")
                else:
                    # Not in calibration mode, just display and automatically start calibration on first point
                    self.update_tcp_messages(
                        f"[{timestamp}] 📥 Received point {point_index}: ({world_coords[0]}, {world_coords[1]})")

                    # Automatically start calibration on first received point
                    if point_index == 1 and not self.calibration_active and not self.calibration.is_calibrated:
                        self.start_calibration()
            else:
                # Old format without index
                world_x, world_y, _ = result
                world_coords = (world_x, world_y)
                self.update_tcp_messages(
                    f"[{timestamp}] 📥 Received coordinates: ({world_coords[0]}, {world_coords[1]})")
        else:
            # Regular message
            self.update_tcp_messages(f"[{timestamp}] 📥 Received: {message}")

    def on_tcp_message_sent(self, message):
        """Handle sent TCP messages"""
        timestamp = time.strftime("%H:%M:%S")
        self.update_tcp_messages(f"[{timestamp}] 📤 Sent: {message}")

    def update_tcp_messages(self, message):
        """Update TCP messages display with scrollable text"""
        # Get current text
        current_text = self.tcp_messages_display.toPlainText()

        # Add new message
        if current_text:
            new_text = f"{message}\n{current_text}"
        else:
            new_text = message

        # Update the text edit
        self.tcp_messages_display.setPlainText(new_text)

        # Keep cursor at the beginning to show newest messages
        cursor = self.tcp_messages_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.tcp_messages_display.setTextCursor(cursor)

    def clear_tcp_messages(self):
        """Clear all TCP messages"""
        self.tcp_messages_display.clear()
        self.status_label.setText("Messages cleared")

    # ---------- TCP Connection Methods ----------
    def toggle_tcp_connection(self):
        """Toggle TCP connection on/off"""
        if self.is_connected:
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
            self.tcp_socket.settimeout(2)  # 2 second timeout

            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("Connecting...")
            self.connection_status_label.setText(f"Status: Connecting to {host}:{port}...")

            # Try to connect in a separate thread
            def connect_thread():
                try:
                    self.tcp_socket.connect((host, port))
                    self.is_connected = True
                    self.tcp_signals.connection_status.emit(f"Connected to {host}:{port}", True)

                    # Send C1_START after successful connection
                    self.tcp_socket.sendall("C1_START".encode('utf-8'))
                    self.tcp_signals.message_sent.emit("C1_START")

                    # Start listening for messages
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

        self.is_connected = False
        self.tcp_socket = None
        self.connect_btn.setText("🔌 Connect")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.connection_status_label.setText("Status: Disconnected")
        self.update_tcp_messages("[System] Disconnected from server")

        # Clear stored coordinates on disconnect
        self.stored_coordinates = []
        self.pending_world_coords = None
        self.calibration_active = False

    def start_listening(self):
        """Start listening for incoming messages in a separate thread"""

        def listen_thread():
            while self.is_connected and self.tcp_socket:
                try:
                    data = self.tcp_socket.recv(1024)
                    if data:
                        message = data.decode('utf-8').strip()
                        self.tcp_signals.message_received.emit(message)
                    else:
                        # Server closed connection
                        if self.is_connected:
                            self.tcp_signals.connection_status.emit("Server disconnected", False)
                        break
                except socket.timeout:
                    continue  # Timeout is expected, just continue listening
                except socket.error:
                    if self.is_connected:
                        self.tcp_signals.connection_status.emit("Connection lost", False)
                    break

        self.listening_thread = threading.Thread(target=listen_thread, daemon=True)
        self.listening_thread.start()

    def on_tcp_connection_status(self, message, is_connected):
        """Handle TCP connection status changes"""
        QTimer.singleShot(0, lambda: self._update_connection_status(message, is_connected))

    def _update_connection_status(self, message, is_connected):
        self.is_connected = is_connected
        self.connect_btn.setEnabled(True)

        if is_connected:
            self.connect_btn.setText("🔌 Disconnect")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    font-weight: bold;
                    padding: 5px 15px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
            """)
            self.update_tcp_messages(f"[System] Connected to server")
        else:
            self.connect_btn.setText("🔌 Connect")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 5px 15px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.update_tcp_messages(f"[System] {message}")

        self.connection_status_label.setText(f"Status: {message}")

    def closeEvent(self, event):
        """Clean up connections when closing the application"""
        if self.is_connected:
            self.disconnect_tcp()
        event.accept()
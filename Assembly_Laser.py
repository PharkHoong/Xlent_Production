import os
import random
import threading
import time
import json
import numpy as np
import cv2
from datetime import datetime
from PIL import Image
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFileDialog,
    QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton,
    QMessageBox, QLabel
)
from PySide6.QtGui import QKeySequence, QShortcut, QColor
from PySide6.QtCore import Signal, QObject, QTimer, Qt, QRectF
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
        self.capture_folder = None
        super().__init__()
        self.setWindowTitle("BMP Annotation Tool")
        self.resize(1400, 900)

        # Define base paths
        self.base_path = "C:\\Users\\SiP-PHChin\\OneDrive - SIP Technology (M) Sdn Bhd\\Desktop"
        self.capture_image_path = f"{self.base_path}\\Capture Image"
        self.labeling_path = f"{self.base_path}\\Labeling"
        self.boxes_json_path = f"{self.base_path}\\BoxesData"  # Folder for JSON files
        self.image_boxes = {}

        # Start with 0 as the first label
        self.labels = ["0"]
        self.label_counter = 0
        self.label_colors = {"0": QColor(255, 0, 0)}

        self.image_files = []
        self.current_index = -1
        self.pending_box = None  # Store the most recently drawn box waiting for confirmation
        self.pending_box_label = None  # Store the label of the pending box
        self.box_saved = False  # Flag to track if a box has been saved

        # Add calibration object
        self.calibration = Calibration()

        # Add calibration status label only (no progress bar)
        self.calibration_status = QLabel("No calibration loaded")
        self.calibration_status.setStyleSheet("color: #666; font-style: italic;")

        # Create necessary folders if they don't exist
        self.create_required_folders()

        # Initialize signals
        self.camera_signals = CameraSignals()
        self.camera_signals.finished.connect(self.on_camera_finished)

        # Add a timer to track bounding box changes
        self.box_tracker_timer = QTimer()
        self.box_tracker_timer.timeout.connect(self.track_bounding_box_changes)
        self.box_tracker_timer.start(300)  # Check every 300ms

        # Track previous box count
        self.previous_box_count = 0

        self.init_ui()

    def init_ui(self):
        """Initialize the main annotation page"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # ---------- Top Toolbar ----------
        top_bar = QHBoxLayout()

        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.clicked.connect(self.capture_from_camera)
        if not CAMERA_AVAILABLE:
            self.capture_btn.setEnabled(False)
            self.capture_btn.setToolTip("Camera module not available")

        undo_btn = QPushButton("↶ Undo")
        undo_btn.clicked.connect(self.undo)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected)

        # Add Save Box button
        self.save_box_btn = QPushButton("💾 Save Current Box")
        self.save_box_btn.clicked.connect(self.save_current_box)
        self.save_box_btn.setEnabled(False)  # Disabled initially
        self.save_box_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)

        top_bar.addWidget(self.capture_btn)
        top_bar.addWidget(undo_btn)
        top_bar.addWidget(delete_btn)
        top_bar.addWidget(self.save_box_btn)
        top_bar.addStretch()

        # ---------- Calibration Status Bar (no progress bar) ----------
        cal_status_layout = QHBoxLayout()
        cal_status_layout.addWidget(QLabel("📐 Calibration:"))
        cal_status_layout.addWidget(self.calibration_status)
        cal_status_layout.addStretch()

        # ---------- Main Content Area ----------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # ---------- Left Column: Annotation Viewer (100%) ----------
        left_column = QVBoxLayout()

        # Create AnnotationWidget
        self.viewer = AnnotationWidget(
            self.get_current_label,
            self.get_label_color
        )

        # Connect signals
        self.viewer.status_message.connect(self.on_annotation_status)

        left_column.addWidget(self.viewer, 1)

        # Image info label - WITHOUT INDEX NUMBER
        self.image_info_label = QLabel("No image loaded")
        self.image_info_label.setStyleSheet("color: #666; font-size: 12px; padding: 2px;")
        left_column.addWidget(self.image_info_label)

        content_layout.addLayout(left_column, 100)

        layout.addLayout(top_bar)
        layout.addLayout(cal_status_layout)
        layout.addLayout(content_layout)

        # ---------- Status Bar ----------
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # ---------- Shortcuts ----------
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_selected)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_current_box)

    def on_annotation_status(self, message):
        """Handle status messages from annotation widget"""
        self.status_label.setText(message)
        # Remove the OBB condition entirely or keep only TCP messages if needed
        timestamp = time.strftime("%H:%M:%S")
        self.update_tcp_messages(f"[{timestamp}] {message}")


    def create_required_folders(self):
        """Create all required folders if they don't exist"""
        folders_to_create = [
            self.capture_image_path,
            self.labeling_path,
            self.boxes_json_path,
        ]

        for folder in folders_to_create:
            try:
                os.makedirs(folder, exist_ok=True)
                print(f"Created/Verified folder: {folder}")
            except Exception as e:
                print(f"Error creating folder {folder}: {e}")

    def track_bounding_box_changes(self):
        """Track when new bounding boxes are drawn"""
        if not hasattr(self.viewer, 'boxes'):
            return

        try:
            # Count ALL boxes (regular + rotated)
            regular_count = len(self.viewer.boxes) if hasattr(self.viewer, 'boxes') else 0
            rotated_count = len(self.viewer.rotated_boxes) if hasattr(self.viewer, 'rotated_boxes') else 0
            current_count = regular_count + rotated_count

            # If more than one box total
            if current_count > 1:
                # Use the safe clear method
                self.viewer.safe_clear_boxes()

                # Reset tracking variables
                self.last_bounding_box = None
                self.last_box_label = None
                self.pending_box = None  # <-- ADD THIS
                self.pending_box_label = None  # <-- ADD THIS
                self.previous_box_count = 0

                # Disable save button
                self.save_box_btn.setEnabled(False)
                self.save_box_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #cccccc;
                        color: #666666;
                        font-weight: bold;
                        padding: 5px;
                    }
                """)

                # Show error message
                QTimer.singleShot(100, lambda: QMessageBox.critical(
                    self,
                    "Error",
                    "Only ONE bounding box allowed!\n\nAll boxes have been cleared."
                ))

                self.status_label.setText("Error: Only one box allowed. Boxes cleared.")

            else:
                # Update previous count
                self.previous_box_count = current_count

                # Store the latest box if it exists
                if current_count == 1:
                    if regular_count == 1:
                        latest_box, latest_label = self.viewer.boxes[0]

                        # Set BOTH variables
                        self.last_bounding_box = (latest_box, latest_label)
                        self.last_box_label = latest_label
                        self.pending_box = latest_box  # <-- ADD THIS
                        self.pending_box_label = latest_label  # <-- ADD THIS

                        # Enable the save button
                        self.save_box_btn.setEnabled(True)
                        self.save_box_btn.setStyleSheet("""
                            QPushButton {
                                background-color: #4CAF50;
                                color: white;
                                font-weight: bold;
                                padding: 5px;
                            }
                        """)

                    elif rotated_count == 1:
                        # Handle rotated box
                        # You need to get the rotated box data and convert/store it
                        rotated_box = self.viewer.rotated_boxes[0]
                        # For now, just set pending_box to None since save_current_box expects a rect
                        self.pending_box = None
                        self.pending_box_label = None
                        self.save_box_btn.setEnabled(False)
                else:
                    # No boxes - disable save button
                    self.save_box_btn.setEnabled(False)
                    self.pending_box = None  # <-- ADD THIS
                    self.pending_box_label = None  # <-- ADD THIS
                    self.save_box_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #cccccc;
                            color: #666666;
                            font-weight: bold;
                            padding: 5px;
                        }
                    """)

        except Exception as e:
            print(f"Error in track_bounding_box_changes: {e}")
            self.viewer.safe_clear_boxes()
            self.save_box_btn.setEnabled(False)
            self.pending_box = None  # <-- ADD THIS
            self.pending_box_label = None  # <-- ADD THIS
            self.save_box_btn.setStyleSheet("""
                QPushButton {
                    background-color: #cccccc;
                    color: #666666;
                    font-weight: bold;
                    padding: 5px;
                }
            """)

    def save_current_box(self):
        """Save the current pending bounding box to JSON file - automatically saves world coordinates"""
        if self.pending_box is None or self.pending_box_label is None:
            QMessageBox.warning(self, "No Box", "No bounding box available to save.")
            return

        if not hasattr(self, 'image_path') or not self.image_path:
            QMessageBox.warning(self, "No Image", "No image loaded.")
            return

        # Check if calibration is loaded
        if not self.calibration.is_calibrated:
            QMessageBox.warning(
                self,
                "Calibration Required",
                "Calibration must be loaded before saving bounding box coordinates.\n\n"
                "Please capture an image with calibration first."
            )
            return

        # Check if a box has already been saved
        if self.box_saved:
            QMessageBox.warning(
                self,
                "Box Already Saved",
                "Only one box can be saved per capture.\n\n"
                "Please capture a new image to save another box."
            )
            return

        try:
            # Read the original image to get dimensions
            image = Image.open(self.image_path)
            img_width, img_height = image.size

            # Get bounding box coordinates
            box = self.pending_box

            # Convert QRectF coordinates to pixel integers
            x1 = max(0, int(box.x()))
            y1 = max(0, int(box.y()))
            x2 = min(img_width, int(box.x() + box.width()))
            y2 = min(img_height, int(box.y() + box.height()))

            # Convert corners to world coordinates
            corners_pixel = [
                (x1, y1),  # top-left
                (x2, y1),  # top-right
                (x2, y2),  # bottom-right
                (x1, y2)  # bottom-left
            ]

            world_corners = []
            for corner in corners_pixel:
                world_point = self.calibration.pixel_to_world(corner)
                if world_point:
                    world_corners.append(world_point)

            if not world_corners or len(world_corners) < 4:
                QMessageBox.critical(
                    self,
                    "Conversion Failed",
                    "Failed to convert pixel coordinates to world coordinates."
                )
                return

            # Show confirmation dialog with coordinates preview
            preview_text = (
                f"Do you want to save this bounding box?\n\n"
                f"📍 World Coordinates:\n"
                f"   Point 1: ({world_corners[0][0]:.2f}, {world_corners[0][1]:.2f})\n"
                f"   Point 2: ({world_corners[1][0]:.2f}, {world_corners[1][1]:.2f})\n"
                f"   Point 3: ({world_corners[2][0]:.2f}, {world_corners[2][1]:.2f})\n"
                f"   Point 4: ({world_corners[3][0]:.2f}, {world_corners[3][1]:.2f})"
            )

            reply = QMessageBox.question(
                self,
                "Confirm Save",
                preview_text,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                self.status_label.setText("Save cancelled")
                return

            # Prepare the data to save - AS A LIST OF LISTS
            save_data = [
                [float(world_corners[0][0]), float(world_corners[0][1])],
                [float(world_corners[1][0]), float(world_corners[1][1])],
                [float(world_corners[2][0]), float(world_corners[2][1])],
                [float(world_corners[3][0]), float(world_corners[3][1])]
            ]

            # Generate filename based on timestamp
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"box_world_{timestamp_str}.json"
            save_path = os.path.join(self.boxes_json_path, filename)

            # Save to JSON file
            with open(save_path, 'w') as f:
                json.dump(save_data, f, indent=2)

            # Update UI - mark box as saved
            self.box_saved = True
            self.save_box_btn.setEnabled(False)
            self.save_box_btn.setText("✓ Box Saved")
            self.save_box_btn.setStyleSheet("""
                QPushButton {
                    background-color: #808080;
                    color: white;
                    font-weight: bold;
                    padding: 5px;
                }
            """)
            self.pending_box = None
            self.pending_box_label = None

            # Show success message
            QMessageBox.information(
                self,
                "Box Saved",
                f"✅ Bounding box saved successfully!\n\n"
                f"📁 File: {filename}\n\n"
                f"Only one box can be saved per capture."
            )

            self.status_label.setText(f"Box saved: {filename}")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save bounding box:\n{str(e)}"
            )

    def delete_selected(self):
        """Delete selected bounding box"""
        self.viewer.delete_selected()
        # Disable save button if no boxes left
        if hasattr(self.viewer, 'boxes') and len(self.viewer.boxes) == 0:
            self.save_box_btn.setEnabled(False)
            self.pending_box = None
            self.pending_box_label = None

    def capture_from_camera(self):
        """Capture from camera and save to Capture Image folder"""
        # First, ask user to select calibration file
        calibration_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Calibration File (Required for capture)",
            self.base_path,
            "JSON Files (*.json);;All Files (*.*)"
        )

        # Check if user selected a calibration file
        if not calibration_file:
            QMessageBox.warning(
                self,
                "Calibration Required",
                "Please select a calibration file before capturing images.\n\n"
                "Calibration is required for accurate coordinate conversion."
            )
            return

        # Load the calibration file
        success, message = self.calibration.load_calibration(calibration_file)
        if success:
            # Update UI to show calibration is loaded
            self.calibration_status.setText(f"Calibration loaded - {len(self.calibration.pixel_points)} points")
            self.calibration_status.setStyleSheet("color: #4CAF50; font-weight: bold;")

            # Show confirmation
            QMessageBox.information(
                self,
                "Calibration Loaded",
                f"✅ Calibration loaded successfully!\n\n"
                f"📁 File: {os.path.basename(calibration_file)}\n"
                f"📊 Number of points: {len(self.calibration.pixel_points)}\n"
                f"📍 Calibration status: Active"
            )
        else:
            # If calibration loading failed, show error and return
            QMessageBox.critical(
                self,
                "Calibration Failed",
                f"❌ Failed to load calibration file:\n{message}\n\n"
                f"Please select a valid calibration file."
            )
            return

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

                    # Add to image files list
                    if image_path not in self.image_files:
                        self.image_files.append(image_path)
                        self.image_files.sort()
                        self.current_index = self.image_files.index(image_path)

                self.camera_signals.finished.emit(success, message, image_path)

            AutoCaptureFlow(callback=callback)

        thread = threading.Thread(target=run_capture, daemon=True)
        thread.start()

    def on_camera_finished(self, success, message, image_path):
        """Handle camera capture completion"""
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("Capture Image")

        # Reset the box saved flag for new capture
        self.box_saved = False
        self.save_box_btn.setText("💾 Save Current Box")
        self.save_box_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)

        if success and image_path:
            if os.path.exists(image_path):
                # Load the captured image
                self.load_current_image()
                self.status_label.setText("Image captured and loaded successfully")
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

    def load_current_image(self):
        """Load the current image into the viewer"""
        if not self.image_files:
            return

        path = self.image_files[self.current_index]
        self.viewer.boxes.clear()
        self.viewer.load_image(path)
        self.image_path = path

        if path in self.image_boxes:
            self.viewer.boxes = self.image_boxes[path].copy()

        # Reset pending box when loading new image
        self.pending_box = None
        self.pending_box_label = None
        self.save_box_btn.setEnabled(False)
        self.box_saved = False
        self.save_box_btn.setText("💾 Save Current Box")
        self.save_box_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)

        # Window title WITHOUT index number
        self.setWindowTitle(
            f"BMP Annotation Tool – {os.path.basename(path)}"
        )

        # Update image info label WITHOUT index number
        self.image_info_label.setText(f"{os.path.basename(path)}")

        # Force update
        self.viewer.update()

    def get_current_label(self):
        """Get the current label from the combo box"""
        return self.label_combo.currentText() if hasattr(self, 'label_combo') else "0"

    def undo(self):
        """Undo last action"""
        self.viewer.undo_last()
        # Disable save button if no boxes left
        if hasattr(self.viewer, 'boxes') and len(self.viewer.boxes) == 0:
            self.save_box_btn.setEnabled(False)
            self.pending_box = None
            self.pending_box_label = None

    def save_current(self):
        """Save annotations for current image in YOLO format"""
        if hasattr(self, "image_path") and self.image_path:
            self.viewer.save_annotations(self.image_path)
            if hasattr(self.viewer, 'boxes'):
                self.image_boxes[self.image_path] = self.viewer.boxes.copy()

    def closeEvent(self, event):
        """Handle window close event"""
        self.save_current()
        event.accept()


import sys
from PySide6.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
import sys
import os
import ctypes
import time
import numpy as np
from datetime import datetime
from typing import Optional, List
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGroupBox, QPushButton, QLabel,
                               QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
                               QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox,
                               QLineEdit, QMessageBox, QSplitter, QScrollArea,
                               QProgressBar, QCheckBox, QFrame, QTreeWidget,
                               QTreeWidgetItem, QFileDialog, QDialog,
                               QDialogButtonBox, QFormLayout, QCheckBox, QComboBox)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, Slot, QSize, QBuffer
from PySide6.QtGui import QFont, QColor, QPalette, QBrush, QImage, QPixmap, QPainter, QPen

# Import the GetEnumName function from the original console script
from SciCam_class import *
import socket
import struct
from ctypes import c_bool


# Replicate the GetEnumName function from the console script
def GetEnumName(enumCls, value):
    """Get enum name from value"""
    if enumCls is None:
        return None
    try:
        for name, member in enumCls.__members__.items():
            if member == value:
                return name
    except:
        pass
    return None


# Replicate the uint32_to_ipv4 function
def uint32_to_ipv4(ip_uint32):
    """Convert uint32 to IPv4 address string"""
    try:
        network_order_ip = socket.htonl(ip_uint32)
        packed_ip = struct.pack("!I", network_order_ip)
        ipv4_address = socket.inet_ntoa(packed_ip)
        return ipv4_address
    except:
        return "0.0.0.0"


# Modified GetNodeValueStr to accept camera instance
def GetNodeValueStr(camera, xmlType, node):
    """Get node value as string"""
    if camera is None:
        return "N/A"

    iVal = SCI_NODE_VAL_INT()
    bVal = c_bool()
    fVal = SCI_NODE_VAL_FLOAT()
    eVal = SCI_NODE_VAL_ENUM()
    sVal = SCI_NODE_VAL_STRING()
    strVal = "N/A"

    try:
        nodeType = node.type
        node_name = node.name.decode() if node.name else ""

        if nodeType == SciCamNodeType.SciCam_NodeType_Bool:
            reVal = camera.SciCam_GetBoolValueEx(xmlType, node_name, bVal)
            if reVal == SCI_CAMERA_OK:
                strVal = str(bVal.value)
        elif nodeType == SciCamNodeType.SciCam_NodeType_Int:
            reVal = camera.SciCam_GetIntValueEx(xmlType, node_name, iVal)
            if reVal == SCI_CAMERA_OK:
                strVal = str(iVal.nVal)
        elif nodeType == SciCamNodeType.SciCam_NodeType_Float:
            reVal = camera.SciCam_GetFloatValueEx(xmlType, node_name, fVal)
            if reVal == SCI_CAMERA_OK:
                strVal = str(fVal.dVal)
        elif nodeType == SciCamNodeType.SciCam_NodeType_Enum:
            reVal = camera.SciCam_GetEnumValueEx(xmlType, node_name, eVal)
            if reVal == SCI_CAMERA_OK:
                strVal = str(eVal.nVal)
        elif nodeType == SciCamNodeType.SciCam_NodeType_String:
            reVal = camera.SciCam_GetStringValueEx(xmlType, node_name, sVal)
            if reVal == SCI_CAMERA_OK:
                strVal = str(sVal.val.decode())
    except Exception as e:
        strVal = f"Error: {str(e)}"

    return strVal


def decode_pixel_type(pixel_type):
    """Decode pixel type from integer value"""
    # Try to get enum name
    enum_name = GetEnumName(SciCamPixelType, pixel_type)
    if enum_name:
        return enum_name

    # If not found in enum, try to decode common values
    pixel_formats = {
        0x01080001: "Mono8",
        0x01100001: "Mono16",
        0x01080003: "BayerRG8",
        0x01080004: "BayerGR8",
        0x01080005: "BayerGB8",
        0x01080006: "BayerBG8",
        0x01100003: "BayerRG16",
        0x01100004: "BayerGR16",
        0x01100005: "BayerGB16",
        0x01100006: "BayerBG16",
        0x02180003: "RGB8",
        0x02100003: "RGB16",
        0x1080001: "BayerRG8 (0x1080001)",  # Your specific format
    }

    return pixel_formats.get(pixel_type, f"Unknown (0x{pixel_type:08x})")


def convert_payload_to_qimage_robust(payload_data):
    """Robust conversion using SDK's ConvertImage function properly"""
    if payload_data is None:
        return None

    try:
        # Get the raw payload pointer
        ppayload = payload_data.get('payload')
        if not ppayload:
            print("No payload pointer")
            return None

        # Get payload attribute
        payloadAttribute = payload_data.get('attribute')
        if not payloadAttribute:
            print("No payload attribute")
            return None

        width = payloadAttribute.imgAttr.width
        height = payloadAttribute.imgAttr.height
        pixel_type = payloadAttribute.imgAttr.pixelType

        print(f"Image: {width}x{height}, Pixel type: {decode_pixel_type(pixel_type)} (0x{pixel_type:08x})")

        if width <= 0 or height <= 0:
            print(f"Invalid dimensions: {width}x{height}")
            return create_placeholder_image(width, height, f"Invalid dimensions")

        # Get image data pointer
        imgData = ctypes.c_void_p()
        reVal = SciCam_Payload_GetImage(ppayload, imgData)

        if reVal != SCI_CAMERA_OK:
            print(f"Failed to get image data: {reVal}")
            return create_placeholder_image(width, height, f"GetImage failed: {reVal}")

        # Try different conversion strategies
        img_attr = payloadAttribute.imgAttr

        # List of formats to try in order of preference
        target_formats = [
            (SciCamPixelType.RGB8, QImage.Format.Format_RGB888, 3, "RGB8"),
            (SciCamPixelType.Mono8, QImage.Format.Format_Grayscale8, 1, "Mono8"),
            (SciCamPixelType.BGR8, QImage.Format.Format_BGR888, 3, "BGR8"),
        ]

        # First try to get the actual pixel format from the SDK if possible
        # Sometimes the SDK provides direct access to the raw buffer
        reVal = SCI_CAMERA_OK
        dstImgSize = ctypes.c_int(0)

        # Try each format
        success = False
        qimage = None

        for target_format, qimage_format, bytes_per_pixel, format_name in target_formats:
            try:
                # Check if conversion is possible
                reVal = SciCam_Payload_ConvertImage(img_attr, imgData, target_format, None, dstImgSize, True)

                if reVal == SCI_CAMERA_OK:
                    buffer_size = dstImgSize.value
                    print(f"{format_name} conversion possible, buffer size: {buffer_size}")

                    if buffer_size > 0:
                        pDstData = (ctypes.c_ubyte * buffer_size)()

                        # Perform the conversion
                        reVal = SciCam_Payload_ConvertImage(img_attr, imgData, target_format, pDstData, dstImgSize,
                                                            True)

                        if reVal == SCI_CAMERA_OK:
                            # Create QImage
                            if bytes_per_pixel == 1:
                                qimage = QImage(pDstData, width, height, width, qimage_format)
                            elif bytes_per_pixel == 3:
                                qimage = QImage(pDstData, width, height, width * 3, qimage_format)

                            if qimage and not qimage.isNull():
                                print(f"Successfully converted to {format_name}")
                                success = True
                                break
                            else:
                                print(f"Failed to create QImage from {format_name}")
                else:
                    print(f"{format_name} conversion not supported: {reVal}")

            except Exception as e:
                print(f"Error trying {format_name} conversion: {str(e)}")

        # If standard conversions failed, try to access raw buffer
        if not success:
            print("Standard conversions failed, trying raw buffer access...")
            qimage = try_raw_buffer_access(img_attr, imgData, width, height, pixel_type)

        if qimage and not qimage.isNull():
            return qimage.copy()
        else:
            print("All conversion methods failed")
            return create_placeholder_image(width, height, f"Failed to convert: {decode_pixel_type(pixel_type)}")

    except Exception as e:
        print(f"Error in robust conversion: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_placeholder_image(640, 480, f"Error: {str(e)[:50]}")


def try_raw_buffer_access(img_attr, imgData, width, height, pixel_type):
    """Try to access raw image buffer and interpret it"""
    try:
        # Get raw buffer pointer
        # Note: This may require SDK-specific functions
        # Try to get image data as raw bytes

        # First, try to get the size of the raw data
        raw_size = width * height

        # For Bayer patterns, the size calculation depends on bit depth
        if pixel_type == 0x1080001:  # Likely BayerRG8
            raw_size = width * height  # 8-bit Bayer
            print(f"Trying BayerRG8 interpretation, raw size: {raw_size}")

            # We need to get the actual data buffer
            # This might require using the SDK's memory access functions
            return None  # Placeholder

        elif pixel_type in [0x01080001, 0x1080001]:  # Mono8 or similar
            # Try to interpret as grayscale
            # Get buffer through ctypes
            buffer_ptr = ctypes.cast(imgData, ctypes.POINTER(ctypes.c_ubyte * (width * height)))
            if buffer_ptr:
                buffer = buffer_ptr.contents
                qimage = QImage(bytes(buffer), width, height, width, QImage.Format.Format_Grayscale8)
                if not qimage.isNull():
                    print("Successfully created QImage from raw grayscale buffer")
                    return qimage

    except Exception as e:
        print(f"Error in raw buffer access: {str(e)}")

    return None


def get_direct_image_data(camera, ppayload, width, height):
    """Try to get direct image data from the SDK"""
    try:
        # Some SDKs provide direct access to the image buffer
        # Check the SDK documentation for the correct method

        # Try SciCam_Payload_GetImageBuffer or similar
        # This is a placeholder - you'll need to check your specific SDK

        # Example approach:
        img_buffer = ctypes.c_void_p()
        buffer_size = ctypes.c_uint(0)

        # This function name might vary - check your SDK
        reVal = camera.SciCam_GetImageBuffer(ppayload, img_buffer, buffer_size)

        if reVal == SCI_CAMERA_OK and buffer_size.value > 0:
            # Convert to byte array
            buffer_ptr = ctypes.cast(img_buffer, ctypes.POINTER(ctypes.c_ubyte * buffer_size.value))
            buffer_data = bytes(buffer_ptr.contents)

            # Try to interpret based on common patterns
            # For width*height buffer size, assume 8-bit grayscale
            if buffer_size.value == width * height:
                qimage = QImage(buffer_data, width, height, width, QImage.Format.Format_Grayscale8)
                if not qimage.isNull():
                    return qimage

            # For 3*width*height buffer size, assume RGB
            elif buffer_size.value == width * height * 3:
                qimage = QImage(buffer_data, width, height, width * 3, QImage.Format.Format_RGB888)
                if not qimage.isNull():
                    return qimage

    except Exception as e:
        print(f"Error getting direct image data: {str(e)}")

    return None


def convert_bayer_to_rgb(buffer_data, width, height, bayer_pattern="RG"):
    """Convert Bayer pattern data to RGB using numpy"""
    try:
        import numpy as np

        # Reshape buffer to 2D array
        bayer_data = np.frombuffer(buffer_data, dtype=np.uint8).reshape((height, width))

        # Create RGB array
        rgb_data = np.zeros((height, width, 3), dtype=np.uint8)

        # Simple Bayer demosaicing (nearest neighbor)
        # This is a basic implementation - you may need more sophisticated demosaicing

        if bayer_pattern == "RG":
            # Red
            rgb_data[0::2, 0::2, 0] = bayer_data[0::2, 0::2]
            # Green
            rgb_data[0::2, 1::2, 1] = bayer_data[0::2, 1::2]
            rgb_data[1::2, 0::2, 1] = bayer_data[1::2, 0::2]
            # Blue
            rgb_data[1::2, 1::2, 2] = bayer_data[1::2, 1::2]

        elif bayer_pattern == "GR":
            # Green
            rgb_data[0::2, 0::2, 1] = bayer_data[0::2, 0::2]
            # Red
            rgb_data[0::2, 1::2, 0] = bayer_data[0::2, 1::2]
            # Blue
            rgb_data[1::2, 0::2, 2] = bayer_data[1::2, 0::2]
            # Green
            rgb_data[1::2, 1::2, 1] = bayer_data[1::2, 1::2]

        # Simple interpolation (fill in missing pixels with neighbors)
        for y in range(height):
            for x in range(width):
                for c in range(3):
                    if rgb_data[y, x, c] == 0:
                        # Average of neighbors
                        neighbors = []
                        for dy in [-1, 0, 1]:
                            for dx in [-1, 0, 1]:
                                ny, nx = y + dy, x + dx
                                if 0 <= ny < height and 0 <= nx < width and rgb_data[ny, nx, c] > 0:
                                    neighbors.append(rgb_data[ny, nx, c])
                        if neighbors:
                            rgb_data[y, x, c] = int(sum(neighbors) / len(neighbors))

        # Convert to QImage
        rgb_bytes = rgb_data.tobytes()
        qimage = QImage(rgb_bytes, width, height, width * 3, QImage.Format.Format_RGB888)

        return qimage

    except Exception as e:
        print(f"Error in Bayer conversion: {str(e)}")
        return None


def create_placeholder_image(width, height, text=""):
    """Create a placeholder image when conversion fails"""
    try:
        if width <= 0 or height <= 0:
            width, height = 640, 480

        placeholder = QImage(width, height, QImage.Format.Format_RGB888)

        # Create gradient background
        for y in range(height):
            for x in range(width):
                r = int(50 + 50 * x / width)
                g = int(50 + 50 * y / height)
                b = 100
                placeholder.setPixelColor(x, y, QColor(r, g, b))

        painter = QPainter(placeholder)

        # Draw grid
        pen = QPen(QColor(80, 80, 120), 1)
        painter.setPen(pen)
        grid_size = 20
        for x in range(0, width, grid_size):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, grid_size):
            painter.drawLine(0, y, width, y)

        # Draw cross in center
        painter.setPen(QPen(QColor(255, 200, 200), 2))
        painter.drawLine(width // 2 - 10, height // 2, width // 2 + 10, height // 2)
        painter.drawLine(width // 2, height // 2 - 10, width // 2, height // 2 + 10)

        # Draw text
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 12, QFont.Bold))

        lines = text.split('\n')
        y_offset = height // 2 - (len(lines) * 15) // 2

        for i, line in enumerate(lines):
            painter.drawText(0, y_offset + i * 30, width, 30,
                             Qt.AlignmentFlag.AlignCenter, line)

        # Draw dimensions
        painter.setFont(QFont("Arial", 10))
        painter.drawText(0, 30, width, 30,
                         Qt.AlignmentFlag.AlignCenter, f"{width} x {height}")

        painter.end()
        return placeholder

    except Exception as e:
        print(f"Error creating placeholder: {str(e)}")
        # Last resort: create simple black image
        simple = QImage(640, 480, QImage.Format.Format_RGB888)
        simple.fill(QColor(0, 0, 0))
        return simple


class EditNodeDialog(QDialog):
    """Dialog for editing node values"""

    def __init__(self, camera, node, parent=None):
        super().__init__(parent)
        self.camera = camera
        self.node = node
        self.setWindowTitle(f"Edit Node: {node.name.decode() if node.name else 'Unknown'}")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        form_layout = QFormLayout()

        # Node name (readonly)
        self.name_label = QLabel(self.node.name.decode() if self.node.name else "Unknown")
        form_layout.addRow("Node Name:", self.name_label)

        # Node type (readonly)
        node_type = GetEnumName(SciCamNodeType, self.node.type) or str(self.node.type)
        self.type_label = QLabel(node_type)
        form_layout.addRow("Node Type:", self.type_label)

        # Value editor based on node type
        self.value_widget = None
        if self.node.type == SciCamNodeType.SciCam_NodeType_Bool:
            self.value_widget = QCheckBox()
            # Try to get current value
            bVal = c_bool()
            reVal = self.camera.SciCam_GetBoolValueEx(SciCamDeviceXmlType.SciCam_DeviceXml_Camera,
                                                      self.node.name.decode(), bVal)
            if reVal == SCI_CAMERA_OK:
                self.value_widget.setChecked(bVal.value)
        elif self.node.type == SciCamNodeType.SciCam_NodeType_Int:
            self.value_widget = QSpinBox()
            self.value_widget.setRange(-1000000, 1000000)
            # Try to get current value and range
            iVal = SCI_NODE_VAL_INT()
            reVal = self.camera.SciCam_GetIntValueEx(SciCamDeviceXmlType.SciCam_DeviceXml_Camera,
                                                     self.node.name.decode(), iVal)
            if reVal == SCI_CAMERA_OK:
                self.value_widget.setValue(iVal.nVal)
                self.value_widget.setRange(iVal.nMin, iVal.nMax)
                if iVal.nInc > 0:
                    self.value_widget.setSingleStep(iVal.nInc)
        elif self.node.type == SciCamNodeType.SciCam_NodeType_Float:
            self.value_widget = QDoubleSpinBox()
            self.value_widget.setRange(-1000000.0, 1000000.0)
            self.value_widget.setDecimals(6)
            # Try to get current value and range
            fVal = SCI_NODE_VAL_FLOAT()
            reVal = self.camera.SciCam_GetFloatValueEx(SciCamDeviceXmlType.SciCam_DeviceXml_Camera,
                                                       self.node.name.decode(), fVal)
            if reVal == SCI_CAMERA_OK:
                self.value_widget.setValue(fVal.dVal)
                self.value_widget.setRange(fVal.dMin, fVal.dMax)
        elif self.node.type == SciCamNodeType.SciCam_NodeType_Enum:
            self.value_widget = QComboBox()
            # Try to get enum values
            eVal = SCI_NODE_VAL_ENUM()
            reVal = self.camera.SciCam_GetEnumValueEx(SciCamDeviceXmlType.SciCam_DeviceXml_Camera,
                                                      self.node.name.decode(), eVal)
            if reVal == SCI_CAMERA_OK:
                for i in range(eVal.itemCount):
                    item_text = f"{eVal.items[i].val}: {eVal.items[i].desc}"
                    self.value_widget.addItem(item_text, eVal.items[i].val)
                    if eVal.items[i].val == eVal.nVal:
                        self.value_widget.setCurrentIndex(i)
        elif self.node.type == SciCamNodeType.SciCam_NodeType_String:
            self.value_widget = QLineEdit()
            # Try to get current value
            sVal = SCI_NODE_VAL_STRING()
            reVal = self.camera.SciCam_GetStringValueEx(SciCamDeviceXmlType.SciCam_DeviceXml_Camera,
                                                        self.node.name.decode(), sVal)
            if reVal == SCI_CAMERA_OK:
                self.value_widget.setText(sVal.val.decode())

        if self.value_widget:
            form_layout.addRow("Value:", self.value_widget)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self.resize(400, 200)

    def get_value(self):
        """Get the edited value"""
        if self.node.type == SciCamNodeType.SciCam_NodeType_Bool:
            return self.value_widget.isChecked()
        elif self.node.type == SciCamNodeType.SciCam_NodeType_Int:
            return self.value_widget.value()
        elif self.node.type == SciCamNodeType.SciCam_NodeType_Float:
            return self.value_widget.value()
        elif self.node.type == SciCamNodeType.SciCam_NodeType_Enum:
            return self.value_widget.currentData()
        elif self.node.type == SciCamNodeType.SciCam_NodeType_String:
            return self.value_widget.text()
        return None


class ImageDisplayWidget(QWidget):
    """Widget for displaying camera images"""

    def __init__(self):
        super().__init__()
        self.current_image = None
        self.scale_factor = 1.0
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Image display label
        self.image_label = QLabel("No Image")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                color: #ffffff;
                border: 2px solid #cccccc;
                border-radius: 4px;
            }
        """)

        # Control buttons for image display
        control_layout = QHBoxLayout()

        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)

        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)

        self.fit_btn = QPushButton("Fit to Window")
        self.fit_btn.clicked.connect(self.fit_to_window)

        self.original_btn = QPushButton("Original Size")
        self.original_btn.clicked.connect(self.original_size)

        control_layout.addWidget(self.zoom_in_btn)
        control_layout.addWidget(self.zoom_out_btn)
        control_layout.addWidget(self.fit_btn)
        control_layout.addWidget(self.original_btn)
        control_layout.addStretch()

        layout.addWidget(self.image_label, 1)  # Stretch factor 1
        layout.addLayout(control_layout)

        self.setLayout(layout)

    def display_image(self, qimage):
        """Display a QImage in the widget"""
        try:
            if qimage is None or qimage.isNull():
                self.image_label.setText("No Image Available")
                self.current_image = None
                return

            self.current_image = qimage

            # Scale the image
            scaled_image = qimage.scaled(
                qimage.size() * self.scale_factor,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Create pixmap and display
            pixmap = QPixmap.fromImage(scaled_image)
            self.image_label.setPixmap(pixmap)
            self.image_label.setText("")

            # Update status
            self.update_status()

        except Exception as e:
            print(f"Error displaying image: {str(e)}")
            self.image_label.setText(f"Error displaying image")
            self.current_image = None

    def update_status(self):
        """Update image status information"""
        if self.current_image:
            status = f"Image: {self.current_image.width()}x{self.current_image.height()} | Zoom: {self.scale_factor:.1f}x"
            self.image_label.setToolTip(status)

    def zoom_in(self):
        """Zoom in on the image"""
        self.scale_factor *= 1.2
        if self.current_image:
            self.display_image(self.current_image)

    def zoom_out(self):
        """Zoom out on the image"""
        self.scale_factor *= 0.8
        if self.current_image:
            self.display_image(self.current_image)

    def fit_to_window(self):
        """Fit image to the widget size"""
        if self.current_image and self.image_label.width() > 0 and self.image_label.height() > 0:
            # Calculate scale factor to fit image in label
            label_width = self.image_label.width() - 10  # Account for border
            label_height = self.image_label.height() - 10

            scale_w = label_width / self.current_image.width()
            scale_h = label_height / self.current_image.height()
            self.scale_factor = min(scale_w, scale_h)

            self.display_image(self.current_image)

    def original_size(self):
        """Show image at original size"""
        self.scale_factor = 1.0
        if self.current_image:
            self.display_image(self.current_image)


class CameraWorker(QThread):
    """Worker thread for camera operations"""
    log_signal = Signal(str)
    device_list_signal = Signal(list)
    image_grabbed_signal = Signal(object)  # Will emit payload data
    image_display_signal = Signal(object)  # Will emit QImage for display

    def __init__(self):
        super().__init__()
        self.camera = SciCamera()
        self.devices = []
        self.current_device = None
        self.is_grabbing = False

    def discovery_devices(self):
        """Discover available devices"""
        try:
            self.log_signal.emit("Discovering devices...")
            devInfos = SCI_DEVICE_INFO_LIST()
            reVal = SciCamera.SciCam_DiscoveryDevices(devInfos, SciCamTLType.SciCam_TLType_Unkown)

            if reVal != SCI_CAMERA_OK:
                self.log_signal.emit(f"Discovery failed: Error {reVal}")
                return

            device_list = []
            for index in range(devInfos.count):
                device_list.append({
                    'index': index,
                    'info': devInfos.pDevInfo[index]
                })

            self.devices = device_list
            self.device_list_signal.emit(device_list)
            self.log_signal.emit(f"Found {len(device_list)} device(s)")

        except Exception as e:
            self.log_signal.emit(f"Error discovering devices: {str(e)}")

    def open_device(self, device_index):
        """Open selected device"""
        try:
            if device_index < 0 or device_index >= len(self.devices):
                self.log_signal.emit("Invalid device index")
                return False

            device_info = self.devices[device_index]['info']
            reVal = self.camera.SciCam_CreateDevice(device_info)
            if reVal != SCI_CAMERA_OK:
                self.log_signal.emit(f"Create device failed: Error {reVal}")
                return False

            reVal = self.camera.SciCam_OpenDevice()
            if reVal != SCI_CAMERA_OK:
                self.log_signal.emit(f"Open device failed: Error {reVal}")
                return False

            self.current_device = device_info
            self.is_grabbing = False
            self.log_signal.emit("Device opened successfully")
            return True

        except Exception as e:
            self.log_signal.emit(f"Error opening device: {str(e)}")
            return False

    def close_device(self):
        """Close current device"""
        try:
            if self.camera:
                # Stop grabbing if active
                if self.is_grabbing:
                    self.stop_grabbing()

                reVal = self.camera.SciCam_CloseDevice()
                if reVal != SCI_CAMERA_OK:
                    self.log_signal.emit(f"Close device failed: Error {reVal}")
                else:
                    self.camera.SciCam_DeleteDevice()
                    self.current_device = None
                    self.is_grabbing = False
                    self.log_signal.emit("Device closed")

        except Exception as e:
            self.log_signal.emit(f"Error closing device: {str(e)}")

    def start_grabbing(self, timeout, buffer_count, strategy):
        """Start continuous grabbing"""
        try:
            # Apply settings
            self.camera.SciCam_SetGrabTimeout(timeout)
            self.camera.SciCam_SetGrabBufferCount(buffer_count)
            self.camera.SciCam_SetGrabStrategy(strategy)

            # Start grabbing
            reVal = self.camera.SciCam_StartGrabbing()
            if reVal == SCI_CAMERA_OK:
                self.is_grabbing = True
                self.log_signal.emit("Continuous grabbing started")
                return True
            else:
                self.log_signal.emit(f"Failed to start grabbing: Error {reVal}")
                return False

        except Exception as e:
            self.log_signal.emit(f"Error starting grabbing: {str(e)}")
            return False

    def stop_grabbing(self):
        """Stop continuous grabbing"""
        try:
            reVal = self.camera.SciCam_StopGrabbing()
            if reVal == SCI_CAMERA_OK:
                self.is_grabbing = False
                self.log_signal.emit("Continuous grabbing stopped")
                return True
            else:
                self.log_signal.emit(f"Failed to stop grabbing: Error {reVal}")
                return False

        except Exception as e:
            self.log_signal.emit(f"Error stopping grabbing: {str(e)}")
            return False

    def grab_single_image(self, timeout=1000):
        """Grab a single image (starts grabbing temporarily if not already grabbing)"""
        try:
            was_grabbing = self.is_grabbing

            # If not already grabbing, start grabbing temporarily
            if not was_grabbing:
                self.log_signal.emit("Starting grab for single image...")
                self.camera.SciCam_SetGrabTimeout(timeout)
                self.camera.SciCam_SetGrabBufferCount(1)
                self.camera.SciCam_SetGrabStrategy(0)  # OneByOne strategy

                reVal = self.camera.SciCam_StartGrabbing()
                if reVal != SCI_CAMERA_OK:
                    self.log_signal.emit(f"Failed to start grabbing for single image: Error {reVal}")
                    return None

            # Now grab the image
            ppayload = ctypes.c_void_p()
            reVal = self.camera.SciCam_Grab(ppayload)

            # Stop grabbing if we started it just for this single image
            if not was_grabbing:
                self.camera.SciCam_StopGrabbing()
                self.is_grabbing = False

            if reVal != SCI_CAMERA_OK:
                self.log_signal.emit(f"Grab failed: Error {reVal}")
                return None

            # Get payload attributes
            payloadAttribute = SCI_CAM_PAYLOAD_ATTRIBUTE()
            reVal = SciCam_Payload_GetAttribute(ppayload, payloadAttribute)

            if reVal != SCI_CAMERA_OK:
                self.log_signal.emit(f"Warning: Get payload attribute failed: Error {reVal}")
                # Still try to proceed with default values
                payloadAttribute = SCI_CAM_PAYLOAD_ATTRIBUTE()

            # Create payload data structure
            payload_data = {
                'payload': ppayload,
                'attribute': payloadAttribute,
                'width': payloadAttribute.imgAttr.width,
                'height': payloadAttribute.imgAttr.height,
                'frame_id': payloadAttribute.frameID,
                'timestamp': payloadAttribute.timeStamp,
                'pixel_type': payloadAttribute.imgAttr.pixelType
            }

            self.log_signal.emit(
                f"Image grabbed: {payloadAttribute.imgAttr.width}x{payloadAttribute.imgAttr.height}, Pixel type: {payloadAttribute.imgAttr.pixelType}")

            # Convert to QImage for display
            qimage = convert_payload_to_qimage_robust(payload_data)
            if qimage:
                self.image_display_signal.emit(qimage)
                self.log_signal.emit("Image converted and sent for display")
            else:
                self.log_signal.emit("Failed to convert image, showing placeholder")
                placeholder = create_placeholder_image(
                    payloadAttribute.imgAttr.width,
                    payloadAttribute.imgAttr.height,
                    f"Pixel Type: {payloadAttribute.imgAttr.pixelType}"
                )
                if placeholder:
                    self.image_display_signal.emit(placeholder)

            # Free the payload after we're done with it
            try:
                self.camera.SciCam_FreePayload(ppayload)
            except:
                pass

            self.image_grabbed_signal.emit(payload_data)
            return payload_data

        except Exception as e:
            self.log_signal.emit(f"Error grabbing image: {str(e)}")
            import traceback
            traceback.print_exc()
            return None


class DeviceInfoWidget(QWidget):
    """Widget to display device information"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Device info group
        info_group = QGroupBox("Device Information")
        info_layout = QVBoxLayout()

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(300)
        self.info_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        info_layout.addWidget(self.info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        self.setLayout(layout)

    def update_info(self, device_info):
        """Update device information display"""
        if not device_info:
            self.info_text.setText("No device selected")
            return

        info_str = ""

        # Device type
        devType = GetEnumName(SciCamDeviceType, device_info.devType)
        info_str += f"<b>Device Type:</b> {devType if devType else 'Unknown'}<br>"

        # Transfer type
        devTlType = GetEnumName(SciCamTLType, device_info.tlType)
        info_str += f"<b>Transfer Type:</b> {devTlType if devTlType else 'Unknown'}<br><br>"

        # Based on transfer type, show specific info
        if device_info.tlType == SciCamTLType.SciCam_TLType_Gige:
            info_str += self._get_gige_info(device_info)
        elif device_info.tlType == SciCamTLType.SciCam_TLType_Usb3:
            info_str += self._get_usb3_info(device_info)
        elif device_info.tlType == SciCamTLType.SciCam_TLType_CL:
            info_str += self._get_cl_info(device_info)

        self.info_text.setText(info_str)

    def _get_gige_info(self, device_info):
        """Get GigE device information"""
        info = device_info.info.gigeInfo
        info_str = ""

        # Camera name
        name = ''.join(chr(c) for c in info.name if c != 0)
        if name:
            info_str += f"<b>Camera Name:</b> {name}<br>"

        # Manufacturer
        manufacture = ''.join(chr(c) for c in info.manufactureName if c != 0)
        if manufacture:
            info_str += f"<b>Manufacturer:</b> {manufacture}<br>"

        # Model
        model = ''.join(chr(c) for c in info.modelName if c != 0)
        if model:
            info_str += f"<b>Model:</b> {model}<br>"

        # Serial number
        serial = ''.join(chr(c) for c in info.serialNumber if c != 0)
        if serial:
            info_str += f"<b>Serial Number:</b> {serial}<br>"

        # IP Address
        ip = uint32_to_ipv4(info.ip)
        info_str += f"<b>IP Address:</b> {ip}<br>"

        # MAC Address
        mac = ':'.join(f'{b:02x}' for b in info.mac[:6])
        info_str += f"<b>MAC Address:</b> {mac}<br>"

        return info_str

    def _get_usb3_info(self, device_info):
        """Get USB3 device information"""
        info = device_info.info.usb3Info
        info_str = ""

        # Camera name
        name = ''.join(chr(c) for c in info.name if c != 0)
        if name:
            info_str += f"<b>Camera Name:</b> {name}<br>"

        # Manufacturer
        manufacture = ''.join(chr(c) for c in info.manufactureName if c != 0)
        if manufacture:
            info_str += f"<b>Manufacturer:</b> {manufacture}<br>"

        # Model
        model = ''.join(chr(c) for c in info.modelName if c != 0)
        if model:
            info_str += f"<b>Model:</b> {model}<br>"

        # Serial number
        serial = ''.join(chr(c) for c in info.serialNumber if c != 0)
        if serial:
            info_str += f"<b>Serial Number:</b> {serial}<br>"

        # GUID
        guid = ''.join(chr(c) for c in info.guid if c != 0)
        if guid:
            info_str += f"<b>GUID:</b> {guid}<br>"

        return info_str

    def _get_cl_info(self, device_info):
        """Get CL device information"""
        info = device_info.info.clInfo
        info_str = ""

        # Card info
        card_name = ''.join(chr(c) for c in info.cardName if c != 0)
        if card_name:
            info_str += f"<b>Card Name:</b> {card_name}<br>"

        # Camera info
        camera_model = ''.join(chr(c) for c in info.cameraModel if c != 0)
        if camera_model:
            info_str += f"<b>Camera Model:</b> {camera_model}<br>"

        # Manufacturer
        manufacture = ''.join(chr(c) for c in info.cameraManufacture if c != 0)
        if manufacture:
            info_str += f"<b>Manufacturer:</b> {manufacture}<br>"

        # Serial number
        serial = ''.join(chr(c) for c in info.cameraSerialNumber if c != 0)
        if serial:
            info_str += f"<b>Serial Number:</b> {serial}<br>"

        return info_str


class NodeTreeWidget(QWidget):
    """Widget to display and control device nodes"""

    def __init__(self, camera_worker):
        super().__init__()
        self.camera_worker = camera_worker
        self.current_nodes = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Control buttons
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh Nodes")
        self.refresh_btn.clicked.connect(self.refresh_nodes)

        self.edit_btn = QPushButton("Edit Selected Node")
        self.edit_btn.clicked.connect(self.edit_selected_node)
        self.edit_btn.setEnabled(False)

        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.edit_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Node tree
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderLabels(["Node", "Type", "Value", "Access"])
        self.node_tree.setColumnWidth(0, 250)
        self.node_tree.setColumnWidth(1, 100)
        self.node_tree.setColumnWidth(2, 150)
        self.node_tree.setColumnWidth(3, 80)
        self.node_tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.node_tree.itemDoubleClicked.connect(self.on_item_double_clicked)

        layout.addWidget(self.node_tree)

        self.setLayout(layout)

    def on_selection_changed(self):
        """Handle tree selection change"""
        selected_items = self.node_tree.selectedItems()
        if selected_items:
            # Get the node index from the item
            item = selected_items[0]
            node_idx = item.data(0, Qt.UserRole)
            if node_idx is not None and node_idx < len(self.current_nodes):
                node = self.current_nodes[node_idx]
                # Enable edit button only for RW nodes
                if node.accessMode == SciCamNodeAccessMode.SciCam_NodeAccessMode_RW:
                    self.edit_btn.setEnabled(True)
                else:
                    self.edit_btn.setEnabled(False)
        else:
            self.edit_btn.setEnabled(False)

    def on_item_double_clicked(self, item, column):
        """Handle double click on tree item"""
        node_idx = item.data(0, Qt.UserRole)
        if node_idx is not None and node_idx < len(self.current_nodes):
            node = self.current_nodes[node_idx]
            # Only allow editing for RW nodes
            if node.accessMode == SciCamNodeAccessMode.SciCam_NodeAccessMode_RW:
                self.edit_node(node_idx)

    def refresh_nodes(self):
        """Refresh the node tree"""
        if not self.camera_worker.camera:
            QMessageBox.warning(self, "Warning", "No camera connected")
            return

        try:
            nodesCount = ctypes.c_uint(0)
            reVal = self.camera_worker.camera.SciCam_GetNodes(None, nodesCount)

            if reVal != SCI_CAMERA_OK or nodesCount.value == 0:
                self.node_tree.clear()
                QMessageBox.information(self, "Info", "No nodes found or failed to get nodes")
                return

            nodes = (SCI_CAM_NODE * nodesCount.value)()
            reVal = self.camera_worker.camera.SciCam_GetNodes(
                ctypes.cast(nodes, PSCI_CAM_NODE).contents, nodesCount)

            if reVal == SCI_CAMERA_OK:
                self.current_nodes = nodes
                self.update_tree(nodes, nodesCount.value)
            else:
                QMessageBox.warning(self, "Warning", f"Failed to get nodes: Error {reVal}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to get nodes: {str(e)}")

    def update_tree(self, nodes, count):
        """Update the tree widget with nodes"""
        self.node_tree.clear()

        # Build parent-child relationships
        node_dict = {}

        # First pass: create all items
        for i in range(count):
            node = nodes[i]
            try:
                # Get node value using the camera instance
                node_value = GetNodeValueStr(
                    self.camera_worker.camera,
                    SciCamDeviceXmlType.SciCam_DeviceXml_Camera,
                    node
                )

                item = QTreeWidgetItem([
                    node.name.decode() if node.name else "Unknown",
                    GetEnumName(SciCamNodeType, node.type) if GetEnumName(SciCamNodeType, node.type) else str(
                        node.type),
                    node_value,
                    GetEnumName(SciCamNodeAccessMode, node.accessMode) if GetEnumName(SciCamNodeAccessMode,
                                                                                      node.accessMode) else str(
                        node.accessMode)
                ])

                # Store node index in item data
                item.setData(0, Qt.UserRole, i)

                # Color code based on access mode
                if node.accessMode == SciCamNodeAccessMode.SciCam_NodeAccessMode_RW:
                    # Green background for RW nodes
                    item.setBackground(3, QBrush(QColor(200, 255, 200)))
                elif node.accessMode == SciCamNodeAccessMode.SciCam_NodeAccessMode_RO:
                    # Yellow background for RO nodes
                    item.setBackground(3, QBrush(QColor(255, 255, 200)))
                elif node.accessMode == SciCamNodeAccessMode.SciCam_NodeAccessMode_WO:
                    # Blue background for WO nodes
                    item.setBackground(3, QBrush(QColor(200, 200, 255)))

                node_dict[i] = item
            except Exception as e:
                print(f"Error processing node {i}: {e}")
                # Create item with error info
                item = QTreeWidgetItem([
                    "Error",
                    "Error",
                    f"Error: {str(e)}",
                    "Error"
                ])
                node_dict[i] = item

        # Second pass: build hierarchy
        for i in range(count):
            if i >= len(nodes):
                continue

            node = nodes[i]
            item = node_dict[i]

            if node.level == 0:
                self.node_tree.addTopLevelItem(item)
            else:
                # Find parent based on level
                parent_idx = i - 1
                while parent_idx >= 0 and nodes[parent_idx].level >= node.level:
                    parent_idx -= 1

                if parent_idx >= 0:
                    parent_item = node_dict[parent_idx]
                    parent_item.addChild(item)

        # Expand all items
        self.node_tree.expandAll()

    def edit_selected_node(self):
        """Edit the selected node"""
        selected_items = self.node_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a node to edit")
            return

        item = selected_items[0]
        node_idx = item.data(0, Qt.UserRole)
        if node_idx is not None and node_idx < len(self.current_nodes):
            self.edit_node(node_idx)

    def edit_node(self, node_idx):
        """Edit a specific node"""
        node = self.current_nodes[node_idx]

        # Create edit dialog
        dialog = EditNodeDialog(self.camera_worker.camera, node, self)
        if dialog.exec() == QDialog.Accepted:
            new_value = dialog.get_value()
            if new_value is not None:
                self.apply_node_value(node, new_value)

    def apply_node_value(self, node, new_value):
        """Apply new value to node"""
        try:
            node_name = node.name.decode() if node.name else ""
            node_type = node.type
            reVal = SCI_CAMERA_OK

            if node_type == SciCamNodeType.SciCam_NodeType_Bool:
                reVal = self.camera_worker.camera.SciCam_SetBoolValueEx(
                    SciCamDeviceXmlType.SciCam_DeviceXml_Camera, node_name, new_value)
            elif node_type == SciCamNodeType.SciCam_NodeType_Int:
                reVal = self.camera_worker.camera.SciCam_SetIntValueEx(
                    SciCamDeviceXmlType.SciCam_DeviceXml_Camera, node_name, new_value)
            elif node_type == SciCamNodeType.SciCam_NodeType_Float:
                reVal = self.camera_worker.camera.SciCam_SetFloatValueEx(
                    SciCamDeviceXmlType.SciCam_DeviceXml_Camera, node_name, new_value)
            elif node_type == SciCamNodeType.SciCam_NodeType_Enum:
                reVal = self.camera_worker.camera.SciCam_SetEnumValueEx(
                    SciCamDeviceXmlType.SciCam_DeviceXml_Camera, node_name, new_value)
            elif node_type == SciCamNodeType.SciCam_NodeType_String:
                reVal = self.camera_worker.camera.SciCam_SetStringValueEx(
                    SciCamDeviceXmlType.SciCam_DeviceXml_Camera, node_name, new_value)

            if reVal == SCI_CAMERA_OK:
                QMessageBox.information(self, "Success", f"Node {node_name} updated successfully")
                # Refresh the node value in the tree
                self.refresh_nodes()
            else:
                QMessageBox.warning(self, "Error", f"Failed to update node {node_name}: Error {reVal}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update node: {str(e)}")


class CameraControlWidget(QWidget):
    """Main camera control widget"""

    def __init__(self):
        super().__init__()
        self.camera_worker = CameraWorker()
        self.current_device_index = -1
        self.last_payload = None
        self.frame_count = 0
        self.fps_timer = QTimer()
        self.last_fps_time = time.time()
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        main_layout = QVBoxLayout()

        # Title
        title_label = QLabel("SciCamera Control Panel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)

        # Create tabs
        self.tab_widget = QTabWidget()

        # Device tab
        self.device_tab = self.create_device_tab()
        self.tab_widget.addTab(self.device_tab, "Devices")

        # Acquisition tab
        self.acquisition_tab = self.create_acquisition_tab()
        self.tab_widget.addTab(self.acquisition_tab, "Acquisition")

        # Nodes tab
        self.nodes_tab = self.create_nodes_tab()
        self.tab_widget.addTab(self.nodes_tab, "Nodes")

        # Status tab
        self.status_tab = self.create_status_tab()
        self.tab_widget.addTab(self.status_tab, "Status")

        # Image display tab
        self.image_tab = self.create_image_tab()
        self.tab_widget.addTab(self.image_tab, "Image Preview")

        main_layout.addWidget(self.tab_widget)

        # Log area
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        self.setLayout(main_layout)

    def create_device_tab(self):
        """Create device management tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Device control buttons
        button_layout = QHBoxLayout()

        self.discover_btn = QPushButton("Discover Devices")
        self.discover_btn.clicked.connect(self.discover_devices)

        self.open_btn = QPushButton("Open Device")
        self.open_btn.clicked.connect(self.open_device)
        self.open_btn.setEnabled(False)

        self.close_btn = QPushButton("Close Device")
        self.close_btn.clicked.connect(self.close_device)
        self.close_btn.setEnabled(False)

        button_layout.addWidget(self.discover_btn)
        button_layout.addWidget(self.open_btn)
        button_layout.addWidget(self.close_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Device list
        device_group = QGroupBox("Available Devices")
        device_layout = QVBoxLayout()

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["Index", "Type", "Model", "Serial"])
        self.device_table.horizontalHeader().setStretchLastSection(True)
        self.device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.device_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.device_table.cellClicked.connect(self.on_device_selected)

        device_layout.addWidget(self.device_table)
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # Device info widget
        self.device_info_widget = DeviceInfoWidget()
        layout.addWidget(self.device_info_widget)

        widget.setLayout(layout)
        return widget

    def create_acquisition_tab(self):
        """Create image acquisition tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Grab settings
        settings_group = QGroupBox("Grab Settings")
        settings_layout = QVBoxLayout()

        # Timeout setting
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("Timeout (ms):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(100, 10000)
        self.timeout_spin.setValue(1000)
        self.timeout_spin.setSingleStep(100)
        timeout_layout.addWidget(self.timeout_spin)
        timeout_layout.addStretch()
        settings_layout.addLayout(timeout_layout)

        # Pixel format setting
        pixel_format_layout = QHBoxLayout()
        pixel_format_layout.addWidget(QLabel("Pixel Format:"))
        self.pixel_format_combo = QComboBox()
        self.pixel_format_combo.addItems(["Mono8", "RGB8", "BayerRG8", "BayerGR8", "BayerGB8", "BayerBG8"])
        self.pixel_format_combo.setCurrentIndex(0)
        pixel_format_layout.addWidget(self.pixel_format_combo)

        self.set_format_btn = QPushButton("Set Format")
        self.set_format_btn.clicked.connect(self.set_pixel_format_from_combo)
        pixel_format_layout.addWidget(self.set_format_btn)
        pixel_format_layout.addStretch()
        settings_layout.addLayout(pixel_format_layout)

        # Buffer count
        buffer_layout = QHBoxLayout()
        buffer_layout.addWidget(QLabel("Buffer Count:"))
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(1, 100)
        self.buffer_spin.setValue(10)
        buffer_layout.addWidget(self.buffer_spin)
        buffer_layout.addStretch()
        settings_layout.addLayout(buffer_layout)

        # Grab strategy
        strategy_layout = QHBoxLayout()
        strategy_layout.addWidget(QLabel("Grab Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["OneByOne", "Latest", "Upcoming"])
        self.strategy_combo.setCurrentIndex(0)
        strategy_layout.addWidget(self.strategy_combo)
        strategy_layout.addStretch()
        settings_layout.addLayout(strategy_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Acquisition control buttons
        acq_button_layout = QHBoxLayout()

        self.start_grab_btn = QPushButton("Start Grabbing")
        self.start_grab_btn.clicked.connect(self.start_grabbing)
        self.start_grab_btn.setEnabled(False)

        self.stop_grab_btn = QPushButton("Stop Grabbing")
        self.stop_grab_btn.clicked.connect(self.stop_grabbing)
        self.stop_grab_btn.setEnabled(False)

        self.single_grab_btn = QPushButton("Grab Single")
        self.single_grab_btn.clicked.connect(self.grab_single)
        self.single_grab_btn.setEnabled(False)

        acq_button_layout.addWidget(self.start_grab_btn)
        acq_button_layout.addWidget(self.stop_grab_btn)
        acq_button_layout.addWidget(self.single_grab_btn)
        acq_button_layout.addStretch()

        layout.addLayout(acq_button_layout)

        # Image info display
        image_group = QGroupBox("Image Information")
        image_layout = QVBoxLayout()

        self.image_info_text = QTextEdit()
        self.image_info_text.setReadOnly(True)
        self.image_info_text.setMaximumHeight(100)
        image_layout.addWidget(self.image_info_text)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group)

        # Save image button
        save_layout = QHBoxLayout()
        self.save_image_btn = QPushButton("Save Last Image")
        self.save_image_btn.clicked.connect(self.save_image)
        self.save_image_btn.setEnabled(False)
        save_layout.addWidget(self.save_image_btn)
        save_layout.addStretch()
        layout.addLayout(save_layout)

        widget.setLayout(layout)
        return widget

    def create_nodes_tab(self):
        """Create device nodes tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.node_widget = NodeTreeWidget(self.camera_worker)
        layout.addWidget(self.node_widget)

        widget.setLayout(layout)
        return widget

    def create_status_tab(self):
        """Create status monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # SDK version
        version_group = QGroupBox("SDK Information")
        version_layout = QVBoxLayout()

        self.version_label = QLabel("SDK Version: Unknown")
        version_layout.addWidget(self.version_label)

        self.get_version_btn = QPushButton("Get SDK Version")
        self.get_version_btn.clicked.connect(self.get_sdk_version)
        version_layout.addWidget(self.get_version_btn)

        version_group.setLayout(version_layout)
        layout.addWidget(version_group)

        # Device status
        status_group = QGroupBox("Device Status")
        status_layout = QVBoxLayout()

        self.device_status_label = QLabel("Device: Not Connected")
        status_layout.addWidget(self.device_status_label)

        self.camera_status_label = QLabel("Camera: Not Open")
        status_layout.addWidget(self.camera_status_label)

        self.grabbing_status_label = QLabel("Grabbing: Not Active")
        status_layout.addWidget(self.grabbing_status_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()

        self.fps_label = QLabel("FPS: 0.0")
        stats_layout.addWidget(self.fps_label)

        self.frame_count_label = QLabel("Frames Grabbed: 0")
        stats_layout.addWidget(self.frame_count_label)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        widget.setLayout(layout)
        return widget

    def create_image_tab(self):
        """Create image display tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Image display widget
        self.image_display = ImageDisplayWidget()
        layout.addWidget(self.image_display)

        # Image controls
        controls_layout = QHBoxLayout()

        self.auto_display_check = QCheckBox("Auto-display images")
        self.auto_display_check.setChecked(True)

        self.clear_image_btn = QPushButton("Clear Image")
        self.clear_image_btn.clicked.connect(self.clear_image_display)

        controls_layout.addWidget(self.auto_display_check)
        controls_layout.addWidget(self.clear_image_btn)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        widget.setLayout(layout)
        return widget

    def connect_signals(self):
        """Connect camera worker signals"""
        self.camera_worker.log_signal.connect(self.update_log)
        self.camera_worker.device_list_signal.connect(self.update_device_list)
        self.camera_worker.image_grabbed_signal.connect(self.on_image_grabbed)
        self.camera_worker.image_display_signal.connect(self.on_image_for_display)

        # Setup FPS timer
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)  # Update every second

    def discover_devices(self):
        """Discover available devices"""
        self.discover_btn.setEnabled(False)
        self.camera_worker.discovery_devices()
        self.discover_btn.setEnabled(True)

    def update_device_list(self, devices):
        """Update the device list table"""
        self.device_table.setRowCount(len(devices))

        for i, device in enumerate(devices):
            info = device['info']

            # Get device type
            dev_type = GetEnumName(SciCamDeviceType, info.devType) or "Unknown"

            # Get model name based on transfer type
            model_name = "Unknown"
            if info.tlType == SciCamTLType.SciCam_TLType_Gige:
                model_name = ''.join(chr(c) for c in info.info.gigeInfo.modelName if c != 0)
            elif info.tlType == SciCamTLType.SciCam_TLType_Usb3:
                model_name = ''.join(chr(c) for c in info.info.usb3Info.modelName if c != 0)
            elif info.tlType == SciCamTLType.SciCam_TLType_CL:
                model_name = ''.join(chr(c) for c in info.info.clInfo.cameraModel if c != 0)

            # Get serial number
            serial = "Unknown"
            if info.tlType == SciCamTLType.SciCam_TLType_Gige:
                serial = ''.join(chr(c) for c in info.info.gigeInfo.serialNumber if c != 0)
            elif info.tlType == SciCamTLType.SciCam_TLType_Usb3:
                serial = ''.join(chr(c) for c in info.info.usb3Info.serialNumber if c != 0)
            elif info.tlType == SciCamTLType.SciCam_TLType_CL:
                serial = ''.join(chr(c) for c in info.info.clInfo.cameraSerialNumber if c != 0)

            self.device_table.setItem(i, 0, QTableWidgetItem(str(i)))
            self.device_table.setItem(i, 1, QTableWidgetItem(dev_type))
            self.device_table.setItem(i, 2, QTableWidgetItem(model_name[:50]))
            self.device_table.setItem(i, 3, QTableWidgetItem(serial[:50]))

    def on_device_selected(self, row, column):
        """Handle device selection"""
        self.current_device_index = row
        self.device_info_widget.update_info(self.camera_worker.devices[row]['info'])
        self.open_btn.setEnabled(True)

    def open_device(self):
        """Open selected device"""
        if self.current_device_index >= 0:
            self.open_btn.setEnabled(False)
            success = self.camera_worker.open_device(self.current_device_index)

            if success:
                self.close_btn.setEnabled(True)
                self.start_grab_btn.setEnabled(True)
                self.single_grab_btn.setEnabled(True)
                self.device_status_label.setText("Device: Connected")
                self.camera_status_label.setText("Camera: Open")
            else:
                self.open_btn.setEnabled(True)

    def close_device(self):
        """Close current device"""
        self.camera_worker.close_device()
        self.close_btn.setEnabled(False)
        self.open_btn.setEnabled(True)
        self.start_grab_btn.setEnabled(False)
        self.stop_grab_btn.setEnabled(False)
        self.single_grab_btn.setEnabled(False)
        self.device_status_label.setText("Device: Not Connected")
        self.camera_status_label.setText("Camera: Not Open")
        self.grabbing_status_label.setText("Grabbing: Not Active")

    def start_grabbing(self):
        """Start continuous grabbing"""
        try:
            # Apply settings
            timeout = self.timeout_spin.value()
            buffer_count = self.buffer_spin.value()

            # Set grab strategy
            strategy_map = {"OneByOne": 0, "Latest": 1, "Upcoming": 2}
            strategy = strategy_map[self.strategy_combo.currentText()]

            # Start grabbing
            success = self.camera_worker.start_grabbing(timeout, buffer_count, strategy)
            if success:
                self.start_grab_btn.setEnabled(False)
                self.stop_grab_btn.setEnabled(True)
                self.single_grab_btn.setEnabled(False)
                self.grabbing_status_label.setText("Grabbing: Active")
            else:
                self.start_grab_btn.setEnabled(True)

        except Exception as e:
            self.update_log(f"Error starting grabbing: {str(e)}")
            self.start_grab_btn.setEnabled(True)

    def stop_grabbing(self):
        """Stop continuous grabbing"""
        try:
            success = self.camera_worker.stop_grabbing()
            if success:
                self.start_grab_btn.setEnabled(True)
                self.stop_grab_btn.setEnabled(False)
                self.single_grab_btn.setEnabled(True)
                self.grabbing_status_label.setText("Grabbing: Not Active")
            else:
                self.stop_grab_btn.setEnabled(True)

        except Exception as e:
            self.update_log(f"Error stopping grabbing: {str(e)}")
            self.stop_grab_btn.setEnabled(True)

    def grab_single(self):
        """Grab a single image"""
        self.single_grab_btn.setEnabled(False)

        # Use the timeout setting for single grab
        timeout = self.timeout_spin.value()
        image_data = self.camera_worker.grab_single_image(timeout)

        self.single_grab_btn.setEnabled(True)

        if image_data:
            self.save_image_btn.setEnabled(True)
            self.frame_count += 1
            self.frame_count_label.setText(f"Frames Grabbed: {self.frame_count}")

    def on_image_grabbed(self, payload_data):
        """Handle grabbed image"""
        self.frame_count += 1

        try:
            info_str = f"""
            <b>Frame ID:</b> {payload_data.get('frame_id', 0)}<br>
            <b>Timestamp:</b> {payload_data.get('timestamp', 0)}<br>
            <b>Resolution:</b> {payload_data.get('width', 0)} x {payload_data.get('height', 0)}<br>
            <b>Pixel Type:</b> {decode_pixel_type(payload_data.get('pixel_type', 0))}<br>
            """

            self.image_info_text.setText(info_str)
            self.last_payload = payload_data
        except Exception as e:
            self.update_log(f"Error updating image info: {str(e)}")

    def on_image_for_display(self, qimage):
        """Handle image for display"""
        try:
            if self.auto_display_check.isChecked() and qimage is not None:
                self.image_display.display_image(qimage)
                # Switch to image tab
                self.tab_widget.setCurrentWidget(self.image_tab)
        except Exception as e:
            self.update_log(f"Error displaying image: {str(e)}")

    def clear_image_display(self):
        """Clear the image display"""
        self.image_display.display_image(None)

    def update_fps(self):
        """Update FPS display"""
        current_time = time.time()
        elapsed = current_time - self.last_fps_time
        if elapsed > 0:
            fps = self.frame_count / elapsed
            self.fps_label.setText(f"FPS: {fps:.1f}")
        self.last_fps_time = current_time
        self.frame_count = 0

    def save_image(self):
        """Save the last grabbed image"""
        if not hasattr(self, 'last_payload') or self.last_payload is None:
            QMessageBox.warning(self, "Warning", "No image to save")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            f"image_frame_{self.last_payload.get('frame_id', 0)}.bmp",
            "BMP Files (*.bmp);;JPEG Files (*.jpg *.jpeg);;TIFF Files (*.tiff);;PNG Files (*.png);;All Files (*.*)"
        )
        if file_path:
            try:
                # Convert payload to QImage first
                qimage = convert_payload_to_qimage_robust(self.last_payload)
                if qimage and not qimage.isNull():
                    # Save the QImage
                    if qimage.save(file_path):
                        self.update_log(f"Image saved successfully: {file_path}")
                    else:
                        self.update_log(f"Failed to save image: {file_path}")
                else:
                    self.update_log("Failed to convert image for saving")

            except Exception as e:
                self.update_log(f"Error saving image: {str(e)}")

    def get_sdk_version(self):
        """Get SDK version information"""
        try:
            version = ctypes.c_uint(SciCamera.SciCam_GetSDKVersion())
            verMain = (version.value >> 24) & 0xff
            verSub = (version.value >> 16) & 0xff
            verRev = (version.value >> 8) & 0xff
            verTest = version.value & 0xff

            version_str = f"SDK Version: V{verMain}.{verSub}.{verRev}.{verTest}"
            self.version_label.setText(version_str)
            self.update_log(version_str)

        except Exception as e:
            self.update_log(f"Error getting SDK version: {str(e)}")

    def set_pixel_format_from_combo(self):
        """Set pixel format based on combo box selection"""
        format_name = self.pixel_format_combo.currentText()
        self.set_pixel_format(format_name)

    def set_pixel_format(self, format_name):
        """Set camera pixel format if supported"""
        try:
            if not self.camera_worker.camera:
                self.update_log("No camera connected")
                return False

            # Look for PixelFormat node
            nodesCount = ctypes.c_uint(0)
            reVal = self.camera_worker.camera.SciCam_GetNodes(None, nodesCount)

            if reVal == SCI_CAMERA_OK and nodesCount.value > 0:
                nodes = (SCI_CAM_NODE * nodesCount.value)()
                reVal = self.camera_worker.camera.SciCam_GetNodes(
                    ctypes.cast(nodes, PSCI_CAM_NODE).contents, nodesCount)

                if reVal == SCI_CAMERA_OK:
                    for i in range(nodesCount.value):
                        node = nodes[i]
                        node_name = node.name.decode() if node.name else ""
                        if "PixelFormat" in node_name or "PixelType" in node_name:
                            # Try to set the format
                            if node.type == SciCamNodeType.SciCam_NodeType_Enum:
                                eVal = SCI_NODE_VAL_ENUM()
                                reVal = self.camera_worker.camera.SciCam_GetEnumValueEx(
                                    SciCamDeviceXmlType.SciCam_DeviceXml_Camera,
                                    node_name, eVal)

                                if reVal == SCI_CAMERA_OK:
                                    # Look for desired format
                                    for j in range(eVal.itemCount):
                                        item_desc = eVal.items[j].desc.decode() if eVal.items[j].desc else ""
                                        if format_name in item_desc:
                                            # Set the format
                                            reVal = self.camera_worker.camera.SciCam_SetEnumValueEx(
                                                SciCamDeviceXmlType.SciCam_DeviceXml_Camera,
                                                node_name, eVal.items[j].val)

                                            if reVal == SCI_CAMERA_OK:
                                                self.update_log(f"Pixel format set to: {item_desc}")
                                                return True

            self.update_log(f"Could not set pixel format to {format_name}")
            return False

        except Exception as e:
            self.update_log(f"Error setting pixel format: {str(e)}")
            return False

    def update_log(self, message):
        """Update log display"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            log_entry = f"[{timestamp}] {message}"
            self.log_text.append(log_entry)

            # Auto-scroll to bottom
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            print(f"Error updating log: {e}")


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SciCamera Control Panel")
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget
        self.central_widget = CameraControlWidget()
        self.setCentralWidget(self.central_widget)

        # Create menu bar
        self.create_menu_bar()

        # Apply style
        self.apply_style()

    def create_menu_bar(self):
        """Create application menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

        # View menu
        view_menu = menubar.addMenu("View")

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self.show_about)

    def apply_style(self):
        """Apply stylesheet to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 2px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f9f9f9;
                gridline-color: #ddd;
            }
            QTableWidget::item:selected {
                background-color: #e0f7fa;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLabel {
                color: #333333;
            }
        """)

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About SciCamera Control Panel",
                          "SciCamera Control Panel\n\n"
                          "A PySide6-based GUI for SciCamera SDK\n"
                          "Provides control and monitoring for SciCamera devices")


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("SciCamera Control Panel")
    app.setOrganizationName("SciCamera")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
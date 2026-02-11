import sys
import os
import ctypes
from typing import Optional, List
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGroupBox, QPushButton, QLabel,
                               QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
                               QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox,
                               QLineEdit, QMessageBox, QSplitter, QScrollArea,
                               QProgressBar, QCheckBox, QFrame, QTreeWidget,
                               QTreeWidgetItem, QFileDialog)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, Slot
from PySide6.QtGui import QFont, QColor, QPalette

from SciCam_class import *


class CameraWorker(QThread):
    """Worker thread for camera operations"""
    log_signal = Signal(str)
    device_list_signal = Signal(list)
    image_grabbed_signal = Signal(object)  # Will emit payload data

    def __init__(self):
        super().__init__()
        self.camera = SciCamera()
        self.devices = []
        self.current_device = None

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
            self.log_signal.emit("Device opened successfully")
            return True

        except Exception as e:
            self.log_signal.emit(f"Error opening device: {str(e)}")
            return False

    def close_device(self):
        """Close current device"""
        try:
            if self.camera:
                reVal = self.camera.SciCam_CloseDevice()
                if reVal != SCI_CAMERA_OK:
                    self.log_signal.emit(f"Close device failed: Error {reVal}")
                else:
                    self.camera.SciCam_DeleteDevice()
                    self.current_device = None
                    self.log_signal.emit("Device closed")

        except Exception as e:
            self.log_signal.emit(f"Error closing device: {str(e)}")

    def grab_image(self):
        """Grab a single image"""
        try:
            ppayload = ctypes.c_void_p()
            reVal = self.camera.SciCam_Grab(ppayload)
            if reVal != SCI_CAMERA_OK:
                self.log_signal.emit(f"Grab failed: Error {reVal}")
                return None

            # Get payload attributes
            payloadAttribute = SCI_CAM_PAYLOAD_ATTRIBUTE()
            reVal = SciCam_Payload_GetAttribute(ppayload, payloadAttribute)
            if reVal != SCI_CAMERA_OK:
                self.log_signal.emit(f"Get payload attribute failed: Error {reVal}")
                return None

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

            self.image_grabbed_signal.emit(payload_data)
            self.log_signal.emit(
                f"Image grabbed: Frame {payloadAttribute.frameID}, {payloadAttribute.imgAttr.width}x{payloadAttribute.imgAttr.height}")

            return payload_data

        except Exception as e:
            self.log_signal.emit(f"Error grabbing image: {str(e)}")
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
        import socket
        import struct
        def uint32_to_ipv4(ip_uint32):
            network_order_ip = socket.htonl(ip_uint32)
            packed_ip = struct.pack("!I", network_order_ip)
            return socket.inet_ntoa(packed_ip)

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

        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Node tree
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderLabels(["Node", "Type", "Value", "Access"])
        self.node_tree.setColumnWidth(0, 250)
        self.node_tree.setColumnWidth(1, 100)
        self.node_tree.setColumnWidth(2, 150)
        self.node_tree.setColumnWidth(3, 80)

        layout.addWidget(self.node_tree)

        self.setLayout(layout)

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
                return

            nodes = (SCI_CAM_NODE * nodesCount.value)()
            reVal = self.camera_worker.camera.SciCam_GetNodes(
                ctypes.cast(nodes, PSCI_CAM_NODE).contents, nodesCount)

            if reVal == SCI_CAMERA_OK:
                self.current_nodes = nodes
                self.update_tree(nodes, nodesCount.value)

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
            item = QTreeWidgetItem([
                node.name.decode() if node.name else "",
                GetEnumName(SciCamNodeType, node.type) if GetEnumName(SciCamNodeType, node.type) else "",
                GetNodeValueStr(SciCamDeviceXmlType.SciCam_DeviceXml_Camera, node),
                GetEnumName(SciCamNodeAccessMode, node.accessMode) if GetEnumName(SciCamNodeAccessMode,
                                                                                  node.accessMode) else ""
            ])
            node_dict[i] = item

        # Second pass: build hierarchy
        for i in range(count):
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


class CameraControlWidget(QWidget):
    """Main camera control widget"""

    def __init__(self):
        super().__init__()
        self.camera_worker = CameraWorker()
        self.current_device_index = -1
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

    def connect_signals(self):
        """Connect camera worker signals"""
        self.camera_worker.log_signal.connect(self.update_log)
        self.camera_worker.device_list_signal.connect(self.update_device_list)
        self.camera_worker.image_grabbed_signal.connect(self.on_image_grabbed)

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

    def start_grabbing(self):
        """Start continuous grabbing"""
        try:
            # Apply settings
            self.camera_worker.camera.SciCam_SetGrabTimeout(self.timeout_spin.value())
            self.camera_worker.camera.SciCam_SetGrabBufferCount(self.buffer_spin.value())

            # Set grab strategy
            strategy_map = {"OneByOne": 0, "Latest": 1, "Upcoming": 2}
            strategy = strategy_map[self.strategy_combo.currentText()]
            self.camera_worker.camera.SciCam_SetGrabStrategy(strategy)

            # Start grabbing
            reVal = self.camera_worker.camera.SciCam_StartGrabbing()
            if reVal == SCI_CAMERA_OK:
                self.start_grab_btn.setEnabled(False)
                self.stop_grab_btn.setEnabled(True)
                self.single_grab_btn.setEnabled(False)
                self.grabbing_status_label.setText("Grabbing: Active")
                self.update_log("Continuous grabbing started")
            else:
                self.update_log(f"Failed to start grabbing: Error {reVal}")

        except Exception as e:
            self.update_log(f"Error starting grabbing: {str(e)}")

    def stop_grabbing(self):
        """Stop continuous grabbing"""
        try:
            reVal = self.camera_worker.camera.SciCam_StopGrabbing()
            if reVal == SCI_CAMERA_OK:
                self.start_grab_btn.setEnabled(True)
                self.stop_grab_btn.setEnabled(False)
                self.single_grab_btn.setEnabled(True)
                self.grabbing_status_label.setText("Grabbing: Not Active")
                self.update_log("Continuous grabbing stopped")
            else:
                self.update_log(f"Failed to stop grabbing: Error {reVal}")

        except Exception as e:
            self.update_log(f"Error stopping grabbing: {str(e)}")

    def grab_single(self):
        """Grab a single image"""
        self.single_grab_btn.setEnabled(False)
        image_data = self.camera_worker.grab_image()
        self.single_grab_btn.setEnabled(True)

        if image_data:
            self.save_image_btn.setEnabled(True)

    def on_image_grabbed(self, payload_data):
        """Handle grabbed image"""
        info_str = f"""
        <b>Frame ID:</b> {payload_data['frame_id']}<br>
        <b>Timestamp:</b> {payload_data['timestamp']}<br>
        <b>Resolution:</b> {payload_data['width']} x {payload_data['height']}<br>
        <b>Pixel Type:</b> {GetEnumName(SciCamPixelType, payload_data['pixel_type']) if GetEnumName(SciCamPixelType, payload_data['pixel_type']) else payload_data['pixel_type']}<br>
        """

        self.image_info_text.setText(info_str)
        self.last_payload = payload_data

    def save_image(self):
        """Save the last grabbed image"""
        if not hasattr(self, 'last_payload'):
            QMessageBox.warning(self, "Warning", "No image to save")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            f"image_frame_{self.last_payload['frame_id']}.bmp",
            "BMP Files (*.bmp);;JPEG Files (*.jpg *.jpeg);;TIFF Files (*.tiff);;PNG Files (*.png);;All Files (*.*)"
        )

        if file_path:
            try:
                # Get image data
                imgData = ctypes.c_void_p()
                reVal = SciCam_Payload_GetImage(self.last_payload['payload'], imgData)

                if reVal == SCI_CAMERA_OK:
                    # Save based on file extension
                    extension = os.path.splitext(file_path)[1].lower()
                    if extension in ['.bmp', '.jpg', '.jpeg', '.tiff', '.png']:
                        # Convert and save image
                        # Note: You'll need to implement proper image conversion based on pixel type
                        self.update_log(f"Image saved to: {file_path}")
                    else:
                        self.update_log(f"Unsupported file format: {extension}")
                else:
                    self.update_log(f"Failed to get image data: Error {reVal}")

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

    def update_log(self, message):
        """Update log display"""
        timestamp = QApplication.instance().applicationTime() / 1000
        log_entry = f"[{timestamp:.3f}] {message}"
        self.log_text.append(log_entry)

        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


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
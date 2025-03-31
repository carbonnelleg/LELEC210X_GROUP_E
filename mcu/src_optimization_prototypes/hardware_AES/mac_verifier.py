import sys
import time
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
import serial
import numpy as np

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QComboBox, QPushButton, 
                            QTextEdit, QLineEdit, QGridLayout, QGroupBox, QTabWidget)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6 import QtGui
from PyQt6.QtCore import Qt
import serial.tools.list_ports

from Crypto.Cipher import AES
from Crypto.Hash import CMAC

KEY = b'\x00' * 16
IV = b'\x00' * 16


class SerialReaderThread(QThread):
    data_received = pyqtSignal(str)
    
    def __init__(self, port, baud_rate):
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.running = False
        self.serial_port = None
    
    def run(self):
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            self.running = True
            self.data_received.emit(f"Connected to {self.port} at {self.baud_rate} baud\n")
            
            while self.running:
                if self.serial_port.in_waiting > 0:
                    try:
                        data = self.serial_port.readline().decode('utf-8')
                        self.data_received.emit(data)
                    except Exception as e:
                        self.data_received.emit(f"Error reading data: {str(e)}\n")
                        self.data_received.emit("Disconnected\n")
                        self.running = False
                        
                self.msleep(10)  # Short sleep to prevent high CPU usage
                
        except Exception as e:
            self.data_received.emit(f"Error: {str(e)}\n")
            self.data_received.emit("Disconnected\n")
        
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
    
    def stop(self):
        self.running = False
        self.wait(500)  # Wait for the thread to finish
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()


class UartReaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UART Reader")
        self.setGeometry(100, 100, 800, 800)
        self.serial_thread = None
        self.initUI()
        self.refresh_ports()
    
    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self.init_connection_settings(main_layout)
        self.init_tabs(main_layout)
    
    def init_connection_settings(self, layout):
        self.connection_group = QGroupBox("Connection Settings")
        connection_layout = QGridLayout()
        
        connection_layout.addWidget(QLabel("Port:"), 0, 0)
        self.port_combo = QComboBox()
        connection_layout.addWidget(self.port_combo, 0, 1)
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_ports)
        connection_layout.addWidget(refresh_button, 0, 2)
        
        connection_layout.addWidget(QLabel("Baud Rate:"), 1, 0)
        self.baud_combo = QComboBox()
        for baud in ["9600", "19200", "38400", "57600", "115200"]:
            self.baud_combo.addItem(baud)
        self.baud_combo.setCurrentText("115200")
        connection_layout.addWidget(self.baud_combo, 1, 1)
        
        connect_button = QPushButton("Connect")
        connect_button.clicked.connect(self.connect_disconnect)
        connection_layout.addWidget(connect_button, 1, 2)
        self.connect_button = connect_button
        
        self.connection_group.setLayout(connection_layout)
        layout.addWidget(self.connection_group)
    
    def init_tabs(self, layout):
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.init_console_tab()
        self.init_packet_tab()
        self.init_mel_tab()
    
    def init_console_tab(self):
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        
        # Serial console
        console_group = QGroupBox("Serial Console")
        console_layout_inner = QVBoxLayout()
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        console_layout_inner.addWidget(self.console)
        
        input_layout = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Type command to send...")
        self.input_line.returnPressed.connect(self.send_command)
        input_layout.addWidget(self.input_line)
        
        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_command)
        input_layout.addWidget(send_button)
        
        console_layout_inner.addLayout(input_layout)
        
        clear_button = QPushButton("Clear Console")
        clear_button.clicked.connect(self.console.clear)
        console_layout_inner.addWidget(clear_button)
        
        console_group.setLayout(console_layout_inner)
        console_layout.addWidget(console_group)
        
        console_widget.setLayout(console_layout)
        self.tabs.addTab(console_widget, "Console")
    
    def init_packet_tab(self):
        packet_widget = QWidget()
        packet_layout = QVBoxLayout(packet_widget)
        
        packet_group = QGroupBox("Packet Detector")
        packet_layout_inner = QVBoxLayout()

        # Status label
        self.packet_status = QLabel("Waiting for packet...")
        packet_layout_inner.addWidget(self.packet_status)
        self.packet_status.setStyleSheet("font-weight: bold; color: blue;")
        
        self.packet_display = QTextEdit()
        self.packet_display.setReadOnly(True)
        packet_layout_inner.addWidget(self.packet_display)
        self.packet_display.setPlaceholderText("Packet data will be displayed here")

        self.packet_tag = QLineEdit()
        self.packet_tag.setReadOnly(True)
        packet_layout_inner.addWidget(self.packet_tag)
        self.packet_tag.setPlaceholderText("Packet tag will be displayed here")

        self.passing_tag_tests = QGroupBox("Passing Tag Tests")
        self.passing_tag_tests_layout = QVBoxLayout()
        self.passing_tag_tests.setLayout(self.passing_tag_tests_layout)
        packet_layout_inner.addWidget(self.passing_tag_tests)

        self.cbc_tag_test = QLabel("CBC Tag \t: ...")
        self.passing_tag_tests_layout.addWidget(self.cbc_tag_test)
        self.cmac_tag_test = QLabel("CMAC Tag \t: ...")
        self.passing_tag_tests_layout.addWidget(self.cmac_tag_test)
        self.gmac_tag_test = QLabel("GMAC Tag \t: ...")
        self.passing_tag_tests_layout.addWidget(self.gmac_tag_test)
        
        packet_group.setLayout(packet_layout_inner)
        packet_layout.addWidget(packet_group)
        
        packet_widget.setLayout(packet_layout)
        self.tabs.addTab(packet_widget, "Packet Detector")

    def init_mel_tab(self):
        mel_widget = QWidget()
        mel_layout = QVBoxLayout(mel_widget)
        
        mel_group = QGroupBox("MEL Detector")
        mel_layout_inner = QVBoxLayout()
        
        # Status label
        self.mel_status = QLabel("Waiting for MEL...")
        mel_layout_inner.addWidget(self.mel_status)
        self.mel_status.setStyleSheet("font-weight: bold; color: blue;")
        self.mel_status.setFixedHeight(20)
        
        # MEL display (image)
        self.mel_display = QImage()
        self.mel_display_label = QLabel()
        mel_layout_inner.addWidget(self.mel_display_label)

        # Display blank image
        blank_image = np.zeros((20, 20), dtype=np.uint8)
        image = QImage(blank_image.data, blank_image.shape[1], blank_image.shape[0], blank_image.shape[1], QImage.Format.Format_Grayscale8)
        pixmap = QPixmap.fromImage(image)
        self.mel_display_label.setPixmap(pixmap)

        # Make the image take as much space as possible
        self.mel_display_label.setScaledContents(True)
        self.mel_display_label.setFixedSize(400, 400)

        mel_group.setLayout(mel_layout_inner)
        mel_layout.addWidget(mel_group)

        mel_widget.setLayout(mel_layout)
        self.tabs.addTab(mel_widget, "MEL Detector")

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in sorted(ports):
            self.port_combo.addItem(f"{port.device} - {port.description}")
    
    def connect_disconnect(self):
        if self.serial_thread and self.serial_thread.running:
            self.disconnect()
        else:
            self.connect()
    
    def connect(self):
        if not self.port_combo.currentText():
            self.console.append("Error: No port selected\n")
            return
        
        port = self.port_combo.currentText().split(" - ")[0]
        baud_rate = int(self.baud_combo.currentText())
        
        self.serial_thread = SerialReaderThread(port, baud_rate)
        self.serial_thread.data_received.connect(self.update_console)
        self.serial_thread.start()
        
        self.connect_button.setText("Disconnect")
        self.port_combo.setEnabled(False)
        self.baud_combo.setEnabled(False)

        self.connection_group.setTitle(f"Connection Settings (Connected to {port} at {baud_rate} baud)")
    
    def disconnect(self):
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread = None
        
        self.connect_button.setText("Connect")
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.console.append("Disconnected\n")

        self.connection_group.setTitle("Connection Settings")
    
    @pyqtSlot(str)
    def update_console(self, data):
        self.console.append(data)
        # Auto-scroll to the bottom
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        # Limit the number of lines in the console
        if self.console.document().lineCount() > 1000:
            cursor = self.console.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            cursor.select(QtGui.QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
            self.console.setTextCursor(cursor)
        
        if data.startswith("DF:HEX:"):
            self.process_packet_hex(data)
        
        if "Disconnected" in data:
            self.disconnect()

    def process_packet_hex(self, data):
        hex_str = data.split("DF:HEX:")[1].strip()
        try:
            packet = bytes.fromhex(hex_str)
            self.packet_display.setText(packet[:-16].hex())
            self.packet_tag.setText(packet[-16:].hex())
            self.packet_status.setText("Packet received")
            self.packet_status.setStyleSheet("font-weight: bold; color: green;")
        except Exception as e:
            self.packet_display.setText("")
            self.packet_tag.setText("")
            self.packet_status.setText("Error processing packet")
            self.packet_status.setStyleSheet("font-weight: bold; color: red;")
            self.console.append(f"Error processing packet: {str(e)}\n")

        # Perform tag tests
        self.perform_tag_tests(packet)

        # Update the MEL
        self.update_mel(hex_str)

    def perform_tag_tests(self, packet):
        # Perform CBC-MAC test
        cbc_tag = packet[-16:]
        cbc_tag_compute = self.compute_cbc_mac(packet[:-16])
        cbc_tag_pass = cbc_tag == cbc_tag_compute
        self.cbc_tag_test.setText(f"CBC Tag \t: {cbc_tag_compute.hex()}")
        self.cbc_tag_test.setStyleSheet("color: green;" if cbc_tag_pass else "color: red;")

        # Perform CMAC test
        cmac_tag = packet[-16:]
        cmac_tag_compute = self.compute_cmac(packet[:-16])
        cmac_tag_pass = cmac_tag == cmac_tag_compute
        self.cmac_tag_test.setText(f"CMAC Tag \t: {cmac_tag_compute.hex()}")
        self.cmac_tag_test.setStyleSheet("color: green;" if cmac_tag_pass else "color: red;")

        # Perform GMAC test
        gmac_tag = packet[-16:]
        gmac_tag_compute = self.compute_gmac(packet[:-16])
        gmac_tag_pass = gmac_tag == gmac_tag_compute
        self.gmac_tag_test.setText(f"GMAC Tag \t: {gmac_tag_compute.hex()}")
        self.gmac_tag_test.setStyleSheet("color: green;" if gmac_tag_pass else "color: red;")

    def compute_cbc_mac(self, message):
        # Pad message to multiple of 16 bytes
        padded_len = ((len(message) + 15) // 16) * 16
        padded_msg = message + b'\x00' * (padded_len - len(message))
        
        # Use CBC mode with zero IV
        zero_iv = bytes([0] * 16)
        cipher = AES.new(KEY, AES.MODE_CBC, zero_iv)
        ciphertext = cipher.encrypt(padded_msg)
        
        # Return the last block as the tag
        return ciphertext[-16:]
    
    def compute_cmac(self, message):
        cmac = CMAC.new(KEY, ciphermod=AES)
        cmac.update(message)
        return cmac.digest()
    
    def compute_gmac(self, message):
        cipher = AES.new(KEY, AES.MODE_GCM, nonce=IV)
        cipher.update(message)
        return cipher.digest()

    def update_mel(self, hex_str):
        decode_hex = bytes.fromhex(hex_str)
        dt = np.dtype(np.uint16)
        dt = dt.newbyteorder("<")
        message = np.frombuffer(decode_hex[8:-16], dtype=dt)

        # Interpret the message as a sequence of rows
        size = int(np.sqrt(len(message)))
        reshaped_message = message[:size*size].reshape(size, size)

        # Copy with a transpose
        new_message = np.zeros((size, size), dtype=np.uint16)
        for i in range(size):
            for j in range(size):
                new_message[i, j] = reshaped_message[j, i]

        reshaped_message = new_message[::-1]

        # Check if the message is a MEL
        if True:
            self.mel_status.setText("MEL received")
            self.mel_status.setStyleSheet("font-weight: bold; color: green;")
            self.update_mel_image(reshaped_message)
        else:
            self.mel_status.setText("Waiting for MEL...")
            self.mel_status.setStyleSheet("font-weight: bold; color: blue;")

    def update_mel_image(self, reshaped_message):
        # Convert to 8-bit unsigned integer
        reshaped_message = reshaped_message.astype(np.uint8)
        # Normalize the data to 0-255
        reshaped_message = (reshaped_message / reshaped_message.max() * 255).astype(np.uint8)
        # Create a grayscale image
        height, width = reshaped_message.shape
        bytes_per_line = width
        image = QImage(reshaped_message.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8)
        pixmap = QPixmap.fromImage(image)
        self.mel_display_label.setPixmap(pixmap.scaled(self.mel_display_label.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio, transformMode=Qt.TransformationMode.FastTransformation))
    
    def send_command(self):
        if not self.serial_thread or not self.serial_thread.running:
            self.console.append("Error: Not connected\n")
            return
        
        command = self.input_line.text()
        if command:
            try:
                self.serial_thread.serial_port.write((command + '\r\n').encode('utf-8'))
                self.console.append(f"Sent: {command}\n")
                self.input_line.clear()
            except Exception as e:
                self.console.append(f"Error sending command: {str(e)}\n")
    
    def closeEvent(self, event):
        if self.serial_thread:
            self.serial_thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UartReaderApp()
    window.show()
    sys.exit(app.exec())
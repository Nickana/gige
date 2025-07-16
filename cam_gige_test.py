import os.path
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import cv2
import numpy as np
from PySide2 import QtWidgets, QtGui
from PySide2.QtCore import QThread, Signal, Qt, QSize
from PySide2.QtGui import QPixmap, QImage, QFont
from PySide2.QtWidgets import QSizePolicy
from harvesters.core import Harvester, ImageAcquirer

from definitions import SAVE_IMAGE_PATH, IMG_DISCONNECTED, LIBRARY_SMARTEK_PATH, ICON_PATH

font = cv2.FONT_HERSHEY_SIMPLEX


class VideoWorker(QThread):
    image_signal1 = Signal(QPixmap)
    image_signal2 = Signal(QPixmap)
    image_signal3 = Signal(QPixmap)
    status_cam_str = Signal(str)
    total_save_frames = Signal(int)
    current_frames = Signal(int)
    paused_stream_signal = Signal(bool)
    stop_signal = Signal()
    save_images_path = Signal(str)
    FPS = Signal(str)

    def __init__(self):
        super().__init__()

        self.h = Harvester()
        self.h.add_file(LIBRARY_SMARTEK_PATH)
        self.h.update()
        self.devises = self.h.device_info_list
        # print(self.devises)
        self.devises_connected = []
        self.stop_signal.connect(self.stop_stream)
        self.streaming = True
        print('sssssssssssssssssssss')
        self.images_history = []
        self.current_image_frame_index = 0
        self.pause_stream = False
        self.ia1 = None
        self.img_size_w_h = None
        self.grab_color_image = False
        self.get_grab_color_image()

    def get_grab_color_image(self):
        # Загружаем XML-файл
        tree = ET.parse("settings.xml")
        # Получаем корневой элемент
        root = tree.getroot()
        ColorImage = int(root.find("genicam/ColorImage").text)
        if ColorImage == 0:
            self.grab_color_image = False
        else:
            self.grab_color_image = True
        print('image: ', self.grab_color_image)
    def connect_devices(self):
        for i in self.devises_connected:
            i.get('ia').stop()
            i.get('ia').destroy()

        self.devises_connected.clear()

        try:
            self.h.update()
            self.devises = self.h.device_info_list
        except Exception as e:
            print(e)
            self.status_cam_str.emit('\n Device not found')

        for i in self.devises:
            try:
                ia = self.h.create(i)
                self.set_ia_devices_settings(ia)
                ia.start()
                self.devises_connected.append({'ia': ia, 'sn': i.serial_number})
            except Exception as e:
                self.status_cam_str.emit('\n Device not connected')
                print('cam connection error', e)
        print(self.devises_connected)

        if self.devises_connected:
            device_connected_str = 'Device connected: '
            for j in self.devises_connected:
                device_connected_str += '\n' + j.get('sn')
            self.status_cam_str.emit(device_connected_str)
            print(device_connected_str)

    def stop_stream(self):
        self.streaming = False
        self.wait()

    def numpy2pixmap(self, np_array: np.array) -> QPixmap:
        np_array = np_array[..., ::-1].copy()
        height, width, channel = np_array.shape
        bytesPerLine = 3 * width
        qImg = QImage(np_array.data, width, height, bytesPerLine, QImage.Format_RGB888)
        pixmap_img = QtGui.QPixmap(QImage(qImg))
        return pixmap_img

    def grab_image_ia(self, ia: ImageAcquirer, sn):
        if ia is None:
            return cv2.imread(IMG_DISCONNECTED)
        current_time = datetime.now().strftime("%H:%M:%S")

        try:
            ia.remote_device.node_map.TriggerSoftware.execute()
            with ia.fetch(timeout=1) as buffer:
                component = buffer.payload.components[0]
                _2d = component.data.reshape(component.height, component.width)
                if self.grab_color_image:
                    image = cv2.cvtColor(_2d, cv2.COLOR_BayerGR2RGB)
                else:
                    image = cv2.cvtColor(_2d, cv2.COLOR_GRAY2RGB)
                resize = cv2.resize(image, self.img_size_w_h)
                cv2.putText(resize, current_time, (20, 100), font, 1, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.putText(resize, sn, (20, 40), font, 1, (0, 0, 255), 2, cv2.LINE_AA)
                image = resize
                ia._release_buffers()
                buffer.queue()

        except Exception as e:
            image = cv2.imread(IMG_DISCONNECTED)
            print(e)
            self.devises_connected = []

        return image

    def show_prev_frames(self):

        self.current_image_frame_index -= 1
        self.current_frames.emit(self.current_image_frame_index)
        images = self.images_history[self.current_image_frame_index]
        for index111, i in enumerate(images):
            if index111 == 0:
                self.image_signal1.emit(self.numpy2pixmap(i))
            if index111 == 1:
                self.image_signal2.emit(self.numpy2pixmap(i))
            if index111 == 2:
                self.image_signal3.emit(self.numpy2pixmap(i))

    def show_next_frames(self):
        self.current_image_frame_index += 1
        print(self.current_image_frame_index, '/', len(self.images_history))
        self.current_frames.emit(self.current_image_frame_index)
        if self.current_image_frame_index <= 0:
            self.current_image_frame_index = 1
        images = self.images_history[self.current_image_frame_index - 1]
        for index111, i in enumerate(images):
            if index111 == 0:
                self.image_signal1.emit(self.numpy2pixmap(i))
            if index111 == 1:
                self.image_signal2.emit(self.numpy2pixmap(i))
            if index111 == 2:
                self.image_signal3.emit(self.numpy2pixmap(i))

    def get_frames_by_index(self, index_frame):
        if self.images_history:
            images = self.images_history[index_frame - 1]
            str_save_path = 'Фото сохранены в:'
            for index, i in enumerate(images):
                # filename = f'C:\PyCharmProject\smartekGigECam\save_images\{datetime.now().strftime("%H_%M_%S_%f")}_{str(index)}.jpg'
                filename = os.path.join(SAVE_IMAGE_PATH, f'{datetime.now().strftime("%H_%M_%S_%f")}_{str(index)}.jpg')
                print(filename)
                cv2.imwrite(filename, i)
                str_save_path += '\n ' + filename

            self.save_images_path.emit(str_save_path)

    def run(self):
        status_navigator_button = False
        self.connect_devices()

        # Загружаем XML-файл
        tree = ET.parse("settings.xml")

        # Получаем корневой элемент
        root = tree.getroot()
        sleep_frame = float(root.find("genicam/sleepFrame").text)

        while self.streaming:
            start_time = time.time()
            FPS = 0
            status = False
            if not self.devises_connected:
                print('device connected...')
                self.status_cam_str.emit('device connected...')
                self.connect_devices()
                self.image_signal1.emit(self.numpy2pixmap(cv2.imread(IMG_DISCONNECTED)))
                self.image_signal2.emit(self.numpy2pixmap(cv2.imread(IMG_DISCONNECTED)))
                self.image_signal3.emit(self.numpy2pixmap(cv2.imread(IMG_DISCONNECTED)))
                time.sleep(1)

            if not self.pause_stream and self.devises_connected:
                all_cam_frames = []
                status_navigator_button = False
                status = True

                for index111, i in enumerate(self.devises_connected):
                    img = self.grab_image_ia(i.get('ia'), i.get('sn'))
                    all_cam_frames.append(img)

                    def img_to_signal():
                        if index111 == 0:
                            self.image_signal1.emit(self.numpy2pixmap(img))
                        if index111 == 1:
                            self.image_signal2.emit(self.numpy2pixmap(img))
                        if index111 == 2:
                            self.image_signal3.emit(self.numpy2pixmap(img))

                    img_to_signal()
                if len(self.images_history) > 30:
                    self.images_history.pop(0)
                self.images_history.append(all_cam_frames)
                self.current_image_frame_index = len(self.images_history)
                self.total_save_frames.emit(len(self.images_history))
                self.current_frames.emit(self.current_image_frame_index)
                time.sleep(sleep_frame)

            else:
                print('pause...')
                if not status_navigator_button:
                    self.paused_stream_signal.emit(True)
                    status_navigator_button = True
                if len(self.images_history) > 0 and (self.current_image_frame_index > 0) and self.pause_stream:
                    self.paused_stream_signal.emit(True)
                time.sleep(1)


            if status:
                end_time = time.time()
                FPS = round(1 / (end_time - start_time), 2)
            self.FPS.emit(f'FPS: {FPS}')
            # print(self.images_history)

    def set_ia_devices_settings(self, ia_device):
        # Загружаем XML-файл
        tree = ET.parse("settings.xml")

        # Получаем корневой элемент
        root = tree.getroot()

        exposure_time = root.find("genicam/ExposureTime")
        Gain = float(root.find("genicam/Gain").text)
        GainGreen = float(root.find("genicam/GainGreen").text)
        GainRed = float(root.find("genicam/GainRed").text)
        GainBlue = float(root.find("genicam/GainBlue").text)
        CoefW = float(root.find("genicam/CoefW").text) + 0.01
        CoefH = float(root.find("genicam/CoefH").text) + 0.01
        Width = int(root.find("genicam/Width").text)
        Height = int(root.find("genicam/Height").text)
        OffsetX = int(root.find("genicam/OffsetX").text)
        OffsetY = int(root.find("genicam/OffsetY").text)
        MaxWidthAndHeight = int(root.find("genicam/MaxWidthAndHeight").text)
        # print('ExposureTime:', exposure_time.text)
        try:
            ia_device.remote_device.node_map.GainSelector.value = 'All'
            ia_device.remote_device.node_map.Gain.value = Gain
        except Exception as e:
            print('Set Gain value error')

        if self.grab_color_image:
            ia_device.remote_device.node_map.PixelFormat.value = 'BayerGR8'
            ia_device.remote_device.node_map.GainSelector.value = 'Red'
            ia_device.remote_device.node_map.Gain.value = GainRed
            ia_device.remote_device.node_map.GainSelector.value = 'Green'
            ia_device.remote_device.node_map.Gain.value = GainGreen
            ia_device.remote_device.node_map.GainSelector.value = 'Blue'
            ia_device.remote_device.node_map.Gain.value = GainBlue
        else:
            ia_device.remote_device.node_map.PixelFormat.value = 'Mono8'

        if MaxWidthAndHeight == 1:
            ia_device.remote_device.node_map.OffsetX.value = 0
            ia_device.remote_device.node_map.OffsetY.value = 0
            max_width, max_height = ia_device.remote_device.node_map.WidthMax.value, ia_device.remote_device.node_map.HeightMax.value
            print(max_width, max_height)
            ia_device.remote_device.node_map.Width.value = max_width
            ia_device.remote_device.node_map.Height.value = max_height
        else:
            try:
                ia_device.remote_device.node_map.Width.value = Width
                ia_device.remote_device.node_map.Height.value = Height
                ia_device.remote_device.node_map.OffsetX.value = OffsetX
                ia_device.remote_device.node_map.OffsetY.value = OffsetY
            except Exception as e:
                self.save_images_path.emit('ПРОВЕРЬТЕ НАСТРОЙКИ XML: \n Width, Height, OffsetX, OffsetY')

        # print("\n".join([x for x in dir(ia_device.remote_device.node_map)]))

        # ia_device.remote_device.node_map.MaxResendPacketRetry.value = 10
        print(ia_device.remote_device.node_map.device_info)
        print(ia_device.remote_device.node_map.PixelFormat.symbolics)
        ia_device.remote_device.node_map.AcquisitionFrameRate.value = 0
        ia_device.remote_device.node_map.ExposureTime.value = float(exposure_time.text)
        print(ia_device.remote_device.node_map.ExposureTime.value)
        print(ia_device.remote_device.node_map.AcquisitionFrameRate.value)
        ia_device.remote_device.node_map.AcquisitionMode.value = 'Continuous'

        ia_device.remote_device.node_map.TriggerMode.value = 'On'
        ia_device.remote_device.node_map.TriggerSource.value = 'Software'

        print(ia_device.remote_device.node_map.Width.value)
        print(ia_device.remote_device.node_map.Height.value)

        self.img_size_w_h = int(ia_device.remote_device.node_map.Width.value / CoefW), int(
            ia_device.remote_device.node_map.Height.value / CoefH)



class VideoWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # Загружаем XML-файл
        tree = ET.parse("settings.xml")
        # Получаем корневой элемент
        root = tree.getroot()
        WidthUI = int(root.find("genicam/WidthUI").text)
        HeightUI = int(root.find("genicam/HeightUI").text)
        minimum_size = (WidthUI, HeightUI)
        icon = QPixmap(ICON_PATH)
        icon = icon.scaled(QSize(50, 50))
        self.setWindowIcon(QPixmap(icon))
        self.setWindowTitle("Видео с камер")
        self.current_frames_int = 0
        self.total_frames_int = 0
        self.pause_stream = False

        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)

        self.layout = QtWidgets.QGridLayout()
        self.main_widget.setLayout(self.layout)

        self.label = QtWidgets.QLabel()
        self.label.setStyleSheet("background-color: rgb(0, 127, 127);")

        self.label2 = QtWidgets.QLabel()
        self.label2.setStyleSheet("background-color: rgb(127, 127, 0);")

        self.label3 = QtWidgets.QLabel()
        self.label3.setStyleSheet("background-color: rgb(127, 127, 255);")

        self.label4 = QtWidgets.QLabel()
        self.label4.setStyleSheet("background-color: rgb(0, 127, 0);")

        self.label.setMinimumSize(*minimum_size)
        self.label2.setMinimumSize(*minimum_size)
        self.label3.setMinimumSize(*minimum_size)
        self.label4.setMinimumSize(*minimum_size)

        self.video_worker1 = VideoWorker()
        self.video_worker1.image_signal1.connect(self.update_frame_cam1)
        self.video_worker1.image_signal2.connect(self.update_frame_cam2)
        self.video_worker1.image_signal3.connect(self.update_frame_cam3)
        # self.video_worker1.pause_video_signal.connect(self.set_state_frame_navigator_buttons)

        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        horizontalSpacer = QtWidgets.QSpacerItem(20, 40, QSizePolicy.Expanding, QSizePolicy.Minimum)
        horizontalSpacer2 = QtWidgets.QSpacerItem(20, 40, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout.addWidget(self.label, 0, 1)
        self.layout.addWidget(self.label2, 0, 2)
        self.layout.addWidget(self.label3, 1, 1)
        self.layout.addItem(horizontalSpacer, 0, 0)
        self.layout.addItem(horizontalSpacer2, 0, 3)

        self.layout_vertical = QtWidgets.QVBoxLayout()
        self.layout_frame_navigator = QtWidgets.QHBoxLayout()

        self.prev_frame_button = QtWidgets.QPushButton('<')
        self.prev_frame_button.setFont(QFont('Arial', 15))
        self.prev_frame_button.clicked.connect(self.prev_frame_button_clicked)

        self.next_frame_button = QtWidgets.QPushButton('>')
        self.next_frame_button.setFont(QFont('Arial', 15))
        self.next_frame_button.clicked.connect(self.next_frame_button_clicked)

        self.current_frame_label = QtWidgets.QLabel()
        self.current_FPS = QtWidgets.QLabel()
        self.video_worker1.FPS.connect(lambda x: self.current_FPS.setText(x))
        self.layout_frame_FPS = QtWidgets.QHBoxLayout()
        self.layout_frame_FPS.addWidget(self.current_frame_label)
        self.layout_frame_FPS.addWidget(self.current_FPS)
        self.current_frame_label.setText('Текущий кадр: ')

        self.total_frames_label = QtWidgets.QLabel()
        self.total_frames_label.setText('Всего сохранено кадров: ')

        self.layout_frame_navigator.addWidget(self.prev_frame_button)
        self.layout_frame_navigator.addWidget(self.next_frame_button)

        self.button_pause_stream = QtWidgets.QPushButton('Остановить')
        self.button_pause_stream.setFont(QFont('Arial', 15))

        self.button_save_frames = QtWidgets.QPushButton('Сохранить \n изображение')
        self.button_save_frames.setFont(QFont('Arial', 15))
        self.button_save_frames.clicked.connect(
            lambda x: self.video_worker1.get_frames_by_index(self.current_frames_int))

        self.button_pause_stream.clicked.connect(self.pause_video_worker)

        self.button_play_stream = QtWidgets.QPushButton('Возобновить')
        self.button_play_stream.setFont(QFont('Arial', 15))

        self.button_play_stream.clicked.connect(self.play_video_worker)

        self.reconnect_all_cam = QtWidgets.QPushButton('Переподключить \n все камеры')
        self.reconnect_all_cam.setFont(QFont('Arial', 15))

        self.reconnect_all_cam.clicked.connect(self.reconnect_thread_cam)

        self.label_save_path = QtWidgets.QLabel()

        self.status_cam_label = QtWidgets.QLabel()

        self.video_worker1.save_images_path.connect(self.set_save_images_show)

        self.video_worker1.status_cam_str.connect(self.set_status_cam_label)

        self.layout_vertical.addWidget(self.button_pause_stream)
        self.layout_vertical.addWidget(self.button_play_stream)
        self.layout_vertical.addLayout(self.layout_frame_navigator)
        self.layout_vertical.addLayout(self.layout_frame_FPS)
        self.layout_vertical.addWidget(self.total_frames_label)
        self.layout_vertical.addWidget(self.reconnect_all_cam)
        self.layout_vertical.addWidget(self.button_save_frames)
        self.layout_vertical.addWidget(self.label_save_path)
        self.layout_vertical.addWidget(self.status_cam_label)
        self.layout_vertical.addStretch()
        self.layout.addLayout(self.layout_vertical, 1, 2)

        self.button_play_stream.setVisible(False)
        self.video_worker1.total_save_frames.connect(self.set_total_frames)
        self.video_worker1.current_frames.connect(self.set_current_frames)
        self.video_worker1.paused_stream_signal.connect(self.enable_prev_frame_button)
        # self.set_status_cam_label('2222222222222222')
        self.video_worker1.start()

    def set_save_images_show(self, str_path):
        self.label_save_path.setText(str_path)

    def set_status_cam_label(self, str_status):
        self.status_cam_label.setText(str_status)

    def reconnect_thread_cam(self):
        self.video_worker1.devises_connected = []

    def enable_prev_frame_button(self, signasad):
        self.prev_frame_button.setEnabled(signasad)

    def set_current_frames(self, current_frames):

        # self.next_frame_button.setEnabled(True)

        self.current_frames_int = current_frames
        self.current_frame_label.setText(f'Текущий кадр: {current_frames} / {self.total_frames_int}')
        # print(current_frames)
        if (current_frames >= 1) and self.pause_stream:
            self.prev_frame_button.setEnabled(True)
        else:
            self.prev_frame_button.setEnabled(False)
        if current_frames >= self.total_frames_int:
            self.next_frame_button.setEnabled(False)
        else:
            self.next_frame_button.setEnabled(True)

    def set_total_frames(self, total_frames):
        self.total_frames_int = total_frames
        self.total_frames_label.setText(f'Всего сохранено кадров: {total_frames}')

    def pause_video_worker(self):
        self.pause_stream = True
        self.video_worker1.pause_stream = True
        self.button_pause_stream.setVisible(False)
        self.button_play_stream.setVisible(True)

    def play_video_worker(self):
        self.pause_stream = False
        self.video_worker1.pause_stream = False
        self.button_pause_stream.setVisible(True)
        self.button_play_stream.setVisible(False)

    def next_frame_button_clicked(self):
        self.video_worker1.show_next_frames()

    def prev_frame_button_clicked(self):
        self.video_worker1.show_prev_frames()

    def update_frame_cam1(self, image: QtGui.QPixmap):
        self.label.setPixmap(image.scaled(self.label.width(), self.label.height(), Qt.KeepAspectRatio))

    def update_frame_cam2(self, image: QtGui.QPixmap):
        self.label2.setPixmap(image.scaled(self.label.width(), self.label.height(), Qt.KeepAspectRatio))

    def update_frame_cam3(self, image: QtGui.QPixmap):
        self.label3.setPixmap(image.scaled(self.label.width(), self.label.height(), Qt.KeepAspectRatio))

    def closeEvent(self, event):
        self.video_worker1.stop_signal.emit()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = VideoWindow()
    window.show()
    sys.exit(app.exec_())

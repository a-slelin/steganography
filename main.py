import sys
import struct
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QTextEdit,
                             QFileDialog, QMessageBox)
from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtCore import Qt

class SteganoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LSB стеганография в палитре PNG (PLTE)")
        self.setGeometry(100, 100, 900, 600)

        # Переменные для хранения изображений
        self.original_image = None      # QImage исходного
        self.stego_image = None         # QImage со встроенным сообщением

        # Центральный виджет и главный layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Верхняя панель с кнопками
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Загрузить изображение")
        self.btn_load.clicked.connect(self.load_image)
        self.btn_save = QPushButton("Сохранить стего-изображение")
        self.btn_save.clicked.connect(self.save_stego_image)
        self.btn_embed = QPushButton("Встроить сообщение")
        self.btn_embed.clicked.connect(self.embed_message)
        self.btn_extract = QPushButton("Извлечь сообщение")
        self.btn_extract.clicked.connect(self.extract_message)
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_embed)
        btn_layout.addWidget(self.btn_extract)
        main_layout.addLayout(btn_layout)

        # Горизонтальная область для двух изображений
        images_layout = QHBoxLayout()
        # Исходное изображение
        self.original_label = QLabel("Исходное изображение")
        self.original_label.setAlignment(Qt.AlignCenter)
        self.original_label.setMinimumSize(300, 300)
        self.original_label.setStyleSheet("border: 1px solid gray;")
        # Стего-изображение
        self.stego_label = QLabel("Изображение со стеганограммой")
        self.stego_label.setAlignment(Qt.AlignCenter)
        self.stego_label.setMinimumSize(300, 300)
        self.stego_label.setStyleSheet("border: 1px solid gray;")
        images_layout.addWidget(self.original_label)
        images_layout.addWidget(self.stego_label)
        main_layout.addLayout(images_layout)

        # Текстовая область для сообщения
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Введите сообщение для встраивания...")
        self.message_input.setMaximumHeight(100)
        main_layout.addWidget(self.message_input)

        # Область для извлечённого сообщения
        self.extracted_output = QTextEdit()
        self.extracted_output.setPlaceholderText("Здесь будет извлечённое сообщение...")
        self.extracted_output.setMaximumHeight(100)
        self.extracted_output.setReadOnly(True)
        main_layout.addWidget(self.extracted_output)

        # Статусная строка
        self.statusBar().showMessage("Готов")

    def load_image(self):
        """Загрузить изображение из файла, конвертировать в палитровое."""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Открыть PNG изображение", "", "PNG Files (*.png)")
        if not file_name:
            return

        # Загружаем изображение
        img = QImage(file_name)
        if img.isNull():
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить изображение.")
            return

        # Если изображение не палитровое (Indexed8), конвертируем
        if img.format() != QImage.Format_Indexed8:
            img = img.convertToFormat(QImage.Format_Indexed8)
            if img.isNull():
                QMessageBox.critical(self, "Ошибка", "Не удалось преобразовать изображение к палитровому формату.")
                return
            self.statusBar().showMessage("Изображение преобразовано в палитровый формат (256 цветов).")

        self.original_image = img
        self.stego_image = None
        self.display_image(self.original_label, self.original_image)
        self.stego_label.clear()
        self.extracted_output.clear()
        self.statusBar().showMessage(f"Загружено: {file_name}")

    def save_stego_image(self):
        """Сохранить текущее стего-изображение в файл."""
        if self.stego_image is None:
            QMessageBox.warning(self, "Предупреждение", "Нет стего-изображения для сохранения.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить изображение", "", "PNG Files (*.png)")
        if not file_name:
            return

        if self.stego_image.save(file_name, "PNG"):
            self.statusBar().showMessage(f"Сохранено: {file_name}")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить изображение.")

    def embed_message(self):
        """Встроить текст из поля ввода в палитру изображения."""
        if self.original_image is None:
            QMessageBox.warning(self, "Предупреждение", "Сначала загрузите изображение.")
            return

        message = self.message_input.toPlainText()
        if not message:
            QMessageBox.warning(self, "Предупреждение", "Введите сообщение для встраивания.")
            return

        # Копируем исходное изображение для работы
        img = self.original_image.copy()
        # Получаем палитру
        colors = img.colorTable()
        if len(colors) == 0:
            QMessageBox.critical(self, "Ошибка", "Изображение не имеет палитры.")
            return

        # Подготавливаем данные для встраивания:
        #   - сначала 2 байта длины сообщения (uint16, big-endian)
        #   - затем сами байты сообщения в UTF-8
        msg_bytes = message.encode('utf-8')
        length = len(msg_bytes)
        if length > 65535:
            QMessageBox.critical(self, "Ошибка", "Сообщение слишком длинное (макс. 65535 байт).")
            return

        # Проверяем, поместится ли сообщение в палитру (максимум 3 бита на цвет)
        max_bits = len(colors) * 3
        needed_bits = (2 + length) * 8  # 2 байта длины + сообщение
        if needed_bits > max_bits:
            QMessageBox.critical(self, "Ошибка",
                f"Сообщение слишком длинное для данной палитры.\n"
                f"Доступно {max_bits} бит, требуется {needed_bits} бит.")
            return

        # Формируем битовый поток
        data = bytearray()
        data.extend(struct.pack('>H', length))  # 2 байта длины, big-endian
        data.extend(msg_bytes)

        # Встраиваем LSB
        bit_index = 0
        total_bits = len(data) * 8
        for i in range(len(colors)):
            # Получаем компоненты текущего цвета
            r = qRed(colors[i])
            g = qGreen(colors[i])
            b = qBlue(colors[i])

            # Для каждого компонента заменяем младший бит
            if bit_index < total_bits:
                byte_idx = bit_index // 8
                bit_in_byte = 7 - (bit_index % 8)   # порядок битов: старший -> младший (можно любой, но нужно согласовать)
                bit = (data[byte_idx] >> bit_in_byte) & 1
                r = (r & 0xFE) | bit
                bit_index += 1
            if bit_index < total_bits:
                byte_idx = bit_index // 8
                bit_in_byte = 7 - (bit_index % 8)
                bit = (data[byte_idx] >> bit_in_byte) & 1
                g = (g & 0xFE) | bit
                bit_index += 1
            if bit_index < total_bits:
                byte_idx = bit_index // 8
                bit_in_byte = 7 - (bit_index % 8)
                bit = (data[byte_idx] >> bit_in_byte) & 1
                b = (b & 0xFE) | bit
                bit_index += 1

            # Сохраняем изменённый цвет обратно
            colors[i] = qRgb(r, g, b)

            if bit_index >= total_bits:
                break

        # Устанавливаем изменённую палитру
        img.setColorTable(colors)
        self.stego_image = img
        self.display_image(self.stego_label, self.stego_image)

        # Сообщаем об успехе
        self.statusBar().showMessage(f"Сообщение встроено. Использовано бит: {bit_index}")
        QMessageBox.information(self, "Готово", "Сообщение успешно встроено в изображение.")

    def extract_message(self):
        """Извлечь сообщение из палитры загруженного стего-изображения."""
        # Сначала проверим, есть ли загруженное стего-изображение, если нет — попробуем использовать оригинальное
        img = self.stego_image if self.stego_image is not None else self.original_image
        if img is None:
            QMessageBox.warning(self, "Предупреждение", "Нет изображения для расшифровки. Загрузите или создайте стего-изображение.")
            return

        # Убедимся, что оно палитровое
        if img.format() != QImage.Format_Indexed8:
            QMessageBox.critical(self, "Ошибка", "Изображение не является палитровым (Indexed8). Невозможно извлечь сообщение.")
            return

        colors = img.colorTable()
        if len(colors) == 0:
            QMessageBox.critical(self, "Ошибка", "Изображение не имеет палитры.")
            return

        # Извлекаем все биты из палитры
        bits = []
        for i in range(len(colors)):
            r = qRed(colors[i])
            g = qGreen(colors[i])
            b = qBlue(colors[i])

            bits.append(r & 1)
            bits.append(g & 1)
            bits.append(b & 1)

        # Преобразуем биты в байты
        data_bytes = bytearray()
        for i in range(0, len(bits), 8):
            if i + 8 > len(bits):
                break
            byte_val = 0
            for j in range(8):
                byte_val = (byte_val << 1) | bits[i + j]
            data_bytes.append(byte_val)

        # Первые 2 байта — длина сообщения
        if len(data_bytes) < 2:
            QMessageBox.critical(self, "Ошибка", "Недостаточно данных для извлечения длины сообщения.")
            return

        length = struct.unpack('>H', data_bytes[0:2])[0]
        if length > len(data_bytes) - 2:
            QMessageBox.critical(self, "Ошибка", "Длина сообщения превышает доступные данные. Возможно, изображение не содержит сообщения.")
            return

        # Извлекаем само сообщение
        msg_bytes = data_bytes[2:2+length]
        try:
            message = msg_bytes.decode('utf-8')
        except UnicodeDecodeError:
            QMessageBox.critical(self, "Ошибка", "Не удалось декодировать сообщение (неверная кодировка).")
            return

        self.extracted_output.setPlainText(message)
        self.statusBar().showMessage("Сообщение извлечено.")

    def display_image(self, label, image):
        """Отобразить QImage в QLabel с сохранением пропорций."""
        if image is None or image.isNull():
            label.clear()
            return
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pixmap)

# Вспомогательные функции для работы с QRgb
def qRed(rgb):
    return (rgb >> 16) & 0xFF

def qGreen(rgb):
    return (rgb >> 8) & 0xFF

def qBlue(rgb):
    return rgb & 0xFF

def qRgb(r, g, b):
    return (0xFF << 24) | (r << 16) | (g << 8) | b

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SteganoWindow()
    window.show()
    sys.exit(app.exec_())
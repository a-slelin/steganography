#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  🔐  LSB-стеганография в PNG-изображениях с палитрой (PLTE чанк)
=============================================================================

Описание модуля:
    Приложение реализует алгоритм стеганографии методом LSB (Least Significant
    Bit — наименьший значащий бит) в палитре PNG-изображений (чанк PLTE).

    Принцип работы метода:
    ─────────────────────────────────────────────────────────────────────────
    PNG-изображения с типом цвета COLOR_PALETTE (ColorType = 3) хранят
    пиксели как индексы в таблице цветов — палитре PLTE. Каждая запись
    палитры содержит тройку байт (R, G, B). В методе LSB мы заменяем
    младший бит (бит 0) каждого байта RGB на один бит скрываемого сообщения.

    Одна запись палитры = 3 бита скрытой информации (R, G, B).
    Палитра из 256 цветов = 768 бит = 96 байт максимальной полезной нагрузки.
    Из них 2 байта занимает заголовок длины → доступно 94 байта текста.

    Изменение на 1 бит из 8 в каждом байте цвета даёт максимальное отклонение
    яркости в 1/255 ≈ 0.4%, что практически неразличимо глазом.

    Формат встраиваемых данных:
    ┌──────────────────────────────────┐
    │  2 байта: длина сообщения        │  ← struct.pack('>H', length) — uint16 big-endian
    │  N байт : UTF-8 текст сообщения  │  ← message.encode('utf-8')
    └──────────────────────────────────┘

    Схема встраивания (биты идут от старшего к младшему):
      data[0] бит7 → R₀[0]   data[0] бит6 → G₀[0]   data[0] бит5 → B₀[0]
      data[0] бит4 → R₁[0]   ...                     ...

Технологии:
    Python 3.8+, PyQt5

Соответствие заданию:
    ✔ Чанк PLTE для хранения информации
    ✔ Метод LSB на цветах палитры
    ✔ ColorType = COLOR_PALETTE (Format_Indexed8)
    ✔ Отображение исходного и стего-изображений
    ✔ Отображение извлечённого сообщения
    ✔ Функция встраивания (encrypt)
    ✔ Функция извлечения (decrypt)
    ✔ Загрузка изображения из файла
    ✔ Сохранение изображения в файл
    ✔ Графический интерфейс на Qt (PyQt5)
"""

import sys
import struct
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit,
    QFileDialog, QMessageBox,
    QFrame, QSizePolicy, QGroupBox,
    QStatusBar
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPalette, QColor
from PyQt5.QtCore import Qt, QSize

# =============================================================================
#  Глобальная таблица стилей (Qt Style Sheets / QSS)
#  Определяет внешний вид всех виджетов приложения в едином тёмном стиле.
# =============================================================================

APP_STYLE = """
/* ── Главное окно ────────────────────────────────────────────────────────── */
QMainWindow, QWidget#central_widget {
    background-color: #1e1e2e;
}

/* ── Шапка приложения ────────────────────────────────────────────────────── */
QLabel#lbl_title {
    color: #cdd6f4;
    font-size: 26px;
    font-weight: bold;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    padding: 8px 0px 0px 0px;
    letter-spacing: 0.5px;
}

QLabel#lbl_subtitle {
    color: #a6adc8;
    font-size: 14px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    padding-bottom: 6px;
}

/* ── Виджет-шапка (фон градиентом через объект) ──────────────────────────── */
QWidget#header_widget {
    background-color: #181825;
    border-radius: 10px;
    border: 1px solid #313244;
}

/* ── Группы (GroupBox) ───────────────────────────────────────────────────── */
QGroupBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 10px;
    margin-top: 20px;
    font-size: 14px;
    font-weight: bold;
    color: #cdd6f4;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    padding: 8px 10px 10px 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px 4px 12px;
    left: 12px;
    color: #89b4fa;
    background-color: #1e1e2e;
    border-radius: 6px;
    font-size: 14px;
}

/* ── Лейблы для отображения изображений ─────────────────────────────────── */
QLabel#lbl_image {
    background-color: #181825;
    border: 2px dashed #45475a;
    border-radius: 8px;
    color: #585b70;
    font-size: 14px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    qproperty-alignment: AlignCenter;
}

QLabel#lbl_image:hover {
    border-color: #89b4fa;
}

/* ── Универсальные кнопки (базовый стиль) ────────────────────────────────── */
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    min-width: 180px;
    min-height: 44px;
}

QPushButton:hover {
    background-color: #b4befe;
}

QPushButton:pressed {
    background-color: #7287fd;
    padding-top: 9px;
    padding-bottom: 7px;
}

QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

/* ── Кнопка «Встроить» (зелёная) ─────────────────────────────────────────── */
QPushButton#btn_embed {
    background-color: #a6e3a1;
    color: #1e1e2e;
}
QPushButton#btn_embed:hover  { background-color: #94e2d5; }
QPushButton#btn_embed:pressed{ background-color: #74c7ec; }

/* ── Кнопка «Извлечь» (оранжевая) ───────────────────────────────────────── */
QPushButton#btn_extract {
    background-color: #fab387;
    color: #1e1e2e;
}
QPushButton#btn_extract:hover  { background-color: #f9e2af; }
QPushButton#btn_extract:pressed{ background-color: #eba0ac; }

/* ── Кнопка «Сохранить» (фиолетовая) ─────────────────────────────────────── */
QPushButton#btn_save {
    background-color: #cba6f7;
    color: #1e1e2e;
}
QPushButton#btn_save:hover  { background-color: #f5c2e7; }
QPushButton#btn_save:pressed{ background-color: #b4befe; }

/* ── Текстовые поля ──────────────────────────────────────────────────────── */
QTextEdit {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 14px;
    font-family: 'Consolas', 'Courier New', monospace;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QTextEdit:focus {
    border: 1px solid #89b4fa;
}

/* ── Полосы прокрутки ────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #181825;
    width: 8px;
    border-radius: 4px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #89b4fa; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

/* ── Статусная строка ────────────────────────────────────────────────────── */
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    font-size: 13px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    border-top: 1px solid #313244;
    padding: 3px 10px;
    min-height: 26px;
}

/* ── Горизонтальный разделитель ──────────────────────────────────────────── */
QFrame#separator {
    background-color: #45475a;
    max-height: 1px;
    border: none;
}

/* ── Диалоговые окна ─────────────────────────────────────────────────────── */
QMessageBox {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QMessageBox QLabel {
    color: #cdd6f4;
    font-size: 11px;
    font-family: 'Segoe UI', 'Arial', sans-serif;
}
QMessageBox QPushButton {
    min-width: 80px;
    min-height: 28px;
}
"""


# =============================================================================
#  Вспомогательные функции для работы с цветовыми значениями Qt (QRgb)
# =============================================================================

def qRed(rgb: int) -> int:
    """
    Извлечь значение красного канала из цветового значения QRgb.

    Qt хранит цвет в формате 0xAARRGGBB (32-битное целое):
      - биты 31..24 — альфа-канал (AA)
      - биты 23..16 — красный канал (RR)
      - биты 15..8  — зелёный канал (GG)
      - биты 7..0   — синий канал (BB)

    Args:
        rgb (int): Цветовое значение в формате 0xAARRGGBB.

    Returns:
        int: Значение красного канала в диапазоне [0, 255].
    """
    return (rgb >> 16) & 0xFF


def qGreen(rgb: int) -> int:
    """
    Извлечь значение зелёного канала из цветового значения QRgb.

    Args:
        rgb (int): Цветовое значение в формате 0xAARRGGBB.

    Returns:
        int: Значение зелёного канала в диапазоне [0, 255].
    """
    return (rgb >> 8) & 0xFF


def qBlue(rgb: int) -> int:
    """
    Извлечь значение синего канала из цветового значения QRgb.

    Args:
        rgb (int): Цветовое значение в формате 0xAARRGGBB.

    Returns:
        int: Значение синего канала в диапазоне [0, 255].
    """
    return rgb & 0xFF


def qRgb(r: int, g: int, b: int) -> int:
    """
    Собрать цветовое значение QRgb из трёх компонентов RGB.

    Устанавливает альфа-канал в 0xFF (полностью непрозрачный).

    Args:
        r (int): Красный канал [0, 255].
        g (int): Зелёный канал [0, 255].
        b (int): Синий канал [0, 255].

    Returns:
        int: Цветовое значение в формате 0xFFRRGGBB.
    """
    return (0xFF << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


# =============================================================================
#  Главное окно приложения
# =============================================================================

class SteganoWindow(QMainWindow):
    """
    Главное окно приложения «LSB-стеганография в PNG».

    Предоставляет пользователю полный цикл работы со стеганографией:

    1. Загрузка PNG-изображения любого типа (с автоматическим
       приведением к палитровому формату Indexed8 при необходимости).
    2. Ввод секретного сообщения для встраивания.
    3. Встраивание сообщения в LSB-биты палитры (чанк PLTE).
    4. Визуальное сравнение исходного и стего-изображений.
    5. Извлечение скрытого сообщения из любого стего-PNG.
    6. Сохранение стего-изображения в файл PNG с сохранёнными LSB.

    Атрибуты:
        original_image (Optional[QImage]):
            Исходное изображение после загрузки и приведения к Indexed8.
            None — пока изображение не загружено.

        stego_image (Optional[QImage]):
            Копия исходного изображения с изменёнными LSB в палитре.
            None — пока встраивание не произведено.
    """

    def __init__(self) -> None:
        """
        Инициализация главного окна приложения.

        Выполняет:
        - Настройку параметров окна (заголовок, размеры).
        - Инициализацию переменных состояния.
        - Применение глобальной таблицы стилей.
        - Построение всех виджетов интерфейса.
        - Начальное обновление состояния кнопок.
        """
        super().__init__()

        # ── Настройки окна ───────────────────────────────────────────────────
        self.setWindowTitle("🔐 PNG Стеганография | LSB метод | PLTE чанк")
        self.setGeometry(100, 80, 1280, 860)  # x, y, ширина, высота
        self.setMinimumSize(1060, 700)  # Минимальный допустимый размер

        # ── Переменные состояния ─────────────────────────────────────────────
        self.original_image: Optional[QImage] = None  # Исходное палитровое изображение
        self.stego_image: Optional[QImage] = None  # Изображение со встроенным сообщением

        # ── Применение глобальной таблицы стилей QSS ────────────────────────
        self.setStyleSheet(APP_STYLE)

        # ── Построение пользовательского интерфейса ──────────────────────────
        self._build_ui()

        # ── Первоначальное обновление доступности кнопок ─────────────────────
        self._refresh_buttons()

    # ─────────────────────────────────────────────────────────────────────────
    #  Построение пользовательского интерфейса
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """
        Собрать весь пользовательский интерфейс и поместить виджеты в окно.

        Структура макета главного окна:
        ┌─────────────────────────────────────────────────────────────┐
        │  [Шапка: иконка + название + описание метода]               │
        │  ─────────────────────────────── (разделитель)              │
        │  ┌─────────────────────────────────────────────────────┐   │
        │  │ [Группа «Исходное»] │ [Группа «Стего-изображение»]  │   │
        │  │  (QLabel + кнопка)  │  (QLabel + кнопка)            │   │
        │  └─────────────────────────────────────────────────────┘   │
        │  ┌─────────────────────────────────────────────────────┐   │
        │  │ [Группа «Ввод»]     │ [Группа «Извлечённое»]        │   │
        │  │  (QTextEdit ввод)   │  (QTextEdit чтение)           │   │
        │  └─────────────────────────────────────────────────────┘   │
        │  [Кнопка «Встроить»]       [Кнопка «Извлечь»]             │
        │  ─────────────────────────────── (статусная строка)         │
        └─────────────────────────────────────────────────────────────┘
        """
        # Центральный виджет, который содержит весь интерфейс
        central = QWidget()
        central.setObjectName("central_widget")
        self.setCentralWidget(central)

        # Корневой вертикальный компоновщик с отступами
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(10)

        # ── 1. Шапка приложения ──────────────────────────────────────────────
        root.addWidget(self._make_header())

        # ── Тонкая горизонтальная линия-разделитель ──────────────────────────
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        # ── 2. Ряд с двумя изображениями (исходное | стего) ─────────────────
        img_row = QHBoxLayout()
        img_row.setSpacing(12)
        img_row.addWidget(self._make_original_group())  # Левая панель
        img_row.addWidget(self._make_stego_group())  # Правая панель
        root.addLayout(img_row, stretch=3)  # stretch=3 — изображения занимают основное пространство

        # ── 3. Ряд с текстовыми полями (ввод | вывод) ───────────────────────
        msg_row = QHBoxLayout()
        msg_row.setSpacing(12)
        msg_row.addWidget(self._make_input_group())  # Поле ввода сообщения
        msg_row.addWidget(self._make_output_group())  # Поле извлечённого сообщения
        root.addLayout(msg_row, stretch=1)

        # ── 4. Ряд кнопок действий ───────────────────────────────────────────
        root.addLayout(self._make_action_row())

        # ── 5. Статусная строка ──────────────────────────────────────────────
        # QStatusBar встроен в QMainWindow; обновляется через self.statusBar()
        self.statusBar().showMessage("✅  Приложение готово к работе. Загрузите PNG-изображение.")

    # ── Шапка ─────────────────────────────────────────────────────────────────

    def _make_header(self) -> QWidget:
        """
        Создать виджет-шапку с названием и кратким описанием приложения.

        Returns:
            QWidget: Панель с заголовком и подзаголовком, оформленная стилем
                     «header_widget» (тёмный фон с рамкой).
        """
        header = QWidget()
        header.setObjectName("header_widget")

        layout = QVBoxLayout(header)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(3)

        # Главный заголовок приложения
        title = QLabel("🔐  PNG LSB-Стеганография  —  скрываем сообщения в палитре изображения")
        title.setObjectName("lbl_title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Краткое пояснение метода
        subtitle = QLabel(
            "Метод LSB (Least Significant Bit) изменяет младший бит каждого байта RGB-палитры (чанк PLTE). "
            "Визуальные изменения — не более 1/255 яркости, абсолютно незаметно для глаза."
        )
        subtitle.setObjectName("lbl_subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        return header

    # ── Панель исходного изображения ──────────────────────────────────────────

    def _make_original_group(self) -> QGroupBox:
        """
        Создать группу-панель для отображения исходного (оригинального) изображения.

        Содержит:
        - QLabel — область предпросмотра изображения.
        - QPushButton — кнопка «Загрузить изображение».

        Returns:
            QGroupBox: Готовая панель с виджетами.
        """
        group = QGroupBox("📷  Исходное изображение (оригинал)")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(8)

        # Область для отображения загруженного изображения
        self.original_label = QLabel(
            "Изображение не загружено\n\n"
            "📂  Нажмите кнопку ниже, чтобы открыть файл PNG.\n\n"
            "Поддерживаются любые PNG:\n"
            "цветные изображения будут приведены\n"
            "к палитровому формату (≤ 256 цветов)."
        )
        self.original_label.setObjectName("lbl_image")
        self.original_label.setAlignment(Qt.AlignCenter)
        self.original_label.setMinimumSize(400, 290)
        self.original_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.original_label.setWordWrap(True)
        vbox.addWidget(self.original_label)

        # Кнопка открытия файла
        self.btn_load = QPushButton("📂  Загрузить PNG-изображение")
        self.btn_load.setToolTip(
            "Открыть PNG-файл с диска.\n"
            "Если изображение не палитровое (Indexed8),\n"
            "оно будет автоматически квантовано до ≤ 256 цветов."
        )
        self.btn_load.clicked.connect(self.load_image)
        vbox.addWidget(self.btn_load, alignment=Qt.AlignHCenter)

        return group

    # ── Панель стего-изображения ───────────────────────────────────────────────

    def _make_stego_group(self) -> QGroupBox:
        """
        Создать группу-панель для отображения стего-изображения.

        Содержит:
        - QLabel — область предпросмотра стего-изображения.
        - QPushButton — кнопка «Сохранить стего-изображение».

        Returns:
            QGroupBox: Готовая панель с виджетами.
        """
        group = QGroupBox("🖼️  Стего-изображение (с встроенным сообщением)")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(8)

        # Область для отображения стего-изображения
        self.stego_label = QLabel(
            "Стего-изображение появится здесь\n"
            "после нажатия «🔒 Встроить сообщение».\n\n"
            "Внешне оно будет неотличимо\n"
            "от оригинала — сообщение скрыто\n"
            "в младших битах палитры PLTE."
        )
        self.stego_label.setObjectName("lbl_image")
        self.stego_label.setAlignment(Qt.AlignCenter)
        self.stego_label.setMinimumSize(400, 290)
        self.stego_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stego_label.setWordWrap(True)
        vbox.addWidget(self.stego_label)

        # Кнопка сохранения стего-изображения в файл
        self.btn_save = QPushButton("💾  Сохранить стего-изображение")
        self.btn_save.setObjectName("btn_save")
        self.btn_save.setToolTip(
            "Сохранить PNG-файл с встроенным сообщением.\n"
            "Палитра (PLTE чанк) со скрытыми битами\n"
            "будет точно сохранена в файле."
        )
        self.btn_save.clicked.connect(self.save_stego_image)
        vbox.addWidget(self.btn_save, alignment=Qt.AlignHCenter)

        return group

    # ── Поле ввода сообщения ──────────────────────────────────────────────────

    def _make_input_group(self) -> QGroupBox:
        """
        Создать группу с текстовым полем для ввода скрываемого сообщения.

        Returns:
            QGroupBox: Группа с QTextEdit для ввода текста сообщения.
        """
        group = QGroupBox("✏️  Сообщение для встраивания")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(6)

        # Подсказка под заголовком группы
        hint = QLabel("Введите текст, который будет скрыт в палитре PNG:")
        hint.setStyleSheet("color: #a6adc8; font-size: 13px;")
        vbox.addWidget(hint)

        # Текстовое поле ввода (редактируемое)
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText(
            "Введите секретное сообщение...\n\n"
            "Поддерживается любой текст в кодировке UTF-8.\n"
            "Максимальная длина зависит от размера палитры.\n"
            "Для стандартной палитры 256 цветов: ≈ 94 байта."
        )
        self.message_input.setMinimumHeight(90)
        self.message_input.setMaximumHeight(130)
        vbox.addWidget(self.message_input)

        return group

    # ── Поле вывода извлечённого сообщения ────────────────────────────────────

    def _make_output_group(self) -> QGroupBox:
        """
        Создать группу с текстовым полем для отображения извлечённого сообщения.

        Поле доступно только для чтения — пользователь не может его редактировать.

        Returns:
            QGroupBox: Группа с QTextEdit (readOnly) для вывода результата.
        """
        group = QGroupBox("🔍  Извлечённое сообщение")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(6)

        # Подсказка под заголовком группы
        hint = QLabel("Скрытый текст, извлечённый из палитры PLTE:")
        hint.setStyleSheet("color: #a6adc8; font-size: 13px;")
        vbox.addWidget(hint)

        # Текстовое поле вывода (только для чтения)
        self.extracted_output = QTextEdit()
        self.extracted_output.setPlaceholderText(
            "Здесь появится скрытое сообщение\n"
            "после нажатия «🔓 Извлечь сообщение».\n\n"
            "Для извлечения нужно стего-изображение —\n"
            "либо только что созданное, либо загруженное из файла."
        )
        self.extracted_output.setMinimumHeight(90)
        self.extracted_output.setMaximumHeight(130)
        self.extracted_output.setReadOnly(True)  # Запрет редактирования выходного поля
        vbox.addWidget(self.extracted_output)

        return group

    # ── Панель кнопок-действий ────────────────────────────────────────────────

    def _make_action_row(self) -> QHBoxLayout:
        """
        Создать горизонтальный ряд с кнопками «Встроить» и «Извлечь».

        Кнопки центрированы и разделены пружинами (addStretch).

        Returns:
            QHBoxLayout: Компоновщик с двумя главными кнопками-действиями.
        """
        row = QHBoxLayout()
        row.setSpacing(20)
        row.addStretch()

        # ── Кнопка встраивания сообщения ────────────────────────────────────
        self.btn_embed = QPushButton("🔒  Встроить сообщение в палитру")
        self.btn_embed.setObjectName("btn_embed")
        self.btn_embed.setMinimumWidth(280)
        self.btn_embed.setToolTip(
            "Встроить текст из поля ввода в LSB-биты RGB-компонентов\n"
            "палитры (PLTE чанк) исходного изображения.\n"
            "Исходник не изменяется — создаётся копия со скрытым текстом."
        )
        self.btn_embed.clicked.connect(self.embed_message)
        row.addWidget(self.btn_embed)

        # ── Кнопка извлечения сообщения ─────────────────────────────────────
        self.btn_extract = QPushButton("🔓  Извлечь сообщение из палитры")
        self.btn_extract.setObjectName("btn_extract")
        self.btn_extract.setMinimumWidth(280)
        self.btn_extract.setToolTip(
            "Считать LSB-биты из палитры (PLTE чанк) изображения\n"
            "и восстановить скрытое сообщение.\n"
            "Работает и с текущим стего-изображением, и с загруженным PNG."
        )
        self.btn_extract.clicked.connect(self.extract_message)
        row.addWidget(self.btn_extract)

        row.addStretch()
        return row

    # ─────────────────────────────────────────────────────────────────────────
    #  Управление состоянием кнопок
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_buttons(self) -> None:
        """
        Обновить доступность (enabled/disabled) кнопок в соответствии с состоянием.

        Правила:
        - «Сохранить»  — активна, только если создано стего-изображение.
        - «Встроить»   — активна, только если загружено исходное изображение.
        - «Извлечь»    — активна, если есть хоть какое-то изображение для анализа.
        """
        has_original = self.original_image is not None
        has_stego = self.stego_image is not None

        self.btn_save.setEnabled(has_stego)  # Нечего сохранять без стего
        self.btn_embed.setEnabled(has_original)  # Нечего встраивать без оригинала
        self.btn_extract.setEnabled(has_original or has_stego)  # Нужно хоть какое-то изображение

    # ─────────────────────────────────────────────────────────────────────────
    #  ОПЕРАЦИЯ 1: Загрузка изображения
    # ─────────────────────────────────────────────────────────────────────────

    def load_image(self) -> None:
        """
        Загрузить PNG-изображение из файловой системы.

        Алгоритм:
        1. Открываем системный диалог выбора файла (фильтр *.png).
        2. Читаем файл в QImage средствами Qt (libpng).
        3. Проверяем формат: если изображение не Format_Indexed8 (палитровое),
           выполняем конвертацию через convertToFormat().
           Qt применяет алгоритм медианного разрезания для квантования до ≤ 256 цветов.
        4. Сохраняем в self.original_image; сбрасываем self.stego_image.
        5. Отображаем оригинал в левой панели, очищаем правую панель и поле вывода.
        6. Обновляем состояние кнопок.

        Примечание по конвертации:
            Приведение полноцветного (RGB32/ARGB32) изображения к Indexed8 — это
            разрушающая операция: от 16 млн цветов → не более 256. Рекомендуется
            использовать изначально палитровые PNG (colortype=3).
        """
        # Открываем диалог выбора файла с фильтром по расширению
        file_path, _ = QFileDialog.getOpenFileName(
            self,  # Родительский виджет
            "Открыть PNG-изображение",  # Заголовок диалога
            "",  # Начальная директория (текущая)
            "PNG-изображения (*.png);;Все файлы (*.*)"
        )

        # Пользователь закрыл диалог без выбора — ничего не делаем
        if not file_path:
            return

        # Загружаем файл в QImage; Qt использует libpng внутри
        img = QImage(file_path)
        if img.isNull():
            QMessageBox.critical(
                self, "❌  Ошибка загрузки",
                f"Не удалось загрузить изображение.\n\n"
                f"Файл: {file_path}\n\n"
                "Убедитесь, что это корректный PNG-файл."
            )
            return

        # ── Проверяем формат и при необходимости конвертируем ─────────────────
        if img.format() == QImage.Format_Indexed8:
            # Изображение уже палитровое — идеальный вариант
            status_msg = f"✅  Загружено палитровое изображение: {file_path}"
        else:
            # Конвертируем цветное изображение в Indexed8 (256 цветов, палитра)
            # Qt использует алгоритм квантования цветов (медианное разрезание)
            img = img.convertToFormat(QImage.Format_Indexed8)
            if img.isNull():
                QMessageBox.critical(
                    self, "❌  Ошибка конвертации",
                    "Не удалось преобразовать изображение в палитровый формат.\n"
                    "Попробуйте другое изображение."
                )
                return
            status_msg = (
                "⚠️  Изображение преобразовано в палитровый формат (≤ 256 цветов). "
                f"Файл: {file_path}"
            )

        # ── Сохраняем состояние и обновляем интерфейс ─────────────────────────
        self.original_image = img
        self.stego_image = None  # Сбрасываем старое стего-изображение

        # Отображаем оригинал в левой панели
        self._show_image(self.original_label, self.original_image)

        # Очищаем правую панель (стего ещё нет)
        self.stego_label.clear()
        self.stego_label.setText(
            "Стего-изображение появится здесь\n"
            "после нажатия «🔒 Встроить сообщение»."
        )

        # Очищаем поле с ранее извлечённым сообщением
        self.extracted_output.clear()

        # Обновляем статусную строку и кнопки
        self.statusBar().showMessage(status_msg)
        self._refresh_buttons()

    # ─────────────────────────────────────────────────────────────────────────
    #  ОПЕРАЦИЯ 2: Сохранение стего-изображения
    # ─────────────────────────────────────────────────────────────────────────

    def save_stego_image(self) -> None:
        """
        Сохранить стего-изображение в PNG-файл.

        Qt сохраняет Format_Indexed8 (QImage) в PNG с чанком PLTE через libpng.
        Это гарантирует точное сохранение всех байтов палитры, включая
        изменённые LSB-биты. После перезагрузки файла сообщение можно извлечь.

        Важно:
            Не сохранять стего-PNG в формате JPEG или BMP — эти форматы не
            сохранят палитру и LSB-биты будут утрачены.
        """
        # Проверяем, что стего-изображение существует
        if self.stego_image is None:
            QMessageBox.warning(
                self, "⚠️  Нет стего-изображения",
                "Сначала встройте сообщение через кнопку\n"
                "«🔒 Встроить сообщение в палитру»."
            )
            return

        # Открываем диалог сохранения файла
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить стего-изображение",
            "stego_image.png",  # Имя по умолчанию
            "PNG-изображения (*.png)"
        )

        # Пользователь закрыл диалог — ничего не делаем
        if not file_path:
            return

        # Гарантируем расширение .png
        if not file_path.lower().endswith(".png"):
            file_path += ".png"

        # Сохраняем в PNG; Qt пишет корректный PLTE чанк
        success = self.stego_image.save(file_path, "PNG")

        if success:
            self.statusBar().showMessage(f"💾  Сохранено: {file_path}")
            QMessageBox.information(
                self, "✅  Файл сохранён",
                f"Стего-изображение успешно записано:\n\n{file_path}\n\n"
                "Скрытое сообщение сохранено в палитре (PLTE чанк).\n"
                "Откройте этот файл в приложении для извлечения сообщения."
            )
        else:
            QMessageBox.critical(
                self, "❌  Ошибка записи",
                f"Не удалось сохранить файл:\n{file_path}\n\n"
                "Проверьте права доступа к директории."
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  ОПЕРАЦИЯ 3: Встраивание сообщения (Encode / Encrypt)
    # ─────────────────────────────────────────────────────────────────────────

    def embed_message(self) -> None:
        """
        Встроить текстовое сообщение в LSB-биты RGB-компонентов палитры PNG.

        Детальный алгоритм:
        ──────────────────────────────────────────────────────────────────────
        1. Кодируем сообщение: msg_bytes = message.encode('utf-8').
        2. Формируем заголовок: length_bytes = struct.pack('>H', len(msg_bytes))
           (2 байта, uint16, big-endian — длина сообщения в байтах).
        3. Склеиваем: data = length_bytes + msg_bytes.
        4. Раскладываем data в битовый поток bits[], начиная со старшего бита
           каждого байта (бит 7 → бит 0).
        5. Берём копию исходного изображения и его палитру colors[].
        6. Для каждого цвета colors[i] (i = 0, 1, ..., len-1):
               r = qRed(colors[i])
               g = qGreen(colors[i])
               b = qBlue(colors[i])
               r = (r & 0xFE) | bit_next   ← заменяем LSB красного
               g = (g & 0xFE) | bit_next   ← заменяем LSB зелёного
               b = (b & 0xFE) | bit_next   ← заменяем LSB синего
               colors[i] = qRgb(r, g, b)
           Прекращаем, когда все биты встроены.
        7. Применяем изменённую палитру: img.setColorTable(colors).
        8. Сохраняем результат в self.stego_image и отображаем.

        Ёмкость:
            max_bits    = len(palette) × 3
            needed_bits = (2 + len(msg_utf8)) × 8
            Если needed_bits > max_bits → ошибка с диагностикой.

        Исходное изображение не изменяется — работаем с его копией (copy()).
        """
        # ── Предварительные проверки ───────────────────────────────────────────
        if self.original_image is None:
            QMessageBox.warning(
                self, "⚠️  Изображение не загружено",
                "Сначала загрузите PNG-изображение через кнопку\n"
                "«📂 Загрузить PNG-изображение»."
            )
            return

        message = self.message_input.toPlainText()
        if not message:
            QMessageBox.warning(
                self, "⚠️  Пустое сообщение",
                "Введите текст в поле «✏️ Сообщение для встраивания»."
            )
            return

        # ── Создаём рабочую копию изображения ────────────────────────────────
        # copy() создаёт глубокую копию; оригинал self.original_image остаётся нетронутым
        img = self.original_image.copy()
        colors = img.colorTable()  # list[int] — палитра в формате QRgb (0xAARRGGBB)

        if not colors:
            QMessageBox.critical(self, "❌  Ошибка", "Изображение не содержит палитры (PLTE).")
            return

        # ── Кодируем сообщение в байты UTF-8 ──────────────────────────────────
        msg_bytes = message.encode('utf-8')
        length = len(msg_bytes)

        # Проверка: длина должна помещаться в uint16 (0..65535)
        if length > 65535:
            QMessageBox.critical(
                self, "❌  Сообщение слишком длинное",
                f"Длина сообщения: {length} байт.\n"
                "Максимально допустимая длина: 65 535 байт."
            )
            return

        # ── Проверка ёмкости палитры ───────────────────────────────────────────
        # Каждый цвет палитры даёт 3 бита (по одному на R, G, B канал)
        max_bits = len(colors) * 3  # Максимум бит, доступных для встраивания
        needed_bits = (2 + length) * 8  # 2 байта заголовка + N байт сообщения

        if needed_bits > max_bits:
            # Вычисляем, сколько текста (ASCII) вмещается
            available_text_bytes = max(0, max_bits // 8 - 2)
            QMessageBox.critical(
                self, "❌  Сообщение не помещается в палитру",
                f"Длина вашего сообщения: {length} байт ({needed_bits} бит)\n"
                f"Доступно в палитре ({len(colors)} цветов): {max_bits} бит\n\n"
                f"Максимальная ёмкость для текста: ~{available_text_bytes} байт (ASCII)\n\n"
                "Сократите сообщение или используйте изображение с большей палитрой."
            )
            return

        # ── Формируем байтовый поток данных ───────────────────────────────────
        data = bytearray()
        data.extend(struct.pack('>H', length))  # 2 байта: длина сообщения (big-endian uint16)
        data.extend(msg_bytes)  # N байт: само сообщение в кодировке UTF-8

        # ── LSB-встраивание: заменяем младший бит каждого байта RGB ───────────
        bit_index = 0  # Текущая позиция в общем битовом потоке
        total_bits = len(data) * 8  # Суммарное число битов для встраивания

        for i in range(len(colors)):

            # Извлекаем компоненты текущего цвета палитры
            r = qRed(colors[i])
            g = qGreen(colors[i])
            b = qBlue(colors[i])

            # ── Красный канал ────────────────────────────────────────────────
            if bit_index < total_bits:
                # Определяем, из какого байта и с какой позиции берём бит
                byte_idx = bit_index // 8  # Индекс байта в массиве data
                bit_in_byte = 7 - (bit_index % 8)  # Смещение бита (7=MSB, 0=LSB)
                bit = (data[byte_idx] >> bit_in_byte) & 1  # Извлекаемый бит (0 или 1)

                r = (r & 0xFE) | bit  # Обнуляем LSB красного и устанавливаем нужный бит
                bit_index += 1

            # ── Зелёный канал ────────────────────────────────────────────────
            if bit_index < total_bits:
                byte_idx = bit_index // 8
                bit_in_byte = 7 - (bit_index % 8)
                bit = (data[byte_idx] >> bit_in_byte) & 1

                g = (g & 0xFE) | bit  # Обнуляем LSB зелёного и устанавливаем нужный бит
                bit_index += 1

            # ── Синий канал ──────────────────────────────────────────────────
            if bit_index < total_bits:
                byte_idx = bit_index // 8
                bit_in_byte = 7 - (bit_index % 8)
                bit = (data[byte_idx] >> bit_in_byte) & 1

                b = (b & 0xFE) | bit  # Обнуляем LSB синего и устанавливаем нужный бит
                bit_index += 1

            # Записываем изменённый цвет обратно в список палитры
            colors[i] = qRgb(r, g, b)

            # Все биты встроены — нет смысла продолжать перебор цветов
            if bit_index >= total_bits:
                break

        # ── Применяем изменённую палитру к изображению ────────────────────────
        img.setColorTable(colors)  # Устанавливаем новую палитру; данные пикселей не меняются
        self.stego_image = img  # Сохраняем результат

        # ── Отображаем стего-изображение в правой панели ─────────────────────
        self._show_image(self.stego_label, self.stego_image)

        # ── Обновляем UI и информируем пользователя ───────────────────────────
        colors_used = (bit_index + 2) // 3  # Приблизительное число изменённых цветов
        self.statusBar().showMessage(
            f"🔒  Встроено {length} байт текста. "
            f"Задействовано {bit_index} бит в ~{colors_used} цветах палитры "
            f"из {len(colors)} доступных."
        )
        self._refresh_buttons()

        QMessageBox.information(
            self, "✅  Сообщение встроено",
            f"Сообщение успешно скрыто в палитре PNG!\n\n"
            f"📊 Статистика:\n"
            f"   • Длина сообщения:        {length} байт\n"
            f"   • Использовано бит:        {bit_index} из {max_bits} доступных\n"
            f"   • Задействовано цветов:    ~{colors_used} из {len(colors)}\n"
            f"   • Заполнение палитры:      {bit_index * 100 // max_bits}%\n\n"
            "Нажмите «💾 Сохранить стего-изображение», чтобы записать файл."
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  ОПЕРАЦИЯ 4: Извлечение сообщения (Decode / Decrypt)
    # ─────────────────────────────────────────────────────────────────────────

    def extract_message(self) -> None:
        """
        Извлечь скрытое сообщение из LSB-битов палитры PNG-изображения.

        Алгоритм (обратный к embed_message):
        ──────────────────────────────────────────────────────────────────────
        1. Выбираем изображение: сначала self.stego_image (только что созданное),
           при его отсутствии — self.original_image (загруженное стего-PNG).
        2. Считываем LSB (бит 0) каждого канала R, G, B из всех цветов палитры:
               bits[3i+0] = R_i & 1
               bits[3i+1] = G_i & 1
               bits[3i+2] = B_i & 1
        3. Группируем биты в байты (по 8 штук, старший бит первым):
               byte_val = bits[8k]<<7 | bits[8k+1]<<6 | ... | bits[8k+7]<<0
        4. Первые 2 байта (data_bytes[0:2]) — длина сообщения (uint16 big-endian).
        5. Следующие length байт (data_bytes[2:2+length]) — UTF-8 текст.
        6. Декодируем байты в строку: msg_bytes.decode('utf-8').
        7. Выводим в поле extracted_output.

        Санитарные проверки:
        - length == 0 → изображение, вероятно, не содержит скрытого сообщения.
        - length > (len(data_bytes) - 2) → данные повреждены или изображение
          не является стего-изображением.
        - UnicodeDecodeError → LSB-данные не являются корректным UTF-8.
        """
        # ── Выбираем изображение для анализа ─────────────────────────────────
        # Приоритет: только что созданное стего > загруженное из файла (оригинал)
        if self.stego_image is not None:
            img = self.stego_image
            source_name = "текущего стего-изображения"
        elif self.original_image is not None:
            img = self.original_image
            source_name = "загруженного изображения"
        else:
            QMessageBox.warning(
                self, "⚠️  Нет изображения для анализа",
                "Загрузите стего-PNG через «📂 Загрузить PNG-изображение»\n"
                "или создайте стего-изображение через «🔒 Встроить сообщение»."
            )
            return

        # ── Проверяем, что изображение палитровое ────────────────────────────
        if img.format() != QImage.Format_Indexed8:
            QMessageBox.critical(
                self, "❌  Неподходящий формат",
                "Изображение не является палитровым (Indexed8).\n"
                "Извлечение данных из LSB палитры невозможно."
            )
            return

        # Получаем список цветов палитры
        colors = img.colorTable()
        if not colors:
            QMessageBox.critical(self, "❌  Ошибка", "Палитра изображения пуста.")
            return

        # ── Считываем LSB из каждого RGB-компонента каждого цвета ────────────
        bits: list = []
        for i in range(len(colors)):
            r = qRed(colors[i])
            g = qGreen(colors[i])
            b = qBlue(colors[i])

            bits.append(r & 1)  # Младший бит красного канала i-го цвета
            bits.append(g & 1)  # Младший бит зелёного канала i-го цвета
            bits.append(b & 1)  # Младший бит синего канала i-го цвета

        # ── Конвертируем битовый поток в байты (MSB первым) ──────────────────
        data_bytes = bytearray()
        for i in range(0, len(bits), 8):
            if i + 8 > len(bits):
                break  # Пропускаем неполный байт в конце

            byte_val = 0
            for j in range(8):
                # Старший бит первым: сдвигаем накопленное значение влево и добавляем бит
                byte_val = (byte_val << 1) | bits[i + j]
            data_bytes.append(byte_val)

        # ── Читаем заголовок: первые 2 байта = длина сообщения ───────────────
        if len(data_bytes) < 2:
            QMessageBox.critical(
                self, "❌  Недостаточно данных",
                "В палитре слишком мало цветов для хранения даже заголовка длины."
            )
            return

        # Распаковываем длину как 16-битное целое без знака (big-endian)
        length = struct.unpack('>H', data_bytes[0:2])[0]

        # ── Санитарные проверки ────────────────────────────────────────────────
        if length == 0:
            # Нулевая длина — скорее всего, в изображении нет сообщения
            QMessageBox.information(
                self, "ℹ️  Сообщение не обнаружено",
                f"В {source_name} не найдено скрытого сообщения\n"
                "(поле длины равно 0).\n\n"
                "Вероятно, это обычное изображение без стеганограммы."
            )
            return

        available_bytes = len(data_bytes) - 2  # Байт данных после заголовка
        if length > available_bytes:
            QMessageBox.critical(
                self, "❌  Данные повреждены или отсутствуют",
                f"Заявленная длина сообщения: {length} байт.\n"
                f"Фактически доступно данных: {available_bytes} байт.\n\n"
                "Возможные причины:\n"
                "  • Изображение не является стего-PNG.\n"
                "  • Файл был пересжат или изменён (JPEG-конвертация и т.п.).\n"
                "  • Палитра повреждена или переупорядочена."
            )
            return

        # ── Декодируем байты сообщения из UTF-8 ──────────────────────────────
        msg_bytes = data_bytes[2:2 + length]  # Срез: пропускаем 2-байтный заголовок
        try:
            message = msg_bytes.decode('utf-8')
        except UnicodeDecodeError:
            QMessageBox.critical(
                self, "❌  Ошибка декодирования",
                "Извлечённые байты не являются корректным UTF-8 текстом.\n\n"
                "Вероятно, изображение не содержит скрытого сообщения\n"
                "или оно было встроено в другой кодировке."
            )
            return

        # ── Выводим результат ─────────────────────────────────────────────────
        self.extracted_output.setPlainText(message)
        self.statusBar().showMessage(
            f"🔓  Сообщение извлечено из {source_name}: {length} байт, "
            f"{len(message)} символов."
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  Вспомогательный метод отображения изображения
    # ─────────────────────────────────────────────────────────────────────────

    def _show_image(self, label: QLabel, image: Optional[QImage]) -> None:
        """
        Отобразить QImage внутри виджета QLabel с масштабированием по размеру.

        Масштабирование:
        - Сохраняет исходные пропорции изображения (KeepAspectRatio).
        - Использует билинейную интерполяцию для сглаживания (SmoothTransformation).
        - Масштабирует по текущему или минимальному размеру лейбла (берём наибольший).

        Args:
            label (QLabel):          Виджет-контейнер для вывода изображения.
            image (Optional[QImage]): Изображение для отображения.
                                      None или пустой QImage — очищает лейбл.
        """
        if image is None or image.isNull():
            label.clear()
            return

        # Конвертируем QImage в QPixmap для работы с QLabel
        pixmap = QPixmap.fromImage(image)

        # Определяем целевой размер: берём текущий или минимальный (что больше)
        target_size = label.size()
        if target_size.width() < label.minimumWidth():
            target_size = label.minimumSize()

        # Масштабируем с сохранением пропорций и сглаживанием
        scaled = pixmap.scaled(
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        label.setPixmap(scaled)


# =============================================================================
#  Точка входа
# =============================================================================

def main() -> None:
    """
    Точка входа приложения.

    Создаёт QApplication, устанавливает глобальный шрифт,
    инициализирует главное окно и запускает цикл событий Qt.
    """
    # Создаём объект приложения Qt; sys.argv передаётся для обработки аргументов CLI
    app = QApplication(sys.argv)
    app.setApplicationName("PNG LSB Steganography")
    app.setApplicationVersion("1.0")

    # Устанавливаем глобальный шрифт для всех виджетов
    font = QFont("Segoe UI", 13)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    # Создаём и отображаем главное окно
    window = SteganoWindow()
    window.show()

    # Запускаем главный цикл обработки событий Qt;
    # sys.exit() гарантирует корректный код завершения процесса
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

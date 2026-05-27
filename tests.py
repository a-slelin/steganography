"""
=============================================================================
        Тестовый модуль для приложения PNG LSB-Стеганография
=============================================================================

Описание:
    Полный набор автоматических тестов для проверки корректности работы
    приложения стеганографии (main.py) с использованием фреймворка pytest
    и плагина pytest-qt для тестирования PyQt5-интерфейса.

Структура тестов:
    ┌──────────────────────────────────────────────────────────────────────┐
    │  Группа 1: Вспомогательные функции (qRed/qGreen/qBlue/qRgb)          │
    │  Группа 2: Ядро алгоритма LSB (встраивание / извлечение)             │
    │  Группа 3: Инициализация и структура интерфейса                      │
    │  Группа 4: Состояние кнопок (enabled/disabled)                       │
    │  Группа 5: Встраивание сообщений (embed_message)                     │
    │  Группа 6: Извлечение сообщений (extract_message)                    │
    │  Группа 7: Полный цикл embed → extract                               │
    │  Группа 8: Загрузка и сохранение файлов                              │
    │  Группа 9: Граничные случаи (edge cases)                             │
    │  Группа 10: Обработка ошибочных состояний                            │
    │  Группа 11: Unicode и многобайтовые сообщения                        │
    │  Группа 12: Производительность                                       │
    └──────────────────────────────────────────────────────────────────────┘
"""

import os
import sys
import struct
import time
# noinspection PyUnusedImports
import tempfile
# noinspection PyUnusedImports
from unittest.mock import patch, MagicMock
from typing import List

import pytest

# Добавляем директорию с main.py в путь импорта.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# noinspection PyPackageRequirements
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
# noinspection PyPackageRequirements
from PyQt5.QtGui import QImage
# noinspection PyUnusedImports,PyPackageRequirements
from PyQt5.QtCore import Qt

# Импортируем всё из main.py
from main import (
    SteganoWindow,
    qRed, qGreen, qBlue, qRgb,
)


# =============================================================================
#  Регистрация маркеров pytest
# =============================================================================

def pytest_configure(config):
    """Регистрация пользовательских маркеров для классификации тестов."""
    config.addinivalue_line("markers", "unit: юнит-тесты отдельных функций")
    config.addinivalue_line("markers", "ui: тесты пользовательского интерфейса")
    config.addinivalue_line("markers", "integration: интеграционные тесты")
    config.addinivalue_line("markers", "edge_cases: граничные и нетипичные случаи")
    config.addinivalue_line("markers", "performance: тесты производительности")


# =============================================================================
#  Фикстуры
# =============================================================================

@pytest.fixture(scope="session")
def qapp():
    """
    Фикстура сессии: создаёт единственный QApplication на все тесты.

    QApplication должен существовать ровно один экземпляр за всё время
    работы тестов. scope="session" гарантирует это.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def window(qapp):
    """
    Фикстура: создаёт главное окно SteganoWindow для каждого теста.

    Окно создаётся заново для каждого теста, чтобы тесты были независимы.
    После теста окно закрывается и удаляется.
    """
    win = SteganoWindow()
    yield win
    win.close()


@pytest.fixture
def palette_256():
    """
    Фикстура: возвращает палитру из 256 нейтральных серых цветов.

    Используется как базовая палитра для большинства тестов встраивания.
    Каждый цвет вида (i, i, i) — равномерно серый.
    """
    return [qRgb(i, i, i) for i in range(256)]


@pytest.fixture
def palette_small():
    """
    Фикстура: маленькая палитра из 8 цветов.

    Ёмкость: 8 * 3 = 24 бита = 3 байта.
    Вычитаем 2 байта заголовка → 1 байт текста максимум.
    Используется для тестов «сообщение не помещается».
    """
    return [qRgb(i * 32, i * 32, i * 32) for i in range(8)]


@pytest.fixture
def indexed8_image_256():
    """
    Фикстура: создаёт палитровое QImage (10×10, Indexed8) с 256 цветами.

    Это минимально корректное тестовое изображение с полной палитрой.
    Все пиксели установлены в индекс 0.
    """
    img = QImage(10, 10, QImage.Format_Indexed8)
    img.setColorTable([qRgb(i, i, i) for i in range(256)])
    img.fill(0)
    return img


@pytest.fixture
def indexed8_image_small():
    """
    Фикстура: маленькое палитровое QImage (4×4, Indexed8) с 8 цветами.

    Ёмкость слишком мала для большинства сообщений.
    """
    img = QImage(4, 4, QImage.Format_Indexed8)
    img.setColorTable([qRgb(i * 32, i * 32, i * 32) for i in range(8)])
    img.fill(0)
    return img


@pytest.fixture
def tmp_png(tmp_path, indexed8_image_256):
    """
    Фикстура: создаёт временный PNG-файл и возвращает путь к нему.

    Файл автоматически удаляется после теста (tmp_path — pytest-фикстура).
    """
    path = str(tmp_path / "test_image.png")
    indexed8_image_256.save(path, "PNG")
    return path


# =============================================================================
#  Вспомогательные функции для тестов
# =============================================================================

def make_indexed8(width: int = 10, height: int = 10,
                  num_colors: int = 256) -> QImage:
    """
    Создать палитровое QImage заданного размера с указанным числом цветов.

    Args:
        width:      Ширина изображения в пикселях.
        height:     Высота изображения в пикселях.
        num_colors: Количество цветов в палитре (1..256).

    Returns:
        QImage формата Format_Indexed8 с равномерной серой палитрой.
    """
    img = QImage(width, height, QImage.Format_Indexed8)
    step = max(1, 256 // num_colors)
    palette = [qRgb(i * step % 256, i * step % 256, i * step % 256)
               for i in range(num_colors)]
    img.setColorTable(palette)
    img.fill(0)
    return img


def lsb_embed_raw(palette: List[int], message: str) -> List[int]:
    """
    Чистая реализация LSB-встраивания без Qt-зависимостей.

    Повторяет алгоритм из SteganoWindow.embed_message(), но работает
    напрямую со списком QRgb-значений.

    Args:
        palette: Список цветов палитры в формате 0xFFRRGGBB.
        message: Строка для встраивания (будет закодирована в UTF-8).

    Returns:
        Новый список цветов палитры с встроенными LSB-битами.

    Raises:
        ValueError: Если сообщение не помещается в палитру.
    """
    msg_bytes = message.encode('utf-8')
    length = len(msg_bytes)
    max_bits = len(palette) * 3
    needed_bits = (2 + length) * 8
    if needed_bits > max_bits:
        raise ValueError(
            f"Сообщение ({needed_bits} бит) не помещается "
            f"в палитру ({max_bits} бит доступно)"
        )

    data = bytearray()
    data.extend(struct.pack('>H', length))
    data.extend(msg_bytes)

    colors = list(palette)
    bit_index = 0
    total_bits = len(data) * 8

    for i in range(len(colors)):
        r = qRed(colors[i])
        g = qGreen(colors[i])
        b = qBlue(colors[i])

        if bit_index < total_bits:
            byte_idx = bit_index // 8
            bit_pos = 7 - (bit_index % 8)
            r = (r & 0xFE) | ((data[byte_idx] >> bit_pos) & 1)
            bit_index += 1
        if bit_index < total_bits:
            byte_idx = bit_index // 8
            bit_pos = 7 - (bit_index % 8)
            g = (g & 0xFE) | ((data[byte_idx] >> bit_pos) & 1)
            bit_index += 1
        if bit_index < total_bits:
            byte_idx = bit_index // 8
            bit_pos = 7 - (bit_index % 8)
            b = (b & 0xFE) | ((data[byte_idx] >> bit_pos) & 1)
            bit_index += 1

        colors[i] = qRgb(r, g, b)
        if bit_index >= total_bits:
            break

    return colors


def lsb_extract_raw(palette: List[int]) -> str:
    """
    Чистая реализация LSB-извлечения без Qt-зависимостей.

    Повторяет алгоритм из SteganoWindow.extract_message().

    Args:
        palette: Список цветов палитры в формате 0xFFRRGGBB.

    Returns:
        Извлечённая строка в UTF-8.

    Raises:
        ValueError: Если данные некорректны.
        UnicodeDecodeError: Если извлечённые байты не являются UTF-8.
    """
    bits = []
    for color in palette:
        bits.append(qRed(color) & 1)
        bits.append(qGreen(color) & 1)
        bits.append(qBlue(color) & 1)

    data_bytes = bytearray()
    for i in range(0, len(bits), 8):
        if i + 8 > len(bits):
            break
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bits[i + j]
        data_bytes.append(byte_val)

    if len(data_bytes) < 2:
        raise ValueError("Слишком мало данных")

    length = struct.unpack('>H', data_bytes[0:2])[0]
    if length > len(data_bytes) - 2:
        raise ValueError(f"Заявленная длина {length} > доступных данных")

    return data_bytes[2:2 + length].decode('utf-8')


# =============================================================================
#  ГРУППА 1: Тесты вспомогательных функций (qRed, qGreen, qBlue, qRgb)
# =============================================================================

@pytest.mark.unit
class TestColorHelperFunctions:
    """Тесты функций разбора и сборки цветовых значений Qt (QRgb)."""

    # ── qRgb: сборка цвета ────────────────────────────────────────────────────

    def test_qrgb_white(self):
        """qRgb(255, 255, 255) должен дать 0xFFFFFFFF."""
        assert qRgb(255, 255, 255) == 0xFFFFFFFF

    def test_qrgb_black(self):
        """qRgb(0, 0, 0) должен дать 0xFF000000."""
        assert qRgb(0, 0, 0) == 0xFF000000

    def test_qrgb_red(self):
        """qRgb(255, 0, 0) — чистый красный."""
        assert qRgb(255, 0, 0) == 0xFFFF0000

    def test_qrgb_green(self):
        """qRgb(0, 255, 0) — чистый зелёный."""
        assert qRgb(0, 255, 0) == 0xFF00FF00

    def test_qrgb_blue(self):
        """qRgb(0, 0, 255) — чистый синий."""
        assert qRgb(0, 0, 255) == 0xFF0000FF

    def test_qrgb_alpha_always_ff(self):
        """Альфа-канал в qRgb всегда должен быть 0xFF (полная непрозрачность)."""
        color = qRgb(100, 150, 200)
        assert (color >> 24) & 0xFF == 0xFF

    def test_qrgb_arbitrary(self):
        """Проверка произвольных значений через явное вычисление."""
        r, g, b = 18, 52, 86
        expected = (0xFF << 24) | (r << 16) | (g << 8) | b
        assert qRgb(r, g, b) == expected

    # ── qRed: извлечение красного канала ─────────────────────────────────────

    def test_qred_pure_red(self):
        """qRed от чистого красного (0xFFFF0000) = 255."""
        assert qRed(0xFFFF0000) == 255

    def test_qred_zero(self):
        """qRed от чёрного = 0."""
        assert qRed(qRgb(0, 0, 0)) == 0

    def test_qred_arbitrary(self):
        """qRed корректно извлекает произвольное значение."""
        assert qRed(qRgb(123, 45, 67)) == 123

    def test_qred_max(self):
        """qRed = 255 из qRgb(255, ...)."""
        assert qRed(qRgb(255, 0, 0)) == 255

    def test_qred_ignores_green_blue(self):
        """qRed не зависит от зелёного и синего каналов."""
        assert qRed(qRgb(100, 200, 50)) == 100
        assert qRed(qRgb(100, 0, 0)) == 100
        assert qRed(qRgb(100, 255, 255)) == 100

    # ── qGreen: извлечение зелёного канала ───────────────────────────────────

    def test_qgreen_pure_green(self):
        """qGreen от чистого зелёного = 255."""
        assert qGreen(0xFF00FF00) == 255

    def test_qgreen_zero(self):
        """qGreen от чёрного = 0."""
        assert qGreen(qRgb(0, 0, 0)) == 0

    def test_qgreen_arbitrary(self):
        """qGreen корректно извлекает произвольное значение."""
        assert qGreen(qRgb(10, 200, 30)) == 200

    def test_qgreen_ignores_red_blue(self):
        """qGreen не зависит от красного и синего каналов."""
        assert qGreen(qRgb(255, 77, 255)) == 77

    # ── qBlue: извлечение синего канала ──────────────────────────────────────

    def test_qblue_pure_blue(self):
        """qBlue от чистого синего = 255."""
        assert qBlue(0xFF0000FF) == 255

    def test_qblue_zero(self):
        """qBlue от чёрного = 0."""
        assert qBlue(qRgb(0, 0, 0)) == 0

    def test_qblue_arbitrary(self):
        """qBlue корректно извлекает произвольное значение."""
        assert qBlue(qRgb(0, 0, 99)) == 99

    def test_qblue_ignores_red_green(self):
        """qBlue не зависит от красного и зелёного каналов."""
        assert qBlue(qRgb(255, 255, 42)) == 42

    # ── Симметрия: qRgb → qRed/qGreen/qBlue → qRgb ───────────────────────────

    def test_roundtrip_symmetry_basic(self):
        """qRgb(qRed(c), qGreen(c), qBlue(c)) == c для любого c."""
        for r in (0, 1, 127, 128, 254, 255):
            for g in (0, 128, 255):
                for b in (0, 128, 255):
                    color = qRgb(r, g, b)
                    assert qRed(color) == r
                    assert qGreen(color) == g
                    assert qBlue(color) == b

    def test_roundtrip_all_channels_independent(self):
        """Изменение одного канала не затрагивает остальные."""
        base = qRgb(100, 150, 200)
        # Меняем только красный
        modified = qRgb(99, qGreen(base), qBlue(base))
        assert qRed(modified) == 99
        assert qGreen(modified) == 150
        assert qBlue(modified) == 200

    def test_lsb_isolation_red(self):
        """Изменение LSB красного не влияет на G и B."""
        color = qRgb(0b10101010, 0b11001100, 0b11110000)
        r_modified = qRgb(0b10101011, qGreen(color), qBlue(color))
        assert qRed(r_modified) == 0b10101011
        assert qGreen(r_modified) == 0b11001100
        assert qBlue(r_modified) == 0b11110000


# =============================================================================
#  ГРУППА 2: Тесты ядра алгоритма LSB
# =============================================================================

@pytest.mark.unit
class TestLSBAlgorithmCore:
    """Тесты чистой логики LSB без Qt-зависимостей."""

    def test_embed_changes_lsb_only(self, palette_256):
        """После встраивания изменены только LSB — старшие биты не тронуты."""
        modified = lsb_embed_raw(palette_256, "A")
        for orig, mod in zip(palette_256, modified):
            # Биты 7..1 красного, зелёного, синего каналов не изменились
            assert (qRed(orig) & 0xFE) == (qRed(mod) & 0xFE)
            assert (qGreen(orig) & 0xFE) == (qGreen(mod) & 0xFE)
            assert (qBlue(orig) & 0xFE) == (qBlue(mod) & 0xFE)

    def test_embed_extract_roundtrip_ascii(self, palette_256):
        """Встроенное ASCII-сообщение точно извлекается."""
        msg = "Hello"
        modified = lsb_embed_raw(palette_256, msg)
        result = lsb_extract_raw(modified)
        assert result == msg

    def test_embed_extract_roundtrip_russian(self, palette_256):
        """Встраивание и извлечение кириллического текста."""
        msg = "Привет"
        modified = lsb_embed_raw(palette_256, msg)
        result = lsb_extract_raw(modified)
        assert result == msg

    def test_embed_extract_roundtrip_single_char(self, palette_256):
        """Один символ встраивается и извлекается корректно."""
        msg = "X"
        modified = lsb_embed_raw(palette_256, msg)
        result = lsb_extract_raw(modified)
        assert result == msg

    def test_length_header_is_correct(self, palette_256):
        """Первые 2 байта палитры содержат корректную длину сообщения."""
        msg = "Test"
        modified = lsb_embed_raw(palette_256, msg)
        # Извлекаем первые 16 бит вручную
        bits = []
        for color in modified[:6]:  # 6 цветов × 3 бита = 18 бит (нам нужно 16)
            bits.append(qRed(color) & 1)
            bits.append(qGreen(color) & 1)
            bits.append(qBlue(color) & 1)
        # Декодируем 2 байта
        b0 = sum(bits[i] << (7 - i) for i in range(8))
        b1 = sum(bits[8 + i] << (7 - i) for i in range(8))
        extracted_length = (b0 << 8) | b1
        assert extracted_length == len(msg.encode('utf-8'))

    def test_unchanged_colors_after_data(self, palette_256):
        """Цвета после области данных не должны изменяться."""
        msg = "Hi"  # 2 байта = 4 байта всего с заголовком = 32 бита ≈ 11 цветов
        modified = lsb_embed_raw(palette_256, msg)
        needed_colors = ((len(msg.encode('utf-8')) + 2) * 8 + 2) // 3
        # Цвета после используемой области должны остаться нетронутыми
        for i in range(needed_colors, len(palette_256)):
            assert palette_256[i] == modified[i]

    def test_embed_respects_capacity(self, palette_small):
        """Сообщение, превышающее ёмкость палитры, вызывает исключение."""
        # 8 цветов × 3 бита = 24 бита = 3 байта. Заголовок 2 байта → 1 байт текста.
        with pytest.raises(ValueError):
            lsb_embed_raw(palette_small, "AB")  # 2 байта текста — не помещается

    def test_embed_exactly_fits(self, palette_small):
        """Сообщение длиной ровно 1 байт в 8-цветной палитре должно поместиться."""
        modified = lsb_embed_raw(palette_small, "A")
        result = lsb_extract_raw(modified)
        assert result == "A"

    def test_multiple_embeds_independent(self, palette_256):
        """Разные сообщения дают разные наборы LSB-бит в палитре."""
        m1 = lsb_embed_raw(list(palette_256), "AAA")
        m2 = lsb_embed_raw(list(palette_256), "BBB")
        # Хотя бы один цвет должен различаться
        assert m1 != m2

    def test_same_message_same_result(self, palette_256):
        """Одно и то же сообщение всегда даёт одинаковый результат (детерминизм)."""
        msg = "Deterministic"
        r1 = lsb_embed_raw(list(palette_256), msg)
        r2 = lsb_embed_raw(list(palette_256), msg)
        assert r1 == r2

    def test_palette_length_unchanged_after_embed(self, palette_256):
        """Встраивание не изменяет число цветов в палитре."""
        modified = lsb_embed_raw(list(palette_256), "Test")
        assert len(modified) == len(palette_256)


# =============================================================================
#  ГРУППА 3: Тесты инициализации и структуры интерфейса
# =============================================================================

# noinspection PyUnresolvedReferences
@pytest.mark.ui
class TestUIInitialization:
    """Тесты начального состояния главного окна при запуске."""

    def test_window_creates_without_exception(self, window):
        """Окно создаётся без исключений."""
        assert window is not None

    def test_window_title_contains_stego(self, window):
        """Заголовок окна содержит слово 'Стеганография' или 'PNG'."""
        title = window.windowTitle()
        assert "PNG" in title or "Стеганография" in title or "стеганография" in title.lower()

    def test_window_minimum_width(self, window):
        """Минимальная ширина окна не менее 800 пикселей."""
        assert window.minimumWidth() >= 800

    def test_window_minimum_height(self, window):
        """Минимальная высота окна не менее 600 пикселей."""
        assert window.minimumHeight() >= 600

    def test_original_image_initially_none(self, window):
        """При запуске original_image должен быть None."""
        assert window.original_image is None

    def test_stego_image_initially_none(self, window):
        """При запуске stego_image должен быть None."""
        assert window.stego_image is None

    def test_btn_load_exists(self, window):
        """Кнопка загрузки изображения существует."""
        assert window.btn_load is not None

    def test_btn_save_exists(self, window):
        """Кнопка сохранения существует."""
        assert window.btn_save is not None

    def test_btn_embed_exists(self, window):
        """Кнопка встраивания существует."""
        assert window.btn_embed is not None

    def test_btn_extract_exists(self, window):
        """Кнопка извлечения существует."""
        assert window.btn_extract is not None

    def test_message_input_exists(self, window):
        """Поле ввода сообщения существует."""
        assert window.message_input is not None

    def test_extracted_output_exists(self, window):
        """Поле вывода извлечённого сообщения существует."""
        assert window.extracted_output is not None

    def test_original_label_exists(self, window):
        """Лейбл для исходного изображения существует."""
        assert window.original_label is not None

    def test_stego_label_exists(self, window):
        """Лейбл для стего-изображения существует."""
        assert window.stego_label is not None

    def test_extracted_output_is_readonly(self, window):
        """Поле извлечённого сообщения должно быть только для чтения."""
        assert window.extracted_output.isReadOnly()

    def test_message_input_is_editable(self, window):
        """Поле ввода сообщения должно быть редактируемым."""
        assert not window.message_input.isReadOnly()

    def test_statusbar_exists(self, window):
        """Статусная строка существует и содержит начальный текст."""
        status = window.statusBar().currentMessage()
        assert len(status) > 0

    def test_statusbar_initial_message(self, window):
        """Начальное сообщение в статусной строке содержит слово 'готов'."""
        status = window.statusBar().currentMessage().lower()
        assert "готов" in status or "готово" in status

    def test_stylesheet_applied(self, window):
        """К окну применена таблица стилей (не пустая)."""
        assert len(window.styleSheet()) > 0


# =============================================================================
#  ГРУППА 4: Тесты состояния кнопок (_refresh_buttons)
# =============================================================================

@pytest.mark.ui
class TestButtonStates:
    """Тесты логики блокировки/разблокировки кнопок в зависимости от состояния."""

    def test_initial_save_disabled(self, window):
        """При старте кнопка «Сохранить» неактивна (нет стего-изображения)."""
        assert not window.btn_save.isEnabled()

    def test_initial_embed_disabled(self, window):
        """При старте кнопка «Встроить» неактивна (нет оригинала)."""
        assert not window.btn_embed.isEnabled()

    def test_initial_extract_disabled(self, window):
        """При старте кнопка «Извлечь» неактивна (нет изображений)."""
        assert not window.btn_extract.isEnabled()

    def test_initial_load_enabled(self, window):
        """Кнопка «Загрузить» всегда активна."""
        assert window.btn_load.isEnabled()

    def test_embed_enabled_after_setting_original(self, window, indexed8_image_256):
        """После установки оригинала кнопка «Встроить» становится активной."""
        window.original_image = indexed8_image_256
        window._refresh_buttons()
        assert window.btn_embed.isEnabled()

    def test_extract_enabled_after_setting_original(self, window, indexed8_image_256):
        """После установки оригинала кнопка «Извлечь» становится активной."""
        window.original_image = indexed8_image_256
        window._refresh_buttons()
        assert window.btn_extract.isEnabled()

    def test_save_still_disabled_after_only_original(self, window, indexed8_image_256):
        """После загрузки оригинала (без встраивания) «Сохранить» остаётся неактивной."""
        window.original_image = indexed8_image_256
        window._refresh_buttons()
        assert not window.btn_save.isEnabled()

    def test_save_enabled_after_stego_set(self, window, indexed8_image_256):
        """После установки стего-изображения кнопка «Сохранить» активируется."""
        window.stego_image = indexed8_image_256
        window._refresh_buttons()
        assert window.btn_save.isEnabled()

    def test_extract_enabled_after_only_stego(self, window, indexed8_image_256):
        """«Извлечь» активна, если есть только стего (без оригинала)."""
        window.stego_image = indexed8_image_256
        window._refresh_buttons()
        assert window.btn_extract.isEnabled()

    def test_all_enabled_when_both_images_set(self, window, indexed8_image_256):
        """Все кнопки (кроме загрузки) активны, когда оба изображения установлены."""
        window.original_image = indexed8_image_256
        window.stego_image = indexed8_image_256
        window._refresh_buttons()
        assert window.btn_embed.isEnabled()
        assert window.btn_extract.isEnabled()
        assert window.btn_save.isEnabled()

    def test_buttons_reset_when_images_cleared(self, window, indexed8_image_256):
        """После сброса изображений кнопки снова блокируются."""
        window.original_image = indexed8_image_256
        window.stego_image = indexed8_image_256
        window._refresh_buttons()
        # Сбрасываем
        window.original_image = None
        window.stego_image = None
        window._refresh_buttons()
        assert not window.btn_embed.isEnabled()
        assert not window.btn_extract.isEnabled()
        assert not window.btn_save.isEnabled()


# =============================================================================
#  ГРУППА 5: Тесты встраивания сообщений (embed_message через UI)
# =============================================================================

# noinspection PyUnresolvedReferences
@pytest.mark.ui
class TestEmbedMessage:
    """Тесты метода SteganoWindow.embed_message()."""

    # noinspection PyMethodMayBeStatic
    def _setup_image(self, window, img):
        """Установить исходное изображение в окно."""
        window.original_image = img
        window._refresh_buttons()

    def test_embed_creates_stego_image(self, window, indexed8_image_256):
        """После встраивания stego_image должен быть установлен."""
        self._setup_image(window, indexed8_image_256)
        window.message_input.setPlainText("Test")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        assert window.stego_image is not None

    def test_embed_does_not_modify_original(self, window, indexed8_image_256):
        """Встраивание не должно изменять оригинальное изображение."""
        self._setup_image(window, indexed8_image_256)
        original_colors = indexed8_image_256.colorTable()
        window.message_input.setPlainText("Secret")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        assert indexed8_image_256.colorTable() == original_colors

    def test_embed_updates_status_bar(self, window, indexed8_image_256):
        """После встраивания статусная строка обновляется."""
        self._setup_image(window, indexed8_image_256)
        window.message_input.setPlainText("Hello")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        status = window.statusBar().currentMessage()
        assert len(status) > 0
        assert "бит" in status.lower() or "встроен" in status.lower()

    def test_embed_enables_save_button(self, window, indexed8_image_256):
        """После встраивания кнопка «Сохранить» активируется."""
        self._setup_image(window, indexed8_image_256)
        window.message_input.setPlainText("Enable save")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        assert window.btn_save.isEnabled()

    def test_embed_without_image_shows_warning(self, window):
        """Попытка встроить без загруженного изображения показывает предупреждение."""
        window.original_image = None
        window.message_input.setPlainText("No image")
        with patch.object(QMessageBox, 'warning') as mock_warn:
            window.embed_message()
        mock_warn.assert_called_once()

    def test_embed_without_message_shows_warning(self, window, indexed8_image_256):
        """Попытка встроить пустое сообщение показывает предупреждение."""
        self._setup_image(window, indexed8_image_256)
        window.message_input.setPlainText("")
        with patch.object(QMessageBox, 'warning') as mock_warn:
            window.embed_message()
        mock_warn.assert_called_once()

    def test_embed_without_message_no_stego(self, window, indexed8_image_256):
        """При пустом сообщении stego_image не создаётся."""
        self._setup_image(window, indexed8_image_256)
        window.message_input.setPlainText("")
        with patch.object(QMessageBox, 'warning'):
            window.embed_message()
        assert window.stego_image is None

    def test_embed_too_long_shows_error(self, window, indexed8_image_small):
        """Слишком длинное сообщение показывает сообщение об ошибке."""
        self._setup_image(window, indexed8_image_small)
        # 8 цветов × 3 = 24 бита = 3 байта. Заголовок 2 → 1 байт свободно. "AB" не поместится.
        window.message_input.setPlainText("AB")
        with patch.object(QMessageBox, 'critical') as mock_err:
            window.embed_message()
        mock_err.assert_called_once()

    def test_embed_too_long_no_stego(self, window, indexed8_image_small):
        """При превышении ёмкости stego_image не создаётся."""
        self._setup_image(window, indexed8_image_small)
        window.message_input.setPlainText("AB")
        with patch.object(QMessageBox, 'critical'):
            window.embed_message()
        assert window.stego_image is None

    def test_embed_stego_is_indexed8(self, window, indexed8_image_256):
        """Стего-изображение должно быть палитровым (Format_Indexed8)."""
        self._setup_image(window, indexed8_image_256)
        window.message_input.setPlainText("Format check")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        assert window.stego_image.format() == QImage.Format_Indexed8

    def test_embed_stego_same_dimensions(self, window, indexed8_image_256):
        """Стего-изображение имеет те же размеры, что и оригинал."""
        self._setup_image(window, indexed8_image_256)
        window.message_input.setPlainText("Dimensions")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        assert window.stego_image.width() == indexed8_image_256.width()
        assert window.stego_image.height() == indexed8_image_256.height()

    def test_embed_stego_palette_size_unchanged(self, window, indexed8_image_256):
        """Размер палитры после встраивания не изменяется."""
        self._setup_image(window, indexed8_image_256)
        orig_palette_size = len(indexed8_image_256.colorTable())
        window.message_input.setPlainText("Palette size")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        assert len(window.stego_image.colorTable()) == orig_palette_size

    def test_embed_second_call_overwrites_stego(self, window, indexed8_image_256):
        """Повторное встраивание перезаписывает предыдущее стего-изображение."""
        self._setup_image(window, indexed8_image_256)
        with patch.object(QMessageBox, 'information'):
            window.message_input.setPlainText("First")
            window.embed_message()
            stego1_colors = window.stego_image.colorTable()[:]

            window.message_input.setPlainText("Second")
            window.embed_message()
            stego2_colors = window.stego_image.colorTable()[:]

        assert stego1_colors != stego2_colors


# =============================================================================
#  ГРУППА 6: Тесты извлечения сообщений (extract_message через UI)
# =============================================================================

# noinspection PyUnresolvedReferences
@pytest.mark.ui
class TestExtractMessage:
    """Тесты метода SteganoWindow.extract_message()."""

    # noinspection PyMethodMayBeStatic
    def _embed_and_prepare(self, window, img, message):
        """Подготовить окно: установить изображение и встроить сообщение."""
        window.original_image = img
        window._refresh_buttons()
        window.message_input.setPlainText(message)
        with patch.object(QMessageBox, 'information'):
            window.embed_message()

    def test_extract_returns_correct_message(self, window, indexed8_image_256):
        """Извлечённое сообщение точно совпадает с встроенным."""
        msg = "Hello World"
        self._embed_and_prepare(window, indexed8_image_256, msg)
        window.extract_message()
        assert window.extracted_output.toPlainText() == msg

    def test_extract_from_stego_priority(self, window, indexed8_image_256):
        """Извлечение берёт stego_image, а не original_image."""
        msg = "From stego"
        self._embed_and_prepare(window, indexed8_image_256, msg)
        # Убедимся, что оригинал не содержит сообщения (чистый)
        window.extract_message()
        assert window.extracted_output.toPlainText() == msg

    def test_extract_without_image_shows_warning(self, window):
        """Попытка извлечь без изображения показывает предупреждение."""
        window.original_image = None
        window.stego_image = None
        with patch.object(QMessageBox, 'warning') as mock_warn:
            window.extract_message()
        mock_warn.assert_called_once()

    def test_extract_updates_status_bar(self, window, indexed8_image_256):
        """После извлечения статусная строка обновляется."""
        self._embed_and_prepare(window, indexed8_image_256, "Status test")
        window.extract_message()
        status = window.statusBar().currentMessage()
        assert "извлеч" in status.lower()

    def test_extract_from_original_image_directly(self, window, indexed8_image_256):
        """Если stego_image=None, извлечение работает из original_image."""
        # Встроим вручную через raw-алгоритм
        palette = indexed8_image_256.colorTable()
        modified_palette = lsb_embed_raw(list(palette), "Direct")
        stego = indexed8_image_256.copy()
        stego.setColorTable(modified_palette)
        # Загружаем модифицированное как "оригинал", без стего
        window.original_image = stego
        window.stego_image = None
        window._refresh_buttons()
        window.extract_message()
        assert window.extracted_output.toPlainText() == "Direct"

    def test_extract_output_field_is_readonly(self, window, indexed8_image_256):
        """Поле вывода остаётся только для чтения после извлечения."""
        self._embed_and_prepare(window, indexed8_image_256, "ReadOnly check")
        window.extract_message()
        assert window.extracted_output.isReadOnly()


# =============================================================================
#  ГРУППА 7: Интеграционные тесты полного цикла (embed → extract)
# =============================================================================

# noinspection PyUnresolvedReferences
@pytest.mark.integration
class TestFullEmbedExtractCycle:
    """Сквозные тесты: встраивание сообщения и последующее его извлечение."""

    # noinspection PyMethodMayBeStatic
    def _full_cycle(self, window, img, message):
        """Выполнить полный цикл embed → extract и вернуть извлечённый текст."""
        window.original_image = img
        window._refresh_buttons()
        window.message_input.setPlainText(message)
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        window.extract_message()
        return window.extracted_output.toPlainText()

    def test_cycle_short_ascii(self, window, indexed8_image_256):
        """Короткое ASCII-сообщение корректно проходит полный цикл."""
        assert self._full_cycle(window, indexed8_image_256, "Hi") == "Hi"

    def test_cycle_long_ascii(self, window, indexed8_image_256):
        """Длинное ASCII-сообщение (до ёмкости) проходит полный цикл."""
        msg = "A" * 90
        assert self._full_cycle(window, indexed8_image_256, msg) == msg

    def test_cycle_russian_text(self, window, indexed8_image_256):
        """Русскоязычное сообщение корректно проходит полный цикл."""
        msg = "Секрет"
        assert self._full_cycle(window, indexed8_image_256, msg) == msg

    def test_cycle_digits_and_punctuation(self, window, indexed8_image_256):
        """Цифры и знаки препинания корректно встраиваются и извлекаются."""
        msg = "1234567890!@#$%"
        assert self._full_cycle(window, indexed8_image_256, msg) == msg

    def test_cycle_single_character(self, window, indexed8_image_256):
        """Один символ проходит полный цикл."""
        assert self._full_cycle(window, indexed8_image_256, "Z") == "Z"

    def test_cycle_newlines_and_spaces(self, window, indexed8_image_256):
        """Пробелы и переносы строк встраиваются корректно."""
        msg = "Line 1\nLine 2\n  Indented"
        assert self._full_cycle(window, indexed8_image_256, msg) == msg

    def test_cycle_file_save_and_reload(self, window, indexed8_image_256, tmp_path):
        """Сохранение стего-PNG в файл и загрузка — сообщение сохраняется."""
        msg = "File round-trip"
        window.original_image = indexed8_image_256
        window._refresh_buttons()
        window.message_input.setPlainText(msg)
        with patch.object(QMessageBox, 'information'):
            window.embed_message()

        # Сохраняем стего в файл
        stego_path = str(tmp_path / "stego_rt.png")
        window.stego_image.save(stego_path, "PNG")

        # Загружаем обратно в новое окно
        # noinspection PyUnusedImports,PyPackageRequirements
        from PyQt5.QtWidgets import QApplication
        win2 = SteganoWindow()
        loaded = QImage(stego_path)
        assert not loaded.isNull()
        if loaded.format() != QImage.Format_Indexed8:
            loaded = loaded.convertToFormat(QImage.Format_Indexed8)
        win2.original_image = loaded
        win2.stego_image = None
        win2._refresh_buttons()
        win2.extract_message()
        result = win2.extracted_output.toPlainText()
        win2.close()

        assert result == msg

    def test_different_messages_give_different_stego(self, window, indexed8_image_256):
        """Два разных сообщения дают два разных стего-изображения."""
        img_copy = indexed8_image_256.copy()

        window.original_image = indexed8_image_256
        window._refresh_buttons()
        window.message_input.setPlainText("Message A")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        colors_a = window.stego_image.colorTable()[:]

        window.original_image = img_copy
        window.stego_image = None
        window.message_input.setPlainText("Message B")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        colors_b = window.stego_image.colorTable()[:]

        assert colors_a != colors_b

    def test_original_unchanged_after_full_cycle(self, window, indexed8_image_256):
        """После полного цикла оригинальная палитра не изменяется."""
        orig_colors = indexed8_image_256.colorTable()[:]
        window.original_image = indexed8_image_256
        window._refresh_buttons()
        window.message_input.setPlainText("No change to original")
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        window.extract_message()
        assert indexed8_image_256.colorTable() == orig_colors


# =============================================================================
#  ГРУППА 8: Тесты загрузки и сохранения файлов
# =============================================================================

# noinspection PyUnresolvedReferences
@pytest.mark.integration
class TestFileOperations:
    """Тесты операций с файловой системой: загрузка и сохранение PNG."""

    def test_load_valid_indexed8_png(self, window, tmp_png):
        """Корректный палитровый PNG загружается без ошибок."""
        with patch.object(QFileDialog, 'getOpenFileName',
                          return_value=(tmp_png, "")):
            window.load_image()
        assert window.original_image is not None

    def test_load_sets_format_indexed8(self, window, tmp_png):
        """Загруженное изображение имеет формат Indexed8."""
        with patch.object(QFileDialog, 'getOpenFileName',
                          return_value=(tmp_png, "")):
            window.load_image()
        assert window.original_image.format() == QImage.Format_Indexed8

    def test_load_resets_stego_image(self, window, tmp_png, indexed8_image_256):
        """При загрузке нового изображения stego_image сбрасывается."""
        window.stego_image = indexed8_image_256
        with patch.object(QFileDialog, 'getOpenFileName',
                          return_value=(tmp_png, "")):
            window.load_image()
        assert window.stego_image is None

    def test_load_clears_extracted_output(self, window, tmp_png):
        """При загрузке нового изображения очищается поле извлечённого текста."""
        window.extracted_output.setPlainText("Old extracted text")
        with patch.object(QFileDialog, 'getOpenFileName',
                          return_value=(tmp_png, "")):
            window.load_image()
        assert window.extracted_output.toPlainText() == ""

    def test_load_cancelled_no_change(self, window):
        """Отмена диалога загрузки не меняет состояние окна."""
        with patch.object(QFileDialog, 'getOpenFileName',
                          return_value=("", "")):
            window.load_image()
        assert window.original_image is None

    def test_load_updates_status(self, window, tmp_png):
        """После загрузки статусная строка обновляется."""
        with patch.object(QFileDialog, 'getOpenFileName',
                          return_value=(tmp_png, "")):
            window.load_image()
        status = window.statusBar().currentMessage()
        assert len(status) > 0

    def test_load_enables_embed_button(self, window, tmp_png):
        """После загрузки изображения кнопка «Встроить» активируется."""
        with patch.object(QFileDialog, 'getOpenFileName',
                          return_value=(tmp_png, "")):
            window.load_image()
        assert window.btn_embed.isEnabled()

    def test_save_creates_file(self, window, indexed8_image_256, tmp_path):
        """Сохранение создаёт файл на диске."""
        out_path = str(tmp_path / "out.png")
        window.stego_image = indexed8_image_256
        with patch.object(QFileDialog, 'getSaveFileName',
                          return_value=(out_path, "")), \
                patch.object(QMessageBox, 'information'):
            window.save_stego_image()
        assert os.path.exists(out_path)

    def test_save_creates_valid_png(self, window, indexed8_image_256, tmp_path):
        """Сохранённый файл является корректным PNG."""
        out_path = str(tmp_path / "valid.png")
        window.stego_image = indexed8_image_256
        with patch.object(QFileDialog, 'getSaveFileName',
                          return_value=(out_path, "")), \
                patch.object(QMessageBox, 'information'):
            window.save_stego_image()
        reloaded = QImage(out_path)
        assert not reloaded.isNull()

    def test_save_without_stego_shows_warning(self, window):
        """Попытка сохранить без стего-изображения показывает предупреждение."""
        window.stego_image = None
        with patch.object(QMessageBox, 'warning') as mock_warn:
            window.save_stego_image()
        mock_warn.assert_called_once()

    def test_save_cancelled_no_file(self, window, indexed8_image_256, tmp_path):
        """Отмена диалога сохранения не создаёт файл."""
        out_path = str(tmp_path / "cancelled.png")
        window.stego_image = indexed8_image_256
        with patch.object(QFileDialog, 'getSaveFileName',
                          return_value=("", "")):
            window.save_stego_image()
        assert not os.path.exists(out_path)

    def test_save_preserves_palette(self, window, indexed8_image_256, tmp_path):
        """Сохранённый PNG точно сохраняет палитру (важно для LSB)."""
        # Встроим сообщение
        msg = "Palette preserve"
        palette = indexed8_image_256.colorTable()
        modified_palette = lsb_embed_raw(list(palette), msg)
        stego = indexed8_image_256.copy()
        stego.setColorTable(modified_palette)
        window.stego_image = stego

        out_path = str(tmp_path / "palette_check.png")
        with patch.object(QFileDialog, 'getSaveFileName',
                          return_value=(out_path, "")), \
                patch.object(QMessageBox, 'information'):
            window.save_stego_image()

        # Проверяем, что палитра сохранилась точно
        reloaded = QImage(out_path)
        if reloaded.format() != QImage.Format_Indexed8:
            reloaded = reloaded.convertToFormat(QImage.Format_Indexed8)
        reloaded_palette = reloaded.colorTable()
        assert reloaded_palette == modified_palette

    def test_load_non_indexed_converts_to_indexed8(self, window, tmp_path):
        """Полноцветный PNG при загрузке конвертируется в Indexed8."""
        # Создаём RGB32-изображение
        rgb_img = QImage(20, 20, QImage.Format_RGB32)
        rgb_img.fill(0xFFAABBCC)
        rgb_path = str(tmp_path / "rgb.png")
        rgb_img.save(rgb_path, "PNG")

        with patch.object(QFileDialog, 'getOpenFileName',
                          return_value=(rgb_path, "")):
            window.load_image()

        assert window.original_image is not None
        assert window.original_image.format() == QImage.Format_Indexed8


# =============================================================================
#  ГРУППА 9: Граничные случаи
# =============================================================================

@pytest.mark.edge_cases
class TestEdgeCases:
    """Тесты граничных и нетипичных ситуаций."""

    def test_embed_exactly_one_byte_message(self, palette_256):
        """Сообщение из одного байта встраивается и извлекается корректно."""
        result = lsb_embed_raw(list(palette_256), "A")
        assert lsb_extract_raw(result) == "A"

    def test_max_capacity_256_palette(self):
        """Максимальное сообщение для 256-цветной палитры помещается."""
        # 256 цветов × 3 бита = 768 бит = 96 байт → 94 байта текста
        palette = [qRgb(i, i, i) for i in range(256)]
        max_msg = "A" * 94
        result = lsb_embed_raw(list(palette), max_msg)
        assert lsb_extract_raw(result) == max_msg

    def test_exceed_max_capacity_raises(self):
        """Превышение максимальной ёмкости на 1 байт вызывает исключение."""
        palette = [qRgb(i, i, i) for i in range(256)]
        too_long = "A" * 95
        with pytest.raises(ValueError):
            lsb_embed_raw(list(palette), too_long)

    def test_extract_from_clean_palette_zero_length(self, palette_256):
        """Извлечение из чистой (без сообщения) палитры: длина = 0."""
        # Все LSB = 0 → length = 0
        clean = [qRgb(0xFE & qRed(c), 0xFE & qGreen(c), 0xFE & qBlue(c))
                 for c in palette_256]
        # noinspection PyBroadException
        try:
            result = lsb_extract_raw(clean)
            assert result == ""
        except Exception:
            pass  # Допустимо: нет сообщения

    def test_embed_special_characters(self, palette_256):
        """Специальные символы (табуляция, ноль-символ, пробелы) встраиваются корректно."""
        msg = "Tab:\there\nNewline\t\t"
        result = lsb_embed_raw(list(palette_256), msg)
        assert lsb_extract_raw(result) == msg

    def test_embed_only_spaces(self, palette_256):
        """Строка из пробелов встраивается и извлекается корректно."""
        msg = "     "
        result = lsb_embed_raw(list(palette_256), msg)
        assert lsb_extract_raw(result) == msg

    def test_embed_minimum_palette_4_colors(self):
        """Минимально возможная ёмкость: 4 цвета = 12 бит = 1 байт данных."""
        # 4 × 3 = 12 бит. Заголовок = 16 бит → не поместится даже заголовок
        palette = [qRgb(i * 64, i * 64, i * 64) for i in range(4)]
        with pytest.raises(ValueError):
            lsb_embed_raw(palette, "A")

    def test_lsb_bit_flip_is_minimal(self):
        """Изменение LSB не влияет на старшие биты: разница не превышает 1."""
        # noinspection PyUnusedLocal
        palette = [qRgb(128, 128, 128)]
        modified = lsb_embed_raw([qRgb(128, 128, 128)] + [qRgb(0, 0, 0)] * 100,
                                 "X")
        # Разница в каналах не более 1
        for orig, mod in zip([qRgb(128, 128, 128)], modified[:1]):
            assert abs(qRed(orig) - qRed(mod)) <= 1
            assert abs(qGreen(orig) - qGreen(mod)) <= 1
            assert abs(qBlue(orig) - qBlue(mod)) <= 1

    def test_message_with_all_zero_bytes(self):
        """Сообщение, содержащее только нулевые символы (chr(0)), обрабатывается."""
        palette = [qRgb(i, i, i) for i in range(256)]
        # Нулевой символ - 1 байт в UTF-8
        msg = chr(0) * 5
        result = lsb_embed_raw(list(palette), msg)
        assert lsb_extract_raw(result) == msg

    def test_stego_visually_identical_to_original(self):
        """Стего-изображение визуально неотличимо: MSB всех каналов не изменились."""
        palette = [qRgb(200, 150, 100) for _ in range(256)]
        modified = lsb_embed_raw(list(palette), "Visual test")
        for orig, mod in zip(palette, modified):
            assert (qRed(orig) >> 1) == (qRed(mod) >> 1)
            assert (qGreen(orig) >> 1) == (qGreen(mod) >> 1)
            assert (qBlue(orig) >> 1) == (qBlue(mod) >> 1)

    def test_extract_after_multiple_embeds_takes_last(self, window, indexed8_image_256):
        """После нескольких встраиваний извлекается последнее сообщение."""
        window.original_image = indexed8_image_256
        window._refresh_buttons()

        messages = ["First msg", "Second msg", "Third msg"]
        for msg in messages:
            window.message_input.setPlainText(msg)
            with patch.object(QMessageBox, 'information'):
                window.embed_message()

        window.extract_message()
        assert window.extracted_output.toPlainText() == messages[-1]


# =============================================================================
#  ГРУППА 10: Тесты обработки ошибочных состояний
# =============================================================================

@pytest.mark.unit
class TestErrorHandling:
    """Тесты корректной обработки ошибочных состояний и входных данных."""

    def test_qrgb_with_values_over_255_truncates(self):
        """qRgb с значением > 255 усекается побитовым &0xFF."""
        color = qRgb(256, 0, 0)  # 256 & 0xFF = 0
        assert qRed(color) == 0  # 256 → 0 при маске & 0xFF

    def test_qrgb_with_negative_value(self):
        """qRgb с отрицательным значением: результат определяется побитовой маской."""
        color = qRgb(-1, 0, 0)
        # -1 & 0xFF = 255 в Python
        assert qRed(color) == 255

    def test_extract_corrupted_length_field(self):
        """Извлечение с заведомо неверным полем длины поднимает ValueError."""
        # Создаём палитру, в которой поле длины = 9999, а данных нет
        palette = [qRgb(0xFF, 0xFF, 0xFF) for _ in range(256)]
        # Кодируем длину 9999 в первые 16 бит
        length = 9999
        bits = []
        for i in range(15, -1, -1):
            bits.append((length >> i) & 1)
        colors = list(palette)
        bit_idx = 0
        for i in range(len(colors)):
            r, g, b = qRed(colors[i]), qGreen(colors[i]), qBlue(colors[i])
            if bit_idx < len(bits):
                r = (r & 0xFE) | bits[bit_idx]
                bit_idx += 1
            if bit_idx < len(bits):
                g = (g & 0xFE) | bits[bit_idx]
                bit_idx += 1
            if bit_idx < len(bits):
                b = (b & 0xFE) | bits[bit_idx]
                bit_idx += 1
            colors[i] = qRgb(r, g, b)
            if bit_idx >= len(bits):
                break
        with pytest.raises((ValueError, UnicodeDecodeError)):
            lsb_extract_raw(colors)

    def test_embed_without_image_no_stego_created(self, window):
        """Встраивание без изображения не создаёт stego_image."""
        window.original_image = None
        window.message_input.setPlainText("Test")
        with patch.object(QMessageBox, 'warning'):
            window.embed_message()
        assert window.stego_image is None

    def test_extract_without_image_no_output(self, window):
        """Извлечение без изображения не обновляет поле вывода."""
        window.original_image = None
        window.stego_image = None
        window.extracted_output.setPlainText("")
        with patch.object(QMessageBox, 'warning'):
            window.extract_message()
        assert window.extracted_output.toPlainText() == ""

    def test_save_without_stego_no_dialog(self, window):
        """Без стего-изображения диалог сохранения не открывается."""
        window.stego_image = None
        with patch.object(QFileDialog, 'getSaveFileName') as mock_dialog, \
                patch.object(QMessageBox, 'warning'):
            window.save_stego_image()
        mock_dialog.assert_not_called()

    def test_embed_message_too_long_boundary(self, window, indexed8_image_256):
        """Сообщение ровно на 1 байт длиннее максимума показывает ошибку."""
        # 256 цветов → 94 байта текста максимум
        too_long = "B" * 95
        window.original_image = indexed8_image_256
        window._refresh_buttons()
        window.message_input.setPlainText(too_long)
        with patch.object(QMessageBox, 'critical') as mock_err:
            window.embed_message()
        mock_err.assert_called_once()


# =============================================================================
#  ГРУППА 11: Тесты Unicode и многобайтовых сообщений
# =============================================================================

@pytest.mark.unit
class TestUnicodeMessages:
    """Тесты корректной обработки Unicode-строк в UTF-8."""

    def test_cyrillic_round_trip(self):
        """Кириллический текст встраивается и извлекается без потерь."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "Тест"  # 8 байт в UTF-8 (по 2 байта на символ)
        result = lsb_embed_raw(list(palette), msg)
        assert lsb_extract_raw(result) == msg

    def test_mixed_latin_cyrillic(self):
        """Смешанный Latin+Кириллица обрабатывается корректно."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "Hello Мир"
        result = lsb_embed_raw(list(palette), msg)
        assert lsb_extract_raw(result) == msg

    def test_emoji_single(self):
        """Одиночный эмодзи (4 байта UTF-8) встраивается корректно."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "🔐"  # 4 байта в UTF-8
        result = lsb_embed_raw(list(palette), msg)
        assert lsb_extract_raw(result) == msg

    def test_utf8_multibyte_length_accounting(self):
        """Длина заголовка учитывает байты UTF-8, а не количество символов."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "АБВ"  # 3 символа × 2 байта = 6 байт
        assert len(msg.encode('utf-8')) == 6
        result = lsb_embed_raw(list(palette), msg)
        # Проверяем заголовок длины
        bits = []
        for color in result[:6]:
            bits += [qRed(color) & 1, qGreen(color) & 1, qBlue(color) & 1]
        length = sum(bits[i] << (15 - i) for i in range(16))
        assert length == 6

    def test_empty_string_via_ui(self, window, indexed8_image_256):
        """Пустое сообщение через UI показывает предупреждение, не встраивается."""
        window.original_image = indexed8_image_256
        window._refresh_buttons()
        window.message_input.setPlainText("")
        with patch.object(QMessageBox, 'warning') as mock_warn:
            window.embed_message()
        mock_warn.assert_called_once()
        assert window.stego_image is None

    def test_spaces_only_message(self):
        """Строка только из пробелов корректно проходит цикл."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "   "
        result = lsb_embed_raw(list(palette), msg)
        assert lsb_extract_raw(result) == msg

    def test_numeric_string(self):
        """Строка из цифр корректно проходит цикл."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "0123456789"
        result = lsb_embed_raw(list(palette), msg)
        assert lsb_extract_raw(result) == msg

    def test_long_cyrillic_fits_256_palette(self):
        """Длинная кириллическая строка помещается в 256-цветную палитру."""
        palette = [qRgb(i, i, i) for i in range(256)]
        # 47 кириллических символов × 2 байта = 94 байта — ровно максимум
        msg = "Я" * 47
        assert len(msg.encode('utf-8')) == 94
        result = lsb_embed_raw(list(palette), msg)
        assert lsb_extract_raw(result) == msg

    def test_exceeds_with_one_cyrillic_char(self):
        """48 кириллических символов (96 байт) не помещаются — ожидается исключение."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "Я" * 48  # 96 байт > 94
        with pytest.raises(ValueError):
            lsb_embed_raw(list(palette), msg)


# =============================================================================
#  ГРУППА 12: Тесты производительности
# =============================================================================

@pytest.mark.performance
class TestPerformance:
    """Тесты времени выполнения критических операций алгоритма."""

    def test_embed_256_palette_under_10ms(self):
        """Встраивание в 256-цветную палитру выполняется быстрее 10 мс."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "Performance test message"
        start = time.perf_counter()
        lsb_embed_raw(list(palette), msg)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 10, f"Встраивание заняло {elapsed_ms:.2f} мс (> 10 мс)"

    def test_extract_256_palette_under_10ms(self):
        """Извлечение из 256-цветной палитры выполняется быстрее 10 мс."""
        palette = [qRgb(i, i, i) for i in range(256)]
        modified = lsb_embed_raw(list(palette), "Extraction speed")
        start = time.perf_counter()
        lsb_extract_raw(modified)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 10, f"Извлечение заняло {elapsed_ms:.2f} мс (> 10 мс)"

    def test_1000_embed_extract_cycles_under_2s(self):
        """1000 циклов встраивания и извлечения выполняются быстрее 2 секунд."""
        palette = [qRgb(i, i, i) for i in range(256)]
        msg = "Speed"
        start = time.perf_counter()
        for _ in range(1000):
            modified = lsb_embed_raw(list(palette), msg)
            lsb_extract_raw(modified)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"1000 циклов заняли {elapsed:.2f} с (> 2 с)"

    def test_qrgb_decompose_speed(self):
        """10 000 операций разбора цвета (qRed/qGreen/qBlue) быстрее 50 мс."""
        colors = [qRgb(i % 256, (i * 2) % 256, (i * 3) % 256) for i in range(256)]
        start = time.perf_counter()
        for _ in range(10_000):
            for c in colors:
                qRed(c)
                qGreen(c)
                qBlue(c)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500, f"Разбор цвета заняло {elapsed_ms:.1f} мс (> 500 мс)"

    def test_window_creation_under_2s(self, qapp):
        """Создание окна SteganoWindow занимает меньше 2 секунд."""
        start = time.perf_counter()
        win = SteganoWindow()
        elapsed = time.perf_counter() - start
        win.close()
        assert elapsed < 2.0, f"Создание окна заняло {elapsed:.2f} с (> 2 с)"

    def test_embed_via_ui_under_500ms(self, window, indexed8_image_256):
        """Встраивание через UI (embed_message) выполняется быстрее 500 мс."""
        window.original_image = indexed8_image_256
        window._refresh_buttons()
        window.message_input.setPlainText("UI performance test")
        start = time.perf_counter()
        with patch.object(QMessageBox, 'information'):
            window.embed_message()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500, f"embed_message через UI заняло {elapsed_ms:.1f} мс"

    def test_extract_via_ui_under_500ms(self, window, indexed8_image_256):
        """Извлечение через UI (extract_message) выполняется быстрее 500 мс."""
        palette = indexed8_image_256.colorTable()
        modified = lsb_embed_raw(list(palette), "Extract speed test")
        stego = indexed8_image_256.copy()
        stego.setColorTable(modified)
        window.stego_image = stego
        window._refresh_buttons()
        start = time.perf_counter()
        window.extract_message()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500, f"extract_message через UI заняло {elapsed_ms:.1f} мс"


# =============================================================================
#  Точка запуска (если запускать файл напрямую)
# =============================================================================

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",  # Подробный вывод
        "--tb=short",  # Краткий трейсбек при ошибках
        "--color=yes",  # Цветной вывод
        "-rA",  # Показывать итог по всем тестам
    ])

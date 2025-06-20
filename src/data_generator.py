"""
Модуль для генерации тестовых данных на основе схемы таблицы ClickHouse.
"""

import random
import string
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any


class DataGenerator:
    """
    Класс, отвечающий за генерацию данных, соответствующих схеме таблицы.

    Поддерживает различные типы данных ClickHouse, "подсказки" (`hints`) для
    управления диапазонами значений и сид для воспроизводимости результатов.
    """

    def __init__(self, schema: List[Dict], hints: Dict = None, seed: int = None):
        """
        Инициализирует генератор.

        Args:
            schema (List[Dict]): Схема таблицы, список словарей {'name': str, 'type': str}.
            hints (Dict, optional): "Подсказки" для генерации значений.
            seed (int, optional): Сид для генератора случайных чисел для воспроизводимости.
        """
        self.schema = schema
        self.hints = hints if hints is not None else {}
        self.rng = random.Random(seed)
        self._setup_type_generators()

    def _setup_type_generators(self):
        """
        Создает сопоставление (маппинг) базовых типов ClickHouse с функциями-генераторами.
        """
        self.type_generators = {
            'UInt8': lambda: self.rng.randint(0, 255),
            'UInt16': lambda: self.rng.randint(0, 65535),
            'UInt32': lambda: self.rng.randint(0, 4294967295),
            'UInt64': lambda: self.rng.randint(0, 18446744073709551615),
            'Int8': lambda: self.rng.randint(-128, 127),
            'Int16': lambda: self.rng.randint(-32768, 32767),
            'Int32': lambda: self.rng.randint(-2147483648, 2147483647),
            'Int64': lambda: self.rng.randint(-9223372036854775808, 9223372036854775807),
            'Float32': lambda: self.rng.uniform(-1e3, 1e3),
            'Float64': lambda: self.rng.uniform(-1e6, 1e6),
            'String': self._generate_string,
            'Date': self._generate_date,
            'DateTime': self._generate_datetime,
            'DateTime64': self._generate_datetime,
            'Bool': lambda: self.rng.choice([True, False]),
        }

    def _generate_string(self, length_min=5, length_max=15) -> str:
        """Генерирует случайную строку."""
        length = self.rng.randint(length_min, length_max)
        return ''.join(self.rng.choice(string.ascii_letters + string.digits) for _ in range(length))

    def _generate_date(self) -> date:
        """Генерирует случайную дату за последний год (по умолчанию)."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        return (start_date + timedelta(days=self.rng.randint(0, 365))).date()

    def _generate_datetime(self) -> datetime:
        """Генерирует случайную дату и время за последний год (по умолчанию)."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        delta_seconds = int((end_date - start_date).total_seconds())
        return start_date + timedelta(seconds=self.rng.randint(0, delta_seconds))

    def generate_row(self) -> Dict[str, Any]:
        """
        Генерирует одну строку данных в виде словаря.

        Проходится по каждой колонке в схеме, определяет, есть ли для нее
        "подсказка" (`hint`), и генерирует соответствующее значение.

        Returns:
            Dict[str, Any]: Словарь, представляющий одну сгенерированную строку.
        """
        row = {}
        for col in self.schema:
            col_name, col_type = col['name'], col['type']

            if col_name in self.hints:
                hint = self.hints[col_name]
                if isinstance(hint, list):
                    row[col_name] = self.rng.choice(hint)
                elif isinstance(hint, dict) and 'start' in hint and 'end' in hint:
                    start = datetime.fromisoformat(hint['start'])
                    end = datetime.fromisoformat(hint['end'])
                    delta = int((end - start).total_seconds())
                    gen_date = start + timedelta(seconds=self.rng.randint(0, delta))
                    row[col_name] = gen_date.date() if col_type == 'Date' else gen_date
                elif isinstance(hint, list) and len(hint) == 2:
                    if 'Float' in col_type:
                        row[col_name] = self.rng.uniform(hint[0], hint[1])
                    else:
                        row[col_name] = self.rng.randint(hint[0], hint[1])
                else:
                    logging.warning("Нераспознанный формат hint для '%s'. Генерируем по типу.", col_name)
                    row[col_name] = self._generate_by_type(col_type)
            else:
                row[col_name] = self._generate_by_type(col_type)
        return row

    def _generate_by_type(self, col_type: str) -> Any:
        """
        Выбирает и вызывает нужный генератор на основе базового типа колонки.

        Args:
            col_type (str): Полный тип колонки из схемы (например, `LowCardinality(String)`).

        Returns:
            Any: Сгенерированное значение.
        """
        base_type = col_type.split('(')[0]
        generator = self.type_generators.get(base_type)

        if generator:
            return generator()
        else:
            logging.warning("Неизвестный тип колонки '%s'. Возвращаем NULL.", col_type)
            return None

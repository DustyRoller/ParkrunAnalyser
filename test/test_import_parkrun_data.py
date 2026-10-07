from typing import Any
from unittest import TestCase

from import_parkrun_data import Event, _parse_data


class TestImport(TestCase):
    def test_parse_data_returns_expected_data(self):
        data: dict[str, Any] = {}
        
        event_data: list[Event] = _parse_data(data)

        self.assertFalse(event_data)


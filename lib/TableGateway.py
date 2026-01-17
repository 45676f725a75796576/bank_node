# Code from my previous project https://github.com/45676f725a75796576/eshop_system

import pyodbc
from json import dumps
from typing import List, Dict, Any

def row_to_dict(cursor, row) -> Dict[str, Any]:
    columns = [c[0] for c in cursor.description]
    return dict(zip(columns, row))

def rows_to_dicts(cursor, rows) -> List[Dict[str, Any]]:
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

class TableGateway:
    def __init__(self, cursor: pyodbc.Cursor):
        self.cursor = cursor

    def insert(self, *args, **kwargs):
        raise NotImplementedError

    def selectById(self, id: int) -> Dict[str, Any]:
        raise NotImplementedError

    def updateById(self, id: int, new_data: dict):
        raise NotImplementedError

    def deleteById(self, id: int):
        raise NotImplementedError

    def selectAll(self) -> List[Dict[str, Any]]:
        raise NotImplementedError
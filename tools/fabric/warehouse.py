"""Conexao Warehouse com token Entra; bindings privados em .local/."""
import json
import struct

import pyodbc

from client import ROOT, credential


def connect():
    config = json.loads((ROOT / ".local/fabric-environment.json").read_text())
    token = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
    connection = pyodbc.connect(
        "Driver={ODBC Driver 18 for SQL Server};Server=" + config["warehouse_server"]
        + ";Database=" + config["warehouse_database"] + ";Encrypt=yes;TrustServerCertificate=no;",
        attrs_before={1256: struct.pack("<I", len(token)) + token}, timeout=30, autocommit=True)
    connection.timeout = 120
    return connection


def results(cursor):
    sets = []
    while True:
        if cursor.description:
            columns = [column[0] for column in cursor.description]
            sets.append([dict(zip(columns, row)) for row in cursor.fetchall()])
        if not cursor.nextset():
            return sets

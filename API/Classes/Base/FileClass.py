"""UTF-8 JSON storage with atomic replacement and intact error information."""
import json
import os
import tempfile
from pathlib import Path

class File:
    @staticmethod
    def readFile(path):
        with open(path, encoding='utf-8-sig') as handle:
            return json.load(handle)

    readParamFile = readFile

    @staticmethod
    def writeFile(data, path):
        payload = json.dumps(data, ensure_ascii=True, indent=4, allow_nan=False)
        path = Path(path)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=path.parent, prefix='.save-',
                                             suffix='.tmp', delete=False) as handle:
                temp = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()

    writeFileUJson = writeFile

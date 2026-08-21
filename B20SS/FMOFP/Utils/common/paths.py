import ast
import os
import sqlite3
import hashlib
from typing import Optional
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class paths:
    def __init__(self):
        self.project_root = self._find_project_root()
        self.db_path = os.path.join(self.project_root, '.import_cache.db')
        self.conn = sqlite3.connect(self.db_path)
        self.c = self.conn.cursor()
        self.skipped_files_count = 0

        self._create_tables()
        self._populate_database()
        if self.skipped_files_count > 0:
            logger.debug(f"Skipped {self.skipped_files_count} unchanged files")

    def _find_project_root(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while current_dir != os.path.dirname(current_dir):  # Stop at the root directory
            if os.path.exists(os.path.join(current_dir, 'FMOFP')):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        raise Exception("Could not find project root")

    def _create_tables(self):
        try:
            # Create files table if it doesn't exist
            self.c.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY,
                    path TEXT UNIQUE,
                    hash TEXT
                )
            ''')

            # Create imports table if it doesn't exist
            self.c.execute('''
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    file_id INTEGER,
                    type TEXT,
                    FOREIGN KEY(file_id) REFERENCES files(id)
                )
            ''')

            # Check if the 'hash' column exists in the 'files' table
            self.c.execute("PRAGMA table_info(files)")
            columns = [column[1] for column in self.c.fetchall()]
            
            if 'hash' not in columns:
                # If 'hash' column doesn't exist, add it
                self.c.execute('ALTER TABLE files ADD COLUMN hash TEXT')

            self.conn.commit()
            logger.info("Database tables created successfully")
        except sqlite3.Error as e:
            logger.error(f"An error occurred while creating tables: {e}")
            raise

    def _populate_database(self):
        changed_files = 0
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file.endswith('.py') and '.venv' not in root:
                    path = os.path.join(root, file)
                    if self._parse_file_if_changed(path):
                        changed_files += 1
        
        if changed_files > 0:
            logger.info(f"Updated {changed_files} modified files")

    def _get_file_hash(self, file_path):
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def _parse_file_if_changed(self, file_path: str) -> bool:
        """Returns True if file was parsed, False if skipped"""
        new_hash = self._get_file_hash(file_path)
        self.c.execute('SELECT hash FROM files WHERE path = ?', (file_path,))
        result = self.c.fetchone()
        
        if result is None or result[0] != new_hash:
            logger.info(f"Parsing file: {file_path}")
            self._parse_file(file_path, new_hash)
            return True
        else:
            self.skipped_files_count += 1
            return False

    def _parse_file(self, file_path: str, file_hash: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content)
            
        except UnicodeDecodeError as e:
            logger.error(f"UnicodeDecodeError in file {file_path}: {e}")
            return
        except SyntaxError as e:
            logger.error(f"SyntaxError in file {file_path}: {e}")
            return
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return

        try:
            self.c.execute('INSERT OR REPLACE INTO files (path, hash) VALUES (?, ?)', (file_path, file_hash))
            file_id = self.c.lastrowid

            self.c.execute('DELETE FROM imports WHERE file_id = ?', (file_id,))

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    self.c.execute('INSERT INTO imports (name, file_id, type) VALUES (?, ?, ?)',
                                   (node.name, file_id, type(node).__name__))

            self.conn.commit()
        except Exception as e:
            logger.error(f"Error updating database for file {file_path}: {e}")
            self.conn.rollback()

    def get_import_statement(self, function_name: str, file_path: str) -> Optional[str]:
        self.c.execute('''
            SELECT files.path, imports.type
            FROM imports
            JOIN files ON imports.file_id = files.id
            WHERE imports.name = ? AND files.path != ?
        ''', (function_name, file_path))
        result = self.c.fetchone()
        if result:
            import_path, import_type = result
            rel_path = os.path.relpath(import_path, os.path.dirname(file_path))
            module_path = rel_path.replace('.py', '').replace(os.path.sep, '.')
            return f"from {module_path} import {function_name}"
        return None

    def update_file(self, file_path: str):
        self._parse_file_if_changed(file_path)

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

# Create an instance of the paths class
paths_instance = paths()

# For backwards compatibility, we'll keep this function
def get_import_statement(function_name: str, file_path: str) -> Optional[str]:
    return paths_instance.get_import_statement(function_name, file_path)

# Usage example 
"""
# To use this module, import it in your Python script:
# from FMOFP.Utils.common.paths import get_import_statement

# Then you can use it like this:
# import_statement = get_import_statement('my_function', './my_file.py')
# if import_statement:
#     logger.info(f"Import statement: {import_statement}")
"""

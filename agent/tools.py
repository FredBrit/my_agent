from tools.calculator import add, ADD_SCHEMA, multiply, MULTIPLY_SCHEMA
from tools.file_tools import (
    read_file, READ_FILE_SCHEMA,
    write_file, WRITE_FILE_SCHEMA,
    edit_file, EDIT_FILE_SCHEMA,
    list_directory, LIST_DIRECTORY_SCHEMA,
)
from tools.code_tools import run_python, RUN_PYTHON_SCHEMA
from tools.search_tools import (
    search_in_files, SEARCH_IN_FILES_SCHEMA,
    read_file_range, READ_FILE_RANGE_SCHEMA,
)
from tools.env_tools import install_package, INSTALL_PACKAGE_SCHEMA

REGISTRY = {
    "add": add,
    "multiply": multiply,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_directory": list_directory,
    "run_python": run_python,
    "search_in_files": search_in_files,
    "read_file_range": read_file_range,
    "install_package": install_package,
}

SCHEMAS = [
    ADD_SCHEMA,
    MULTIPLY_SCHEMA,
    READ_FILE_SCHEMA,
    WRITE_FILE_SCHEMA,
    EDIT_FILE_SCHEMA,
    LIST_DIRECTORY_SCHEMA,
    RUN_PYTHON_SCHEMA,
    SEARCH_IN_FILES_SCHEMA,
    READ_FILE_RANGE_SCHEMA,
    INSTALL_PACKAGE_SCHEMA,
]
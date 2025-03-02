import os
import re
import time
import json
import inspect
import pathlib
import tiktoken
import openai
from openai import OpenAI
from rich.text import Text
from rich.tree import Tree
from rich.markup import escape
from rich.filesize import decimal
from typing import Iterable, Optional, List, Dict, Union, Tuple, Callable

## Tools


def generate_tree_string(folder_path: str, prefix: str = "") -> str:

    """Generate an ASCII tree of a directory structure.

    This function recursively traverses a directory to create a visual hierarchy 
    similar to the Unix 'tree' command, using box-drawing characters.

    Args:
        folder_path (str): Directory path to visualize.
        prefix (str, optional): Internal prefix for recursion (not user-set). Defaults to "".

    Returns:
        str: ASCII tree with:
            ├── for non-final items
            └── for the last item
            │   for vertical hierarchy lines

    Example:
        >>> print(generate_tree_string("/path/to/dir"))
        ├── file1.txt
        ├── subdir
        │   ├── subfile1.txt
        │   └── subfile2.txt
        └── file2.txt
    """
        
    tree_string = ""
    try:
        # Check if directory exists first
        if not os.path.exists(folder_path):
            return f"{prefix}[Error: Directory '{folder_path}' does not exist]\n"
            
        # Get and sort directory contents, excluding hidden files
        entries = sorted(os.listdir(folder_path))
        entries = [e for e in entries if not e.startswith(".")]  # Ignore hidden files
        
        # Process each entry in the directory
        for i, entry in enumerate(entries):
            path = os.path.join(folder_path, entry)
            
            # Choose the appropriate connector based on whether this is the last entry
            # ├── for items with more siblings, └── for the last item
            connector = "├── " if i < len(entries) - 1 else "└── "
            tree_string += f"{prefix}{connector}{entry}\n"
            
            # Recursively process subdirectories
            if os.path.isdir(path):
                # Create new prefix for subdirectory contents:
                # │    for continuing levels (more siblings exist)
                # └    for the last item in this level
                new_prefix = prefix + ("│   " if i < len(entries) - 1 else "    ")
                tree_string += generate_tree_string(path, new_prefix)
    except PermissionError:
        # Handle cases where we can't access the directory contents
        tree_string += f"{prefix}└── [Permission Denied]\n"
    
    return tree_string


def get_directory_tree(
        directory: pathlib.Path,
        tree: Optional[Tree] = None,
        show_hidden: bool = False,
        inplace: bool = False,
        ignore_list_extras: Iterable[str] = (),
        ) -> Optional[Tree]:
    """Recursively build a Tree with directory contents.

    Args:
        directory (pathlib.Path): The directory to walk.
        tree (Tree, optional):
            The Tree object to build.
            If not provided, a new Tree is created.
        show_hidden (bool, optional):
            Whether to show hidden files.
        inplace (bool, optional):
            Whether to print the tree in place.
            If False, the tree is returned.
        ignore_list_extras (Iterable[str], optional):
            Additional file extensions to ignore.

    Returns:
        If inplace is False, the Tree object with the directory contents.
        Else, None.
    """

    default_ignore_list: Iterable[str] = ".ipynb_checkpoints", ".DS_Store", ".git", ".idea", ".coverage", ".pytest_cache"
    
    # Get the ignore list that includes the default and any extras
    ignore_list = sorted(set(default_ignore_list) | set(ignore_list_extras))

    # Create a new Tree if one is not provided
    tree = tree or Tree(label=f"[bold]{directory!s}[/bold] File Tree")  # type: ignore

    # Sort dirs first then by filename
    paths = sorted(
        pathlib.Path(directory).iterdir(),
        key=lambda path: (path.is_file(), path.name.lower()),
    )

    # Sort dirs first then by filename
    for path in paths:

        # Remove hidden files if show_hidden is False
        if path.name.startswith(".") and not show_hidden:
            continue

        # Skip files in the ignore list by suffix or name
        if path.is_file() and (path.suffix in ignore_list or path.name in ignore_list):
            continue

        # Skip directories only by name (not suffix)
        if path.is_dir() and path.name in ignore_list:
            continue

        # Add the directory to the tree
        if path.is_dir():

            # Style directories starting with "__" differently
            style = "dim" if path.name.startswith("__") else ""

            # Add the directory to the tree
            branch = tree.add(
                f"[bold magenta]:open_file_folder: [link file://{path}]{escape(path.name)}",
                style=style,
                guide_style=style,
            )
            get_directory_tree(path, branch)

        # Add the file to the tree
        else:
            main_style = "dim green" if path.name.startswith("_") else "green"
            ext_style = "dim red" if path.name.startswith("_") else "bold red"
            file_size_style = "dim blue" if path.name.startswith("_") else "blue"
            text_filename = Text(path.name, main_style)
            text_filename.highlight_regex(r"\..*$", ext_style)
            text_filename.stylize(f"link file://{path}")
            text_filename.append(f" ({decimal(path.stat().st_size)})", file_size_style)
            if path.suffix == ".py":
                icon = "🐍 "
            elif path.suffix == ".ipynb":
                icon = "🐍📓 "
            elif path.suffix == ".sh":
                icon = "🔧 "
            elif ".env" in path.name.lower():
                icon = "🔑 "
            elif path.suffix == ".csv":
                icon = "📊 "
            elif path.suffix in [".yaml", ".yml", ".json"]:
                icon = "📜 "
            elif path.suffix in [".txt", ".md"]:
                icon = "📝 "
            elif path.suffix in [".png", ".jpg", ".jpeg", ".gif", ".svg"]:
                icon = "🖼️ "
            elif path.suffix in [".zip", ".tar", ".gz", ".7z"]:
                icon = "📦 "
            elif path.suffix in [".pdf"]:
                icon = "📰 "
            elif path.suffix in [".mp4", ".avi", ".mov", ".mkv"]:
                icon = "🎥 "
            elif path.suffix in [".mp3", ".wav", ".flac"]:
                icon = "🎵 "
            elif path.suffix in [".html", ".css", ".js"]:
                icon = "🌐 "
            elif path.suffix in [".exe", ".msi"]:
                icon = "🛠️ "
            elif path.suffix in [".docx", ".pptx", ".xlsx"]:
                icon = "📄 "
            elif path.suffix in [".parquet", ".feather"]:
                icon = "🧼 "
            elif path.suffix in [".db", ".sqlite", ".sql", ".jsonl"]:
                icon = "🗄️ "
            else:
                icon = "📄 "

            # Prefix hidden files with a "🤫" emoji
            if path.name.startswith("."):
                icon = "🤫"+icon

            # Add the file to the tree (with icon prefix)
            tree.add(Text(icon) + text_filename)

    # If inplace is False, return the tree... otherwise the Tree object is updated in place
    if not inplace:
        return tree
    return None


def get_lines_from_file(file_path: str,
                        line_range: Optional[str],
                        as_list: bool = False) -> str:
    """Retrieve lines of code from a file within a given range.

    Args:
        file_path (str): Path to the file.
        line_range (str, optional): Line range in "start-end" format (1-based). 
            Example: "10-20" retrieves lines 10 to 20. Defaults to all lines.
        as_list (bool, optional): If True, returns lines as a list.

    Returns:
        str: Concatenated lines from the range or an error message if the file 
            is not found or the range is invalid.

    Example:
        code = get_lines_from_file("astropy/_dev/scm_version.py", line_range="1-20")

    Output:
        # Try to use setuptools_scm...
        import os.path as pth
        try:
            from setuptools_scm import get_version
            version = get_version(root="..", relative_to=__file__)
        except:
            raise ImportError("setuptools_scm broken or missing")
    """
    if not os.path.isfile(file_path):
        return f"[Error] File not found: {file_path}"

    with open(file_path, 'r', encoding='utf-8') as f:
        snippets = f.readlines()

    if line_range:
        try:
            if "-" not in line_range:
                line_range=f"{line_range.strip()}-{line_range.strip()}"
            start_line, end_line = [int(x.strip()) for x in line_range.split("-")]
            snippets = snippets[start_line-1 : end_line]
        except ValueError:
            return f"[Error] Invalid line range: {line_range}. Must be either a single integer or two integers delimited by a single dash."
    return ''.join(snippets) if not as_list else snippets


def _normalize_imports(lines: List[str]) -> List[str]:
    """Processes a list of lines to collect and normalize all import statements.

    This function extracts all `import` and `from ... import ...` statements from a given list of 
    Python source code lines, handling both single-line and multi-line imports. It removes duplicates, 
    splits multi-item imports, trims extra whitespace, and returns a sorted list of unique import statements.

    Args:
        lines (list[str]): 
            The lines of code from which to extract import statements.

    Returns:
        list[str]: 
            A sorted list of unique import statements, each formatted as a single line.
    """
    
    imports = set()  # Stores unique import statements
    current_import = []  # Temporary storage for multi-line imports
    inside_multiline = False  # Tracks whether we are inside a multi-line import

    # Regex to detect import statements (either `import X` or `from X import Y`)
    import_pattern = re.compile(r'^\s*(from\s+\S+\s+import\s+|import\s+)')

    for line in lines:
        stripped = line.strip()  # Remove leading/trailing whitespace

        if inside_multiline:
            # Handling multi-line imports: Collect lines until we reach the closing parenthesis `)`
            if stripped.endswith(')'):
                current_import.append(stripped[:-1])  # Remove the closing `)`
                # Flatten, normalize whitespace, and store as a single line
                imports.add(' '.join(' '.join(current_import).split()))
                current_import = []  # Reset buffer
                inside_multiline = False  # Exit multi-line mode
            else:
                current_import.append(stripped)  # Continue accumulating multi-line import
            continue

        match = import_pattern.match(line)  # Check if the line starts with `import` or `from ... import`
        if match:
            if stripped.endswith('('):  
                # Multi-line import detected: Start accumulating lines
                current_import.append(stripped[:-1])  # Store line without the opening `(`
                inside_multiline = True
            elif '(' in stripped and ')' in stripped:
                # Handle inline multi-item import: `from X import (a, b, c)`
                base_import, items = stripped.split('(', 1)  # Split before the first `(`
                items = items.rstrip(')').split(',')  # Extract and split imported items
                for item in items:
                    imports.add(f"{base_import.strip()} {item.strip()}")  # Store each as a separate import
            else:
                # Standard single-line import: `import X` or `from X import Y`
                imports.add(stripped)

    return sorted(imports)  # Return sorted list of unique imports


def _collect_imports_from_lines(lines: List[str]) -> List[str]:
    """Collects import statements from a list of lines.

    Args:
        lines (list[str]):
            The lines of code in which to search for import statements.

    Returns:
        list[str]:
            A list of import statements, each stripped of trailing newlines.
    """
    imports = []
    import_pattern = re.compile(r'^\s*(?:import|from)\s+')
    for line in lines:
        if import_pattern.match(line):
            imports.append(line.rstrip('\n'))
    return _normalize_imports(imports)


def search_code(
    root_directory: str,
    search_string: str,
    n_lines_before: int = 0,
    n_lines_after: int = 0,
    return_imports: bool = False
    ) -> Union[List[Dict[str, Union[str, int, List[str]]]], str]:
    """Searches for a given string in all .py files under root_directory.
    
    Optionally returning surrounding lines (context) and import statements from matching files.

    Args:
        root_directory (str): Path to the root directory of the codebase to search.
        search_string (str): The string to search for in .py files.
        n_lines_before (int, optional): Number of lines of context before match. Defaults to 0.
        n_lines_after (int, optional): Number of lines of context after match. Defaults to 0.
        return_imports (bool, optional): Whether to return import statements. Defaults to False.

    Returns:
        Union[List[Dict[str, Union[str, int, List[str]]]], str]: List of match dictionaries or an error message.
    """
    try:
        matches: List[Dict[str, Union[str, int, List[str]]]] = []
        pattern = re.compile(rf"\b{re.escape(search_string)}\b")  # Ensure exact word match

        for dirpath, _, filenames in os.walk(root_directory):
            for filename in filenames:
                if filename.endswith('.py'):
                    full_path = os.path.join(dirpath, filename)

                    # Safe file reading
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                    except (UnicodeDecodeError, FileNotFoundError) as e:
                        print(f"Skipping file {full_path} due to error: {e}")
                        continue

                    file_imports = _collect_imports_from_lines(lines) if return_imports else []

                    for i, line in enumerate(lines, start=1):
                        if pattern.search(line):  # Exact match instead of substring
                            start_idx = max(0, i - 1 - n_lines_before)
                            end_idx = min(len(lines), i - 1 + n_lines_after + 1)

                            context_before = [l.rstrip('\n') for l in lines[start_idx:i - 1]] if start_idx < i - 1 else []
                            context_after = [l.rstrip('\n') for l in lines[i:end_idx]] if i < end_idx else []

                            match_entry = {
                                'file': full_path,
                                'line': i,
                                'content': line.rstrip('\n'),
                                'context_before': context_before,
                                'context_after': context_after
                            }

                            if return_imports:
                                match_entry['imports'] = file_imports

                            matches.append(match_entry)

        return matches
    except Exception as e:
        return f"An error occurred: {e}"


def _get_indent_level(line: str) -> int:
    """Utility to count the number of leading spaces in a line.

    leading_spaces = (line-length minus (line-length minus non-prefixing-spaces))
    
    Args:
        line (str): The line of code

    Returns:
        The number of leading spaces 
    """
    return len(line) - len(line.lstrip(' '))


def _extract_entire_definition(lines: List[str], start_index: int) -> List[str]:
    """Extracts all lines in the definition block (function or class). 
    
    This is starting at start_index and continuing until we reach a line with 
    less-or-equal indentation that indicates the next top-level definition, or the end of file.

    Args:
        lines (list[str]):
            The lines containing the entirety of the class definition.
        start_index (int):
            Where we will start checking from looking for the relevant information.

    Returns:
        A list of strings representing the lines for a given definition block (function/class/method)
    """
    definition_block = []
    initial_indent = _get_indent_level(lines[start_index])
    definition_block.append(lines[start_index])
    # Gather everything that's part of this definition’s indentation
    for idx in range(start_index + 1, len(lines)):
        line = lines[idx]
        if line.strip() == '':
            # Blank lines inside the definition are included
            definition_block.append(line)
            continue
        if _get_indent_level(line) <= initial_indent and re.match(r'^\s*(def|class)\s+', line):
            # Found a new top-level definition
            break
        definition_block.append(line)
    return definition_block


def _find_method_block_in_lines(
    block_lines: List[str], 
    method_name: str
    ) -> Optional[Tuple[int, int]]:
    """Within a block of lines (e.g. a class block), find the start and end line indices (inclusive).
    
    This is used to allow for effective retrieval of method code from a file.
    For example, the definition for 'def method_name(...)' may exist within a class.

    Args:
        block_lines (List[str]):
            The line-by-line strings making up the class definition.
        method_name (str):
            The name of the method to be extracted.

    Returns:
        Optional[Tuple[int, int]]: The start and end line indices (if found, inclusive) for the method.
    """
    pattern = re.compile(rf'^\s*def\s+{re.escape(method_name)}\s*\(')
    for i, line in enumerate(block_lines):
        if pattern.search(line):
            # Found the start. Now find where it ends by indentation.
            start_idx = i
            init_indent = _get_indent_level(line)

            # Move forward to find where this method ends.
            for j in range(i + 1, len(block_lines)):
                if block_lines[j].strip() == '':
                    continue
                if _get_indent_level(block_lines[j]) <= init_indent and re.match(r'^\s*(def|class)\s+', block_lines[j]):
                    # Reached the next method/class -> end of this method’s block
                    return (start_idx, j - 1)
            return (start_idx, len(block_lines) - 1)  # Goes until end of block

    return None


def _extract_class_up_to_init_or_method(
    lines: List[str],
    class_index: int,
    method_name: str
    ) -> List[str]:
    """Grab the first part of a class definition up to the point at which initialization has completed.

    (1) Extract the entire class definition at class_index (using _extract_entire_definition).
    (2) Within that class block, find the __init__ block (if any) and the block for method_name (if any).
    (3) Return lines from the start of the class up through the furthest end of either __init__ or the method.

    Args:
        lines (list[str]):
            The lines of code containing the class definition.
        class_index (int):
            The starting point of the class (indexable) for the definition within the lines.
        method_name (str):
            The method we want to retrieve (in addition to the initialization code)
    
    Returns:
        list[str]:
            The relevant lines as a list of strings.
    """
    class_block = _extract_entire_definition(lines, class_index)
    # Look for __init__ and the target method
    init_block_bounds = _find_method_block_in_lines(class_block, '__init__')
    method_block_bounds = _find_method_block_in_lines(class_block, method_name)

    # If neither __init__ nor method is found, we just return the whole class
    if not init_block_bounds and not method_block_bounds:
        return class_block

    furthest_line = 0
    if init_block_bounds:
        furthest_line = max(furthest_line, init_block_bounds[1])
    if method_block_bounds:
        furthest_line = max(furthest_line, method_block_bounds[1])

    # Slice from start of the class block up to furthest_line
    return class_block[:furthest_line + 1]


def _parse_class_and_method(object_name: str) -> Tuple[Optional[str], str]:
    """Get the class and method names separately from an object if applicable.

    For example, for the Cat class with method _meow:
        - If object_name = "Cat._meow", returns ("Cat", "_meow").
        - Otherwise (object_name="Cat"), returns (None, object_name) if there's no dot.
        
    Args:
        object_name (str):
            The string containing the object name, one of:
                - Class Name: 'Cat'
                - Method Name: '_meow'
                - Function Name: make_cat_meow
                - Method With Class Prefix: Cat._meow

    Returns:
        Tuple[Optional[str], str]:
            - The class name (or None if no dot found) 
            - The method name
    """
    if '.' in object_name:
        parts = object_name.split('.', 1)  # Split on first dot
        if len(parts) == 2:
            return parts[0], parts[1]  # class_name, method_name
    return None, object_name  # No dot -> treat entire string as the object


def get_object_definition(
    root_directory: str,
    object_name: str,
    return_imports: bool = False
    ) -> Optional[Dict[str, Union[str, int, List[str]]]]:
    """Finds the first definition of a function, class, or method in the codebase.

    If object_name is a method using dot notation (e.g., "Cat._meow"), the function locates class 'Cat',
    extracts its definition block, and includes the method plus any __init__.

    Args:
        root_directory (str): Root directory of the codebase.
        object_name (str): Function/class name (e.g., "my_function", "MyClass", "Cat._meow").
        return_imports (bool, optional): Whether to collect import statements.

    Returns:
        Optional[Dict[str, Union[str, int, List[str]]]]]: Object definition details or None.
            - file (str): File path.
            - line (int): 1-based line number.
            - content (str): Matching def/class line.
            - definition_block (list[str]): Extracted definition lines.
            - imports (list[str], optional): Imports if return_imports=True.
    """
    try:
        class_name, method_name = _parse_class_and_method(object_name)

        # If we have a separate class_name, we'll do a 2-phase search:
        #   - Phase A: find the class definition for class_name
        #   - Phase B: from that block, locate method_name
        if class_name:
            # We only search for 'class class_name'
            class_pattern = re.compile(rf'^\s*class\s+{re.escape(class_name)}\b')

            for dirpath, _, filenames in os.walk(root_directory):
                for filename in filenames:
                    if filename.endswith('.py'):
                        full_path = os.path.join(dirpath, filename)
                        with open(full_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        file_imports = _collect_imports_from_lines(lines) if return_imports else []

                        for i, line in enumerate(lines, start=1):
                            if class_pattern.search(line.strip()):
                                # Found the class
                                class_definition_block = _extract_entire_definition(lines, i - 1)
                                # Now see if we can find the method inside
                                bounds = _find_method_block_in_lines(class_definition_block, method_name)

                                if bounds is None:
                                    continue

                                init_bounds = _find_method_block_in_lines(class_definition_block, '__init__')
                                furthest_line = max(bounds[1], init_bounds[1] if init_bounds else 0)
                                final_block = class_definition_block[: furthest_line + 1]

                                result = {
                                    'file': full_path,
                                    'line': i,
                                    'content': line.rstrip('\n'),
                                    'definition_block': [l.rstrip('\n') for l in final_block],
                                }
                                if return_imports:
                                    result['imports'] = file_imports
                                return result
            return None

        else:
            # class_name is None -> (handle "def object_name" or "class object_name")
            pattern = re.compile(rf'^\s*(?:def|class)\s+{re.escape(method_name)}\b')

            for dirpath, _, filenames in os.walk(root_directory):
                for filename in filenames:
                    if filename.endswith('.py'):
                        full_path = os.path.join(dirpath, filename)

                        with open(full_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()

                        file_imports = _collect_imports_from_lines(lines) if return_imports else []

                        for i, line in enumerate(lines, start=1):
                            if pattern.search(line.strip()):
                                stripped = line.strip()
                                if stripped.startswith(f'class {method_name}'):
                                    definition_block = _extract_entire_definition(lines, i - 1)
                                else:
                                    def_indent = _get_indent_level(line)
                                    class_line_idx = None
                                    for rev_idx in range(i - 2, -1, -1):
                                        if lines[rev_idx].lstrip().startswith('class '):
                                            class_indent = _get_indent_level(lines[rev_idx])
                                            if class_indent < def_indent:
                                                class_line_idx = rev_idx
                                                break

                                    if class_line_idx is None:
                                        definition_block = _extract_entire_definition(lines, i - 1)
                                    else:
                                        definition_block = _extract_class_up_to_init_or_method(
                                            lines, class_line_idx, method_name
                                        )

                                result = {
                                    'file': full_path,
                                    'line': i,
                                    'content': line.rstrip('\n'),
                                    'definition_block': [l.rstrip('\n') for l in definition_block],
                                }
                                if return_imports:
                                    result['imports'] = file_imports

                                return result

            return None
    except Exception as e:
        return f"An error occurred: {e}"


def generate_patches(answer: str) -> str:
    """
    Generate patches based on the provided answer if the model has already understood the problem.

    Args:
        answer (str): 
            The model's response containing the solution.

    Returns:
        str: 
            A status message indicating that the repository issue has been resolved 
            and execution should stop.
    """
    return "The repo issue solved!, We stop the execution here."


## Utils

def function_to_schema(func: Callable) -> dict:
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }

    try:
        signature = inspect.signature(func)
    except ValueError as e:
        raise ValueError(
            f"Failed to get signature for function {func.__name__}: {str(e)}"
        )

    parameters = {}
    for param in signature.parameters.values():
        try:
            param_type = type_map.get(param.annotation, "string")
        except KeyError as e:
            raise KeyError(
                f"Unknown type annotation {param.annotation} for parameter {param.name}: {str(e)}"
            )
        parameters[param.name] = {"type": param_type}

    required = [
        param.name
        for param in signature.parameters.values()
        if param.default == inspect._empty
    ]

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": (func.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required,
                "additionalProperties": False,  # Ensures no extra properties are allowed
            },
        },
    }


def print_pretty(json_data):
    """
    Prints a JSON object in a formatted, easy-to-read manner.
    
    Args:
        json_data (dict): The JSON data to print.
    """
    print(json.dumps(json_data, indent=4, sort_keys=True))


def count_tiktoken_length(messages: Union[str, List[Dict[str, str]]], model_name: str = "gpt-3.5-turbo") -> int:
    """
    Counts the total number of tokens in a list of messages or a single string using tiktoken.

    Args:
        messages (Union[str, List[Dict[str, str]]]): Either a single string or a list of messages,
                                                     where each message is a dictionary with keys like "role" and "content".
        model_name (str): The model name for tokenization. Default is "gpt-3.5-turbo".

    Returns:
        int: Total number of tokens.
    """
    try:
        encoding = tiktoken.encoding_for_model(model_name)
        total_tokens = 0

        # Handle the case where messages is a string
        if isinstance(messages, str):
            return len(encoding.encode(messages))

        # Validate messages is a list of dicts
        if not isinstance(messages, list) or not all(isinstance(msg, dict) for msg in messages):
            raise ValueError("messages must be a list of dictionaries or a single string.")

        # Count tokens for each message
        for message in messages:
            for key, value in message.items():
                if isinstance(value, str):  # Ensure value is a string before encoding
                    total_tokens += len(encoding.encode(value))

        return total_tokens
    except Exception as e:
        raise RuntimeError(f"Error in calculating token length: {e}")


def set_openai_key(path_to_key: str = "/home/loc/Documents/keys/OPENAI_API_KEY.txt") -> None:
    """
    Sets the OpenAI API key from a file to an environment variable.

    Args:
        path_to_key (str): Path to the file containing the OpenAI API key.
                           Default is '/home/loc/Documents/keys/OPENAI_API_KEY.txt'.
    """
    # Check if the path exists
    if os.path.exists(path_to_key):
        with open(path_to_key, "r") as f:
            api_key = f.read().strip()  # Read and strip any extra whitespace/newlines
        os.environ["OPENAI_API_KEY"] = api_key  # Set the environment variable
        print(f"API key set successfully.")
    else:
        raise FileNotFoundError(f"{path_to_key} does not exist!")  # Use a proper exception


def test_openai_api(model: str = "gpt-4") -> None:
    """
    Tests the OpenAI API by generating a chat completion with a simple prompt.

    Args:
        model (str): The name of the model to use. Default is 'gpt-4'.
    """
    try:
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),  # This is the default and can be omitted
        )

        
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "Hello assistant!",
                }
            ],
            model="gpt-4o",
        )

        # Access the assistant's response content
        response_content = response.choices[0].message.content
        print(response_content)
        
    except Exception as e:
        print(f"An error occurred: {e}")


def create_openai_client() -> Optional[OpenAI]:
    """
    Creates an instance of the OpenAI client using the API key from the environment variable.

    Returns:
        OpenAI | None: The OpenAI client instance if successful, otherwise None.
    """
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in the environment variables.")
        
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        print(f"Failed to create OpenAI client: {e}")
        return None


def safe_completion(client, model_name, messages, tool_schemas, retries=3):
    for _ in range(retries):
        try:
            return client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tool_schemas
            )
        except openai.RateLimitError:
            print("Rate limit exceeded. Waiting before retrying...")
            time.sleep(60)  # Wait 60 seconds
    raise Exception("Exceeded retry attempts due to rate limit.")
import os
import ast
import sys
import json
import unittest
from typing import Dict, Tuple, List, Set, Optional
from collections import defaultdict, Counter

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# Dictionary to store the directory and file details together
project_structure = {}

class CodeMetrics:
    def __init__(self):
        self.total_lines = 0
        self.total_chars = 0
        self.function_count = 0
        self.class_count = 0
        self.import_count = 0
        self.cyclomatic_complexity = 0
        self.max_nest_depth = 0
        self.cognitive_complexity = 0
        self.lambda_count = 0
        self.fstring_count = 0
        self.comprehension_count = 0
        self.recursive_functions = set()
        self.avg_function_length = 0
        self.function_lengths = []
        self.imports = []  # Track imported modules
        self.functions = []  # Store function names with complexity
        self.dependencies = set()  # Track module dependencies
        
    def add_function(self, name, complexity, line_count):
        self.functions.append({
            'name': name,
            'complexity': complexity,
            'line_count': line_count
        })

class FunctionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.metrics = CodeMetrics()
        self.current_function = None
        self.current_function_lines = 0
        self.nest_depth = 0
        self.current_function_complexity = 0
        
    def visit_ClassDef(self, node):
        self.metrics.class_count += 1
        self.generic_visit(node)
        
    def visit_Import(self, node):
        self.metrics.import_count += len(node.names)
        for name in node.names:
            self.metrics.imports.append(name.name)
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        if node.module:  # Sometimes module can be None for relative imports
            self.metrics.import_count += len(node.names)
            module_name = node.module
            self.metrics.dependencies.add(module_name)
            for name in node.names:
                self.metrics.imports.append(f"{module_name}.{name.name}")
        self.generic_visit(node)
        
    def visit_FunctionDef(self, node):
        self.metrics.function_count += 1
        old_function = self.current_function
        old_complexity = self.current_function_complexity
        self.current_function = node.name
        self.current_function_complexity = 0
        
        # Check for recursion
        for n in ast.walk(node):
            if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == node.name:
                self.metrics.recursive_functions.add(node.name)
        
        # Calculate cyclomatic complexity for this function
        function_complexity = 1  # Base complexity is 1
        function_complexity += sum(1 for child in ast.walk(node)
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, 
                               ast.With, ast.Assert, ast.BoolOp)))
        
        self.current_function_complexity = function_complexity
        self.metrics.cyclomatic_complexity += function_complexity
        
        end_lineno = getattr(node, 'end_lineno', node.lineno)
        function_length = end_lineno - node.lineno
        self.metrics.function_lengths.append(function_length)
        
        # Store function details
        self.metrics.add_function(
            node.name, 
            function_complexity,
            function_length
        )
        
        self.generic_visit(node)
        self.current_function = old_function
        self.current_function_complexity = old_complexity

    def visit_Lambda(self, node):
        self.metrics.lambda_count += 1
        self.generic_visit(node)

    def visit_JoinedStr(self, node):
        self.metrics.fstring_count += 1
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.metrics.comprehension_count += 1
        self.generic_visit(node)

    def visit_DictComp(self, node):
        self.metrics.comprehension_count += 1
        self.generic_visit(node)

    def visit_SetComp(self, node):
        self.metrics.comprehension_count += 1
        self.generic_visit(node)

def get_inclusion_choice(use_defaults=False):
    # Always return all True and text format for simplicity
    # Parameters are kept for backward compatibility
    return True, True, True, True, True, "text"

def analyze_file(file_path: str) -> CodeMetrics:
    if not file_path.endswith('.py'):
        return CodeMetrics()
        
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        tree = ast.parse(content)
        visitor = FunctionVisitor()
        visitor.visit(tree)
        metrics = visitor.metrics
        
        # Calculate average function length
        if metrics.function_lengths:
            metrics.avg_function_length = sum(metrics.function_lengths) / len(metrics.function_lengths)
        
        # Count non-blank, non-comment lines
        lines = content.splitlines()
        in_multiline = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_multiline:
                    in_multiline = False
                else:
                    if stripped.endswith('"""') or stripped.endswith("'''"):
                        continue
                    in_multiline = True
                continue
            if in_multiline or stripped.startswith('#'):
                continue
            metrics.total_lines += 1
            metrics.total_chars += len(stripped)
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error analyzing file {file_path}: {str(e)}")
        return CodeMetrics()

def analyze_directory(path: str) -> Dict[str, CodeMetrics]:
    metrics_by_file = {}
    
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith('.py'):  # Already filtering for .py files
                file_path = os.path.join(root, file)
                metrics_by_file[file_path] = analyze_file(file_path)
                
    return metrics_by_file

def get_dependencies(metrics_by_file):
    """Extract module dependencies from metrics"""
    dependencies = {}
    for file_path, metrics in metrics_by_file.items():
        module_name = file_path.replace('\\', '.').replace('/', '.')
        if module_name.endswith('.py'):
            module_name = module_name[:-3]
        dependencies[module_name] = list(metrics.dependencies)
    return dependencies

def get_top_complex_functions(metrics_by_file, top_n=10):
    """Find the most complex functions"""
    all_functions = []
    for file_path, metrics in metrics_by_file.items():
        for func in metrics.functions:
            all_functions.append({
                'file': file_path,
                'name': func['name'],
                'complexity': func['complexity'],
                'line_count': func['line_count']
            })
    
    return sorted(all_functions, key=lambda x: x['complexity'], reverse=True)[:top_n]

def get_top_imports(metrics_by_file, top_n=10):
    """Find the most imported modules"""
    all_imports = []
    for _, metrics in metrics_by_file.items():
        all_imports.extend(metrics.imports)
    
    return Counter(all_imports).most_common(top_n)

def write_metrics_to_file(metrics_by_file, output_format="text"):
    """Write metrics to file with specified format"""
    total_metrics = CodeMetrics()
    
    # Calculate project totals
    for _, metrics in metrics_by_file.items():
        for attr in vars(total_metrics):
            if not attr.startswith('_') and isinstance(getattr(metrics, attr), (int, float)):
                setattr(total_metrics, attr, getattr(total_metrics, attr) + getattr(metrics, attr))
    
    # Get interesting data
    top_complex_functions = get_top_complex_functions(metrics_by_file, top_n=5)  # Reduced from 10 to 5 for brevity
    top_imports = get_top_imports(metrics_by_file, top_n=5)  # Reduced from 10 to 5 for brevity
    
    # Text output (default)
    with open('code_analysis.txt', 'w', encoding='utf-8') as f:
        f.write("\nCODE ANALYSIS RESULTS\n")
        f.write("=" * 80 + "\n\n")
        
        # Project Summary
        f.write("PROJECT SUMMARY\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total Lines of Code: {total_metrics.total_lines}\n")
        f.write(f"Total Functions: {total_metrics.function_count}\n")
        f.write(f"Total Classes: {total_metrics.class_count}\n")
        f.write(f"Total Cyclomatic Complexity: {total_metrics.cyclomatic_complexity}\n")
        f.write(f"Total Lambda Functions: {total_metrics.lambda_count}\n")
        f.write(f"Total F-strings: {total_metrics.fstring_count}\n")
        f.write(f"Total Comprehensions: {total_metrics.comprehension_count}\n\n")
        
        # Top Complex Functions
        f.write("TOP COMPLEX FUNCTIONS\n")
        f.write("-" * 80 + "\n")
        for func in top_complex_functions:
            f.write(f"Function: {func['name']} (in {func['file']})\n")
            f.write(f"  Complexity: {func['complexity']}\n")
            f.write(f"  Line Count: {func['line_count']}\n\n")
        
        # Most Imported Modules
        f.write("MOST IMPORTED MODULES\n")
        f.write("-" * 80 + "\n")
        for module, count in top_imports:
            f.write(f"{module}: {count} imports\n")
            
    logger.info(f"Code analysis written to code_analysis.txt")

def write_structure_to_file(output_format="text"):
    """Write project structure with improved format"""
    output_file = 'project_structure.txt'
    
    # Text output (default)
    with open(output_file, 'w', encoding='utf-8') as f:
        content_written = False
        for path, files in project_structure.items():
            f.write(f'Directory: {path}\n')
            content_written = True
            
            for file, details in files:
                f.write(f'  ├─ {file}\n')
                content_written = True
                
                for i, (class_or_function, methods) in enumerate(details):
                    is_last_item = i == len(details) - 1
                    prefix = "  │  └─ " if is_last_item else "  │  ├─ "
                    # Just show the class or function name without import statement
                    f.write(f'{prefix}{class_or_function}\n')
                    content_written = True
                    
                    if methods:
                        for j, method in enumerate(methods):
                            is_last_method = j == len(methods) - 1
                            method_prefix = "  │     └─ " if is_last_method else "  │     ├─ "
                            f.write(f'{method_prefix}{method}\n')
                            content_written = True
            f.write('\n')
        
        if not content_written:
            f.write("No content was generated based on the selected options.\n")
    
    logger.info(f"Project structure written to {output_file}")

if __name__ == "__main__":
    # Default path is FMOFP
    default_path = 'FMOFP'
    
    # Get command line arguments
    args = sys.argv[1:]
    
    # Process command line options
    analysis_path = default_path
    
    # Simple command line handling - just look for a path
    if args:
        analysis_path = args[0]
    
    logger.info(f"Starting analysis of {analysis_path}")

    # Always include everything and use text format
    include_folders = True
    include_files = True
    include_functions = True
    include_import_paths = True
    include_neat_stuff = True
    output_format = "text"

    # Process directory structure
    for root, dirs, files in os.walk(analysis_path):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        project_structure[root] = []
        
        for file in files:
            file_path = os.path.normpath(os.path.join(root, file))
            # Only process Python files, ignoring __init__.py
            if file.endswith('.py') and file != '__init__.py':
                file_details = []
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        tree = ast.parse(content)
                        for node in tree.body:
                            if isinstance(node, ast.ClassDef):
                                class_name = node.name
                                class_functions = [class_node.name for class_node in node.body 
                                                if isinstance(class_node, ast.FunctionDef) and class_node.name != '__init__']
                                # Just add the class name without import statement
                                file_details.append((class_name, class_functions))
                            elif isinstance(node, ast.FunctionDef) and node.name != '__init__':
                                function_name = node.name
                                # Just add the function name without import statement
                                file_details.append((function_name, []))
                    project_structure[root].append((file, file_details))
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {str(e)}")
                    continue

    # Write project structure
    write_structure_to_file()

    # Always process neat stuff
    logger.debug("Starting code analysis")
    metrics = analyze_directory(analysis_path)
    write_metrics_to_file(metrics)
    logger.debug("Code analysis completed")

    logger.info("Script execution completed")
#!/usr/bin/env python3
import sys
import jedi

def get_function_or_class_code(filename, function_name):
    try:
        script = jedi.Script(path=filename)
        for function in script.get_names(all_scopes=True, definitions=True):
            if function.name == function_name and (function.type == 'function' or function.type == 'class'):
                code_text = function.get_line_code(after=function.get_definition_end_position()[0] - function.get_definition_start_position()[0])
                return code_text 
        return "Function not found!"
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python print_function.py <filename> <function_name>")
    else:
        filename = sys.argv[1]
        function_name = sys.argv[2]
        code = get_function_or_class_code(filename, function_name)
        print(code)

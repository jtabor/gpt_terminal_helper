#! /usr/bin/python3
import json
import subprocess
import sys
import re
from typing import List, Dict, Any, Optional, Union, Callable

approved_command_list = ['ls', 'cat', 'head', 'tail' ,'grep', 'echo']
command_list_required = [";","$"]

file_prompt_required = ['/','..','~']

class FunctionArgument:
    def __init__(self, name: str, description: str, arg_type: str, is_required: bool = False):
        self.name = name
        self.description = description
        self.type = arg_type
        self.is_required = is_required

class ChatFunction:
    def __init__(self, name: str, description: str, arguments: List[FunctionArgument] = None, function: Callable = None):
        self.name = name
        self.description = description
        self.arguments = arguments or []
        
        if function is None:
            self.run = self.empty_function
        else:
            self.run = function
            
    def empty_function(self, from_gpt):
        raise Exception(f"Error - run not set for this function: {from_gpt}")
    
    def get_function_description(self, provider: str = "openai") -> Dict[str, Any]:
        """Generate function description based on the specified provider format.
        
        Args:
            provider: The provider to generate the description for ('openai' or 'claude')
            
        Returns:
            Dictionary containing the function description in the specified format
        """
        if provider.lower() == "openai":
            return self._generate_openai_description()
        elif provider.lower() == "claude":
            return self._generate_claude_description()
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _generate_openai_description(self) -> Dict[str, Any]:
        """Generate OpenAI-compatible function description."""
        properties = {}
        required = []
        
        for arg in self.arguments:
            properties[arg.name] = {
                "type": arg.type,
                "description": arg.description
            }
            
            if arg.is_required:
                required.append(arg.name)
                
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def _generate_claude_description(self) -> Dict[str, Any]:
        """Generate Claude-compatible function description."""
        properties = {}
        required = []
        
        for arg in self.arguments:
            properties[arg.name] = {
                "type": arg.type,
                "description": arg.description
            }
            
            if arg.is_required:
                required.append(arg.name)
                
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

def safe_input(prompt):
    with open('/dev/tty', 'r') as tty:
            print(prompt, end='', flush=True)  # Print the prompt manually
            return tty.readline().strip()  # Read from /dev/tty

def prompt_user(prompt=""):
    if prompt:
        prompt += " (y/n)[y]: "
    else:
        prompt = "y/n[y]: "
    
    while True:
        user_input = safe_input(prompt).lower()
        if user_input == 'y':
            return True
        elif user_input == 'n':
            return False
        elif user_input == '':
            return True
        else:
            print("Please enter 'y' for yes or 'n' for no.")

def run_in_terminal(from_gpt):

    result = ""
    print("assistant running > : " + str(from_gpt)) 
    if (from_gpt):
        args = json.loads(from_gpt)
        command = args['command']
        prompt_required = True

        for value in approved_command_list:
            # pattern = r'\b' + re.escape(value) + r'\b'
            pattern = r'(?<!\S)' + re.escape(value) + r'(?!\S)'
            if re.search(pattern, command):
                # print("Matched value: " + value)
                prompt_required = False

        for value in command_list_required:
            if (value in command):
                # print("Matched value: " + value)
                prompt_required = True
        if ('return_result' in args):
            return_result = args['return_result']
        else:
            return_result = False
#TODO - handle this more reasonably.. it can lead to loops
        return_result = True
        if (prompt_required):
            run_command = prompt_user("Run: %s return? %s" % (command,str(return_result)))
        else:
            run_command = True
        if run_command:
            if return_result:
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                result = "RUNNING: " + command + "\nSTDOUT:\n" + str(result.stdout) + "\nSTDERR:\n" + str(result.stderr)
                # print(str(return_result),file=sys.stderr)
            else:
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            if (return_result):
                return [False,result]
                # result = "The User denied running the command: " + command
        return [return_result,result]
    return [False,result]

# OpenAI style tool definition
# Define arguments for run_in_terminal function
run_in_terminal_args = [
    FunctionArgument(
        name="command",
        description="The full command to run in the shell. The command will be run in python's subprocess.run command.",
        arg_type="string",
        is_required=True
    ),
    FunctionArgument(
        name="return_result",
        description="If True, this will give you the result of the command. If False, the command will be run and the result will be sent directly to the user.",
        arg_type="boolean",
        is_required=False
    )
]

# Create the run_in_terminal ChatFunction instance
run_in_terminal_function = ChatFunction(
    name="run_in_terminal",
    description="Run the input string in a Linux shell",
    arguments=run_in_terminal_args,
    function=run_in_terminal
)

def write_file(from_gpt):
    return_result = True
    result = ""
    if (from_gpt):
        args = json.loads(from_gpt)
        filename = args['filename']
        file_contents = args['file_text']
        prompt_required = False
        for value in file_prompt_required:
            if value in filename:
                prompt_required = True
        if prompt_required:
            permission = prompt_user("Okay to write file: %s with contents:\n %s" %(filename,file_contents))
        else:
            permission = True
        if (permission):
            with open(filename,'w') as f:
                f.write(file_contents)
            result = "FILE " + filename + " written"
        else:
            result = "FILE WRITE DENIED BY USER: " + str(filename)
    return [return_result,result]

# Define arguments for write_file function
write_file_args = [
    FunctionArgument(
        name="filename",
        description="filename of the file to save",
        arg_type="string",
        is_required=True
    ),
    FunctionArgument(
        name="file_text",
        description="The contents of the new file",
        arg_type="string",
        is_required=True
    )
]

# Create the write_file ChatFunction instance
write_file_function = ChatFunction(
    name="write_file",
    description="This saves the input text to a file named filename in the current directory",
    arguments=write_file_args,
    function=write_file
)


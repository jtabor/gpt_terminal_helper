#! /usr/bin/python3
import json
import subprocess
import sys
import re

approved_command_list = ['ls', 'cat', 'head', 'tail' ,'grep', 'echo']
command_list_required = [";","$"]

file_prompt_required = ['/','..','~']
class ChatFunction:
    def __init__(self,description,function=None):

        self.description = description
        self.name = description['function']['name'] 
        
        if (function is None):
            self.run = self.empty_function
        else:
            self.run = function 
        
    def empty_function(self, from_gpt):
        raise "Error - run not set for this function: " + str(from_gpt)

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
    print("> : " + str(from_gpt)) 
    if (from_gpt):
        args = json.loads(from_gpt)
        command = args['command']
        prompt_required = True

        for value in approved_command_list:
            # pattern = r'\b' + re.escape(value) + r'\b'
            pattern = r'(?<!\S)' + re.escape(value) + r'(?!\S)'
            if re.search(pattern, command):
                print("Matched value: " + value)
                prompt_required = False

        for value in command_list_required:
            if (value in command):
                print("Matched value: " + value)
                prompt_required = True
        if ('return_result' in args):
            return_result = args['return_result']
        else:
            return_result = False
        return_result = True
        if (prompt_required):
            run_command = prompt_user("Run: %s return? %s" % (command,str(return_result)))
        else:
            run_command = True
        if run_command:
            if return_result:
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                result = "RUNNING: " + command + "\nSTDOUT:\n" + str(result.stdout) + "\nSTDERR:\n" + str(result.stderr)
                print(str(return_result),file=sys.stderr)
            else:
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            if (return_result):
                return [False,result]
                # result = "The User denied running the command: " + command
        return [return_result,result]
    return [False,result]

run_in_terminal_desc = {
        "type": "function",
        "function": {
            "name": "run_in_terminal",
            "description": "Run the input string in a Linux shell",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The full command to run in the shell.  The command will be run in python's subprocess.run command.",
                    },
                    "return_result": {
                        "type": "boolean",
                        "description": "If True, this will give you the result of the command.  If False, the command will be run and the result will be sent directly to the user."}
                },
                "required": ["command"],
            },
        },
    }

run_in_terminal_function = ChatFunction(run_in_terminal_desc, run_in_terminal)

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


write_file_desc = {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "This saves the input text to a file named filename in the current directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "filename of the file to save",
                    },
                    "file_text": {
                        "type": "string",
                        "description": "The contents of the new file"}
                },
                "required": ["filename","file_text"]
            },
        },
    }
write_file_function = ChatFunction(write_file_desc, write_file)


#! /usr/bin/python3
from openai import OpenAI
import os
import io
import base64
import chat_functions as cf
import sys
import re
import csv
import select
import subprocess
from datetime import datetime

GPT_MODEL = 'gpt-4-turbo-2024-04-09'
# GPT_MODEL = 'gpt-4o-2024-05-13'
SYSTEM_PROMPT = "You are a helpful command line assistant.  You take requests from the user and generate Linux shell commands for them.  You ask for extra info if you need it.  Use the provided function calls to accomplish the user's request.  You can call shell commands with return_result = True to get more information to accomplish your goal.  Unless otherwise specified, assume you are using the current directory for all requests.  Try to take some initiative while answering the user's question.  They will approve all shell commands."

GLOBAL_CONFIG = os.path.expanduser("~/.gpt/global_context.md")

global_config = None

messages = [{"role": "system", "content": [{"type":"text", "text":SYSTEM_PROMPT}]}]

if os.path.exists(GLOBAL_CONFIG):
    with open(GLOBAL_CONFIG, "r") as file:
        global_config = file.read()
        messages.append({"role": "system", "content": "USER SPECIFIC INFO: \n" + global_config})


LOCAL_CONFIG = os.getcwd() + "/.gpt/local_context.md"
if os.path.exists(LOCAL_CONFIG):
    with open(LOCAL_CONFIG, "r") as file:
        local_config = file.read()
        messages.append({"role": "system", "content": "DIRECTORY SPECIFIC INFO: \n" + local_config})

tools = [cf.run_in_terminal_function, cf.write_file_function]
tools_descriptions = [tool.description for tool in tools]

if (len(sys.argv) != 2):
    print("usage: gpt_command.py <prompt>",file=sys.stderr)
    exit()

prompt = sys.argv[1]

#return base64 encoded image from cv2 image input
def encode_image(image):
    success, jpg_bytes = cv2.imencode('.jpg',image)
    image_file = io.BytesIO(jpg_bytes)
    return base64.b64encode(image_file.read()).decode("utf-8") 

#Return True when done
def call_and_process(message_list):
    
    should_continue = False

    client = OpenAI()
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=message_list,
        tools=tools_descriptions,
        max_tokens=1000)
    
    tools_called = response.choices[0].message.tool_calls

    return_message = response.choices[0].message.content
    if return_message:
        print("GPT: " + str(return_message), file=sys.stderr)
        message_list.append({"role": "assistant", "content": return_message})
        if (tools_called is not None):
            print("INFO: Tools pending: " + str(len(response.choices[0].message.tool_calls)),file=sys.stderr)
        user_input = cf.safe_input("Answer: ").lower()
        if user_input != '':
            message_list.append({"role": "user", "content": user_input})
            should_continue = True

    if (tools_called is not None and len(tools_called) > 0):
        for call in tools_called:
            function = call.function
            for tool in tools:
                if (function.name == tool.name):
                    [should_continue, return_message] = tool.run(function.arguments)
                    message_list.append({"role": "system", "content": return_message})
                    print(return_message,file=sys.stderr)

    return [should_continue, message_list]

stdin = ""
ready = True
while ready:
    # Use select to check if there's any input from stdin
    ready, _, _ = select.select([sys.stdin], [], [], 0.1)
    if ready:
        chunk = sys.stdin.read(1)
        if chunk == '':  # EOF reached
            break
        stdin += chunk

if (len(stdin) > 0):
    stdin = "CONTENTS OF STDIN:\n" + stdin
    print(stdin)
    messages.append({ "role": "system", "content": [ { "type": "text", "text": stdin, } ], })

lsb_release_result = subprocess.run("lsb_release -a", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
lsb_release_result = lsb_release_result.stdout
lsb_release_result = "PLATFORM: " + lsb_release_result

date = "CURRENT TIME: " + datetime.now().strftime("%B %d, %Y %H:%M:%S")

current_directory = "CURRENT DIRECTORY: " + os.getcwd()

messages.append({ "role": "system", "content": [ { "type": "text", "text": lsb_release_result, } ], })
messages.append({ "role": "system", "content": [ { "type": "text", "text": current_directory + "\n" + date, } ], })

messages.append({ "role": "user", "content": [ { "type": "text", "text": prompt, } ], })
print("DEBUG: " + str(messages))

[result, messages] = call_and_process(messages)

while result:
    [result, messages] = call_and_process(messages)    

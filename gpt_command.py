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
import argparse
import json
import gpt_db

GPT_MODEL = 'gpt-4-turbo-2024-04-09'
# GPT_MODEL = 'gpt-4o-2024-05-13'
SYSTEM_PROMPT = "You are a helpful command line assistant.  You take requests from the user and generate Linux shell commands for them.  You ask for extra info if you need it.  Use the provided function calls to accomplish the user's request.  You can call shell commands with return_result = True to get more information to accomplish your goal.  Unless otherwise specified, assume you are using the current directory for all requests.  Try to take some initiative while answering the user's question.  They will approve all shell commands."

GPT_DIRECTORY = os.path.expanduser("~/.gpt")
GLOBAL_CONFIG = GPT_DIRECTORY + " /global_context.md"
MAX_FILES_LIST = 20

global_config = None

if not os.path.exists(GPT_DIRECTORY):
    os.makedirs(GPT_DIRECTORY)

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
def add_message_to_chat(message, chat_id):
    for content in message['content']:
        gpt_db.add_message(chat_id, message['role'], content['type'],content[content['type']])

def generate_environment_messages():
    lsb_release_result = subprocess.run("lsb_release -a", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lsb_release_result = lsb_release_result.stdout
    lsb_release_result = "PLATFORM: " + lsb_release_result

    date = "CURRENT TIME: " + datetime.now().strftime("%B %d, %Y %H:%M:%S")

    current_directory = "CURRENT DIRECTORY: " + os.getcwd()
    to_return = []
    to_return.append({ "role": "system", "content": [ { "type": "text", "text": lsb_release_result, } ], })
    to_return.append({ "role": "system", "content": [ { "type": "text", "text": current_directory + "\n" + date, } ], })
    return to_return

def load_default_chat(prompt,stdin):
    messages = [{"role": "system", "content": [{"type":"text", "text":SYSTEM_PROMPT}]}]
    messages.append({ "role": "system", "content": [ { "type": "text", "text": stdin, } ], })
    messages.append({ "role": "user", "content": [ { "type": "text", "text": prompt, } ], })
    chat_id = gpt_db.add_chat(prompt)
    environment_messages = generate_environment_messages()
    for message in messages:
        add_message_to_chat(message,chat_id)
    #NOTE: Don't save the environment.. we want that fresh each time (I think)
    for environment_message in environment_messages:
        messages.append(environment_messages)

    return [messages,chat_id]

def load_chat_from_db(chat_id):
    db_messages = get_all_messages(chat_id)
    to_return = []
    for db_message in db_messages:
        to_return.append({"role":db_message.role,"content": [ { "type": "text", "text": db_message.content}]})

    to_return.append({"role":"system","content": [{"type":"text", "text": "NOTE The conversation has been reloaded in the following environment"}]})
    environment_messages = generate_environment_messages()
    for environment_message in environment_messages:
        to_return.append(environment_messages)
    return to_return


#return base64 encoded image from cv2 image input
def encode_image(image):
    success, jpg_bytes = cv2.imencode('.jpg',image)
    image_file = io.BytesIO(jpg_bytes)
    return base64.b64encode(image_file.read()).decode("utf-8") 

#Return True when done
def call_and_process(message_list, chat_id):
    
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
        add_message_to_chat(return_message,chat_id)
        print("GPT: " + str(return_message), file=sys.stderr)
        message_list.append({"role": "assistant", "content": return_message})
        if (tools_called is not None):
            print("INFO: Tools pending: " + str(len(response.choices[0].message.tool_calls)),file=sys.stderr)
        user_input = cf.safe_input("Answer: ").lower()
        if user_input != '':
            new_message = {"role": "user", "content":[{"type":"text", "text": user_input}]}
            message_list.append(new_message)
            add_message_to_chat(new_message,chat_id)
            should_continue = True

    if (tools_called is not None and len(tools_called) > 0):
        for call in tools_called:
            function = call.function
            for tool in tools:
                if (function.name == tool.name):
                    [should_continue, return_message] = tool.run(function.arguments)
                    new_message = {"role": "system", "content":[{"type":"text", "text":return_message }]}
                    message_list.append(new_message)
                    add_message_to_chat(new_message,chat_id)
                    print(return_message,file=sys.stderr)

    return [should_continue, message_list]

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Command line tool for conversation management.")
    parser.add_argument('prompt', nargs='?', default='', help='String prompt to start a conversation unless a flag is provided.')
    parser.add_argument('--last', '-l', action='store_true', help='Loads the last conversation.')
    parser.add_argument('--incognito', '-i', action='store_true', help='Marks the conversation as not saved.')
    parser.add_argument('--resume','-r', action='store_true', help='Open the conversation list and choose one to continue')

    args = parser.parse_args()  
    if (not (args.resume or len(args.prompt) > 0) or args.last):
        parser.print_help()
        exit()

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

    chat_loaded = False
    if (args.resume):
        recent_chats = gpt_db.get_recent_chats(MAX_FILES_LIST)
        num_chats = 0
        for chat in recent_chats:
            print("[%d] - %s" % (num_chats,recent_chats.title))
        selection = False
        while not selection:
            answer = input("Select a conversation to continue: ")
            answer = answer.lower()
            if (answer.isdigit()):
                answer = int(answer)
                chat_id = recent_chats[answer].id 
                selection = True
            else:
                print("ERROR - Invalid input - quitting.")
                exit()

        messages = load_chat_from_file(chat_id)
        chat_loaded = True

    if not chat_loaded:
        [messages, chat_id] = load_default_chat(args.prompt,stdin)
    print("DEBUG: " + str(messages))
    [result, messages] = call_and_process(messages, chat_id)

    while result:
        [result, messages] = call_and_process(messages, chat_id) 

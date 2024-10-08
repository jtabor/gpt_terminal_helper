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
import textwrap

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

session = PromptSession()
bindings = KeyBindings()

# Add a key binding for Ctrl+D to accept the input
@bindings.add('c-d')
def _(event):
    event.current_buffer.validate_and_handle()


from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

# GPT_MODEL = 'gpt-4-turbo-2024-04-09'
GPT_MODEL = 'gpt-4-turbo'
# GPT_MODEL = 'gpt-4o-2024-05-13'
SYSTEM_PROMPT = "You are a helpful command line assistant.  You take requests from the user and generate Linux shell commands for them.  You ask for extra info if you need it.  Use the provided function calls to accomplish the user's request.  You can call shell commands with return_result = True to get more information to accomplish your goal.  Unless otherwise specified, assume you are using the current directory for all requests.  Try to take some initiative while answering the user's question.  They will approve all shell commands."

GPT_DIRECTORY = os.path.expanduser("~/.gpt")
GLOBAL_CONFIG = GPT_DIRECTORY + "/global_context.md"
MAX_FILES_LIST = 20
INDENT_WIDTH = 12

MAX_TOKENS = 4096
global_config = None

if not os.path.exists(GPT_DIRECTORY):
    os.makedirs(GPT_DIRECTORY)

tools = [cf.run_in_terminal_function, cf.write_file_function]
tools_descriptions = [tool.description for tool in tools]
def add_message_to_chat(message, chat_id):
    if (not args.incognito):
        for content in message['content']:
                gpt_db.add_message(chat_id, message['role'], content['type'],content[content['type']])

def print_message(message, show_system=True, raw_text=False):
    if (message['role'] != 'system' or show_system) and not raw_text:
        role_text = f"**{message['role']}**:"
        content_text = "\n".join(content['text'] for content in message['content'] if content['type'] == 'text')
        markdown_message = Markdown(f"{role_text}\n{content_text}")
        
        panel = Panel(markdown_message, expand=True)
        console.print(panel)
    if (message['role'] != 'system' or show_system) and raw_text:
        role_text = f"**{message['role']}**:"
        content_text = "\n".join(content['text'] for content in message['content'] if content['type'] == 'text')
        print(content_text)     
    
def multiline_user_input(prompt):
    
    print(prompt)
    user_input = session.prompt(multiline=True, key_bindings=bindings)
    print("\033[F" * (user_input.count('\n') + 2) + "\033[K", end='')  
    return user_input


def print_numbered_list(conversations):
    for index, conversation in enumerate(conversations):
        text = Text.assemble(
            # (f"{index}-", "black on white"),
            (f"[{index}]:", "bold blue"),
            (" " + conversation, "default")
        )
        console.print(text)
    console.print("\n")

def print_message_old(message,show_system=False):
    
    if message['role'] != 'system' or show_system:
        wrapper = textwrap.TextWrapper(width=os.get_terminal_size().columns-15,initial_indent='',subsequent_indent=' '*INDENT_WIDTH)
        remaining_pad = INDENT_WIDTH - len(message['role'])
        spaces = ' '*remaining_pad
        formatted_chat = str(message['role']) + ":" + spaces
        first_line = True
        for content in message['content']:
            if content['type'] == 'text':
                formatted_message = wrapper.fill(content[content['type']].strip().replace('\n',' '))
                if not first_line:
                    formatted_message = formatted_message[INDENT_WIDTH:]
                formatted_chat += formatted_message + '\n'
            else:
                message_text = "UNKNOWN_TYPE: " + content['type']
                formatted_message = wrapper.fill(message_text.strip().replace('\n',' '))
                if not first_line:
                    formatted_message = formatted_message[INDENT_WIDTH:]
                formatted_chat += '\n' + formatted_message
            first_line = False
        print(formatted_chat)

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

def generate_user_specific_messages():
    to_return = []
    if os.path.exists(GLOBAL_CONFIG):
        with open(GLOBAL_CONFIG, "r") as file:
            global_config = file.read()
            to_return.append({"role": "system", "content": [{"type":"text", "text":"USER SPECIFIC INFO: \n" + global_config}]})

    LOCAL_CONFIG = os.getcwd() + "/.gpt/local_context.md"
    if os.path.exists(LOCAL_CONFIG):
        with open(LOCAL_CONFIG, "r") as file:
            local_config = file.read()
            to_return.append({"role": "system", "content":  [{"type":"text","text":"DIRECTORY SPECIFIC INFO: \n" + local_config}]})
    return to_return

def load_default_chat(prompt,stdin):
    messages = [{"role": "system", "content": [{"type":"text", "text":SYSTEM_PROMPT}]}]
    messages.append({ "role": "system", "content": [ { "type": "text", "text": stdin, } ], })
    messages.append({ "role": "user", "content": [ { "type": "text", "text": prompt, } ], })
    if (not args.incognito):
        chat_id = gpt_db.add_chat(prompt)
    else:
        chat_id = None
    user_specific_messages = generate_user_specific_messages()
   
    for user_specific_message in user_specific_messages:
        messages.append(user_specific_message)
    
    for message in messages:
        add_message_to_chat(message,chat_id)
    
    #NOTE: Don't save the environment.. we want that fresh each time (I think)
    environment_messages = generate_environment_messages()
    for environment_message in environment_messages:
        messages.append(environment_message)

    return [messages,chat_id]

def load_chat_from_db(chat_id):
    db_messages = gpt_db.get_all_messages(chat_id)
    if (not args.incognito):
        gpt_db.update_chat_date(chat_id)
    to_return = []
    for db_message in db_messages:
        to_return.append({"role":db_message.role,"content": [ { "type": db_message.message_type, "text": db_message.content}]})

    to_return.append({"role":"system","content": [{"type":"text", "text": "NOTE The conversation has been reloaded in the following environment"}]})
    environment_messages = generate_environment_messages()
    for environment_message in environment_messages:
        to_return.append(environment_message)
    user_specific_messages = generate_user_specific_messages()
    for user_specific_message in user_specific_messages:
        to_return.append(user_specific_message)
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
        max_tokens=MAX_TOKENS)
    
    tools_called = response.choices[0].message.tool_calls

    return_message = response.choices[0].message.content


    if return_message:
        return_message ={"role": "assistant", "content": [{"type":"text", "text":return_message}]} 
        print_message(return_message)
        add_message_to_chat(return_message,chat_id)
        message_list.append(return_message)
        if (tools_called is not None):
            print("INFO: Tools pending: " + str(len(response.choices[0].message.tool_calls)),file=sys.stderr)
        # user_input = cf.safe_input("Answer: ").lower()
        user_input = multiline_user_input("Answer: ") 
        if user_input != '':
            new_message = {"role": "user", "content":[{"type":"text", "text": user_input}]}
            print_message(new_message)
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
                    print_message(new_message,show_system=True)
                    message_list.append(new_message)
                    add_message_to_chat(new_message,chat_id)
                    # print(return_message,file=sys.stderr)

    return [should_continue, message_list]

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="A chatGPT powered helper for terminals.")
    parser.add_argument('prompt', nargs='?', default='', help='String prompt to start a conversation unless a flag is provided.')
    parser.add_argument('--last', '-l', action='store_true', help='Loads the last conversation.')
    parser.add_argument('--incognito', '-i', action='store_true', help='Marks the conversation as not saved.')
    parser.add_argument('--resume','-r', action='store_true', help='Open the conversation list and choose one to continue')
    parser.add_argument('--print','-p', action='store_true', help='Convert a previous conversation to text')
    parser.add_argument('--gpt4o' , '-o' , action='store_true', help='Use the GPT 4o model')

    args = parser.parse_args()  
    if (not (args.resume or (len(args.prompt) > 0) or args.last or args.print)):
        parser.print_help()
        exit()
    if (args.gpt4o):
        print("DEBUG USING 4o")
        GPT_MODEL = "gpt-4o"
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
    first_chat = 0
    if (args.resume or args.print):
        selection = False
        while not selection:
            recent_chats = gpt_db.get_recent_chats(first_chat,first_chat + MAX_FILES_LIST - 1)
            print_numbered_list([chat.title for chat in recent_chats])
            answer = input("Select a conversation to continue (n for more): ")
            answer = answer.lower()
            if (answer.isdigit()):
                answer = int(answer)
                chat_id = recent_chats[answer].id 
                selection = True
            elif (answer == 'n'):
                first_chat = first_chat + MAX_FILES_LIST
            else:
                print("ERROR - Invalid input - quitting.")
                exit()
        print("\n\n")
        messages = load_chat_from_db(chat_id)
        for message in messages:
            print_message(message,args.print,args.print)
        if (args.resume):
            answer = multiline_user_input("Additional Prompt:")
            user_message ={"role": "user", "content": [{"type":'text', "text": answer}]}
            print_message(user_message)
            messages.append(user_message)
            add_message_to_chat(user_message, chat_id)
            chat_loaded = True
        else:
            exit()

    if not chat_loaded:
        [messages, chat_id] = load_default_chat(args.prompt,stdin)

    [result, messages] = call_and_process(messages, chat_id)

    while result:
        [result, messages] = call_and_process(messages, chat_id) 

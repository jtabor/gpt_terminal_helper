#! /usr/bin/python3
from openai import OpenAI
from anthropic import Anthropic
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
USE_CLAUDE = False  # Flag to determine which API to use
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
# OpenAI tools format
tools_descriptions_openai = [tool.description for tool in tools]
# Claude tools format
tools_descriptions_claude = [tool.claude_description for tool in tools]
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
    
    if USE_CLAUDE:
        # Use Anthropic Claude API
        client = Anthropic()
        
        # Convert our message format to Anthropic format
        anthropic_messages = []
        for message in message_list:
            if message['role'] == 'system':
                # Skip system messages initially - we'll add them as a system message
                continue
            
            content = []
            for item in message['content']:
                if item['type'] == 'text':
                    content.append({"type": "text", "text": item['text']})
            
            anthropic_messages.append({"role": message['role'], "content": content})
        
        # Extract system messages and combine them
        system_prompt = SYSTEM_PROMPT
        for message in message_list:
            if message['role'] == 'system':
                for content in message['content']:
                    if content['type'] == 'text':
                        system_prompt += "\n" + content['text']
        
        response = client.messages.create(
            model=GPT_MODEL,
            system=system_prompt,
            messages=anthropic_messages,
            tools=tools_descriptions_claude,
            max_tokens=MAX_TOKENS
        )
        
        # Safely extract text from the response - content might be different types
        return_message = ""
        if response.content and len(response.content) > 0:
            # Get the first content item that has text
            for content_item in response.content:
                if hasattr(content_item, 'text') and content_item.text:
                    return_message = content_item.text
                    break
        
        # Complete debug of the Claude response structure
        # print("DEBUG Claude response:", response, file=sys.stderr)
        
        # Try to find tool calls in different possible locations in the Claude API response
        tools_called = []
        
        # In the Anthropic API v0.19+, tool use might be in the content array
        for content_item in response.content:
            # Check if the content item has a type attribute
            if hasattr(content_item, 'type') and content_item.type == 'tool_use':
                # print("DEBUG: Found content item with type tool_use", file=sys.stderr)
                tools_called.append(content_item)
            
            # Check if content item has tool_use attribute
            if hasattr(content_item, 'tool_use') and content_item.tool_use:
                # print("DEBUG: Found content item with tool_use attribute", file=sys.stderr)
                tools_called.append(content_item.tool_use)
        
        # Also check at the top level of the response
        if hasattr(response, 'tool_calls') and response.tool_calls:
            # print("DEBUG: Found top-level tool_calls", file=sys.stderr)
            tools_called = response.tool_calls
            
        if hasattr(response, 'tool_outputs') and response.tool_outputs:
            # print("DEBUG: Found top-level tool_outputs", file=sys.stderr)
            tools_called = response.tool_outputs
            
        if hasattr(response, 'tools') and response.tools:
            # print("DEBUG: Found top-level tools", file=sys.stderr)
            tools_called = response.tools
        
    else:
        # Use OpenAI API
        client = OpenAI()
        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=message_list,
            tools=tools_descriptions_openai,
            max_tokens=MAX_TOKENS
        )
        
        tools_called = response.choices[0].message.tool_calls
        return_message = response.choices[0].message.content

    if return_message:
        return_message = {"role": "assistant", "content": [{"type":"text", "text":return_message}]} 
        print_message(return_message)
        add_message_to_chat(return_message, chat_id)
        message_list.append(return_message)
        
        if tools_called is not None and len(tools_called) > 0:
            print("INFO: Tools pending: " + str(len(tools_called)), file=sys.stderr)
            
        user_input = multiline_user_input("Answer: ") 
        if user_input != '':
            new_message = {"role": "user", "content":[{"type":"text", "text": user_input}]}
            print_message(new_message)
            message_list.append(new_message)
            add_message_to_chat(new_message, chat_id)
            should_continue = True

    if tools_called is not None and len(tools_called) > 0:
        if USE_CLAUDE:
            # Process Claude tool calls
            for tool_use in tools_called:
                # print("DEBUG Processing Claude tool:", tool_use, file=sys.stderr)
                
                # Extract tool name and input based on different potential structures
                tool_name = None
                tool_input = None
                
                # Check all possible structures for Claude tool calls
                if hasattr(tool_use, 'name'):
                    tool_name = tool_use.name
                elif hasattr(tool_use, 'id'):
                    tool_name = tool_use.id
                
                if hasattr(tool_use, 'input'):
                    tool_input = tool_use.input
                elif hasattr(tool_use, 'tool_use') and hasattr(tool_use.tool_use, 'input'):
                    tool_input = tool_use.tool_use.input
                elif hasattr(tool_use, 'parameters'):
                    tool_input = tool_use.parameters
                elif hasattr(tool_use, 'input_json'):
                    tool_input = json.loads(tool_use.input_json)
                
                # If we have tool name and input, proceed
                if tool_name and tool_input:
                    # Convert the input to a string format expected by our functions
                    if isinstance(tool_input, dict):
                        tool_args = json.dumps(tool_input)
                    else:
                        tool_args = tool_input
                    
                    # print(f"DEBUG Using tool: {tool_name} with args: {tool_args}", file=sys.stderr)
                    
                    for tool in tools:
                        if tool_name == tool.name or (hasattr(tool, 'claude_description') and 
                                                     tool.claude_description['name'] == tool_name):
                            [should_continue, return_message] = tool.run(tool_args)
                            # For Claude, we need to add this as a tool_result
                            tool_result_message = {"role": "system", "content":[{"type":"text", "text":return_message}]}
                            print_message(tool_result_message, show_system=True)
                            message_list.append(tool_result_message)
                            add_message_to_chat(tool_result_message, chat_id)
                            
                            # Claude needs to receive the tool response in a special format
                            if USE_CLAUDE:
                                # Create the anthropic format response for the next API call
                                anthropic_messages = []
                                for message in message_list:
                                    if message['role'] == 'system':
                                        # Skip system messages for now
                                        continue
                                    
                                    content = []
                                    for item in message['content']:
                                        if item['type'] == 'text':
                                            content.append({"type": "text", "text": item['text']})
                                    
                                    anthropic_messages.append({"role": message['role'], "content": content})
                                
                                # Extract system messages again
                                system_prompt = SYSTEM_PROMPT
                                for message in message_list:
                                    if message['role'] == 'system':
                                        for content in message['content']:
                                            if content['type'] == 'text':
                                                system_prompt += "\n" + content['text']
                                
                                # Add the tool result directly as tool_outputs
                                client = Anthropic()
                                
                                # Get the tool_id for Claude tool result
                                tool_id = None
                                if hasattr(tool_use, 'id'):
                                    tool_id = tool_use.id
                                
                                # print(f"DEBUG Sending tool result for tool_id: {tool_id} with result: {return_message}", file=sys.stderr)
                                
                                # Create response with tool results
                                try:
                                    # Build the message with the tool result included
                                    # Create a new request instead of using tool_results which may not be supported
                                    # Include the command execution result in the message history
                                    tool_result_anthropic_message = {
                                        "role": "user", 
                                        "content": [
                                            {"type": "text", "text": f"Here is the result of the command: {return_message}"}
                                        ]
                                    }
                                    
                                    # Add the tool result as a user message so Claude can see it
                                    anthropic_messages.append(tool_result_anthropic_message)
                                    
                                    # Make a new request with the updated message history
                                    response = client.messages.create(
                                        model=GPT_MODEL,
                                        system=system_prompt,
                                        messages=anthropic_messages,
                                        tools=tools_descriptions_claude,
                                        max_tokens=MAX_TOKENS
                                    )
                                    
                                    # Add the response to our messages - safely extract text
                                    if response.content and len(response.content) > 0:
                                        response_text = ""
                                        # Extract text from the first content item that has text
                                        for content_item in response.content:
                                            if hasattr(content_item, 'text') and content_item.text:
                                                response_text = content_item.text
                                                break
                                        
                                        if response_text:
                                            tool_response_message = {"role": "assistant", "content": [{"type":"text", "text":response_text}]}
                                            print_message(tool_response_message)
                                            add_message_to_chat(tool_response_message, chat_id)
                                            message_list.append(tool_response_message)
                                except Exception as e:
                                    print(f"ERROR in Claude tool result handling: {e}", file=sys.stderr)
        else:
            # Process OpenAI tool calls
            for call in tools_called:
                function = call.function
                for tool in tools:
                    if function.name == tool.name:
                        [should_continue, return_message] = tool.run(function.arguments)
                        new_message = {"role": "system", "content":[{"type":"text", "text":return_message}]}
                        print_message(new_message, show_system=True)
                        message_list.append(new_message)
                        add_message_to_chat(new_message, chat_id)

    return [should_continue, message_list]

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="A ChatGPT/Claude powered helper for terminals.")
    parser.add_argument('prompt', nargs='?', default='', help='String prompt to start a conversation unless a flag is provided.')
    parser.add_argument('--last', '-l', action='store_true', help='Loads the last conversation.')
    parser.add_argument('--incognito', '-i', action='store_true', help='Marks the conversation as not saved.')
    parser.add_argument('--resume','-r', action='store_true', help='Open the conversation list and choose one to continue')
    parser.add_argument('--print','-p', action='store_true', help='Convert a previous conversation to text')
    parser.add_argument('--gpt4o', '-o', action='store_true', help='Use the GPT 4o model')
    parser.add_argument('--claude-3-5', '-c5', action='store_true', help='Use Claude 3.5 Sonnet model')
    parser.add_argument('--claude-3-7', '-c7', action='store_true', help='Use Claude 3.7 Sonnet model')

    args = parser.parse_args()  
    if (not (args.resume or (len(args.prompt) > 0) or args.last or args.print)):
        parser.print_help()
        exit()
    if (args.gpt4o):
        # print("DEBUG USING GPT-4o")
        GPT_MODEL = "gpt-4o"
        USE_CLAUDE = False
    elif (getattr(args, 'claude_3_5', False)):
        # print("DEBUG USING Claude 3.5 Sonnet")
        GPT_MODEL = "claude-3-5-sonnet-20240620"
        USE_CLAUDE = True
    elif (getattr(args, 'claude_3_7', False)):
        # print("DEBUG USING Claude 3.7 Sonnet")
        GPT_MODEL = "claude-3-7-sonnet-20250219"
        USE_CLAUDE = True
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

# GPT Terminal Helper

A chatGPT powered helper for terminals.

## Introduction

This python program helps a user run terminal commands.  It provides chatGPT with some extra tools and information so it can help terminal users better:

1. User defined prompts
    1. The user can define additions to the default prompt in their gpt directory (`~/.gpt/global_context.md` by default, the directory can be overridden with the GPT_DIRECTORY environment variable).  
    2. The user can also define a per-directory addition to the prompt if there some extra information they need to add about using the current directory by creating a file in `.gpt/local_context.md` in the directory gpt_terminal_helper will be run from.  This helps give special instructions for a project or set of data.
2. Environment - The system automatically adds the output of `lsb_release -a` at the start of each conversation so GPT knows about your platform.  
3. Current time - the current time is added to each chat.
4. The current directory is added to each chat.
5. There are a few functions that are also added to chat gpt by default.
    1. `run_in_terminal` - This allows chatgpt to run arbitrary terminal commands.  It will auto-run a few commands without results, but it will otherwise ask the user for confirmation before running something.  The results are returned to chatGPT, so make sure the commands don't return too much text, or you'll incur high API costs.
    2. `write_file` - This allows chatGPT to write a file.  This is nice for asking it to write python scripts and so forth.
    3. User defined functions - More functions can be added in [chat_functions.py](https://github.com/jtabor/gpt_terminal_helper/blob/master/chat_functions.py).


Chat history is saved in a sqlite file in GPT_DIRECTORY so you can continue conversations or convert them to plain text for copy and pasting.  The conversation is formatted as markdown with the [rich](https://github.com/Textualize/rich) python library.  


## Setup

1. Add OpenAI keys to the environment by running this command, or adding it to your `.bashrc` or `.zshrc` file, depending on which shell you're using.
    `export OPENAI_API_KEY="your_api_key_here"`
2. Install the required python packages while you're in the repo's directory.
    `python3 -m pip install -r requirements.txt`


## Usage

Default usage: `gpt_command.py "<insert prompt here>"`

Additional arguments (`gpt_command.py -h` to display this help):
```
usage: gpt [-h] [--last] [--incognito] [--resume] [--print] [--gpt4o] [prompt]

A chatGPT powered helper for terminals.

positional arguments:
  prompt           String prompt to start a conversation unless a flag is provided.

options:
  -h, --help       show this help message and exit
  --last, -l       Loads the last conversation.
  --incognito, -i  Marks the conversation as not saved.
  --resume, -r     Open the conversation list and choose one to continue
  --print, -p      Convert a previous conversation to text
  --gpt4o, -o      Use the GPT 4o model
```

## TODO
1. Add support for local LLMs (Ollama)/other LLMs with OpenAi library.
2. Use the OpenAi Assistants API?  This will use threads instead of having to send the entire conversation up each time (maybe saves API usage too?).  Also adds support for file search.
3. Config file for model options (ie. control the model used, temperature, etc.)  Maybe have an option for user-defined 'presets' they can load themselves with a command line arg.

## Contributing
Feel free to open a PR if you want to contribute, especially if it's for one of the TODOs.

## Introduction

See the instructions [here](README.md) for how to install the necessary dependencies and run an interactive shell that will spin up a set of federators on your local machine and allow you to transfer assets between the main chain and a side chain.

For all these scripts, make sure the `RIPPLED_MAINCHAIN_EXE`, `RIPPLED_SIDECHAIN_EXE`, `RIPPLED_SIDECHAIN_CFG_DIR`, and `NUM_FEDERATORS` environment variables are correctly set, and the side chain configuration files exist.

Note: the unit tests do not use the configuration files, so the `RIPPLED_SIDECHAIN_CFG_DIR` is not needed for that script.

## Dev Env Setup

### Manage dependencies and virtual environments

To simplify managing library dependencies and the virtual environment, this package uses [`poetry`](https://python-poetry.org/docs).

* [Install `poetry`](https://python-poetry.org/docs/#osx-linux-bashonwindows-install-instructions):

        curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python - poetry install

### Set up Python environment

This step isn't strictly necessary if you prefer to just use your local Python version. However, to make it easy to manage your Python environment, including switching between versions, install `pyenv` and follow these steps:

* Install [`pyenv`](https://github.com/pyenv/pyenv):

        brew install pyenv

    For other installation options, see the [`pyenv` README](https://github.com/pyenv/pyenv#installation).

* Use `pyenv` to install the optimized version (currently 3.8.0):

        pyenv install 3.8.0

* Set the [global](https://github.com/pyenv/pyenv/blob/master/COMMANDS.md#pyenv-global) version of Python with `pyenv`:

        pyenv global 3.8.0

### Set up shell environment

To enable autocompletion and other functionality from your shell, add `pyenv` to your environment.

These steps assume that you're using a [Zsh](http://zsh.sourceforge.net/) shell. For other shells, see the [`pyenv` README](https://github.com/pyenv/pyenv#basic-github-checkout).

* Add `pyenv init` to your Zsh shell:

        echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init -)"\nfi' >> ~/.zshrc

* Source or restart your terminal:

        . ~/.zshrc

## Unit tests

The "tests" directory contains a simple unit test. It take several minutes to run, and will create the necessary configuration files, start a test main chain in standalone mode, and a test side chain with 5 federators, and do some simple cross-chain transactions. Side chains do not yet have extensive tests. Testing is being actively worked on.

To run the tests, type:
```
poetry run pytest tests
```

To capture logging information and to set the log level (to help with debugging), type this instead:
```
poetry run pytest tests --full-trace --log-file=log.txt --log-file-level=info
```

The response should be something like the following:
```
============================= test session starts ==============================
platform darwin -- Python 3.9.1, pytest-6.2.5, py-1.11.0, pluggy-1.0.0
rootdir: /Users/mvadari/Documents/sidechain-launch-kit
plugins: anyio-3.3.4
collected 1 item

tests/simple_xchain_transfer_test.py .                              [100%]

======================== 1 passed in 221.90s (0:03:41) =========================


```

## Generate reference docs

You can see the complete reference documentation at [link TBD]. You can also generate them locally using `poetry` and `sphinx`:

```bash
# Go to the docs/ folder
cd docs/

# Build the docs
poetry run sphinx-apidoc -o source/ ../xrpl
poetry run make html
```

To see the output:

```bash
# Go to docs/_build/html/
cd docs/_build/html/

# Open the index file to view it in a browser:
open _build/html/index.html
```

## Scripts
### shell.py

This is an interactive shell for experimenting with side chains. It will spin up a test main chain running in standalone mode, and a test side chain with five federators - all running on the local machine. There are commands to make payments within a chain, make cross-chain payments, check balances, check server info, and check federator info. There is a simple "help" system, but more documentation is needed for this tool (or more likely we need to replace this with some web front end).

Note: a "repl" is another name for an interactive shell. It stands for "read-eval-print-loop". It is pronounced "rep-ul".

### create_config_file.py

This is a script used to create the config files needed to run a test side chain on your local machine. To run this, make sure the rippled is built, `RIPPLED_MAINCHAIN_EXE`, `RIPPLED_SIDECHAIN_EXE`, `RIPPLED_SIDECHAIN_CFG_DIR`, and `NUM_FEDERATORS` environment variables are correctly set, and the side chain configuration files exist. Also make sure the python dependencies are installed and the virtual environment is activated. Running this will create config files in the directory specified by the `RIPPLED_SIDECHAIN_CFG_DIR` environment variable.

### utils/log_analyzer.py

This is a script used to take structured log files and convert them to json for easier debugging.

## Python modules

### sidechain_launch.py

A python module that can be used to write python scripts to interact with side chains. This is used to write unit tests and the interactive shell. To write a standalone script, look at how the tests are written in `test/simple_xchain_transfer_test.py`. The idea is to call `sidechain._multinode_with_callback`, which sets up the two chains, and place your code in the callback. For example:

```
def multinode_test(params: Params):
    def callback(mc_app: App, sc_app: App):
        my_function(mc_app, sc_app, params)

    sidechain._multinode_with_callback(params, callback)
```

The functions `sidechain.main_to_side_transfer` and `sidechain.side_to_main_transfer` can be used as convenience functions to initiate cross chain transfers. Of course, these transactions can also be initiated with a payment to the door account with the memo data set to the destination account on the destination chain (which is what those convenience functions do under the hood).

Transactions execute asynchonously. Use the function `test_utils.wait_for_balance_change` to ensure a transaction has completed.

### chain/chain.py

Python module for an application. An application is responsible for local network (or single server) and an address book that maps aliases to accounts.

### classes/config_file.py

Python module representing a config file that is read from disk.

### repl.py

Python module with the implementation of the interactive shell.

### chain/sidechain.py

A Python module representing a sidechain running on the local machine.

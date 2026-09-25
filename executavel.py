"""Ponto de entrada do .exe (PyInstaller). Duplo clique = gravar."""

import sys

from f1tele.__main__ import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

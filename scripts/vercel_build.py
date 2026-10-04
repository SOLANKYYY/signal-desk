"""Publish only the two static UI assets; authenticated HTML stays in Flask."""
from pathlib import Path
from shutil import copy2
root=Path(__file__).resolve().parents[1]
(root/'public').mkdir(exist_ok=True)
for name in ('app.js','styles.css'):copy2(root/'frontend'/name,root/'public'/name)
print('Static assets prepared.')

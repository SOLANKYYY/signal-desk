"""Publish only the two static UI assets; authenticated HTML stays in Flask."""
from pathlib import Path
from shutil import copy2
root=Path(__file__).resolve().parents[1]
(root/'public').mkdir(exist_ok=True)
for name in ('app.js','styles.css','intel.js','intel.css','dashboard.css','coursework.js','assistant.js','replica-lab.js','exercise9.js'):copy2(root/'frontend'/name,root/'public'/name)
print('Static assets prepared.')

# Explicit opt-in only; never runs during normal deployments.
import os
if os.getenv('MODEL_INVENTORY_CHECK')=='1':
    from provider_check import main
    main()

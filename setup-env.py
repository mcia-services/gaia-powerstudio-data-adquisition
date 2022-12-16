import os

os.system('.venv\\Scripts\\activate.bat')



# Distinguish between Windows and Linux
if os.name == 'nt':
    os.system('rmdir /S /Q .venv | py -m venv .venv && .venv\\Scripts\\activate.bat && pip install -r requirements.txt')
else:
    os.system('python3 -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt')

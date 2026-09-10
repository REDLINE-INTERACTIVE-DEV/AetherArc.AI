import ast, pathlib, re, xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
required = [
    'app.py', 'requirements.txt', '.env.example', 'START_AETHER_SERVER.py',
    'index.html', 'style.css', '.github/workflows/build-android.yml',
    'mobile/settings.gradle', 'mobile/build.gradle', 'mobile/app/build.gradle',
    'mobile/app/src/main/AndroidManifest.xml',
    'mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java',
    'mobile/app/src/main/assets/index.html',
]
missing=[p for p in required if not (ROOT/p).exists()]
assert not missing, f'Missing required files: {missing}'
for p in ROOT.rglob('*.py'):
    if any(part in {'.git','.gradle','build','__pycache__'} for part in p.parts): continue
    ast.parse(p.read_text(encoding='utf-8'))
for p in ROOT.rglob('*.xml'):
    if any(part in {'.git','.gradle','build'} for part in p.parts): continue
    ET.parse(p)
html=(ROOT/'index.html').read_text(encoding='utf-8')
mobile=(ROOT/'mobile/app/src/main/assets/index.html').read_text(encoding='utf-8')
assert '/api/chat' in html or '/api/chat' in mobile
assert 'image_data' in mobile and 'genimg' in mobile
assert 'image_data' in mobile
assert 'FileResponse(FRONTEND/' in (ROOT/'app.py').read_text(encoding='utf-8')
secret_patterns=[r'ghp_[A-Za-z0-9]{20,}',r'github_pat_[A-Za-z0-9_]{20,}',r'(?i)sk-[A-Za-z0-9]{20,}']
for p in ROOT.rglob('*'):
    if not p.is_file() or any(part in {'.git','.gradle','build','__pycache__'} for part in p.parts): continue
    if p.name in {'.env.example'}: continue
    try: text=p.read_text(encoding='utf-8')
    except Exception: continue
    for pat in secret_patterns: assert not re.search(pat,text), f'Possible secret in {p}'
print('STATIC_VERIFY_OK')

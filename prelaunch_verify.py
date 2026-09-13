from pathlib import Path

ROOT = Path(__file__).resolve().parent
required = [
    '.github/workflows/build-android.yml',
    'mobile/settings.gradle',
    'mobile/build.gradle',
    'mobile/app/build.gradle',
    'mobile/app/src/main/AndroidManifest.xml',
    'mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java',
    'mobile/app/src/main/assets/index.html',
]
missing = [p for p in required if not (ROOT / p).exists()]
assert not missing, f'Missing required files: {missing}'

# Check source/config files for the old hosting URL/config without scanning this verifier itself.
for path in ROOT.rglob('*'):
    if path == ROOT / 'prelaunch_verify.py':
        continue
    if not path.is_file() or any(part in {'.git', '.gradle', 'build', '__pycache__'} for part in path.parts):
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        continue
    assert 'onrender.com' not in text.lower(), f'Legacy hosting URL found in {path}'
    assert 'render.yaml' not in text.lower(), f'Legacy hosting config reference found in {path}'

mobile = (ROOT / 'mobile/app/src/main/assets/index.html').read_text(encoding='utf-8')
assert 'AndroidAether.chat' in mobile
assert 'openai/gpt-oss-20b' in mobile
assert 'aether_hf_token' in mobile

main = (ROOT / 'mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java').read_text(encoding='utf-8')
assert 'file:///android_asset/index.html' in main
assert 'router.huggingface.co/v1/chat/completions' in main

assert not (ROOT / 'render.yaml').exists()
assert not (ROOT / 'app.py').exists()

print('STANDALONE_AETHER_VERIFY_OK')

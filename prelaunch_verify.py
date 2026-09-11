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

for path in ROOT.rglob('*'):
    if not path.is_file() or any(part in {'.git', '.gradle', 'build', '__pycache__'} for part in path.parts):
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        continue
    assert 'onrender.com' not in text.lower(), f'Legacy Render URL found in {path}'
    assert 'render.yaml' not in text.lower(), f'Legacy Render config reference found in {path}'

mobile = (ROOT / 'mobile/app/src/main/assets/index.html').read_text(encoding='utf-8')
assert 'AndroidAether.chat' in mobile
assert 'Qwen/Qwen2.5-7B-Instruct' in mobile
assert 'aether_hf_token' in mobile

main = (ROOT / 'mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java').read_text(encoding='utf-8')
assert 'file:///android_asset/index.html' in main
assert 'router.huggingface.co/v1/chat/completions' in main

print('STANDALONE_AETHER_VERIFY_OK')

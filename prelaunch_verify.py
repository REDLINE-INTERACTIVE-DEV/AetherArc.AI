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
assert 'POST /api/chat' in mobile
assert 'Hugging Face' not in mobile
assert 'aether_hf_token' not in mobile

main = (ROOT / 'mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java').read_text(encoding='utf-8')
assert 'file:///android_asset/index.html' in main
assert 'Hugging Face' not in main
assert 'router.huggingface.co/v1/chat/completions' not in main

brain = (ROOT / 'backend/app/core/brain.py').read_text(encoding='utf-8')
native = (ROOT / 'backend/app/core/native_brain.py').read_text(encoding='utf-8')
assert 'from app.agents.base import AgentMessage, BaseAgent' not in brain
assert 'AetherNativeBrain' in brain
assert 'external_model_used' in brain
assert 'httpx' not in native
assert 'AI_API_KEY' not in native

print('STANDALONE_AETHER_VERIFY_OK')

from pathlib import Path
ROOT=Path(__file__).resolve().parent
mobile=(ROOT/'mobile/app/src/main/assets/index.html').read_text(encoding='utf-8')
activity=(ROOT/'mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java').read_text(encoding='utf-8')
brain=(ROOT/'backend/app/core/brain.py').read_text(encoding='utf-8')
native=(ROOT/'backend/app/core/native_brain.py').read_text(encoding='utf-8')
assert 'Paste your backend URL first' not in mobile
assert 'backendUrl' in mobile
assert 'getBackendUrl' in activity
assert 'onrender.com' not in mobile
assert 'aether_hf_token' not in mobile
assert 'BaseAgent' not in brain
assert 'AetherNativeBrain' in native
assert 'CognitiveState' in native
print('Aether prelaunch verification passed.')

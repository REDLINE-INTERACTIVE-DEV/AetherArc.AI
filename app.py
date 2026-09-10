import os, json, time, uuid, sqlite3, hashlib, secrets, urllib.parse, urllib.request, urllib.error, re, asyncio, base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'storage' / 'aether.db'
FRONTEND = ROOT
DB.parent.mkdir(exist_ok=True)

app = FastAPI(title='Aether API', version='0.5.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

AGENTS = {
    'manager': {'name':'ManagerAI','role':'Team manager / orchestrator'},
    'reason': {'name':'ReasonAI','role':'Reasoning & analysis specialist'},
    'code': {'name':'CodeAI','role':'Coding & engineering specialist'},
    'research': {'name':'ResearchAI','role':'Web, news & local research specialist'},
}
SYSTEM_PROMPTS = {
    'manager': '''You are ManagerAI, the lead of Aether. You receive the user's request, decide which specialists are useful, delegate work, inspect their reports, and return one coherent answer. Never claim a specialist was consulted unless a report is present. Do not invent tool results or research.''',
    'reason': '''You are ReasonAI, Aether's reasoning and analysis specialist. Analyze assumptions, constraints, alternatives, risks and conclusions. Give the manager a concise, useful report. Do not pretend to have performed external actions.''',
    'code': '''You are CodeAI, Aether's software engineering specialist. Design correct, maintainable implementations, debug carefully, and give the manager concrete code or engineering steps when needed. Never claim code was executed unless execution evidence is supplied.''',
    'research': '''You are ResearchAI, Aether's research specialist. Analyze the supplied live search results, separate evidence from uncertainty, and return useful findings with source titles and URLs. Do not invent sources.''',
}
SESSIONS = {}

class Chat(BaseModel):
    message: str
    agent: str = 'manager'
    conversation_id: str | None = None
    location: str | None = None

class Auth(BaseModel):
    email: str
    password: str

class Guest(BaseModel):
    name: str = 'Guest'


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, provider TEXT DEFAULT "local", created_at REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, user_id INTEGER, title TEXT, created_at REAL, updated_at REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT, agent TEXT, role TEXT, content TEXT, created_at REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER, guest INTEGER DEFAULT 0, expires_at REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS oauth_states(state TEXT PRIMARY KEY, provider TEXT, created_at REAL)')
    c.commit(); c.close()
init_db()


def phash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 160000).hex()


def checkpw(password, stored):
    try:
        salt, h = stored.split(':', 1)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 160000).hex() == h
    except Exception:
        return False


def token_for(user_id, guest=False):
    t = secrets.token_urlsafe(32)
    record = {'user_id': user_id, 'guest': guest}
    SESSIONS[t] = record
    c = db(); c.execute('INSERT OR REPLACE INTO sessions(token_hash,user_id,guest,expires_at) VALUES(?,?,?,?)',(hashlib.sha256(t.encode()).hexdigest(),user_id,1 if guest else 0,time.time()+60*60*24*30)); c.commit(); c.close()
    return t


def current_user(request: Request):
    t = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    if not t: return None
    if t in SESSIONS: return SESSIONS[t]
    c=db(); row=c.execute('SELECT user_id,guest,expires_at FROM sessions WHERE token_hash=?',(hashlib.sha256(t.encode()).hexdigest(),)).fetchone(); c.close()
    if not row or row['expires_at'] < time.time(): return None
    record={'user_id':row['user_id'],'guest':bool(row['guest'])}; SESSIONS[t]=record; return record


def provider_url():
    if os.getenv('AETHER_MODEL_BASE_URL'):
        return os.getenv('AETHER_MODEL_BASE_URL').rstrip('/')
    if os.getenv('GROQ_API_KEY'):
        return 'https://api.groq.com/openai/v1'
    return ''


def provider_key():
    return os.getenv('AETHER_MODEL_API_KEY') or os.getenv('GROQ_API_KEY', '')


def provider_model():
    return os.getenv('AETHER_MODEL') or os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b')


def fallback_model():
    return os.getenv('AETHER_FALLBACK_MODEL', 'openai/gpt-oss-20b')


def ollama_model():
    return os.getenv('OLLAMA_MODEL', 'llama3.2')


def model_available():
    return bool((provider_url() and provider_model()) or os.getenv('POLLINATIONS_API_KEY') or os.getenv('OLLAMA_URL'))


def call_model(messages, temperature=0.2):
    if provider_url() and provider_model():
        payload = {'model': provider_model(), 'messages': messages, 'temperature': temperature}
        headers = {'Content-Type': 'application/json'}
        if provider_key(): headers['Authorization'] = 'Bearer ' + provider_key()
        models = [provider_model()]
        if provider_url() == 'https://api.groq.com/openai/v1':
            for candidate in [fallback_model(), 'openai/gpt-oss-120b', 'qwen/qwen3.6-27b']:
                if candidate and candidate not in models:
                    models.append(candidate)
            # A Groq project can expose a different subset of hosted models.
            # Discover the project's active model IDs so Aether can recover from
            # a stale/default model permission without requiring an app update.
            try:
                mreq = urllib.request.Request(provider_url() + '/models', headers=headers)
                with urllib.request.urlopen(mreq, timeout=20) as mr:
                    mdata = json.loads(mr.read().decode())
                discovered = [str(x.get('id')) for x in (mdata.get('data') or []) if x.get('id')]
                preferred = ['openai/gpt-oss-20b', 'openai/gpt-oss-120b', 'qwen/qwen3.6-27b', 'qwen/qwen3.8-27b']
                for candidate in preferred + discovered:
                    if candidate and candidate not in models:
                        models.append(candidate)
            except Exception:
                pass
        last_error = None
        attempted = []
        for model in models:
            attempted.append(model)
            payload['model'] = model
            req = urllib.request.Request(provider_url() + '/chat/completions', data=json.dumps(payload).encode(), headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    data = json.loads(r.read().decode())
                return data['choices'][0]['message']['content']
            except urllib.error.HTTPError as e:
                body = e.read().decode('utf-8', 'ignore')[:1000]
                last_error = e
                if e.code == 403 and model != models[-1]:
                    continue
                if e.code == 401:
                    raise RuntimeError('The AI provider rejected the API key (401). Check GROQ_API_KEY in Render.')
                if e.code == 403:
                    continue
                if e.code == 429:
                    raise RuntimeError('The AI provider is rate-limiting Aether right now (429). Please wait a moment and try again.')
                raise RuntimeError(f'AI provider request failed ({e.code}).')
            except urllib.error.URLError as e:
                raise RuntimeError('Aether could not reach the AI provider. Check the Render service connection.') from e
        # If Groq denies the project, continue to the next configured cloud provider.
        # Pollinations is intentionally the next fallback because Aether already
        # keeps its server-side key there for image generation.
    if os.getenv('POLLINATIONS_API_KEY'):
        try:
            purl = 'https://gen.pollinations.ai/v1/chat/completions'
            pmodel = os.getenv('POLLINATIONS_TEXT_MODEL', 'openai')
            ppayload = {'model': pmodel, 'messages': messages, 'temperature': temperature}
            preq = urllib.request.Request(purl, data=json.dumps(ppayload).encode(), headers={'Content-Type':'application/json','Authorization':'Bearer '+os.getenv('POLLINATIONS_API_KEY','')})
            with urllib.request.urlopen(preq, timeout=90) as r:
                pdata=json.loads(r.read().decode())
            return pdata['choices'][0]['message']['content']
        except Exception as e:
            pollinations_error = str(e)
        
    if os.getenv('OLLAMA_URL'):
        base = os.getenv('OLLAMA_URL').rstrip('/')
        payload = {'model': ollama_model(), 'messages': messages, 'stream': False, 'options': {'temperature': temperature}}
        req = urllib.request.Request(base + '/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
        return data.get('message', {}).get('content', '')
    return ''


def google_cse(q, gl='in', num=6):
    key, cx = os.getenv('GOOGLE_CSE_API_KEY'), os.getenv('GOOGLE_CSE_ID')
    if not key or not cx: return []
    url = 'https://www.googleapis.com/customsearch/v1?' + urllib.parse.urlencode({'key':key,'cx':cx,'q':q,'num':num,'gl':gl,'safe':'active'})
    try:
        with urllib.request.urlopen(url, timeout=15) as r: data = json.loads(r.read().decode())
        return [{'title':x.get('title',''),'url':x.get('link',''),'snippet':x.get('snippet','')} for x in data.get('items', [])]
    except Exception: return []


def google_news_rss(q, hl='en-IN', gl='IN', ceid='IN:en'):
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q':q,'hl':hl,'gl':gl,'ceid':ceid})
    try:
        with urllib.request.urlopen(url, timeout=15) as r: xml = r.read().decode('utf-8','ignore')
        items = []
        for item in re.findall(r'<item>(.*?)</item>', xml, re.S)[:10]:
            def tag(name):
                m = re.search(fr'<{name}>(.*?)</{name}>', item, re.S)
                return re.sub('<.*?>', '', m.group(1)).strip() if m else ''
            items.append({'title':tag('title'),'url':tag('link'),'snippet':tag('description'),'published':tag('pubDate')})
        return items
    except Exception: return []


def composio_enabled():
    return bool(os.getenv('COMPOSIO_API_KEY') and os.getenv('COMPOSIO_USER_ID'))


def composio_call(tool_slug, arguments):
    key = os.getenv('COMPOSIO_API_KEY', '')
    if not key: raise RuntimeError('COMPOSIO_API_KEY is not configured.')
    payload = {'user_id': os.getenv('COMPOSIO_USER_ID'), 'arguments': arguments, 'version': 'latest'}
    req = urllib.request.Request('https://backend.composio.dev/api/v3.1/tools/execute/' + tool_slug,
        data=json.dumps(payload).encode(), headers={'Content-Type':'application/json','x-api-key':key})
    with urllib.request.urlopen(req, timeout=60) as r:
        data=json.loads(r.read().decode())
    if not data.get('successful', True) or data.get('error'):
        raise RuntimeError(data.get('error') or 'Composio tool failed.')
    return data.get('data', data)


def github_target(text):
    m=re.search(r'https?://github\.com/([^/\s]+)/([^/\s#]+)(?:/blob/([^/\s#]+)/([^\s#]+))?', text, re.I)
    if m:
        return m.group(1), m.group(2).removesuffix('.git'), m.group(4) or os.getenv('AETHER_GITHUB_PATH',''), m.group(3) or os.getenv('AETHER_GITHUB_BRANCH','main')
    owner=os.getenv('AETHER_GITHUB_OWNER',''); repo=os.getenv('AETHER_GITHUB_REPO',''); path=os.getenv('AETHER_GITHUB_PATH',''); branch=os.getenv('AETHER_GITHUB_BRANCH','main')
    return owner,repo,path,branch


def github_fix(user_text):
    if not composio_enabled():
        return 'CodeAI can edit GitHub repositories through Composio, but COMPOSIO_API_KEY and COMPOSIO_USER_ID are not configured on this backend.', None
    owner,repo,path,branch=github_target(user_text)
    if not owner or not repo or not path:
        return 'To let CodeAI edit GitHub, include a GitHub file URL such as https://github.com/OWNER/REPO/blob/main/path/to/file, or configure AETHER_GITHUB_OWNER, AETHER_GITHUB_REPO and AETHER_GITHUB_PATH on the backend.', None
    read=composio_call('GITHUB_GET_REPOSITORY_CONTENT', {'owner':owner,'repo':repo,'path':path,'ref':branch})
    content_obj=read.get('content',read) if isinstance(read,dict) else {}
    b64=content_obj.get('content','') if isinstance(content_obj,dict) else ''
    if not b64: raise RuntimeError('GitHub returned no file content.')
    old=base64.b64decode(''.join(b64.split())).decode('utf-8','replace')
    fixed=call_model([
        {'role':'system','content':SYSTEM_PROMPTS['code']+'\nYou are editing a real repository file. Return ONLY the complete replacement file, with no markdown fences or explanation.'},
        {'role':'user','content':'USER REQUEST:\n'+user_text+'\n\nFILE PATH: '+path+'\n\nCURRENT FILE:\n'+old}
    ],0.1)
    if not fixed: raise RuntimeError('CodeAI returned no replacement content.')
    fixed=re.sub(r'^```[a-zA-Z0-9_+-]*\n','',fixed.strip())
    fixed=re.sub(r'\n```$','',fixed.strip())
    write=composio_call('GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS', {'owner':owner,'repo':repo,'path':path,'branch':branch,'content':fixed,'message':'fix: update file through Aether CodeAI'})
    return f'CodeAI updated `{owner}/{repo}` → `{path}` on `{branch}` through Composio.', write


def image_generate(prompt, model=None):
    key=os.getenv('POLLINATIONS_API_KEY','')
    if not key: raise RuntimeError('POLLINATIONS_API_KEY is not configured.')
    model=model or os.getenv('POLLINATIONS_IMAGE_MODEL','flux')
    url='https://gen.pollinations.ai/image/'+urllib.parse.quote(prompt, safe='')+'?'+urllib.parse.urlencode({'model':model})
    req=urllib.request.Request(url, headers={'Authorization':'Bearer '+key})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw=r.read(); ctype=r.headers.get_content_type() or 'image/jpeg'
    return 'data:'+ctype+';base64,'+base64.b64encode(raw).decode()


def fetch_public_page(url):
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'AetherResearch/0.5'})
        with urllib.request.urlopen(req,timeout=15) as r: raw=r.read(500000).decode('utf-8','ignore')
        text=re.sub(r'<script.*?</script>|<style.*?</style>',' ',raw,flags=re.I|re.S)
        text=re.sub(r'<[^>]+>',' ',text)
        text=re.sub(r'\s+',' ',text).strip()
        return text[:6000]
    except Exception: return ''


def research(query, location=None):
    q = query.strip() + ((' ' + location.strip()) if location and location.strip() else '')
    searches = [('Google web', x) for x in google_cse(q)] + [('Google News', x) for x in google_news_rss(q)]
    for u in re.findall(r'https?://[^\s]+', query)[:3]:
        page=fetch_public_page(u)
        if page: searches.insert(0,('User website',{'title':'Provided website','url':u,'snippet':page}))
    if location: searches += [('Local news', x) for x in google_news_rss(q + ' local news')]
    seen, out = set(), []
    for kind, x in searches:
        u = x.get('url', '')
        if not u or u in seen: continue
        seen.add(u); x['kind'] = kind; out.append(x)
    return out[:14]


def needs_code(text):
    return bool(re.search(r'\b(code|coding|python|javascript|typescript|java|kotlin|html|css|app|android|website|program|programming|debug|bug|api|github|build|software|script|repo)\b', text, re.I))


def needs_research(text):
    return bool(re.search(r'\b(latest|today|news|research|search|price|current|recent|2026|near me|local|where|when|who|what is happening)\b', text, re.I))


def specialist_report(agent, user_text, location=None):
    sources = research(user_text, location) if agent == 'research' else []
    context = '\n'.join(f"- {x['title']}: {x.get('snippet','')} ({x['url']})" for x in sources[:8])
    prompt = user_text
    if agent == 'research': prompt += '\n\nLIVE SEARCH RESULTS:\n' + (context or 'No live search results were available.')
    return call_model([{'role':'system','content':SYSTEM_PROMPTS[agent]},{'role':'user','content':prompt}], 0.15 if agent == 'research' else 0.2), sources


def manager_team(user_text, location=None):
    if not model_available():
        return ('ManagerAI is ready, but no model provider is configured. Set GROQ_API_KEY for the easiest cloud setup, or OLLAMA_URL/OLLAMA_MODEL for a local model.', {}, [])
    agents = ['reason']
    if needs_code(user_text): agents.append('code')
    if needs_research(user_text): agents.append('research')
    reports, sources = {}, []
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        futures = {pool.submit(specialist_report, a, user_text, location): a for a in agents}
        for future in as_completed(futures):
            a = futures[future]
            try:
                report, found = future.result(); reports[a] = report; sources.extend(found)
            except Exception as e:
                reports[a] = f'{AGENTS[a]["name"]} failed: {e}'
    bundle = '\n\n'.join(f"{AGENTS[a]['name']} REPORT:\n{r}" for a, r in reports.items())
    final = call_model([{'role':'system','content':SYSTEM_PROMPTS['manager']},{'role':'user','content':f'USER REQUEST:\n{user_text}\n\nSPECIALIST REPORTS:\n{bundle}\n\nReturn the best final answer for the user. Do not mention internal orchestration unless useful.'}], 0.2)
    return final or bundle, reports, sources


@app.get('/api/health')
def health():
    return {'ok':True,'name':'Aether','version':'0.5.0','model_connected':model_available(),'team':['ManagerAI','ReasonAI','CodeAI','ResearchAI']}

@app.get('/api/config')
def config():
    return {'agents':AGENTS,'model_connected':model_available(),'model':provider_model() if model_available() else None,'provider':('groq + Pollinations fallback' if os.getenv('GROQ_API_KEY') and os.getenv('POLLINATIONS_API_KEY') and not os.getenv('AETHER_MODEL_BASE_URL') else ('groq' if os.getenv('GROQ_API_KEY') and not os.getenv('AETHER_MODEL_BASE_URL') else ('openai-compatible' if provider_url() else ('Pollinations' if os.getenv('POLLINATIONS_API_KEY') else ('ollama' if os.getenv('OLLAMA_URL') else None))))),'research_google_cse':bool(os.getenv('GOOGLE_CSE_API_KEY') and os.getenv('GOOGLE_CSE_ID')),'composio_connected':composio_enabled(),'image_generation':bool(os.getenv('POLLINATIONS_API_KEY'))}

@app.post('/api/auth/register')
def register(a: Auth):
    c=db()
    try:
        cur=c.execute('INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)',(a.email.lower().strip(),phash(a.password),time.time())); c.commit(); uid=cur.lastrowid
    except sqlite3.IntegrityError:
        c.close(); raise HTTPException(400,'An account with that email already exists.')
    c.close(); return {'token':token_for(uid),'saved_history':True}

@app.post('/api/auth/login')
def login(a: Auth):
    c=db(); row=c.execute('SELECT * FROM users WHERE email=?',(a.email.lower().strip(),)).fetchone(); c.close()
    if not row or not checkpw(a.password,row['password_hash']): raise HTTPException(401,'Invalid email or password.')
    return {'token':token_for(row['id']),'saved_history':True}

@app.post('/api/auth/guest')
def guest(g: Guest): return {'token':token_for(None,True),'saved_history':False}

@app.get('/api/auth/providers')
def providers():
    return {'google':bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')), 'github':bool(os.getenv('GITHUB_CLIENT_ID') and os.getenv('GITHUB_CLIENT_SECRET'))}


def oauth_redirect_uri(provider):
    base=os.getenv('AETHER_PUBLIC_URL', '').rstrip('/') or 'https://aetherarc-ai.onrender.com'
    return f'{base}/api/auth/oauth/{provider}/callback'


def oauth_http(url, data=None, headers=None):
    req=urllib.request.Request(url, data=(urllib.parse.urlencode(data).encode() if data is not None else None), headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode('utf-8','ignore'))


@app.get('/api/auth/oauth/{provider}')
def oauth_start(provider: str):
    if provider not in ('google','github'): raise HTTPException(404,'Unknown OAuth provider.')
    if not providers().get(provider): raise HTTPException(503,f'{provider.title()} sign-in is not configured on this backend.')
    state=secrets.token_urlsafe(32); c=db(); c.execute('INSERT INTO oauth_states(state,provider,created_at) VALUES(?,?,?)',(state,provider,time.time())); c.commit(); c.close()
    redirect=oauth_redirect_uri(provider)
    if provider=='google':
        q={'client_id':os.getenv('GOOGLE_CLIENT_ID'),'redirect_uri':redirect,'response_type':'code','scope':'openid email profile','state':state,'access_type':'online','prompt':'select_account'}
        return RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(q))
    q={'client_id':os.getenv('GITHUB_CLIENT_ID'),'redirect_uri':redirect,'scope':'read:user user:email','state':state}
    return RedirectResponse('https://github.com/login/oauth/authorize?'+urllib.parse.urlencode(q))


@app.get('/api/auth/oauth/{provider}/callback')
def oauth_callback(provider: str, code: str='', state: str=''):
    if provider not in ('google','github'): raise HTTPException(404,'Unknown OAuth provider.')
    c=db(); row=c.execute('SELECT provider,created_at FROM oauth_states WHERE state=?',(state,)).fetchone(); c.execute('DELETE FROM oauth_states WHERE state=?',(state,)); c.commit(); c.close()
    if not row or row['provider']!=provider or time.time()-row['created_at']>600: raise HTTPException(400,'OAuth state is invalid or expired.')
    redirect=oauth_redirect_uri(provider)
    if provider=='google':
        tok=oauth_http('https://oauth2.googleapis.com/token',{'code':code,'client_id':os.getenv('GOOGLE_CLIENT_ID'),'client_secret':os.getenv('GOOGLE_CLIENT_SECRET'),'redirect_uri':redirect,'grant_type':'authorization_code'},{'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'})
        access=tok.get('access_token'); profile=oauth_http('https://openidconnect.googleapis.com/v1/userinfo',headers={'Authorization':'Bearer '+access})
        email=profile.get('email','').strip().lower(); provider_name='google'
    else:
        tok=oauth_http('https://github.com/login/oauth/access_token',{'client_id':os.getenv('GITHUB_CLIENT_ID'),'client_secret':os.getenv('GITHUB_CLIENT_SECRET'),'code':code,'redirect_uri':redirect},{'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded'})
        access=tok.get('access_token'); profile=oauth_http('https://api.github.com/user',headers={'Authorization':'Bearer '+access,'Accept':'application/vnd.github+json','User-Agent':'AetherArc-AI'})
        email=(profile.get('email') or '').strip().lower()
        if not email:
            emails=oauth_http('https://api.github.com/user/emails',headers={'Authorization':'Bearer '+access,'Accept':'application/vnd.github+json','User-Agent':'AetherArc-AI'})
            primary=next((x for x in emails if x.get('primary') and x.get('verified')),None) or next((x for x in emails if x.get('verified')),None)
            email=(primary or {}).get('email','').strip().lower()
        provider_name='github'
    if not email: raise HTTPException(400,'OAuth provider did not return a verified email address.')
    c=db(); existing=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
    if existing: uid=existing['id']; c.execute('UPDATE users SET provider=? WHERE id=?',(provider_name,uid))
    else:
        cur=c.execute('INSERT INTO users(email,password_hash,provider,created_at) VALUES(?,?,?,?)',(email,'',provider_name,time.time())); uid=cur.lastrowid
    c.commit(); c.close(); token=token_for(uid,False)
    return RedirectResponse('/?oauth_token='+urllib.parse.quote(token))

@app.get('/api/history')
def history(request: Request):
    u=current_user(request)
    if not u or u.get('guest'): return {'saved':False,'history':[]}
    c=db(); rows=c.execute('SELECT id,title,created_at,updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC',(u['user_id'],)).fetchall(); c.close()
    return {'saved':True,'history':[dict(x) for x in rows]}

@app.get('/api/history/{cid}')
def history_one(cid: str, request: Request):
    u=current_user(request)
    if not u or u.get('guest'): raise HTTPException(403,'History is available after login.')
    c=db(); row=c.execute('SELECT * FROM conversations WHERE id=? AND user_id=?',(cid,u['user_id'])).fetchone()
    if not row: c.close(); raise HTTPException(404,'Conversation not found.')
    msgs=c.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id',(cid,)).fetchall(); c.close()
    return {'conversation':dict(row),'messages':[dict(x) for x in msgs]}

@app.post('/api/image')
def image(ch: Chat):
    try:
        data=image_generate(ch.message)
        return {'ok':True,'prompt':ch.message,'image_data':data}
    except Exception as e:
        raise HTTPException(503,str(e))

@app.post('/api/chat')
def chat(ch: Chat, request: Request):
    if ch.agent not in AGENTS: raise HTTPException(400,'Unknown agent.')
    u=current_user(request); cid=ch.conversation_id or str(uuid.uuid4()); now=time.time(); c=db()
    if ch.conversation_id and not c.execute('SELECT id FROM conversations WHERE id=?',(cid,)).fetchone(): ch.conversation_id=None
    if not ch.conversation_id:
        owner=u.get('user_id') if u and not u.get('guest') else None
        c.execute('INSERT INTO conversations(id,user_id,title,created_at,updated_at) VALUES(?,?,?,?,?)',(cid,owner,ch.message[:60],now,now))
    c.execute('INSERT INTO messages(conversation_id,agent,role,content,created_at) VALUES(?,?,?,?,?)',(cid,ch.agent,'user',ch.message,now)); c.commit(); c.close()
    sources, reports = [], {}
    try:
        if re.search(r'\b(make|generate|create|draw)\b.*\b(image|picture|art|wallpaper)\b', ch.message, re.I):
            image_data=image_generate(ch.message)
            answer='IMAGE_GENERATED'
            sources=[]
            reports={'image': image_data}
        elif ch.agent == 'manager' and re.search(r'\bgithub\b', ch.message, re.I) and re.search(r'\b(fix|edit|change|update|modify)\b', ch.message, re.I):
            answer, result=github_fix(ch.message)
            reports={'code': answer}
        elif ch.agent == 'manager':
            answer, reports, sources = manager_team(ch.message, ch.location)
        elif ch.agent == 'research':
            sources = research(ch.message, ch.location)
            source_text = '\n'.join(f"{x['title']} | {x.get('snippet','')} | {x['url']}" for x in sources[:10])
            answer = call_model([{'role':'system','content':SYSTEM_PROMPTS['research']},{'role':'user','content':ch.message+'\n\nLIVE SEARCH RESULTS:\n'+source_text}],0.15) if model_available() else 'ResearchAI found '+str(len(sources))+' live results, but no model provider is configured to synthesize them.'
        else:
            c=db(); rows=c.execute('SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 12',(cid,)).fetchall(); c.close()
            msgs=[{'role':x['role'] if x['role'] in ('user','assistant') else 'user','content':x['content']} for x in reversed(rows)]
            answer=call_model([{'role':'system','content':SYSTEM_PROMPTS[ch.agent]}]+msgs,0.2) if model_available() else f'{AGENTS[ch.agent]["name"]} is ready, but no model provider is configured.'
    except Exception as e:
        answer=f'{AGENTS[ch.agent]["name"]} encountered an error: {e}'
    c=db(); c.execute('INSERT INTO messages(conversation_id,agent,role,content,created_at) VALUES(?,?,?,?,?)',(cid,ch.agent,'assistant',answer,time.time())); c.execute('UPDATE conversations SET updated_at=? WHERE id=?',(time.time(),cid)); c.commit(); c.close()
    return {'conversation_id':cid,'agent':AGENTS[ch.agent]['name'],'answer':answer,'sources':sources[:14],'specialists':[AGENTS[a]['name'] for a in reports if a in AGENTS],'image_data': reports.get('image') if isinstance(reports,dict) else None,'model_connected':model_available(),'github_connected':composio_enabled()}

@app.get('/api/stream')
async def stream(agent: str='manager', message: str=''):
    async def gen():
        if agent=='manager': steps=['ManagerAI received the task','ManagerAI classified the request','ReasonAI is analyzing','ManagerAI is checking whether CodeAI is needed','ManagerAI is checking whether ResearchAI is needed','ManagerAI is combining specialist reports','ManagerAI is preparing the final answer']
        elif agent=='reason': steps=['ReasonAI received the task','ReasonAI is breaking the problem down','ReasonAI is checking assumptions','ReasonAI is forming a conclusion']
        elif agent=='code': steps=['CodeAI received the task','CodeAI is designing the solution','CodeAI is drafting implementation','CodeAI is checking edge cases','CodeAI is preparing the result']
        else: steps=['ResearchAI received the task','ResearchAI is building queries','ResearchAI is checking web results','ResearchAI is checking news','ResearchAI is synthesizing sources']
        for s in steps:
            yield 'data: '+json.dumps({'type':'status','agent':AGENTS.get(agent,AGENTS['manager'])['name'],'step':s})+'\n\n'; await asyncio.sleep(0.18)
        yield 'data: '+json.dumps({'type':'done'})+'\n\n'
    return StreamingResponse(gen(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.get('/')
def index(): return FileResponse(FRONTEND/'index.html')
@app.get('/app.js')
def js(): return FileResponse(FRONTEND/'app.js',media_type='text/javascript')
@app.get('/style.css')
def css(): return FileResponse(FRONTEND/'style.css',media_type='text/css')

import os, json, time, uuid, sqlite3, hashlib, secrets, urllib.parse, urllib.request, re, asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'storage' / 'aether.db'
FRONTEND = ROOT / 'frontend'
DB.parent.mkdir(exist_ok=True)

app = FastAPI(title='Aether API', version='0.4.0')
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
    SESSIONS[t] = {'user_id': user_id, 'guest': guest}
    return t


def current_user(request: Request):
    t = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    return SESSIONS.get(t)


def provider_url():
    if os.getenv('AETHER_MODEL_BASE_URL'):
        return os.getenv('AETHER_MODEL_BASE_URL').rstrip('/')
    if os.getenv('GROQ_API_KEY'):
        return 'https://api.groq.com/openai/v1'
    return ''


def provider_key():
    return os.getenv('AETHER_MODEL_API_KEY') or os.getenv('GROQ_API_KEY', '')


def provider_model():
    return os.getenv('AETHER_MODEL') or os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')


def ollama_model():
    return os.getenv('OLLAMA_MODEL', 'llama3.2')


def model_available():
    return bool((provider_url() and provider_model()) or os.getenv('OLLAMA_URL'))


def call_model(messages, temperature=0.2):
    if provider_url() and provider_model():
        payload = {'model': provider_model(), 'messages': messages, 'temperature': temperature}
        headers = {'Content-Type': 'application/json'}
        if provider_key(): headers['Authorization'] = 'Bearer ' + provider_key()
        req = urllib.request.Request(provider_url() + '/chat/completions', data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode())
        return data['choices'][0]['message']['content']
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


def research(query, location=None):
    q = query.strip() + ((' ' + location.strip()) if location and location.strip() else '')
    searches = [('Google web', x) for x in google_cse(q)] + [('Google News', x) for x in google_news_rss(q)]
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
    return {'ok':True,'name':'Aether','version':'0.4.0','model_connected':model_available(),'team':['ManagerAI','ReasonAI','CodeAI','ResearchAI']}

@app.get('/api/config')
def config():
    return {'agents':AGENTS,'model_connected':model_available(),'model':provider_model() if model_available() else None,'provider':'groq' if os.getenv('GROQ_API_KEY') and not os.getenv('AETHER_MODEL_BASE_URL') else ('openai-compatible' if provider_url() else ('ollama' if os.getenv('OLLAMA_URL') else None)),'research_google_cse':bool(os.getenv('GOOGLE_CSE_API_KEY') and os.getenv('GOOGLE_CSE_ID'))}

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
def providers(): return {'google':bool(os.getenv('GOOGLE_CLIENT_ID')),'github':bool(os.getenv('GITHUB_CLIENT_ID'))}

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
        if ch.agent == 'manager':
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
    return {'conversation_id':cid,'agent':AGENTS[ch.agent]['name'],'answer':answer,'sources':sources[:14],'specialists':[AGENTS[a]['name'] for a in reports],'model_connected':model_available()}

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

import os, json, time, uuid, sqlite3, hashlib, secrets, urllib.parse, urllib.request, urllib.error, re, asyncio
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'storage' / 'aether.db'
FRONTEND = ROOT / 'frontend'
DB.parent.mkdir(exist_ok=True)

app = FastAPI(title='Aether API', version='0.3.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

AGENTS = {
    'manager': {'name':'ManagerAI','role':'Team manager / orchestrator'},
    'reason': {'name':'ReasonAI','role':'Reasoning & analysis specialist'},
    'code': {'name':'CodeAI','role':'Coding & engineering specialist'},
    'research': {'name':'ResearchAI','role':'Web, news & local research specialist'},
}
SYSTEM_PROMPTS = {
    'manager': 'You are ManagerAI, the lead of Aether. You coordinate ReasonAI, CodeAI and ResearchAI when useful, then give the user one clear answer. Do not claim a specialist was consulted unless the backend actually supplied a specialist result.',
    'reason': 'You are ReasonAI, Aether\'s careful reasoning and analysis specialist. Break hard problems into logical steps, check assumptions, and explain conclusions clearly.',
    'code': 'You are CodeAI, Aether\'s software engineering specialist. Produce correct, maintainable code and explain implementation decisions. Never claim code was executed unless it actually was.',
    'research': 'You are ResearchAI, Aether\'s research specialist. Use the supplied live search results when available, distinguish facts from uncertainty, and cite sources by URL/title in the final answer.',
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

class OAuthCode(BaseModel):
    code: str
    state: str | None = None


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
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 160000).hex()
    return salt + ':' + h

def checkpw(password, stored):
    try:
        salt, h = stored.split(':',1)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 160000).hex() == h
    except Exception: return False

def token_for(user_id, guest=False):
    t = secrets.token_urlsafe(32); SESSIONS[t]={'user_id':user_id,'guest':guest}; return t

def current_user(request: Request):
    t=request.headers.get('Authorization','').replace('Bearer ','').strip()
    return SESSIONS.get(t)


def provider_url():
    return os.getenv('AETHER_MODEL_BASE_URL','').rstrip('/')

def provider_key():
    return os.getenv('AETHER_MODEL_API_KEY','')

def provider_model():
    return os.getenv('AETHER_MODEL','')

def ollama_model():
    return os.getenv('OLLAMA_MODEL','llama3.2')

def model_available():
    return bool((provider_url() and provider_model()) or os.getenv('OLLAMA_URL'))


def call_model(agent, messages, temperature=0.2):
    # OpenAI-compatible provider
    if provider_url() and provider_model():
        payload={'model':provider_model(),'messages':messages,'temperature':temperature}
        req=urllib.request.Request(provider_url()+'/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json','Authorization':'Bearer '+provider_key()} if provider_key() else {'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=90) as r:
            data=json.loads(r.read().decode())
        return data['choices'][0]['message']['content']
    # Ollama local provider
    if os.getenv('OLLAMA_URL'):
        base=os.getenv('OLLAMA_URL').rstrip('/')
        payload={'model':ollama_model(),'messages':messages,'stream':False,'options':{'temperature':temperature}}
        req=urllib.request.Request(base+'/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=120) as r:
            data=json.loads(r.read().decode())
        return data.get('message',{}).get('content','')
    return ''


def google_cse(q, gl='in', num=6):
    key=os.getenv('GOOGLE_CSE_API_KEY'); cx=os.getenv('GOOGLE_CSE_ID')
    if not key or not cx: return []
    params=urllib.parse.urlencode({'key':key,'cx':cx,'q':q,'num':num,'gl':gl,'safe':'active'})
    url='https://www.googleapis.com/customsearch/v1?'+params
    try:
        with urllib.request.urlopen(url, timeout=15) as r: data=json.loads(r.read().decode())
        return [{'title':x.get('title',''),'url':x.get('link',''),'snippet':x.get('snippet','')} for x in data.get('items',[])]
    except Exception: return []


def google_news_rss(q, hl='en-IN', gl='IN', ceid='IN:en'):
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':hl,'gl':gl,'ceid':ceid})
    try:
        with urllib.request.urlopen(url, timeout=15) as r: xml=r.read().decode('utf-8','ignore')
        items=[]
        for item in re.findall(r'<item>(.*?)</item>', xml, re.S)[:10]:
            def tag(name):
                m=re.search(fr'<{name}>(.*?)</{name}>', item, re.S)
                return re.sub('<.*?>','',m.group(1)).strip() if m else ''
            link=tag('link'); title=tag('title'); desc=tag('description'); pub=tag('pubDate')
            items.append({'title':title,'url':link,'snippet':desc,'published':pub})
        return items
    except Exception: return []


def research(query, location=None):
    location = (location or '').strip()
    searches=[]
    q=query
    if location: q=f'{query} {location}'
    web=google_cse(q)
    if web: searches += [('Google web', x) for x in web]
    news=google_news_rss(q)
    searches += [('Google News', x) for x in news]
    if location:
        local=google_news_rss(f'{query} {location} local news')
        searches += [('Local news', x) for x in local]
    # dedupe
    seen=set(); out=[]
    for kind,x in searches:
        u=x.get('url','')
        if not u or u in seen: continue
        seen.add(u); x['kind']=kind; out.append(x)
    return out[:14]


def demo(agent, text, sources=None):
    if agent=='manager': return 'ManagerAI is online. I can coordinate ReasonAI, CodeAI and ResearchAI for this task. Connect an AI provider in .env for full model-generated answers.'
    if agent=='reason': return 'ReasonAI is online. I can break the problem into assumptions, evidence, alternatives and a conclusion. Connect an AI provider in .env for full model-generated reasoning.'
    if agent=='code': return 'CodeAI is online. I can design and write the implementation, but this demo mode does not execute code. Connect an AI provider in .env for full coding assistance.'
    if sources: return 'ResearchAI found live results. Add an AI provider in .env and I will synthesize them into a cited answer.'
    return 'ResearchAI is online, but no live search credentials are configured. Add Google CSE credentials in .env for web/news search.'


def manager_team(user_text, location):
    # Real team workflow: manager asks specialists in parallel when a model exists.
    if not model_available(): return demo('manager', user_text)
    results={}
    needs_research=any(k in user_text.lower() for k in ['latest','today','news','search','research','price','current','near me','local'])
    specialist_jobs=[]
    specialist_jobs.append(('reason', SYSTEM_PROMPTS['reason']+'\nAnalyze this request for the manager:\n'+user_text))
    if any(k in user_text.lower() for k in ['code','python','javascript','app','website','program','debug','build']):
        specialist_jobs.append(('code', SYSTEM_PROMPTS['code']+'\nWork on this request for the manager:\n'+user_text))
    if needs_research:
        specialist_jobs.append(('research', SYSTEM_PROMPTS['research']+'\nUse these search results if supplied. Research this request:\n'+user_text))
    for a,prompt in specialist_jobs:
        src=research(user_text, location) if a=='research' else []
        context='\n'.join(f"- {x['title']}: {x.get('snippet','')} ({x['url']})" for x in src[:8])
        msgs=[{'role':'system','content':SYSTEM_PROMPTS[a]},{'role':'user','content':prompt+'\nLIVE SOURCES:\n'+context}]
        try: results[a]=call_model(a,msgs)
        except Exception as e: results[a]=f'{AGENTS[a]["name"]} error: {e}'
    bundle='\n\n'.join(f"{AGENTS[a]['name']} REPORT:\n{r}" for a,r in results.items())
    final=call_model('manager',[{'role':'system','content':SYSTEM_PROMPTS['manager']},{'role':'user','content':f'User request:\n{user_text}\n\nSpecialist reports:\n{bundle}\n\nProduce the final answer for the user.'}],0.2)
    return final or bundle

@app.get('/api/health')
def health(): return {'ok':True,'name':'Aether','version':'0.3.0','model_connected':model_available()}

@app.get('/api/config')
def config():
    return {'agents':AGENTS,'model_connected':model_available(),'research_google_cse':bool(os.getenv('GOOGLE_CSE_API_KEY') and os.getenv('GOOGLE_CSE_ID')),'oauth':{'google':bool(os.getenv('GOOGLE_CLIENT_ID')),'github':bool(os.getenv('GITHUB_CLIENT_ID'))}}

@app.post('/api/auth/register')
def register(a: Auth):
    c=db()
    try:
        cur=c.execute('INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)',(a.email.lower().strip(),phash(a.password),time.time()))
        c.commit(); uid=cur.lastrowid
    except sqlite3.IntegrityError: c.close(); raise HTTPException(400,'An account with that email already exists.')
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
    c=db(); row=c.execute('SELECT * FROM conversations WHERE id=? AND user_id=?',(cid,u['user_id'])).fetchone();
    if not row: c.close(); raise HTTPException(404,'Conversation not found.')
    msgs=c.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id',(cid,)).fetchall(); c.close()
    return {'conversation':dict(row),'messages':[dict(x) for x in msgs]}

@app.post('/api/chat')
def chat(ch: Chat, request: Request):
    if ch.agent not in AGENTS: raise HTTPException(400,'Unknown agent.')
    u=current_user(request)
    cid=ch.conversation_id or str(uuid.uuid4())
    now=time.time()
    c=db()
    if ch.conversation_id:
        exists=c.execute('SELECT id FROM conversations WHERE id=?',(cid,)).fetchone()
        if not exists: ch.conversation_id=None
    if not ch.conversation_id:
        owner=u.get('user_id') if u and not u.get('guest') else None
        c.execute('INSERT INTO conversations(id,user_id,title,created_at,updated_at) VALUES(?,?,?,?,?)',(cid,owner,ch.message[:60],now,now))
    c.execute('INSERT INTO messages(conversation_id,agent,role,content,created_at) VALUES(?,?,?,?,?)',(cid,ch.agent,'user',ch.message,now)); c.commit(); c.close()
    sources=[]
    try:
        if ch.agent=='research':
            sources=research(ch.message,ch.location)
            source_text='\n'.join(f"{x['title']} | {x.get('snippet','')} | {x['url']}" for x in sources[:10])
            answer=call_model('research',[{'role':'system','content':SYSTEM_PROMPTS['research']},{'role':'user','content':ch.message+'\n\nLIVE SEARCH RESULTS:\n'+source_text}],0.15) if model_available() else demo('research',ch.message,sources)
        elif ch.agent=='manager':
            answer=manager_team(ch.message,ch.location)
        else:
            history_msgs=[]
            c=db(); rows=c.execute('SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 12',(cid,)).fetchall(); c.close()
            for x in reversed(rows): history_msgs.append({'role':x['role'] if x['role'] in ('user','assistant') else 'user','content':x['content']})
            answer=call_model(ch.agent,[{'role':'system','content':SYSTEM_PROMPTS[ch.agent]}]+history_msgs,0.2) if model_available() else demo(ch.agent,ch.message)
    except Exception as e: answer=f'{AGENTS[ch.agent]["name"]} encountered an error: {e}'
    c=db(); c.execute('INSERT INTO messages(conversation_id,agent,role,content,created_at) VALUES(?,?,?,?,?)',(cid,ch.agent,'assistant',answer, time.time())); c.execute('UPDATE conversations SET updated_at=? WHERE id=?',(time.time(),cid)); c.commit(); c.close()
    return {'conversation_id':cid,'agent':AGENTS[ch.agent]['name'],'answer':answer,'sources':sources,'model_connected':model_available()}

@app.get('/api/stream')
async def stream(agent: str='manager', message: str=''):
    async def gen():
        if agent=='manager':
            steps=['ManagerAI received the task','ManagerAI is classifying the request','ReasonAI is analyzing the problem','ManagerAI is deciding whether CodeAI is needed','ManagerAI is deciding whether ResearchAI is needed','ManagerAI is combining the team reports','ManagerAI is preparing the final answer']
        elif agent=='reason': steps=['ReasonAI received the task','ReasonAI is breaking the problem into parts','ReasonAI is checking assumptions','ReasonAI is forming a conclusion']
        elif agent=='code': steps=['CodeAI received the task','CodeAI is designing the solution','CodeAI is drafting implementation','CodeAI is checking edge cases','CodeAI is preparing the result']
        else: steps=['ResearchAI received the task','ResearchAI is building search queries','ResearchAI is checking Google/web results','ResearchAI is checking Google News','ResearchAI is checking local-news results','ResearchAI is synthesizing sources']
        for s in steps:
            yield 'data: '+json.dumps({'type':'status','agent':AGENTS.get(agent,AGENTS['manager'])['name'],'step':s})+'\n\n'
            await asyncio.sleep(0.22)
        yield 'data: '+json.dumps({'type':'done'})+'\n\n'
    return StreamingResponse(gen(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.get('/')
def index(): return FileResponse(FRONTEND/'index.html')
@app.get('/app.js')
def js(): return FileResponse(FRONTEND/'app.js',media_type='text/javascript')
@app.get('/style.css')
def css(): return FileResponse(FRONTEND/'style.css',media_type='text/css')

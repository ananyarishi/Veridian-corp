from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from .config import settings
from .database import connect_db, close_db, get_db
from .security import create_access_token, get_current_user, hash_password, verify_password
from .schemas import LoginRequest, NewRequest, ReviewRequest, CommentRequest, PolicyCreate
from .seed_data import POLICIES, REQUESTS, TICKETS
from .agent import analyze_request
from fastapi.encoders import jsonable_encoder

def now_iso(): return datetime.now(timezone.utc).isoformat()
def clean(doc):
    if not doc: return doc
    doc.pop("_id",None)
    return doc

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await connect_db()
        if settings.seed_on_start:
            await seed_database()
        app.state.db_ready=True
    except Exception as exc:
        app.state.db_ready=False
        print(f"[startup] MongoDB unavailable: {exc}")
    yield
    await close_db()

app=FastAPI(title="Veridian Corp IT Service Agent API",version="1.0.0",description="JWT-secured IT triage, policy, reviewer decision, and audit APIs.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

async def seed_database():
    db=get_db()
    if await db.users.count_documents({})==0:
        await db.users.insert_one({"username":settings.demo_admin_username,"display_name":"IT Admin","role":"reviewer","email":"admin@veridiancorp.com","password_hash":hash_password(settings.demo_admin_password),"is_active":True,"created_at":now_iso()})
    if await db.policies.count_documents({})==0:
        await db.policies.insert_many([{**p,"created_at":now_iso(),"updated_at":now_iso()} for p in POLICIES])
    if await db.requests.count_documents({})==0:
        docs=[]
        for r in REQUESTS:
            docs.append({**r,"summary":r["message"][:75]+("…" if len(r["message"])>75 else ""),"category":"Unclassified","action":"Flag for Review","confidence":0.0,"reasoning":"Awaiting AI analysis.","matched_policy":[],"status":"Pending Review","created_at":now_iso(),"updated_at":now_iso(),"review_history":[],"comments":[]})
        await db.requests.insert_many(docs)
    if await db.tickets.count_documents({})==0:
        await db.tickets.insert_many([{**t,"created_at":now_iso()} for t in TICKETS])

@app.get("/")
async def root(): return {"name":"Veridian Corp IT Service Agent API","docs":"/docs","health":"/api/health"}
@app.get("/api/health")
async def health():
    try:
        db=get_db(); await db.command("ping")
        return {"status":"ok","database":"connected","ai_provider":"openai" if settings.openai_api_key else "policy-grounded fallback"}
    except Exception:
        return {"status":"degraded","database":"disconnected","detail":"Start MongoDB and check MONGODB_URI."}

@app.post("/api/auth/login")
async def login(body: LoginRequest):
    db=get_db()
    user=await db.users.find_one({"username":body.username})
    if not user or not user.get("is_active",True) or not verify_password(body.password,user["password_hash"]):
        raise HTTPException(status_code=401,detail="Incorrect username or password")
    token=create_access_token(user["username"])
    await db.audit.insert_one({"timestamp":now_iso(),"request_id":None,"employee":None,"action":"Login","taken_by":user["username"],"details":"Successful reviewer login","confidence":None,"result":"Success"})
    return {"access_token":token,"token_type":"bearer","user":{"username":user["username"],"display_name":user.get("display_name"),"role":user.get("role")}}

@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)): return user

@app.get("/api/requests")
async def list_requests(q: Optional[str]=None, action: Optional[str]=None, status: Optional[str]=None, limit:int=Query(100,ge=1,le=500), user=Depends(get_current_user)):
    db=get_db(); query={}
    if action: query["action"]=action
    if status: query["status"]=status
    if q: query["$or"]=[{"id":{"$regex":q,"$options":"i"}},{"employee":{"$regex":q,"$options":"i"}},{"message":{"$regex":q,"$options":"i"}}]
    docs=await db.requests.find(query,{"_id":0}).sort("date_opened",1).to_list(limit)
    return {"items":docs,"total":len(docs)}

@app.post("/api/requests", status_code=201)
async def create_request(body: NewRequest, user=Depends(get_current_user)):
    """Create an employee IT request, run policy analysis, and record an audit trail."""
    db = get_db()
    now = now_iso()
    # Generate the next REQ number from stored IDs so newly submitted requests persist across restarts.
    existing_ids = await db.requests.find({"id": {"$regex": r"^REQ-\d+$"}}, {"id": 1, "_id": 0}).to_list(10000)
    numbers = [int(item["id"].split("-")[1]) for item in existing_ids if item.get("id", "").split("-")[-1].isdigit()]
    request_id = f"REQ-{max(numbers, default=0) + 1:02d}"
    req = {
        "id": request_id,
        "employee": body.employee.strip(),
        "email": body.email.strip(),
        "message": body.message.strip(),
        "summary": body.message.strip()[:75] + ("…" if len(body.message.strip()) > 75 else ""),
        "date_opened": datetime.now(timezone.utc).date().isoformat(),
        "category": "Unclassified",
        "action": "Flag for Review",
        "confidence": 0.0,
        "reasoning": "Request submitted; awaiting policy analysis.",
        "matched_policy": [],
        "needs_human_review": True,
        "status": "Pending Review",
        "created_at": now,
        "updated_at": now,
        "created_by": user["username"],
        "review_history": [],
        "comments": [],
    }
    await db.requests.insert_one(req)
    await db.audit.insert_one({"timestamp": now, "request_id": request_id, "employee": req["employee"], "action": "Request Submitted", "taken_by": user["username"], "details": "New IT request submitted through the Requests page.", "result": "Created"})
    policies = await db.policies.find({}, {"_id": 0}).to_list(100)
    result = await analyze_request(req, policies)
    updated = {
        "category": result.get("category", "General IT Request"),
        "action": result["action"],
        "confidence": result["confidence"],
        "reasoning": result["reasoning"],
        "matched_policy": result.get("matched_policy", []),
        "needs_human_review": result.get("needs_human_review", False),
        "ai_provider": result.get("provider", "unknown"),
        "updated_at": now_iso(),
    }
    await db.requests.update_one({"id": request_id}, {"$set": updated})
    await db.audit.insert_one({"timestamp": now_iso(), "request_id": request_id, "employee": req["employee"], "action": "AI Analysis", "taken_by": "AI Agent", "details": result["reasoning"], "confidence": result["confidence"], "result": result["action"], "provider": result.get("provider")})
    return clean({**req, **updated})

@app.get("/api/requests/{request_id}")
async def get_request(request_id:str,user=Depends(get_current_user)):
    doc=await get_db().requests.find_one({"id":request_id},{"_id":0})
    if not doc: raise HTTPException(404,"Request not found")
    return doc

@app.post("/api/requests/{request_id}/analyze")
async def analyze(request_id:str, user=Depends(get_current_user)):
    db=get_db(); req=await db.requests.find_one({"id":request_id},{"_id":0})
    if not req: raise HTTPException(404,"Request not found")
    policies=await db.policies.find({},{"_id":0}).to_list(100)
    result=await analyze_request(req,policies)
    updated={"category":result.get("category","General IT Request"),"action":result["action"],"confidence":result["confidence"],"reasoning":result["reasoning"],"matched_policy":result.get("matched_policy",[]),"needs_human_review":result.get("needs_human_review",False),"ai_provider":result.get("provider","unknown"),"updated_at":now_iso()}
    await db.requests.update_one({"id":request_id},{"$set":updated})
    await db.audit.insert_one({"timestamp":now_iso(),"request_id":request_id,"employee":req.get("employee"),"action":"AI Analysis","taken_by":"AI Agent","details":result["reasoning"],"confidence":result["confidence"],"result":result["action"],"provider":result.get("provider")})
    return {**req,**updated}

@app.post("/api/requests/{request_id}/review")
async def review_request(request_id:str, body:ReviewRequest, user=Depends(get_current_user)):
    db=get_db(); req=await db.requests.find_one({"id":request_id},{"_id":0})
    if not req: raise HTTPException(404,"Request not found")
    if body.decision=="Auto-Resolve": status_value="Resolved"
    elif body.decision=="Route to Team": status_value="In Progress"
    else: status_value="Pending Review"
    event={"timestamp":now_iso(),"reviewer":user["username"],"decision":body.decision,"note":body.note,"assigned_team":body.assigned_team}
    await db.requests.update_one({"id":request_id},{"$set":{"action":body.decision,"status":status_value,"updated_at":now_iso(),"assigned_team":body.assigned_team},"$push":{"review_history":event}})
    await db.audit.insert_one({"timestamp":now_iso(),"request_id":request_id,"employee":req.get("employee"),"action":"Reviewer Decision","taken_by":user["username"],"details":body.note or f"Reviewer selected {body.decision}","confidence":req.get("confidence"),"result":status_value,"assigned_team":body.assigned_team})
    return {"ok":True,"request_id":request_id,"action":body.decision,"status":status_value,"review_event":event}

@app.post("/api/requests/{request_id}/comments")
async def add_comment(request_id:str, body:CommentRequest, user=Depends(get_current_user)):
    db=get_db()
    if not await db.requests.find_one({"id":request_id}): raise HTTPException(404,"Request not found")
    comment={"comment":body.comment,"by":user["username"],"timestamp":now_iso()}
    await db.requests.update_one({"id":request_id},{"$push":{"comments":comment},"$set":{"updated_at":now_iso()}})
    await db.audit.insert_one({"timestamp":now_iso(),"request_id":request_id,"action":"Comment Added","taken_by":user["username"],"details":body.comment,"result":"Recorded"})
    return {"ok":True,"comment":comment}

@app.get("/api/tickets")
async def list_tickets(q:Optional[str]=None, user=Depends(get_current_user)):
    db=get_db(); query={}
    if q: query={"$or":[{"id":{"$regex":q,"$options":"i"}},{"employee":{"$regex":q,"$options":"i"}},{"issue":{"$regex":q,"$options":"i"}}]}
    docs=await db.tickets.find(query,{"_id":0}).to_list(100)
    return {"items":docs,"total":len(docs)}

@app.get("/api/policies")
async def list_policies(q:Optional[str]=None, category:Optional[str]=None, user=Depends(get_current_user)):
    query={}
    if category: query["category"]=category
    if q: query["$or"]=[{"id":{"$regex":q,"$options":"i"}},{"title":{"$regex":q,"$options":"i"}},{"body":{"$regex":q,"$options":"i"}}]
    docs=await get_db().policies.find(query,{"_id":0}).to_list(100)
    return {"items":docs,"total":len(docs)}

@app.post("/api/policies")
async def create_policy(body:PolicyCreate,user=Depends(get_current_user)):
    if user.get("role")!="reviewer": raise HTTPException(403,"Reviewer role required")
    db=get_db()
    if await db.policies.find_one({"id":body.id}): raise HTTPException(409,"Policy ID already exists")
    doc={**body.model_dump(),"created_at":now_iso(),"updated_at":now_iso(),"created_by":user["username"]}
    await db.policies.insert_one(doc)
    await db.audit.insert_one({"timestamp":now_iso(),"action":"Policy Created","taken_by":user["username"],"details":f"Created {body.id}: {body.title}","result":"Recorded"})
    return {**doc}

@app.get("/api/audit")
async def list_audit(q:Optional[str]=None, action:Optional[str]=None, result:Optional[str]=None, limit:int=Query(200,ge=1,le=1000), user=Depends(get_current_user)):
    query={}
    if action: query["action"]=action
    if result: query["result"]=result
    if q: query["$or"]=[{"request_id":{"$regex":q,"$options":"i"}},{"employee":{"$regex":q,"$options":"i"}},{"details":{"$regex":q,"$options":"i"}},{"taken_by":{"$regex":q,"$options":"i"}}]
    docs=await get_db().audit.find(query,{"_id":0}).sort("timestamp",-1).to_list(limit)
    return {"items":docs,"total":len(docs)}

@app.get("/api/dashboard/summary")
async def dashboard_summary(user=Depends(get_current_user)):
    db=get_db()
    total=await db.requests.count_documents({})
    auto=await db.requests.count_documents({"action":"Auto-Resolve"})
    routed=await db.requests.count_documents({"action":"Route to Team"})
    flagged=await db.requests.count_documents({"action":"Flag for Review"})
    tickets=await db.tickets.count_documents({})
    policies=await db.policies.count_documents({})
    return {"total_requests":total,"auto_resolved":auto,"routed_to_team":routed,"flagged_for_review":flagged,"tickets":tickets,"policies":policies,"audit_events":await db.audit.count_documents({})}

@app.get("/api/audit/export")
async def export_audit(user=Depends(get_current_user)):
    from fastapi.responses import StreamingResponse
    import csv, io
    docs=await get_db().audit.find({},{"_id":0}).sort("timestamp",-1).to_list(1000)
    out=io.StringIO(); fields=["timestamp","request_id","employee","action","taken_by","details","confidence","result"]
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction="ignore"); writer.writeheader(); writer.writerows(docs)
    from fastapi.responses import Response
    return Response(out.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=veridian-audit-log.csv"})

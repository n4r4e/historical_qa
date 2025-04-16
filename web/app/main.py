from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import os
from app.qa_system import HistoricalKnowledgeGraphQA
from app.config import Settings

# Load settings
settings = Settings()

# Initialize FastAPI application
app = FastAPI(title="Knowledge Graph QA System")

# Configure static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize QA system (loaded only once at app startup)
qa_system = HistoricalKnowledgeGraphQA()

# Request/Response models
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str

# Root path - Display web interface
@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API endpoint - Process questions
@app.post("/api/query", response_model=QueryResponse)
async def process_query(query_req: QueryRequest):
    try:
        answer = qa_system.process_query(query_req.question)
        return QueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    
# Form submission handler (for direct HTML form submissions)
@app.post("/submit-query", response_class=HTMLResponse)
async def submit_query(request: Request, question: str = Form(...)):
    try:
        answer = qa_system.process_query(question)
        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "question": question, "answer": answer}
        )
    except Exception as e:
        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "question": question, "error": str(e)}
        )

    
if __name__ == "__main__":
    # Run development server
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
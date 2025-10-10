from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_l1_page(request: Request):
    return templates.TemplateResponse("L1_index.html", {"request": request})

@router.get("/dashboard-l2", response_class=HTMLResponse)
async def dashboard_l2_page(request: Request):
    return templates.TemplateResponse("L2_index.html", {"request": request})

@router.get("/add-cloth", response_class=HTMLResponse)
async def add_cloth_page(request: Request):
    return templates.TemplateResponse("L1_addCloth.html", {"request": request})

@router.get("/add-design", response_class=HTMLResponse)
async def add_design_page(request: Request):
    return templates.TemplateResponse("L1_addDesign.html", {"request": request})

@router.get("/L2_cloth.html", response_class=HTMLResponse)
async def l2_cloth_page(request: Request):
    return templates.TemplateResponse("L2_cloth.html", {"request": request})

@router.get("/L2_design.html", response_class=HTMLResponse)
async def l2_design_page(request: Request):
    return templates.TemplateResponse("L2_design.html", {"request": request})
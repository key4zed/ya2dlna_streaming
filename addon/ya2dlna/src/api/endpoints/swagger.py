"""
Swagger/OpenAPI эндпоинт для предоставления спецификации API в YAML формате.
"""
import yaml
from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter(tags=["swagger"])


@router.get("/openapi.yaml", include_in_schema=False)
async def get_openapi_yaml(request: Request):
    """
    Возвращает OpenAPI спецификацию в YAML формате.
    
    Этот эндпоинт позволяет скачать спецификацию API в виде YAML файла,
    который можно импортировать в Swagger UI, Postman или другие инструменты.
    """
    # Получаем JSON спецификацию из приложения FastAPI
    openapi_json = request.app.openapi()
    # Конвертируем JSON в YAML
    yaml_content = yaml.dump(openapi_json, default_flow_style=False, allow_unicode=True)
    # Возвращаем ответ с правильным Content-Type
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": "attachment; filename=ya2dlna_openapi.yaml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


@router.get("/swagger", include_in_schema=False)
async def redirect_to_swagger_ui():
    """
    Перенаправляет на встроенный Swagger UI FastAPI.
    
    Этот эндпоинт предоставляет удобную ссылку для доступа к интерактивной документации API.
    """
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
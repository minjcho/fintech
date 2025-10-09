from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.openapi.utils import get_openapi
import httpx
import json
from typing import Optional, Dict, Any
import logging
import asyncio

# CSV router removed - now handled by csv-manager service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Fintech API Gateway",
    description="Unified API Gateway for AI Fintech Microservices with CSV Management",
    version="1.0.1",  # Changed version to force refresh
    docs_url="/api/ai/docs",
    redoc_url="/api/ai/redoc",
    openapi_url="/api/ai/openapi.json",
    swagger_ui_parameters={
        "docExpansion": "list",  # 'none', 'list', or 'full'
        "defaultModelsExpandDepth": 1,
        "persistAuthorization": True
    }
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "https://j13a409.p.ssafy.io",
        "https://j13a409.p.ssafy.io:3002"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSV router moved to csv-manager service

# Service endpoints
SERVICES = {
    "classifier": {
        "url": "http://classifier:8001",
        "prefix": "/api/ai/classify",
        "name": "Expense Classifier"
    },
    "analysis": {
        "url": "http://analysis:8002", 
        "prefix": "/api/ai/data",
        "name": "Data Analysis"
    },
    "csv-manager": {
        "url": "http://csv-manager:8003",
        "prefix": "/api/ai/csv",
        "name": "CSV Management"
    }
}


async def fetch_service_openapi(service_name: str, service_config: dict) -> Optional[dict]:
    """Fetch OpenAPI spec from a service with retry logic"""
    max_retries = 3
    for retry in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # Increased timeout
                response = await client.get(f"{service_config['url']}/openapi.json")
                if response.status_code == 200:
                    spec = response.json()
                    paths = spec.get('paths', {})
                    logger.info(f"Successfully fetched OpenAPI spec from {service_name} with {len(paths)} endpoints")
                    return spec
                else:
                    logger.error(f"Failed to fetch OpenAPI spec from {service_name}: Status {response.status_code}, attempt {retry + 1}/{max_retries}")
        except Exception as e:
            logger.error(f"Failed to fetch OpenAPI spec from {service_name}: {e}, attempt {retry + 1}/{max_retries}")

        if retry < max_retries - 1:
            await asyncio.sleep(2)

    return None


def update_refs_in_dict(obj: Any, service_name: str, schema_mappings: Dict[str, str]) -> Any:
    """Recursively update $ref references in a dictionary"""
    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            if key == '$ref' and isinstance(value, str):
                # Update schema reference
                if value.startswith('#/components/schemas/'):
                    schema_name = value.split('/')[-1]
                    if schema_name in schema_mappings:
                        new_obj[key] = f"#/components/schemas/{schema_mappings[schema_name]}"
                    else:
                        new_obj[key] = value
                else:
                    new_obj[key] = value
            else:
                new_obj[key] = update_refs_in_dict(value, service_name, schema_mappings)
        return new_obj
    elif isinstance(obj, list):
        return [update_refs_in_dict(item, service_name, schema_mappings) for item in obj]
    else:
        return obj


def merge_openapi_specs(gateway_spec: dict, service_specs: Dict[str, dict]) -> dict:
    """Merge multiple OpenAPI specs into one"""
    merged = gateway_spec.copy()

    # Ensure components and schemas exist
    if 'components' not in merged:
        merged['components'] = {}
    if 'schemas' not in merged['components']:
        merged['components']['schemas'] = {}
    if 'securitySchemes' not in merged['components']:
        merged['components']['securitySchemes'] = {}

    # Merge each service spec
    for service_name, spec in service_specs.items():
        if not spec:
            continue
            
        service_config = SERVICES[service_name]
        prefix = service_config['prefix']
        
        # Create schema name mappings for this service
        schema_mappings = {}
        
        # First, create schema mappings
        if 'components' in spec and 'schemas' in spec['components']:
            for schema_name in spec['components']['schemas'].keys():
                # Create prefixed name
                prefixed_name = f"{service_name}_{schema_name}"
                schema_mappings[schema_name] = prefixed_name
        
        # Then merge schemas with updated references
        if 'components' in spec and 'schemas' in spec['components']:
            for schema_name, schema in spec['components']['schemas'].items():
                prefixed_name = schema_mappings[schema_name]
                # Update any $ref inside the schema itself
                updated_schema = update_refs_in_dict(schema, service_name, schema_mappings)
                merged['components']['schemas'][prefixed_name] = updated_schema

        # Merge security schemes from services
        if 'components' in spec and 'securitySchemes' in spec['components']:
            for scheme_name, scheme in spec['components']['securitySchemes'].items():
                # Add security scheme (HTTPBearer for JWT)
                if scheme_name not in merged['components']['securitySchemes']:
                    merged['components']['securitySchemes'][scheme_name] = scheme
        
        # Then merge paths with updated references
        if 'paths' in spec:
            for path, path_item in spec['paths'].items():
                # Skip root and health endpoints from services
                if path in ['/', '/health', '/openapi.json', '/docs', '/redoc']:
                    continue
                    
                # Adjust the path to include service prefix if not already present
                if not path.startswith(prefix):
                    if path.startswith('/api/ai/'):
                        # Path already has /api/ai/ prefix, use as is
                        new_path = path
                    elif path.startswith('/ai/'):
                        # Convert /ai/ to /api/ai/
                        new_path = path.replace('/ai/', '/api/ai/', 1)
                    else:
                        # Add the service prefix
                        new_path = f"{prefix}{path}"
                else:
                    new_path = path
                
                # Update the entire path_item with new references
                updated_path_item = update_refs_in_dict(path_item, service_name, schema_mappings)
                
                # Update operation IDs and tags
                for method, operation in updated_path_item.items():
                    if isinstance(operation, dict):
                        # Add service tag
                        operation['tags'] = [service_config['name']]
                        # Update operation ID to avoid conflicts
                        if 'operationId' in operation:
                            operation['operationId'] = f"{service_name}_{operation['operationId']}"
                        # Update summary to include service name
                        if 'summary' in operation:
                            operation['summary'] = f"[{service_config['name']}] {operation['summary']}"
                        # Preserve security requirements from original spec
                        # This ensures endpoints that require auth maintain their security settings
                
                merged['paths'][new_path] = updated_path_item
    
    # Add tags description - must match exactly with operation tags
    merged['tags'] = [
        {"name": "Gateway", "description": "API Gateway endpoints"},
        {"name": "CSV Management", "description": "CSV file upload and management endpoints"},
        {"name": "Expense Classifier", "description": "Expense classification endpoints"},
        {"name": "Data Analysis", "description": "Data analysis endpoints"}
    ]
    
    return merged


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root to /api/ai"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/ai", status_code=307)


@app.get("/api/ai", tags=["Gateway"])
async def root():
    """Root endpoint showing available services"""
    return {
        "service": "AI Fintech API Gateway",
        "version": "1.0.0",
        "services": {
            "classifier": {
                "name": SERVICES['classifier']['name'],
                "prefix": SERVICES['classifier']['prefix'],
                "docs": "/docs#tag/Expense-Classifier"
            },
            "analysis": {
                "name": SERVICES['analysis']['name'],
                "prefix": SERVICES['analysis']['prefix'],
                "docs": "/docs#tag/Data-Analysis"
            },
            "csv-manager": {
                "name": SERVICES['csv-manager']['name'],
                "prefix": SERVICES['csv-manager']['prefix'],
                "docs": "/docs#tag/CSV-Management"
            }
        },
        "documentation": {
            "swagger": "/api/ai/docs",
            "redoc": "/api/ai/redoc",
            "openapi": "/api/ai/openapi.json"
        }
    }


@app.get("/api/ai/health", tags=["Gateway"])
async def health_check():
    """Check health of all services"""
    health_status = {
        "gateway": "healthy",
        "services": {}
    }
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, service_config in SERVICES.items():
            try:
                response = await client.get(f"{service_config['url']}/health")
                health_status["services"][service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code
                }
            except Exception as e:
                health_status["services"][service_name] = {
                    "status": "unreachable",
                    "error": str(e)
                }
    
    # Set overall status
    all_healthy = all(
        s.get("status") == "healthy" 
        for s in health_status["services"].values()
    )
    
    if not all_healthy:
        health_status["gateway"] = "degraded"
    
    return health_status


@app.get("/api/ai/services", tags=["Gateway"])
async def list_services():
    """List all available services and their endpoints"""
    services_info = {}
    
    tasks = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, service_config in SERVICES.items():
            tasks[service_name] = client.get(f"{service_config['url']}/openapi.json")
        
        for service_name, task in tasks.items():
            try:
                response = await task
                if response.status_code == 200:
                    spec = response.json()
                    services_info[service_name] = {
                        "name": SERVICES[service_name]['name'],
                        "prefix": SERVICES[service_name]['prefix'],
                        "title": spec.get("info", {}).get("title", ""),
                        "version": spec.get("info", {}).get("version", ""),
                        "description": spec.get("info", {}).get("description", ""),
                        "endpoints": len(spec.get("paths", {}))
                    }
            except Exception as e:
                services_info[service_name] = {
                    "name": SERVICES[service_name]['name'],
                    "prefix": SERVICES[service_name]['prefix'],
                    "error": f"Could not fetch service info: {str(e)}"
                }
    
    return services_info


async def proxy_request(
    service: str,
    path: str,
    request: Request,
    method: str
) -> Response:
    """Proxy requests to backend services"""
    
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service '{service}' not found")
    
    service_config = SERVICES[service]
    target_url = f"{service_config['url']}/{path}"
    
    # Prepare headers (remove host header)
    headers = dict(request.headers)
    headers.pop("host", None)
    
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            # Get request body if present
            body = None
            if method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # Make the proxied request
            response = await client.request(
                method=method,
                url=target_url,
                headers=headers,
                content=body,
                params=request.query_params
            )
            
            # Return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=f"Request to {service} service timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Request error to {service}: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Service {service} is unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error proxying to {service}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal gateway error"
        )


# Proxy routes for classifier service
@app.api_route(
    "/api/ai/classify/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False  # We'll include the actual endpoints from the service
)
async def proxy_classifier(path: str, request: Request):
    return await proxy_request(
        service="classifier",
        path=f"ai/classify/{path}" if path else "ai/classify",
        request=request,
        method=request.method
    )


@app.api_route(
    "/api/ai/classify",
    methods=["GET", "POST"],
    include_in_schema=False
)
async def proxy_classifier_root(request: Request):
    return await proxy_request(
        service="classifier",
        path="ai/classify",
        request=request,
        method=request.method
    )


@app.api_route(
    "/api/ai/classify/",
    methods=["GET", "POST"],
    include_in_schema=False
)
async def proxy_classifier_root_slash(request: Request):
    return await proxy_request(
        service="classifier",
        path="ai/classify",
        request=request,
        method=request.method
    )


# Proxy routes for analysis service (data endpoints)
@app.api_route(
    "/api/ai/data/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False
)
async def proxy_data(path: str, request: Request):
    return await proxy_request(
        service="analysis",
        path=f"ai/data/{path}" if path else "ai/data",
        request=request,
        method=request.method
    )


@app.api_route(
    "/api/ai/data",
    methods=["GET", "POST"],
    include_in_schema=False
)
async def proxy_data_root(request: Request):
    return await proxy_request(
        service="analysis",
        path="ai/data",
        request=request,
        method=request.method
    )


@app.api_route(
    "/api/ai/data/",
    methods=["GET", "POST"],
    include_in_schema=False
)
async def proxy_data_root_slash(request: Request):
    return await proxy_request(
        service="analysis",
        path="ai/data",
        request=request,
        method=request.method
    )


# Proxy routes for csv-manager service
@app.api_route(
    "/api/ai/csv/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False
)
async def proxy_csv(path: str, request: Request):
    return await proxy_request(
        service="csv-manager",
        path=f"api/ai/csv/{path}" if path else "api/ai/csv",
        request=request,
        method=request.method
    )


@app.api_route(
    "/api/ai/csv",
    methods=["GET", "POST"],
    include_in_schema=False
)
async def proxy_csv_root(request: Request):
    return await proxy_request(
        service="csv-manager",
        path="api/ai/csv",
        request=request,
        method=request.method
    )


@app.api_route(
    "/api/ai/csv/",
    methods=["GET", "POST"],
    include_in_schema=False
)
async def proxy_csv_root_slash(request: Request):
    return await proxy_request(
        service="csv-manager",
        path="api/ai/csv",
        request=request,
        method=request.method
    )


# Store fetched schemas
_service_schemas_cache = {}


async def fetch_and_cache_schemas():
    """Fetch and cache service schemas on startup"""
    global _service_schemas_cache
    for service_name, service_config in SERVICES.items():
        spec = await fetch_service_openapi(service_name, service_config)
        if spec:
            _service_schemas_cache[service_name] = spec
            logger.info(f"Cached schema for {service_name}")
        else:
            logger.warning(f"Failed to fetch schema for {service_name}")


@app.on_event("startup")
async def startup_event():
    """Fetch service schemas on startup"""
    import asyncio
    # Wait a bit for services to be ready
    await asyncio.sleep(5)  # Increased wait time for services to fully initialize

    # Try multiple times to fetch schemas
    max_retries = 10  # Increased retries
    for attempt in range(max_retries):
        await fetch_and_cache_schemas()
        if len(_service_schemas_cache) == len(SERVICES):  # Check if all services cached
            logger.info(f"All service schemas fetched successfully on attempt {attempt + 1}")
            break
        else:
            missing = [s for s in SERVICES.keys() if s not in _service_schemas_cache]
            logger.warning(f"Attempt {attempt + 1}: Missing schemas for {missing}, retrying...")
            await asyncio.sleep(3)  # Increased retry delay

    # Log final status
    if _service_schemas_cache:
        logger.info(f"Cached schemas for: {list(_service_schemas_cache.keys())}")
        for service, spec in _service_schemas_cache.items():
            paths = spec.get('paths', {})
            logger.info(f"Service '{service}' has {len(paths)} endpoints")
    else:
        logger.error("Failed to fetch any service schemas after all retries")


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    # Get base gateway schema
    gateway_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Use cached schemas or fetch synchronously
    service_specs = _service_schemas_cache.copy()

    # If cache is empty or incomplete, try to fetch synchronously (fallback)
    if len(service_specs) < len(SERVICES):
        missing = [s for s in SERVICES.keys() if s not in service_specs]
        logger.warning(f"Service schemas missing for {missing}, attempting synchronous fetch...")

        # Try to fetch missing schemas synchronously
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for service_name in missing:
                service_config = SERVICES[service_name]
                spec = loop.run_until_complete(fetch_service_openapi(service_name, service_config))
                if spec:
                    service_specs[service_name] = spec
                    _service_schemas_cache[service_name] = spec
                    logger.info(f"Successfully fetched {service_name} schema synchronously")
        finally:
            loop.close()

    # Log what we have
    logger.info(f"Building OpenAPI with schemas for: {list(service_specs.keys())}")

    # Merge schemas
    merged_schema = merge_openapi_specs(gateway_schema, service_specs)

    app.openapi_schema = merged_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Add endpoint to manually refresh schemas
@app.post("/api/ai/refresh-schemas", tags=["Gateway"])
async def refresh_schemas():
    """Manually refresh service schemas"""
    global _service_schemas_cache
    app.openapi_schema = None  # Clear cache
    _service_schemas_cache.clear()  # Clear existing cache
    await fetch_and_cache_schemas()
    
    # Report which services were successfully cached
    successful = list(_service_schemas_cache.keys())
    failed = [s for s in SERVICES.keys() if s not in successful]
    
    return {
        "status": "Schemas refreshed", 
        "successful": successful,
        "failed": failed,
        "total": len(SERVICES)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
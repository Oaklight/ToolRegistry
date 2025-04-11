from toolregistry.tool_registry import ToolRegistry

spec_url = "https://raw.githubusercontent.com/APIs-guru/openapi-directory/refs/heads/main/APIs/api.gov.uk/vehicle-enquiry/1.1.0/openapi.yaml"

# Initialize the ToolRegistry and register OpenAPI tools synchronously
registry = ToolRegistry()
registry.register_openapi_tools(spec_url)

# print("Registry:", registry)

print(registry.get_available_tools())

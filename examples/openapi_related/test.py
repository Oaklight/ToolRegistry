import json
from pprint import pprint
from textwrap import indent

from toolregistry.openapi_integration import (
    get_openapi_spec,
)

# spec_file = "./openapi.yaml"

# spec = parse_openapi_spec(spec_file)
# print(json.dumps(spec, indent=2))

spec_url = "http://localhost:8000"

spec = get_openapi_spec(spec_url)
print(json.dumps(spec, indent=2))

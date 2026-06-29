import requests

# The official SPARQL endpoint for NFDI4Culture
SPARQL_ENDPOINT = "https://nfdi4culture.de/sparql"

def execute_sparql(query):
    """
    Sends a SPARQL query to the NFDI4Culture endpoint and returns the JSON results.
    """
    # Auto-inject prefixes if missing to prevent 'Undefined namespace prefix' errors
    prefixes = """
PREFIX nfdi: <https://nfdi.fiz-karlsruhe.de/ontology/>
PREFIX cto: <https://nfdi4culture.de/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <https://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""
    if "PREFIX nfdi:" not in query:
        query = prefixes + query
        
    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(
            SPARQL_ENDPOINT, 
            data={"query": query}, 
            headers=headers,
            timeout=30 # Add a timeout for the API call
        )
        
        response.raise_for_status()
        data = response.json()
        
        # Parse the standard SPARQL JSON results format
        if "results" in data and "bindings" in data["results"]:
            vars_list = data.get("head", {}).get("vars", [])
            bindings = data["results"]["bindings"]
            
            # Format the output for easier frontend rendering
            formatted_results = []
            for item in bindings:
                row = {}
                for var in vars_list:
                    if var in item:
                        row[var] = item[var]["value"]
                    else:
                        row[var] = ""
                formatted_results.append(row)
                
            return {
                "success": True,
                "columns": vars_list,
                "results": formatted_results
            }
        elif "boolean" in data:
            # Handle ASK queries
            return {
                "success": True,
                "columns": ["boolean"],
                "results": [{"boolean": str(data["boolean"])}]
            }
        else:
             return {
                 "success": False,
                 "error": "Unexpected JSON structure returned from endpoint."
             }
             
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
             error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
             
        return {
            "success": False,
            "error": error_msg
        }

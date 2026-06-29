import re
import requests
from sparql_client import execute_sparql

def extract_prefixes(query):
    """Extract prefixes from the SPARQL query to resolve namespace URLs."""
    prefixes = {}
    pattern = re.compile(r'PREFIX\s+(\w+):\s*<([^>]+)>', re.IGNORECASE)
    for match in pattern.finditer(query):
        prefixes[match.group(1)] = match.group(2)
    return prefixes

def extract_classes_and_properties(query):
    """
    Parse the SPARQL query using regex to find all classes and properties.
    """
    prefixes = extract_prefixes(query)
    
    # Extract classes: '?var a class' or '?var rdf:type class'
    class_pattern = re.compile(
        r'\?\w+\s+(?:a|rdf:type)\s+([\w\-]+:[\w\-]+|<[^>]+>)',
        re.IGNORECASE
    )
    classes = set(class_pattern.findall(query))
    
    # Extract properties: '?var property ?other' or '?var property literal'
    # Excluding 'a', 'rdf:type', 'rdfs:label'
    prop_pattern = re.compile(
        r'\?\w+\s+([\w\-]+:[\w\-]+|<[^>]+>)\s+(?:\?\w+|"[^"]*"|\d+)',
        re.IGNORECASE
    )
    all_props = prop_pattern.findall(query)
    
    properties = set()
    for p in all_props:
        p_clean = p.strip()
        p_upper = p_clean.upper()
        if p_clean != 'a' and 'RDF:TYPE' not in p_upper and 'RDFS:LABEL' not in p_upper and 'SCHEMA:NAME' not in p_upper:
            properties.add(p_clean)
            
    return list(classes), list(properties), prefixes

def run_ask_query(pattern):
    """Run a simple SPARQL ASK query to see if a pattern exists in the CKG."""
    ask_query = f"ASK {{ {pattern} }}"
    res = execute_sparql(ask_query)
    if res.get("success"):
        results = res.get("results", [])
        if results and results[0].get("boolean") == "true":
            return True
    return False

def count_instances(pattern, prefix_str=""):
    """Count occurrences of a pattern in the CKG."""
    count_query = f"{prefix_str}\nSELECT (COUNT(?s) AS ?count) WHERE {{ {pattern} }}"
    res = execute_sparql(count_query)
    if res.get("success"):
        results = res.get("results", [])
        if results:
            try:
                return int(results[0].get("count", 0))
            except ValueError:
                return 0
    return 0

def get_sample_labels_for_class(class_name, prefixes):
    """Retrieve up to 5 sample labels of instances of a given class."""
    # Define prefixes to prepended
    prefix_str = ""
    for k, v in prefixes.items():
        prefix_str += f"PREFIX {k}: <{v}>\n"
        
    query = f"""{prefix_str}
SELECT DISTINCT ?label WHERE {{
  ?s a {class_name} .
  ?s rdfs:label ?label .
}} LIMIT 5
"""
    res = execute_sparql(query)
    if res.get("success") and res.get("results"):
        return [row.get("label") for row in res["results"] if row.get("label")]
    return []

def remove_filters(query):
    """Remove FILTER clauses from a SPARQL query, correctly handling nested parentheses."""
    import re
    while True:
        match = re.search(r'FILTER\s*\(', query, re.IGNORECASE)
        if not match:
            break
        start_idx = match.start()
        open_parentheses = 1
        idx = match.end()
        while idx < len(query) and open_parentheses > 0:
            if query[idx] == '(':
                open_parentheses += 1
            elif query[idx] == ')':
                open_parentheses -= 1
            idx += 1
        query = query[:start_idx] + query[idx:]
    return query

def diagnose_empty_results(query, user_query):
    """
    Main diagnostic engine function. Analyzes why a query returned 0 results.
    """
    print(f"\n[DIAGNOSTIC] Running diagnostic checks for: '{user_query}'...")
    classes, properties, prefixes = extract_classes_and_properties(query)
    
    prefix_str = ""
    for k, v in prefixes.items():
        prefix_str += f"PREFIX {k}: <{v}>\n"
        
    diagnostics = []
    
    # 1. Check Classes
    for cls in classes:
        # Check if the class has any instances
        pattern = f"?s a {cls} ."
        cnt = count_instances(pattern, prefix_str)
        
        if cnt == 0:
            diagnostics.append({
                "type": "empty_class",
                "target": cls,
                "message": f"The class '{cls}' has 0 instances in the database. Any query using this class will return 0 results."
            })
        elif cnt < 100:
            diagnostics.append({
                "type": "sparse_class",
                "target": cls,
                "count": cnt,
                "message": f"The class '{cls}' has very few instances ({cnt} total) in the database. Data might be under-populated."
            })
            
    # 2. Check Properties
    for prop in properties:
        pattern = f"?s {prop} ?o ."
        cnt = count_instances(pattern, prefix_str)
        if cnt == 0:
            diagnostics.append({
                "type": "empty_property",
                "target": prop,
                "message": f"The property '{prop}' is never used/populated in the database."
            })
            
    # 3. Check Filters by relaxing the query
    # If classes and properties are mostly fine, check if the filters are too strict
    has_empty_class_or_prop = any(d["type"] in ["empty_class", "empty_property"] for d in diagnostics)
    
    if not has_empty_class_or_prop:
        # Attempt to relax the query: remove FILTER clauses
        relaxed_query = remove_filters(query)
        # Also clean up any trailing triple pattern anomalies
        
        if relaxed_query != query:
            relaxed_res = execute_sparql(relaxed_query)
            if relaxed_res.get("success") and len(relaxed_res.get("results", [])) > 0:
                # The query works without filters!
                # This means the query structure is 100% correct, but the specific filter terms do not match any data.
                # Let's try to extract the filter literals
                filter_literals = re.findall(r'"([^"]+)"', query)
                literals_str = ", ".join([f"'{lit}'" for lit in filter_literals])
                
                msg = f"The query structure is valid, but the search filter terms ({literals_str}) returned no matches."
                
                # Retrieve some samples from the main class
                samples = []
                for cls in classes:
                    s_labels = get_sample_labels_for_class(cls, prefixes)
                    if s_labels:
                        samples.extend(s_labels)
                        
                if samples:
                    sample_strings = [f'"{s}"' for s in samples[:4]]
                    msg += f" Here are some example terms that DO exist in the database: {', '.join(sample_strings)}."
                
                diagnostics.append({
                    "type": "strict_filter",
                    "message": msg,
                    "samples": samples[:5]
                })
                
    # 4. Synthesize human readable summary and recommendation
    if not diagnostics:
        return {
            "success": True,
            "status": "valid_structure_no_data",
            "message": "The query syntax and structure are valid, and classes/properties are populated. However, no matching data exists in the database for this specific query combination.",
            "recommendation": "Try broader search keywords or different relationships."
        }
        
    # Build recommendations
    recs = []
    status = "schema_issue"
    
    for d in diagnostics:
        recs.append(d["message"])
        if d["type"] == "strict_filter":
            status = "missing_data"
            
    # Professional solutions/workarounds based on specific failures
    if status == "schema_issue":
        # Check if the user was querying events
        if any("nfdi:NFDI_0000131" in d.get("target", "") for d in diagnostics):
            recs.append("PRO WORKAROUND: The event class `nfdi:NFDI_0000131` contains 0/sparse location data in this endpoint. We recommend querying source items (`cto:CTO_0001005`) and their related locations (`cto:CTO_0001011`) instead, which contains over 730k populated records.")
    elif status == "missing_data":
        recs.append("PRO WORKAROUND: The search term could be misspelled or missing in the Culture Knowledge Graph. You can search Wikidata or Wikipedia to check if the entity exists or use a federated query.")
        
    return {
        "success": True,
        "status": status,
        "diagnostics": diagnostics,
        "message": "\n".join(recs),
        "recommendation": recs[-1] if recs else "Try adjusting the parameters."
    }

import requests

def fetch_wikipedia_summary(wikipedia_url):
    """
    Given a Wikipedia article URL, fetch its summary extract via the Wikimedia API.
    """
    if not wikipedia_url:
        return None
    try:
        # Example URL: https://en.wikipedia.org/wiki/Johann_Sebastian_Bach
        if "/wiki/" not in wikipedia_url:
            return None
        parts = wikipedia_url.split("/wiki/")
        title = parts[-1]
        domain_part = parts[0].replace("https://", "").replace("http://", "")
        lang = domain_part.split(".")[0]
        
        api_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
        headers = {
            "User-Agent": "CKG-Explorer-Bot/1.0 (contact: hermes.challenges@uni-marburg.de)"
        }
        res = requests.get(api_url, headers=headers, timeout=5)
        res.raise_for_status()
        data = res.json()
        return data.get("extract")
    except Exception as e:
        print(f"[WIKIPEDIA ERROR] Failed to fetch summary for {wikipedia_url}: {e}")
        return None

def search_wikidata_person(name):
    """
    Search Wikidata for a person by name and return biographical info.
    Returns a dict with: qid, label, description, birthDate, deathDate, image, wikipedia_url, wikipedia_summary
    """
    # Step 1: Search for entity by name using Wikidata Search API
    search_url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "CKG-Explorer-Bot/1.0 (contact: hermes.challenges@uni-marburg.de)"
    }
    
    try:
        r = requests.get(search_url, params=params, headers=headers, timeout=5)
        r.raise_for_status()
        search_data = r.json()
        
        search_results = search_data.get("search", [])
        if not search_results:
            return None
            
        qid = search_results[0]["id"]
        label = search_results[0].get("label", name)
        description = search_results[0].get("description", "")
        
        # Step 2: Fetch details for this specific QID via SPARQL
        sparql_query = f"""
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX schema: <http://schema.org/>

        SELECT ?birthDate ?deathDate ?image ?article ?desc ?gndId ?mimoId WHERE {{
          OPTIONAL {{ wd:{qid} wdt:P569 ?birthDate . }}
          OPTIONAL {{ wd:{qid} wdt:P570 ?deathDate . }}
          OPTIONAL {{ wd:{qid} wdt:P18 ?image . }}
          OPTIONAL {{ wd:{qid} wdt:P227 ?gndId . }}
          OPTIONAL {{ wd:{qid} wdt:P3763 ?mimoId . }}
          OPTIONAL {{
            ?article schema:about wd:{qid} .
            ?article schema:inLanguage "en" .
            ?article schema:isPartOf <https://en.wikipedia.org/> .
          }}
          OPTIONAL {{
            wd:{qid} schema:description ?desc .
            FILTER(LANG(?desc) = "en")
          }}
        }} LIMIT 1
        """
        
        sparql_url = "https://query.wikidata.org/sparql"
        sparql_headers = {
            "Accept": "application/sparql-results+json",
            "User-Agent": "CKG-Explorer-Bot/1.0 (contact: hermes.challenges@uni-marburg.de)"
        }
        
        res = requests.post(sparql_url, data={"query": sparql_query}, headers=sparql_headers, timeout=5)
        res.raise_for_status()
        sparql_data = res.json()
        
        bindings = sparql_data.get("results", {}).get("bindings", [])
        
        birth_date = None
        death_date = None
        image_url = None
        wikipedia_url = None
        gnd_id = None
        mimo_id = None
        desc_val = description
        
        if bindings:
            binding = bindings[0]
            
            b_date = binding.get("birthDate", {}).get("value", "")
            if b_date:
                birth_date = b_date.split("T")[0] if "T" in b_date else b_date
                
            d_date = binding.get("deathDate", {}).get("value", "")
            if d_date:
                death_date = d_date.split("T")[0] if "T" in d_date else d_date
                
            image_url = binding.get("image", {}).get("value")
            wikipedia_url = binding.get("article", {}).get("value")
            gnd_id = binding.get("gndId", {}).get("value")
            mimo_id = binding.get("mimoId", {}).get("value")
            
            d_val = binding.get("desc", {}).get("value")
            if d_val:
                desc_val = d_val
                
        # Fetch the Wikipedia summary extract
        wikipedia_summary = fetch_wikipedia_summary(wikipedia_url)
                
        return {
            "qid": qid,
            "label": label,
            "description": desc_val,
            "birthDate": birth_date,
            "deathDate": death_date,
            "image": image_url,
            "wikipedia_url": wikipedia_url,
            "wikipedia_summary": wikipedia_summary,
            "gnd_id": gnd_id,
            "mimo_id": mimo_id
        }
        
    except Exception as e:
        print(f"[WIKIDATA ERROR] Failed to fetch data for {name}: {e}")
        return None

if __name__ == "__main__":
    print("Testing J.S. Bach...")
    import json
    print(json.dumps(search_wikidata_person("Johann Sebastian Bach"), indent=2))


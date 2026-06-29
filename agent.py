import os
import re
import requests
import google.generativeai as genai

# ==============================================================================
# Configuration
# ==============================================================================
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
MODEL_NAME = "models/gemini-2.5-flash"
SUMMARY_MODEL = "models/gemini-2.0-flash-lite"
RUN_LOCAL = os.environ.get("RUN_LOCAL", "False").lower() in ("true", "1", "yes")
LOCAL_LLM_URL = "http://localhost:11434/api/generate"
LOCAL_MODEL_NAME = "gemma"

CONFIG = {
    "google_api_key": GOOGLE_API_KEY,
    "model_name": MODEL_NAME,
    "summary_model": SUMMARY_MODEL,
    "run_local": RUN_LOCAL,
    "local_llm_url": LOCAL_LLM_URL,
    "local_model_name": LOCAL_MODEL_NAME
}

# ==============================================================================
# Initialization
# ==============================================================================
if not CONFIG["run_local"]:
    genai.configure(api_key=CONFIG["google_api_key"])

def update_config(api_key, run_local, local_url=None, local_model=None):
    """Dynamically update the LLM configuration at runtime."""
    global CONFIG
    if api_key:
        CONFIG["google_api_key"] = api_key
        if not run_local:
            genai.configure(api_key=api_key)
    CONFIG["run_local"] = run_local
    if local_url:
        CONFIG["local_llm_url"] = local_url
    if local_model:
        CONFIG["local_model_name"] = local_model
    
def load_cheat_sheet(filepath="agent_cheat_sheet.txt"):
    """Load the system instructions and schema."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "System Instruction: You are an expert musicological AI agent. Please strictly use SPARQL syntax."

SYSTEM_PROMPT = load_cheat_sheet()

def extract_sparql(text):
    """Clean the LLM output to extract the best SPARQL query.
    The LLM often outputs multiple code blocks (planning + final). 
    We find ALL blocks and pick the one that looks like a real query.
    """
    # Find ALL ```sparql ... ``` blocks
    blocks = re.findall(r'```sparql\s+(.*?)\s+```', text, re.DOTALL | re.IGNORECASE)
    
    if not blocks:
        # Try generic ``` ... ``` blocks
        blocks = re.findall(r'```\s+(.*?)\s+```', text, re.DOTALL)
    
    if blocks:
        # Pick the best block: prefer ones with SELECT/ASK/CONSTRUCT (real queries)
        for block in reversed(blocks):
            cleaned = block.strip()
            if any(kw in cleaned.upper() for kw in ['SELECT', 'ASK', 'CONSTRUCT', 'DESCRIBE']):
                return cleaned
        # If none has SELECT, return the last block
        return blocks[-1].strip()
    
    # If no blocks, just return the text assuming it is only the query
    return text.strip()

def post_process_sparql(sparql_query):
    """
    Automatically fix common LLM mistakes in SPARQL queries.
    This is a safety net that catches problems even when the LLM ignores instructions.
    """
    q = sparql_query
    
    # Skip if this is an error message, not a real SPARQL query
    if "Error" in q or "SELECT" not in q.upper():
        return q
    if "LIMIT" not in q.upper():
        q = q.rstrip().rstrip('}')  
        q += "\n} LIMIT 100" if q.count('}') < q.count('{') else "\nLIMIT 100"
    
    # Fix 2: Replace exact string matching with FILTER CONTAINS
    # Pattern: ?var rdfs:label "SomeLiteral" .
    exact_match_pattern = re.compile(
        r'(\?\w+)\s+rdfs:label\s+"([^"]+)"\s*\.', 
        re.IGNORECASE
    )
    
    for match in exact_match_pattern.finditer(q):
        var = match.group(1)
        literal = match.group(2).lower()
        label_var = var + "Label"
        old = match.group(0)
        new = f'{var} rdfs:label {label_var} .\n  FILTER(CONTAINS(LCASE(STR({label_var})), "{literal}"))'
        q = q.replace(old, new)
    
    # Fix 3: Remove `?person a nfdi:NFDI_0000004 .` constraint as it returns 0 results
    q = re.sub(r'\?\w+\s+a\s+nfdi:NFDI_0000004\s*\.?\s*\n?', '', q)
    
    return q

def call_llm(prompt, system_instruction=None, use_summary_model=False):
    """
    Unified LLM caller that routes requests to Google Gemini or Local Ollama
    based on the active CONFIG.
    """
    if CONFIG["run_local"]:
        try:
            full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            payload = {
                "model": CONFIG["local_model_name"],
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_ctx": 32000,
                    "num_predict": -1,
                    "temperature": 0.1
                }
            }
            res = requests.post(CONFIG["local_llm_url"], json=payload, timeout=30)
            res.raise_for_status()
            return res.json().get("response", "")
        except Exception as e:
            return f"Error running local model: {str(e)}"
    else:
        try:
            model_name = CONFIG["summary_model"] if use_summary_model else CONFIG["model_name"]
            if system_instruction:
                model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)
            else:
                model = genai.GenerativeModel(model_name=model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error from Google AI Studio: {str(e)}"

def generate_sparql(user_query):
    """
    Sends the user's natural language query to the LLM (Google AI Studio or Local)
    and returns the raw text and the extracted SPARQL query.
    """
    rules = """
IMPORTANT RULES YOU MUST FOLLOW:
1. Return ONLY the SPARQL query inside ```sparql ``` block. No explanations, no reasoning.
2. NEVER use exact string matching like rdfs:label "Name". ALWAYS use fuzzy matching: FILTER(CONTAINS(LCASE(STR(?label)), "name")).
3. ALWAYS add LIMIT 100 at the end.
4. ALWAYS use SELECT DISTINCT to avoid duplicate rows.
5. When searching for works BY a person (composer, creator, artist), use cto:CTO_0001009 to link source items to creators.
   CORRECT PATTERN — always include OPTIONAL fields for richer data:
   ?item a cto:CTO_0001005 .
   ?item rdfs:label ?itemLabel .
   ?item cto:CTO_0001009 ?creator .
   ?creator rdfs:label ?creatorLabel .
   FILTER(CONTAINS(LCASE(STR(?creatorLabel)), "name"))
   OPTIONAL { ?item cto:CTO_0001072 ?creationDate . }
   OPTIONAL { ?item cto:CTO_0001073 ?creationPeriod . }
   OPTIONAL { ?item cto:CTO_0001069 ?holdingOrg . ?holdingOrg rdfs:label ?holdingOrgLabel . }
   OPTIONAL { ?item cto:CTO_0001011 ?location . ?location rdfs:label ?locationLabel . }
   OPTIONAL { ?item cto:CTO_0001068 ?shelfMark . }
6. Do NOT constrain persons with `a nfdi:NFDI_0000004` — it returns 0 results. Just use rdfs:label with FILTER.
7. Do NOT constrain locations with `a nfdi:NFDI_0000106` — it returns 0 results. Just use rdfs:label with FILTER.
8. For biographical data (birth/death dates), use a Federated Query with Wikidata.
9. When the user asks about source items in general (by title, keyword), also include OPTIONAL creator info:
   ?item a cto:CTO_0001005 .
   ?item rdfs:label ?itemLabel .
   FILTER(CONTAINS(LCASE(STR(?itemLabel)), "keyword"))
   OPTIONAL { ?item cto:CTO_0001009 ?creator . ?creator rdfs:label ?creatorLabel . }
   OPTIONAL { ?item cto:CTO_0001072 ?creationDate . }
"""
    
    prompt = f"""{SYSTEM_PROMPT}

{rules}

User Request: {user_query}
"""
    
    raw_response = call_llm(prompt)
    sparql_query = extract_sparql(raw_response)
    sparql_query = post_process_sparql(sparql_query)
    
    return {
        "raw_response": raw_response,
        "sparql_query": sparql_query
    }

def build_fallback_summary(total_count, simplified_results):
    """Build a robust, clean fallback summary if the LLM fails or is rate-limited."""
    items = []
    for row in simplified_results[:5]:
        val = ""
        # Look for typical name/label fields first
        for k in ['itemLabel', 'title', 'label', 'creatorLabel']:
            if k in row and row[k]:
                val = row[k]
                break
        if not val:
            # Look for any non-URI string value
            for k, v in row.items():
                if v and not v.startswith("http"):
                    val = v
                    break
        if not val:
            # Fall back to the last segment of any URI
            for k, v in row.items():
                if v and v.startswith("http"):
                    val = v.split('/')[-1].split('#')[-1]
                    break
        if val:
            items.append(f'"{val}"')
            
    item_list = ', '.join(items)
    if item_list:
        return f"Found {total_count} results from the Culture Knowledge Graph. Some notable items include: {item_list}."
    else:
        return f"Found {total_count} results from the Culture Knowledge Graph."

def generate_summary(user_query, sparql_query, json_results):
    """
    Takes the JSON results and generates a conversational, analytical summary.
    The summary should feel like a research assistant explaining findings.
    """
    import json
    
    simplified_results = []
    if isinstance(json_results, dict):
        res_data = json_results.get("results", [])
        if isinstance(res_data, list):
            simplified_results = res_data
        elif isinstance(res_data, dict):
            # Standard SPARQL JSON results format has a "bindings" list
            bindings = res_data.get("bindings", [])
            for b in bindings:
                row = {}
                for k, v in b.items():
                    if isinstance(v, dict) and "value" in v:
                        row[k] = v["value"]
                    else:
                        row[k] = str(v)
                simplified_results.append(row)
    elif isinstance(json_results, list):
        simplified_results = json_results
        
    total_count = len(simplified_results)
    
    # Clean data: remove ugly URIs, keep only human-readable fields
    clean_items = []
    for row in simplified_results[:20]:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, str) and v.startswith("http"):
                continue  # Skip URI values — they're in the table already
            clean_row[k] = v
        if clean_row:
            clean_items.append(clean_row)
            
    # Fallback if cleaning removed all columns (e.g. only URIs were returned)
    if not clean_items and simplified_results:
        for row in simplified_results[:20]:
            clean_items.append({k: (v.split('/')[-1].split('#')[-1] if isinstance(v, str) and v.startswith("http") else v) for k, v in row.items()})
    
    data_str = json.dumps(clean_items, ensure_ascii=False, indent=2)
    
    prompt = f"""You are an expert musicological research assistant analyzing results from the Culture Knowledge Graph.

User Research Question: "{user_query}"
Total Results Retrieved: {total_count}
Sample Data:
{data_str}

Analyze the data sample above and write a direct, conversational summary for the researcher in 3 to 4 sentences. 
Start directly by stating how many results were found, then explain the main themes or types of items in this dataset, mention a couple of notable examples by name, and end with a thought-provoking follow-up question.

Do not use headers, do not include numbered steps or bullet points, and do not explain your thought process. Output only the final paragraph."""
    import time
    
    cleaned = ""
    for attempt in range(3):
        try:
            raw = call_llm(prompt, use_summary_model=True)
            if "Error" in raw:
                raise Exception(raw)
                
            lines = raw.split('\n')
            final_lines = []
            
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('*') and len(stripped) > 2:
                    continue
                if re.match(r'^\d+\.\s+(State|Describe|Highlight|Suggest|Output|Write|No |If )', stripped):
                    continue
                if not final_lines and not stripped:
                    continue
                final_lines.append(line)
            
            cleaned = '\n'.join(final_lines).strip()
            if len(cleaned) >= 15 and cleaned.count('*') <= 5:
                break
        except Exception as e:
            print(f"[SUMMARY] Attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(2)
                
    if not cleaned or len(cleaned) < 15 or cleaned.count('*') > 5:
        print("[SUMMARY] Using fallback summary.")
        cleaned = build_fallback_summary(total_count, simplified_results)
        
    if len(cleaned) > 1500:
        cleaned = cleaned[:1400] + '...'
        
    return cleaned

def get_matching_entity_from_table(question, table_results):
    """
    Checks if the user's question mentions any composer or item from the table
    in order to fetch their Wikidata card.
    Uses structural matching (e.g., matching the last name before comma, 
    or checking word boundaries) to avoid false matches on common words.
    """
    import re
    potential_names = set()
    name_columns = ['creatorLabel', 'authorLabel', 'personLabel', 'itemLabel', 'title', 'label']
    for row in table_results:
        for col in name_columns:
            val = row.get(col, "")
            if val and isinstance(val, str) and not val.startswith("http") and len(val) > 2:
                potential_names.add(val)
                
    # Extract lowercase words from the question using regex to ensure whole-word matching
    q_words = set(re.findall(r'\b\w+\b', question.lower()))
    
    for name in potential_names:
        name_lower = name.lower()
        # 1. Direct full match (e.g. "Johann Sebastian Bach" in "Who is Johann Sebastian Bach?")
        if name_lower in question.lower():
            return name
            
        # 2. Check if name is formatted as "Last, First" (e.g., "Delsenbach, Johann Adam")
        # In RISM, the part before the comma is the last name. The last name must be explicitly
        # mentioned as a whole word in the user's question to be considered a match.
        if ',' in name:
            parts = [p.strip().lower() for p in name.split(',')]
            last_name = parts[0]
            if len(last_name) > 2 and last_name in q_words:
                return name
        else:
            # 3. If no comma, check if any word of the name (length > 3) matches as a whole word in the question
            name_words = set(re.findall(r'\b\w+\b', name_lower))
            for nw in name_words:
                if len(nw) > 3 and nw in q_words:
                    return name
                    
    return None

def extract_entity_name_from_question(question):
    """
    Attempts to extract a person's name or search topic from phrases like
    'who is X', 'من هو X', 'search wikipedia for X', 'ابحث عن X', etc.
    """
    import re
    # Patterns for English/Arabic queries
    patterns = [
        r'(?:who is|who was|tell me about|search wikipedia for|search for|about|info on|details of)\s+(.+)',
        r'(?:من هو|من هي|من يكون|ابحث عن|ابحث في ويكيبيديا عن|معلومات عن|اخبرني عن|تفاصيل عن)\s+(.+)'
    ]
    for pattern in patterns:
        m = re.search(pattern, question, re.IGNORECASE)
        if m:
            target = m.group(1).strip()
            # Clean up trailing punctuation
            target = re.sub(r'[\?\!\.\،\:\;\-\_]+$', '', target).strip()
            if len(target) > 2:
                return target
                
    # Fallback: if there are no search keywords, let's see if the query has 1 to 4 words
    q_clean = re.sub(r'[\?\!\.\،]+$', '', question).strip()
    words = q_clean.split()
    if 1 <= len(words) <= 4:
        return q_clean
        
    return None

def generate_chat_response(question, table_results, chat_history):
    """
    Answers a question about the active results table.
    Enriches with Wikidata/Wikipedia if a composer/person name is detected in the prompt or matches table items.
    """
    # Try resolving name against table results first (highest specificity)
    matched_name = get_matching_entity_from_table(question, table_results)
    
    # If no table match, extract the name directly from the user's question (flexible external search)
    if not matched_name:
        matched_name = extract_entity_name_from_question(question)
        
    wikidata_context = ""
    wikidata_card = None
    
    if matched_name:
        from wikidata_client import search_wikidata_person
        # Clean up name format for optimal Wikidata query (e.g. convert "Last, First" to "First Last")
        search_query = matched_name
        if ',' in matched_name:
            parts = [p.strip() for p in matched_name.split(',')]
            if len(parts) == 2:
                search_query = f"{parts[1]} {parts[0]}"
                
        print(f"[CHAT] Querying Wikidata for: {search_query}...")
        wiki_res = search_wikidata_person(search_query)
        if wiki_res:
            wikidata_card = wiki_res
            summary_part = f"\n- Wikipedia Summary Extract: {wiki_res['wikipedia_summary']}" if wiki_res.get('wikipedia_summary') else ""
            wikidata_context = f"""
[Wikidata & Wikipedia Enrichment Context]
We searched Wikidata and Wikipedia for "{search_query}" and found:
- Name: {wiki_res['label']}
- Description: {wiki_res['description']}
- Birth Date: {wiki_res['birthDate']}
- Death Date: {wiki_res['deathDate']}
- Wikipedia URL: {wiki_res['wikipedia_url']}{summary_part}
- Image URL: {wiki_res['image']}
- GND ID: {wiki_res.get('gnd_id')}
- MIMO ID: {wiki_res.get('mimo_id')}

Please answer the user's question using this Wikipedia summary context. Explain the details in the user's query language (e.g. Arabic if they asked in Arabic). If there is an image, mention that you have displayed a visual card with their portrait and external links (Wikipedia, GND, and MIMO where available).
"""

    import json
    data_sample = json.dumps(table_results[:20], ensure_ascii=False, indent=2)
    
    history_context = ""
    if chat_history:
        history_context = "Conversation history:\n"
        for msg in chat_history[-6:]:
            role = "User" if msg.get("sender") == "user" else "Assistant"
            history_context += f"{role}: {msg.get('text')}\n"
            
    system_instruction = (
        "You are an expert musicological research assistant. Your job is to help the researcher analyze the "
        "active results table, converse with them about the data, and answer their questions. You have access "
        "to a table and sometimes to external Wikidata/Wikipedia biography context if relevant."
    )
    
    prompt = f"""Active results table data (first 20 rows):
{data_sample}
 
{wikidata_context}

{history_context}
User's Question: "{question}"

Instructions:
1. Answer the user's question directly and conversationally using the table data, history, and any provided Wikidata/Wikipedia context.
2. If Wikidata context is provided, integrate it into your explanation (mentioning that you've shown their portrait and links to Wikipedia, GND, and MIMO where available).
3. If no Wikidata/Wikipedia context is provided (or if the question is a general analytical question about the table), answer directly using the table data. Do NOT mention that Wikidata information was not found or is missing unless the user specifically asked you to search for it.
4. Keep the response highly structured (using lists or bold text), professional, and in the user's language (e.g. Arabic if they ask in Arabic).
"""

    raw_response = call_llm(prompt, system_instruction=system_instruction)
    
    return {
        "text": raw_response,
        "wikidata_card": wikidata_card
    }

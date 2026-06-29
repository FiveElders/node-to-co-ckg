from flask import Flask, render_template, request, jsonify
from agent import generate_sparql
from sparql_client import execute_sparql

app = Flask(__name__)

# Disable caching for development
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ask", methods=["POST"])
def ask_question():
    """Endpoint for generating SPARQL from Natural Language."""
    data = request.json
    user_query = data.get("question", "")
    
    if not user_query:
        return jsonify({"error": "No question provided"}), 400
        
    # Step 1: LLM translates NLP to SPARQL
    ai_result = generate_sparql(user_query)
    
    if "Error" in ai_result.get("sparql_query", ""):
         return jsonify({
             "success": False,
             "sparql": ai_result["sparql_query"],
             "error": ai_result["sparql_query"] # تمرير رسالة الخطأ الحقيقية
         })
         
    return jsonify({
        "success": True,
        "sparql": ai_result["sparql_query"],
        "raw_response": ai_result["raw_response"]
    })

@app.route("/api/execute", methods=["POST"])
def run_query():
    """Endpoint for executing a given SPARQL query."""
    data = request.json
    sparql_query = data.get("query", "")
    user_query = data.get("question", "")
    
    if not sparql_query:
        return jsonify({"success": False, "error": "No query provided"}), 400
        
    # Step 2: Execute SPARQL against CKG endpoint
    execution_result = execute_sparql(sparql_query)
    
    # Run diagnostic check-up if query returns no results
    if execution_result.get("success") and len(execution_result.get("results", [])) == 0:
        from sparql_diagnose import diagnose_empty_results
        diagnostic = diagnose_empty_results(sparql_query, user_query or "Direct Query")
        execution_result["diagnostic"] = diagnostic
        
    return jsonify(execution_result)

@app.route("/api/summarize", methods=["POST"])
def summarize_results():
    """Endpoint for generating a natural language summary of SPARQL results."""
    from agent import generate_summary
    data = request.json
    user_query = data.get("question", "")
    sparql_query = data.get("sparql", "")
    json_results = data.get("results", {})
    
    summary = generate_summary(user_query, sparql_query, json_results)
    
    return jsonify({"success": True, "summary": summary})

@app.route("/api/config", methods=["POST"])
def config_models():
    """Endpoint to update LLM key and local configuration."""
    from agent import update_config, CONFIG
    data = request.json
    api_key = data.get("api_key", "").strip()
    run_local = data.get("run_local", False)
    local_url = data.get("local_url", "").strip()
    local_model = data.get("local_model", "").strip()
    
    update_config(
        api_key=api_key if api_key else None,
        run_local=run_local,
        local_url=local_url if local_url else None,
        local_model=local_model if local_model else None
    )
    
    return jsonify({
        "success": True,
        "config": {
            "run_local": CONFIG["run_local"],
            "local_model_name": CONFIG["local_model_name"],
            "local_llm_url": CONFIG["local_llm_url"],
            "has_api_key": bool(CONFIG["google_api_key"])
        }
    })

@app.route("/api/chat_results", methods=["POST"])
def chat_results():
    """Endpoint for asking questions about the active results table."""
    from agent import generate_chat_response
    data = request.json
    question = data.get("question", "")
    table_results = data.get("results", [])
    chat_history = data.get("history", [])
    
    if not question:
        return jsonify({"success": False, "error": "No question provided"}), 400
        
    chat_res = generate_chat_response(question, table_results, chat_history)
    return jsonify({
        "success": True,
        "text": chat_res["text"],
        "wikidata_card": chat_res["wikidata_card"]
    })

if __name__ == "__main__":
    app.run(debug=True, port=5050)


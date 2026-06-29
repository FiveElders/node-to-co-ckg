import rdflib
import os

def generate_agent_cheat_sheet(owl_file, ttl_file, output_filename="agent_cheat_sheet.txt"):
    print("🚀 جاري بناء دماغ الوكيل الذكي (Agent Schema)...")
    
    # 1. إنشاء مساحة عمل (Graph) في الذاكرة لدمج الملفين
    g = rdflib.Graph()
    
    # 2. تحميل ملف OWL (غالباً يكون مكتوباً بصيغة RDF/XML)
    if os.path.exists(owl_file):
        print(f"📥 جاري قراءة ملف OWL: {owl_file}")
        g.parse(owl_file, format="xml")
    else:
        print(f"⚠️ تحذير: الملف {owl_file} غير موجود.")

    # 3. تحميل ملف TTL (مكتوب بصيغة Turtle)
    if os.path.exists(ttl_file):
        print(f"📥 جاري قراءة ملف TTL: {ttl_file}")
        g.parse(ttl_file, format="turtle")
    else:
        print(f"⚠️ تحذير: الملف {ttl_file} غير موجود.")
            
    print(f"✅ تم دمج {len(g)} عبارة دلالية من الملفين بنجاح.")

    # 4. استعلام SPARQL لاستخراج القاموس المفلتر (مُحسّن لجلب النطاق والمجال والتسلسل الهرمي)
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT DISTINCT ?uri ?type ?label ?domain ?range ?subClass WHERE {
      VALUES ?type { owl:Class owl:ObjectProperty owl:DatatypeProperty rdf:Property }
      ?uri a ?type .
      OPTIONAL { 
          ?uri rdfs:label ?label .
          FILTER(LANG(?label) = "en" || LANG(?label) = "") 
      }
      OPTIONAL { ?uri rdfs:domain ?domain . FILTER(!isBlank(?domain)) }
      OPTIONAL { ?uri rdfs:range ?range . FILTER(!isBlank(?range)) }
      OPTIONAL { ?uri rdfs:subClassOf ?subClass . FILTER(!isBlank(?subClass)) }
      
      # الفلتر الشامل: الموسيقى (cto) + الأساس (nfdi) + خصائص عالمية (schema, dcterms)
      FILTER(
          CONTAINS(STR(?uri), "nfdi4culture") || 
          CONTAINS(STR(?uri), "nfdi.fiz-karlsruhe") || 
          CONTAINS(STR(?uri), "schema.org") ||
          CONTAINS(STR(?uri), "purl.org/dc/terms") ||
          CONTAINS(STR(?uri), "skos/core")
      )
    }
    """
    
    print("🔍 جاري فلترة البيانات واستخراج المصطلحات وتحديد نطاقاتها...")
    results = g.query(query)
    
    # 5. تصنيف النتائج
    agent_dictionary = {
        "Classes (Nodes / الكيانات)": {},
        "Object Properties (Edges / روابط الكيانات)": {},
        "Data Properties (Filters / الفلاتر والخصائص)": {}
    }

    def simplify_uri(u):
        if not u: return None
        return str(u).replace("https://nfdi4culture.de/ontology/", "cto:")\
                     .replace("https://nfdi.fiz-karlsruhe.de/ontology/", "nfdi:")\
                     .replace("https://schema.org/", "schema:")\
                     .replace("http://purl.org/dc/terms/", "dcterms:")\
                     .replace("http://www.w3.org/2004/02/skos/core#", "skos:")\
                     .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:")\
                     .replace("http://www.w3.org/2001/XMLSchema#", "xsd:")\
                     .replace("http://www.w3.org/2002/07/owl#", "owl:")
    
    for row in results:
        uri = str(row.uri)
        type_uri = str(row.type)
        label = str(row.label) if row.label else uri.split('/')[-1].split('#')[-1]
        
        simplified_uri = simplify_uri(uri)
        domain = simplify_uri(row.domain)
        range_ = simplify_uri(row.range)
        subclass = simplify_uri(row.subClass)
        
        entry = f"- {label}: {simplified_uri}"
        
        # إضافة المعلومات الإضافية (Domain, Range, SubClassOf)
        extras = []
        if subclass: extras.append(f"SubClassOf: {subclass}")
        if domain: extras.append(f"Domain: {domain}")
        if range_: extras.append(f"Range: {range_}")
        
        if extras:
            entry += f" ({', '.join(extras)})"
            
        if "Class" in type_uri:
            if simplified_uri not in agent_dictionary["Classes (Nodes / الكيانات)"]:
                agent_dictionary["Classes (Nodes / الكيانات)"][simplified_uri] = entry
        elif "ObjectProperty" in type_uri:
            if simplified_uri not in agent_dictionary["Object Properties (Edges / روابط الكيانات)"]:
                agent_dictionary["Object Properties (Edges / روابط الكيانات)"][simplified_uri] = entry
        elif "DatatypeProperty" in type_uri or "Property" in type_uri:
            if simplified_uri not in agent_dictionary["Data Properties (Filters / الفلاتر والخصائص)"]:
                agent_dictionary["Data Properties (Filters / الفلاتر والخصائص)"][simplified_uri] = entry

    # 6. حفظ النتيجة في ملف نصي
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("=== NFDI4Culture Musicological Knowledge Graph Schema ===\n")
        f.write("System Instruction: You are an expert musicological AI agent. When generating SPARQL queries, strictly use ONLY the following classes and properties. Do not invent any vocabularies outside this list.\n\n")
        
        f.write("[Prefixes]\n")
        f.write("PREFIX nfdi: <https://nfdi.fiz-karlsruhe.de/ontology/>\n")
        f.write("PREFIX cto: <https://nfdi4culture.de/ontology/>\n")
        f.write("PREFIX schema: <https://schema.org/>\n")
        f.write("PREFIX dcterms: <http://purl.org/dc/terms/>\n")
        f.write("PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n")
        f.write("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n")
        f.write("PREFIX owl: <http://www.w3.org/2002/07/owl#>\n\n")

        for category, items_dict in agent_dictionary.items():
            f.write(f"[{category}]\n")
            unique_items = sorted(list(items_dict.values()))
            for item in unique_items:
                f.write(f"{item}\n")
            f.write("\n")

        # 7. إضافة أمثلة Few-Shot Prompting
        f.write("[Example Queries]\n")
        f.write("Example 1: Find a person's birth date\n")
        f.write("```sparql\n")
        f.write("PREFIX nfdi: <https://nfdi.fiz-karlsruhe.de/ontology/>\n")
        f.write("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n")
        f.write("SELECT ?birthDate WHERE {\n")
        f.write("  ?person a nfdi:NFDI_0000004 .\n")
        f.write("  ?person rdfs:label \"Ludwig van Beethoven\" .\n")
        f.write("  ?person nfdi:NFDI_0000105 ?birthDate .\n")
        f.write("}\n")
        f.write("```\n\n")
        
        f.write("Example 2: Find source items (e.g. manuscripts) related to a specific person\n")
        f.write("```sparql\n")
        f.write("PREFIX cto: <https://nfdi4culture.de/ontology/>\n")
        f.write("PREFIX nfdi: <https://nfdi.fiz-karlsruhe.de/ontology/>\n")
        f.write("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n")
        f.write("SELECT ?sourceItem ?title WHERE {\n")
        f.write("  ?person a nfdi:NFDI_0000004 .\n")
        f.write("  ?person rdfs:label \"Ludwig van Beethoven\" .\n")
        f.write("  ?sourceItem a cto:CTO_0001005 .\n")
        f.write("  ?sourceItem cto:CTO_0001009 ?person .\n")
        f.write("  ?sourceItem rdfs:label ?title .\n")
        f.write("}\n")
        f.write("```\n")
            
    print(f"🎉 تم الانتهاء! افتح الملف '{output_filename}' لنسخ التعليمات للـ Agent.")

# =========================================================
# ضع أسماء ملفاتك هنا (تأكد أنها في نفس مجلد السكربت)
# =========================================================
my_owl_file = "cto.owl"         # اسم ملف الـ OWL (غالباً يخص الموسيقى)
my_ttl_file = "ontology.ttl"    # اسم ملف الـ TTL (غالباً يخص الأساس)

generate_agent_cheat_sheet(my_owl_file, my_ttl_file)
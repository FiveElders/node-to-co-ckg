# Jury Simulation Test Report

This report documents the automated evaluation of the Musicological Knowledge Graph Agent against a series of target queries designed to simulate a technical jury review.

## Summary Table

| Test Area / Target | Status | Details |
| :--- | :--- | :--- |
| Pillar 1: List source items created by someone named Bach | ✅ PASSED | Returned 100 rows. |
| Pillar 1: Find source items with Altar in their title | ✅ PASSED | Returned 100 rows. |
| Pillar 1: Find source items related to Leipzig | ✅ PASSED | Returned 100 rows. |
| Pillar 2: Johann Sebastian Bach ID matching | ✅ PASSED | GND matches: True, MIMO matches: True |
| Pillar 2: Violin ID matching | ✅ PASSED | GND matches: True, MIMO matches: True |
| Pillar 2: Harpsichord ID matching | ✅ PASSED | GND matches: True, MIMO matches: True |
| Pillar 3: Zero-Result Diagnostics | ✅ PASSED | Successfully identified empty search filters and suggested valid database options. |

## Pillars Evaluated

### 1. SPARQL Generation and Live CKG Execution
Evaluates the agent's capability to parse unstructured natural language questions and compile them into standard, syntax-compliant SPARQL queries, executing them in real-time against the NFDI4Culture endpoint.

### 2. Authority Hub Interoperability (GND & MIMO)
Verifies the precision of the dynamic Linked Open Data (LOD) connector. Resolves Wikidata records, matching GND IDs (German National Library) for individuals and MIMO IDs (Musical Instrument Museums Online) for instrument objects.

### 3. Zero-Result Diagnostic Engine
Checks if the system handles queries with correct grammar but empty matches (e.g. nonexistent composers) by automatically stripping filters, verifying ontology populations, and recommending real database alternatives.

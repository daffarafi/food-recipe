import os
from dotenv import load_dotenv
from SPARQLWrapper import SPARQLWrapper, JSON, BASIC
from django.shortcuts import render
from fuzzywuzzy import process
from urllib.parse import unquote

load_dotenv()

def find_similar_recipes(query, all_titles):
    # Find the single best match using fuzzy matching
    best_match = process.extractOne(query, all_titles, score_cutoff=70)
    return best_match[0] if best_match else None

def perform_sparql_search(query):
    # Setup SPARQL connection
    sparql = SPARQLWrapper(os.getenv("GRAPHDB_REPO_URL"))
    sparql.setCredentials(os.getenv("GRAPHDB_USER"), os.getenv("GRAPHDB_PASSWORD"))
    sparql.setHTTPAuth(BASIC)
    sparql.setReturnFormat(JSON)

    # Construct SPARQL query for recipes
    sparql_query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX vocab: <https://food-recipe.up.railway.app/vocab#>

    SELECT DISTINCT ?title
    WHERE {
        ?recipe rdfs:label ?title .
    }
    """

    sparql.setQuery(sparql_query)
    results = sparql.queryAndConvert()['results']['bindings']

    # Extract titles from results
    return [result['title']['value'] for result in results]

def search_recipes(query):
    # Setup SPARQL connection
    sparql = SPARQLWrapper(os.getenv("GRAPHDB_REPO_URL"))
    sparql.setCredentials(os.getenv("GRAPHDB_USER"), os.getenv("GRAPHDB_PASSWORD"))
    sparql.setHTTPAuth(BASIC)
    sparql.setReturnFormat(JSON)

    # Construct SPARQL query for search
    sparql_query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX vocab: <https://food-recipe.up.railway.app/vocab#>

    SELECT DISTINCT ?food
    WHERE {{
        ?food vocab:hasRecipe ?recipe .
        ?recipe rdfs:label ?title .

        # Optional fields
        OPTIONAL {{ ?recipe vocab:cuisineOf/rdfs:label ?cuisine }}
        OPTIONAL {{ ?recipe vocab:hasCategory/rdfs:label ?category }}
        OPTIONAL {{ ?recipe vocab:hasTags/rdfs:label ?tags }}

        # Match the query in any of these fields
        FILTER(
            CONTAINS(LCASE(?title), LCASE("{query}")) ||
            CONTAINS(LCASE(?cuisine), LCASE("{query}")) ||
            CONTAINS(LCASE(?category), LCASE("{query}")) ||
            CONTAINS(LCASE(?tags), LCASE("{query}"))
        )
    }}
    GROUP BY ?food
    LIMIT 50
    """

    sparql.setQuery(sparql_query)
    return sparql.queryAndConvert()['results']['bindings']

def search_view(request):
    query = request.GET.get('q', '').strip()
    
    if not query:
        return render(request, 'search/search_results.html', {'results': [], 'query': query})

    # Fetch all recipe titles for fuzzy matching
    all_titles = perform_sparql_search(None)
    
    # Perform search and check for results
    search_results = search_recipes(query)
    suggestion = None
    if not search_results:
        # Generate a single suggestion if no results are found
        suggestion = find_similar_recipes(query, all_titles)

    # Add slugified names and decoded titles to results
    for result in search_results:
        slug = result['food']['value'].split('/')[-1]
        decoded_title = unquote(slug).replace('_', ' ')
        result['slug'] = slug
        result['food_title'] = decoded_title

    # Prepare context
    context = {
        'results': search_results,
        'query': query,
        'suggestion': suggestion,
    }

    return render(request, 'search/search_results.html', context)


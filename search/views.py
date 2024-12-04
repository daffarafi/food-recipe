import os
from dotenv import load_dotenv
from SPARQLWrapper import SPARQLWrapper, JSON, BASIC
from django.shortcuts import render
from fuzzywuzzy import process
from urllib.parse import unquote
from django.core.paginator import Paginator

load_dotenv()

# Utility to set up SPARQL connection
def get_sparql_connection():
    sparql = SPARQLWrapper(os.getenv("GRAPHDB_REPO_URL"))
    sparql.setCredentials(os.getenv("GRAPHDB_USER"), os.getenv("GRAPHDB_PASSWORD"))
    sparql.setHTTPAuth(BASIC)
    sparql.setReturnFormat(JSON)
    return sparql

# Fetch all recipe titles
def get_all_titles():
    sparql = get_sparql_connection()
    sparql_query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX vocab: <https://food-recipe.up.railway.app/vocab#>

    SELECT DISTINCT ?title
    WHERE {
        ?recipe rdfs:label ?title .
    }
    """
    sparql.setQuery(sparql_query)
    try:
        results = sparql.queryAndConvert()['results']['bindings']
        return [result['title']['value'].lower() for result in results]
    except Exception as e:
        print(f"Error fetching titles: {e}")
        return []

# Find the best suggestion using fuzzy matching
def find_similar_recipes(query, all_titles):
    best_match = process.extractOne(query.lower(), all_titles, score_cutoff=70)
    return best_match[0] if best_match else None

# Perform recipe search
def search_recipes(query):
    sparql = get_sparql_connection()
    sparql_query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX vocab: <https://food-recipe.up.railway.app/vocab#>

    SELECT DISTINCT ?food
    WHERE {{
        ?food vocab:hasRecipe ?recipe .
        ?recipe rdfs:label ?title .
        OPTIONAL {{ ?recipe vocab:cuisineOf/rdfs:label ?cuisine }}
        OPTIONAL {{ ?recipe vocab:hasCategory/rdfs:label ?category }}
        OPTIONAL {{ ?recipe vocab:hasTags/rdfs:label ?tags }}

        FILTER(
            CONTAINS(LCASE(?title), LCASE("{query}")) ||
            CONTAINS(LCASE(?cuisine), LCASE("{query}")) ||
            CONTAINS(LCASE(?category), LCASE("{query}")) ||
            CONTAINS(LCASE(?tags), LCASE("{query}"))
        )
    }}
    GROUP BY ?food
    """
    sparql.setQuery(sparql_query)
    try:
        results = sparql.queryAndConvert()['results']['bindings']
        for result in results:
            slug = result['food']['value'].split('/')[-1]
            decoded_title = unquote(slug).replace('_', ' ')
            result['slug'] = slug
            result['food_title'] = decoded_title
        return results
    except Exception as e:
        print(f"Error performing search: {e}")
        return []

# View to handle recipe search
def search_view(request):
    query = request.GET.get('q', '').strip()
    page_number = request.GET.get('page', 1)  # Get current page from request
    if not query:
        return render(request, 'search/search_results.html', {'results': [], 'query': query})

    # Fetch all recipe titles for fuzzy matching
    all_titles = get_all_titles()

    # Perform search
    search_results = search_recipes(query)

    # Generate suggestion if no results are found
    suggestion = None if search_results else find_similar_recipes(query, all_titles)

    # Pagination setup
    paginator = Paginator(search_results, 50)  # Show 50 results per page
    current_page = paginator.get_page(page_number)

    # Prepare context
    context = {
        'results': current_page,
        'query': query,
        'suggestion': suggestion,
    }
    return render(request, 'search/search_results.html', context)

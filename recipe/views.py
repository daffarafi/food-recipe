import os
from dotenv import load_dotenv
from SPARQLWrapper import SPARQLWrapper, JSON, BASIC
from django.shortcuts import render
from django.http import Http404

load_dotenv()

def query_ingredient_from_wikidata(ingredient_label):
    """
    Query Wikidata to fetch a URL for the given ingredient label.
    """
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setReturnFormat(JSON)
    
    wikidata_query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX schema: <http://schema.org/>

    SELECT DISTINCT ?wikidataItem ?url
    WHERE {{
        ?wikidataItem rdfs:label "{ingredient_label}"@id .
        OPTIONAL {{ ?wikidataItem schema:about ?url . }}
    }} LIMIT 1
    """

    sparql.setQuery(wikidata_query)
    results = sparql.queryAndConvert().get('results', {}).get('bindings', [])
    if not results:
        return None

    result = results[0]
    return result['wikidataItem']['value']

def recipe_detail_view(request, recipe_name):
    # Query GraphDB for recipe details
    sparql = SPARQLWrapper(os.getenv("GRAPHDB_REPO_URL"))
    sparql.setCredentials(os.getenv("GRAPHDB_USER"), os.getenv("GRAPHDB_PASSWORD"))
    sparql.setHTTPAuth(BASIC)
    sparql.setReturnFormat(JSON)

    sparql_query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX vocab: <https://food-recipe.up.railway.app/vocab#>
    PREFIX base: <https://food-recipe.up.railway.app/data/>

    SELECT ?recipe ?title ?url ?description ?prepTime ?cookTime 
           ?cuisine ?category ?ingredients ?instructions
    WHERE {{
        ?food vocab:hasRecipe ?recipe .
        FILTER(CONTAINS(STR(?food), "{recipe_name}"))
        ?recipe rdfs:label ?title .

        OPTIONAL {{ ?recipe vocab:hasUrl ?url }}
        OPTIONAL {{ ?recipe vocab:hasDescription ?description }}
        OPTIONAL {{ ?recipe vocab:hasPrepTime ?prepTime }}
        OPTIONAL {{ ?recipe vocab:hasCookTime ?cookTime }}
        OPTIONAL {{ ?recipe vocab:cuisineOf/rdfs:label ?cuisine }}
        OPTIONAL {{ ?recipe vocab:hasCategory/rdfs:label ?category }}
        OPTIONAL {{ ?recipe vocab:hasIngredients/vocab:ingredient/rdfs:label ?ingredients }}
        OPTIONAL {{ ?recipe vocab:hasInstructions ?instructions }}
    }}
    """

    sparql.setQuery(sparql_query)
    results = sparql.queryAndConvert()['results']['bindings']

    if not results:
        raise Http404("Recipe not found")

    # Process GraphDB results
    recipes = {}
    for result in results:
        recipe_id = result['recipe']['value']
        if recipe_id not in recipes:
            recipes[recipe_id] = {
                'title': result.get('title', {}).get('value', ''),
                'url': result.get('url', {}).get('value', ''),
                'description': result.get('description', {}).get('value', ''),
                'prepTime': result.get('prepTime', {}).get('value', ''),
                'cookTime': result.get('cookTime', {}).get('value', ''),
                'cuisine': result.get('cuisine', {}).get('value', ''),
                'category': result.get('category', {}).get('value', ''),
                'ingredients': [],
                'instructions': []
            }
        # Handle ingredients
        if 'ingredients' in result:
            ingredient = result['ingredients']['value']
            ingredient_url = query_ingredient_from_wikidata(ingredient)
            recipes[recipe_id]['ingredients'].append({
                'label': ingredient,
                'url': ingredient_url
            })
        # Handle instructions
        if 'instructions' in result:
            instructions = result['instructions']['value'].split('|')
            recipes[recipe_id]['instructions'] = instructions

    # Convert recipes to a list
    recipe_list = list(recipes.values())

    print(recipe_list[0]['ingredients'])

    context = {
        'recipes': recipe_list
    }

    return render(request, 'recipe/recipe_list.html', context)
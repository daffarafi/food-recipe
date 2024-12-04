import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from SPARQLWrapper import SPARQLWrapper, JSON, BASIC
from django.shortcuts import render
from django.http import Http404
import re

load_dotenv()

class WikidataIngredientService:
    @classmethod
    async def batch_query_ingredients(cls, ingredients):
        """
        Batch query ingredients from Wikidata with async support.
        """
        # Prepare Wikidata batch query
        async with aiohttp.ClientSession() as session:
            wikidata_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX wdt: <http://www.wikidata.org/prop/direct/>
            PREFIX wd: <http://www.wikidata.org/entity/>
            PREFIX schema: <http://schema.org/>

            SELECT DISTINCT ?label ?wikidataItem ?url
            WHERE {{
                VALUES ?label {{ {" ".join(f'"{ingredient}"@id' for ingredient in ingredients)} }}
                ?wikidataItem rdfs:label ?label .
                OPTIONAL {{ ?wikidataItem schema:about ?url . }}
            }}
            """

            async with session.post(
                'https://query.wikidata.org/sparql',
                headers={'Accept': 'application/sparql-results+json'},
                data={'query': wikidata_query}
            ) as response:
                results = await response.json()

        # Process results
        ingredient_urls = {}
        for result in results['results']['bindings']:
            ingredient = result['label']['value']
            wikidata_url = result.get('wikidataItem', {}).get('value')
            schema_url = result.get('url', {}).get('value', '')
            ingredient_urls[ingredient] = schema_url or wikidata_url

        return ingredient_urls

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
        ?cuisine ?category ?ingredients ?instructions ?steps 
        ?dietType ?recordHealth ?rating ?totalLikes ?totalSteps ?totalIngredients
        ?author ?tags ?voteCount ?courseFor
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
        OPTIONAL {{ ?recipe vocab:hasSteps ?steps }}
        OPTIONAL {{ ?recipe vocab:hasDietType/rdfs:label ?dietType }}
        OPTIONAL {{ ?recipe vocab:hasRecordHealth ?recordHealth }}
        OPTIONAL {{ ?recipe vocab:hasRating ?rating }}
        OPTIONAL {{ ?recipe vocab:totalLikes ?totalLikes }}
        OPTIONAL {{ ?recipe vocab:totalSteps ?totalSteps }}
        OPTIONAL {{ ?recipe vocab:totalIngredients ?totalIngredients }}
        OPTIONAL {{ ?recipe vocab:hasAuthor/rdfs:label ?author }}
        OPTIONAL {{ ?recipe vocab:hasTags/rdfs:label ?tags }}
        OPTIONAL {{ ?recipe vocab:voteCount ?voteCount }}
        OPTIONAL {{ ?recipe vocab:courseFor/rdfs:label ?courseFor }}
    }}
    """

    sparql.setQuery(sparql_query)
    results = sparql.queryAndConvert()['results']['bindings']

    if not results:
        raise Http404("Recipe not found")
    
    # Collect unique ingredients
    unique_ingredients = set()
    for result in results:
        if 'ingredients' in result:
            unique_ingredients.add(result['ingredients']['value'])

    # Query Wikidata for unique ingredients
    ingredient_urls = asyncio.run(
        WikidataIngredientService.batch_query_ingredients(list(unique_ingredients))
    )

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
                'ingredients': {},
                'instructions': [],
                'dietType': result.get('dietType', {}).get('value', ''),
                'recordHealth': result.get('recordHealth', {}).get('value', ''),
                'rating': result.get('rating', {}).get('value', ''),
                'totalLikes': result.get('totalLikes', {}).get('value', ''),
                'totalSteps': result.get('totalSteps', {}).get('value', ''),
                'totalIngredients': result.get('totalIngredients', {}).get('value', ''),
                'author': result.get('author', {}).get('value', ''),
                'tags': {},
                'voteCount': result.get('voteCount', {}).get('value', ''),
                'courseFor': result.get('courseFor', {}).get('value', '')
            }
        # Handle ingredients
        if 'ingredients' in result:
            ingredient = result['ingredients']['value']
            ingredient_url = ingredient_urls.get(ingredient)
            recipes[recipe_id]['ingredients'][ingredient] = {
                'label': ingredient,
                'url': ingredient_url
            }
        # Handle tags
        if 'tags' in result:
            tag = result['tags']['value']
            recipes[recipe_id]['tags'][tag] = tag
        # Handle instructions
        if 'instructions' in result:
            instructions = result['instructions']['value'].split('|')
            recipes[recipe_id]['instructions'] = instructions
        # Handle steps
        if 'steps' in result:
            steps = result['steps']['value']
            recipes[recipe_id]['instructions'] = re.split(r'\s*\d+\)\s*', steps)[1:]

    # Convert recipes to a list
    recipe_list = []
    for recipe in recipes.values():
        recipe['ingredients'] = list(recipe['ingredients'].values())
        recipe['tags'] = list(recipe['tags'].values())
        recipe_list.append(recipe)

    print(recipe_list[0])

    context = {
        'recipes': recipe_list
    }

    return render(request, 'recipe/recipe_list.html', context)

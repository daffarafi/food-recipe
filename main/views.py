import os
from dotenv import load_dotenv
from SPARQLWrapper import JSON, SPARQLWrapper, BASIC
from django.shortcuts import render
from django.http import JsonResponse

load_dotenv()

sparql = SPARQLWrapper(os.getenv("GRAPHDB_REPO_URL"))

sparql.setCredentials(os.getenv("GRAPHDB_USER"), os.getenv("GRAPHDB_PASSWORD"))
sparql.setHTTPAuth(BASIC)
sparql.setReturnFormat(JSON)


def show_main(request):
    # Taro query sparqlnya disini
    sparql.setQuery("""
        select * where {
            ?s ?p ?o .
        } limit 100
    """)

    results = sparql.queryAndConvert()['results']['bindings']

    return JsonResponse(results, safe=False)
    # return render(request, 'main.html', {"results": results})
